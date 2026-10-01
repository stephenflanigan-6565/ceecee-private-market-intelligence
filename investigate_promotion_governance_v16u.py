#!/usr/bin/env python3
"""V16U — INVESTIGATE promotion governance test.

Read-only governance layer over proven V16T explainable investigation bases.
Determines which factual-basis records are eligible for a later operational
INVESTIGATE transition and which remain blocked by ownership verification.
It does NOT write INVESTIGATE state, authorize contact/outreach, infer seller
intent/motivation/distress, score sellers, or emit owner names/addresses.
"""
from collections import Counter
from datetime import datetime, timezone

from explainable_investigation_basis_v16t import build_explainable_investigation_basis_v16t

VERSION = 'V16U'
MODE = 'READ_ONLY_INVESTIGATE_PROMOTION_GOVERNANCE_TEST'


def build_investigate_promotion_governance_v16u():
    basis = build_explainable_investigation_basis_v16t()
    if basis.get('status') != 'ok':
        return {
            'status': 'failed', 'version': VERSION, 'mode': MODE,
            'error': 'V16T prerequisite failed', 'guards': _guards(),
        }

    source_items = list(basis.get('investigation_basis', {}).get('items', []))
    out = []
    state_counts = Counter()
    eligible = 0
    ownership_blocked = 0
    nonbasis_blocked = 0

    for item in source_items:
        pid = str(item.get('parcel_id'))
        basis_present = bool(item.get('explainable_investigation_basis_present'))
        ownership_block = bool(item.get('manual_owner_verification_required'))
        source_state = item.get('qualification_state')

        # Governance rule: V16U can only propose INVESTIGATE eligibility when
        # V16T established an explainable factual basis AND ownership evidence
        # is not in the multiple-row manual-verification conflict state.
        # Even then, this test remains read-only and performs no state change.
        if basis_present and ownership_block:
            governance_state = 'INVESTIGATE_BLOCKED_OWNERSHIP_VERIFICATION_REQUIRED'
            proposed_transition = False
            ownership_blocked += 1
            reasons = [
                'V16T_EXPLAINABLE_INVESTIGATION_BASIS_PRESENT',
                'OWNERSHIP_VERIFICATION_CONFLICT_BLOCKS_PROMOTION',
            ]
        elif basis_present:
            governance_state = 'INVESTIGATE_PROMOTION_ELIGIBLE_READ_ONLY'
            proposed_transition = True
            eligible += 1
            reasons = [
                'V16T_EXPLAINABLE_INVESTIGATION_BASIS_PRESENT',
                'NO_CURRENT_OWNERSHIP_CONFLICT_FLAG',
                'SEPARATE_OPERATIONAL_WRITE_REQUIRED_BEFORE_STATE_CHANGE',
            ]
        else:
            governance_state = 'INVESTIGATE_NOT_ELIGIBLE_NO_EXPLAINABLE_BASIS'
            proposed_transition = False
            nonbasis_blocked += 1
            reasons = ['V16T_EXPLAINABLE_INVESTIGATION_BASIS_ABSENT']

        state_counts[governance_state] += 1
        out.append({
            'parcel_id': pid,
            'source_v16t_state': source_state,
            'explainable_investigation_basis_present': basis_present,
            'manual_owner_verification_required': ownership_block,
            'ownership_verification_gate': item.get('ownership_verification_gate'),
            'governance_state': governance_state,
            'promotion_eligible_read_only': proposed_transition,
            'governance_reasons': reasons,
            'basis_reasons': list(item.get('basis_reasons') or []),
            'current_event_reasons': list(item.get('current_event_reasons') or []),
            'temporal_state': item.get('temporal_state'),
            'investigate_state_change': False,
            'database_write_performed': False,
            'contact_authorized': False,
            'seller_intent': False,
        })

    # Operational presentation only: eligible proposals, ownership blocks, then
    # non-basis records. This is not a seller ranking or likelihood score.
    order = {
        'INVESTIGATE_PROMOTION_ELIGIBLE_READ_ONLY': 0,
        'INVESTIGATE_BLOCKED_OWNERSHIP_VERIFICATION_REQUIRED': 1,
        'INVESTIGATE_NOT_ELIGIBLE_NO_EXPLAINABLE_BASIS': 2,
    }
    out.sort(key=lambda x: (order.get(x['governance_state'], 9), x['parcel_id']))

    return {
        'status': 'ok', 'version': VERSION, 'mode': MODE,
        'generated_at': datetime.now(timezone.utc).isoformat(),
        'market_code': basis.get('market_code'),
        'source_population': {
            'v16t_items_evaluated': len(source_items),
            'v16t_explainable_basis_records': sum(1 for x in source_items if x.get('explainable_investigation_basis_present')),
        },
        'governance_summary': {
            'investigate_promotion_eligible_read_only': eligible,
            'ownership_verification_blocked_basis_records': ownership_blocked,
            'nonbasis_records_not_eligible': nonbasis_blocked,
            'governance_state_counts': dict(sorted(state_counts.items())),
        },
        'investigate_governance': {'items': out, 'items_returned': len(out)},
        'interpretation': {
            'purpose': 'Test INVESTIGATE promotion governance without changing operational state.',
            'eligibility_rule': 'Requires a V16T explainable investigation basis and no current ownership-conflict flag.',
            'ownership_rule': 'A basis record requiring manual ownership verification remains blocked from INVESTIGATE promotion in this test.',
            'authority_boundary': 'Promotion eligibility is a read-only governance result, not an INVESTIGATE state change, seller intent claim, contact authorization, or outreach authority.',
            'next_if_verified': 'Only after this governance test is verified may a separate isolated version test the controlled operational INVESTIGATE state transition.',
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
        'ownership_conflict_can_promote': False,
        'historical_only_event_can_qualify_alone': False,
    }
