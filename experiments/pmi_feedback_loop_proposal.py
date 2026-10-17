"""Isolated proposal only: derived property research, never seller qualification."""
from datetime import date
from seller_ai_memory import digest
from pmi_case_sources import _valid_url, SOURCE_SPECS

VERSION = "PROPERTY_FEEDBACK_LOOP_PROPOSAL_V1"
DIMENSIONS = {"property_form": "form", "project_status": "project",
              "current_use": "use", "occupancy_status": "use"}
POSITIVE = {"USEFUL_INVESTIGATION"}
NEGATIVE = {"FALSE_POSITIVE", "SOURCE_ERROR"}
MAX_INVENTORY = 200
MAX_CANDIDATES = 3

def checked_sources(case, sources):
    output, rejected = [], []
    for s in sources:
        rows = s.get("records", [])
        if (s.get("source_key") not in {"parcel", "owner", "transfer_current", "transfer_history"}
                or s.get("status") not in {"SUCCESS", "EMPTY"} or not s.get("complete")
                or s.get("expected_count") != len(rows)
                or not _valid_url(s.get("query_url", "")) or not s.get("observed_at")
                or not any(key == s.get("source_key") and ("/" + service + "/") in s.get("query_url", "") for key, _, service in SOURCE_SPECS)
                or any(str(r.get("PARCELID")) != str(case["parcel_id"]) for r in rows)
                or any("OBJECTID" not in r for r in rows)):
            rejected.append(s.get("source_key"))
            continue
        # Canonical row order: a pagination reorder isn't new property evidence.
        rows = sorted(rows, key=lambda r: str(r["OBJECTID"]))
        value = {"case_id": case["case_id"], "parcel_id": case["parcel_id"],
                 "source_key": s["source_key"], "records": rows,
                 "source_url": s["query_url"],
                 "recorded_dates": s.get("recorded_dates", []),
                 "meaning": "SOURCE_REPORTS_ONLY",
                 "current_occupancy_established": False}
        value["evidence_id"] = "source_" + digest(value)
        output.append(value)
    return sorted(output, key=lambda x: x["source_key"]), rejected

def explicit_facts(case, as_of, max_age_days):
    facts, excluded, conflicts = {}, [], []
    for event in case.get("evidence", []):
        data = event["data"]
        field = data.get("field")
        if data.get("kind") != "FACT" or field not in DIMENSIONS:
            continue
        try:
            observed = date.fromisoformat(data["observed_at"][:10])
            age = (as_of - observed).days
        except (KeyError, TypeError, ValueError):
            age = -1
        if (not data.get("verified") or not data.get("current")
                or age < 0 or age > max_age_days
                or not (data.get("source_url") or data.get("source_record_id"))):
            excluded.append({"event_id": event["event_id"], "reason": "UNVERIFIED_UNDATED_OR_NOT_CURRENT"})
            continue
        facts.setdefault(field, []).append({"event_id": event["event_id"],
            "value": data["value"], "observed_at": data["observed_at"],
            "source": data.get("source_url") or data.get("source_record_id")})
    # Explicit supersession only. Newer timestamps alone never erase disagreement.
    superseded = {e["data"].get("supersedes") for e in case.get("evidence", [])
                  if e["data"].get("verified") and e["data"].get("supersedes")}
    usable = {}
    for field, values in facts.items():
        values = [v for v in values if v["event_id"] not in superseded]
        if not values:
            continue
        if len({str(v["value"]).casefold() for v in values}) > 1:
            conflicts.append({"field": field, "observations": values})
        else:
            usable[field] = values
    return usable, excluded, conflicts

def chosen_review(case):
    reviews = [e for e in case["history"] if e["kind"] == "REVIEW"]
    reviews = [e for e in reviews if e["data"].get("verified")
               and any(str(t).startswith("selection_route:") for t in e["data"].get("pattern_tags", []))]
    return sorted(reviews, key=lambda e: (e["recorded_at"], e["event_id"]))[-1] if reviews else None

def reassess(case, sources, *, previous=None, as_of, max_age_days=30):
    checked, rejected = checked_sources(case, sources)
    facts, unknown, conflicts = explicit_facts(case, as_of, max_age_days)
    review = chosen_review(case)
    state = "AWAITING_EXPLICIT_REVIEW"
    if review:
        state = ("REVIEW_SUPPORTS_PROPERTY_RESEARCH" if review["data"]["outcome"] in POSITIVE
                 else "REVIEW_CONTRADICTS_ORIGINAL" if review["data"]["outcome"] in NEGATIVE
                 else "REVIEW_RETAINED_NO_PROPERTY_DECISION")
    old = {s["source_key"]: s for s in (previous or {}).get("source_evidence", [])}
    changed = []
    for s in checked:
        prior = old.get(s["source_key"])
        if prior and prior["evidence_id"] != s["evidence_id"]:
            before = {str(r["OBJECTID"]): r for r in prior["records"]}
            after = {str(r["OBJECTID"]): r for r in s["records"]}
            for oid in sorted(before.keys() | after.keys()):
                a, b = before.get(oid, {}), after.get(oid, {})
                delta = {k: {"before": a.get(k), "after": b.get(k)}
                         for k in a.keys() | b.keys() if a.get(k) != b.get(k)}
                if delta:
                    changed.append({"source_key": s["source_key"], "object_id": oid,
                                    "fields": delta, "prior_evidence_id": prior["evidence_id"],
                                    "new_evidence_id": s["evidence_id"]})
    result = {"version": VERSION, "case_id": case["case_id"],
              "original_baseline_revision": digest(case["baseline"]),
              "review_reference": None if not review else {k: review["data"][k]
                  for k in ("event_id", "analysis_id", "hypothesis_id", "case_revision", "outcome")},
              "assessment": state, "source_evidence": checked, "rejected_sources": rejected,
              "usable_explicit_facts": facts, "excluded_observations": unknown,
              "contradictions": conflicts,
              "source_changes": changed,
              "needs_source_recheck": bool(changed or conflicts or rejected),
              "seller_intent": "UNKNOWN", "contact_authorized": False,
              "rules_adopted": 0,
              "next_question": "Reconcile changed records and dated use observations; confirm the owner's objective independently."}
    # Evidence change notices are retained in the prior version, not fresh learning.
    if previous and not changed:
        result["source_changes"] = previous.get("source_changes", [])
        result["needs_source_recheck"] = bool(result["source_changes"] or conflicts or rejected)
    result["projection_id"] = digest(result)
    return result

def compare(seed, inventory, *, as_of, max_age_days=30, assessments=None):
    review = chosen_review(seed)
    if not review or review["data"]["outcome"] not in POSITIVE:
        return {"candidates": [], "excluded": [], "reason": "NO_VERIFIED_USEFUL_PROPERTY_REVIEW"}
    seed_facts, _, conflicts = explicit_facts(seed, as_of, max_age_days)
    if conflicts:
        return {"candidates": [], "excluded": [], "reason": "SEED_EVIDENCE_CONFLICT"}
    route_tags = set(review["data"]["pattern_tags"])
    candidates, excluded = [], []
    cases = sorted(inventory, key=lambda c: c["case_id"])[:MAX_INVENTORY]
    for case in cases:
        if case["case_id"] == seed["case_id"]:
            continue
        current_review = chosen_review(case)
        routes = {"selection_route:" + h["route"] for h in case["baseline"]["hypotheses"]
                  if h["disposition"] == "SUPPORTED"}
        facts, unknown, conflicts = explicit_facts(case, as_of, max_age_days)
        shared = [f for f in seed_facts if f in facts
                  and str(seed_facts[f][0]["value"]).casefold() == str(facts[f][0]["value"]).casefold()]
        differences = [f for f in seed_facts if f in facts and f not in shared]
        if current_review and current_review["data"]["outcome"] in NEGATIVE:
            reason = "REVIEWED_FALSE_POSITIVE"
        elif not route_tags.intersection(routes):
            reason = "NO_SUPPORTED_SHARED_EXPLANATION"
        elif conflicts or differences:
            reason = "CONTRADICTORY_OBSERVATIONS"
        elif len({DIMENSIONS[f] for f in shared}) < 2:
            reason = "INSUFFICIENT_INDEPENDENT_PROPERTY_DIMENSIONS"
        else:
            candidates.append({"case_id": case["case_id"],
                "informed_by_review": review["event_id"],
                "review_analysis_id": review["data"]["analysis_id"],
                "shared_explanation_tags": sorted(route_tags.intersection(routes)),
                "supporting_evidence": {f: {"seed": seed_facts[f], "candidate": facts[f]} for f in shared},
                "contradictions": conflicts, "excluded_observations": unknown,
                "daily_source_changes": (assessments or {}).get(case["case_id"], {}).get("source_changes", []),
                "missing_information": ["Current owner objective", "Independent check of original property opportunity"],
                "next_question": "Does the reviewed property explanation hold here, and what source would disprove it?",
                "basis": "BOUNDED_RESEARCH_COMPARISON_ONLY", "seller_intent": "UNKNOWN",
                "contact_authorized": False})
            continue
        excluded.append({"case_id": case["case_id"], "reason": reason})
    return {"version": VERSION, "candidates": candidates[:MAX_CANDIDATES],
            "excluded": excluded, "inventory_examined": len(cases),
            "inventory_truncated": len(inventory) > MAX_INVENTORY,
            "candidate_limit": MAX_CANDIDATES, "rules_adopted": 0}

def persist_projection(store, projection):
    # Reuses append-only memory; isolated proof adapter, not installed in runtime.
    from pmi_review_store import _TransactionMemory
    with store._session(write=True) as connection:
        memory = _TransactionMemory(connection, store.postgres)
        return memory._append("property_projection:" + projection["projection_id"],
            "PROPERTY_FEEDBACK_PROJECTION", projection["case_id"], "", projection)
