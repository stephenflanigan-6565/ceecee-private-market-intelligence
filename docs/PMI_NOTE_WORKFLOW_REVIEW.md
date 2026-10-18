# Note-to-evidence workflow patch

Review candidate only. Do not merge or deploy without approval. Baseline is deployed main `6860e9c71b3dfba813dd5e43a44dfbfd9f74f05c` (tree `51a4373c5ffb741d9957874121d68b5a172f9142`). Existing case versions, original explanation bindings, imports, notes, evidence and review events remain append-only. No schema migration, seller scoring, price filter, discovery source, hosting or external notification changes.

## Workflow

1. Open What's new / Needs review in the workspace and open a property.
2. Review saved research presents existing notes with exact text and entry time. Select a note; its passage is already filled in. The server checks that any chosen excerpt occurs exactly in the original note on the same case.
3. Review the proposed field/value. Suggestions are deliberately literal and bounded: explicit past-marketing wording proposes historical marketing; explicit unknown condition proposes UNKNOWN; other notes default to unresolved acquisition context. This is not general natural-language learning. Relative purchase dates, dollar estimates, sell scores, plans and ownership are not converted to supported facts. Cece can correct the field/value in the same form.
4. Supply an actual source and observation date only if known, and explicitly confirm verified/current only if established. Empty provenance can be saved as unresolved evidence; it cannot qualify for matching. A note entry timestamp is never substituted. The note ID and exact passage remain in the saved evidence.
5. Save once. A content identity scoped to case, note, quote, fact, source, date, correction and operator prevents a repeated identical note confirmation even after reloading a lost response. The existing event-ID guard remains for other forms. Reusing an ID with different contents is rejected. A deliberately changed confirmation is a new record; use the correction selector to supersede an earlier value.
6. The receipt distinguishes the committed save from failed/pending derived assessment. The normal learning poll retries derived work. The panel shows used/excluded IDs, historical context, contradictions and before/after assessment changes. Formal explanation reviews remain separate and easy to reach.

## Meaning and boundaries

Supported current listing/representation status is now included in the evidence assessment and compared for explicit differences between otherwise comparable properties. Status never adds a matching dimension. SOLD/CLOSED is not a fresh lead; LISTED/REPRESENTED does not establish availability; HISTORICAL_MARKETING is not current marketing. Unknowns never match. A past sale does not delete a property or permanently remove it from research. Conflicting current facts are excluded until corrected. A correction to unknown retracts the old certainty without deleting it.

Condition and other supported property facts are shown with their evidence and affect the saved evidence assessment; they do not automatically prove the original ratio-based explanation or seller intent. Existing independent-dimension thresholds remain experimental. No new ranking or seller-selection rule is adopted. Westhampton Beach remains a pilot, not a luxury or universal price criterion.

## Daily activity

Read-only activity uses existing saved events and research runs, grouped by UTC day (explicitly labeled). It distinguishes newly imported inventory, properties with saved updates, source-check changes, failures and unresolved research. The source job checks existing inventory, so discovery is explicitly zero. No-change is shown only for a successful run whose source change summaries all say UNCHANGED. First observations, incomplete checks and failed checks are not labeled no-change. Last success uses successful runs, not the latest failed attempt. No new scheduler or email service is added.

## Validation and limitations

Fixtures adapt the five October 17 updates for 313 DUNE, 15 BAY, 110 DUNE, 12 SCHOOL and 123 POINT. They are not newly verified facts about those properties. Tests cover exact quotation, missing source/date, same-case binding, five distinct properties, preservation, correction to unknown, conflicting facts, sold/listed/historical distinctions, unchanged inputs, retry deduplication, assessment failure/recovery, read-only activity and successful/changed/failed source jobs. Existing runtime tests cover SQLite/PostgreSQL concurrency, interrupted transactions, source provenance and restored earlier states. GitHub Actions runs both backends and existing regressions in isolated databases. No production database is used.

Live records were not changed or re-exported during this patch. Existing versioned records remain the baseline; activation should first retain the existing complete research export via the supported workflow. Do not call a fixture run a live daily-cycle proof. Human usability is demonstrated through actual Flask GET/POST paths but Cece's own live walkthrough remains an acceptance step.

## Deployment and rollback (approval required)

1. Review the exact PR head and passing CI. Preserve the full supported research export, including case versions, notes/events, evidence, reviews, research snapshots and job history; verify counts and source revision.
2. Approve the exact head for merge. Use the existing main-to-DigitalOcean deployment; no environment or account changes. Check the active revision and authenticated screens.
3. With Cece's explicit input, reuse one existing note, confirm its actual passage/source/date/status, and save once. Confirm one durable event, the receipt, assessment ID/evidence use or explicit unresolved result, and retained original records. Do not submit on her behalf without authorization.
4. Observe one naturally due real daily research cycle after deployment. Record run IDs, start/completion, last-success time, changed/no-change/failure reasons and app-visible property links. Verify updated inventory is not counted as discovery. Compare notes and baseline versions against the preserved export.
5. If code checks fail, redeploy/revert code to `6860e9c71b3dfba813dd5e43a44dfbfd9f74f05c` through the existing process. Do not restore/reset the database. New evidence has ordinary FACT fields plus optional note provenance, so old readers retain the records. The hosting UI previously showed one-click rollback unavailable; code rollback remains the documented path, not a tested one-click promise.

Remaining live checks: approved deployment revision, real note confirmation/readback and Cece usability, one real daily-cycle outcome and visible report, full export preservation comparison. No synthetic test completes these checks.

## PR 10 review corrections (18 October)

Unknown values share case/whitespace/separator normalization in property comparisons, packet support and reviewed pattern support; raw originals remain unchanged. UNAVAILABLE and NOT ESTABLISHED cannot support matches. Explicitly superseded facts are removed before current exclusions are calculated, preserving history while clearing obsolete unknown/stale/unverified flags. Unrelated unresolved notes or facts still require review.

The property page and daily review queue compare saved EVIDENCE/REVIEW event IDs with consumed assessment IDs, including absent assessments and plain page reopen. Pending evidence is distinct from evidence used as support. Two independent authenticated clients concurrently confirm one note in the new regression; only one evidence event and version may persist. SQLite and PostgreSQL run these same cases. No schema, selection thresholds, production data or deployment changes.
