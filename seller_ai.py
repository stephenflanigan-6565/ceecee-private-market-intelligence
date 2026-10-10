"""PMI's internal evidence, hypothesis, and reviewed-case reasoning engine.

Standard library only. No model, API key, network client, or paid AI service.
The engine reasons within explicit, expandable patterns and retained outcomes.
"""
import argparse
import copy
import json
from pathlib import Path
import re

from opportunity_intelligence import evaluate_payload
from public_intelligence import build_public_context
from seller_ai_memory import ReviewMemory, digest

VERSION = "PMI_INTERNAL_INTELLIGENCE_V1"
OMIT = {
    "owner_identity", "owner_name", "names", "name", "mailing_address",
    "property_address", "address", "parcel_id", "phone", "email", "owner",
    "seller_intent", "contact_authorized", "operator_contract", "guards",
    "policy", "current_find_state", "route_state", "state", "recommended_action",
}
CLOSED = {"EXPLAINED_ROUTE_CLOSED", "VACANCY_HYPOTHESIS_CONTRADICTED_BY_PROPERTY_FORM"}

# Initial reasoning examples, not an exhaustive list of seller circumstances.
BUILTIN_PATTERNS = [{
    "pattern_id": "COMPLETED_PROJECT_UNUSED_PROPERTY",
    "title": "Completed project with an unused property",
    "conditions": [{"field": "project_status", "value": "COMPLETED"},
                   {"field": "current_use", "value": "VACANT"}],
    "contradictions": [{"field": "current_use", "value": "OCCUPIED"},
                       {"field": "project_status", "value": "IN_PROGRESS"},
                       {"field": "declared_strategy", "value": "HOLD"}],
    "opportunity": "Clarify whether a completed, unused project is ready for an exit or a different use.",
    "possible_seller_reason": "The owner may be considering an exit after project completion; this remains a hypothesis.",
    "agent_help": "Compare a sale, lease, or hold plan against the owner's actual objective.",
    "alternative_explanations": ["Preparation for occupancy or leasing.", "A documented long-term hold."],
    "next_check": "Is the completed property being held, leased, occupied, or offered for sale?",
    "would_disprove": ["A current occupancy, leasing, or long-term hold plan."],
    "pattern_tags": ["COMPLETED_PROJECT_UNUSED_PROPERTY"],
}]


def _leaves(value, path="", closed=False, route=None, usable=True, identity=None, evidence_context=None):
    if isinstance(value, dict):
        evidence_context = dict(evidence_context or {})
        for marker in ("source_record_id", "source_url", "event_date", "inspection_date", "as_of", "observed_at", "project_id", "quality_state", "evidence_grade"):
            if marker in value and (value[marker] is None or isinstance(value[marker], (str, int, float, bool))):
                evidence_context[marker] = value[marker]
        state = value.get("state")
        closed = closed or (isinstance(state, str) and state in CLOSED)
        route = value.get("route", route)
        if isinstance(state, str) and state in {"INVALID", "SUPERSEDED", "RETRACTED", "HISTORICAL", "NON_CURRENT"}:
            usable = False
        if value.get("current") is False or value.get("is_current") in (False, 0):
            usable = False
        quality = value.get("quality_state")
        if isinstance(quality, str) and quality in {"INVALID", "SUPERSEDED", "RETRACTED", "HISTORICAL", "NON_CURRENT", "SUSPECT_DATE_EXCLUDED_FROM_DERIVED"}:
            usable = False
        if value.get("about") == "THIRD_PARTY":
            usable = False
        if identity:
            parcel = value.get("parcel_id")
            address = value.get("property_address")
            market = value.get("market_code")
            if market is not None and identity["market_code"] is not None and str(market).strip() != str(identity["market_code"]).strip():
                usable = False
            if parcel is not None and identity["parcel_id"] is not None and str(parcel).strip() != str(identity["parcel_id"]).strip():
                usable = False
            if isinstance(address, str) and identity["property_address"] and " ".join(address.casefold().split()) != " ".join(identity["property_address"].casefold().split()):
                usable = False
        for key in sorted(value):
            if str(key).lower() not in OMIT:
                token = str(key).replace("~", "~0").replace("/", "~1")
                historical = str(key).casefold() in {"history", "historical", "past_records"} or str(key).casefold().startswith("historical_")
                yield from _leaves(value[key], path + "/" + token, closed, route, usable and not historical, identity, evidence_context)
    elif isinstance(value, list):
        for index, item in enumerate(value):
            yield from _leaves(item, path + "/" + str(index), closed, route, usable, identity, evidence_context)
    elif value is not None:
        tokens = [token for token in path.split("/") if token and not token.isdigit()]
        yield path, tokens[-1] if tokens else "", value, closed, route, usable, evidence_context or {}


def prepare_bundle(payload, as_of=None):
    baseline = evaluate_payload(payload)
    coverage = copy.deepcopy(baseline["coverage"])
    coverage.pop("canonical_226_concept_taxonomy_loaded", None)
    coverage.update(hypothesis_vocabulary="EXPANDABLE", finalized_seller_reason_list_required=False)
    public = build_public_context(payload.get("public_information", {}), baseline["cases"], as_of=as_of)
    names = {}
    for case in baseline["cases"]:
        for name in case["owner_identity"]["names"]:
            normalized = " ".join(name.casefold().split())
            if normalized and normalized not in {"unknown", "unavailable", "not established"}:
                names.setdefault(normalized, set()).add(case["case_id"])
    packets = []
    for case in baseline["cases"]:
        observations = []
        for index, source in enumerate(case["source_records"]):
            for path, field, value, closed, route, usable, evidence_context in _leaves(source["record"], "/" + str(index), identity=case):
                observations.append({
                    "fact_id": "fact_" + digest({"case_id": case["case_id"], "path": path, "value": value})[:24],
                    "field": field, "source_path": source["source_path"] + path,
                    "source_version": source["source_version"], "value": value,
                    "source_route": route, "closed_explanation": closed,
                    "usable_for_pattern": usable,
                    "source_evidence_context": evidence_context,
                    "source_snapshot_hash": source["source_snapshot_hash"],
                })
        context = public["by_case"].get(case["case_id"], {"observations": [], "statements": [], "unresolved_links": []})
        observations.extend(copy.deepcopy(context["observations"]))
        packets.append({
            "case_id": case["case_id"], "case_revision": digest({
                "property_revision": case["case_revision"], "public_context": context}),
            "property_address": case["property_address"], "parcel_id": case["parcel_id"],
            "market_code": case["market_code"],
            "identity_ambiguous": case["disposition"] in {"ADDRESS_CONFLICT", "IDENTITY_CONFLICT"},
            "baseline_disposition": case["disposition"],
            "prior_route_decisions": [{"route": item["route"], "disposition": item["disposition"]}
                                      for item in case["hypotheses"]],
            "observations": observations, "public_context": copy.deepcopy(context),
            "related_property_context": [{
                "owner_alias": "owner_" + digest(name)[:24],
                "relationship": "SHARED_REPORTED_NAME_NOT_VERIFIED_CONTROL",
                "other_case_ids": sorted(ids - {case["case_id"]})}
                for name, ids in sorted(names.items()) if case["case_id"] in ids and len(ids) > 1],
            "coverage": copy.deepcopy(coverage), "seller_intent": "UNKNOWN",
        })
    return {"packets": packets, "person_findings": public["person_findings"],
            "public_information_coverage": public["coverage"], "external_calls": 0, "model_calls": 0}


def prepare_packets(payload, as_of=None):
    return prepare_bundle(payload, as_of)["packets"]


def _same(value, expected):
    if isinstance(value, str) and isinstance(expected, str):
        return " ".join(value.casefold().split()) == " ".join(expected.casefold().split())
    return type(value) is type(expected) and value == expected


def _matches(observations, clause):
    # Public quotations use the dedicated attribution/property-specific gates.
    if clause["field"] == "public_statement":
        return []
    return [item for item in observations if item.get("field") == clause["field"]
            and item.get("usable_for_pattern", True)
            and not item.get("closed_explanation", False) and _same(item["value"], clause["value"])]


def _hypothesis(packet, definition, supporting, *, contradictions=(), origin="INTERNAL_PATTERN",
                eligible=True, expressed=False, matched_conditions=None):
    supported = list(dict.fromkeys(item["fact_id"] for item in supporting))
    conflict_ids = list(dict.fromkeys(item["fact_id"] for item in contradictions))
    eligible = bool(eligible and supported and not conflict_ids and packet["property_address"]
                    and not packet["identity_ambiguous"])
    reasons = []
    if conflict_ids:
        reasons.append("Supplied observations contradict this explanation; resolve that conflict.")
    if not packet["property_address"]:
        reasons.append("Resolve the property address before a property handoff.")
    if packet["identity_ambiguous"]:
        reasons.append("Resolve the conflicting property identity before an owner-specific handoff.")
    if not eligible and not reasons:
        reasons.append("Useful context for machine research; a sale circumstance is not established.")
    signatures = []
    for fact in supporting:
        if fact["source_version"] == "PUBLIC_INFORMATION_V1":
            signature = {"public_statement": fact["fact_id"]}
        else:
            path = re.sub(r"\[\d+\]", "[]", fact["source_path"])
            path = "/".join(token for token in path.split("/") if not token.isdigit())
            signature = {"field": fact["field"], "value": fact["value"],
                "source_route": fact.get("source_route"), "source_version": fact["source_version"],
                "source_path_shape": path, "source_evidence_context": fact.get("source_evidence_context", {})}
        signatures.append(json.dumps(signature, sort_keys=True, separators=(",", ":")))
    fingerprint = digest({"case_id": packet["case_id"], "pattern": definition["pattern_id"],
        "facts": sorted(set(signatures)),
        "conditions": sorted(definition.get("conditions", []), key=digest),
        "contradictions": sorted(definition.get("contradictions", []), key=digest)})
    return {
        "hypothesis_id": "hyp_" + fingerprint[:24], "evidence_fingerprint": fingerprint,
        "pattern_id": definition["pattern_id"], "origin": origin, "title": definition["title"],
        "opportunity": definition["opportunity"], "possible_seller_reason": definition["possible_seller_reason"],
        "agent_help": definition["agent_help"], "alternative_explanations": definition["alternative_explanations"],
        "next_check": definition["next_check"], "would_disprove": definition["would_disprove"],
        "pattern_tags": definition["pattern_tags"], "matched_conditions": matched_conditions or [],
        "supporting_fact_ids": supported, "contradicting_fact_ids": conflict_ids,
        "challenge": {"support": "CONTRADICTED" if conflict_ids else "SUPPORTED" if eligible else "UNCLEAR",
                      "reason": " ".join(reasons) or "An implemented pattern matches supplied evidence; verify the owner's objective."},
        "operator_review_eligible": eligible,
        "disposition": "SUPPORTED_OPPORTUNITY_HYPOTHESIS" if eligible else "MACHINE_RESEARCH",
        "seller_intent": "EXPRESSED_SALE_PLAN_SOURCE_ATTESTED" if expressed and eligible else "UNKNOWN",
        "contact_authorized": False,
    }


def _statement_definition(statement, buying=False):
    kind = statement["kind"]
    if kind == "EXPLICIT_SELL_TO_BUY_PLAN":
        title = "Disclosed sale connected to a purchase"
        opportunity = "Coordinate the stated sale and purchase rather than infer an obligation from buying interest."
        help_text = "Plan sale and purchase timing, contingencies, and the next property search."
    elif buying:
        title = "Buying interest linked to an owned property"
        opportunity = "Establish whether the buyer plans to retain, rent, or sell the linked property."
        help_text = "Clarify the buy-and-hold or buy-and-sell plan before proposing sale services."
    else:
        title = "Owner's attributed public sale plan"
        opportunity = "Investigate a current sale plan stated about this specific property."
        help_text = "Offer a property-specific sale plan aligned with the owner's stated objective."
    return {
        "pattern_id": kind, "title": title, "opportunity": opportunity,
        "possible_seller_reason": "The attributed statement contains a sale plan." if not buying else
                                  "A purchase may involve a sale, but no sale requirement is established.",
        "agent_help": help_text,
        "alternative_explanations": ["Plans may change.", "The person may retain the property or refer to another property."],
        "next_check": "Confirm that the sale plan is still current and concerns this property." if not buying else
                      "Will the purchase involve selling this property, retaining it, or neither?",
        "would_disprove": ["A corrected identity link, outdated statement, or explicit hold plan."],
        "pattern_tags": [kind],
    }


def analyze(packet, memory=None):
    observations = packet["observations"]
    statements = packet["public_context"]["statements"]
    facts = {item["fact_id"]: item for item in observations}
    holds = [facts[item["fact_id"]] for item in statements
             if item["kind"] == "EXPLICIT_HOLD_PLAN" and item["usable"] and item["property_specific"]]
    registry = {item["pattern_id"]: copy.deepcopy(item) for item in BUILTIN_PATTERNS}
    if memory:
        for pattern_id in list(registry):
            reviewed = [event["data"] for event in memory.history("pattern:" + pattern_id)
                        if event["kind"] == "PATTERN" and event["data"]["verified"]]
            if reviewed and not reviewed[-1]["approved"]:
                registry.pop(pattern_id)
    learned = {item["pattern_id"]: item for item in memory.patterns()} if memory else {}
    registry.update(learned)
    hypotheses = []
    for pattern_id, definition in sorted(registry.items()):
        groups = [_matches(observations, clause) for clause in definition["conditions"]]
        if not groups or any(not group for group in groups):
            continue
        conflicts = list(holds) + [item for clause in definition["contradictions"] for item in _matches(observations, clause)]
        for clause in definition["conditions"]:
            conflicts.extend(item for item in observations if item.get("field") == clause["field"]
                             and item.get("usable_for_pattern", True)
                             and not item.get("closed_explanation", False) and not _same(item["value"], clause["value"]))
        hypotheses.append(_hypothesis(packet, definition, [item for group in groups for item in group],
            contradictions=conflicts, origin="REVIEWED_MEMORY_PATTERN" if pattern_id in learned else "INTERNAL_PATTERN",
            matched_conditions=copy.deepcopy(definition["conditions"])))
    for statement in statements:
        kind = statement["kind"]
        if kind not in {"EXPLICIT_SELLING_PLAN", "EXPLICIT_SELL_TO_BUY_PLAN", "EXPLICIT_BUYING_PLAN"}:
            continue
        buying = kind == "EXPLICIT_BUYING_PLAN"
        hypotheses.append(_hypothesis(packet, _statement_definition(statement, buying),
            [facts[statement["fact_id"]]], contradictions=holds, origin="PUBLIC_STATEMENT_PROPERTY_LINK",
            eligible=statement["usable"] and statement["property_specific"] and not buying,
            expressed=not buying, matched_conditions=[{"field": "public_statement_kind", "value": kind}]))
    for hypothesis in hypotheses:
        hypothesis["comparable_reviewed_cases"] = memory.examples(hypothesis["pattern_tags"], limit=5) if memory else []
        hypothesis["reviewed_pattern_lessons"] = [lesson for lesson in memory.lessons()
            if lesson["pattern"] in hypothesis["pattern_tags"]] if memory else []
        hypothesis["public_context_fact_ids"] = [item["fact_id"] for item in statements if item["usable"]]
    if memory:
        # Revisit a previously disproved case only when its supplied evidence
        # changes. A finding about another property never settles this one.
        latest = {}
        for event in memory.history(packet["case_id"]):
            review = event["data"]
            if event["kind"] == "FEEDBACK" and review["verified"]:
                latest[review["hypothesis_id"]] = review
        for hypothesis in hypotheses:
            review = latest.get(hypothesis["hypothesis_id"])
            if review:
                hypothesis["current_case_review"] = {key: review[key] for key in (
                    "event_id", "outcome", "method", "analysis_id", "case_revision")}
                if review["outcome"] in {"FALSE_POSITIVE", "SELLER_REASON_DISPROVED", "NO_SELLER_REASON_FOUND", "SOURCE_ERROR"}:
                    hypothesis["operator_review_eligible"] = False
                    hypothesis["disposition"] = "MACHINE_RESEARCH"
                    hypothesis["seller_intent"] = "UNKNOWN"
                    hypothesis["challenge"] = {
                        "support": "DISPROVED_BY_REVIEW",
                        "reason": "A verified finding holds this unchanged case; reconsider when relevant evidence changes.",
                    }
    result = {
        "version": VERSION, "case_id": packet["case_id"], "case_revision": packet["case_revision"],
        "property_address": packet["property_address"], "hypotheses": hypotheses,
        "observations": observations, "coverage": packet["coverage"],
        "prior_route_decisions": packet["prior_route_decisions"], "public_context": packet["public_context"],
        "baseline_disposition": packet["baseline_disposition"], "related_property_context": packet["related_property_context"],
        "seller_intent": "EXPRESSED_SALE_PLAN_SOURCE_ATTESTED" if any(
            item["seller_intent"] == "EXPRESSED_SALE_PLAN_SOURCE_ATTESTED" for item in hypotheses) else "UNKNOWN",
        "contact_authorized": False, "external_calls": 0, "model_calls": 0,
        "reasoning_method": "INTERNAL_EVIDENCE_PATTERNS_AND_REVIEWED_CASES",
        "learning_method": "REVIEWED_CASE_MEMORY_AND_EXPLICIT_PATTERN_ADOPTION" if memory else "STATELESS_ANALYSIS",
        "learning_memory_connected": memory is not None,
    }
    result["analysis_id"] = digest(result)
    if memory:
        memory.remember_analysis(result)
    return result


def analyze_batch(payload, memory=None, review_limit=5, as_of=None):
    if type(review_limit) is not int or not 0 <= review_limit <= 50:
        raise ValueError("review_limit must be between zero and 50 properties.")
    bundle = prepare_bundle(payload, as_of)
    results = [analyze(packet, memory) for packet in bundle["packets"]]
    candidates = [r for r in results if any(h["operator_review_eligible"] for h in r["hypotheses"])]
    candidates.sort(key=lambda r: (r["seller_intent"] == "UNKNOWN", r["case_id"]))
    selected = candidates[:review_limit]
    return {
        "status": "ok", "version": VERSION, "results": results,
        "review_batch": [{"case_id": r["case_id"], "property_address": r["property_address"],
                          "hypotheses": [h for h in r["hypotheses"] if h["operator_review_eligible"]]} for r in selected],
        "review_backlog_case_ids": [r["case_id"] for r in candidates[review_limit:]],
        "person_findings": bundle["person_findings"], "public_information_coverage": bundle["public_information_coverage"],
        "coverage": {"input_cases": len(results), "cases_retained": len(results),
                     "review_eligible_properties": len(candidates), "review_batch_size": len(selected),
                     "review_limit": review_limit, "backlog_preserved": True},
        "external_calls": 0, "model_calls": 0, "contact_authorized": False,
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["packets", "analyze", "review", "lessons", "suggest-patterns", "register-pattern"])
    parser.add_argument("--input", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--memory", type=Path)
    parser.add_argument("--case-id")
    parser.add_argument("--review-limit", type=int, default=5)
    parser.add_argument("--as-of")
    args = parser.parse_args(argv)
    if args.output and args.input and args.output.resolve() == args.input.resolve():
        parser.error("Output must not replace the input.")
    if args.memory and any(path and path.resolve() == args.memory.resolve() for path in (args.input, args.output)):
        parser.error("Memory must use its own database path.")
    if args.action in {"review", "lessons", "suggest-patterns", "register-pattern"} and not args.memory:
        parser.error("This action requires an explicit local memory path.")
    memory = ReviewMemory(str(args.memory)) if args.memory else None
    if args.action == "lessons":
        result = memory.lessons()
    elif args.action == "suggest-patterns":
        result = memory.suggest_patterns()
    else:
        if args.input is None:
            parser.error("This action requires an existing JSON input.")
        payload = json.loads(args.input.read_text())
        if args.action == "review":
            result = memory.review(**payload)
        elif args.action == "register-pattern":
            result = memory.register_pattern(**payload)
        elif args.action == "packets":
            result = prepare_bundle(payload, args.as_of)
        elif args.case_id:
            packet = next((p for p in prepare_packets(payload, args.as_of) if p["case_id"] == args.case_id), None)
            if packet is None:
                parser.error("Case is absent from the supplied snapshot.")
            result = analyze(packet, memory)
        else:
            result = analyze_batch(payload, memory, args.review_limit, args.as_of)
    rendered = json.dumps(result, indent=2, allow_nan=False) + "\n"
    if args.output:
        args.output.write_text(rendered)
    else:
        print(rendered, end="")


if __name__ == "__main__":
    main()
