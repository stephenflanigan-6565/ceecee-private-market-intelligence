#!/usr/bin/env python3
"""V16V — Controlled operational INVESTIGATE state transition.

Uses the proven V16U governance result as the sole promotion authority and the
proven V16D investigation_state table as the sole operational state store.
Only the three previously verified V16U-eligible Westhampton Beach parcels may
transition to INVESTIGATE. Ownership-conflicted basis records remain blocked.
Contact authorization and seller-intent inference remain hard OFF.
"""
import json
from datetime import datetime, timezone

from db import connect, execute
from investigate_promotion_governance_v16u import build_investigate_promotion_governance_v16u

VERSION = 'V16V'
MODE = 'CONTROLLED_OPERATIONAL_INVESTIGATE_STATE_TRANSITION'
PILOT = 'WESTHAMPTON_BEACH_NY'

EXPECTED_ELIGIBLE = {
    '0905004010100063000',
    '0905011000300030000',
    '0905019020100046000',
}
EXPECTED_OWNERSHIP_BLOCKED = {
    '0905008000100037000',
    '0905018000200001005',
}
EXPECTED_V16U_ITEMS = 32


def _now():
    return datetime.now(timezone.utc).isoformat()


def _rollback(c):
    try:
        c.rollback()
    except Exception:
        pass


def build_investigate_state_transition_v16v():
    governance = build_investigate_promotion_governance_v16u()
    if governance.get('status') != 'ok':
        return _failed('V16U_PREREQUISITE_FAILED')

    items = list(governance.get('investigate_governance', {}).get('items', []))
    eligible_items = [x for x in items if x.get('governance_state') == 'INVESTIGATE_PROMOTION_ELIGIBLE_READ_ONLY']
    blocked_items = [x for x in items if x.get('governance_state') == 'INVESTIGATE_BLOCKED_OWNERSHIP_VERIFICATION_REQUIRED']
    eligible_ids = {str(x.get('parcel_id')) for x in eligible_items}
    blocked_ids = {str(x.get('parcel_id')) for x in blocked_items}

    # Fail closed before opening the write transaction if the proven V16U
    # contract has changed in any material way.
    if len(items) != EXPECTED_V16U_ITEMS:
        return _failed('V16U_ITEM_COUNT_GUARD_FAILED', {'found': len(items), 'expected': EXPECTED_V16U_ITEMS})
    if eligible_ids != EXPECTED_ELIGIBLE:
        return _failed('V16U_ELIGIBLE_SET_GUARD_FAILED', {'found': sorted(eligible_ids), 'expected': sorted(EXPECTED_ELIGIBLE)})
    if blocked_ids != EXPECTED_OWNERSHIP_BLOCKED:
        return _failed('V16U_OWNERSHIP_BLOCKED_SET_GUARD_FAILED', {'found': sorted(blocked_ids), 'expected': sorted(EXPECTED_OWNERSHIP_BLOCKED)})
    if eligible_ids & blocked_ids:
        return _failed('V16U_ELIGIBLE_BLOCKED_OVERLAP_GUARD_FAILED')

    c = connect()
    try:
        # V16V does not create or migrate schema. The proven V16D state layer
        # must already exist and contain every bounded target row.
        target_ids = sorted(EXPECTED_ELIGIBLE | EXPECTED_OWNERSHIP_BLOCKED)
        before = {}
        for pid in target_ids:
            row = execute(c, """SELECT state,reason_json,trigger_count,first_entered_at,last_evaluated_at,
                                      contact_authorized,seller_intent_inferred
                               FROM investigation_state
                               WHERE market_code=? AND parcel_id=?""", (PILOT, pid)).fetchone()
            if row is None:
                _rollback(c)
                return _failed('V16D_STATE_ROW_MISSING_ABORTED_ZERO_WRITES', {'parcel_id': pid})
            before[pid] = {
                'state': str(row[0]),
                'reason_json': str(row[1]),
                'trigger_count': int(row[2] or 0),
                'first_entered_at': row[3],
                'last_evaluated_at': row[4],
                'contact_authorized': bool(row[5]),
                'seller_intent_inferred': bool(row[6]),
            }

        # Blocked records must not already be INVESTIGATE. If they are, stop;
        # V16V will never silently normalize or conceal a governance breach.
        already_bad = [pid for pid in sorted(EXPECTED_OWNERSHIP_BLOCKED) if before[pid]['state'] == 'INVESTIGATE']
        if already_bad:
            _rollback(c)
            return _failed('OWNERSHIP_BLOCKED_RECORD_ALREADY_INVESTIGATE_ABORTED_ZERO_WRITES', {'parcel_ids': already_bad})

        now = _now()
        changed = []
        already_investigate = []
        for item in eligible_items:
            pid = str(item['parcel_id'])
            old = before[pid]
            first = old['first_entered_at'] or now
            explanation = {
                'operational_authority': 'V16U_VERIFIED_PROMOTION_GOVERNANCE',
                'source_basis': 'V16T_EXPLAINABLE_INVESTIGATION_BASIS',
                'basis_reasons': list(item.get('basis_reasons') or []),
                'current_event_reasons': list(item.get('current_event_reasons') or []),
                'temporal_state': item.get('temporal_state'),
                'ownership_verification_gate': item.get('ownership_verification_gate'),
                'manual_owner_verification_required': False,
                'rule': 'INVESTIGATE means investigate, not seller. Contact remains separately governed.',
                'seller_intent': False,
            }
            reason_json = json.dumps(explanation, sort_keys=True, separators=(',', ':'))
            execute(c, """UPDATE investigation_state
                       SET state=?, reason_json=?, first_entered_at=?, last_evaluated_at=?,
                           contact_authorized=0, seller_intent_inferred=0
                       WHERE market_code=? AND parcel_id=?""",
                    ('INVESTIGATE', reason_json, first, now, PILOT, pid))
            if old['state'] == 'INVESTIGATE':
                already_investigate.append(pid)
            else:
                changed.append(pid)

        c.commit()

        after = {}
        for pid in target_ids:
            row = execute(c, """SELECT state,trigger_count,first_entered_at,last_evaluated_at,
                                      contact_authorized,seller_intent_inferred
                               FROM investigation_state
                               WHERE market_code=? AND parcel_id=?""", (PILOT, pid)).fetchone()
            after[pid] = {
                'state': str(row[0]),
                'trigger_count': int(row[1] or 0),
                'first_entered_at': row[2],
                'last_evaluated_at': row[3],
                'contact_authorized': bool(row[4]),
                'seller_intent_inferred': bool(row[5]),
            }

        eligible_verified = all(
            after[pid]['state'] == 'INVESTIGATE' and
            not after[pid]['contact_authorized'] and
            not after[pid]['seller_intent_inferred']
            for pid in EXPECTED_ELIGIBLE
        )
        blocked_untouched = all(
            after[pid]['state'] == before[pid]['state'] and
            after[pid]['first_entered_at'] == before[pid]['first_entered_at'] and
            after[pid]['last_evaluated_at'] == before[pid]['last_evaluated_at'] and
            after[pid]['trigger_count'] == before[pid]['trigger_count'] and
            after[pid]['contact_authorized'] == before[pid]['contact_authorized'] and
            after[pid]['seller_intent_inferred'] == before[pid]['seller_intent_inferred']
            for pid in EXPECTED_OWNERSHIP_BLOCKED
        )

        return {
            'status': 'ok' if eligible_verified and blocked_untouched else 'failed',
            'version': VERSION,
            'mode': MODE,
            'market_code': PILOT,
            'source_governance': {
                'version': 'V16U',
                'items_evaluated': len(items),
                'eligible_count': len(eligible_ids),
                'ownership_blocked_count': len(blocked_ids),
                'contract_guard_passed': True,
            },
            'transition': {
                'eligible_parcel_ids': sorted(EXPECTED_ELIGIBLE),
                'changed_to_investigate_this_run': sorted(changed),
                'already_investigate_idempotent': sorted(already_investigate),
                'ownership_blocked_parcel_ids': sorted(EXPECTED_OWNERSHIP_BLOCKED),
                'eligible_verified_investigate': eligible_verified,
                'ownership_blocked_records_untouched': blocked_untouched,
            },
            'before_states': {pid: before[pid]['state'] for pid in target_ids},
            'after_states': {pid: after[pid]['state'] for pid in target_ids},
            'guards': {
                'database_writes': True,
                'write_scope': 'ONLY_THREE_V16U_VERIFIED_ELIGIBLE_INVESTIGATION_STATE_ROWS',
                'new_table_created': False,
                'schema_migration_performed': False,
                'ownership_conflict_promoted': False,
                'contact_authorized': False,
                'seller_intent_inferred': False,
                'seller_scoring': False,
                'outreach_touched': False,
                'owner_names_addresses_emitted': False,
                'sensitive_motivation_inferred': False,
                'price_or_luxury_gate_used': False,
            },
            'interpretation': [
                'Exactly the V16U-eligible records may hold operational INVESTIGATE state.',
                'The two ownership-conflicted factual-basis records remain blocked and untouched.',
                'INVESTIGATE is an internal research state only; it does not authorize contact or imply seller intent.',
                'Repeated execution is bounded and idempotent with respect to the three eligible INVESTIGATE states.',
            ],
            'next_locked_step': 'VERIFY_INVESTIGATION_INBOX_READS_THE_THREE_PERSISTED_INVESTIGATE_RECORDS',
        }
    except Exception:
        _rollback(c)
        raise
    finally:
        c.close()


def _failed(error, detail=None):
    out = {
        'status': 'failed', 'version': VERSION, 'mode': MODE, 'error': error,
        'guards': {
            'database_writes': False,
            'investigate_state_touched': False,
            'contact_authorized': False,
            'seller_intent_inferred': False,
            'seller_scoring': False,
            'outreach_touched': False,
        },
    }
    if detail is not None:
        out['detail'] = detail
    return out
