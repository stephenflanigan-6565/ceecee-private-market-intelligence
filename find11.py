#!/usr/bin/env python3
import os,json,math,urllib.parse,urllib.request
from collections import Counter
from datetime import datetime,timezone
from find2 import build_find2

VERSION='FIND11'
MARKET='WESTHAMPTON_BEACH_NY'
PARCEL_URL='https://gis.southamptontownny.gov/gisserver/rest/services/DataServices/TaxParcels/MapServer/0/query'

# EXPERIMENTAL observability thresholds only; these are not entitlement, value, seller-intent, or universal-market rules.
K_NEIGHBORS=12
MIN_NEWER_NEIGHBORS=3
MIN_YEAR_GAP=15
RECENT_QUANTILE=.85


def _get(params,timeout=15):
    q=urllib.parse.urlencode(params)
    req=urllib.request.Request(PARCEL_URL+'?'+q,headers={'User-Agent':'PMI-Research/1.0'})
    with urllib.request.urlopen(req,timeout=timeout) as r:
        return json.loads(r.read().decode('utf-8'))

def _town_coords():
    # One source, paged only if the service cap requires it. No owner fields requested.
    out={}; offset=0; pages=0
    while pages<5:
        d=_get({'f':'json','where':'1=1','outFields':'SCTM,X_COORD,Y_COORD','returnGeometry':'false',
                'resultOffset':offset,'resultRecordCount':2000,'orderByFields':'OBJECTID'})
        if d.get('error'): raise RuntimeError('Town parcel query error: '+str(d.get('error')))
        fs=d.get('features') or []; pages+=1
        for f in fs:
            a=f.get('attributes') or {}; pid=''.join(ch for ch in str(a.get('SCTM') or '') if ch.isdigit())
            try: x=float(a.get('X_COORD')); y=float(a.get('Y_COORD'))
            except: continue
            if len(pid)==19 and math.isfinite(x) and math.isfinite(y): out[pid]=(x,y)
        if len(fs)<2000: break
        offset += len(fs)
    return out,pages

def _q(xs,q):
    s=sorted(xs)
    if not s:return None
    pos=(len(s)-1)*q; lo=int(math.floor(pos)); hi=int(math.ceil(pos))
    if lo==hi:return s[lo]
    return s[lo]+(s[hi]-s[lo])*(pos-lo)

def build_find11():
    # Reuse the proven DB extraction from FIND2, but do not reuse its land-opportunity candidate selection.
    f2=build_find2(include_all_candidates=True)
    import psycopg
    conn=psycopg.connect(os.environ['DATABASE_URL'])
    try:
        cur=conn.cursor();cur.execute("""SELECT parcel_id,evidence_family,payload_json FROM evidence_ledger
          WHERE market_code=%s AND is_current=1 AND evidence_family=ANY(%s)
          ORDER BY parcel_id,evidence_family,evidence_key""",(MARKET,['PROPERTY_CONTEXT','ASSESSMENT_CONTEXT']))
        rows=cur.fetchall()
    finally: conn.close()
    # Use FIND2's field semantics helpers rather than create a second semantics contract.
    from find2 import _payload,_flat,_pick,_num,ALIASES
    by={}
    for pid,fam,pj in rows:
        d=by.setdefault(str(pid),{})
        for k,v in _flat(_payload(pj)).items():
            if k not in d and v not in (None,''): d[k]=v
    props=[]
    for pid,m in by.items():
        y=_num(_pick(m,ALIASES['year_built'])); addr=_pick(m,ALIASES['address']); pc=_pick(m,ALIASES['property_class'])
        if y is not None and 1600<=y<=datetime.now().year+1:
            props.append({'parcel_id':pid,'property_address':str(addr).strip() if addr else None,
                          'property_class':str(pc).strip() if pc else None,'year_built':int(y)})
    years=[p['year_built'] for p in props]; recent_cut=_q(years,RECENT_QUANTILE)
    coords,pages=_town_coords()
    spatial=[p for p in props if p['parcel_id'] in coords]
    for p in spatial:p['x'],p['y']=coords[p['parcel_id']]
    candidates=[]; reasons=Counter()
    for p in spatial:
        ds=[]
        for n in spatial:
            if n is p:continue
            dx=p['x']-n['x'];dy=p['y']-n['y']; ds.append((dx*dx+dy*dy,n))
        ds.sort(key=lambda z:z[0]); neigh=[n for _,n in ds[:K_NEIGHBORS]]
        if len(neigh)<K_NEIGHBORS:continue
        newer=[n for n in neigh if n['year_built']>=p['year_built']+MIN_YEAR_GAP]
        recent=[n for n in neigh if recent_cut is not None and n['year_built']>=recent_cut]
        # Require both materially newer local neighbors and a recent-construction presence.
        if len(newer)<MIN_NEWER_NEIGHBORS or len(recent)<MIN_NEWER_NEIGHBORS:continue
        local_years=[n['year_built'] for n in neigh]; med=sorted(local_years)[len(local_years)//2]
        if p['year_built']>=med:continue
        reasons['OLDER_SUBJECT_WITH_LOCAL_NEWER_REDEVELOPMENT_CONCENTRATION']+=1
        candidates.append({
          'parcel_id':p['parcel_id'],'property_address':p['property_address'],'property_class':p['property_class'],
          'observed_relationship':'OLDER_SUBJECT_WITH_LOCAL_NEWER_REDEVELOPMENT_CONCENTRATION',
          'subject_year_built':p['year_built'],'local_neighbor_count':len(neigh),
          'local_neighbor_year_built_median':med,'materially_newer_neighbor_count':len(newer),
          'recent_construction_neighbor_count':len(recent),'market_recent_year_cutoff':round(recent_cut,1) if recent_cut else None,
          'example_newer_neighbors':[{'parcel_id':n['parcel_id'],'property_address':n['property_address'],'year_built':n['year_built']} for n in sorted(newer,key=lambda z:z['year_built'],reverse=True)[:4]],
          'hypothesis':'LOCAL_REDEVELOPMENT_OR_REINVESTMENT_PATTERN_MAY_CREATE_PROPERTY_LEVEL_OPTIONALITY_OR_MISMATCH_WORTH_RESEARCHING',
          'state':'OBSERVED_DISCOVERY_HYPOTHESIS','seller_intent':'UNKNOWN','contact_authorized':False,
          'next_question':'Does one authoritative property/site fact materially support or destroy the redevelopment-halo hypothesis for this parcel?',
          'kill_tests':['LOCAL_NEWER_PATTERN_IS_NOT_SPATIALLY_COHERENT','SUBJECT_ALREADY_MATERIALLY_REDEVELOPED','SITE_OR_USE_CONSTRAINT_REMOVES_PLAUSIBLE_OPTIONALITY','PATTERN_IS_EXPLAINED_BY_NONCOMPARABLE_PROPERTY_FORM']})
    # deterministic presentation, not ranking: strongest count then parcel id
    candidates.sort(key=lambda r:(-r['recent_construction_neighbor_count'],-r['materially_newer_neighbor_count'],r['parcel_id']))
    return {'status':'ok','version':VERSION,'mode':'READ_ONLY_INDEPENDENT_REDEVELOPMENT_HALO_DISCOVERY_EXPERIMENT',
      'generated_at':datetime.now(timezone.utc).isoformat(),
      'purpose':'TEST_WHETHER_EXISTING_PROPERTY_YEAR_PLUS_PROVEN_TOWN_PARCEL_COORDINATES_CAN_OBSERVE_A_GENUINELY_INDEPENDENT_NEIGHBORHOOD_REDEVELOPMENT_HALO_RAIL',
      'architecture':{'opportunity_universe_family':'OU-023_NEIGHBORHOOD_REDEVELOPMENT_HALO / OU-024_NEW_CONSTRUCTION_ENCIRCLEMENT',
        'independent_of_land_assessment_ratio_route':True,'property_not_seller_model':True,'spatial_plus_temporal':True},
      'summary':{'working_property_universe':f2.get('summary',{}).get('whole_market_properties'),
        'valid_year_built_records':len(props),'town_coordinate_matches':len(spatial),'town_source_pages':pages,
        'market_recent_year_cutoff_for_experiment':round(recent_cut,1) if recent_cut else None,
        'observed_halo_candidates':len(candidates),'relationship_counts':dict(reasons)},
      'research_thresholds':{'status':'EXPERIMENTAL_OBSERVABILITY_ONLY_NOT_UNIVERSAL_RULES','nearest_neighbors':K_NEIGHBORS,
        'minimum_materially_newer_neighbors':MIN_NEWER_NEIGHBORS,'minimum_year_gap':MIN_YEAR_GAP,
        'recent_construction_definition':'TOP_15_PERCENT_OF_VALID_YEAR_BUILT_WITHIN_CURRENT_WHB_WORKING_UNIVERSE'},
      'candidates':candidates[:40],
      'candidate_payload':{'total':len(candidates),'returned':min(40,len(candidates)),'complete':len(candidates)<=40,'display_policy':'DETERMINISTIC_DIAGNOSTIC_NOT_OPERATOR_RANKING'},
      'interpretation_policy':{'observed_halo_not_opportunity_proof':True,'new_construction_nearby_not_seller_intent':True,
        'older_improvement_not_obsolescence_proof':True,'no_entitlement_or_buildability_inference':True,'unknown_valid_state':True,
        'data_serves_decision':True,'no_generic_enrichment':True,'human_originated_opportunities_may_enter_same_future_property_intelligence_framework':True},
      'database_writes':0,'guards':{'database_writes':False,'external_calls':True,'external_calls_read_only':True,'schema_changes':False,
        'v19v_touched':False,'seller_qualification_changes':False,'seller_intent_inferred':False,'seller_scoring':False,'overall_ranking':False,
        'contact_authorized':False,'outreach_touched':False},
      'next_if_verified':'COMPARE FIND11 CANDIDATES AGAINST EXISTING FIND9 DISCOVERY COVERAGE. PROMOTE ONLY IF THIS RAIL FINDS MEANINGFUL NOVEL PROPERTIES; OTHERWISE KILL OR REVISE THE RAIL WITHOUT ADDING DATA.'}

if __name__=='__main__':print(json.dumps(build_find11(),indent=2,sort_keys=True))
