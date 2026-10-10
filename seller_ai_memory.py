"""Append-only review memory, separate from the legacy evidence ledger.

SQLite is an explicit local development store. The PostgreSQL adapter uses the
same schema but requires an operator-applied migration; it never creates tables.
"""
from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
import json
import math
import re
import sqlite3

SCHEMA = """CREATE TABLE IF NOT EXISTS pmi_ai_review_records (
 record_key TEXT PRIMARY KEY, kind TEXT NOT NULL,
 case_id TEXT NOT NULL, analysis_id TEXT NOT NULL,
 data_json TEXT NOT NULL, recorded_at TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS pmi_ai_review_case
 ON pmi_ai_review_records(case_id, kind);"""

OUTCOMES = {
    "USEFUL_INVESTIGATION", "FALSE_POSITIVE", "SELLER_REASON_CONFIRMED",
    "SELLER_REASON_DISPROVED", "NO_SELLER_REASON_FOUND", "SOURCE_ERROR",
}
METHODS = {"OPERATOR_REVIEW", "OWNER_DISCLOSURE", "AUTHORITATIVE_RECORD"}

PATTERN_KEYS = {
    "pattern_id", "title", "conditions", "contradictions", "opportunity",
    "possible_seller_reason", "agent_help", "alternative_explanations",
    "next_check", "would_disprove", "pattern_tags",
}
PATTERN_TEXT_KEYS = {
    "pattern_id", "title", "opportunity", "possible_seller_reason",
    "agent_help", "next_check",
}
# Rules match observations, never operational decisions, identities, sensitive
# personal traits, source URLs, or instructions that could masquerade as facts.
DISALLOWED_FIELDS = {
    "action", "actions", "recommended_action", "next_action", "outreach",
    "contact", "contact_authorized", "contact_permission", "seller_intent",
    "operator_review_eligible", "disposition", "classification", "rank",
    "ranking", "score", "seller_score", "probability", "confidence", "guards",
    "policy", "state", "route_state", "current_find_state", "baseline_disposition",
    "url", "source_url", "endpoint", "api_key", "command", "instructions",
    "route", "source_path", "source_version", "source_snapshot_hash", "fact_id",
    "analysis_id", "case_id", "case_revision", "verified", "approved",
    "public_statement", "raw_quote", "quote", "context_tags", "statement_text",
    "public_post", "profile_text", "social_context",
    "owner", "owner_name", "owner_identity", "name", "names", "address",
    "property_address", "mailing_address", "phone", "email", "parcel_id",
    "age", "birth_date", "gender", "race", "ethnicity", "religion",
    "sexual_orientation", "health", "diagnosis", "disability", "children",
    "kids", "family_status", "marital_status", "marriage", "divorce", "death",
    "bereavement", "financial_distress", "income", "political_affiliation",
}
POSITIVE_OUTCOMES = {"USEFUL_INVESTIGATION", "SELLER_REASON_CONFIRMED"}
CONTEXT_ONLY_FIELDS = {
    "location", "city", "town", "county", "region", "market", "market_code",
    "state_code", "zip", "zipcode", "zip_code", "postal_code", "country",
    "latitude", "longitude", "neighborhood", "school_district", "price",
    "equity", "estimated_equity", "appreciation", "purchase_price", "sale_price",
    "asking_price", "market_value", "assessed_value", "assessment_value",
    "appraised_value", "valuation", "value", "value_change", "assessed_total",
    "assessed_land", "assessed_improvements", "property_type", "bedrooms",
    "bathrooms", "square_feet", "sqft", "lot_size", "land_size", "luxury",
    "living_sqft", "building_sqft", "year_built", "acres", "acreage",
    "assessment_total", "assessment_land", "assessment_building", "assessment_share",
    "land_share", "building_share", "improvement_share",
    "mortgage_amount", "mortgage_balance", "loan_amount", "loan_balance", "lien_amount",
    "debt_amount", "balance", "tax_amount", "annual_taxes", "tax_rate",
    "public_statement_kind", "posted_at", "observed_at", "source_date",
}


def _context_only(field):
    normalized = field.casefold()
    return (normalized in CONTEXT_ONLY_FIELDS or any(
        term in normalized for term in ("price", "equity", "appreciation", "valuation",
                                       "assessment", "assessed", "square_foot", "sqft")))


def _text(value, label, limit=2000):
    if not isinstance(value, str) or not value.strip() or len(value) > limit:
        raise ValueError(label + " must be nonempty and bounded.")
    return value


def _strings(value, label, *, required=False):
    if not isinstance(value, list) or len(value) > 32 or (required and not value):
        raise ValueError(label + " must be a bounded list.")
    for item in value:
        _text(item, label)
    if len(set(value)) != len(value):
        raise ValueError(label + " cannot contain duplicate entries.")


def _safe_field(value):
    _text(value, "Condition field", 128)
    if not re.fullmatch(r"[A-Za-z][A-Za-z0-9_]{0,127}", value):
        raise ValueError("Conditions must use observation fields, not URLs or actions.")
    normalized = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", value).casefold()
    sensitive = re.search(
        r"(?:^|_)(?:age|agegroup|birth|birthdate|birthyear|birth_year|birthday|date_of_birth|"
        r"family_size|family_status|family_members|children|kids|race|racial|ethnicity|ethnic|"
        r"religion|religious|marital|marriage|divorce|bereavement|death|health|medical|diagnosis|"
        r"disability|gender|sex|sexual_orientation|income|financial_distress)(?:_|$)", normalized)
    operational = re.search(
        r"(?:^|_)(?:score|ranking|rank|probability|confidence|classification|disposition)(?:_|$)", normalized)
    if (normalized in DISALLOWED_FIELDS or normalized.startswith((
            "guard_", "policy_", "action_", "command_", "instruction_",
            "contact_", "seller_score_", "ranking_", "public_statement_", "raw_quote_",
            "context_tags_", "statement_text_", "social_context_")) or sensitive or operational):
        raise ValueError("Operational, identity, or sensitive personal fields cannot define a rule.")
    return value


def _primitive(value):
    if value is None or type(value) is bool:
        return
    if type(value) is int and value.bit_length() <= 256:
        return
    if type(value) is float and math.isfinite(value):
        return
    if isinstance(value, str) and value.strip() and len(value) <= 2000:
        return
    raise ValueError("Condition values must be bounded JSON primitives.")


def _conditions(value, label, *, required=False):
    if not isinstance(value, list) or len(value) > 32 or (required and not value):
        raise ValueError(label + " must be a bounded nonempty list of conditions.")
    seen = set()
    for item in value:
        if not isinstance(item, dict) or set(item) != {"field", "value"}:
            raise ValueError("Every condition requires exactly field and value.")
        _safe_field(item["field"])
        _primitive(item["value"])
        token = canonical(item)
        if token in seen:
            raise ValueError("Duplicate conditions are not supported.")
        seen.add(token)


def _pattern(definition):
    if not isinstance(definition, dict) or set(definition) != PATTERN_KEYS:
        raise ValueError("Pattern definition has unsupported or missing fields.")
    for key in PATTERN_TEXT_KEYS:
        _text(definition[key], key, 128 if key == "pattern_id" else 2000)
    _conditions(definition["conditions"], "conditions", required=True)
    if all(_context_only(item["field"]) for item in definition["conditions"]):
        raise ValueError("Location, value, and public-statement context cannot qualify a property alone.")
    _conditions(definition["contradictions"], "contradictions")
    for key in ("alternative_explanations", "would_disprove", "pattern_tags"):
        _strings(definition[key], key, required=True)
    if set(map(canonical, definition["conditions"])) & set(map(canonical, definition["contradictions"])):
        raise ValueError("A condition cannot also be its own contradiction.")
    # JSON round-trip gives the event its own immutable value snapshot.
    return json.loads(canonical(definition))


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def digest(value):
    return hashlib.sha256(canonical(value).encode()).hexdigest()


class ReviewMemory:
    def __init__(self, path):
        self.factory = lambda: sqlite3.connect(path)
        self.postgres = False
        with self._session() as connection:
            connection.executescript(SCHEMA)

    @classmethod
    def postgres_store(cls, dsn):
        import psycopg
        store = cls.__new__(cls)
        store.factory = lambda: psycopg.connect(dsn)
        store.postgres = True
        # Readiness check only. Apply the supplied migration separately.
        with store._session() as connection:
            connection.execute("SELECT record_key FROM pmi_ai_review_records LIMIT 1")
        return store

    @contextmanager
    def _session(self):
        connection = self.factory()
        try:
            yield connection
            connection.commit()
        except BaseException:
            connection.rollback()
            raise
        finally:
            connection.close()

    def _execute(self, connection, sql, params=()):
        return connection.execute(sql.replace("?", "%s") if self.postgres else sql, params)

    def _get(self, key):
        with self._session() as connection:
            row = self._execute(connection,
                "SELECT data_json FROM pmi_ai_review_records WHERE record_key=?", (key,)).fetchone()
        return json.loads(row[0]) if row else None

    def _append(self, key, kind, case_id, analysis_id, payload):
        serialized = canonical(payload)
        with self._session() as connection:
            self._execute(connection, """INSERT INTO pmi_ai_review_records
                (record_key,kind,case_id,analysis_id,data_json,recorded_at)
                VALUES (?,?,?,?,?,?) ON CONFLICT(record_key) DO NOTHING""",
                (key, kind, case_id, analysis_id, serialized,
                 datetime.now(timezone.utc).isoformat()))
            stored = self._execute(connection,
                "SELECT data_json FROM pmi_ai_review_records WHERE record_key=?", (key,)).fetchone()
            if stored[0] != serialized:
                raise ValueError("An existing record cannot be overwritten; use a new review event.")
        return json.loads(stored[0])

    def remember_analysis(self, analysis):
        content = {key: value for key, value in analysis.items() if key != "analysis_id"}
        if analysis.get("analysis_id") != digest(content):
            raise ValueError("Analysis identifier does not match its content.")
        return self._append("analysis:" + analysis["analysis_id"], "ANALYSIS",
                            analysis["case_id"], analysis["analysis_id"], analysis)

    def analysis(self, analysis_id):
        return self._get("analysis:" + analysis_id)

    def review(self, *, event_id, analysis_id, hypothesis_id, actor, outcome,
               method, detail, verified=False, supersedes=None):
        for value in (event_id, hypothesis_id, actor, detail):
            if not isinstance(value, str) or not value.strip():
                raise ValueError("Review identity, actor, hypothesis, and finding are required.")
        if len(event_id) > 128 or len(detail) > 8000:
            raise ValueError("Review identifiers or findings exceed the supported size.")
        if outcome not in OUTCOMES or method not in METHODS or type(verified) is not bool:
            raise ValueError("Unsupported review outcome or evidence method.")
        if outcome == "SELLER_REASON_CONFIRMED" and method != "OWNER_DISCLOSURE":
            raise ValueError("Seller confirmation requires the owner's disclosed reason.")
        analysis = self.analysis(analysis_id)
        if analysis is None:
            raise ValueError("Review must reference a stored analysis.")
        hypothesis = next((item for item in analysis["hypotheses"]
                           if item["hypothesis_id"] == hypothesis_id), None)
        if hypothesis is None:
            raise ValueError("Unknown hypothesis in the referenced analysis.")
        if supersedes is not None:
            previous = self._get("feedback:" + supersedes)
            if previous is None or (previous["analysis_id"], previous["hypothesis_id"]) != (
                    analysis_id, hypothesis_id):
                raise ValueError("Correction must reference the same analysis and hypothesis.")
        payload = {
            "event_id": event_id, "analysis_id": analysis_id,
            "case_id": analysis["case_id"], "case_revision": analysis["case_revision"],
            "hypothesis_id": hypothesis_id, "actor": actor, "outcome": outcome,
            "method": method, "detail": detail, "verified": verified,
            "supersedes": supersedes,
            "pattern_tags": hypothesis["pattern_tags"],
        }
        return self._append("feedback:" + event_id, "FEEDBACK",
                            payload["case_id"], analysis_id, payload)

    def history(self, case_id):
        with self._session() as connection:
            rows = self._execute(connection, """SELECT kind,data_json,recorded_at
                FROM pmi_ai_review_records WHERE case_id=?
                ORDER BY recorded_at,record_key""", (case_id,)).fetchall()
        return [{"kind": row[0], "data": json.loads(row[1]), "recorded_at": row[2]}
                for row in rows]

    def register_pattern(self, definition, actor, event_id, verified=False, approved=True):
        """Retain an explicit rule review, activation, or retirement.

        Registration is separate from suggestions and case reviews. A new event
        appends a revision; it does not overwrite prior definitions. An
        unverified draft cannot replace the latest verified revision. A verified
        review with approved=False retires the rule without erasing its history.
        """
        definition = _pattern(definition)
        _text(actor, "Pattern reviewer", 128)
        _text(event_id, "Pattern review event identifier", 128)
        if type(verified) is not bool or type(approved) is not bool:
            raise ValueError("Pattern verification and approval must be booleans.")
        payload = {
            "event_id": event_id, "actor": actor, "verified": verified,
            "approved": verified and approved, "definition": definition,
            "definition_digest": digest(definition),
        }
        return self._append("pattern:" + event_id, "PATTERN",
                            "pattern:" + definition["pattern_id"], "", payload)

    def patterns(self):
        """Latest verified definitions, filtering explicitly retired patterns."""
        with self._session() as connection:
            rows = self._execute(connection, """SELECT data_json FROM pmi_ai_review_records
                WHERE kind='PATTERN' ORDER BY recorded_at,record_key""").fetchall()
        latest = {}
        for row in rows:
            event = json.loads(row[0])
            if event["verified"]:
                definition = event["definition"]
                latest[definition["pattern_id"]] = event
        return [latest[key]["definition"] for key in sorted(latest) if latest[key]["approved"]]

    @staticmethod
    def _matched_conditions(hypothesis, observations):
        """Use only clauses evidenced in the referenced analysis snapshot."""
        support_ids = set(hypothesis.get("supporting_fact_ids", []))
        supporting = [item for item in observations if item.get("fact_id") in support_ids]
        candidates = hypothesis.get("matched_conditions")
        if not isinstance(candidates, list) or not candidates:
            candidates = []
            for item in supporting:
                field = item.get("field")
                if not field and isinstance(item.get("source_path"), str):
                    tokens = [part for part in item["source_path"].split("/")
                              if part and not part.isdigit()]
                    field = tokens[-1] if tokens else ""
                candidates.append({"field": field, "value": item.get("value")})
        conditions, seen = [], set()
        for clause in candidates:
            try:
                _conditions([clause], "Matched conditions", required=True)
            except ValueError:
                continue
            # Even an internal hypothesis cannot teach an unreferenced clause.
            matching = []
            for item in supporting:
                field = item.get("field")
                if not field and isinstance(item.get("source_path"), str):
                    tokens = [part for part in item["source_path"].split("/")
                              if part and not part.isdigit()]
                    field = tokens[-1] if tokens else ""
                value = item.get("value")
                expected = clause["value"]
                same = (" ".join(value.casefold().split()) == " ".join(expected.casefold().split())
                        if isinstance(value, str) and isinstance(expected, str)
                        else type(value) is type(expected) and value == expected)
                if (field == clause["field"] and same and not item.get("closed_explanation", False)
                        and item.get("usable_for_pattern", True) is not False):
                    matching.append(item)
            token = canonical(clause)
            if matching and token not in seen:
                conditions.append(json.loads(token))
                seen.add(token)
        return sorted(conditions, key=canonical), supporting

    def _latest_examples(self):
        with self._session() as connection:
            rows = self._execute(connection, """SELECT data_json,recorded_at,record_key
                FROM pmi_ai_review_records WHERE kind='FEEDBACK'
                ORDER BY recorded_at,record_key""").fetchall()
        latest = {}
        snapshots = {}
        for row in rows:
            event = json.loads(row[0])
            if not event["verified"]:
                continue
            analysis_id = event["analysis_id"]
            if analysis_id not in snapshots:
                snapshots[analysis_id] = self.analysis(analysis_id)
            analysis = snapshots[analysis_id]
            if analysis is None:
                continue
            hypothesis = next((item for item in analysis["hypotheses"]
                               if item["hypothesis_id"] == event["hypothesis_id"]), None)
            if hypothesis is None:
                continue
            identity = hypothesis.get("pattern_id") or tuple(sorted(hypothesis.get("pattern_tags", [])))
            if not identity:
                identity = event["hypothesis_id"]
            conditions, supporting = self._matched_conditions(hypothesis, analysis.get("observations", []))
            latest[(event["case_id"], identity)] = {
                "snapshot_reference": {
                    "analysis_id": analysis_id, "case_id": event["case_id"],
                    "case_revision": event["case_revision"],
                    "hypothesis_id": event["hypothesis_id"],
                    "review_event_id": event["event_id"],
                },
                # Comparable cases are derived retrieval, not new evidence.
                # Do not recursively copy previous comparable-case trees into
                # every future analysis. The original snapshot remains intact.
                "hypothesis": {key: value for key, value in hypothesis.items()
                               if key not in {"comparable_reviewed_cases", "reviewed_pattern_lessons"}},
                "review": event,
                "matched_conditions": conditions,
                "supporting_observations": supporting,
                "recorded_at": row[1],
            }
        return sorted(latest.values(), key=lambda item: (
            item["recorded_at"], item["snapshot_reference"]["review_event_id"]), reverse=True)

    def examples(self, pattern_tags=None, limit=20):
        """Comparable verified cases and exact snapshot citations; no intent transfer."""
        if type(limit) is not int or not 1 <= limit <= 200:
            raise ValueError("Example limit must be between one and 200.")
        if isinstance(pattern_tags, str):
            pattern_tags = [pattern_tags]
        if pattern_tags is not None:
            _strings(pattern_tags, "Pattern tags")
        wanted = set(pattern_tags or [])
        examples = self._latest_examples()
        if wanted:
            examples = [item for item in examples if wanted.intersection(item["hypothesis"].get("pattern_tags", []))]
        return examples[:limit]

    def suggest_patterns(self):
        """Propose comparable evidence combinations without registering a rule.

        Verified useful/confirmed and false-positive examples contribute to
        empirical counts. Every case is counted once per combination. These
        counts describe reviewed properties; they are not seller probabilities,
        a ranking, or permission to activate the proposal.
        """
        combinations = {}
        for example in self._latest_examples():
            conditions = example["matched_conditions"]
            outcome = example["review"]["outcome"]
            if not conditions or outcome not in POSITIVE_OUTCOMES | {"FALSE_POSITIVE"}:
                continue
            if all(_context_only(clause["field"]) for clause in conditions):
                continue
            token = canonical(conditions)
            group = combinations.setdefault(token, {"conditions": conditions, "cases": {}})
            case_id = example["snapshot_reference"]["case_id"]
            # Examples are newest first. Another analysis of the same property
            # cannot add a second vote for the same evidence combination.
            group["cases"].setdefault(case_id, example)
        suggestions = []
        for token, group in sorted(combinations.items()):
            examples = list(group["cases"].values())
            outcomes = {}
            tags = set()
            for example in examples:
                outcome = example["review"]["outcome"]
                outcomes[outcome] = outcomes.get(outcome, 0) + 1
                tags.update(example["hypothesis"].get("pattern_tags", []))
            suggestions.append({
                "suggestion_id": "suggestion_" + digest(group["conditions"])[:24],
                "conditions": group["conditions"], "pattern_tags": sorted(tags),
                "outcomes": dict(sorted(outcomes.items())), "reviewed_properties": len(examples),
                "examples": [example["snapshot_reference"] for example in examples],
                "approved": False, "adopted": False,
            })
        return suggestions

    def lessons(self):
        """Empirical feedback counts, never a seller score or automatic rule.

        Each property contributes its latest verified outcome to a pattern.
        Replaying an analysis or review cannot inflate the counts.
        Reviewer prose and personal details stay out of the model context.
        """
        with self._session() as connection:
            rows = self._execute(connection, """SELECT data_json FROM pmi_ai_review_records
                WHERE kind='FEEDBACK' ORDER BY recorded_at,record_key""").fetchall()
        latest = {}
        for row in rows:
            event = json.loads(row[0])
            if event["verified"]:
                for tag in event["pattern_tags"]:
                    latest[(event["case_id"], tag)] = event["outcome"]
        patterns = {}
        for (_, tag), outcome in latest.items():
            counts = patterns.setdefault(tag, {})
            counts[outcome] = counts.get(outcome, 0) + 1
        return [{"pattern": tag, "reviewed_properties": sum(counts.values()),
                 "outcomes": dict(sorted(counts.items()))}
                for tag, counts in sorted(patterns.items())]
