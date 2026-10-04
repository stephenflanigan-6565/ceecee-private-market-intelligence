#!/usr/bin/env python3
from datetime import datetime, timezone

VERSION = 'C210_CLOSE1'

def build_c210_close1():
    return {
        'status': 'ok',
        'version': VERSION,
        'mode': 'READ_ONLY_CLASS_210_ASSESSMENT_CAUSE_CLOSEOUT',
        'generated_at': datetime.now(timezone.utc).isoformat(),
        'target': {
            'parcel_id': '0905008000100024000',
            'property_address': '104 ONECK LN',
            'property_class': '210',
            'assessment_route_survives': False,
            'family': 'STAGED_PROPERTY_IMPROVEMENT_EVOLUTION_WITH_SOURCE_CONFLICT',
            'authoritative_timeline': {
                '2016': 'PRIOR_VILLAGE_ZBA_DETERMINATION_D16026_REFERENCED_BY_2020_RECORD',
                '2020': 'VILLAGE_ZBA_RECORD_DOCUMENTS_EXISTING_SINGLE_FAMILY_PROPERTY_AND_PROPOSED_DETACHED_STRUCTURE_GARAGE_PATIO_MODIFICATIONS'
            },
            'supporting_public_permit_context': {
                '2011': 'PUBLIC_PERMIT_HISTORY_REPORTS_NEW_RESIDENCE_PERMIT_COMPLETE'
            },
            'secondary_source_conflict_retained': {
                'field': 'year_built',
                'values': [2015, 2019],
                'status': 'CONFLICTED_NOT_USED_AS_CAUSAL_ANCHOR'
            },
            'assessment_context': {
                '2017_land': 438100.0,
                '2017_total': 683300.0,
                '2017_improvement_derived': 245200.0,
                '2025_land': 257700.0,
                '2025_improvement': 577050.0,
                'history_character': 'STAGED_CHANGE_NOT_SINGLE_RECENT_REDEVELOPMENT_DISCONTINUITY'
            },
            'meaning': 'Municipal records establish an existing residence with a multi-year sequence of accessory/structural modification activity. Conflicting secondary year-built fields are not reliable causal anchors. The assessment pattern is therefore treated as staged property/improvement evolution rather than an unexplained single-family assessment anomaly.',
            'next_research_need': 'NO_FURTHER_CLASS_210_ASSESSMENT_CAUSE_RESEARCH; RETAIN SOURCE CONFLICT AS PROPERTY_HISTORY_INTEGRITY FLAG; PRESERVE INDEPENDENT PROPERTY_LAND_OWNERSHIP_ROUTES',
            'seller_intent': 'UNKNOWN',
            'contact_authorized': False,
            'independent_other_routes_preserved': True
        },
        'class_210_branch_closeout': {
            'original_class_210_cases': 19,
            'assessment_routes_causally_resolved_or_invalidated': 19,
            'assessment_routes_remaining_unresolved': 0,
            'assessment_anomaly_branch_closed': True,
            'independent_routes_preserved': True,
            'do_not_convert_route_kill_into_property_kill': True
        },
        'reusable_pattern': {
            'name': 'STAGED_PROPERTY_IMPROVEMENT_EVOLUTION_WITH_SOURCE_CONFLICT',
            'required_evidence': [
                'AUTHORITATIVE_OR_STRONG_MUNICIPAL_MULTI_YEAR_PROPERTY_MODIFICATION_TIMELINE',
                'ASSESSMENT_HISTORY_SHOWS_STAGED_CHANGE',
                'CONFLICTING_SECONDARY_YEAR_BUILT_NOT_USED_AS_CAUSAL_ANCHOR'
            ],
            'effect': 'KILL_ASSESSMENT_ANOMALY_ROUTE_ONLY_WHEN_STAGED_PROPERTY_EVOLUTION_MATERIALLY_EXPLAINS_THE_PATTERN',
            'not_sufficient_alone': ['YEAR_BUILT_CONFLICT', 'RECENT_SALE', 'ONE_PERMIT', 'ASSESSMENT_CHANGE_WITHOUT_PROPERTY_CONTEXT']
        },
        'next_if_verified': 'CLOSE CLASS_210 ASSESSMENT_CAUSE BRANCH; RETURN TO BROADER PMI FIND ENGINE AND PRESERVE ALL INDEPENDENT PROPERTY_LAND_OWNERSHIP_MARKET_RELATIONSHIP ROUTES',
        'database_writes': 0,
        'guards': {
            'database_writes': False,
            'external_calls': False,
            'schema_changes': False,
            'investigate_state_touched': False,
            'v19v_touched': False,
            'seller_qualification_changes': False,
            'seller_intent_inferred': False,
            'seller_scoring': False,
            'overall_ranking': False,
            'contact_authorized': False,
            'outreach_touched': False
        }
    }
