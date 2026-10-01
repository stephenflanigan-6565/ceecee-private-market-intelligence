#!/usr/bin/env python3
"""V16T — explainable investigation-basis qualification test.

Read-only bridge from V16S cleaned temporal context toward a later, separately
governed INVESTIGATE promotion test. It identifies records whose CURRENT factual
evidence is sufficiently explainable to justify investigation consideration.
It does not change INVESTIGATE state, infer seller intent/motivation/distress,
score sellers, authorize contact/outreach, or emit owner names/addresses.
"""
from collections import Counter
from datetime import datetime, timezone

from temporal_relevance_cleanup_v16s import build_temporal_relevance_cleanup_v16s
from deeper_research_queue_v16q import build_deeper_research_queue_v16q

VERSION = 'V16T'
MODE = 'READ_ONLY_EXPLAINABLE_INVESTIGATION_BASIS_TEST'


def build_explainable_investigation_basis_v16t():
    temporal = build_temporal_relevance_cleanup_v16s()
    queue_base = build_deeper_research_queue_v16q()
    if temporal.get('status') != 'ok' or queue_base.get('status') != 'ok':
        return {
            'status': 'failed', 'version': VERSION, 'mode': MODE,
            'error': 'V16S or V16Q prerequisite failed',
            'guards': _guards(),
        }

    q_items = list(queue_base.get('deeper_research_queue', {}).get('items', []))
    q_by_pid = {str(x.get('parcel_id')): x for x in q_items}
    s_items = list(temporal.get('temporal_cleanup', {}).get('items', []))

    out = []
    state_counts = Counter()
    basis_reason_counts = Counter()
    ownership_blocked = 0

    for s in s_items:
        pid = str(s.get('parcel_id'))
        q = q_by_pid.get(pid, {})
        reasons = list(q.get('queue_reasons') or [])
        temporal_state = s.get('temporal_state')

        independent_context_complete = bool(
            q.get('ownership_evidence_rows', 0) > 0 and
            q.get('assessment_evidence_rows', 0) > 0 and
            q.get('property_context_rows', 0) > 0 and
            q.get('transfer_title_evidence_rows', 0) > 0
        )
        current_event_basis = bool(reasons)
        retained_temporal = temporal_state == 'TEMPORALLY_RELEVANT_CONTEXT_PRESENT'
        recent_multi_event = temporal_state == 'RECENT_MULTI_EVENT_CONTEXT_PRESENT'
        historical_only = temporal_state == 'HISTORICAL_ONLY_CONTEXT'
        ownership_conflict = bool(s.get('manual_owner_verification_required'))

        # V16T is deliberately narrow. A record needs a validated recent-event
        # basis, complete independent context, and either retained temporal
        # relevance or a resolved recent multi-event sequence. Historical-only
        # chronology can never qualify by itself.
        qualified = bool(
            current_event_basis and independent_context_complete and
            (retained_temporal or recent_multi_event) and not historical_only
        )

        basis_reasons = []
        if qualified:
            basis_reasons.append('VALIDATED_CURRENT_EVENT_BASIS')
            basis_reasons.append('INDEPENDENT_PROPERTY_ASSESSMENT_OWNERSHIP_TITLE_CONTEXT_PRESENT')
            if retained_temporal:
                basis_reasons.append('TEMPORALLY_RELEVANT_EVENT_SEQUENCE_PRESENT')
            if recent_multi_event:
                basis_reasons.append('RECENT_MULTI_EVENT_SEQUENCE_PRESENT')
            for r in basis_reasons:
                basis_reason_counts[r] += 1

        if qualified and ownership_conflict:
            state = 'BASIS_PRESENT_OWNERSHIP_VERIFICATION_REQUIRED'
            ownership_blocked += 1
        elif qualified:
            state = 'BASIS_PRESENT_PENDING_SEPARATE_INVESTIGATE_TEST'
        elif historical_only:
            state = 'NO_BASIS_HISTORICAL_ONLY'
        else:
            state = 'NO_BASIS_CURRENT_EVIDENCE_INSUFFICIENT'
        state_counts[state] += 1

        out.append({
            'parcel_id': pid,
            'qualification_state': state,
            'explainable_investigation_basis_present': qualified,
            'current_event_basis_present': current_event_basis,
            'current_event_reasons': reasons,
            'independent_context_complete': independent_context_complete,
            'temporal_state': temporal_state,
            'basis_reasons': basis_reasons,
            'ownership_verification_gate': s.get('ownership_verification_gate'),
            'manual_owner_verification_required': ownership_conflict,
            'investigate_state_change': False,
            'seller_intent': False,
            'contact_authorized': False,
        })

    # Operational presentation only: show explainable-basis records first.
    # This is not a score, probability, rank, or seller-likelihood estimate.
    out.sort(key=lambda x: (not x['explainable_investigation_basis_present'], x['parcel_id']))
    qualified_count = sum(1 for x in out if x['explainable_investigation_basis_present'])

    return {
        'status': 'ok', 'version': VERSION, 'mode': MODE,
        'generated_at': datetime.now(timezone.utc).isoformat(),
        'market_code': temporal.get('market_code'),
        'source_population': {
            'v16s_items_evaluated': len(s_items),
            'v16t_items_evaluated': len(out),
        },
        'qualification_summary': {
            'explainable_investigation_basis_count': qualified_count,
            'ownership_verification_required_among_basis_records': ownership_blocked,
            'qualification_state_counts': dict(sorted(state_counts.items())),
            'basis_reason_counts': dict(sorted(basis_reason_counts.items())),
        },
        'investigation_basis': {'items': out, 'items_returned': len(out)},
        'interpretation': {
            'purpose': 'Determine whether cleaned current evidence supports an explainable factual basis for later investigation consideration.',
            'admission_rule': 'Requires a validated current-event reason, complete independent property/assessment/ownership/title context, and either a temporally relevant event sequence or resolved recent multi-event sequence.',
            'historical_rule': 'HISTORICAL_ONLY chronology remains true history but cannot create an investigation basis by itself.',
            'authority_boundary': 'An explainable investigation basis is not seller intent, motivation, distress, a seller score, INVESTIGATE state, contact authorization, or outreach authority.',
            'next_if_verified': 'Inspect the factual basis records. Only after this test is verified may a separate isolated version test operational INVESTIGATE promotion governance.',
        },
        'guards': _guards(),
    }


def _guards():
    return {
        'database_writes': False,
        'investigate_state_touched': False,
        'seller_intent_inferred': False,
        'seller_scoring': False,
        'contact_authorized': False,
        'outreach_touched': False,
        'owner_names_addresses_emitted': False,
        'sensitive_motivation_inferred': False,
        'price_or_luxury_gate_used': False,
        'historical_only_event_can_qualify_alone': False,
    }
