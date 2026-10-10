"""Bounded, read-only official Suffolk research for one explicitly linked parcel.

No address/name search, county scan, legacy qualification update, or seller intent
inference occurs here. A failed refresh is an observation, never a deletion.
"""
from __future__ import annotations

import hashlib
import json
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone

SOURCE_HOST = "gis.suffolkcountyny.gov"
BASE_URL = "https://" + SOURCE_HOST + "/server/rest/services/LocalGovernmentSQLData/"
SOURCE_SPECS = (
    ("parcel", "Suffolk parcel record", "TaxParcelPolygon"),
    ("owner", "Suffolk recorded ownership", "TaxParcelOwner"),
    ("transfer_current", "Suffolk current transfer record", "TaxParcelTransferCurrent"),
    ("transfer_history", "Suffolk transfer history", "TaxParcelTransferHistory"),
)
MAX_RECORDS = 100
PAGE_SIZE = 25
REQUEST_TIMEOUT = 8.0
CASE_DEADLINE_SECONDS = 70.0
MAX_RESPONSE_BYTES = 512 * 1024
PARCEL_PATTERN = re.compile(r"(?:0[1-9]|10)[0-9]{17}\Z")
QUERY_PATHS = {urllib.parse.urlsplit(BASE_URL + spec[2] + "/FeatureServer/0/query").path
               for spec in SOURCE_SPECS}
DATE_MEANINGS = {
    "RECORDDATE": "county recording date; not a stated sale plan",
    "DOCDATE": "document date; distinct from county recording",
    "ENTRYDATE": "record entry date; not a new seller event",
    "SALEDATE": "recorded historical sale date; not present seller intent",
    "CREATEDATE": "source record creation date",
    "LASTUPDATE": "source record update date; not a verified property change date",
}


class SourceError(RuntimeError):
    """A bounded, operator-readable failure without raw upstream payloads."""


def _canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def _hash(records):
    return hashlib.sha256(_canonical(records).encode("utf-8")).hexdigest()


def _valid_url(url):
    try:
        parts = urllib.parse.urlsplit(url)
        query = urllib.parse.parse_qs(parts.query)
        where = query.get("where", [])
        return (parts.scheme == "https" and parts.hostname == SOURCE_HOST
                and parts.port in (None, 443) and not parts.username and not parts.password
                and parts.path in QUERY_PATHS and not parts.fragment
                and len(where) == 1
                and bool(re.fullmatch(r"PARCELID = '((?:0[1-9]|10)[0-9]{17})'", where[0])))
    except (ValueError, TypeError):
        return False


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        # Reject even same-host rewrites: they could discard the exact parcel guard.
        raise SourceError("Official source redirect was refused; exact parcel scope was preserved.")


def _fetch_official_json(url, *, timeout=REQUEST_TIMEOUT):
    if not _valid_url(url):
        raise SourceError("Source URL is outside the exact-parcel official allowlist.")
    deadline = time.monotonic() + min(REQUEST_TIMEOUT, max(0.05, timeout))
    request = urllib.request.Request(url, headers={
        "User-Agent": "PMI-CaseResearch/1.0", "Accept": "application/json"})
    opener = urllib.request.build_opener(_NoRedirect())
    try:
        with opener.open(request, timeout=min(REQUEST_TIMEOUT, max(0.05, timeout))) as response:
            if not _valid_url(response.geturl()):
                raise SourceError("Official source response escaped the allowed parcel query.")
            chunks, size = [], 0
            # read1 avoids waiting for a full requested buffer during slow streaming.
            read = getattr(response, "read1", response.read)
            while True:
                if time.monotonic() >= deadline:
                    raise SourceError("Official source request exceeded its time budget.")
                chunk = read(min(65536, MAX_RESPONSE_BYTES + 1 - size))
                if not chunk:
                    break
                size += len(chunk)
                if size > MAX_RESPONSE_BYTES:
                    raise SourceError("Official source response exceeded the size limit.")
                chunks.append(chunk)
            return json.loads(b"".join(chunks).decode("utf-8"))
    except SourceError:
        raise
    except urllib.error.HTTPError as exc:
        raise SourceError("Official source returned HTTP %s." % exc.code) from None
    except (urllib.error.URLError, TimeoutError, OSError):
        raise SourceError("Official source could not be reached within the request budget.") from None
    except (ValueError, UnicodeError):
        raise SourceError("Official source returned unreadable JSON.") from None


def _url(service, parcel_id, **extra):
    params = {"where": "PARCELID = '%s'" % parcel_id, "f": "json"}
    params.update(extra)
    return BASE_URL + service + "/FeatureServer/0/query?" + urllib.parse.urlencode(params)


def _call(fetch, url, deadline):
    remaining = deadline - time.monotonic()
    if remaining <= 0:
        raise SourceError("Case research time budget was reached; remaining sources were held.")
    data = fetch(url, timeout=min(REQUEST_TIMEOUT, remaining))
    if time.monotonic() > deadline:
        raise SourceError("Case research time budget was reached; response was not accepted.")
    if not isinstance(data, dict):
        raise SourceError("Official source returned an invalid response structure.")
    try:
        if len(_canonical(data).encode("utf-8")) > MAX_RESPONSE_BYTES:
            raise SourceError("Official source response exceeded the size limit.")
    except (TypeError, ValueError):
        raise SourceError("Official source returned invalid JSON values.") from None
    if "error" in data:
        raise SourceError("Official source reported a query error; no records were replaced.")
    return data


def _count(data):
    count = data.get("count")
    if isinstance(count, bool) or not isinstance(count, int) or count < 0:
        raise SourceError("Official source did not provide a valid record count.")
    return count


def _dates(records):
    dates = []
    for record in records:
        for field, meaning in DATE_MEANINGS.items():
            value = record.get(field)
            if value in (None, ""):
                continue
            rendered = str(value)
            if isinstance(value, (float, int)) and not isinstance(value, bool):
                try:
                    rendered = datetime.fromtimestamp(value / 1000, timezone.utc).date().isoformat()
                except (OverflowError, OSError, ValueError):
                    rendered = "Unrecognized source date"
            dates.append({"object_id": record["OBJECTID"], "field": field,
                          "value": rendered, "raw_value": value, "meaning": meaning})
    return dates


def _change(records, prior, complete):
    if not complete:
        return {"status": "NOT_COMPARED", "message": "Refresh incomplete; prior successful evidence is retained.",
                "added": None, "changed": None, "removed": None, "changed_fields": []}
    if not prior or prior.get("status") not in ("SUCCESS", "EMPTY") or not prior.get("complete"):
        return {"status": "BASELINE", "message": "First complete source baseline; no earlier comparison exists.",
                "added": len(records), "changed": 0, "removed": 0, "changed_fields": []}
    old = {str(r["OBJECTID"]): r for r in prior.get("records", [])}
    new = {str(r["OBJECTID"]): r for r in records}
    added, removed = len(new.keys() - old.keys()), len(old.keys() - new.keys())
    changed_ids = sorted((k for k in old.keys() & new.keys()
                          if _canonical(old[k]) != _canonical(new[k])), key=int)
    changed = len(changed_ids)
    changed_fields = [{"object_id": new[k]["OBJECTID"],
                       "fields": sorted(field for field in old[k].keys() | new[k].keys()
                                        if old[k].get(field) != new[k].get(field))[:20]}
                      for k in changed_ids[:10]]
    return {"status": "CHANGED" if added or removed or changed else "UNCHANGED",
            "message": "%s added, %s changed, %s removed recorded rows." % (added, changed, removed),
            "added": added, "changed": changed, "removed": removed,
            "changed_fields": changed_fields, "changed_fields_truncated": changed > 10}


def _display_text(value):
    """Keep source quotations factual and small; HTML escaping belongs to the UI."""
    return " ".join(str(value).split())[:200] if value not in (None, "") else ""


def _source_findings(source, case):
    """Describe returned fields without turning recorded context into motivation."""
    records, key = source["records"], source["source_key"]
    findings = []
    if key == "owner":
        names = []
        for record in records:
            name = _display_text(record.get("OWNERNAME")) or " ".join(
                part for part in (_display_text(record.get("FIRSTNAME")),
                                  _display_text(record.get("LASTNAME"))) if part)
            if name and name not in names:
                names.append(name)
        if names:
            extra = "; %s additional recorded name(s) are in the source rows" % (len(names) - 3) if len(names) > 3 else ""
            findings.append("The county ownership source reports: " + "; ".join(names[:3]) + extra +
                            ". These are recorded names; current authority to make a sale decision needs confirmation.")
        elif records:
            findings.append("Ownership rows were returned, but their name fields were blank. The property remains available for investigation.")
    if key == "parcel":
        addresses = list(dict.fromkeys(_display_text(r.get("FULLADDRESS")) for r in records
                                       if _display_text(r.get("FULLADDRESS"))))
        if addresses:
            findings.append("County parcel source address: " + "; ".join(addresses[:3]) + ".")
            saved = _display_text(case.get("property_address"))
            if saved and saved.upper() not in (address.upper() for address in addresses):
                findings.append("The saved address (" + saved + ") differs from the county address text. "
                                "The parcel ID matched exactly; check address formatting or a possible address correction.")
    if key in ("transfer_current", "transfer_history"):
        dates = [d["value"] for d in source["recorded_dates"]
                 if d["field"] == "RECORDDATE" and re.fullmatch(r"\d{4}-\d{2}-\d{2}", d["value"])]
        if dates:
            findings.append(source["source_name"] + " latest county recording date: " + max(dates) +
                            ". This dates a recorded document; its document type and parties require review.")
    changed_fields = source["change_summary"].get("changed_fields", [])
    if changed_fields:
        fields = sorted({field for change in changed_fields for field in change["fields"]})[:20]
        findings.append(source["source_name"] + " recorded fields changed on existing record IDs: " +
                        ", ".join(fields) + ". Review the before and after records to interpret the change.")
    return findings


def _collect_source(spec, parcel_id, observed_at, fetch, deadline, prior):
    key, name, service = spec
    citation = _url(service, parcel_id, outFields="*", returnGeometry="false",
                    orderByFields="OBJECTID", resultOffset=0, resultRecordCount=PAGE_SIZE)
    source = {"source_key": key, "source_name": name, "query_url": citation,
              "citation": citation, "observed_at": observed_at, "status": "ERROR",
              "complete": False, "expected_count": None, "records": [],
              "content_hash": None, "recorded_dates": [], "requests": [], "error": None}
    try:
        count_url = _url(service, parcel_id, returnCountOnly="true")
        source["requests"].append(count_url)
        expected = _count(_call(fetch, count_url, deadline))
        source["expected_count"] = expected
        if expected > MAX_RECORDS:
            source["status"] = "INCOMPLETE"
            raise SourceError("Source has %s records, above the %s-record case limit; no partial baseline was accepted."
                              % (expected, MAX_RECORDS))
        seen, offset = set(), 0
        while offset < expected:
            page_url = _url(service, parcel_id, outFields="*", returnGeometry="false",
                            orderByFields="OBJECTID", resultOffset=offset, resultRecordCount=PAGE_SIZE)
            source["requests"].append(page_url)
            data = _call(fetch, page_url, deadline)
            features = data.get("features")
            if not isinstance(features, list) or not features or len(features) > PAGE_SIZE:
                source["status"] = "INCOMPLETE"
                raise SourceError("Official source paging did not reconcile with its record count.")
            for feature in features:
                record = feature.get("attributes") if isinstance(feature, dict) else None
                if not isinstance(record, dict) or str(record.get("PARCELID", "")) != parcel_id:
                    raise SourceError("Returned record did not match the exact requested parcel; source was held.")
                oid = record.get("OBJECTID")
                if isinstance(oid, bool) or not isinstance(oid, int) or oid < 0 or oid in seen:
                    source["status"] = "INCOMPLETE"
                    raise SourceError("Official source returned missing or duplicate record identities.")
                seen.add(oid)
                source["records"].append(record)
            offset += len(features)
            if offset > expected or (offset >= expected and data.get("exceededTransferLimit") is True):
                source["status"] = "INCOMPLETE"
                raise SourceError("Official source results were truncated or changed during paging.")
        # A second count catches common changes while paginating, including zero-to-one.
        source["requests"].append(count_url)
        if _count(_call(fetch, count_url, deadline)) != expected:
            source["status"] = "INCOMPLETE"
            raise SourceError("Official source count changed during research; previous evidence was retained.")
        source["records"].sort(key=lambda row: row["OBJECTID"])
        source.update(status="SUCCESS" if expected else "EMPTY", complete=True,
                      content_hash=_hash(source["records"]), recorded_dates=_dates(source["records"]))
    except Exception as exc:
        source["error"] = str(exc) if isinstance(exc, SourceError) else "Official source check failed; previous evidence was retained."
        # Do not expose raw network/provider exceptions, which may contain source payloads.
    source["change_summary"] = _change(source["records"], prior, source["complete"])
    if not source["complete"] and prior and prior.get("complete") and prior.get("status") in ("SUCCESS", "EMPTY"):
        source["previous_successful_observed_at"] = prior.get("observed_at")
        source["previous_successful_content_hash"] = prior.get("content_hash")
    return source


def collect_case(case, previous_sources=None, *, fetch_json=None, observed_at=None):
    """Return bounded research evidence; persistence and review belong to callers.

    ``fetch_json`` receives the exact official query URL and keyword ``timeout``.
    Source hashes cover canonically serialized OBJECTID-sorted raw record lists.
    ``previous_sources`` maps source keys to complete SUCCESS/EMPTY source docs.
    """
    if observed_at is None:
        observed_at = datetime.now(timezone.utc).isoformat()
    elif isinstance(observed_at, datetime):
        if observed_at.tzinfo is None:
            raise ValueError("observed_at must be timezone-aware")
        observed_at = observed_at.isoformat()
    else:
        parsed = datetime.fromisoformat(str(observed_at).replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            raise ValueError("observed_at must be timezone-aware")
        observed_at = parsed.isoformat()
    case = case if isinstance(case, dict) else {}
    parcel_id = case.get("parcel_id")
    bundle = {"case_id": case.get("case_id"), "parcel_id": parcel_id,
              "observed_at": observed_at, "status": "UNSUPPORTED", "sources": [],
              "findings": [], "next_checks": [], "change_summary": {},
              "seller_intent_inferred": False}
    if not isinstance(parcel_id, str) or not PARCEL_PATTERN.fullmatch(parcel_id):
        bundle["findings"] = ["Automatic source research requires an exact 19-digit Suffolk parcel ID. No address or owner guess was made."]
        bundle["next_checks"] = ["Verify the official parcel identifier before running this source connection."]
        return bundle
    prior = previous_sources if isinstance(previous_sources, dict) else {}
    deadline = time.monotonic() + CASE_DEADLINE_SECONDS
    fetch = fetch_json or _fetch_official_json
    for spec in SOURCE_SPECS:
        bundle["sources"].append(_collect_source(spec, parcel_id, observed_at, fetch, deadline, prior.get(spec[0])))
    completed = [s for s in bundle["sources"] if s["complete"]]
    bundle["status"] = "SUCCESS" if len(completed) == len(SOURCE_SPECS) else ("PARTIAL" if completed else "ERROR")
    for source in bundle["sources"]:
        bundle["change_summary"][source["source_key"]] = source["change_summary"]
        if not source["complete"]:
            bundle["findings"].append(source["source_name"] + ": check incomplete. " + source["error"])
            bundle["next_checks"].append("Recheck " + source["source_name"].lower() + "; retain earlier successful evidence meanwhile.")
        elif source["status"] == "EMPTY":
            bundle["findings"].append(source["source_name"] + ": no matching rows were returned by this complete check.")
        else:
            bundle["findings"].append(source["source_name"] + ": %s exact-parcel recorded row(s) checked. " % len(source["records"]) + source["change_summary"]["message"])
            bundle["findings"].extend(_source_findings(source, case))
    owner = next((s for s in completed if s["source_key"] == "owner"), None)
    if owner and owner["records"]:
        bundle["next_checks"].append("Confirm the recorded owner or entity is the current decision maker before using person-specific information.")
    bundle["findings"].append("These checks establish recorded property context and source changes. They do not establish current occupancy, outstanding debt, or a reason to sell.")
    bundle["next_checks"].append("Review what changed and whether it supports a useful property investigation; owner plans remain unknown without attributed evidence.")
    return bundle
