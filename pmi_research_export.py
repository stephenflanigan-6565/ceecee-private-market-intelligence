"""Complete research snapshot validation and a readable delivery companion.

The JSON retains saved explanations and history. Its companion reports what is
actually saved; neither format scores sellers or creates new opportunities.
"""
from collections import Counter
from datetime import datetime
import re

from seller_ai_memory import digest

VERSION = "PMI_DAILY_RESEARCH_EXPORT_V1"
OPERATIONAL_PREFIX = "DRIVE_EXPORT_"
SOURCE_FIELDS = ("imports", "cases", "case_versions", "memory", "research")
SECRET_FIELDS = frozenset({
    "lease_token", "worker_id", "database_url", "dsn", "password", "passwd",
    "pmi_review_access_key", "api_key", "apikey", "authorization", "access_token",
    "refresh_token", "client_secret", "private_key", "credentials",
})


def without_secrets(value):
    """Retain source content while excluding explicit credential/lease fields."""
    if isinstance(value, dict):
        return {key: without_secrets(item) for key, item in value.items()
                if str(key).casefold() not in SECRET_FIELDS}
    if isinstance(value, list):
        return [without_secrets(item) for item in value]
    return value


def source_revision(snapshot):
    return digest({field: snapshot[field] for field in SOURCE_FIELDS})


def _list(value, name):
    if not isinstance(value, list) or any(not isinstance(item, dict) for item in value):
        raise ValueError("The research snapshot has an invalid " + name + " collection.")
    return value


def exported_counts(snapshot):
    cases = _list(snapshot.get("cases"), "cases")
    research = snapshot.get("research")
    if not isinstance(research, dict):
        raise ValueError("The research snapshot has no research collection.")
    return {
        "pmi_review_imports": len(_list(snapshot.get("imports"), "imports")),
        "pmi_review_cases": len(cases),
        "pmi_review_case_versions": len(_list(snapshot.get("case_versions"), "case versions")),
        "pmi_review_events": sum(len(_list(case.get("history"), "case history")) for case in cases),
        "pmi_ai_review_records": len(_list(snapshot.get("memory"), "review memory")),
        "pmi_research_control": len(_list(research.get("controls"), "research controls")),
        "pmi_research_runs": len(_list(research.get("runs"), "research runs")),
        "pmi_research_snapshots": len(_list(research.get("source_snapshots"), "source snapshots")),
        "pmi_research_sources": len(_list(research.get("source_pointers"), "source pointers")),
        "pmi_research_schedule": len(_list(research.get("schedules"), "research schedules")),
    }


def review_counts(snapshot):
    """Count all saved work and deduplicate mirrored REVIEW/FEEDBACK identities."""
    cases = snapshot["cases"]
    case_ids = {case["case_id"] for case in cases}
    reviews = {}
    notes_by_case, evidence_by_case, work = {}, {}, set()
    for case in cases:
        history = case["history"]
        notes_by_case[case["case_id"]] = sum(event["kind"] == "STATE" and bool(event["data"].get("note")) for event in history)
        evidence_by_case[case["case_id"]] = sum(event["kind"] == "EVIDENCE" for event in history)
        if any(event["kind"] in {"STATE", "EVIDENCE", "REVIEW"} for event in history):
            work.add(case["case_id"])
        for event in history:
            if event["kind"] == "REVIEW":
                reviews[event["event_id"]] = {"data": event["data"], "recorded_at": event["recorded_at"]}
    for item in snapshot["memory"]:
        if item["kind"] == "FEEDBACK":
            reviews[item["data"]["event_id"]] = {"data": item["data"], "recorded_at": item["recorded_at"]}
            if item["case_id"] in case_ids:
                work.add(item["case_id"])
    formal_cases = {item["data"]["case_id"] for item in reviews.values()}
    verified = sum(item["data"].get("verified") is True for item in reviews.values())
    latest = {}
    for event_id, item in sorted(reviews.items(), key=lambda pair: (pair[1]["recorded_at"], pair[0])):
        data = item["data"]
        if data.get("verified") is True:
            latest[(data["case_id"], data["hypothesis_id"])] = data["outcome"]
    stages = Counter(case["state"] for case in cases)
    notes = {case_id for case_id, count in notes_by_case.items() if count}
    return {
        "total_properties": len(cases), "properties_with_operator_work": len(work),
        "properties_without_operator_work": len(cases) - len(work),
        "properties_with_notes": len(notes), "note_records": sum(notes_by_case.values()),
        "properties_with_formal_reviews": len(formal_cases),
        "notes_without_formal_review": len(notes - formal_cases),
        "review_events": len(reviews), "verified_review_events": verified,
        "unverified_review_events": len(reviews) - verified,
        "evidence_records": sum(evidence_by_case.values()),
        "completed_properties": stages.get("COMPLETE", 0),
        "waiting_properties": stages.get("WAITING", 0),
        "workflow_stages": dict(sorted(stages.items())),
        "verified_outcomes": dict(sorted(Counter(latest.values()).items())),
    }


def _index(items, key, label):
    index = {}
    for item in items:
        identity = item.get(key)
        if not isinstance(identity, (str, int)) or identity in index:
            raise ValueError("The research snapshot has duplicate or missing " + label + " identities.")
        index[identity] = item
    return index


def _no_secrets(value):
    if isinstance(value, dict):
        if any(str(key).casefold() in SECRET_FIELDS for key in value):
            raise ValueError("The research snapshot contains an excluded credential or lease field.")
        for item in value.values():
            _no_secrets(item)
    elif isinstance(value, list):
        for item in value:
            _no_secrets(item)


def validate_snapshot(snapshot):
    """Return the snapshot or reject incomplete, altered, or dangling records."""
    try:
        if not isinstance(snapshot, dict) or snapshot.get("version") != VERSION:
            raise ValueError("Unsupported research snapshot version.")
        generated = datetime.fromisoformat(snapshot["generated_at"].replace("Z", "+00:00"))
        if generated.tzinfo is None or generated.utcoffset().total_seconds() != 0:
            raise ValueError("Research snapshots require a UTC generation timestamp.")
        counts = exported_counts(snapshot)
        manifest = snapshot.get("manifest", {})
        if manifest.get("complete") is not True or manifest.get("source_counts") != counts or manifest.get("exported_counts") != counts:
            raise ValueError("Research snapshot source counts do not reconcile.")
        if any(type(value) is not int or value < 0 for values in (manifest["source_counts"], manifest["exported_counts"]) for value in values.values()):
            raise ValueError("Research snapshot source counts are invalid.")
        revision = snapshot.get("source_revision")
        if not isinstance(revision, str) or not re.fullmatch(r"[0-9a-f]{64}", revision) or revision != source_revision(snapshot):
            raise ValueError("Research snapshot source revision does not match its content.")
        _no_secrets(snapshot)
        cases = _index(snapshot["cases"], "case_id", "case")
        imports = _index(snapshot["imports"], "import_id", "import")
        versions = _index(snapshot["case_versions"], "version_id", "case version")
        memory = _index(snapshot["memory"], "record_key", "memory record")
        events = {}
        for case_id, case in cases.items():
            version = versions.get(case["version_id"])
            if version is None or version["case_id"] != case_id or case["import_id"] not in imports:
                raise ValueError("A research snapshot operative case reference is missing.")
            if case["baseline"]["case_id"] != case_id:
                raise ValueError("A research snapshot case identity is inconsistent.")
            if any(case.get(key) != value for key, value in version["data"].items()):
                raise ValueError("A research snapshot operative case does not match its saved version.")
            for event in case["history"]:
                if event["case_id"] != case_id or event["event_id"] in events:
                    raise ValueError("A research snapshot event reference is inconsistent.")
                events[event["event_id"]] = event
        for version in versions.values():
            if version["case_id"] not in cases or version["data"]["baseline"]["case_id"] != version["case_id"]:
                raise ValueError("A research snapshot historical case reference is missing.")
        for item in memory.values():
            if item["kind"].startswith(OPERATIONAL_PREFIX):
                raise ValueError("Operational delivery metadata must not be a research source.")
            if item["kind"] in {"ANALYSIS", "FEEDBACK"} and item["case_id"] not in cases:
                raise ValueError("A research snapshot memory case reference is missing.")
            if item["kind"] == "FEEDBACK":
                data = item["data"]
                analysis = memory.get("analysis:" + data["analysis_id"])
                if analysis is None or analysis["kind"] != "ANALYSIS" or analysis["case_id"] != item["case_id"]:
                    raise ValueError("A research snapshot feedback analysis reference is missing.")
                if not any(hypothesis["hypothesis_id"] == data["hypothesis_id"] for hypothesis in analysis["data"]["hypotheses"]):
                    raise ValueError("A research snapshot feedback hypothesis reference is missing.")
                mirror = events.get(data["event_id"])
                if mirror is not None and (mirror["kind"] != "REVIEW" or mirror["data"] != data):
                    raise ValueError("Mirrored review feedback does not reconcile.")
                if data.get("supersedes") and "feedback:" + data["supersedes"] not in memory:
                    raise ValueError("A research snapshot correction reference is missing.")
        for event in events.values():
            if event["kind"] == "REVIEW" and "feedback:" + event["event_id"] not in memory:
                raise ValueError("A research snapshot formal review feedback reference is missing.")
            if event["kind"] == "EVIDENCE" and event["data"].get("supersedes"):
                prior = events.get(event["data"]["supersedes"])
                if prior is None or prior["case_id"] != event["case_id"] or prior["kind"] != "EVIDENCE":
                    raise ValueError("A research snapshot evidence correction reference is missing.")
        research = snapshot["research"]
        _index(research["controls"], "control_id", "research control")
        _index(research["runs"], "run_id", "research run")
        sources = _index(research["source_snapshots"], "snapshot_id", "source snapshot")
        _index(research["schedules"], "case_id", "research schedule")
        pointers = set()
        for field in ("runs", "source_snapshots", "schedules"):
            for item in research[field]:
                if item["case_id"] not in cases or item["parcel_id"] != cases[item["case_id"]]["parcel_id"]:
                    raise ValueError("A research snapshot parcel reference is missing.")
        for item in research["source_pointers"]:
            key = (item["case_id"], item["source_key"])
            source = sources.get(item["snapshot_id"])
            if key in pointers or source is None or (source["case_id"], source["source_key"]) != key:
                raise ValueError("A research snapshot source pointer reference is missing.")
            pointers.add(key)
        if snapshot.get("review_counts") != review_counts(snapshot):
            raise ValueError("Research snapshot review counts do not reconcile.")
    except (KeyError, TypeError, AttributeError, OverflowError):
        raise ValueError("The research snapshot structure is incomplete or invalid.") from None
    return snapshot


def build_summary(snapshot):
    """A short companion; the full JSON contains all explanations and history."""
    validate_snapshot(snapshot)
    counts = snapshot["review_counts"]
    research = snapshot["research"]
    lines = ["# PMI daily research export", "", "Generated: " + snapshot["generated_at"],
             "Source revision: " + snapshot["source_revision"], "",
             "All source and exported row counts reconcile. The JSON contains the complete saved record, including property explanations, source citations, notes, corrections, and history.", "",
             f"- Properties: {counts['total_properties']}; with operator work: {counts['properties_with_operator_work']}; without saved operator work: {counts['properties_without_operator_work']}.",
             f"- Workflow marked complete: {counts['completed_properties']}; waiting: {counts['waiting_properties']}.",
             f"- Properties with notes: {counts['properties_with_notes']}; note records: {counts['note_records']}; properties with notes but no formal finding: {counts['notes_without_formal_review']}.",
             f"- Formal review events: {counts['review_events']} ({counts['verified_review_events']} verified, {counts['unverified_review_events']} unverified); evidence records: {counts['evidence_records']}.",
             f"- Research runs: {len(research['runs'])}; retained source snapshots: {len(research['source_snapshots'])}; current source pointers: {len(research['source_pointers'])}.", "",
             "Notes and workflow completion are retained as context; they do not establish a seller's intent or a verified finding."]
    if counts["verified_outcomes"]:
        lines.extend(["", "Latest verified outcomes by property and hypothesis:", ""])
        lines.extend("- " + outcome.replace("_", " ").capitalize() + ": " + str(count) + "." for outcome, count in counts["verified_outcomes"].items())
    else:
        lines.extend(["", "No verified formal outcome is recorded in this snapshot. Review the existing notes and evidence before treating any explanation as learned."])
    lines.extend(["", "Exporting this record does not change qualification, scores, discovery rules, or authorize contact.", ""])
    return "\n".join(lines)
