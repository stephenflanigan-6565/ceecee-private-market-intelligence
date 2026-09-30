#!/usr/bin/env python3
"""V16S — temporal relevance cleanup.

Read-only research bridge built on the proven V16R1 factual-resolution output.
Preserves historical chronology while separating temporally relevant context
from historical-only prior-event associations. No seller inference, scoring,
INVESTIGATE mutation, contact authorization, outreach, or database writes.
"""
from collections import Counter
from datetime import datetime, timezone

from factual_research_resolution_v16r import build_factual_research_resolution_v16r

VERSION = 'V16S'
MODE = 'READ_ONLY_TEMPORAL_RELEVANCE_CLEANUP'


def _band(days):
    if days is None:
        return None
    try:
        d = int(days)
    except (TypeError, ValueError):
        return None
    if d == 0:
        return 'SAME_DAY'
    if 0 < d <= 365:
        return 'LE_365_DAYS'
    if 365 < d <= 1095:
        return '366_DAYS_TO_3_YEARS'
    if d > 1095:
        return 'HISTORICAL_ONLY'
    return 'INVALID_CHRONOLOGY'


def build_temporal_relevance_cleanup_v16s():
    base = build_factual_research_resolution_v16r()
    if base.get('status') != 'ok':
        return {
            'status': 'failed', 'version': VERSION, 'mode': MODE,
            'error': 'V16R1 prerequisite failed',
            'guards': {
                'database_writes': False, 'investigate_state_touched': False,
                'seller_intent_inferred': False, 'seller_scoring': False,
                'contact_authorized': False, 'outreach_touched': False,
                'owner_names_addresses_emitted': False,
                'sensitive_motivation_inferred': False,
            },
        }

    source_items = list(base.get('resolved_research', {}).get('items', []))
    band_counts = Counter()
    property_state_counts = Counter()
    cleaned = []
    historical_associations = 0
    temporally_relevant_associations = 0
    same_day_recent_sequence_properties = 0
    ownership_conflict_properties = 0

    for item in source_items:
        temporal_relationships = []
        has_temporally_relevant_relationship = False
        has_historical_only_relationship = False
        has_same_day_recent_sequence = False

        for ans in item.get('research_answers', []):
            question = ans.get('question')

            if question == 'RECONCILE_MULTIPLE_RECENT_RECORDED_EVENTS':
                if bool(ans.get('same_day_ordering_present')):
                    has_same_day_recent_sequence = True

            if question not in {
                'CONFIRM_CONVEYANCE_RELATIONSHIP_TO_PRIOR_ESTATE_FIDUCIARY_RECORD',
                'CONFIRM_CONVEYANCE_RELATIONSHIP_TO_PRIOR_COURT_FORECLOSURE_TAX_RECORD',
            }:
                continue
            if ans.get('resolution') != 'ORDERED_PRIOR_EVENT_AND_RECENT_CONVEYANCE_CONFIRMED':
                continue

            days = ans.get('days_between_recorded_events')
            band = _band(days)
            if band is None:
                continue
            band_counts[band] += 1
            current_relevance = band in {'SAME_DAY', 'LE_365_DAYS', '366_DAYS_TO_3_YEARS'}
            if current_relevance:
                has_temporally_relevant_relationship = True
                temporally_relevant_associations += 1
            if band == 'HISTORICAL_ONLY':
                has_historical_only_relationship = True
                historical_associations += 1

            temporal_relationships.append({
                'question': question,
                'prior_event_date': ans.get('prior_event_date'),
                'conveyance_date': ans.get('conveyance_date'),
                'days_between_recorded_events': days,
                'temporal_band': band,
                'current_research_weight': 'RETAIN' if current_relevance else 'HISTORICAL_CONTEXT_ONLY',
                'relationship_scope': 'RECORDED_CHRONOLOGY_ONLY',
            })

        if has_same_day_recent_sequence:
            same_day_recent_sequence_properties += 1

        owner_recon = item.get('ownership_reconciliation')
        ownership_conflict = owner_recon == 'MULTIPLE_DISTINCT_CURRENT_OWNERSHIP_ROWS_REQUIRE_VERIFICATION'
        if ownership_conflict:
            ownership_conflict_properties += 1

        if has_temporally_relevant_relationship:
            temporal_state = 'TEMPORALLY_RELEVANT_CONTEXT_PRESENT'
        elif has_historical_only_relationship:
            temporal_state = 'HISTORICAL_ONLY_CONTEXT'
        elif has_same_day_recent_sequence:
            temporal_state = 'RECENT_MULTI_EVENT_CONTEXT_PRESENT'
        else:
            temporal_state = 'NO_TEMPORAL_RELATIONSHIP_ADDED'
        property_state_counts[temporal_state] += 1

        cleaned.append({
            'parcel_id': item.get('parcel_id'),
            'queue_state': item.get('queue_state'),
            'temporal_state': temporal_state,
            'temporal_relationships': temporal_relationships,
            'same_day_recent_sequence_present': has_same_day_recent_sequence,
            'ownership_reconciliation': owner_recon,
            'ownership_verification_gate': item.get('ownership_verification_gate', 'PROBABLE_PENDING_MANUAL_VERIFICATION'),
            'manual_owner_verification_required': ownership_conflict,
            'seller_intent': False,
            'investigate_state_change': False,
            'contact_authorized': False,
        })

    return {
        'status': 'ok', 'version': VERSION, 'mode': MODE,
        'generated_at': datetime.now(timezone.utc).isoformat(),
        'market_code': base.get('market_code'),
        'source_population': {
            'v16r1_resolved_candidates': len(source_items),
            'v16s_items_evaluated': len(cleaned),
        },
        'temporal_summary': {
            'temporal_band_counts': dict(sorted(band_counts.items())),
            'property_temporal_state_counts': dict(sorted(property_state_counts.items())),
            'temporally_relevant_associations': temporally_relevant_associations,
            'historical_only_associations': historical_associations,
            'same_day_recent_sequence_properties': same_day_recent_sequence_properties,
            'ownership_conflict_properties_still_blocked': ownership_conflict_properties,
        },
        'temporal_cleanup': {'items': cleaned, 'items_returned': len(cleaned)},
        'interpretation': {
            'purpose': 'Preserve factual title history while preventing remote prior events from carrying automatic current research weight.',
            'policy': 'SAME_DAY, <=365 days, and 366 days to 3 years remain temporally relevant research context. Events more than 3 years apart remain true historical chronology but are classified HISTORICAL_ONLY.',
            'authority_boundary': 'Temporal relevance is research context only. It does not establish seller intent, motivation, distress, INVESTIGATE state, or contact authority.',
        },
        'guards': {
            'database_writes': False, 'investigate_state_touched': False,
            'seller_intent_inferred': False, 'seller_scoring': False,
            'contact_authorized': False, 'outreach_touched': False,
            'owner_names_addresses_emitted': False,
            'sensitive_motivation_inferred': False,
        },
    }
