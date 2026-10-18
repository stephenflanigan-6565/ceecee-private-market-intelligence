import unittest
from unittest.mock import patch
from test_exporter_interruption import InterruptionSQLite,InterruptionPostgres
from pmi_export_budget import check_retained_payload_budget
from pmi_google_drive import DriveError

class BudgetChecks:
 def test_budget_exact_boundary(self):
  total=check_retained_payload_budget(self.store)
  with patch('pmi_export_budget.MAX_RETAINED_PAYLOAD_BYTES',total): self.assertEqual(check_retained_payload_budget(self.store),total)
  with patch('pmi_export_budget.MAX_RETAINED_PAYLOAD_BYTES',total-1):
   with self.assertRaisesRegex(DriveError,'retained_payload_budget_exceeded'): check_retained_payload_budget(self.store)
 def test_reject_before_snapshot_preserves_history_and_reports_failure(self):
  before=self.store.research_export_snapshot()
  with patch('pmi_export_budget.MAX_RETAINED_PAYLOAD_BYTES',0), patch.object(self.service.store,'research_export_snapshot',side_effect=AssertionError('must not materialize')):
   self.assertEqual(self.service.poll()['status'],'FAILED')
  self.assertFalse(self.client.files)
  status=self.service.status()
  self.assertEqual(status['last_outcome'],'FAILED')
  self.assertEqual(status['error_code'],'retained_payload_budget_exceeded')
  self.assertEqual(status['failure_stage'],'resource_preflight')
  after=self.store.research_export_snapshot()
  self.assertEqual(before['source_revision'],after['source_revision'])
 def test_small_export_still_verified(self):
  self.assertEqual(self.service.poll()['status'],'VERIFIED')

class SQLiteBudget(BudgetChecks,InterruptionSQLite): pass
class PostgresBudget(BudgetChecks,InterruptionPostgres): pass
