"""Explain operator work without turning notes into facts or adopting rules.

This projection runs inside PMI's existing database connection. It uses saved
review history and the existing review-memory methods, without calling a model
or collecting any new property or personal data.
"""
from collections import Counter, defaultdict

VERSION = "PMI_REVIEW_LEARNING_V1"
CASE_LIMIT = 100
SUGGESTION_LIMIT = 25
GUARDS = {
    "external_calls": 0,
    "model_calls": 0,
    "case_writes": 0,
    "rules_adopted": 0,
    "seller_scores_created": 0,
    "seller_intent_inferred": False,
    "contact_authorized": False,
    "notes_promoted_to_facts": False,
    "schema_changes": False,
}


def build_report(cases, events, memory_inputs, lessons, suggestions, *, input_revision, generated_at):
    """Build bounded output while counting the entire current workspace.

    REVIEW events mirror core FEEDBACK records. Event identity, rather than row
    count, prevents those two records from counting as two completed reviews.
    Raw review counts retain corrections; outcome counts use the latest verified
    finding for each property and hypothesis. An unverified correction cannot
    erase an earlier verified finding.
    """
    by_case = {case["case_id"]: case for case in cases}
    case_events = defaultdict(list)
    reviews = {}
    for event in events:
        if event["case_id"] not in by_case:
            continue
        case_events[event["case_id"]].append(event)
        if event["kind"] == "REVIEW":
            reviews[event["event_id"]] = {
                "event_id": event["event_id"], "case_id": event["case_id"],
                "data": event["data"], "recorded_at": event["recorded_at"],
            }
    # Core feedback is the canonical saved finding, also when a historical core
    # review predates the workspace event mirror.
    for item in memory_inputs:
        if item["kind"] != "FEEDBACK" or item["case_id"] not in by_case:
            continue
        data = item["data"]
        event_id = data.get("event_id")
        if event_id:
            reviews[event_id] = {
                "event_id": event_id, "case_id": item["case_id"],
                "data": data, "recorded_at": item["recorded_at"],
            }
    case_reviews = defaultdict(list)
    latest_verified = {}
    for item in sorted(reviews.values(), key=lambda review: (review["recorded_at"], review["event_id"])):
        case_reviews[item["case_id"]].append(item)
        if item["data"].get("verified") is True:
            latest_verified[(item["case_id"], item["data"].get("hypothesis_id"))] = item
    verified_outcomes = Counter(item["data"]["outcome"] for item in latest_verified.values())
    notes_count = formal_count = evidence_count = 0
    reviewed_cases = []
    for case in sorted(cases, key=lambda item: ((item.get("property_address") or "").casefold(), item["case_id"])):
        history = case_events[case["case_id"]]
        findings = case_reviews[case["case_id"]]
        if not history and not findings:
            continue
        notes = [event for event in history if event["kind"] == "STATE" and event["data"].get("note")]
        evidence = [event for event in history if event["kind"] == "EVIDENCE"]
        verified = sum(item["data"].get("verified") is True for item in findings)
        notes_count += bool(notes)
        formal_count += bool(findings)
        evidence_count += len(evidence)
        state = ("VERIFIED_FINDINGS" if verified else "UNVERIFIED_FINDINGS" if findings
                 else "EVIDENCE_ONLY" if evidence else "NOTES_ONLY" if notes else "WORKFLOW_ONLY")
        reviewed_cases.append({
            "case_id": case["case_id"], "property_address": case.get("property_address"),
            "state": case["state"], "note_count": len(notes), "review_count": len(findings),
            "verified_review_count": verified, "evidence_count": len(evidence),
            "next_check": case.get("next_check") or "Check the saved explanation against a named source and record the finding.",
            "learning_state": state,
            # Context stays verbatim. It is never parsed into factual conditions
            # or passed to the pattern suggestion algorithm.
            "latest_note": notes[-1]["data"]["note"] if notes else None,
        })
    verified_events = sum(item["data"].get("verified") is True for item in reviews.values())
    status = "READY" if verified_events else "NEEDS_STRUCTURED_FINDINGS" if reviewed_cases else "NO_OPERATOR_REVIEWS"
    next_checks = []
    if not reviewed_cases:
        next_checks.append("Open one property, check why it surfaced, and save what you found.")
    else:
        without_verified = sum(case["verified_review_count"] == 0 for case in reviewed_cases)
        if without_verified:
            next_checks.append(
                f"For {without_verified} properties with operator work but no verified finding, record whether the explanation was useful, mistaken, disproved, or still unresolved, and name the source checked."
            )
        if verified_events:
            next_checks.append("Compare the verified useful findings with the false positives; check the cited evidence before approving any suggested discovery rule.")
        if verified_outcomes.get("SOURCE_ERROR"):
            next_checks.append("Recheck the properties with verified source errors against the official record and save a correction.")
        next_checks.append("Keep an unresolved owner plan separate from a useful property finding; record the next check rather than assuming the owner wants to sell.")
    return {
        "version": VERSION, "input_revision": input_revision, "generated_at": generated_at,
        "status": status,
        "counts": {
            "total_properties": len(cases), "properties_with_operator_work": len(reviewed_cases),
            "properties_with_notes": notes_count, "properties_with_formal_reviews": formal_count,
            "review_events": len(reviews), "verified_review_events": verified_events,
            "unverified_review_events": len(reviews) - verified_events, "evidence_records": evidence_count,
        },
        "workflow_stages": dict(sorted(Counter(case["state"] for case in cases).items())),
        "verified_outcomes": dict(sorted(verified_outcomes.items())),
        "lessons": lessons, "suggestions": suggestions[:SUGGESTION_LIMIT],
        "suggestion_count": len(suggestions), "reviewed_cases": reviewed_cases[:CASE_LIMIT],
        "next_checks": next_checks, "guards": dict(GUARDS),
    }
