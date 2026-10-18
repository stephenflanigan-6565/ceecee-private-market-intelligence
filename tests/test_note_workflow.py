"""Isolated, attributed fixture scenarios; no live evidence is fabricated."""
import copy
from datetime import datetime, timezone
import os
import unittest
from unittest.mock import patch
from test_property_selection_feedback import SelectionLoopChecks
from test_property_loop_runtime import RuntimeChecks
from pmi_property_loop import explicit_facts
from pmi_note_workflow import assessment

NOTES = {
 '313 DUNE': 'Since 2021 have not been on the market for sale. Home value around 6-7M.',
 '15 BAY': "Purchased in 2012, since then I don't have any information about the condition. Valued around $900K in excellent condition.",
 '110 DUNE': 'Purchased two years ago; approximately $4 million value opinion.',
 '12 SCHOOL': 'Stopped trying to sell it in 2017. Low sell score. Value around $1M.',
 '123 POINT': 'Purchased by Nickyl Llc in 2024. High selling score. Value $2-3M up to the condition.'}

class WorkflowChecks:
    setUp = SelectionLoopChecks.setUp
    tearDown = SelectionLoopChecks.tearDown
    token = SelectionLoopChecks.token
    page = SelectionLoopChecks.page
    rows = SelectionLoopChecks.rows

    def proposal(self, label='313 DUNE'):
        self.store.set_state(self.cid, 'NEW', NOTES[label], 'fixture', 'recent-' + label)
        return self.store.propose_note(self.cid, 'recent-' + label)

    def submit(self, proposal, **changes):
        form = {'csrf_token': self.token(self.page()), 'note_id': proposal['note_id'],
                'supporting_passage': proposal['passage'], 'field': proposal['field'],
                'value': proposal['value'], 'confirm': 'on', **changes}
        return self.client.post('/review/cases/' + self.cid + '/note-evidence', data=form)

    def test_five_updates_preserve_exact_notes_and_unknown_dates(self):
        before = self.rows('pmi_review_case_versions')
        baseline = self.store.case(self.cid)['baseline']
        for label, text in NOTES.items():
            p = self.proposal(label)
            self.assertEqual(p['passage'], text)
            self.assertEqual(p['source_ref'], '')
            self.assertEqual(p['observed_at'], '')
            self.assertFalse(p['verified'] or p['current'])
            response = self.submit(p)
            self.assertEqual(response.status_code, 303)
        case = self.store.case(self.cid)
        self.assertEqual(case['baseline'], baseline)
        self.assertTrue(before <= self.rows('pmi_review_case_versions'))
        self.assertEqual(len(case['notes']), 10)
        self.assertEqual(len(case['evidence']), 5)
        for e in case['evidence']:
            self.assertIsNone(e['data']['observed_at'])
            self.assertIsNone(e['data']['source_record_id'])
            self.assertIn(e['data']['supporting_passage'], NOTES.values())
        self.assertEqual(self.store.property_loop_report()['cases'][self.cid]['facts'], {})

    def test_browser_save_retry_and_readable_confirmation(self):
        p = self.proposal()
        self.assertIn('Review saved research', self.page().get_data(as_text=True))
        response = self.submit(p)
        self.assertIn('Evidence saved', self.client.get(response.location).get_data(as_text=True))
        rows = self.rows('pmi_review_events')
        # A new form/CSRF request after a lost POST response still deduplicates.
        self.assertEqual(self.submit(p).status_code, 303)
        self.assertEqual(rows, self.rows('pmi_review_events'))

    def test_source_validation_binding_and_no_auto_verification(self):
        p = self.proposal()
        self.assertEqual(self.submit(p, verified='on').status_code, 400)
        self.assertEqual(self.submit(p, supporting_passage='invented quote').status_code, 400)
        self.assertEqual(self.submit(p, note_id='missing').status_code, 400)
        self.assertEqual(len(self.store.case(self.cid)['evidence']), 0)

    def test_status_changes_corrections_unknown_and_no_seller_rule(self):
        p = self.proposal()
        date = datetime.now(timezone.utc).date().isoformat()
        for value in ('SOLD', 'LISTED', 'HISTORICAL_MARKETING', 'UNKNOWN'):
            prior = self.store.case(self.cid)['evidence']
            self.assertEqual(self.submit(p, value=value, verified='on', current='on',
                source_ref='SYNTHETIC-only', observed_at=date,
                supersedes=prior[-1]['event_id'] if prior else '').status_code, 303)
            report = self.store.property_loop_report()['cases'][self.cid]
            self.assertEqual(report['evidence_assessment']['listing_status'], value)
            self.assertFalse(report['evidence_assessment']['selection_rules_changed'])
            self.assertEqual(report['seller_intent'], 'UNKNOWN')
        self.assertEqual(len(self.store.case(self.cid)['evidence']), 4)
        self.assertEqual(report['facts'], {})
        before = self.store.property_loop_report()
        self.store.refresh_learning()
        self.assertEqual(before, self.store.property_loop_report())

    def test_failed_assessment_keeps_save_and_recovers_without_duplicate(self):
        p = self.proposal('15 BAY')
        with patch.object(self.store, 'refresh_learning', side_effect=RuntimeError('fixture')):
            response = self.submit(p)
        self.assertEqual(response.status_code, 303)
        text = self.client.get(response.location).get_data(as_text=True)
        self.assertIn('Evidence saved. Assessment failed', text)
        self.assertEqual(len(self.store.case(self.cid)['evidence']), 1)
        self.submit(p)
        self.assertEqual(len(self.store.case(self.cid)['evidence']), 1)
        report = self.store.property_loop_report()['cases'][self.cid]
        self.assertEqual(len(report['consumed_event_ids']), 1)

    def test_conflicts_and_unknown_are_not_matches(self):
        p = self.proposal('15 BAY')
        date = datetime.now(timezone.utc).date().isoformat()
        for value in ('DATED', 'RENOVATED'):
            self.submit(p, value=value, field='condition', verified='on', current='on', source_ref='SYNTHETIC', observed_at=date)
        r = self.store.property_loop_report()['cases'][self.cid]
        self.assertEqual(len(r['contradictions']), 1)
        self.assertNotIn('condition', r['facts'])
        self.assertTrue(r['evidence_assessment']['needs_review'])

    def test_daily_activity_read_only_and_not_discovery(self):
        self.proposal()
        tables = ['pmi_review_events', 'pmi_review_case_versions', 'pmi_ai_review_records']
        before = {t: self.rows(t) for t in tables}
        a = self.store.workflow_activity()
        self.assertEqual(a['new_candidates'], [])
        self.assertTrue(a['needs_review'])
        self.assertTrue(a['updated'])
        response = self.client.get('/review/')
        self.assertEqual(response.status_code, 200)
        self.assertIn('New candidates discovered: 0', response.get_data(as_text=True))
        self.assertEqual(before, {t: self.rows(t) for t in tables})

    def test_daily_source_results_changes_failure_and_last_success(self):
        from pmi_research_store import ResearchStore
        from test_research_store import pilot_payload, bundle
        self.store.import_payload(pilot_payload(), 'fixture')
        cid = next(c['case_id'] for c in self.store.list_cases() if c['parcel_id'].startswith('0900'))
        for c in self.store.list_cases():
            if c['pilot']:
                self.store.set_pilot(c['case_id'], False, 'fixture', 'disable-' + c['case_id'])
        self.store.set_pilot(cid, True, 'fixture', 'pilot-on')
        research = ResearchStore(self.store.dsn)
        research.initialize()
        for status, change in [('SUCCESS', 'UNCHANGED'), ('SUCCESS', 'CHANGED'), ('ERROR', 'UNAVAILABLE')]:
            with research._session(write=True) as c:
                research._sql(c, "UPDATE pmi_research_schedule SET next_due_at='2000-01-01T00:00:00+00:00'")
            claim = research.claim_next('fixture')
            data = bundle(claim, status=status, source_status=status)
            data['sources'][0]['change_summary'] = {'status': change, 'message': 'SYNTHETIC ' + change}
            research.finish(claim['run_id'], claim['lease_token'], data)
        a = self.store.workflow_activity()
        self.assertEqual([r['status'] for r in a['runs']], ['SUCCESS', 'SUCCESS', 'ERROR'])
        self.assertEqual(a['runs'][0]['reason'], 'No changes found')
        self.assertTrue(a['runs'][1]['changed'])
        self.assertEqual(a['last_success'], a['runs'][1]['completed_at'])
        self.assertEqual(a['new_candidates'], [])
        self.assertEqual(self.client.get('/review/').status_code, 200)

    def test_five_distinct_fixture_properties_do_not_cross_bind(self):
        from test_review_store import payload
        data = payload(5)
        for row, name in zip(data['profiles'], NOTES):
            row['property_address'] = 'FIXTURE ' + name
        self.store.import_payload(data, 'fixture')
        ids = {}
        for row in self.store.list_cases():
            name = row['property_address'].replace('FIXTURE ', '')
            if name in NOTES:
                ids[name] = row['case_id']
                self.store.set_state(row['case_id'], 'NEW', NOTES[name], 'fixture', 'five-' + name)
        self.assertEqual(len(ids), 5)
        for name, cid in ids.items():
            p = self.store.propose_note(cid, 'five-' + name)
            self.assertEqual(p['passage'], NOTES[name])
            with self.assertRaises(ValueError):
                self.store.propose_note(cid, 'five-' + next(n for n in ids if n != name))

    def test_listing_difference_and_unknown_dimensions_affect_comparisons(self):
        from pmi_property_loop import comparisons
        from test_review_store import payload
        self.store.import_payload(payload(2), 'fixture')
        ids = [c['case_id'] for c in self.store.list_cases()]
        today = datetime.now(timezone.utc).date().isoformat()
        for cid in ids:
            for field, value in [('property_form', 'COTTAGE'), ('project_status', 'COMPLETED'), ('listing_status', 'SOLD' if cid == ids[0] else 'LISTED')]:
                self.store.add_evidence(cid, {'field': field, 'value': value, 'source_record_id': 'SYNTHETIC', 'observed_at': today, 'current': True, 'verified': True}, 'fixture', cid + field)
        finding = {'assessment': 'REVIEW_SUPPORTS_PROPERTY_RESEARCH', 'current_baseline_matches': True,
                   'original_explanation': {'route': 'LAND_PROPERTY_UTILIZATION'}}
        cases = [self.store.case(cid) for cid in ids]
        result = comparisons(cases[0], finding, cases, self.store.property_loop_report()['cases'], datetime.now(timezone.utc).date())
        self.assertEqual(result['candidates'], [])
        self.assertEqual(result['excluded'][0]['reason'], 'DIFFERENT_SUPPORTED_LISTING_OR_REPRESENTATION_STATUS')
        for event in cases[0]['evidence']:
            event['data']['value'] = 'UNKNOWN'
        self.assertEqual(explicit_facts(cases[0], datetime.now(timezone.utc).date(), 30)[0], {})

class WorkflowSQLiteTests(WorkflowChecks, unittest.TestCase):
    postgres = False

@unittest.skipUnless(os.environ.get('PMI_TEST_POSTGRES_DSN'), 'Disposable PostgreSQL required')
class WorkflowPostgresTests(WorkflowChecks, unittest.TestCase):
    postgres = True
