"""Protected operator workspace. Reads never initialize or mutate storage."""
import hashlib
import hmac
import json
import os
import secrets
import uuid
from urllib.parse import urlsplit

from flask import Blueprint, Response, g, redirect, render_template, request, url_for
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

from pmi_review_store import ReviewStore

COOKIE = "pmi_review_operator"
LOGIN_COOKIE = "pmi_review_login"
SESSION_SECONDS = 12 * 60 * 60


def source_url(value):
    if not isinstance(value, str) or any(ord(c) < 32 for c in value):
        return None
    try:
        parsed = urlsplit(value)
        if parsed.scheme.lower() in {"http", "https"} and parsed.hostname and not parsed.username and not parsed.password:
            return value
    except ValueError:
        pass
    return None


def create_blueprint(source_loader, *, store_factory=None, access_key=None, allow_http=False):
    key = access_key if access_key is not None else os.getenv("PMI_REVIEW_ACCESS_KEY", "")
    configured = isinstance(key, str) and len(key) >= 24
    signing_key = hashlib.sha256(("PMI_OPERATOR_V1:" + key).encode()).hexdigest()
    signer = URLSafeTimedSerializer(signing_key, salt="pmi-review-session-v1")
    login_signer = URLSafeTimedSerializer(signing_key, salt="pmi-review-login-v1")
    actor = os.getenv("PMI_REVIEW_OPERATOR_NAME", "PMI operator")[:128]
    bp = Blueprint("pmi_review", __name__, url_prefix="/review", template_folder="templates", static_folder="static")

    def store():
        if store_factory:
            return store_factory()
        dsn = os.getenv("DATABASE_URL", "")
        if not dsn or (not allow_http and not dsn.startswith(("postgres://", "postgresql://"))):
            raise RuntimeError("Persistent review database is not configured.")
        return ReviewStore(dsn)

    def csrf(identity):
        return hmac.new(signing_key.encode(), ("csrf:" + identity["nonce"]).encode(), hashlib.sha256).hexdigest()

    def load_identity():
        try:
            data = signer.loads(request.cookies.get(COOKIE, ""), max_age=SESSION_SECONDS)
            if isinstance(data, dict) and isinstance(data.get("nonce"), str) and data.get("actor") == actor:
                return data
        except (BadSignature, SignatureExpired):
            pass
        return None

    def context(**values):
        identity = getattr(g, "pmi_operator", None)
        result = dict(actor=actor if identity else None, configured=configured, ready=False,
                      csrf_token=csrf(identity) if identity else "", message=request.args.get("message", ""), error="")
        result.update(values)
        return result

    def login_page(error="", status=200):
        identity = {"nonce": secrets.token_urlsafe(24)}
        response = Response(render_template("pmi_review/login.html", **context(csrf_token=csrf(identity), error=error)), status=status)
        response.set_cookie(LOGIN_COOKIE, login_signer.dumps(identity), max_age=3600, httponly=True,
                            secure=not allow_http, samesite="Lax", path="/review")
        return response

    @bp.app_template_filter("source_url")
    def source_filter(value):
        return source_url(value)

    @bp.before_request
    def guard():
        if request.endpoint == "pmi_review.static":
            return None
        if request.content_length is not None and request.content_length > 128 * 1024:
            return "The submitted review exceeds the supported size.", 413
        g.pmi_operator = load_identity() if configured else None
        if not configured:
            return render_template("pmi_review/setup.html", **context(error="Operator access has not been configured.")), 503
        if request.endpoint == "pmi_review.login":
            return None
        if not g.pmi_operator:
            if request.method == "GET" and request.endpoint == "pmi_review.index":
                return login_page()
            if request.method == "GET":
                return redirect(url_for("pmi_review.index"))
            return login_page("Sign in before saving a finding.", 401)
        if request.method != "GET":
            supplied = request.form.get("csrf_token", "")
            if not supplied or not hmac.compare_digest(supplied.encode(), csrf(g.pmi_operator).encode()):
                return render_template("pmi_review/setup.html", **context(error="This form expired. Reopen the case and try again.")), 403

    @bp.after_request
    def private_headers(response):
        if request.endpoint != "pmi_review.static":
            response.headers["Cache-Control"] = "no-store"
            response.headers["Pragma"] = "no-cache"
            response.headers["X-Content-Type-Options"] = "nosniff"
            response.headers["X-Frame-Options"] = "DENY"
            response.headers["Referrer-Policy"] = "same-origin"
            response.headers["Content-Security-Policy"] = "default-src 'self'; style-src 'self'; img-src 'self' data:; form-action 'self'; frame-ancestors 'none'; base-uri 'none'"
        return response

    def unavailable():
        return render_template("pmi_review/setup.html", **context(error="Review storage is unavailable. Your saved work has not been replaced.")), 503

    def go_case(case_id, message):
        return redirect(url_for("pmi_review.case_detail", case_id=case_id, message=message), code=303)

    def event_id():
        value = request.form.get("event_id") or str(uuid.uuid4())
        if len(value) > 128:
            raise ValueError("Save identifier is too long.")
        return value

    def checked(name):
        return request.form.get(name, "").lower() in {"on", "true", "1"}

    def case_page(case_id, *, error="", status=200):
        review_store = store()
        try:
            item = review_store.case(case_id)
        except KeyError:
            item = None
        if item is None:
            return render_template("pmi_review/setup.html", **context(ready=True, error="This case was not found.")), 404
        cases = review_store.list_cases()
        counts = count_cases(cases)
        pilot = [row for row in cases if row.get("pilot")]
        ordered = pilot if item.get("pilot") else cases
        positions = [i for i, row in enumerate(ordered) if row["case_id"] == case_id]
        pos = positions[0] if positions else 0
        ids = {name: str(uuid.uuid4()) for name in ("state", "evidence", "public_statement", "pilot")}
        for hypothesis in item.get("analysis", {}).get("hypotheses", []):
            ids["review_" + hypothesis["hypothesis_id"]] = str(uuid.uuid4())
        return render_template("pmi_review/case.html", **context(ready=True, case=item, error=error, counts=counts,
                               event_ids=ids, previous_case=ordered[pos-1] if pos else None,
                               next_case=ordered[pos+1] if pos+1 < len(ordered) else None)), status

    def count_cases(cases):
        return {"all": len(cases), "pilot": sum(bool(c.get("pilot")) for c in cases),
                "seller": sum(c.get("lane") == "SELLER_REVIEW" for c in cases),
                "research": sum(c.get("lane") == "PROPERTY_RESEARCH" for c in cases),
                "held": sum(c.get("lane") == "HELD" for c in cases)}

    @bp.get("")
    @bp.get("/")
    def index():
        try:
            review_store = store()
            if not review_store.ready():
                return render_template("pmi_review/setup.html", **context())
            cases = review_store.list_cases()
            counts = count_cases(cases)
            view = request.args.get("view", "pilot")
            if view not in counts:
                view = "pilot"
            q = request.args.get("q", "").strip()[:200]
            if view == "pilot":
                shown = [c for c in cases if c.get("pilot")]
            elif view == "all":
                shown = cases
            else:
                lane = {"seller": "SELLER_REVIEW", "research": "PROPERTY_RESEARCH", "held": "HELD"}[view]
                shown = [c for c in cases if c.get("lane") == lane]
            if q:
                shown = [c for c in shown if q.casefold() in " ".join(str(c.get(k) or "") for k in
                         ("property_address", "parcel_id", "why", "owner_names")).casefold()]
            return render_template("pmi_review/index.html", **context(ready=True, cases=shown, counts=counts,
                                   active_view=view, filter=view, query=q))
        except Exception:
            return unavailable()

    @bp.post("/login")
    def login():
        try:
            seed = login_signer.loads(request.cookies.get(LOGIN_COOKIE, ""), max_age=3600)
            valid_csrf = isinstance(seed, dict) and isinstance(seed.get("nonce"), str) and hmac.compare_digest(request.form.get("csrf_token", "").encode(), csrf(seed).encode())
        except (BadSignature, SignatureExpired):
            valid_csrf = False
        if not valid_csrf:
            return login_page("Reopen this page and sign in again.", 403)
        supplied = request.form.get("access_key", "")
        if not hmac.compare_digest(supplied.encode(), key.encode()):
            return login_page("The access passphrase did not match.", 401)
        response = redirect(url_for("pmi_review.index"), code=303)
        response.set_cookie(COOKIE, signer.dumps({"actor": actor, "nonce": secrets.token_urlsafe(24)}),
                            max_age=SESSION_SECONDS, httponly=True, secure=not allow_http, samesite="Lax", path="/review")
        response.delete_cookie(LOGIN_COOKIE, path="/review")
        return response

    @bp.post("/logout")
    def logout():
        response = redirect(url_for("pmi_review.index"), code=303)
        response.delete_cookie(COOKIE, path="/review")
        return response

    @bp.post("/initialize")
    def initialize():
        try:
            store().initialize()
            return redirect(url_for("pmi_review.index", message="Review workspace is ready. Load the existing property research to begin."), code=303)
        except Exception:
            return unavailable()

    @bp.post("/import")
    def import_cases():
        try:
            review_store = store()
            if not review_store.ready():
                return render_template("pmi_review/setup.html", **context(error="Initialize the review workspace before loading research.")), 409
            review_store.import_payload(source_loader(), actor)
            return redirect(url_for("pmi_review.index", message="Existing property research loaded. Seller hypotheses remain separate from the research pilot."), code=303)
        except ValueError as exc:
            return render_template("pmi_review/setup.html", **context(ready=True, error=str(exc))), 400
        except Exception:
            return unavailable()

    @bp.get("/cases/<case_id>")
    def case_detail(case_id):
        try:
            return case_page(case_id)
        except Exception:
            return unavailable()

    def mutation(case_id, action, success):
        try:
            action(store())
            return go_case(case_id, success)
        except (ValueError, KeyError) as exc:
            return case_page(case_id, error=str(exc), status=400)
        except Exception:
            return unavailable()

    @bp.post("/cases/<case_id>/state")
    def update_state(case_id):
        return mutation(case_id, lambda s: s.set_state(case_id, request.form.get("state", ""),
                        request.form.get("note", ""), actor, event_id()), "Progress saved.")

    @bp.post("/cases/<case_id>/pilot")
    def update_pilot(case_id):
        return mutation(case_id, lambda s: s.set_pilot(case_id, checked("enabled"),
                        actor, event_id()), "Research pilot updated.")

    def reference(value):
        value = value.strip()
        return {"source_url": value} if source_url(value) else {"source_record_id": value}

    @bp.post("/cases/<case_id>/evidence")
    def add_evidence(case_id):
        data = {"observed_at": request.form.get("observed_at", ""), "current": checked("current"),
                "verified": checked("verified"), "detail": request.form.get("detail", ""),
                **reference(request.form.get("source_ref", ""))}
        if request.form.get("supersedes"):
            data["supersedes"] = request.form["supersedes"]
        if request.form.get("evidence_type") == "public_statement":
            identity = reference(request.form.get("identity_source_ref", ""))
            person_id = request.form.get("person_id", "").strip()
            if not person_id:
                # A local attribution reference does not assert that matching
                # names across properties identify one person.
                person_id = "case_person_" + hashlib.sha256(json.dumps(
                    [case_id, " ".join(request.form.get("person_name", "").casefold().split()),
                     request.form.get("identity_source_ref", "").strip()], ensure_ascii=False).encode()).hexdigest()[:24]
            data.update(kind="PUBLIC_STATEMENT", display_name=request.form.get("person_name", ""),
                        person_id=person_id, relationship="OWNER", identity_method="OPERATOR_VERIFIED",
                        identity_verified=checked("identity_verified"),
                        identity_source_url=identity.get("source_url", ""), identity_source_record_id=identity.get("source_record_id", ""),
                        quote=request.form.get("quote", ""), statement_kind=request.form.get("kind", ""),
                        access=request.form.get("access", "PUBLIC"), about="SELF",
                        property_specific=checked("property_specific"), valid_until=request.form.get("valid_until") or None)
        else:
            value = request.form.get("value", "")
            try:
                decoded = json.loads(value)
                if not isinstance(decoded, (dict, list)):
                    value = decoded
            except (ValueError, TypeError):
                pass
            data.update(kind="FACT", field=request.form.get("field", ""), value=value, usable=True)
        return mutation(case_id, lambda s: s.add_evidence(case_id, data, actor, event_id()),
                        "Source evidence saved and the case rechecked.")

    @bp.post("/cases/<case_id>/review")
    def submit_review(case_id):
        data = {k: request.form.get(k, "") for k in ("analysis_id", "hypothesis_id", "outcome", "method", "detail")}
        data["verified"] = checked("verified")
        if request.form.get("supersedes"):
            data["supersedes"] = request.form["supersedes"]
        return mutation(case_id, lambda s: s.review(case_id, data, actor, event_id()), "Reviewed finding saved in case memory.")

    @bp.get("/export")
    def export():
        try:
            payload = store().export_payload()
            return Response(json.dumps(payload, ensure_ascii=False, allow_nan=False, indent=2),
                            mimetype="application/json", headers={"Content-Disposition": "attachment; filename=PMI-review-backup.json"})
        except Exception:
            return unavailable()

    return bp
