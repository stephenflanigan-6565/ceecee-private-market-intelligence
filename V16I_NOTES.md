# V16I — Scheduled Production Run

Protected source: V16H Attention Delivery Payload (PROVEN / LOCKED).

Allowed change only: add a thin scheduled-job entrypoint for the already-proven V16H chain.

DigitalOcean App Platform job configuration:
- Resource type: Job
- Trigger: On a schedule
- Run command: `python scheduled_production_run_v16i.py`
- Cron: `0 8 * * *`
- Time zone: `America/New_York`

Behavior:
- Calls V16H directly; no HTTP loopback.
- Quiet run exits 0 and sends nothing.
- INVESTIGATE decision exits 0; external notification transport is still intentionally disconnected.
- Pipeline failure exits non-zero so DigitalOcean records a failed job invocation.
- No seller logic, thresholds, Contact Governor, outreach, or scoring changed.

Verification gate: deploy, add the scheduled job component, run/observe one job invocation, and inspect its JSON log. Only after that is V16I eligible to be promoted/locked.
