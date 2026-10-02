#!/usr/bin/env python3
from persistent_evidence_reevaluation_v17e3 import build_persistent_evidence_reevaluation_v17e3

VERSION='V17F'
MODE='UNRESOLVED_FACTUAL_RESEARCH_ROUTER_READ_ONLY'

ROUTES={
 'RECORDED_PARTY_ROLES_NOT_EXPOSED_BY_GIS': {
   'resolution_channel':'SUFFOLK_COUNTY_CLERK_MANUAL_VERIFICATION',
   'automation_status':'MANUAL_AUTHORIZED_SOURCE_REQUIRED',
   'research_action':'Verify Grantor/Grantee and instrument relationship in the official Clerk land-record result.',
   'why':'County GIS transfer history does not expose recorded party roles.'},
 'ONE_OR_MORE_TARGET_EVENTS_LACK_RECORDDATE_OR_LIBERPAGE': {
   'resolution_channel':'SUFFOLK_COUNTY_CLERK_MANUAL_VERIFICATION',
   'automation_status':'MANUAL_AUTHORIZED_SOURCE_REQUIRED',
   'research_action':'Verify the target conveyance recording date and Liber/Page from the official Clerk land-record result.',
   'why':'ENTRYDATE cannot be substituted for RECORDDATE and the GIS row lacks instrument identity fields.'},
 'WHY_SOURCE_DOCUMENT_DATE_FIELD_CONTAINS_1112_11_11': {
   'resolution_channel':'SOURCE_RECORD_VALIDATION',
   'automation_status':'MANUAL_AUTHORIZED_SOURCE_REQUIRED',
   'research_action':'Inspect the authoritative land-record result/image metadata for the historical instrument and preserve the 1112-11-11 source value unless authoritative evidence explains it.',
   'why':'V17C established that 1112-11-11 is the source DOCDATE field anomaly, not the recording date.'}
}

def build_unresolved_research_router_v17f():
    src=build_persistent_evidence_reevaluation_v17e3()
    if src.get('status')!='ok':
        return {'status':'failed','version':VERSION,'error':'V17E3 prerequisite failed'}
    qs=((src.get('reevaluation') or {}).get('unresolved_questions') or [])
    jobs=[]; unknown_route=[]
    for i,q in enumerate(qs,1):
        code=q.get('unknown')
        rule=ROUTES.get(code)
        if rule is None:
            unknown_route.append(code)
            rule={'resolution_channel':'UNCLASSIFIED_RESEARCH_REVIEW','automation_status':'NO_ROUTE_ASSIGNED',
                  'research_action':'Review this unresolved factual question without changing operational state.',
                  'why':'No governed research route is defined for this unknown code.'}
        jobs.append({'job_id':f'V17F:{i:02d}','parcel_id':q.get('parcel_id'),
                     'research_request_id':q.get('research_request_id'),'unresolved_code':code,**rule})
    by_channel={}
    for j in jobs: by_channel[j['resolution_channel']]=by_channel.get(j['resolution_channel'],0)+1
    return {'status':'ok','version':VERSION,'mode':MODE,'market_code':src.get('market_code'),
      'source_contract':{'version':src.get('version'),'unresolved_received':len(qs)},
      'routing_summary':{'jobs_prepared':len(jobs),'automatic_external_retrieval_jobs':0,
                         'manual_authoritative_verification_jobs':sum(1 for j in jobs if j['automation_status']=='MANUAL_AUTHORIZED_SOURCE_REQUIRED'),
                         'unclassified_jobs':len(unknown_route),'by_channel':by_channel},
      'research_jobs':jobs,
      'decision':{'safe_to_auto_retrieve_from_current_sources':False,
                  'reason':'REMAINING_QUESTIONS_REQUIRE_PARTY_OR_INSTRUMENT_DETAILS_NOT_EXPOSED_BY_CURRENT_GIS_SOURCE'},
      'guards':{'database_writes':False,'external_retrieval_performed':False,'clerk_site_scraped':False,
                'investigate_state_touched':False,'new_candidate_created':False,'seller_intent_inferred':False,
                'seller_scoring':False,'contact_authorized':False,'outreach_touched':False}}
