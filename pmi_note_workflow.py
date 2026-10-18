"""Bounded, operator-confirmed note bridge. No source lookup or seller scoring."""
import re

UNKNOWN = {'unknown', 'not known', 'unsure', 'n/a', 'none', 'not supplied', '', 'unverified'}
FIELDS = ('listing_status', 'representation_status', 'condition', 'project_status',
          'property_form', 'current_use', 'occupancy_status', 'acquisition_context')


def unknown(value):
    return str(value).strip().casefold() in UNKNOWN


def propose(note):
    """Literal suggestions only. Whole exact note is retained as the passage.

    Relative dates, estimates and intentions are never resolved from entry time.
    An unsupported sentence remains context for the operator, not a guessed fact.
    """
    text = note['data']['note']
    lower = text.casefold()
    field, value = 'acquisition_context', 'UNKNOWN'
    if 'not been on the market' in lower or 'stopped trying to sell' in lower:
        field, value = 'listing_status', 'HISTORICAL_MARKETING'
    elif "don't have any information about the condition" in lower:
        field, value = 'condition', 'UNKNOWN'
    elif re.search(r'\bsold\b', lower):
        field, value = 'listing_status', 'UNKNOWN'  # negation/date needs human review
    return {'note_id': note['event_id'], 'passage': text, 'field': field, 'value': value,
            'source_ref': '', 'observed_at': '', 'verified': False, 'current': False,
            'entry_time': note['recorded_at']}


def assessment(facts, excluded, conflicts, evidence):
    """Evidence context qualifies research; never changes seller ranks or intent."""
    values = {field: str(rows[0]['value']).strip().upper().replace(' ', '_')
              for field, rows in facts.items()}
    listing = values.get('listing_status', 'UNKNOWN')
    representation = values.get('representation_status', 'UNKNOWN')
    reasons = []
    if conflicts:
        reasons.append('Conflicting supported observations require review before comparison.')
    if listing in {'SOLD', 'CLOSED'}:
        reasons.append('A completed sale is not a fresh seller lead. Future property research remains possible.')
    elif listing in {'LISTED', 'ACTIVE', 'ACTIVE_LISTING', 'REPRESENTED'} or representation == 'REPRESENTED':
        reasons.append('Listing or representation is reported; availability for a new listing is not established.')
    elif listing == 'HISTORICAL_MARKETING':
        reasons.append('Past marketing is historical context, not evidence of a current listing or sale plan.')
    else:
        reasons.append('Current listing availability is unknown; no seller lead is established.')
    if 'condition' not in facts:
        reasons.append('Current condition is unknown; do not treat a conditional value opinion as an as-is value.')
    for field in ('condition', 'project_status', 'property_form', 'current_use', 'occupancy_status'):
        if field in facts:
            reasons.append(f"Supported {field.replace('_', ' ')}: {facts[field][0]['value']}. Review its relevance to the original explanation.")
    historical = [e['event_id'] for e in evidence if e['data'].get('kind') == 'FACT'
                  and (not e['data'].get('current') or e['data'].get('field') == 'acquisition_context')]
    return {'listing_status': listing, 'representation_status': representation,
            'reasons': reasons, 'used_event_ids': sorted({r['event_id'] for rows in facts.values() for r in rows}),
            'historical_context_event_ids': historical, 'excluded': excluded,
            'needs_review': bool(conflicts or excluded or listing == 'UNKNOWN'),
            'seller_intent': 'UNKNOWN', 'selection_rules_changed': False}
