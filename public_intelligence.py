"""Internal public/authorized evidence linkage; URLs are inert provenance only.

Statement categories and identity verification are trusted operator attestations,
not conclusions extracted or proved from a quotation by this module. No source
access, person discovery, demographic inference, or contact action occurs here.
"""
import copy
from datetime import date, datetime, timezone
import hashlib
import json
import re

VERSION = "PUBLIC_INFORMATION_V1"
KINDS = {"EXPLICIT_SELLING_PLAN", "EXPLICIT_BUYING_PLAN", "EXPLICIT_SELL_TO_BUY_PLAN",
         "EXPLICIT_HOLD_PLAN", "ANNOUNCED_TRANSITION", "OTHER_CONTEXT"}
METHODS = {"AUTHORITATIVE_RECORD", "OPERATOR_VERIFIED", "NAME_MATCH"}


def _canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def _text(value, field, required=False):
    if value is None and not required:
        return None
    if not isinstance(value, str) or not value.strip() or len(value) > 8000:
        raise ValueError(field + " must be nonempty, bounded text.")
    return value.strip()


def _boolean(value, field):
    if type(value) is not bool:
        raise ValueError(field + " must be a boolean.")
    return value


def _date(value, field):
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if not isinstance(value, str) or not re.match(r"^\d{4}-\d{2}-\d{2}(?:$|T)", value):
        raise ValueError(field + " must be an ISO date or timestamp.")
    try:
        if "T" in value:
            return datetime.fromisoformat(value.replace("Z", "+00:00")).date()
        return date.fromisoformat(value)
    except ValueError:
        raise ValueError(field + " must be a valid ISO date or timestamp.") from None


def _parcel(value):
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (str, int)) or not str(value).strip():
        raise ValueError("parcel_id must be nonempty text or an integer.")
    return str(value).strip()


def _address(value):
    value = _text(value, "property_address")
    return " ".join(value.split()).casefold() if value else None


def _provenance(record):
    url = _text(record.get("source_url"), "source_url")
    source_id = _text(record.get("source_record_id"), "source_record_id")
    if url and (not re.match(r"^https?://[^\s/]+(?:/[^\s]*)?$", url) or "@" in url.split("/", 3)[2]):
        raise ValueError("source_url must be an inert HTTP(S) source locator.")
    if not url and not source_id:
        raise ValueError("Evidence needs a source_url or source_record_id.")
    verified = _boolean(record.get("verified", False), "verified")
    actor = _text(record.get("verified_by"), "verified_by")
    if verified and not actor:
        raise ValueError("Verified evidence needs a verified_by operator attestation.")
    return {"source_url": url, "source_record_id": source_id,
            "verified": verified, "verified_by": actor,
            "verification_basis": "TRUSTED_OPERATOR_ATTESTATION" if verified else "UNVERIFIED"}


def _resolve(reference, cases):
    """Resolve both references together; never silently prefer conflicting IDs."""
    parcel = _parcel(reference.get("parcel_id"))
    address = _address(reference.get("property_address"))
    market = _text(reference.get("market_code"), "market_code")
    if not parcel and not address:
        return [], "NO_PROPERTY_REFERENCE"
    scoped = [case for case in cases if market is None or case.get("market_code") == market]
    parcel_matches = {case["case_id"] for case in scoped if _parcel(case.get("parcel_id")) == parcel} if parcel else None
    address_matches = {case["case_id"] for case in scoped if _address(case.get("property_address")) == address} if address else None
    # Parcel identifiers are local to a jurisdiction. An unscoped duplicate
    # needs an explicit market even if a supplemental address happens to fit.
    if market is None and parcel_matches and len(parcel_matches) > 1:
        return sorted(parcel_matches), "AMBIGUOUS_PROPERTY_REFERENCE"
    if parcel_matches is not None and address_matches is not None:
        matches = parcel_matches & address_matches
        if not matches and (parcel_matches or address_matches):
            return sorted(parcel_matches | address_matches), "CONFLICTING_PROPERTY_REFERENCE"
    else:
        matches = parcel_matches if parcel_matches is not None else address_matches
    if not matches:
        return [], "PROPERTY_NOT_IN_SUPPLIED_CASES"
    if len(matches) != 1:
        return sorted(matches), "AMBIGUOUS_PROPERTY_REFERENCE"
    return sorted(matches), None


def build_public_context(public_information, cases, as_of=None):
    """Link supplied statements in both directions, preserving unusable context.

    `usable` requires a self statement, current/date-valid operator attestation,
    and a strong owner/controller link to that case. `property_specific` requires
    an explicit reference resolving uniquely to that case, even when the person
    owns only one property. Life-event categories never prove sale intent.
    """
    if public_information is None:
        public_information = {}
    if not isinstance(public_information, dict) or not isinstance(cases, list):
        raise ValueError("Public information must be an object and cases a list.")
    _canonical(public_information)
    today = _date(as_of, "as_of") if as_of is not None else datetime.now(timezone.utc).date()
    case_ids = []
    for case in cases:
        if not isinstance(case, dict):
            raise ValueError("Every case must be an object.")
        case_ids.append(_text(case.get("case_id"), "case_id", required=True))
        _parcel(case.get("parcel_id"))
        _address(case.get("property_address"))
        _text(case.get("market_code"), "market_code")
    if len(case_ids) != len(set(case_ids)):
        raise ValueError("Case identifiers must be unique.")
    collections = {}
    for field in ("people", "property_links", "statements"):
        collection = public_information.get(field, [])
        if not isinstance(collection, list) or any(not isinstance(item, dict) for item in collection):
            raise ValueError(field + " must contain objects.")
        collections[field] = collection
    people = {}
    for person in collections["people"]:
        person_id = _text(person.get("person_id"), "person_id", required=True)
        _text(person.get("display_name"), "display_name")
        if person_id in people and _canonical(people[person_id]) != _canonical(person):
            raise ValueError("Conflicting duplicate person_id.")
        people[person_id] = copy.deepcopy(person)
    by_case = {case_id: {"observations": [], "statements": [], "unresolved_links": []} for case_id in case_ids}
    links_by_person = {}
    unresolved = []
    seen_links = set()
    for link in collections["property_links"]:
        person_id = _text(link.get("person_id"), "person_id", required=True)
        if person_id not in people:
            raise ValueError("Property link refers to an unknown person_id.")
        if link.get("relationship") not in {"OWNER", "CONTROLLER"} or link.get("method") not in METHODS:
            raise ValueError("Unsupported ownership relationship or verification method.")
        provenance = _provenance(link)
        key = _canonical(link)
        if key in seen_links:
            continue
        seen_links.add(key)
        matched, reason = _resolve(link, cases)
        strong = reason is None and provenance["verified"] and link["method"] in {"AUTHORITATIVE_RECORD", "OPERATOR_VERIFIED"}
        if reason is None and not strong:
            reason = "NAME_MATCH_ONLY" if link["method"] == "NAME_MATCH" else "UNVERIFIED_PROPERTY_LINK"
        record = {**copy.deepcopy(link), "source_provenance": provenance,
                  "strong": strong, "matched_case_ids": matched, "unresolved_reason": reason}
        links_by_person.setdefault(person_id, []).append(record)
        if reason:
            unresolved.append(record)
            for case_id in matched:
                by_case[case_id]["unresolved_links"].append(copy.deepcopy(record))
    statements = {}
    duplicate_statements = 0
    for statement in collections["statements"]:
        statement_id = _text(statement.get("statement_id"), "statement_id", required=True)
        key = _canonical(statement)
        if statement_id in statements:
            if _canonical(statements[statement_id]) != key:
                raise ValueError("Conflicting duplicate statement_id.")
            duplicate_statements += 1
        else:
            statements[statement_id] = copy.deepcopy(statement)
    findings = []
    linked_usable = 0
    for statement_id, statement in statements.items():
        person_id = _text(statement.get("person_id"), "person_id", required=True)
        if person_id not in people:
            raise ValueError("Statement refers to an unknown person_id.")
        quote = _text(statement.get("quote"), "quote", required=True)
        if statement.get("kind") not in KINDS or statement.get("about") not in {"SELF", "THIRD_PARTY"} or statement.get("access") not in {"PUBLIC", "AUTHORIZED"}:
            raise ValueError("Unsupported statement kind, attribution, or access.")
        provenance = _provenance(statement)
        current = _boolean(statement.get("current", False), "current")
        captured = _date(statement.get("captured_at"), "captured_at")
        valid_until = _date(statement.get("valid_until"), "valid_until")
        tags = statement.get("context_tags", [])
        if not isinstance(tags, list) or any(not isinstance(tag, str) or not tag.strip() or len(tag) > 256 for tag in tags):
            raise ValueError("context_tags must contain bounded nonempty text.")
        reasons = []
        if not provenance["verified"]:
            reasons.append("UNVERIFIED_STATEMENT")
        if statement["about"] != "SELF":
            reasons.append("THIRD_PARTY_STATEMENT")
        if not current:
            reasons.append("NON_CURRENT_STATEMENT")
        if captured is None:
            reasons.append("MISSING_CAPTURE_DATE")
        elif captured > today:
            reasons.append("FUTURE_CAPTURE_DATE")
        if valid_until is not None and valid_until < today:
            reasons.append("EXPIRED_STATEMENT")
        if captured is not None and valid_until is not None and valid_until < captured:
            reasons.append("INVALID_VALIDITY_WINDOW")
        target_ids, target_reason = _resolve(statement, cases)
        has_reference = target_reason != "NO_PROPERTY_REFERENCE"
        fact_id = "public_" + hashlib.sha256(key_for_statement(statement).encode()).hexdigest()
        base = {**copy.deepcopy(statement), "quote": quote, "fact_id": fact_id,
                "source_provenance": provenance, "statement_usable": not reasons,
                "classification_basis": "SUPPLIED_OPERATOR_CATEGORY_NOT_MACHINE_TEXT_INFERENCE",
                "self_statement": statement["about"] == "SELF", "current": current,
                "date_valid": not any(reason in reasons for reason in {"MISSING_CAPTURE_DATE", "FUTURE_CAPTURE_DATE", "EXPIRED_STATEMENT", "INVALID_VALIDITY_WINDOW"}),
                "seller_intent": "UNKNOWN", "contact_authorized": False}
        links = links_by_person.get(person_id, [])
        # A weak link is retained as context only if its reference is unambiguous.
        linked_ids = sorted({case_id for link in links if link["unresolved_reason"] in {None, "NAME_MATCH_ONLY", "UNVERIFIED_PROPERTY_LINK"} for case_id in link["matched_case_ids"]})
        strong_ids = sorted({case_id for link in links if link["strong"] for case_id in link["matched_case_ids"]})
        for case_id in linked_ids:
            identity_links = [link for link in links if case_id in link["matched_case_ids"]]
            context_reasons = list(reasons)
            if case_id not in strong_ids:
                context_reasons.append("NO_VERIFIED_OWNER_OR_CONTROLLER_LINK")
            property_specific = has_reference and target_reason is None and target_ids == [case_id]
            if has_reference and not property_specific:
                context_reasons.append(target_reason or "STATEMENT_REFERENCES_ANOTHER_PROPERTY")
            usable = not context_reasons
            item = {**copy.deepcopy(base), "property_specific": property_specific,
                    "strong_property_link": case_id in strong_ids,
                    "usable": usable, "identity_links": copy.deepcopy(identity_links),
                    "context_reasons": context_reasons}
            by_case[case_id]["statements"].append(item)
            by_case[case_id]["observations"].append({
                "fact_id": fact_id, "source_path": "public_information/statements/" + statement_id,
                "source_version": VERSION, "field": "public_statement", "value": quote,
                "metadata": copy.deepcopy(item)})
            linked_usable += int(usable)
        findings.append({**copy.deepcopy(base), "person": copy.deepcopy(people[person_id]),
                         "matched_case_ids": linked_ids, "strong_link_case_ids": strong_ids,
                         "identity_links": copy.deepcopy(links),
                         "property_specific": has_reference and target_reason is None,
                         "target_case_ids": target_ids if target_reason is None else [],
                         "usable": not reasons and bool(strong_ids) and (not has_reference or target_reason is None and bool(set(target_ids) & set(strong_ids))),
                         "buyer_context_relevant": not reasons and statement["kind"] in {"EXPLICIT_BUYING_PLAN", "EXPLICIT_SELL_TO_BUY_PLAN"},
                         "context_reasons": reasons + (["NO_MATCHED_PROPERTY_LINK"] if not linked_ids else []),
                         "unresolved_reason": target_reason if has_reference and target_reason else "NO_MATCHED_PROPERTY_LINK" if not linked_ids else None})
    return {"by_case": by_case, "person_findings": findings,
            "coverage": {"version": VERSION, "as_of": today.isoformat(), "people": len(people),
                         "property_links": len(seen_links), "statements": len(statements),
                         "duplicate_statements_deduplicated": duplicate_statements,
                         "linked_usable_statements": linked_usable,
                         "unresolved_links": copy.deepcopy(unresolved),
                         "source_access_performed": False, "external_calls": False,
                         "verification_is_operator_attestation": True,
                         "social_source_coverage_established": False,
                         "contact_authorized": False}}


def key_for_statement(statement):
    return _canonical(statement)
