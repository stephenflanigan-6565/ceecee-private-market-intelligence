#!/usr/bin/env python3
import json
from collections import Counter
from datetime import datetime, timezone
from find17 import build_find17

VERSION = 'FIND18'

# These are already-resolved authoritative Town zoning facts from the FIND5D/FIND6 evidence chain.
# FIND18 intentionally reuses memory; it does not make another external request.
RESOLVED_SITE_CONTEXT = {
    '0905009000200013011': {
        'property_address': '233 ONECK LN',
        'zone_code': 'R1',
        'zone_description': 'Residential 1',
        'dim_reg_observed': '40000',
        'site_use_evidence_state': 'SINGLE_ZONE_CONTEXT_RESOLVED',
        'source_state': 'PARCEL_AND_ZONING_RESOLVED',
    },
    '0905012000400025000': {
        'property_address': '36 SUNSET AVE',
        'zone_code': 'B1',
        'zone_description': 'Business District 1',
        'dim_reg_observed': '2000',
        'site_use_evidence_state': 'SITE_USE_CONTEXT_COMPLICATES_OR_SPECIALIZES_ROUTE',
        'source_state': 'PARCEL_AND_ZONING_RESOLVED',
    },
}

# Existing property/assessment facts already preserved in the property-intelligence chassis.
EXISTING_PROPERTY_CONTEXT = {
    '0905009000200013011': {
        'acres': 0.77,
        'assessment_total': 1017200.0,
        'land_assessment': 1017200.0,
        'improvement_assessment': 0.0,
        'land_share_of_assessment': 1.0,
        'prior_relationships': ['LAND_DOMINANT_UNDER_IMPROVEMENT'],
    },
    '0905012000400025000': {
        'acres': 1.0,
        'assessment_total': 658700.0,
        'land_assessment': 658700.0,
        'improvement_assessment': 0.0,
        'land_share_of_assessment': 1.0,
        'prior_relationships': ['LAND_DOMINANT_UNDER_IMPROVEMENT'],
    },
}

def _reason_case(f17):
    pid = str(f17.get('parcel_id'))
    z = RESOLVED_SITE_CONTEXT.get(pid)
    p = EXISTING_PROPERTY_CONTEXT.get(pid, {})
    base = {
        'parcel_id': pid,
        'property_address': f17.get('property_address'),
        'seller_intent': 'UNKNOWN',
        'contact_authorized': False,
        'property_form_evidence': {
            'state': f17.get('state'),
            'observed_prop_type': f17.get('observed_prop_type'),
            'orpts_interpretation': f17.get('orpts_interpretation'),
            'family': f17.get('property_form_family'),
        },
        'existing_property_context': p,
        'existing_site_use_context': z,
        'why_pmi_noticed_it': [
            'PRIOR_LAND_DOMINANT_UNDER_IMPROVEMENT_RELATIONSHIP',
            'FIND17_AUTHORITATIVE_PROPERTY_FORM_SUPPORTS_VACANT_OR_MINIMALLY_IMPROVED_FORM',
        ],
        'limits': [
            'ZONING_CONTEXT_IS_NOT_ENTITLEMENT',
            'DIM_REG_IS_PRESERVED_AS_AN_OBSERVED_ZONING_ATTRIBUTE_ONLY',
            'DIM_REG_SEMANTICS_NOT_ASSUMED',
            'PROPERTY_FORM_DOES_NOT_PROVE_CURRENT_PHYSICAL_CONDITION',
            'NO_BUILDABILITY_OR_DEVELOPMENT_CAPACITY_INFERENCE',
            'NO_SELLER_INTENT_INFERENCE',
        ],
    }
    if not z:
        base.update({
            'state': 'SITE_USE_CONTEXT_UNKNOWN_NONBLOCKING',
            'opportunity_branch': 'UNKNOWN',
            'hypothesis': 'OU_005_OR_OU_012_NOT_YET_SUPPORTED',
            'decision_effect': 'DO_NOT_RESEARCH_GENERICALLY; ONLY RESOLVE SITE_USE_IF THIS PROPERTY LATER SURVIVES FOR_ANOTHER_REASON',
            'next_best_question': 'None now.',
        })
        return base

    zone = z.get('zone_code')
    if zone and zone.startswith('R'):
        base.update({
            'state': 'RESIDENTIAL_INFILL_SITE_HYPOTHESIS_SUPPORTED_BUT_CONSTRAINT_UNRESOLVED',
            'opportunity_branch': 'OU_005_INFILL_RESIDENTIAL_SITE',
            'hypothesis': 'VACANT_OR_MINIMALLY_IMPROVED_PROPERTY_FORM_PLUS_RESIDENTIAL_ZONING_CONTEXT_SUPPORTS_A_REAL_INFILL_SITE_QUESTION',
            'decision_effect': 'PRESERVE_AS_RESIDENTIAL_INFILL_SITE_HYPOTHESIS; DO_NOT_CALL_BUILDABLE',
            'corroboration': [
                'VACANT_OR_MINIMALLY_IMPROVED_PROPERTY_FORM',
                'SINGLE_RESIDENTIAL_ZONE_CONTEXT_RESOLVED',
                'LAND_DOMINANT_ASSESSMENT_RELATIONSHIP',
            ],
            'contradictions_and_unknowns': [
                'LAWFUL_USE_AND_DIMENSIONAL_COMPLIANCE_NOT_PROVEN',
                'ACCESS_NOT_PROVEN',
                'SITE_CONSTRAINTS_NOT_PROVEN',
                'DIM_REG_MEANING_NOT_INFERRED',
            ],
            'next_best_question': 'Only if this property advances: what authoritative lawful-use or dimensional/site constraint fact most strongly determines whether a residential infill path is actually viable?',
        })
    elif zone in {'B1','HC','PC'}:
        base.update({
            'state': 'SPECIALIZED_SITE_USE_HBU_HYPOTHESIS_SUPPORTED',
            'opportunity_branch': 'OU_012_HIGHER_AND_BETTER_USE_OR_SPECIALIZED_SITE_USE',
            'hypothesis': 'VACANT_OR_MINIMALLY_IMPROVED_PROPERTY_FORM_PLUS_NONSTANDARD_RESIDENTIAL_SITE_USE_CONTEXT_SUPPORTS_A_HIGHER_AND_BETTER_USE_QUESTION',
            'decision_effect': 'DO_NOT_FORCE_INTO_RESIDENTIAL_INFILL; PRESERVE_SPECIALIZED_SITE_USE_OPTIONALITY',
            'corroboration': [
                'VACANT_OR_MINIMALLY_IMPROVED_PROPERTY_FORM',
                'BUSINESS_OR_MIXED_SITE_USE_CONTEXT',
                'LAND_DOMINANT_ASSESSMENT_RELATIONSHIP',
            ],
            'contradictions_and_unknowns': [
                'PERMITTED_USES_NOT_ENUMERATED_IN_CURRENT_EVIDENCE',
                'DEVELOPMENT_CAPACITY_NOT_PROVEN',
                'ACCESS_AND_SITE_CONSTRAINTS_NOT_PROVEN',
                'DIM_REG_MEANING_NOT_INFERRED',
            ],
            'next_best_question': 'Only if this property advances: which authoritative permitted-use or site-constraint fact would most strongly support or destroy the specialized/HBU opportunity?',
        })
    else:
        base.update({
            'state': 'SITE_USE_BRANCH_UNKNOWN_NONBLOCKING',
            'opportunity_branch': 'UNKNOWN',
            'hypothesis': 'PROPERTY_FORM_SUPPORTED_BUT_SITE_USE_MECHANISM_NOT_CLASSIFIED',
            'decision_effect': 'PRESERVE_PROPERTY_FORM_HYPOTHESIS_WITHOUT_GENERIC_RESEARCH',
            'next_best_question': 'None unless this property advances and site-use classification becomes material.',
        })
    return base

def build_find18():
    f17 = build_find17()
    supported = f17.get('supported_property_form_hypotheses') or []
    results = [_reason_case(x) for x in supported]
    states = Counter(x.get('state') for x in results)
    branches = Counter(x.get('opportunity_branch') for x in results)
    return {
        'status': 'ok',
        'version': VERSION,
        'mode': 'READ_ONLY_EXISTING_EVIDENCE_SITE_USE_BRANCHING_EXPERIMENT',
        'generated_at': datetime.now(timezone.utc).isoformat(),
        'purpose': 'TEST_WHETHER_EXISTING_PROPERTY_FORM_PLUS_ALREADY_RESOLVED_SITE_USE_CONTEXT_CAN_BRANCH_OU_004_INTO_OU_005_INFILL_OR_OU_012_HBU_WITHOUT_NEW_DATA_RESEARCH',
        'source_checkpoint': 'FIND17_SUPPORTED_PROPERTY_FORM_HYPOTHESES_PLUS_EXISTING_FIND5D_FIND6_SITE_USE_MEMORY',
        'architecture': {
            'existing_discovery_universe_properties': 230,
            'input_supported_find17_cases': len(supported),
            'external_lookup_required': False,
            'generic_zoning_enrichment': False,
            'reuses_resolved_site_context': True,
            'branching_not_ranking': True,
        },
        'summary': {
            'cases_tested': len(results),
            'states': dict(states),
            'opportunity_branches': dict(branches),
            'new_properties_created': 0,
            'existing_discovery_universe_properties': 230,
        },
        'results': results,
        'interpretation_policy': {
            'data_serves_decision': True,
            'property_form_first': True,
            'site_use_context_second': True,
            'zoning_not_entitlement': True,
            'dim_reg_not_silently_interpreted': True,
            'residential_infill_and_hbu_are_distinct_branches': True,
            'unknown_valid_state': True,
            'targeted_research_only_if_branch_advances': True,
            'route_kill_never_equals_property_kill': True,
            'seller_intent_remains_unknown': True,
        },
        'database_writes': 0,
        'guards': {
            'database_writes': False,
            'external_calls': False,
            'schema_changes': False,
            'v19v_touched': False,
            'seller_qualification_changes': False,
            'seller_intent_inferred': False,
            'seller_scoring': False,
            'overall_ranking': False,
            'contact_authorized': False,
            'outreach_touched': False,
        },
        'next_if_verified': 'PROMOTE SITE_USE_BRANCHING AS PROPERTY_INTELLIGENCE CONTEXT, NOT ENTITLEMENT. THEN RETURN TO THE FULL MARKET AND TEST THE NEXT GENUINELY INDEPENDENT DISCOVERY FAMILY; DO NOT DEEPEN THESE TWO PARCELS UNLESS A LATER DECISION MAKES THE MISSING SITE FACT MATERIAL.'
    }

if __name__ == '__main__':
    print(json.dumps(build_find18(), indent=2, sort_keys=True))
