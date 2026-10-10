"""Durable operator workspace over PMI's isolated, internal review memory.

No source URLs are fetched. Constructors and read methods never create a
file/table or analyze a case. initialize/import/evidence/review are explicit
write operations; the HTTP layer is responsible for operator auth and CSRF.
"""
from contextlib import contextmanager
import copy
from datetime import date, datetime, timezone
import json
import math
from pathlib import Path
import re
import sqlite3
from urllib.parse import urlsplit

from opportunity_intelligence import evaluate_payload
from public_intelligence import build_public_context
from seller_ai import analyze, prepare_bundle
from seller_ai_memory import ReviewMemory, SCHEMA as MEMORY_SCHEMA, canonical, digest, _safe_field

STATES = {"NEW", "IN_REVIEW", "WAITING", "COMPLETE", "DISMISSED"}
SCHEMA = """
CREATE TABLE IF NOT EXISTS pmi_review_imports (
 import_id TEXT PRIMARY KEY, payload_json TEXT NOT NULL, summary_json TEXT NOT NULL,
 actor TEXT NOT NULL, recorded_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS pmi_review_case_versions (
 version_id TEXT PRIMARY KEY, case_id TEXT NOT NULL, data_json TEXT NOT NULL,
 recorded_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS pmi_review_cases (
 case_id TEXT PRIMARY KEY, version_id TEXT NOT NULL, state TEXT NOT NULL,
 pilot INTEGER NOT NULL, import_id TEXT NOT NULL, updated_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS pmi_review_events (
 event_id TEXT PRIMARY KEY, case_id TEXT NOT NULL, kind TEXT NOT NULL,
 data_json TEXT NOT NULL, recorded_at TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS pmi_review_event_case ON pmi_review_events(case_id, recorded_at);
"""


def _now():
    return datetime.now(timezone.utc).isoformat()


def _text(value, label, limit=8000, required=True):
    if value is None and not required:
        return None
    if not isinstance(value, str) or len(value) > limit or (required and not value.strip()):
        raise ValueError(label + " must be bounded, nonempty text.")
    return value.strip()


def _bool(value, label):
    if type(value) is not bool:
        raise ValueError(label + " must be a boolean.")
    return value


def _date(value):
    value = _text(value, "Observation date", 64)
    if not re.match(r"^\d{4}-\d{2}-\d{2}(?:$|T)", value):
        raise ValueError("Observation date must be an ISO date or timestamp.")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00")).date() if "T" in value else date.fromisoformat(value)
    except ValueError:
        raise ValueError("Observation date must be valid.") from None
    if parsed > datetime.now(timezone.utc).date():
        raise ValueError("Observation date cannot be in the future.")
    return value


def _source(data, prefix=""):
    url = _text(data.get(prefix + "source_url"), "Source URL", 2000, required=False) or None
    reference = _text(data.get(prefix + "source_record_id"), "Source record", 2000, required=False) or None
    source_ref = _text(data.get(prefix + "source_ref"), "Source reference", 2000, required=False) or None
    if source_ref and not url and not reference:
        if source_ref.lower().startswith(("http://", "https://")):
            url = source_ref
        else:
            reference = source_ref
    if url:
        parsed = urlsplit(url)
        if parsed.scheme not in {"http", "https"} or not parsed.hostname or parsed.username or parsed.password or re.search(r"\s", url):
            raise ValueError("Source URL must be an HTTP(S) locator without credentials.")
    if not url and not reference:
        raise ValueError("A source URL or source record is required.")
    return {"source_url": url, "source_record_id": reference}


class _TransactionMemory(ReviewMemory):
    """Use core memory inside the workspace transaction, without auto-migration."""
    def __init__(self, connection, postgres):
        self.connection, self.postgres = connection, postgres

    @contextmanager
    def _session(self):
        yield self.connection


class ReviewStore:
    def __init__(self, dsn):
        if not isinstance(dsn, str) or not dsn.strip():
            raise ValueError("An explicit persistent database location is required.")
        self.postgres = dsn.startswith(("postgres://", "postgresql://"))
        self.dsn = dsn
        self.path = None
        if not self.postgres:
            self.path = dsn[10:] if dsn.startswith("sqlite:///") else dsn
            if self.path == ":memory:" or not Path(self.path).is_absolute():
                raise ValueError("Local SQLite requires an explicit absolute persistent path.")

    def _connect(self, *, write=False):
        if self.postgres:
            import psycopg
            return psycopg.connect(self.dsn)
        if write:
            return sqlite3.connect(self.path, timeout=20)
        # mode=ro prevents both creation and accidental writes in all GET paths.
        return sqlite3.connect(Path(self.path).as_uri() + "?mode=ro", uri=True, timeout=20)

    @contextmanager
    def _session(self, *, write=False):
        connection = self._connect(write=write)
        try:
            if self.postgres:
                connection.execute("SET TRANSACTION READ WRITE" if write else "SET TRANSACTION READ ONLY")
                if write:
                    # Serialize workspace mutations, including the five-case
                    # pilot limit, across processes on PostgreSQL.
                    connection.execute("SELECT pg_advisory_xact_lock(73421609)")
            elif write:
                connection.execute("BEGIN IMMEDIATE")
            yield connection
            if write:
                connection.commit()
        except BaseException:
            if write:
                connection.rollback()
            raise
        finally:
            connection.close()

    def _sql(self, connection, sql, params=()):
        return connection.execute(sql.replace("?", "%s") if self.postgres else sql, params)

    def ready(self):
        try:
            with self._session() as connection:
                for table in ("pmi_review_imports", "pmi_review_case_versions", "pmi_review_cases", "pmi_review_events", "pmi_ai_review_records"):
                    self._sql(connection, "SELECT 1 FROM " + table + " LIMIT 1")
            return True
        except (OSError, sqlite3.Error):
            return False
        except Exception:
            if self.postgres:
                return False
            raise

    def initialize(self):
        with self._session(write=True) as connection:
            for statement in (SCHEMA + MEMORY_SCHEMA).split(";"):
                if statement.strip():
                    self._sql(connection, statement)
        return {"status": "ok", "ready": True}

    def _require(self):
        if not self.ready():
            raise ValueError("Initialize the protected review workspace first.")

    def _event(self, connection, event_id):
        row = self._sql(connection, "SELECT case_id,kind,data_json,recorded_at FROM pmi_review_events WHERE event_id=?", (event_id,)).fetchone()
        return {"event_id": event_id, "case_id": row[0], "kind": row[1], "data": json.loads(row[2]), "recorded_at": row[3]} if row else None

    def _append(self, connection, case_id, kind, data, event_id):
        _text(event_id, "Event identifier", 128)
        existing = self._event(connection, event_id)
        if existing:
            if (existing["case_id"], existing["kind"], canonical(existing["data"])) != (case_id, kind, canonical(data)):
                raise ValueError("An event identifier cannot overwrite an earlier event.")
            return existing, False
        now = _now()
        self._sql(connection, "INSERT INTO pmi_review_events(event_id,case_id,kind,data_json,recorded_at) VALUES(?,?,?,?,?)", (event_id, case_id, kind, canonical(data), now))
        return {"event_id": event_id, "case_id": case_id, "kind": kind, "data": copy.deepcopy(data), "recorded_at": now}, True

    def _events(self, connection, case_id):
        rows = self._sql(connection, "SELECT event_id,kind,data_json,recorded_at FROM pmi_review_events WHERE case_id=? ORDER BY recorded_at,event_id", (case_id,)).fetchall()
        return [{"event_id": row[0], "case_id": case_id, "kind": row[1], "data": json.loads(row[2]), "recorded_at": row[3]} for row in rows]

    def _document(self, connection, case_id, *, lock=False):
        suffix = " FOR UPDATE OF c" if lock and self.postgres else ""
        row = self._sql(connection, "SELECT v.data_json,c.state,c.pilot,c.import_id,c.updated_at FROM pmi_review_cases c JOIN pmi_review_case_versions v ON v.version_id=c.version_id WHERE c.case_id=?" + suffix, (case_id,)).fetchone()
        if not row:
            raise KeyError(case_id)
        return json.loads(row[0]), {"state": row[1], "pilot": bool(row[2]), "import_id": row[3], "updated_at": row[4]}

    def _save(self, connection, document, *, import_id=None, state=None, pilot=None):
        version_id, now = digest(document), _now()
        case_id = document["baseline"]["case_id"]
        self._sql(connection, "INSERT INTO pmi_review_case_versions(version_id,case_id,data_json,recorded_at) VALUES(?,?,?,?) ON CONFLICT(version_id) DO NOTHING", (version_id, case_id, canonical(document), now))
        prior = self._sql(connection, "SELECT state,pilot,import_id FROM pmi_review_cases WHERE case_id=?", (case_id,)).fetchone()
        self._sql(connection, "INSERT INTO pmi_review_cases(case_id,version_id,state,pilot,import_id,updated_at) VALUES(?,?,?,?,?,?) ON CONFLICT(case_id) DO UPDATE SET version_id=excluded.version_id,state=excluded.state,pilot=excluded.pilot,import_id=excluded.import_id,updated_at=excluded.updated_at", (case_id, version_id, state or (prior[0] if prior else "NEW"), int(pilot if pilot is not None else bool(prior[1]) if prior else False), import_id or (prior[2] if prior else ""), now))

    def _apply_evidence(self, packet, baseline, events):
        packet = copy.deepcopy(packet)
        captured = [event for event in events if event["kind"] == "EVIDENCE"]
        superseded = {event["data"]["supersedes"] for event in captured if event["data"].get("supersedes")}
        for event in captured:
            data = event["data"]
            disabled = event["event_id"] in superseded
            if data["kind"] == "FACT":
                source_identity = digest({key: data[key] for key in ("field", "value", "source_url", "source_record_id", "observed_at")})
                packet["observations"].append({
                    "fact_id": "captured_" + digest({"case_id": baseline["case_id"], "event_id": event["event_id"]})[:24],
                    "field": data["field"], "value": data["value"],
                    # Audit citations retain event identity; a duplicate source
                    # observation must not evade a reviewed negative finding.
                    "source_path": "operator_evidence/facts/" + source_identity + "/" + data["field"],
                    "source_version": "OPERATOR_EVIDENCE_V1", "source_snapshot_hash": digest(data),
                    "source_route": None, "closed_explanation": False,
                    "usable_for_pattern": not disabled and data["verified"] and data["current"] and data["usable"],
                    "source_evidence_context": {"source_url": data["source_url"], "source_record_id": data["source_record_id"], "observed_at": data["observed_at"], "case_id": baseline["case_id"], "parcel_id": baseline["parcel_id"], "property_address": baseline["property_address"], "market_code": baseline["market_code"], "quality_state": "SUPERSEDED" if disabled else "VERIFIED" if data["verified"] else "UNVERIFIED"},
                    "verification": {"verified_by": data["actor"], "verified": data["verified"], "basis": "TRUSTED_OPERATOR_ATTESTATION"},
                })
            else:
                public = copy.deepcopy(data["public_information"])
                if disabled:
                    public["statements"][0]["current"] = False
                context = build_public_context(public, [baseline])["by_case"][baseline["case_id"]]
                statement = public["statements"][0]
                semantic_id = "public_capture_" + digest({key: value for key, value in statement.items() if key not in {"statement_id", "verified_by", "context_tags"}})
                for item in context["statements"]:
                    item["fact_id"] = semantic_id
                for observation in context["observations"]:
                    observation["fact_id"] = semantic_id
                    observation["metadata"]["fact_id"] = semantic_id
                if not data["usable"]:
                    for statement in context["statements"]:
                        statement["usable"] = False
                        statement["context_reasons"].append("OPERATOR_MARKED_UNUSABLE")
                    for observation in context["observations"]:
                        observation["metadata"]["usable"] = False
                        observation["metadata"]["context_reasons"].append("OPERATOR_MARKED_UNUSABLE")
                # Repeated capture is separate workflow history, not a second
                # sale plan or a new hypothesis for the same source statement.
                if any(item["fact_id"] == semantic_id for item in packet["public_context"]["statements"]):
                    continue
                for key in ("observations", "statements", "unresolved_links"):
                    packet["public_context"][key].extend(context[key])
                packet["observations"].extend(context["observations"])
        packet["case_revision"] = digest({"base_revision": packet["case_revision"], "capture": [{"event_id": event["event_id"], "data": event["data"]} for event in captured]})
        return packet

    def import_payload(self, payload, actor):
        self._require()
        actor = _text(actor, "Operator", 128)
        if not isinstance(payload, dict):
            raise ValueError("Import a native complete export object.")
        # Validate every object, value, identity, and source status before any
        # transaction can replace an operative case pointer.
        native = evaluate_payload(payload)
        snapshots = payload.get("snapshots", [payload])
        for snapshot in snapshots if isinstance(snapshots, list) else []:
            if snapshot.get("version") == "FIND4":
                meta, rows = snapshot.get("profile_payload", {}), snapshot.get("profiles", [])
                if not isinstance(meta, dict) or meta.get("complete") is not True or type(meta.get("returned")) is not int or type(meta.get("total")) is not int or meta["returned"] != len(rows) or meta["total"] != len(rows):
                    raise ValueError("FIND4 import requires the complete, reconciled profile export.")
        bundle = prepare_bundle(payload)
        baseline = {case["case_id"]: case for case in native["cases"]}
        packets = {packet["case_id"]: packet for packet in bundle["packets"]}
        import_id = digest(payload)
        with self._session(write=True) as connection:
            prior = self._sql(connection, "SELECT summary_json FROM pmi_review_imports WHERE import_id=?", (import_id,)).fetchone()
            if prior:
                return {**json.loads(prior[0]), "already_imported": True}
            initial_import = self._sql(connection, "SELECT COUNT(*) FROM pmi_review_imports").fetchone()[0] == 0
            memory = _TransactionMemory(connection, self.postgres)
            for case_id, case in baseline.items():
                packet = self._apply_evidence(packets[case_id], case, self._events(connection, case_id))
                document = {"baseline": case, "native_packet": packets[case_id], "packet": packet, "analysis": analyze(packet, memory)}
                self._save(connection, document, import_id=import_id)
                self._append(connection, case_id, "IMPORT", {"actor": actor, "import_id": import_id, "analysis_id": document["analysis"]["analysis_id"]}, "import:" + import_id + ":" + case_id[-24:])
            rows = self._sql(connection, "SELECT case_id FROM pmi_review_cases WHERE pilot=1").fetchall()
            if initial_import and not rows:
                chosen = [case_id for case_id, case in sorted(baseline.items()) if case["disposition"] == "SUPPORTED_PROPERTY_INVESTIGATION"][:5]
                for case_id in chosen:
                    self._sql(connection, "UPDATE pmi_review_cases SET pilot=1 WHERE case_id=?", (case_id,))
                    self._append(connection, case_id, "PILOT", {"enabled": True, "actor": actor, "basis": "INITIAL_SUPPORTED_RESEARCH_SAMPLE_NOT_SELLER_RANKING"}, "pilot:" + import_id + ":" + case_id[-24:])
            cases = self._list(connection)
            summary = {"status": "ok", "import_id": import_id, "input_cases": len(baseline), "cases_retained": len(cases), "imported_cases_retained": len(baseline), "seller_review_count": sum(case["lane"] == "SELLER_REVIEW" for case in cases), "pilot_count": sum(case["pilot"] for case in cases), "coverage": native["coverage"], "public_information_coverage": bundle["public_information_coverage"], "external_calls": 0, "model_calls": 0, "contact_authorized": False}
            self._sql(connection, "INSERT INTO pmi_review_imports(import_id,payload_json,summary_json,actor,recorded_at) VALUES(?,?,?,?,?)", (import_id, canonical(payload), canonical(summary), actor, _now()))
        return summary

    def _summary(self, document, metadata):
        baseline, analysis = document["baseline"], document["analysis"]
        eligible = [hyp for hyp in analysis["hypotheses"] if hyp["operator_review_eligible"]]
        research = baseline["disposition"] in {"SUPPORTED_PROPERTY_INVESTIGATION", "RESEARCH_HYPOTHESIS"}
        lane = "SELLER_REVIEW" if eligible else "PROPERTY_RESEARCH" if research else "HELD"
        return {"case_id": baseline["case_id"], "property_address": baseline["property_address"], "parcel_id": baseline["parcel_id"], "market_code": baseline["market_code"], **metadata, "lane": lane, "baseline_disposition": baseline["disposition"], "why": eligible[0]["opportunity"] if eligible else baseline["narrative"], "next_check": eligible[0]["next_check"] if eligible else baseline["next_check"] or "Review the existing evidence and identify a source-backed next check.", "analysis_id": analysis["analysis_id"], "hypothesis_count": len(analysis["hypotheses"]), "owner_names": baseline["owner_identity"]["names"], "seller_intent": analysis["seller_intent"]}

    def _list(self, connection):
        rows = self._sql(connection, "SELECT v.data_json,c.state,c.pilot,c.import_id,c.updated_at FROM pmi_review_cases c JOIN pmi_review_case_versions v ON v.version_id=c.version_id").fetchall()
        output = [self._summary(json.loads(row[0]), {"state": row[1], "pilot": bool(row[2]), "import_id": row[3], "updated_at": row[4]}) for row in rows]
        return sorted(output, key=lambda case: (case["lane"] != "SELLER_REVIEW", (case["property_address"] or "").casefold(), case["case_id"]))

    def list_cases(self):
        self._require()
        with self._session() as connection:
            return self._list(connection)

    def case(self, case_id):
        self._require()
        with self._session() as connection:
            document, metadata = self._document(connection, case_id)
            events = self._events(connection, case_id)
            evidence = [copy.deepcopy(event) for event in events if event["kind"] == "EVIDENCE"]
            replaced = {}
            for event in evidence:
                if event["data"].get("supersedes"):
                    replaced.setdefault(event["data"]["supersedes"], []).append(event["event_id"])
            for event in evidence:
                event["superseded"] = event["event_id"] in replaced
                event["superseded_by"] = replaced.get(event["event_id"], [])
            return {**self._summary(document, metadata), "analysis": document["analysis"], "baseline": document["baseline"], "evidence": evidence, "history": events, "notes": [event for event in events if event["kind"] == "STATE" and event["data"]["note"]]}

    def history(self, case_id):
        self._require()
        with self._session() as connection:
            self._document(connection, case_id)
            return self._events(connection, case_id)

    def set_state(self, case_id, state, note, actor, event_id):
        self._require()
        if state not in STATES:
            raise ValueError("Unsupported workflow status.")
        data = {"state": state, "note": _text(note or "", "Workflow note", required=False), "actor": _text(actor, "Operator", 128)}
        with self._session(write=True) as connection:
            self._document(connection, case_id, lock=True)
            event, fresh = self._append(connection, case_id, "STATE", data, event_id)
            if fresh:
                self._sql(connection, "UPDATE pmi_review_cases SET state=?,updated_at=? WHERE case_id=?", (state, event["recorded_at"], case_id))
        return self.case(case_id)

    def set_pilot(self, case_id, enabled, actor, event_id):
        self._require()
        enabled = _bool(enabled, "Pilot membership")
        data = {"enabled": enabled, "actor": _text(actor, "Operator", 128), "basis": "OPERATOR_SELECTED_RESEARCH_SAMPLE_NOT_SELLER_RANKING"}
        with self._session(write=True) as connection:
            document, metadata = self._document(connection, case_id, lock=True)
            existing = self._event(connection, event_id)
            if existing:
                self._append(connection, case_id, "PILOT", data, event_id)
            else:
                eligible = any(h["operator_review_eligible"] for h in document["analysis"]["hypotheses"])
                if enabled and document["baseline"]["disposition"] != "SUPPORTED_PROPERTY_INVESTIGATION" and not eligible:
                    raise ValueError("Choose a supported property inquiry or an eligible seller hypothesis for the pilot.")
                if enabled and not metadata["pilot"]:
                    count = self._sql(connection, "SELECT COUNT(*) FROM pmi_review_cases WHERE pilot=1").fetchone()[0]
                    if count >= 5:
                        raise ValueError("The pilot holds up to five properties. Remove one before adding another.")
                event, _ = self._append(connection, case_id, "PILOT", data, event_id)
                self._sql(connection, "UPDATE pmi_review_cases SET pilot=?,updated_at=? WHERE case_id=?", (int(enabled), event["recorded_at"], case_id))
        return self.case(case_id)

    def _evidence_data(self, baseline, data, actor, event_id):
        if not isinstance(data, dict):
            raise ValueError("Evidence must be a structured object.")
        kind = str(data.get("kind") or data.get("evidence_type") or "FACT").upper()
        if kind not in {"FACT", "PUBLIC_STATEMENT"}:
            raise ValueError("Unsupported evidence type.")
        # An operator submits to an already resolved case; supplied conflicting
        # identity is rejected rather than silently assigning another parcel.
        for field in ("case_id", "parcel_id", "property_address", "market_code"):
            if data.get(field) is not None and str(data[field]).strip().casefold() != str(baseline.get(field)).strip().casefold():
                raise ValueError("Captured evidence identity must match this property case.")
        result = {"kind": kind, "actor": actor, "observed_at": _date(data.get("observed_at")), **_source(data), "verified": _bool(data.get("verified", False), "Evidence verification"), "current": _bool(data.get("current", False), "Current evidence"), "usable": _bool(data.get("usable", True), "Usable evidence"), "detail": _text(data.get("detail", ""), "Evidence note", required=False), "supersedes": _text(data.get("supersedes") or None, "Correction identifier", 128, required=False)}
        if kind == "FACT":
            field = _safe_field(data.get("field"))
            value = data.get("value")
            if type(value) not in (str, bool, int, float) or (isinstance(value, float) and not math.isfinite(value)) or (isinstance(value, str) and (not value.strip() or len(value) > 2000)):
                raise ValueError("A factual value must be a nonempty, finite JSON scalar.")
            result.update(field=field, value=value)
        else:
            person_id = _text(data.get("person_id"), "Person identity", 128)
            name = _text(data.get("display_name", data.get("person_name")), "Person name", 2000, required=False) or None
            identity_verified = _bool(data.get("identity_verified", False), "Identity verification")
            identity = _source(data, "identity_")
            relationship = data.get("relationship", "OWNER")
            method = data.get("identity_method", "OPERATOR_VERIFIED")
            if not identity_verified or method not in {"AUTHORITATIVE_RECORD", "OPERATOR_VERIFIED"}:
                raise ValueError("Public statement capture requires an explicitly verified owner/controller attribution.")
            specific = _bool(data.get("property_specific", False), "Property-specific statement")
            link = {"person_id": person_id, "relationship": relationship, "method": method, **identity, "verified": identity_verified, "verified_by": actor, **{key: baseline[key] for key in ("parcel_id", "property_address", "market_code")}}
            statement = {"statement_id": "capture:" + event_id, "person_id": person_id, "quote": _text(data.get("quote"), "Public statement"), "kind": data.get("statement_kind"), "about": data.get("about", "SELF"), "access": data.get("access", "PUBLIC"), **{key: result[key] for key in ("source_url", "source_record_id", "verified", "current")}, "verified_by": actor, "captured_at": result["observed_at"], "context_tags": data.get("context_tags", []), "valid_until": data.get("valid_until") or None}
            if specific:
                statement.update({key: baseline[key] for key in ("parcel_id", "property_address", "market_code")})
            public = {"people": [{"person_id": person_id, "display_name": name}], "property_links": [link], "statements": [statement]}
            build_public_context(public, [baseline])  # full contract validation
            result.update(person_id=person_id, display_name=name, quote=statement["quote"], statement_kind=statement["kind"], property_specific=specific, public_information=public)
        return result

    def add_evidence(self, case_id, data, actor, event_id):
        self._require()
        actor = _text(actor, "Operator", 128)
        _text(event_id, "Event identifier", 128)
        with self._session(write=True) as connection:
            document, _ = self._document(connection, case_id, lock=True)
            normalized = self._evidence_data(document["baseline"], data, actor, event_id)
            if normalized["supersedes"]:
                previous = self._event(connection, normalized["supersedes"])
                if previous is None or previous["case_id"] != case_id or previous["kind"] != "EVIDENCE" or previous["data"]["kind"] != normalized["kind"]:
                    raise ValueError("A source correction must reference earlier evidence on this same case.")
                key = "field" if normalized["kind"] == "FACT" else "person_id"
                if previous["data"][key] != normalized[key]:
                    raise ValueError("A source correction must address the same fact or person.")
            _, fresh = self._append(connection, case_id, "EVIDENCE", normalized, event_id)
            if fresh:
                packet = self._apply_evidence(document["native_packet"], document["baseline"], self._events(connection, case_id))
                document.update(packet=packet, analysis=analyze(packet, _TransactionMemory(connection, self.postgres)))
                self._save(connection, document)
        return self.case(case_id)

    def review(self, case_id, data, actor, event_id):
        self._require()
        if not isinstance(data, dict):
            raise ValueError("A reviewed finding must be a structured object.")
        actor = _text(actor, "Operator", 128)
        with self._session(write=True) as connection:
            document, _ = self._document(connection, case_id, lock=True)
            memory = _TransactionMemory(connection, self.postgres)
            analysis = memory.analysis(data.get("analysis_id"))
            if analysis is None or analysis["case_id"] != case_id:
                raise ValueError("The reviewed analysis must belong to this property case.")
            payload = memory.review(event_id=event_id, analysis_id=data.get("analysis_id"), hypothesis_id=data.get("hypothesis_id"), actor=actor, outcome=data.get("outcome"), method=data.get("method"), detail=data.get("detail"), verified=_bool(data.get("verified", False), "Finding verification"), supersedes=data.get("supersedes") or None)
            _, fresh = self._append(connection, case_id, "REVIEW", payload, event_id)
            if fresh:
                document["analysis"] = analyze(document["packet"], memory)
                self._save(connection, document)
        return self.case(case_id)

    def export_payload(self):
        self._require()
        with self._session() as connection:
            imports = self._sql(connection, "SELECT import_id,payload_json,summary_json,actor,recorded_at FROM pmi_review_imports ORDER BY recorded_at,import_id").fetchall()
            case_ids = [case["case_id"] for case in self._list(connection)]
            cases = []
            for case_id in case_ids:
                document, metadata = self._document(connection, case_id)
                cases.append({**self._summary(document, metadata), **document, "history": self._events(connection, case_id)})
            memory_rows = self._sql(connection, "SELECT record_key,kind,case_id,analysis_id,data_json,recorded_at FROM pmi_ai_review_records ORDER BY recorded_at,record_key").fetchall()
            return {"version": "PMI_OPERATOR_REVIEW_EXPORT_V1", "generated_at": _now(), "imports": [{"import_id": row[0], "payload": json.loads(row[1]), "summary": json.loads(row[2]), "actor": row[3], "recorded_at": row[4]} for row in imports], "cases": cases, "memory": [{"record_key": row[0], "kind": row[1], "case_id": row[2], "analysis_id": row[3], "data": json.loads(row[4]), "recorded_at": row[5]} for row in memory_rows], "external_calls": 0, "model_calls": 0, "contact_authorized": False}
