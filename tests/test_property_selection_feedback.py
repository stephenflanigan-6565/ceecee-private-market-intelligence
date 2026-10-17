"""Synthetic regression demonstration; never uses production data or credentials."""
import os
import json
from pathlib import Path
import re
import sqlite3
import tempfile
import unittest
import uuid

from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch
from urllib.parse import urlsplit, parse_qs, urlencode, urlunsplit, quote

from flask import Flask
from pmi_review import create_blueprint
from pmi_review_store import ReviewStore
from test_review_store import payload


class SelectionLoopChecks:
    postgres = False
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = str(Path(self.tmp.name) / 'synthetic.sqlite')
        dsn = 'sqlite:///' + self.db
        if self.postgres:
            import psycopg
            raw = os.environ['PMI_TEST_POSTGRES_DSN']
            url = urlsplit(raw)
            if (os.environ.get('PMI_TEST_POSTGRES_ISOLATED') != '1'
                    or url.scheme not in {'postgres', 'postgresql'}
                    or url.hostname not in {'127.0.0.1', 'localhost', 'pmi-feedback-postgres'}
                    or not url.path.lstrip('/').startswith('pmi_feedback_test')
                    or url.query):
                raise ValueError('Use an explicitly isolated local pmi_feedback_test database, without DSN query overrides.')
            self.pg_base = raw
            self.schema = 'pmi_feedback_' + uuid.uuid4().hex
            with psycopg.connect(raw, autocommit=True) as c:
                c.execute('CREATE SCHEMA ' + self.schema)
            dsn = urlunsplit((url.scheme, url.netloc, url.path,
                             urlencode({'options': '-c search_path=' + self.schema}, quote_via=quote), ''))
        self.store = ReviewStore(dsn)
        self.store.initialize()
        self.store.import_payload(payload(), 'SYNTHETIC operator')
        self.cid = self.store.list_cases()[0]['case_id']
        for n in range(5):
            self.store.set_state(self.cid, 'COMPLETE', 'SYNTHETIC working note ' + str(n), 'SYNTHETIC operator', 'note-' + str(n))
        self.app = Flask(__name__)
        self.app.config['TESTING'] = True
        self.app.register_blueprint(create_blueprint(lambda: payload(), store_factory=lambda: self.store,
                                   access_key='SYNTHETIC-local-only-login-passphrase', allow_http=True))
        self.client = self.app.test_client()
        page = self.client.get('/review/')
        self.client.post('/review/login', data={'csrf_token': self.token(page), 'access_key': 'SYNTHETIC-local-only-login-passphrase'})

    def tearDown(self):
        if self.postgres and hasattr(self, 'schema'):
            import psycopg
            with psycopg.connect(self.pg_base, autocommit=True) as c:
                c.execute('DROP SCHEMA ' + self.schema + ' CASCADE')
        self.tmp.cleanup()

    def token(self, response):
        return re.search(r'name="csrf_token"\s+value="([^"]+)"', response.get_data(as_text=True)).group(1)

    def page(self):
        return self.client.get('/review/cases/' + self.cid)

    def data(self):
        case = self.store.case(self.cid)
        return {'selection_version_id': case['selection_version_id'], 'selection_reason_id': case['selection_reason_ids'][0],
                'outcome': 'USEFUL_INVESTIGATION', 'method': 'AUTHORITATIVE_RECORD',
                'detail': 'SYNTHETIC demonstration only: checked reference DEMO-001 on 2026-10-17; property research useful, owner intent unknown.', 'verified': True}

    def rows(self, table):
        with self.store._session() as c:
            return set(self.store._sql(c, 'SELECT * FROM ' + table).fetchall())

    def test_representative_five_note_case_through_actual_form(self):
        before = self.store.case(self.cid)
        old_versions = self.rows('pmi_review_case_versions')
        original_events = self.rows('pmi_review_events')
        report_before = self.store.learning_report()
        self.assertEqual(before['analysis']['hypotheses'], [])
        self.assertEqual(report_before['counts']['review_events'], 0)
        db_before = {t: self.rows(t) for t in ('pmi_review_cases', 'pmi_review_case_versions', 'pmi_review_events', 'pmi_ai_review_records')}
        page = self.page()
        self.assertEqual(page.status_code, 200)
        self.assertIn('Reviewed finding — original property explanation', page.get_data(as_text=True))
        self.assertEqual({t: self.rows(t) for t in db_before}, db_before, 'GET must not create review snapshots')
        fields = {k: re.search(r'name="'+k+r'" value="([^"]+)"', page.get_data(as_text=True)).group(1)
                  for k in ('selection_version_id', 'selection_reason_id')}
        response = self.client.post('/review/cases/' + self.cid + '/review', data={
            **self.data(), **fields, 'verified': 'true', 'csrf_token': self.token(page), 'event_id': 'demo-review'})
        self.assertEqual(response.status_code, 303)
        after = self.store.case(self.cid)
        report = self.client.get('/review/learning.json').get_json()
        # Same authenticated read path sees newly saved feedback immediately.
        export = self.client.get('/review/export').get_json()
        self.assertTrue(export)
        self.assertEqual(report['counts']['review_events'], 1)
        self.assertEqual(report['counts']['verified_review_events'], 1)
        self.assertEqual(report['verified_outcomes'], {'USEFUL_INVESTIGATION': 1})
        self.assertEqual(after['notes'], before['notes'])
        self.assertEqual(after['baseline'], before['baseline'])
        self.assertEqual(after['analysis'], before['analysis'])
        self.assertEqual(after['lane'], before['lane'])
        self.assertTrue(old_versions <= self.rows('pmi_review_case_versions'))
        self.assertTrue(original_events <= self.rows('pmi_review_events'))
        self.assertEqual(report['suggestions'], [])
        self.assertEqual(report['guards']['rules_adopted'], 0)
        self.assertFalse(after['analysis']['contact_authorized'])
        findings = [x for x in after['history'] if x['kind'] == 'REVIEW']
        self.assertEqual(len(findings), 1)
        with self.store._session() as c:
            snapshot = json.loads(self.store._sql(c, "SELECT data_json FROM pmi_ai_review_records WHERE kind='ANALYSIS' AND analysis_id=?", (findings[0]['data']['analysis_id'],)).fetchone()[0])
        self.assertEqual(snapshot['baseline_snapshot'], before['baseline'])
        result = {'data_type': 'SYNTHETIC representative land-dominant property, NOT 12 SCHOOL ST production records',
                  'before': {'notes': 5, 'formal_reviews': 0, 'learning_status': report_before['status'], 'seller_hypotheses': 0},
                  'after': {'notes': len(after['notes']), 'formal_reviews': report['counts']['review_events'],
                            'verified_reviews': report['counts']['verified_review_events'], 'learning_status': report['status'],
                            'verified_outcomes': report['verified_outcomes'], 'lessons': report['lessons'],
                            'suggestions': report['suggestions'], 'rules_adopted': report['guards']['rules_adopted']},
                  'retention': {'original_notes_identical': True, 'original_baseline_identical': True, 'all_old_versions_and_events_retained': True},
                  'downstream': {'seller_analysis_unchanged': True, 'lane_unchanged': True, 'contact_authorized': False,
                                 'learning_and_export_read_after_save': True, 'automatic_selection_adjustment': False}}
        self.assertEqual(result['after']['rules_adopted'], 0)

    def test_unverified_finding_never_becomes_verified_learning(self):
        self.store.review(self.cid, {**self.data(), 'verified': False}, 'operator', 'tentative')
        report = self.store.learning_report()
        self.assertEqual(report['counts']['review_events'], 1)
        self.assertEqual(report['counts']['verified_review_events'], 0)
        self.assertEqual(report['lessons'], [])
        self.assertEqual(report['suggestions'], [])

    def test_replay_and_explicit_correction_preserve_history(self):
        data = self.data()
        self.store.review(self.cid, data, 'operator', 'same-event')
        self.store.review(self.cid, data, 'operator', 'same-event')
        self.assertEqual(self.store.learning_report()['counts']['review_events'], 1)
        self.store.review(self.cid, {**data, 'outcome': 'FALSE_POSITIVE', 'supersedes': 'same-event'}, 'operator', 'correction')
        report = self.store.learning_report()
        self.assertEqual(report['counts']['review_events'], 2)
        self.assertEqual(report['verified_outcomes'], {'FALSE_POSITIVE': 1})
        self.assertEqual(len(self.store.case(self.cid)['notes']), 5)

    def test_wrong_case_version_and_unknown_reason_are_rejected_atomically(self):
        self.store.import_payload(payload(2), 'operator')
        other = next(c for c in self.store.list_cases() if c['case_id'] != self.cid)
        wrong = self.store.case(other['case_id'])['selection_version_id']
        for changes in ({'selection_version_id': wrong}, {'selection_reason_id': 'forged'}):
            before = self.rows('pmi_ai_review_records')
            with self.assertRaises(ValueError):
                self.store.review(self.cid, {**self.data(), **changes}, 'operator', str(uuid.uuid4()))
            self.assertEqual(self.rows('pmi_ai_review_records'), before)

    def test_property_review_cannot_be_used_as_seller_confirmation(self):
        with self.assertRaises(ValueError):
            self.store.review(self.cid, {**self.data(), 'outcome': 'SELLER_REASON_CONFIRMED', 'method': 'OWNER_DISCLOSURE'}, 'operator', 'bad')
        self.store.review(self.cid, self.data(), 'operator', 'good')
        saved = next(e['data'] for e in self.store.case(self.cid)['history'] if e['kind'] == 'REVIEW')
        with self.assertRaises(ValueError):
            self.store.review(self.cid, {**saved, 'outcome': 'SELLER_REASON_CONFIRMED', 'method': 'OWNER_DISCLOSURE'}, 'operator', 'bad-direct')

    def test_prior_version_remains_reviewable_after_reimport(self):
        old = self.data()
        prior = self.store.case(self.cid)['baseline']
        revised = payload()
        revised['profiles'][0]['why_pmi_noticed_it'][0]['noticed_because'] = 'SYNTHETIC revised explanation'
        self.store.import_payload(revised, 'operator')
        current = self.store.case(self.cid)['baseline']
        self.assertNotEqual(current, prior)
        self.store.review(self.cid, old, 'operator', 'old-version-review')
        self.assertEqual(self.store.case(self.cid)['baseline'], current)
        saved = next(e['data'] for e in self.store.case(self.cid)['history'] if e['kind'] == 'REVIEW')
        with self.store._session() as c:
            snapshot = json.loads(self.store._sql(c, "SELECT data_json FROM pmi_ai_review_records WHERE analysis_id=? AND kind='ANALYSIS'", (saved['analysis_id'],)).fetchone()[0])
        self.assertEqual(snapshot['baseline_snapshot'], prior)

    def test_concurrent_duplicate_is_one_review(self):
        data = self.data()
        with ThreadPoolExecutor(max_workers=3) as pool:
            list(pool.map(lambda _: self.store.review(self.cid, data, 'operator', 'concurrent'), range(3)))
        self.assertEqual(self.store.learning_report()['counts']['review_events'], 1)
        self.assertEqual(len([e for e in self.store.case(self.cid)['history'] if e['kind'] == 'REVIEW']), 1)

    def test_late_failure_rolls_back_snapshot_feedback_and_event(self):
        tables = ('pmi_ai_review_records', 'pmi_review_events', 'pmi_review_case_versions', 'pmi_review_cases')
        before = {t: self.rows(t) for t in tables}
        with patch.object(self.store, '_append', side_effect=RuntimeError('Synthetic transaction failure')):
            with self.assertRaises(RuntimeError):
                self.store.review(self.cid, self.data(), 'operator', 'fail-late')
        self.assertEqual({t: self.rows(t) for t in tables}, before)

    def test_http_verification_is_explicit_and_conflicting_duplicate_cannot_overwrite(self):
        page = self.page()
        text = page.get_data(as_text=True)
        selection_form = text[text.index('Reviewed finding — original property explanation'):]
        selection_form = selection_form[:selection_form.index('</form>')]
        checkbox = re.search(r'<input[^>]*name="verified"[^>]*>', selection_form).group(0)
        self.assertNotIn('checked', checkbox)
        data = self.data()
        data.pop('verified')
        response = self.client.post('/review/cases/' + self.cid + '/review', data={
            **data, 'csrf_token': self.token(page), 'event_id': 'unchecked'})
        self.assertEqual(response.status_code, 303)
        self.assertEqual(self.store.learning_report()['counts']['verified_review_events'], 0)
        before = self.rows('pmi_ai_review_records')
        with self.assertRaises(ValueError):
            self.store.review(self.cid, {**data, 'verified': True}, 'PMI operator', 'unchecked')
        self.assertEqual(self.rows('pmi_ai_review_records'), before)


class SelectionLoopSQLiteTests(SelectionLoopChecks, unittest.TestCase):
    pass


@unittest.skipUnless(os.environ.get('PMI_TEST_POSTGRES_DSN'), 'Isolated PostgreSQL DSN not supplied')
class SelectionLoopPostgreSQLTests(SelectionLoopChecks, unittest.TestCase):
    postgres = True


if __name__ == '__main__':
    unittest.main()
