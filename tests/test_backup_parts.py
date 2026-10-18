"""Synthetic-only V2 preservation, restore, corruption and retry checks."""
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from datetime import datetime, timezone

import pmi_backup_parts as parts
from pmi_review_store import ReviewStore
from pmi_research_store import ResearchStore
from pmi_drive_export_service import DriveExportService
from test_research_export_snapshot import ResearchExportSnapshotTests
from test_drive_export_service import FakeDrive
from test_exporter_interruption import ENV

def seed(dsn):
 fixture = ResearchExportSnapshotTests()
 fixture.path=dsn; fixture.review=ReviewStore(dsn); fixture.research=ResearchStore(dsn)
 fixture.now=datetime.now(timezone.utc)
 fixture.test_full_history_sources_reviews_corrections_and_exact_notes_retained()
 return fixture.review

def empty(dsn):
 store=ReviewStore(dsn); store.initialize(); ResearchStore(dsn).initialize()
 with store._session(write=True) as c:
  store._sql(c,'DELETE FROM pmi_research_control')
 return store

class PartsSQLite(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
  self.root=Path(self.temp.name); self.store=seed(str(self.root/'source.sqlite'))
  self.client=FakeDrive(); self.service=DriveExportService(self.store.dsn,store=self.store,environment=ENV,client_factory=lambda:self.client)

 def package(self):
  directory=self.root/'parts'; directory.mkdir()
  return parts.build_package(self.store,directory),directory

 def destination(self): return empty(str(self.root/'restore.sqlite'))

 def test_complete_restore_every_record(self):
  before=self.store.research_export_snapshot()
  manifest,directory=self.package()
  folder=self.client.ensure_private_folder('synthetic',None)['id']
  remote=parts.deliver(self.client,folder,manifest,directory,'synthetic-export')
  retrieved=self.root/'retrieved'; retrieved.mkdir()
  downloaded=parts.retrieve(self.client,remote['id'],retrieved,expected_sha256=parts.sha(parts.encoded(manifest)))
  destination=self.destination()
  counts=parts.restore(destination,downloaded,retrieved)
  self.assertEqual(counts,before['manifest']['source_counts'])
  self.assertEqual(destination.research_export_snapshot()['source_revision'],before['source_revision'])
  self.assertEqual(self.store.research_export_snapshot()['source_revision'],before['source_revision'])
  with self.assertRaisesRegex(ValueError,'empty_database'): parts.restore(destination,downloaded,retrieved)

 def test_lost_ack_retry_reuses_parts_and_manifest(self):
  original=self.client.upload; failed=[False]
  def upload(*args):
   result=original(*args)
   if args[-1].startswith('part-') and not failed[0]:
    failed[0]=True; raise OSError('simulated lost acknowledgement')
   return result
  self.client.upload=upload
  self.assertEqual(self.service.poll()['status'],'FAILED')
  self.assertFalse(self.service.status()['bootstrap_verified'])
  self.assertEqual(self.service.poll()['status'],'RETRY_WAIT')
  self.assertEqual(self.service.poll(force=True)['status'],'VERIFIED')
  identities=[(value['kind'],value['name']) for value in self.client.files.values()]
  self.assertEqual(len(identities),len(set(identities)))
  self.assertEqual(self.service.poll()['status'],'IDLE')

 def test_corrupt_readback_never_verified(self):
  self.client.corrupt='part-0000'
  self.assertEqual(self.service.poll()['status'],'FAILED')
  self.assertFalse(self.service.status()['bootstrap_verified'])
  self.assertFalse(any(f['kind']=='manifest' for f in self.client.files.values()))

 def test_corrupt_or_missing_parts_no_restore(self):
  manifest,directory=self.package(); destination=self.destination()
  path=directory/'part-0000.jsonl'; path.write_bytes(path.read_bytes()+b'X')
  with self.assertRaises(ValueError): parts.restore(destination,manifest,directory)
  with destination._session() as c:
   self.assertEqual(c.execute('SELECT count(*) FROM pmi_review_events').fetchone()[0],0)
  path.unlink()
  with self.assertRaises(FileNotFoundError): parts.restore(destination,manifest,directory)

 def test_restore_rolls_back_mid_insert(self):
  manifest,directory=self.package(); destination=self.destination(); sql=destination._sql
  def fail(c,query,params=()):
   if query.startswith('INSERT INTO pmi_review_events'): raise OSError('simulated interruption')
   return sql(c,query,params)
  with patch.object(destination,'_sql',side_effect=fail):
   with self.assertRaises(OSError): parts.restore(destination,manifest,directory)
  with destination._session() as c:
   for table in parts.TABLES: self.assertEqual(c.execute('SELECT count(*) FROM '+table).fetchone()[0],0)
  parts.restore(destination,manifest,directory)

 def test_explicit_limits_and_disk_failure(self):
  with patch.object(parts,'ROW_BYTES',10):
   with self.assertRaisesRegex(ValueError,'record_too_large'): self.package()
  directory=self.root/'disk'; directory.mkdir()
  with patch.object(parts.os,'fsync',side_effect=OSError('disk full')):
   with self.assertRaises(OSError): parts.build_package(self.store,directory)
  with patch.object(parts,'MAX_PARTS',0):
   with self.assertRaisesRegex(ValueError,'package_too_large'): parts.build_package(self.store,self.root/'unused')

 def test_manifest_trust_and_schema_rejected(self):
  manifest,directory=self.package()
  remote=parts.deliver(self.client,'private-folder',manifest,directory,'synthetic-export')
  with self.assertRaisesRegex(ValueError,'manifest_readback_mismatch'):
   parts.retrieve(self.client,remote['id'],directory,expected_sha256='0'*64)
  manifest['tables']['pmi_review_events']['columns'][0]='unexpected_column'
  with self.assertRaisesRegex(ValueError,'invalid_backup_schema'): parts.validate_manifest(manifest)

 def test_failure_code_and_first_receipt_fail_closed(self):
  with patch.object(parts,'ROW_BYTES',10):
   self.assertEqual(self.service.poll()['status'],'FAILED')
  self.assertEqual(self.service.status()['error_code'],'backup_record_too_large')
  self.assertEqual(self.service.status()['failure_stage'],'snapshot')
  identities=self.client.identities
  with patch.object(self.service,'_append',side_effect=OSError('synthetic ledger unavailable')):
   with self.assertRaises(OSError): self.service.poll(force=True)
  self.assertEqual(self.client.identities,identities)

 def test_abandoned_spool_cleanup_and_unknown_file_protection(self):
  with patch.object(parts.tempfile,'gettempdir',return_value=str(self.root)):
   base=self.root/('pmi-research-v2-'+parts.sha(self.store.dsn.encode())[:24])
   old=base/'attempt-abandoned'; old.mkdir(parents=True)
   (old/'part-0000.jsonl').write_bytes(b'synthetic abandoned upload')
   with parts.spool_directory(self.store): self.assertFalse(old.exists())
   unknown=base/'do-not-delete'; unknown.write_text('synthetic user file')
   with self.assertRaisesRegex(ValueError,'spool_unsafe'):
    with parts.spool_directory(self.store): pass
   self.assertTrue(unknown.exists())

@unittest.skipUnless(os.getenv('PMI_EXPORT_TEST_PG')=='1','disposable PG not configured')
class PartsPostgres(PartsSQLite):
 def setUp(self):
  import psycopg
  self.temp=tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup); self.root=Path(self.temp.name)
  dsn='postgresql://pmi_test:disposable_test_only@127.0.0.1:5432/pmi_export_synthetic'
  with psycopg.connect(dsn,autocommit=True) as c:
   c.execute('DROP SCHEMA public CASCADE'); c.execute('CREATE SCHEMA public')
  self.store=seed(dsn); self.client=FakeDrive()
  self.service=DriveExportService(dsn,store=self.store,environment=ENV,client_factory=lambda:self.client)
 def destination(self):
  import psycopg
  dsn='postgresql://pmi_test:disposable_test_only@127.0.0.1:5432/pmi_restore_synthetic'
  with psycopg.connect(dsn,autocommit=True) as c:
   c.execute('DROP SCHEMA public CASCADE'); c.execute('CREATE SCHEMA public')
  return empty(dsn)
