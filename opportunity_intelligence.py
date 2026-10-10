"""Read-only reasoning over supplied PMI discovery snapshots.

No database, source refresh, score, or seller-intent prediction. Existing explicit
route decisions are reconciled into property cases; unsupported observations stay
in machine research. Original records remain attached for later human review.
"""
import argparse
import copy
import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path

VERSION = "OPPORTUNITY_INTELLIGENCE_V1"
CONTROL_KEYS = {"url", "path", "source_url", "input_path", "input_file", "snapshot_path",
                "snapshot_file", "database_url", "live_refresh", "refresh", "fetch_url", "policy_overrides"}
VACANT_FORM_CODES = {"311", "312", "314", "315", "322"}
SUPPORTED = {"ACTIVE_CORROBORATED_RESEARCH_ROUTE",
             "SUPPORTED_PROPERTY_FORM_HYPOTHESIS",
             "RESIDENTIAL_INFILL_SITE_HYPOTHESIS_SUPPORTED_BUT_CONSTRAINT_UNRESOLVED",
             "SPECIALIZED_SITE_USE_HBU_HYPOTHESIS_SUPPORTED"}
RESEARCH = {"ACTIVE_RESEARCH_ROUTE", "TARGETED_FACT_REQUIRED", "UNKNOWN_NONBLOCKING",
            "SITE_USE_CONTEXT_UNKNOWN_NONBLOCKING", "SITE_USE_BRANCH_UNKNOWN_NONBLOCKING",
            "NOVEL_DISCOVERY_SUPPORTED_NOT_PROVEN", "DISTINCT_CORROBORATION_SUPPORTED_NOT_PROVEN"}
CLOSED = {"EXPLAINED_ROUTE_CLOSED", "VACANCY_HYPOTHESIS_CONTRADICTED_BY_PROPERTY_FORM"}
CONTEXT = {"CONTEXT_ONLY_NOT_QUALIFYING"}
CATEGORY_FIELDS = ("categories", "category_ids", "concept_ids", "opportunity_branch", "causal_family")
SET_FIELDS = {"supporting_evidence", "corroboration", "observed_relationships",
              "contradictions_and_unknowns", "contradictions_or_quality_flags",
              "explained_or_closed_routes", "why_it_still_deserves_attention",
              "categories", "category_ids", "concept_ids", "evidence_keys"}


class InputError(ValueError):
    """The submitted snapshot does not match a supported source contract."""


def _json(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def _hash(value):
    return hashlib.sha256(_json(value).encode("utf-8")).hexdigest()


def _unique(items):
    return list({_json(item): item for item in items}.values())


def _canonical(value, field=None):
    if isinstance(value, dict):
        return {key: _canonical(item, key) for key, item in value.items()}
    if isinstance(value, list):
        result = [_canonical(item) for item in value]
        if field in SET_FIELDS or field in {"why_pmi_noticed_it", "names"}:
            return sorted(_unique(result), key=_json)
        return result
    return value


def _text(value):
    return value.strip() if isinstance(value, str) else None


def _readable(value):
    text = _text(value) or "An existing property hypothesis"
    return text.replace("_", " ").strip().rstrip(".")


def intelligence_contract():
    return {
        "status": "ok", "version": VERSION,
        "input": {"profiles": "FIND4/FIND9/FIND13 property profiles with route dictionaries",
                  "snapshots": "Optional list of native profile exports and FIND17/FIND18 results"},
        "semantics": {"supported_property_investigation_is_not_seller_motivation": True,
                      "missing_owner_nonblocking": True, "unknowns_do_not_create_support": True,
                      "route_count_is_not_evidence_independence": True,
                      "taxonomy_labels_preserved_without_inventing_registry": True},
        "database_writes": 0, "external_calls": False,
        "contact_authorized": False, "seller_scoring": False,
    }


def _snapshots(payload):
    if not isinstance(payload, dict):
        raise InputError("Submit a JSON object containing profiles or snapshots.")
    if CONTROL_KEYS.intersection(str(key).lower() for key in payload):
        raise InputError("Submit existing data; fetch, file, refresh, and policy controls are unsupported.")
    if "snapshots" in payload:
        if "profiles" in payload or "results" in payload:
            raise InputError("Use snapshots or a native export, not both.")
        sources = payload["snapshots"]
        if not isinstance(sources, list):
            raise InputError("snapshots must be a list of native export objects.")
    else:
        sources = [payload]
    for snapshot in sources:
        if not isinstance(snapshot, dict) or CONTROL_KEYS.intersection(str(key).lower() for key in snapshot):
            raise InputError("Each snapshot must contain data, without fetch or policy controls.")
        if snapshot.get("status", "ok") != "ok":
            raise InputError("An error or degraded source response cannot be evaluated as data.")
    return sources


def _rows(snapshot):
    version = snapshot.get("version")
    if "profiles" in snapshot:
        if version in {"FIND17", "FIND18"}:
            raise InputError("FIND17 and FIND18 require their native results collection.")
        if "results" in snapshot or "cases" in snapshot:
            raise InputError("A profile export cannot also contain results or cases.")
        rows = snapshot["profiles"]
        field = "profiles"
    elif version in {"FIND17", "FIND18"} and "results" in snapshot:
        rows = snapshot["results"]
        field = "results"
    else:
        raise InputError("Unsupported export: supply profiles, or native FIND17/FIND18 results.")
    if not isinstance(rows, list) or any(not isinstance(row, dict) for row in rows):
        raise InputError("Source rows must be a list of property objects.")
    return field, rows


def _identity(row, snapshot):
    pid = row.get("parcel_id")
    if pid is not None and (isinstance(pid, bool) or not isinstance(pid, (str, int))):
        raise InputError("parcel_id must be a string or integer when supplied.")
    pid = str(pid).strip() if pid is not None else None
    address = row.get("property_address")
    if address is not None and not isinstance(address, str):
        raise InputError("property_address must be a string when supplied.")
    address = _text(address)
    market = row.get("market_code") or snapshot.get("market_code")
    if market is not None and not isinstance(market, str):
        raise InputError("market_code must be a string when supplied.")
    market = _text(market)
    if not pid and not address:
        raise InputError("Each property needs a parcel identity or property address.")
    anchor = ("parcel", pid) if pid else ("address", " ".join(address.split()).casefold())
    return (market, *anchor), pid, address, market


def _route_records(row, snapshot):
    version = snapshot.get("version")
    if "profiles" in snapshot:
        routes = row.get("why_pmi_noticed_it", [])
        if not isinstance(routes, list) or any(not isinstance(route, dict) for route in routes):
            raise InputError("Profile why_pmi_noticed_it must contain route objects, not strings.")
        for route in routes:
            if not _text(route.get("route")) or not _text(route.get("state")):
                raise InputError("Every profile route needs a route identifier and explicit state.")
        return [(route["route"], route) for route in routes]
    if version == "FIND17":
        if not _text(row.get("state")):
            raise InputError("Every FIND17 result needs an explicit state.")
        return [("OU_004_PROPERTY_FORM", row)]
    if not _text(row.get("state")):
        raise InputError("Every FIND18 result needs an explicit state.")
    branch = row.get("opportunity_branch")
    route = branch if _text(branch) and branch != "UNKNOWN" else "FIND18_UNRESOLVED_SITE_USE"
    return [(route, row)]


def _support(record, version):
    support = record.get("supporting_evidence") or record.get("corroboration") or []
    if not isinstance(support, list):
        raise InputError("Supporting evidence and corroboration must be lists.")
    if version == "FIND17" and record.get("state") == "SUPPORTED_PROPERTY_FORM_HYPOTHESIS":
        if record.get("observed_prop_type") is not None and record.get("source_evidence_state") == "AUTHORITATIVE_PROPERTY_TYPE_FACT_PRESENT":
            support = support + [{"observed_prop_type": record["observed_prop_type"],
                                  "source_evidence_state": record["source_evidence_state"]}]
    return _unique([item for item in support if (isinstance(item, str) and item.strip())
                    or (isinstance(item, dict) and item)])


def _classification(record, support, version):
    state = record.get("state")
    if record.get("route") == "OWNERSHIP_CONTEXT":
        return "CONTEXT"
    code = _form_code(record, version)
    if version == "FIND17":
        if state not in {"SUPPORTED_PROPERTY_FORM_HYPOTHESIS", "VACANCY_HYPOTHESIS_CONTRADICTED_BY_PROPERTY_FORM", "UNKNOWN_NONBLOCKING"}:
            return "UNCLASSIFIED"
        if record.get("source_evidence_state") != "AUTHORITATIVE_PROPERTY_TYPE_FACT_PRESENT":
            return "RESEARCH"
        if state == "SUPPORTED_PROPERTY_FORM_HYPOTHESIS" and code == "210":
            return "CONFLICT"
        if state == "SUPPORTED_PROPERTY_FORM_HYPOTHESIS" and code not in VACANT_FORM_CODES:
            return "RESEARCH"
        if state == "VACANCY_HYPOTHESIS_CONTRADICTED_BY_PROPERTY_FORM" and code in VACANT_FORM_CODES:
            return "CONFLICT"
    if version == "FIND18" and state not in {"RESIDENTIAL_INFILL_SITE_HYPOTHESIS_SUPPORTED_BUT_CONSTRAINT_UNRESOLVED", "SPECIALIZED_SITE_USE_HBU_HYPOTHESIS_SUPPORTED", "SITE_USE_CONTEXT_UNKNOWN_NONBLOCKING", "SITE_USE_BRANCH_UNKNOWN_NONBLOCKING"}:
        return "UNCLASSIFIED"
    if version == "FIND18" and state in SUPPORTED:
        form = record.get("property_form_evidence") or {}
        site = record.get("existing_site_use_context") or {}
        if not isinstance(site, dict):
            raise InputError("existing_site_use_context must be an object when supplied.")
        if code == "210" or form.get("state") in CLOSED:
            return "CONFLICT"
        if code not in VACANT_FORM_CODES or form.get("state") != "SUPPORTED_PROPERTY_FORM_HYPOTHESIS":
            return "RESEARCH"
        zone = _text(site.get("zone_code"))
        if not zone:
            return "RESEARCH"
        if state == "RESIDENTIAL_INFILL_SITE_HYPOTHESIS_SUPPORTED_BUT_CONSTRAINT_UNRESOLVED" and not zone.startswith("R"):
            return "CONFLICT"
        if state == "SPECIALIZED_SITE_USE_HBU_HYPOTHESIS_SUPPORTED" and zone not in {"B1", "HC", "PC"}:
            return "CONFLICT"
    if state in CLOSED:
        return "CLOSED"
    if state in CONTEXT:
        return "CONTEXT"
    if state in SUPPORTED:
        return "SUPPORTED" if support else "RESEARCH"
    if state in RESEARCH:
        return "RESEARCH"
    return "UNCLASSIFIED"


def _form_code(record, version):
    form = record.get("property_form_evidence") or {}
    if not isinstance(form, dict):
        raise InputError("property_form_evidence must be an object when supplied.")
    value = record.get("observed_prop_type") if version == "FIND17" else form.get("observed_prop_type")
    text = str(value).strip().upper() if value is not None else ""
    return text[:3] if len(text) >= 3 and text[:3].isdigit() else None


def _form_family(code):
    if code in VACANT_FORM_CODES:
        return "VACANT_OR_MINIMALLY_IMPROVED"
    return "RESIDENTIAL_IMPROVED" if code == "210" else None


def _hypotheses(entries):
    grouped = defaultdict(list)
    for entry in entries:
        grouped[entry["route"]].append(entry)
    output = []
    form_codes = {_form_code(entry["record"], entry["version"]) for entry in entries
                  if entry["version"] == "FIND18" or
                  (entry["version"] == "FIND17" and entry["record"].get("source_evidence_state") == "AUTHORITATIVE_PROPERTY_TYPE_FACT_PRESENT")}
    form_codes.discard(None)
    form_families = {_form_family(code) for code in form_codes}
    form_families.discard(None)
    for route, members in sorted(grouped.items()):
        variants = []
        for entry in members:
            record = entry["record"]
            support = _support(record, entry["version"])
            classification = _classification(record, support, entry["version"])
            variants.append({"source_version": entry["version"], "source_path": entry["path"],
                             "source_record_hash": _hash(_canonical(record)),
                             "source_state": record.get("state"), "classification": classification,
                             "supporting_observations": support, "record": copy.deepcopy(record)})
        classifications = {variant["classification"] for variant in variants}
        conflict = "CONFLICT" in classifications or ("CLOSED" in classifications and bool(classifications & {"SUPPORTED", "RESEARCH"}))
        targeted_conflict = "SUPPORTED" in classifications and any(entry["record"].get("state") == "TARGETED_FACT_REQUIRED" for entry in members)
        conflict = conflict or targeted_conflict
        form_conflict = len(form_families) > 1 and any(entry["version"] == "FIND18" for entry in members)
        if conflict or form_conflict:
            disposition = "CONFLICT"
        elif "SUPPORTED" in classifications:
            disposition = "SUPPORTED"
        elif "RESEARCH" in classifications:
            disposition = "RESEARCH"
        elif "CLOSED" in classifications:
            disposition = "CLOSED"
        elif "UNCLASSIFIED" in classifications:
            disposition = "UNCLASSIFIED"
        else:
            disposition = "CONTEXT"
        supporting = _unique([item for variant in variants for item in variant["supporting_observations"]])
        noticed = _unique([record.get("noticed_because") or record.get("hypothesis")
                          for record in [entry["record"] for entry in members]
                          if record.get("noticed_because") or record.get("hypothesis")])
        questions = _unique([entry["record"].get("next_question") or entry["record"].get("next_best_question")
                             for entry in members if entry["record"].get("next_question") or entry["record"].get("next_best_question")])
        if form_conflict:
            questions = ["Verify which authoritative property-form record applies before pursuing this site-use hypothesis."]
        elif conflict:
            questions = ["Resolve the material fact or source disagreement affecting this hypothesis before advancing it."]
        output.append({"route": route, "disposition": disposition, "noticed_because": noticed,
                       "supporting_observations": supporting, "next_questions": questions,
                       "conflicts": (["CONFLICTING_ROUTE_DECISIONS"] if conflict else []) +
                                    (["CONFLICTING_PROPERTY_FORM_OBSERVATIONS"] if form_conflict else []),
                       "fact_disagreements": (["DIFFERENT_PROPERTY_FORM_CODES_WITHIN_THE_SAME_SUPPORTED_FAMILY"] if len(form_codes) > 1 and len(form_families) == 1 and any(entry["version"] == "FIND18" for entry in members) else []),
                       "variants": sorted(variants, key=lambda item: (str(item["source_version"]), item["source_record_hash"])),
                       "evidence_independence": "NOT_INFERRED_FROM_ROUTE_OR_OBSERVATION_COUNT"})
    return output


def _case(key, rows, entries):
    hypotheses = _hypotheses(entries)
    addresses = sorted(_unique([row["address"] for row in rows if row["address"]]), key=lambda value: (value.casefold(), value))
    address_keys = {" ".join(address.split()).casefold() for address in addresses}
    address_conflict = len(address_keys) > 1
    address = addresses[0] if addresses else None
    names = []
    owner_states = []
    categories = []
    unknowns = []
    for entry in rows:
        row = entry["record"]
        owner = row.get("owner_identity") or {}
        if not isinstance(owner, dict) or not isinstance(owner.get("names", []), list):
            raise InputError("owner_identity must be an object with a names list.")
        if any(not isinstance(name, str) for name in owner.get("names", [])):
            raise InputError("Owner names must be text when supplied.")
        names.extend(owner.get("names") or [])
        owner_states.append(owner.get("verification_state", "UNKNOWN"))
        reported_unknowns = row.get("contradictions_and_unknowns") or []
        if not isinstance(reported_unknowns, list):
            raise InputError("contradictions_and_unknowns must be a list when supplied.")
        unknowns.extend(reported_unknowns)
        for field in CATEGORY_FIELDS:
            value = row.get(field)
            if value is not None:
                categories.extend(value if isinstance(value, list) else [value])
    for entry in entries:
        for field in CATEGORY_FIELDS:
            value = entry["record"].get(field)
            if value is not None:
                categories.extend(value if isinstance(value, list) else [value])
    supported = [hypothesis for hypothesis in hypotheses if hypothesis["disposition"] == "SUPPORTED"]
    conflicts = [hypothesis for hypothesis in hypotheses if hypothesis["disposition"] == "CONFLICT"]
    research = [hypothesis for hypothesis in hypotheses if hypothesis["disposition"] == "RESEARCH"]
    identity_ambiguous = any(row.get("identity_ambiguous") for row in rows)
    eligible = bool(supported and address and not address_conflict and not identity_ambiguous)
    if supported and not address:
        disposition = "ADDRESS_REQUIRED"
    elif address_conflict:
        disposition = "ADDRESS_CONFLICT"
    elif identity_ambiguous:
        disposition = "IDENTITY_CONFLICT"
    elif supported:
        disposition = "SUPPORTED_PROPERTY_INVESTIGATION"
    elif conflicts:
        disposition = "CONFLICT_REQUIRES_RECONCILIATION"
    elif research:
        disposition = "RESEARCH_HYPOTHESIS"
    elif any(hypothesis["disposition"] == "UNCLASSIFIED" for hypothesis in hypotheses):
        disposition = "UNCLASSIFIED"
    elif any(hypothesis["disposition"] == "CLOSED" for hypothesis in hypotheses):
        disposition = "CLOSED_EXPLANATIONS_ONLY"
    else:
        disposition = "CONTEXT_ONLY"
    chosen = (supported or conflicts or research or hypotheses)
    next_check = next((question for hypothesis in chosen for question in hypothesis["next_questions"]), None)
    anchor = address or ("parcel " + str(rows[0]["parcel_id"]))
    explanations = [_readable(reason) for hypothesis in supported for reason in hypothesis["noticed_because"]]
    if eligible:
        narrative = f"{anchor} warrants focused property investigation. "
        narrative += "; ".join(explanations) + "." if explanations else "An existing hypothesis has explicit corroborating observations."
    elif disposition == "RESEARCH_HYPOTHESIS":
        narrative = f"Retain {anchor} in machine research: the existing explanations have not yet supplied corroborated opportunity support."
    elif disposition.startswith("CLOSED"):
        narrative = f"Retain the history for {anchor}; the supplied opportunity explanations are closed."
    elif disposition in {"ADDRESS_REQUIRED", "ADDRESS_CONFLICT", "IDENTITY_CONFLICT"}:
        narrative = f"Preserve the supported property reasoning for {anchor}; resolve its address before an address-based handoff."
    elif conflicts:
        narrative = f"Retain {anchor}; source records disagree on an opportunity explanation."
    else:
        narrative = f"Retain {anchor} as context; the supplied records do not establish a supported property opportunity."
    identity = {"market_code": key[0], "parcel_id": next((row["parcel_id"] for row in rows if row["parcel_id"]), None), "property_address": address}
    revision_records = sorted([{ "source_version": row["version"], "source_metadata": row["metadata"], "record": _canonical(row["record"])} for row in rows], key=_json)
    result = {
        "case_id": "case_" + _hash(key)[:24],
        "identity_aliases": [{"anchor": "ADDRESS", "value": value, "case_id": "case_" + _hash((key[0], "address", " ".join(value.split()).casefold()))[:24]} for value in addresses],
        "case_revision": "sha256:" + _hash({"policy": VERSION, "identity": key, "records": _unique(revision_records)}),
        **identity, "address_observations": addresses,
        "owner_identity": {"names": _unique(names), "reported_verification_states": _unique(owner_states)},
        "categories": _unique(categories), "disposition": disposition,
        "operator_review_eligible": eligible, "narrative": narrative,
        "hypotheses": hypotheses, "next_check": next_check,
        "reported_contradictions_and_unknowns": _unique(unknowns),
        "seller_intent": "UNKNOWN", "seller_qualification": "NOT_ESTABLISHED_BY_THIS_EVALUATOR",
        "contact_authorized": False,
        "provenance": {"level": "SUPPLIED_SOURCE_SNAPSHOT", "fact_dates_or_confidence_not_invented": True},
        "source_records": [{"source_version": row["version"], "source_path": row["path"], "source_snapshot_hash": row["snapshot_hash"],
                            "source_metadata": copy.deepcopy(row["metadata"]),
                            "record": copy.deepcopy(row["record"])} for row in rows],
    }
    return result


def evaluate_payload(payload):
    """Evaluate existing data without side effects; return every case plus a review subset."""
    try:
        _json(payload)
    except (ValueError, TypeError, RecursionError) as error:
        raise InputError("Input must contain finite JSON values.") from error
    pending = [(payload, 0)]
    while pending:
        value, depth = pending.pop()
        if depth > 64:
            raise InputError("JSON nesting exceeds the 64-level structural limit.")
        if isinstance(value, dict):
            pending.extend((item, depth + 1) for item in value.values())
        elif isinstance(value, list):
            pending.extend((item, depth + 1) for item in value)
    snapshots = _snapshots(payload)
    grouped_rows = defaultdict(list)
    grouped_routes = defaultdict(list)
    exports = []
    address_parcels = defaultdict(set)
    for snapshot in snapshots:
        if snapshot.get("version") is not None and not isinstance(snapshot["version"], str):
            raise InputError("version must be a string when supplied.")
        _, rows = _rows(snapshot)
        for row in rows:
            key, pid, address, market = _identity(row, snapshot)
            if pid and address:
                address_parcels[(market, " ".join(address.split()).casefold())].add(pid)
    for index, snapshot in enumerate(snapshots):
        if snapshot.get("version") is not None and not isinstance(snapshot["version"], str):
            raise InputError("version must be a string when supplied.")
        field, rows = _rows(snapshot)
        metadata = snapshot.get("profile_payload") or {}
        if not isinstance(metadata, dict):
            raise InputError("profile_payload must be an object when supplied.")
        claimed_complete = metadata.get("complete") is True
        consistent = (metadata.get("total", len(rows)) == len(rows) and metadata.get("returned", len(rows)) == len(rows))
        exports.append({"version": snapshot.get("version"), "generated_at": snapshot.get("generated_at"),
                        "source_checkpoints": copy.deepcopy(snapshot.get("source_checkpoints") or snapshot.get("source_checkpoint")),
                        "input_rows": len(rows), "profile_payload": copy.deepcopy(metadata),
                        "complete_export_established": claimed_complete and consistent,
                        "scope": "TARGETED_EXPERIMENT" if field == "results" else "SUPPLIED_PROFILES",
                        "reported_source": copy.deepcopy(snapshot.get("source"))})
        snapshot_hash = _hash(snapshot)
        for ordinal, row in enumerate(rows):
            key, pid, address, market = _identity(row, snapshot)
            path = f"snapshots[{index}].{field}[{ordinal}]"
            mapped = address_parcels[(market, " ".join(address.split()).casefold())] if address else set()
            ambiguous = not pid and len(mapped) > 1
            if not pid and len(mapped) == 1:
                pid = next(iter(mapped))
                key = (market, "parcel", pid)
            source_metadata = {name: copy.deepcopy(snapshot[name]) for name in ("source", "source_checkpoints", "source_checkpoint", "as_of", "policy", "interpretation_policy", "triage_policy") if name in snapshot}
            grouped_rows[key].append({"record": row, "version": snapshot.get("version"), "path": path,
                                      "metadata": source_metadata, "snapshot_hash": snapshot_hash,
                                      "parcel_id": pid, "address": address, "market_code": market, "identity_ambiguous": ambiguous})
            for route_index, (route, record) in enumerate(_route_records(row, snapshot)):
                grouped_routes[key].append({"route": route, "record": record,
                                            "version": snapshot.get("version"), "path": f"{path}.why_pmi_noticed_it[{route_index}]" if field == "profiles" else path})
    cases = [_case(key, rows, grouped_routes[key]) for key, rows in grouped_rows.items()]
    cases.sort(key=lambda case: ((case.get("property_address") or "").casefold(), case["case_id"]))
    review = [case for case in cases if case["operator_review_eligible"]]
    return {
        "status": "ok", "version": VERSION,
        "summary": {"properties_evaluated": len(cases), "operator_review_candidates": len(review),
                    "dispositions": dict(sorted(Counter(case["disposition"] for case in cases).items()))},
        "coverage": {"source_exports": exports, "full_market_coverage_established": False,
                     "canonical_226_concept_taxonomy_loaded": False,
                     "category_policy": "PRESERVE_SUPPLIED_LABELS_WITHOUT_REDEFINING_THE_TAXONOMY"},
        "review_queue": review, "cases": cases,
        "database_writes": 0,
        "guards": {"external_calls": False, "schema_changes": False, "seller_scoring": False,
                   "seller_intent_inferred": False, "contact_authorized": False,
                   "production_state_changes": False, "v19v_touched": False},
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True, help="Existing JSON snapshot file")
    parser.add_argument("--output", type=Path, help="Explicit local output file; default stdout")
    args = parser.parse_args(argv)
    if args.output and args.output.resolve() == args.input.resolve():
        parser.error("Output must not replace the input snapshot.")
    try:
        result = evaluate_payload(json.loads(args.input.read_text(encoding="utf-8")))
    except (OSError, ValueError) as error:
        parser.exit(2, f"Input could not be evaluated: {type(error).__name__}\n")
    rendered = json.dumps(result, indent=2, sort_keys=True, allow_nan=False) + "\n"
    if args.output:
        args.output.write_text(rendered, encoding="utf-8")
    else:
        print(rendered, end="")


if __name__ == "__main__":
    main()
