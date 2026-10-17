# PMI small feedback loop — isolated proposal and validation

Status: prototype only, not merged or deployed. Main remains PR #8 merge 237c8e49b4cfdfdf4bf3976e42649826165b9761. No real operator finding was invented or saved.

## Current code and smallest proposed integration

PR #8 explicitly links a reviewed finding to the saved original explanation. Its feedback reaches the learning report, but does not reassess the baseline property explanation or find comparable properties. The daily worker persists official-record snapshots and run history but intentionally does not pass them into case analysis.

Propose one versioned derived property-research assessment, separate from seller qualification:
1. Read the existing explicit reviewed finding, its original analysis/baseline version, existing typed evidence and notes. Notes remain verbatim context and are never parsed into verified facts.
2. Assess whether that finding supports or contradicts the original property research. Preserve the finding's event/analysis/hypothesis/case-revision references and all older reasoning.
3. Include complete, exact-parcel official-source rows as SOURCE_REPORTS_ONLY evidence with the source URL, raw record IDs/values, source dates and a content identifier. A county record reporting a name is not current ownership verification; a fetch date is not a property observation date. Unsupported fields remain context, not seller evidence.
4. Produce at most three comparison candidates from up to 200 already-saved properties, with a visible truncation indicator. No provider calls in comparison. Candidate output cites the seed finding and matching case evidence, contradictions, unknowns and the next question. No seller probability, qualification or outreach.
5. In production, the existing post-save refresh and existing daily worker would call the derived projection. A retry through the existing learning poll must recover interrupted derived processing without repeating source acquisition or duplicating feedback. This production wiring is NOT in this prototype.

The experimental comparison policy requires the same supported explanation family and two independently named property dimensions from explicitly verified, current typed observations. Vacancy alone, price/equity, notes, unverified records, stale observations and a reviewed false positive cannot seed or satisfy the comparison. The prototype's freshness window is a configurable 30-day TEST policy, not an adopted production rule. Use source-appropriate date meaning and freshness in a reviewed production implementation. Comparisons remain research suggestions, never automatic selection-rule adoption.

## Implemented in isolation

- experiments/pmi_feedback_loop_proposal.py: source-evidence projection, versioned property reassessment, bounded comparison and append-only persistence using the existing memory table.
- tests/test_feedback_loop_proposal.py: real ReviewStore/ResearchStore storage, explicit fixture reviews/evidence, retained notes and a test-only finish adapter around the existing run_once scheduler.
- .github/workflows/pmi-feedback-loop-proposal.yml: disposable PostgreSQL 16 test job, synthetic records only, no deployment, credentials or app writes.

No existing production module, V19V, discovery rule, ownership contract or outreach safeguard was modified. The adapter is deliberately experimental; it is not installed in the application's worker, case screen or learning report.

## Verified isolated results

Code under test: e04eaa9565fb3f553e98eddc2870671c16bff333.
Run: https://github.com/stephenflanigan-6565/ceecee-private-market-intelligence/actions/runs/39069433741
Job: 117503773609.
PostgreSQL version: 160015 / 16.15.
10 tests, 0 failures, 0 errors, 0 skips; 12.930 seconds.
Five tests exercised SQLite and the same five exercised PostgreSQL. Container cleanup succeeded.

Synthetic before/after:
- Before explicit verified finding: AWAITING_EXPLICIT_REVIEW, no comparison candidates.
- After explicit verified USEFUL_INVESTIGATION: REVIEW_SUPPORTS_PROPERTY_RESEARCH. The saved review reference seed-review appears in the persisted assessment and each candidate. The existing learning report counts the explicit feedback. All five original synthetic notes and original baseline remain identical on reopening.
- Two candidates have the same supported explanation family and explicitly verified property-form and occupancy observations. They retain UNKNOWN seller intent and contact_authorized=false.
- Five failures cover vacancy alone, unverified supporting observation, contradictory property form, stale evidence, and a reviewed false positive. No rejection erases the property.
- Undated vacation-home/vacancy observations do not become current facts. If both are encoded as incompatible claims of the same current field, the prototype preserves the disagreement instead of selecting the most recently fetched one. In real records, vacation-home use and physical vacancy can be different concepts and can coexist; their meaning must be reconciled first.

Scheduled execution proof, not just counters:
- The tests use the actual persisted claim/lease/finish scheduler and run_once, with an injected synthetic collector and controlled clock.
- Day 1: five selected pilots execute and retain actual fixture rows.
- At 23 hours: scheduler returns IDLE.
- At 24 hours: five due pilots execute; unchanged row content produces no additional derived projection records.
- Next day: five pilots execute with OWNERNAME changed from SYNTHETIC owner A to SYNTHETIC owner B.
- Fifteen stored run records include case, started/completed times and SUCCESS status. The logs contain the before/after source rows, exact OWNERNAME value change, linked review reference and needs_source_recheck=true. The changed evidence also appears as daily-source context in the comparison output.
- This is proof of isolated scheduled execution with a controlled clock, NOT proof that the live app has run this integration daily.
- Source rows failing parcel identity, exact approved source URL, complete-count reconciliation or source status are rejected.

## What remains unproved or unimplemented

- Cece's actual chosen finding on 12 SCHOOL ST has not been supplied. No opinion is inferred from her five notes.
- The original source references, effective/record dates, observed dates, retrieval dates and verification status for “vacation home” and “vacant” have not been inspected here.
- No actual inventory candidates or before/after production assessment have been computed. All examples above are explicitly synthetic.
- Production hooks, presentation in the case/learning screen, crash/retry recovery, per-explanation handling when a case has multiple reviewed reasons, current projection selection when evidence cycles back to an earlier state, and expired/failed-source disclosure still require implementation and isolated acceptance tests before deployment approval.
- In particular, the prototype chooses a latest review for its single-explanation demonstration. Production must resolve each original reason/version independently rather than apply one review across unrelated explanations.
- The current prototype persists a derived assessment; it does not modify seller_ai hypotheses or activate a selection pattern. It must not be described as a trained or self-adjusting seller algorithm.
- Main and the running app have not received any of this experimental code.

## Real 12 SCHOOL ST acceptance

After Cece explicitly chooses the finding and verification status through the existing review control, reuse her saved notes and evidence; no investigation or note re-entry is required. B9's existing login can inspect:
- chosen outcome, event ID and referenced original reason/version;
- preserved five notes and prior explanations;
- the two use/occupancy source records, their source meanings and separate dates;
- saved finding after reopening and exactly one learning-report occurrence;
- the subsequent derived reassessment citing that exact event and dated evidence;
- a bounded saved-inventory candidate list with nonmatches;
- a later actual scheduled run whose changed source values alter or flag the assessment, not merely its timestamp.

Do not save a real review on Cece's behalf without her or Stephen's explicit choice. Do not reinterpret a historical vacation-home classification as current occupancy, or a fresh fetch as current vacancy.

## Rollback and approval gate

This test branch is not to be merged or deployed. There is currently no production change to roll back. A future runtime patch must remain separately reviewable on the existing merged baseline and include both SQLite and PostgreSQL tests for the outstanding cases above.

Before deploying that future patch: present its exact commit, results, live-source/date assumptions and code-only rollback steps for approval. Rollback restores the previous runtime code, never restores over or resets the database. Appended operator reviews, source snapshots and reasoning versions remain retained. No schema migration or destructive backfill is proposed.

## Continuity and next action

The existing Drive handoff was read successfully, but its Markdown update could not be written: both shell execution and apply_patch return “No usable execution environment is available.” Do not claim it was updated. This report and the test logs are the durable repository checkpoint until supported file access is restored.

One next action for the real case: Cece explicitly chooses her finding on the existing 12 SCHOOL ST review control. Reuse the existing stored source records to resolve the vacation-home/vacancy dates before treating either as current. No new sources or connector are needed.

Keep the separate five-case comparison research cycle within this bounded loop; do not add social intelligence, outreach or new selection rules.
