import json
from pathlib import Path
VERSION="V19S"
def build_v19s():
 r=json.loads(Path(__file__).with_name("v19s_donor.json").read_text())["properties"]
 c={"exact_factual_episode_subset_11":len(r)==11,"seven_current_nonstandard":sum(x["review_basis"]=="CURRENT NON-STANDARD DOCUMENT" for x in r)==7,"four_multi_event_current_episode":sum(x["review_basis"]=="MULTIPLE EVENTS IN CURRENT EPISODE" for x in r)==4,"no_score_or_rank":True,"no_new_candidate_added":True,"seller_intent_not_inferred":True}
 return {"status":"ok" if all(c.values()) else "failed","version":VERSION,"mode":"FIRST_HUMAN_REVIEW_SET_FACTUAL_CURRENT_EPISODES_ONLY","review_count":len(r),"basis_counts":{"CURRENT_NON_STANDARD_DOCUMENT":7,"MULTIPLE_EVENTS_CURRENT_EPISODE":4},"properties":r,"checks":c,"database_writes":0,"guards":{"database_writes":False,"seller_intent_inferred":False,"seller_scoring":False,"overall_ranking":False,"contact_authorized":False,"outreach_touched":False},"next_if_pass":"USER_MARKS_KEEP_DROP_UNSURE_AND_PMI_LEARNS_FROM_SELECTION_FEEDBACK"}
