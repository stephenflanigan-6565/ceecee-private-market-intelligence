# PMI five-pilot runtime patch — review checkpoint

Status: TESTED PATCH, DRAFT / UNMERGED / NOT DEPLOYED.

- Draft PR: https://github.com/stephenflanigan-6565/ceecee-private-market-intelligence/pull/9
- Tested code/test commit: feffc920f0177a7adbc3b4fab0ae60dfd165fe5d
- Tested tree: 1b7f2a8933a31b6d9b539e40104d5ce0d07c9f23
- Baseline main: 237c8e49b4cfdfdf4bf3976e42649826165b9761
- Runtime branch: codex/five-pilot-runtime
- Earlier prototype branch remains unchanged and unmerged: codex/feedback-loop-proposal-tests at 24087ae4ef39400b06c2eed474a225a5c1816ac7.
- No real operator finding, production database write, merge or deployment was performed.

## What changed

pmi_property_loop.py adds a derived property-research assessment using existing append-only review storage. Each finding resolves the exact retained analysis ID, hypothesis ID, original schema version, baseline revision and original explanation. Verified explicit corrections supersede only their linked findings; independent contradictory findings remain a conflict. Historical explanations remain visible and cannot seed current-baseline comparisons.

pmi_review_store.py refreshes this projection within the existing serialized learning transaction. pmi_research_store.py refreshes after source acquisition commits. A projection error does not undo collected sources. The existing learning poll retries from saved inputs without another acquisition. Imports preserve the deferred-refresh contract and are picked up by that poll.

The report, comparisons, sequence and predecessor commit atomically as one append-only PROPERTY_LOOP record. Retry of the same current inputs creates no extra record. Evidence returning A → B → A creates a new current sequence even when its source snapshot content ID is reused. A new source run or freshness-evaluation day can create an evaluation checkpoint without claiming new market/property facts.

Source snapshots, matching acquisition run IDs, last successful check time, source observation timestamp, source-record dates and source-supplied effective dates remain distinct. Missing effective dates stay unknown. The latest failed source attempt is shown alongside retained last-good records. Missing research initialization, invalid binding, rejected source identity and stale checks remain explicit.

pmi_review.py and templates/pmi_review/{case,property_loop}.html render the saved assessment in the authenticated case page. GET remains read-only. The display labels the evaluation/save time and states that newer changes may await a poll. It includes exact original finding history, bounded comparisons, evidence, exclusions and dated source changes.

## Experimental policy — not seller selection

Current explicit research thresholds: two independent property dimensions, observations no older than 30 days, source checks flagged stale after two days, up to 200 saved inventory properties examined and three suggestions per explanation. Truncation is disclosed. These values are experimental implementation assumptions for review, not validated business rules.

Notes are not parsed as facts. Vacancy alone cannot satisfy the two-dimension requirement. Source-record retrieval does not establish present occupancy, ownership authority or seller intent. Comparisons use verified typed observations; failed/stale official checks are disclosed, not silently promoted into current facts. No rules, seller scores or contact permissions are changed.

## Verified tests

Final run: https://github.com/stephenflanigan-6565/ceecee-private-market-intelligence/actions/runs/39072262956
Job: 117512129855. PostgreSQL 16.15 (160015).
- 14 runtime checks: seven SQLite + seven PostgreSQL, zero failures/errors/skips.
- 115 existing review, authentication, learning, scheduler and source-storage regressions passed.
- Corrections and same-property reimport retain separate historical/current explanation bindings.
- Different reasons and invalid version bindings cannot borrow each other's findings.
- Five actual persisted scheduler claims/checks per cycle; A/B/A records preserve snapshot identity and distinct run identity.
- Failed and stale sources retain previous records and disclose status/dates.
- Interrupted projection after committed acquisition is repaired by the learning poll without new research runs.
- Failure after projection INSERT but before COMMIT rolls back; concurrent retry produces one new sequence.
- Authenticated app readback shows two synthetic comparisons and performs no GET writes.
- Existing tests were narrowly updated to allow derived PROPERTY_LOOP rows while asserting exact protected analysis/feedback preservation.

Earlier Windows broad-suite execution encountered existing SQLite temporary-file cleanup errors. Linux CI is the completed regression evidence. An intermediate strengthened test read an import before its deferred poll; the final test explicitly exercises that poll and passes on both databases.

## Review artifacts and limits

Local synthetic app preview: local-evidence/app-preview.html.
Local saved assessment: local-evidence/assessment.json.
These are generated from synthetic fixtures through the actual authenticated app route, NOT 12 SCHOOL ST or real pilot results. The preview contains the assessment section with a static presentation wrapper; it is not a deployed application.

The runtime code and protected v19v.py are unchanged since the final tested tree. v19v.py has no Git diff from baseline (local CRLF bytes may hash differently from repository LF bytes).

This patch reuses the existing enabled worker and five-pilot scheduler; it does not start or enable a deployed scheduler. Production rollout, actual daily executions and Cece's real finding/date reconciliation remain unproved. The bounded comparison policy does not cap the whole workspace's saved history; full derived reports consume additional append-only storage. This is a small-workspace implementation, not a large-inventory performance acceptance.

## Approval and rollback

Next step: review draft PR #9 and approve deployment of its exact reviewed commit separately. Do not merge the prototype. Before real-case acceptance, Cece or Stephen must explicitly choose the finding and verification status; reuse the existing notes rather than asking for re-entry.

Code-only rollback: redeploy the previous approved runtime revision through the existing deployment pipeline. Do not restore/reset the database. All operator findings, original explanations, research runs/source snapshots and PROPERTY_LOOP history must remain retained. No schema migration or destructive backfill is introduced.
