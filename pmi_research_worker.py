"""One bounded official-record researcher, coordinated by a durable DB lease."""
from datetime import datetime, timezone
import logging
import threading
import time
import uuid

from pmi_case_sources import collect_case

LOG = logging.getLogger(__name__)


def _now():
    return datetime.now(timezone.utc).isoformat()


def _failed_bundle(case):
    return {"case_id": case["case_id"], "parcel_id": case["parcel_id"],
            "observed_at": _now(), "status": "ERROR", "sources": [],
            "findings": ["The official-record check could not complete. Previously saved evidence was retained."],
            "next_checks": ["CC will retry this property after six hours. You can continue reviewing saved evidence."],
            "change_summary": "No new records were confirmed by this check."}


def run_once(store, *, collector=collect_case, worker_id=None):
    """Collect one currently due pilot outside the scheduling SQL transaction."""
    if not store.review_ready():
        return {"status": "WAITING_FOR_WORKSPACE"}
    if not store.ready():
        store.initialize()
    claim = store.claim_next(worker_id or "worker_" + uuid.uuid4().hex)
    if claim is None:
        return {"status": "IDLE"}
    case = claim["case"]
    try:
        bundle = collector(case, claim["previous_sources"])
    except Exception:
        # Source/connection text may contain private details. Neither logs nor
        # the operator-facing result expose exception strings or stack traces.
        bundle = _failed_bundle(case)
    try:
        return store.finish(claim["run_id"], claim["lease_token"], bundle)
    except ValueError:
        # Invalid collector data never becomes evidence. A still-valid lease
        # saves a safe error and schedules a bounded retry; an expired worker
        # remains fenced even when attempting to save this error envelope.
        try:
            return store.finish(claim["run_id"], claim["lease_token"], _failed_bundle(case))
        except ValueError:
            return {"status": "RESULT_NOT_SAVED"}


def run_learning_once(store):
    """Refresh stored review analysis without creating an absent workspace."""
    if not store.ready():
        return "WAITING"
    report = store.refresh_learning()
    if report is None:
        return "WAITING"
    # The report's status describes its findings. The transient refreshed flag
    # describes this poll, and never exposes review details in public health.
    if report.get("refreshed") is True:
        return "CHANGED"
    if report.get("refreshed") is False:
        return "UNCHANGED"
    outcome = report.get("status")
    if outcome in {"CHANGED", "UNCHANGED", "WAITING", "UNAVAILABLE"}:
        return outcome
    raise ValueError("Invalid learning refresh outcome")


class _WorkerHandle:
    def __init__(self):
        self._stop = threading.Event()
        self._lock = threading.Lock()
        self._thread = None
        self._state = {"started": False, "last_poll_at": None,
                       "last_outcome": "STARTING", "last_completed_at": None,
                       "completed_runs": 0, "learning_started": False,
                       "learning_last_poll_at": None,
                       "learning_last_outcome": None,
                       "learning_last_completed_at": None,
                       "learning_refreshes": 0, "export_started": False,
                       "export_last_poll_at": None, "export_last_outcome": None,
                       "export_last_completed_at": None, "export_verified_runs": 0}

    def stop(self):
        self._stop.set()
        if self._thread and self._thread is not threading.current_thread():
            self._thread.join(timeout=2)

    def health(self):
        with self._lock:
            result = dict(self._state)
        result["alive"] = bool(self._thread and self._thread.is_alive())
        return result


def start_worker(store_factory, *, collector=collect_case, interval_seconds=30,
                 startup_delay=5, learning_factory=None,
                 learning_interval_seconds=120, export_factory=None,
                 export_poll_seconds=120, research_enabled=True):
    """Share one daemon for acquisition and optional stored-review analysis.

    Each task has its own safe error handling. Learning starts on the first
    poll, then checks no more often than every 30 seconds. The review store
    makes unchanged reports idempotent and coordinates concurrent processes.
    """
    handle = _WorkerHandle()
    if not research_enabled:
        handle._state["last_outcome"] = "DISABLED"
    interval = max(0.01, float(interval_seconds))
    delay = max(0, float(startup_delay))
    learning_interval = max(30.0, float(learning_interval_seconds))
    export_interval = max(30.0, float(export_poll_seconds))
    worker_id = "worker_" + uuid.uuid4().hex

    def poll():
        with handle._lock:
            handle._state["started"] = True
        if handle._stop.wait(delay):
            return
        next_learning_poll = None
        next_export_poll = None
        while not handle._stop.is_set():
            if learning_factory is not None and (next_learning_poll is None or time.monotonic() >= next_learning_poll):
                learning_checked_at = _now()
                try:
                    learning_outcome = run_learning_once(learning_factory())
                except Exception:
                    learning_outcome = "UNAVAILABLE"
                    LOG.warning("CC review analysis is temporarily unavailable; retrying after the learning polling interval.")
                with handle._lock:
                    handle._state.update({"learning_started": True,
                                          "learning_last_poll_at": learning_checked_at,
                                          "learning_last_outcome": learning_outcome})
                    if learning_outcome in {"CHANGED", "UNCHANGED"}:
                        handle._state["learning_last_completed_at"] = _now()
                    if learning_outcome == "CHANGED":
                        handle._state["learning_refreshes"] += 1
                next_learning_poll = time.monotonic() + learning_interval
            if research_enabled:
                checked_at = _now()
                try:
                    result = run_once(store_factory(), collector=collector, worker_id=worker_id)
                    outcome = result.get("status", "ERROR")
                except Exception:
                    outcome = "UNAVAILABLE"
                    LOG.warning("CC research storage is temporarily unavailable; retrying after the polling interval.")
                with handle._lock:
                    handle._state.update({"last_poll_at": checked_at, "last_outcome": outcome})
                    if outcome in {"SUCCESS", "PARTIAL", "ERROR", "UNSUPPORTED"}:
                        handle._state["last_completed_at"] = _now()
                        handle._state["completed_runs"] += 1
            if export_factory is not None and (next_export_poll is None or time.monotonic() >= next_export_poll):
                export_checked_at = _now()
                try:
                    export_result = export_factory().poll(worker_id=worker_id)
                    export_outcome = export_result.get("status", "UNAVAILABLE")
                    if export_outcome not in {"UNCONFIGURED", "WAITING", "BUSY", "RETRY_WAIT", "IDLE", "VERIFIED", "FAILED", "UNAVAILABLE"}:
                        export_outcome = "UNAVAILABLE"
                except Exception:
                    export_outcome = "UNAVAILABLE"
                    LOG.warning("CC private Drive export is temporarily unavailable; retrying after the export polling interval.")
                with handle._lock:
                    handle._state.update({"export_started": True,
                                          "export_last_poll_at": export_checked_at,
                                          "export_last_outcome": export_outcome})
                    if export_outcome == "VERIFIED":
                        handle._state["export_last_completed_at"] = _now()
                        handle._state["export_verified_runs"] += 1
                next_export_poll = time.monotonic() + export_interval
            if handle._stop.wait(interval):
                break

    handle._thread = threading.Thread(target=poll, name="pmi-case-research", daemon=True)
    handle._thread.start()
    return handle
