# Seller AI reasoning and review memory

This draft adds an AI reasoning core over existing PMI profiles. It generates
creative opportunity hypotheses, challenges them against cited observations,
and carries reviewed outcomes into later model context. The vocabulary is
expandable; the user clarified that no final list of seller reasons was adopted.

Each hypothesis records the circumstance, possible seller reason, useful agent
contribution, supporting observations, competing explanations, one consequential
next check, and what would disprove it. The challenge pass can hold an idea in
machine research or reject that explanation without erasing independent ideas.
Model outputs never authorize contact or establish confirmed seller intent.

An address supports a human handoff; unknown ownership remains nonblocking.
Price, presumed equity, missing fields, and repeated signals do not qualify an
opportunity. The model's two passes are reasoning checks, not independent factual
corroboration. Citation validation proves that a cited observation was supplied;
the model can still misunderstand its meaning. Realtor review remains essential.

Packets also link properties with the same reported owner name using anonymous
aliases. This enables portfolio hypotheses without treating name matches as
verified common control. It does not build personal demographic profiles.
Known owner names and property addresses are removed from model context, including
their occurrences in source prose. Exact source observations and addresses remain
in local records for the operator. This is targeted redaction, not a general
guarantee that arbitrary source text contains no personal information.

## Learning behavior

Analysis snapshots and review events are append-only. A review references an
exact case revision and hypothesis, identifies its reviewer and evidence method,
and records a finding. Replayed requests do not overwrite history or inflate
pattern counts. Corrections append another event and retain the previous finding.

Only verified reviews influence retrieved pattern lessons. Each property
contributes its latest verified outcome to a pattern, so repeated analyses of one
property cannot manufacture a successful pattern. Reviewer prose and personal
details stay out of model lessons. The model receives both useful outcomes and
false positives; a prior success is not proof about another owner's intent.

An operator's inference cannot be recorded as a confirmed owner reason:
SELLER_REASON_CONFIRMED requires OWNER_DISCLOSURE. That is a trusted reviewer
attestation, not a machine verification of the conversation. There is no public
review-write endpoint in this draft.

This is learning through persistent feedback retrieval. Model weights are not
retrained. The lessons currently report empirical outcomes, not calibrated
probabilities, seller scores, or automatically adopted rules.

## Running the draft

Preparing packets is offline and makes no model calls:

    python seller_ai.py packets --input existing-find4.json --output packets.json

Analyze one explicitly selected case with a configured provider:

    python seller_ai.py analyze --input existing-find4.json --case-id CASE_ID --memory reviews.db --output analysis.json

The process requires OPENAI_API_KEY and PMI_REASONING_MODEL in its environment.
Credentials are never supplied in input JSON, committed, or printed. Each
analysis makes two model calls, unless the proposal pass returns no hypotheses.
The provider adapter uses OpenAI Responses with strict structured output and
store: false. It does not fetch websites, refresh property sources, or run
model-suggested commands. Provider charges apply only when analysis is invoked.

The selected model must support Responses structured output. Model choice is
explicit rather than hardcoded. API details were checked against the
[OpenAI structured-output guide](https://developers.openai.com/api/docs/guides/structured-outputs?api-mode=responses).

A review JSON uses these fields:

    {
      "event_id": "operator-assigned-idempotency-key",
      "analysis_id": "stored-analysis-id",
      "hypothesis_id": "H1",
      "actor": "realtor",
      "outcome": "USEFUL_INVESTIGATION",
      "method": "OPERATOR_REVIEW",
      "detail": "The observed project status justified a focused inquiry.",
      "verified": true
    }

Store it and read the learned outcomes:

    python seller_ai.py review --input review.json --memory reviews.db
    python seller_ai.py lessons --memory reviews.db

SQLite is for explicitly selected local development. The PostgreSQL adapter
requires the supplied separate-table migration before use; it never changes the
legacy ledger or creates production tables automatically.

## Verification and current limits

Sixty-nine offline tests passed: 25 new reasoning/memory checks and 44 existing
source-profile evaluator checks. The new tests exercise citation fabrication, challenge
coverage, unsupported ideas, contradictions, unknown owners, missing addresses,
case-specific identity redaction, reported-name links, persistent memory,
idempotency, corrections, verified-only learning, and provider failures.

    python -m unittest discover -s tests -v

Packets were prepared successfully for all 194 current FIND4 profiles, without a
model call. Those profiles contain 147 supported property-research routes,
28 research hypotheses, and 19 closed-explanation cases; seller intent is unknown
for all 194. These are inputs for an intelligence experiment, not 194 seller leads.

No actual model hypotheses or seller outcomes have yet been validated on that
batch. Only synthetic model responses exercise the reasoning tests. PostgreSQL
operation, live provider behavior, and operator workload require a controlled
pilot. The core is not registered with Flask and has no live background worker;
production integration must keep long model calls out of Gunicorn's default
30-second request timeout. Provider credentials, protected operator access, and
an explicit memory migration/worker setup are required before activation.

Existing application routes, protected V19V, marketing, and contact permissions
are unchanged by this draft.
