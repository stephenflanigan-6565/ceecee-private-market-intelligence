"""Synthetic runtime acceptance, shared SQLite/PostgreSQL checks."""
import copy
from datetime import datetime, timedelta, timezone
import json
import os
import unittest
from unittest.mock import patch
from pmi_property_loop import refresh, bound_findings
from pmi_research_store import ResearchStore
from pmi_research_worker import run_once, run_learning_once
from pmi_case_sources import _url
from test_property_selection_feedback import SelectionLoopChecks
from test_research_store import pilot_payload
from test_review_store import payload


class RuntimeChecks:
    setUp = SelectionLoopChecks.setUp
    tearDown = SelectionLoopChecks.tearDown
    token = SelectionLoopChecks.token
    data = SelectionLoopChecks.data
    page = SelectionLoopChecks.page
    rows = SelectionLoopChecks.rows

    def report(self):
        return self.store.property_loop_report()

    def review(self, event='finding', **changes):
        self.store.review(self.cid, {**self.data(), **changes}, 'synthetic', event)

    def refresh(self, day=None):
        with self.store._session(write=True, snapshot=True) as connection:
            return refresh(self.store, connection, as_of=day)

    def test_corrected_finding_and_version_are_independent(self):
        data = self.data()
        self.store.review(self.cid, data, 'synthetic', 'original')
        original = self.report()['cases'][self.cid]['findings'][0]
        self.store.review(self.cid, {**data, 'outcome': 'FALSE_POSITIVE', 'supersedes': 'original'}, 'synthetic', 'corrected')
        corrected = self.report()['cases'][self.cid]['findings'][0]
        self.assertEqual(corrected['active_event_ids'], ['corrected'])
        self.assertEqual(corrected['assessment'], 'REVIEW_CONTRADICTS_ORIGINAL')
        self.assertEqual(corrected['analysis_id'], original['analysis_id'])
        self.assertEqual(len(corrected['finding_history']), 2)
        modified = payload()
        modified['profiles'][0]['why_pmi_noticed_it'][0]['noticed_because'] = 'SYNTHETIC revised explanation'
        # Import changes the retained baseline; older findings stay tied to it.
        self.store.import_payload(modified, 'synthetic')
        historical = self.report()['cases'][self.cid]['findings'][0]
        self.assertEqual(historical['analysis_id'], original['analysis_id'])
        self.assertFalse(historical['current_baseline_matches'])
        self.review('new-version')
        findings = self.report()['cases'][self.cid]['findings']
        self.assertEqual(len(findings), 2)
        self.assertEqual(sum(f['current_baseline_matches'] for f in findings), 1)
        self.assertEqual(len(self.store.case(self.cid)['notes']), 5)

    def test_two_explanations_and_old_version_cannot_cross_bind(self):
        self.review()
        case = self.store.case(self.cid)
        with self.store._session() as c:
            rows = self.store._sql(c, "SELECT analysis_id,data_json FROM pmi_ai_review_records WHERE kind='ANALYSIS'").fetchall()
        analyses = {aid: json.loads(raw) for aid, raw in rows}
        event = next(e for e in case['history'] if e['kind'] == 'REVIEW')
        original = analyses[event['data']['analysis_id']]
        second = copy.deepcopy(original)
        second['analysis_id'] = 'synthetic-other-version'
        second['case_revision'] = 'forged'
        analyses[second['analysis_id']] = second
        other = copy.deepcopy(event)
        other['event_id'] = 'wrong-version'
        other['data'].update(analysis_id=second['analysis_id'], case_revision='forged', outcome='FALSE_POSITIVE')
        case['history'].append(other)
        result, invalid = bound_findings(case, analyses)
        self.assertEqual(invalid, ['wrong-version'])
        self.assertEqual(result[0]['active_event_ids'], ['finding'])
        # Independent reasons within an immutable analysis are isolated too.
        second = copy.deepcopy(original)
        second['analysis_id'] = 'synthetic-second-reason'
        second['hypotheses'][0]['hypothesis_id'] = 'second-reason'
        second['hypotheses'][0]['retained_explanation']['route'] = 'OTHER'
        analyses[second['analysis_id']] = second
        other['data'].update(analysis_id=second['analysis_id'], case_revision=original['case_revision'], hypothesis_id='second-reason')
        result, invalid = bound_findings(case, analyses)
        self.assertEqual(len(result), 2)
        self.assertEqual({r['assessment'] for r in result}, {'REVIEW_SUPPORTS_PROPERTY_RESEARCH', 'REVIEW_CONTRADICTS_ORIGINAL'})

    def source_setup(self, count=1):
        self.store.import_payload(pilot_payload(count), 'synthetic')
        self.pilots = [c['case_id'] for c in self.store.list_cases() if c['parcel_id'].startswith('0900')]
        for c in self.store.list_cases():
            if c['pilot']:
                self.store.set_pilot(c['case_id'], False, 'synthetic', 'off-' + c['case_id'])
        for cid in self.pilots[:5]:
            self.store.set_pilot(cid, True, 'synthetic', 'on-' + cid)
        self.research = ResearchStore(self.store.dsn)
        self.research.initialize()

    def collect(self, owner='A', status='SUCCESS'):
        def collector(case, previous):
            now = datetime.now(timezone.utc).isoformat()
            return {'case_id': case['case_id'], 'parcel_id': case['parcel_id'], 'observed_at': now,
                'status': status, 'sources': [{'source_key': 'owner', 'status': status,
                'complete': status == 'SUCCESS', 'expected_count': 1 if status == 'SUCCESS' else 0,
                'query_url': _url('TaxParcelOwner', case['parcel_id'], outFields='*', returnGeometry='false'),
                'observed_at': now, 'recorded_dates': [{'field': 'record_date', 'value': '2020-01-01'}],
                'records': [{'OBJECTID': 1, 'PARCELID': case['parcel_id'], 'OWNERNAME': owner}] if status == 'SUCCESS' else []}],
                'findings': [], 'next_checks': [], 'change_summary': 'SYNTHETIC'}
        return run_once(self.research, collector=collector)

    def due(self):
        with self.research._session(write=True) as c:
            self.research._sql(c, 'UPDATE pmi_research_schedule SET next_due_at=?', ('2000-01-01T00:00:00+00:00',))

    def test_scheduler_five_pilots_provenance_and_reversion(self):
        self.source_setup(5)
        for _ in range(5):
            self.assertEqual(self.collect()['status'], 'SUCCESS')
        a = self.report()
        self.assertEqual(run_once(self.research)['status'], 'IDLE')
        self.due()
        for _ in range(5): self.collect('B')
        b = self.report()
        self.due()
        for _ in range(5): self.collect('A')
        restored = self.report()
        self.assertGreater(restored['sequence'], b['sequence'])
        for cid in self.pilots:
            old = a['cases'][cid]['sources']['retained'][0]
            new = restored['cases'][cid]['sources']['retained'][0]
            self.assertEqual(new['snapshot_id'], old['snapshot_id'])
            self.assertNotEqual(new['run_ids'], old['run_ids'])
            self.assertTrue(new['run_ids'])
            self.assertEqual(new['recorded_dates'][0]['value'], '2020-01-01')
            self.assertIsNone(new['effective_dates'])
        self.assertEqual(restored['source_changes'][0]['before'][0]['OWNERNAME'], 'B')
        self.assertEqual(restored['source_changes'][0]['after'][0]['OWNERNAME'], 'A')
        sequence = restored['sequence']
        run_learning_once(self.store)
        self.assertEqual(self.report()['sequence'], sequence)

    def test_failed_and_stale_sources_are_disclosed_without_erasure(self):
        self.source_setup()
        self.collect()
        cid = self.pilots[0]
        first = self.report()['cases'][cid]['sources']['retained'][0]
        self.due()
        self.collect(status='ERROR')
        failed = self.report()['cases'][cid]['sources']
        self.assertEqual(failed['status'], 'ERROR')
        self.assertEqual(failed['retained'][0]['snapshot_id'], first['snapshot_id'])
        self.assertEqual(failed['latest_run']['source_attempts'][0]['status'], 'ERROR')
        later = datetime.now(timezone.utc).date() + timedelta(days=3)
        stale = self.refresh(later)['cases'][cid]['sources']['retained'][0]
        self.assertTrue(stale['stale'])
        self.assertEqual(stale['raw_source'], first['raw_source'])

    def test_interrupted_projection_recovers_without_reacquisition(self):
        self.source_setup()
        original_sql = self.store._sql
        def fail_insert(connection, sql, params=()):
            if params and 'PROPERTY_LOOP' in params:
                raise RuntimeError('synthetic interruption before commit')
            return original_sql(connection, sql, params)
        prior = self.report()
        with patch.object(ResearchStore, '_sql', side_effect=fail_insert):
            saved = self.collect()
        self.assertEqual(saved['status'], 'SUCCESS')
        self.assertEqual(self.report(), prior)
        before_runs = self.rows('pmi_research_runs')
        run_learning_once(self.store)
        recovered = self.report()
        self.assertGreater(recovered['sequence'], prior['sequence'])
        self.assertEqual(self.rows('pmi_research_runs'), before_runs)
        run_learning_once(self.store)
        self.assertEqual(self.report(), recovered)

    def test_app_readback_and_experimental_comparisons(self):
        self.source_setup(3)
        self.cid = self.pilots[0]
        for cid in self.pilots:
            for field, value in [('property_form', 'DETACHED'), ('occupancy_status', 'VACANT')]:
                self.store.add_evidence(cid, {'kind': 'FACT', 'field': field, 'value': value,
                    'observed_at': datetime.now(timezone.utc).date().isoformat(), 'source_record_id': 'SYNTHETIC',
                    'verified': True, 'current': True}, 'synthetic', cid + field)
        self.review()
        finding = self.report()['cases'][self.cid]['findings'][0]
        self.assertEqual(len(finding['comparisons']['candidates']), 2)
        self.assertTrue(finding['comparisons']['policy']['experimental'])
        before = self.rows('pmi_ai_review_records')
        response = self.page()
        self.assertEqual(response.status_code, 200)
        text = response.get_data(as_text=True)
        self.assertIn('Property research assessment and comparisons', text)
        self.assertIn(finding['analysis_id'], text)
        self.assertIn('SYNTHETIC', text)
        self.assertEqual(self.rows('pmi_ai_review_records'), before)

    def test_atomic_rollback_after_insert_and_concurrent_retry(self):
        from concurrent.futures import ThreadPoolExecutor
        prior = self.report()
        with self.assertRaises(RuntimeError):
            with self.store._session(write=True, snapshot=True) as connection:
                refresh(self.store, connection, as_of=datetime.now(timezone.utc).date() + timedelta(days=1))
                raise RuntimeError('synthetic crash after insert before commit')
        self.assertEqual(self.report(), prior)
        tomorrow = datetime.now(timezone.utc).date() + timedelta(days=1)
        with ThreadPoolExecutor(max_workers=2) as pool:
            reports = list(pool.map(lambda _: self.refresh(tomorrow), range(2)))
        self.assertEqual({r['sequence'] for r in reports}, {prior['sequence'] + 1})
        self.assertEqual(sum(r['refreshed'] for r in reports), 1)


class RuntimeSQLiteTests(RuntimeChecks, unittest.TestCase):
    postgres = False


@unittest.skipUnless(os.environ.get('PMI_TEST_POSTGRES_DSN'), 'Disposable PostgreSQL required')
class RuntimePostgresTests(RuntimeChecks, unittest.TestCase):
    postgres = True
