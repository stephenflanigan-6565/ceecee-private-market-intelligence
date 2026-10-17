"""Versioned property research only; never changes seller selection or outreach."""
from datetime import date, datetime, timezone
import json
from seller_ai_memory import canonical, digest
from pmi_case_sources import _valid_url, SOURCE_SPECS

VERSION = "PMI_PROPERTY_LOOP_RUNTIME_V1"
POLICY = {"experimental": True, "fact_max_age_days": 30, "source_check_max_age_days": 2,
          "minimum_independent_dimensions": 2, "inventory_limit": 200,
          "candidate_limit": 3, "seller_selection_rule": False}
DIMENSIONS = {"property_form": "form", "project_status": "project",
              "current_use": "use", "occupancy_status": "use"}
def checked_sources(case, sources):
    output, rejected = [], []
    for s in sources:
        rows = s.get("records", [])
        if (s.get("source_key") not in {"parcel", "owner", "transfer_current", "transfer_history"}
                or s.get("status") not in {"SUCCESS", "EMPTY"} or not s.get("complete")
                or s.get("expected_count") != len(rows)
                or not _valid_url(s.get("query_url", "")) or not s.get("observed_at")
                or not any(key == s.get("source_key") and ("/" + service + "/") in s.get("query_url", "") for key, _, service in SOURCE_SPECS)
                or any(str(r.get("PARCELID")) != str(case["parcel_id"]) for r in rows)
                or any("OBJECTID" not in r for r in rows)):
            rejected.append(s.get("source_key"))
            continue
        # Canonical row order: a pagination reorder isn't new property evidence.
        rows = sorted(rows, key=lambda r: str(r["OBJECTID"]))
        value = {"case_id": case["case_id"], "parcel_id": case["parcel_id"],
                 "source_key": s["source_key"], "records": rows,
                 "source_url": s["query_url"],
                 "recorded_dates": s.get("recorded_dates", []),
                 "meaning": "SOURCE_REPORTS_ONLY",
                 "current_occupancy_established": False}
        value["evidence_id"] = "source_" + digest(value)
        output.append(value)
    return sorted(output, key=lambda x: x["source_key"]), rejected

def explicit_facts(case, as_of, max_age_days):
    facts, excluded, conflicts = {}, [], []
    for event in case.get("evidence", []):
        data = event["data"]
        field = data.get("field")
        if data.get("kind") != "FACT" or field not in DIMENSIONS:
            continue
        try:
            observed = date.fromisoformat(data["observed_at"][:10])
            age = (as_of - observed).days
        except (KeyError, TypeError, ValueError):
            age = -1
        if (not data.get("verified") or not data.get("current")
                or age < 0 or age > max_age_days
                or not (data.get("source_url") or data.get("source_record_id"))):
            excluded.append({"event_id": event["event_id"], "reason": "UNVERIFIED_UNDATED_OR_NOT_CURRENT"})
            continue
        facts.setdefault(field, []).append({"event_id": event["event_id"],
            "value": data["value"], "observed_at": data["observed_at"],
            "source": data.get("source_url") or data.get("source_record_id")})
    # Explicit supersession only. Newer timestamps alone never erase disagreement.
    superseded = {e["data"].get("supersedes") for e in case.get("evidence", [])
                  if e["data"].get("verified") and e["data"].get("supersedes")}
    usable = {}
    for field, values in facts.items():
        values = [v for v in values if v["event_id"] not in superseded]
        if not values:
            continue
        if len({str(v["value"]).casefold() for v in values}) > 1:
            conflicts.append({"field": field, "observations": values})
        else:
            usable[field] = values
    return usable, excluded, conflicts


def bound_findings(case, analyses):
    """Each analysis/reason is independent; corrections never cross versions."""
    groups, invalid = {}, []
    for event in case['history']:
        if event['kind'] != 'REVIEW':
            continue
        data = event['data']
        original = analyses.get(data.get('analysis_id'), {})
        if original.get('origin') != 'RETAINED_PROPERTY_SELECTION':
            continue
        reason = next((h for h in original.get('hypotheses', [])
                       if h['hypothesis_id'] == data.get('hypothesis_id')), None)
        if (not reason or original.get('case_id') != case['case_id']
                or original.get('case_revision') != data.get('case_revision')
                or digest(original['baseline_snapshot']) != data.get('case_revision')):
            invalid.append(event['event_id'])
            continue
        key = (data['analysis_id'], data['hypothesis_id'])
        groups.setdefault(key, {'original': original, 'reason': reason, 'events': []})['events'].append(event)
    output = []
    for (analysis_id, hypothesis_id), group in sorted(groups.items()):
        events = group['events']
        verified = [e for e in events if e['data'].get('verified') is True]
        superseded = {e['data'].get('supersedes') for e in verified}
        active = [e for e in verified if e['event_id'] not in superseded]
        # Conflicting independent findings require an explicit correction, not
        # a timestamp tie-break that quietly chooses an operator's conclusion.
        outcomes = {e['data']['outcome'] for e in active}
        state = ('AWAITING_EXPLICIT_REVIEW' if not active else
                 'CONFLICTING_FINDINGS' if len(outcomes) > 1 else
                 'REVIEW_SUPPORTS_PROPERTY_RESEARCH' if outcomes == {'USEFUL_INVESTIGATION'} else
                 'REVIEW_CONTRADICTS_ORIGINAL')
        original = group['original']
        output.append({'analysis_id': analysis_id, 'hypothesis_id': hypothesis_id,
            'original_version': original['version'], 'case_revision': original['case_revision'],
            'original_explanation': group['reason']['retained_explanation'],
            'original_baseline': original['baseline_snapshot'],
            'current_baseline_matches': original['case_revision'] == digest(case['baseline']),
            'assessment': state, 'active_event_ids': sorted(e['event_id'] for e in active),
            'finding_history': events})
    return output, invalid


def _sources(store, connection, case, as_of, research_ready):
    if not research_ready:
        return {'status': 'NOT_INITIALIZED', 'latest_run': None, 'retained': []}
    cid = case['case_id']
    run = store._sql(connection, 'SELECT run_id,started_at,completed_at,status,bundle_json FROM pmi_research_runs WHERE case_id=? ORDER BY started_at DESC,run_id DESC LIMIT 1', (cid,)).fetchone()
    latest = None if not run else {'run_id': run[0], 'started_at': run[1],
        'completed_at': run[2], 'status': run[3],
        'source_attempts': (json.loads(run[4]) if run[4] else {}).get('sources', [])}
    retained = []
    rows = store._sql(connection, 'SELECT source_key,snapshot_id,checked_at,source_json FROM pmi_research_sources WHERE case_id=? ORDER BY source_key', (cid,)).fetchall()
    for key, snapshot_id, checked_at, raw in rows:
        source = json.loads(raw)
        checked, rejected = checked_sources(case, [source])
        try:
            age = (as_of - date.fromisoformat(checked_at[:10])).days
        except (TypeError, ValueError):
            age = -1
        linked_runs = store._sql(connection, 'SELECT run_id,bundle_json FROM pmi_research_runs WHERE case_id=? AND completed_at=? ORDER BY run_id', (cid, checked_at)).fetchall()
        run_ids = [rid for rid, bundle in linked_runs if any(
            s.get('source_key') == key and s.get('records') == source.get('records')
            and s.get('observed_at') == source.get('observed_at')
            and s.get('status') in {'SUCCESS', 'EMPTY'}
            for s in (json.loads(bundle) if bundle else {}).get('sources', []))]
        retained.append({'source_key': key, 'snapshot_id': snapshot_id,
            'run_ids': run_ids, 'checked_at': checked_at,
            'source_observed_at': source.get('observed_at'),
            'recorded_dates': source.get('recorded_dates', []),
            'effective_dates': source.get('effective_dates'),
            'effective_date_meaning': 'SOURCE_SUPPLIED_ONLY; unknown when absent',
            'stale': age < 0 or age > POLICY['source_check_max_age_days'],
            'validation': 'REJECTED' if rejected or not run_ids else 'SOURCE_REPORTS_ONLY',
            'evidence': checked, 'raw_source': source})
    return {'status': latest['status'] if latest else 'NO_CHECK',
            'latest_run': latest, 'retained': retained}


def comparisons(seed, finding, cases, assessments, as_of):
    result = {'candidates': [], 'excluded': [], 'policy': dict(POLICY),
              'inventory_examined': min(len(cases), POLICY['inventory_limit']),
              'inventory_truncated': len(cases) > POLICY['inventory_limit']}
    if finding['assessment'] != 'REVIEW_SUPPORTS_PROPERTY_RESEARCH' or not finding['current_baseline_matches']:
        result['reason'] = 'NO_CURRENT_VERIFIED_USEFUL_EXPLANATION'
        return result
    seed_facts, _, conflicts = explicit_facts(seed, as_of, POLICY['fact_max_age_days'])
    if conflicts:
        result['reason'] = 'SEED_EVIDENCE_CONFLICT'
        return result
    route = finding['original_explanation']['route']
    for case in cases[:POLICY['inventory_limit']]:
        if case['case_id'] == seed['case_id']:
            continue
        matches = [h for h in case['baseline']['hypotheses'] if h.get('route') == route and h.get('disposition') == 'SUPPORTED']
        candidate_assessment = assessments[case['case_id']]
        blocked = any(f['current_baseline_matches'] and f['original_explanation'].get('route') == route
                      and f['assessment'] in {'REVIEW_CONTRADICTS_ORIGINAL', 'CONFLICTING_FINDINGS'}
                      for f in candidate_assessment['findings'])
        facts, excluded, conflicts = explicit_facts(case, as_of, POLICY['fact_max_age_days'])
        shared = [f for f in seed_facts if f in facts and str(seed_facts[f][0]['value']).casefold() == str(facts[f][0]['value']).casefold()]
        differences = [f for f in seed_facts if f in facts and f not in shared]
        reason = ('REVIEWED_CONTRADICTION' if blocked else 'NO_SUPPORTED_SHARED_EXPLANATION' if not matches
                  else 'CONTRADICTORY_OBSERVATIONS' if conflicts or differences
                  else 'INSUFFICIENT_INDEPENDENT_DIMENSIONS' if len({DIMENSIONS[f] for f in shared}) < POLICY['minimum_independent_dimensions'] else None)
        if reason:
            result['excluded'].append({'case_id': case['case_id'], 'reason': reason})
        else:
            result['candidates'].append({'case_id': case['case_id'], 'property_address': case['baseline']['property_address'],
                'seed_reference': {k: finding[k] for k in ('analysis_id', 'hypothesis_id', 'case_revision', 'active_event_ids')},
                'candidate_baseline_revision': digest(case['baseline']), 'candidate_original_explanations': matches,
                'supporting_evidence': {f: {'seed': seed_facts[f], 'candidate': facts[f]} for f in shared},
                'excluded_observations': excluded, 'contradictions': conflicts,
                'source_status': candidate_assessment['sources'],
                'missing_information': ['Current owner objective', 'Independent check of property opportunity'],
                'next_question': 'Does the original explanation hold here, and which dated source could disprove it?',
                'seller_intent': 'UNKNOWN', 'contact_authorized': False})
    result['qualifying_candidate_count'] = len(result['candidates'])
    result['candidates_truncated'] = len(result['candidates']) > POLICY['candidate_limit']
    result['candidates'] = result['candidates'][:POLICY['candidate_limit']]
    return result


def latest(store, connection):
    row = store._sql(connection, "SELECT data_json FROM pmi_ai_review_records WHERE kind='PROPERTY_LOOP' ORDER BY record_key DESC LIMIT 1").fetchone()
    return json.loads(row[0]) if row else None


def refresh(store, connection, *, as_of=None):
    """Called within the existing serialized workspace transaction.

    The sequence, comparison set and assessment set commit in one append. Input
    identity is compared only to the current revision, so A→B→A is a new event.
    No cursor is advanced before commit; the normal learning poll retries.
    """
    as_of = as_of or datetime.now(timezone.utc).date()
    cases = []
    pointers = store._sql(connection, 'SELECT case_id,pilot FROM pmi_review_cases ORDER BY case_id').fetchall()
    analyses = {aid: json.loads(raw) for aid, raw in store._sql(connection, "SELECT analysis_id,data_json FROM pmi_ai_review_records WHERE kind='ANALYSIS'").fetchall()}
    if store.postgres:
        research_ready = store._sql(connection, "SELECT to_regclass('pmi_research_sources')").fetchone()[0] is not None
    else:
        research_ready = store._sql(connection, "SELECT name FROM sqlite_master WHERE type='table' AND name='pmi_research_sources'").fetchone() is not None
    # Saved inventory only. No collection, re-analysis, or seller-score writes.
    for cid, pilot in pointers:
        doc, _ = store._document(connection, cid)
        events = store._events(connection, cid)
        cases.append({'case_id': cid, 'parcel_id': doc['baseline']['parcel_id'],
            'baseline': doc['baseline'], 'pilot': bool(pilot), 'history': events,
            'evidence': [e for e in events if e['kind'] == 'EVIDENCE']})
    assessments = {}
    for case in cases:
        findings, invalid = bound_findings(case, analyses)
        facts, excluded, conflicts = explicit_facts(case, as_of, POLICY['fact_max_age_days'])
        assessments[case['case_id']] = {'findings': findings, 'invalid_binding_event_ids': invalid,
            'sources': _sources(store, connection, case, as_of, research_ready),
            'facts': facts, 'excluded_observations': excluded, 'contradictions': conflicts,
            'current_baseline_revision': digest(case['baseline']), 'pilot': case['pilot'],
            'seller_intent': 'UNKNOWN', 'contact_authorized': False}
    for case in cases:
        for finding in assessments[case['case_id']]['findings']:
            finding['comparisons'] = comparisons(case, finding, cases, assessments, as_of)
    # Avoid recursive source/findings references in comparisons (only source data
    # is shared). Day changes are evaluation checkpoints for freshness, not facts.
    payload = {'version': VERSION, 'evaluated_on': as_of.isoformat(), 'policy': dict(POLICY),
               'cases': assessments, 'rules_adopted': 0, 'contact_authorized': False}
    revision = digest(payload)
    prior = latest(store, connection)
    if prior and prior['input_revision'] == revision:
        return {**prior, 'refreshed': False}
    changes = []
    for cid, item in assessments.items():
        old = (prior or {}).get('cases', {}).get(cid, {})
        for source in item['sources']['retained']:
            before = next((s for s in old.get('sources', {}).get('retained', []) if s['source_key'] == source['source_key']), None)
            if before and before['raw_source']['records'] != source['raw_source']['records']:
                changes.append({'case_id': cid, 'source_key': source['source_key'],
                    'before_snapshot_id': before['snapshot_id'], 'after_snapshot_id': source['snapshot_id'],
                    'before_run_ids': before['run_ids'], 'after_run_ids': source['run_ids'],
                    'before': before['raw_source']['records'], 'after': source['raw_source']['records']})
    sequence = (prior or {}).get('sequence', 0) + 1
    payload.update(input_revision=revision, sequence=sequence,
        previous_sequence=(prior or {}).get('sequence'), source_changes=changes,
        generated_at=datetime.now(timezone.utc).isoformat())
    store._sql(connection, 'INSERT INTO pmi_ai_review_records(record_key,kind,case_id,analysis_id,data_json,recorded_at) VALUES(?,?,?,?,?,?)',
        (f'property_loop:{sequence:020d}', 'PROPERTY_LOOP', 'workspace:property_loop', '', canonical(payload), payload['generated_at']))
    return {**payload, 'refreshed': True}
