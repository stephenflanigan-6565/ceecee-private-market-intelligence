"""One bounded official-record researcher, coordinated by a durable DB lease."""
from datetime import datetime, timezone
import logging
import threading
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


class _WorkerHandle:
    def __init__(self):
        self._stop = threading.Event()
        self._lock = threading.Lock()
        self._thread = None
        self._state = {"started": False, "last_poll_at": None,
                       "last_outcome": "STARTING", "last_completed_at": None,
                       "completed_runs": 0}

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
                 startup_delay=5):
    """Start one daemon per web process; database fencing bounds actual work."""
    handle = _WorkerHandle()
    interval = max(0.01, float(interval_seconds))
    delay = max(0, float(startup_delay))
    worker_id = "worker_" + uuid.uuid4().hex

    def poll():
        with handle._lock:
            handle._state["started"] = True
        if handle._stop.wait(delay):
            return
        while not handle._stop.is_set():
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
            if handle._stop.wait(interval):
                break

    handle._thread = threading.Thread(target=poll, name="pmi-case-research", daemon=True)
    handle._thread.start()
    return handle
