"""Real template/form integration: typed evidence, feedback and public attribution."""
from pathlib import Path
import re
import tempfile
import unittest
import uuid

from flask import Flask
from pmi_review import create_blueprint
from pmi_review_store import ReviewStore
from test_review_store import payload


class ReviewFlowTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.store = ReviewStore(str(Path(self.tmp.name) / 'review.db'))
        self.app = Flask(__name__)
        self.app.config['TESTING'] = True
        self.app.register_blueprint(create_blueprint(lambda: payload(2), store_factory=lambda: self.store,
                                   access_key='synthetic-browser-form-passphrase-123', allow_http=True))
        self.client = self.app.test_client()
        page = self.client.get('/review/')
        self.client.post('/review/login', data={'csrf_token': self.token(page), 'access_key': 'synthetic-browser-form-passphrase-123'})
        self.client.post('/review/initialize', data={'csrf_token': self.token(self.client.get('/review/'))})
        self.client.post('/review/import', data={'csrf_token': self.token(self.client.get('/review/'))})
        self.ids = [c['case_id'] for c in self.store.list_cases()]

    def tearDown(self):
        self.tmp.cleanup()

    def token(self, response):
        return re.search(r'name="csrf_token"\s+value="([^"]+)"', response.get_data(as_text=True)).group(1)

    def post(self, case_id, action, data):
        page = self.client.get('/review/cases/' + case_id)
        return self.client.post('/review/cases/' + case_id + '/' + action,
                                data={'csrf_token': self.token(page), 'event_id': str(uuid.uuid4()), **data})

    def fact(self, case_id, field, value, **extra):
        return self.post(case_id, 'evidence', {'evidence_type': 'fact', 'field': field, 'value': value,
                         'source_ref': 'SYNTHETIC-SOURCE', 'observed_at': '2026-10-09',
                         'current': 'true', 'verified': 'true', **extra})

    def test_actual_form_checkbox_values_create_hypothesis_and_negative_feedback_holds(self):
        case_id = self.ids[0]
        self.assertEqual(self.fact(case_id, 'project_status', 'Completed').status_code, 303)
        self.assertEqual(self.fact(case_id, 'current_use', 'Vacant').status_code, 303)
        case = self.store.case(case_id)
        self.assertEqual(case['lane'], 'SELLER_REVIEW')
        hypothesis = case['analysis']['hypotheses'][0]
        saved = self.post(case_id, 'review', {'analysis_id': case['analysis_id'], 'hypothesis_id': hypothesis['hypothesis_id'],
                         'outcome': 'FALSE_POSITIVE', 'method': 'OPERATOR_REVIEW', 'detail': 'Synthetic checked result disproves this explanation.', 'verified': 'true'})
        self.assertEqual(saved.status_code, 303)
        self.assertNotEqual(self.store.case(case_id)['lane'], 'SELLER_REVIEW')
        self.assertEqual(self.fact(case_id, 'current_use', 'Vacant').status_code, 303)
        self.assertNotEqual(self.store.case(case_id)['lane'], 'SELLER_REVIEW')

    def test_public_form_auto_reference_is_case_local_and_statement_is_escaped(self):
        data = {'evidence_type': 'public_statement', 'person_name': 'Synthetic same name', 'person_id': '',
                'source_ref': 'SYNTHETIC-STATEMENT', 'identity_source_ref': 'SYNTHETIC-DEED',
                'observed_at': '2026-10-09', 'identity_verified': 'true', 'verified': 'true', 'current': 'true',
                'property_specific': 'true', 'kind': 'EXPLICIT_SELLING_PLAN', 'access': 'PUBLIC',
                'quote': '<script>synthetic</script> I plan to sell this specific property.', 'valid_until': '2026-12-31'}
        for case_id in self.ids:
            self.assertEqual(self.post(case_id, 'evidence', data).status_code, 303)
        first, second = [self.store.case(i) for i in self.ids]
        self.assertNotEqual(first['evidence'][0]['data']['person_id'], second['evidence'][0]['data']['person_id'])
        self.assertEqual(first['lane'], 'SELLER_REVIEW')
        self.assertEqual(first['evidence'][0]['data']['public_information']['statements'][0]['valid_until'], '2026-12-31')
        page = self.client.get('/review/cases/' + self.ids[0]).get_data(as_text=True)
        self.assertNotIn('<script>synthetic</script>', page)
        self.assertIn('&lt;script&gt;synthetic&lt;/script&gt;', page)

    def test_source_correction_preserves_original_and_updates_reasoning(self):
        case_id = self.ids[0]
        self.fact(case_id, 'project_status', 'Completed')
        self.fact(case_id, 'current_use', 'Vacant')
        old_event = self.store.case(case_id)['evidence'][-1]['event_id']
        self.assertEqual(self.fact(case_id, 'current_use', 'Occupied', supersedes=old_event).status_code, 303)
        case = self.store.case(case_id)
        self.assertNotEqual(case['lane'], 'SELLER_REVIEW')
        previous = next(e for e in case['evidence'] if e['event_id'] == old_event)
        self.assertTrue(previous['superseded'])
        self.assertEqual(previous['data']['value'], 'Vacant')
        self.assertEqual(len(case['evidence']), 3)


if __name__ == '__main__':
    unittest.main()
