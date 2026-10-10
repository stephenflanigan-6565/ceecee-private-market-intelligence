# PMI internal intelligence and review memory

PMI reasons inside its own application environment using supplied property
facts, public/authorized information, explicit relationships, and reviewed cases.
The engine has no external model client, AI credential, model download, or paid
AI dependency. Python's standard library is sufficient for local analysis.

The user clarified that the intended system is PMI's own persistent reasoning
and memory. No fixed seller-reason list was adopted. The implemented pattern
vocabulary is expandable; initial examples do not define its whole universe.

## How the engine works

Each property retains source observations, stable citations, route decisions,
and an immutable case revision. The engine matches implemented or explicitly
reviewed patterns, checks contradictory observations, and records a possible
seller circumstance, competing explanations, useful agent service, and the next
consequential check. A closed explanation's observations cannot silently
reopen that explanation. Independently supported alternatives remain possible.

A completed project with an unused property is one initial example. Additional
patterns can be registered after review. Generic price, apparent equity, age,
family details, missing information, or an assessment anomaly do not establish
a seller opportunity. Unknown ownership remains nonblocking for a supported
address-based property investigation.

This is a custom evidence and case-based expert system. It reasons within the
patterns and input contracts implemented here. It does not provide unrestricted
natural-language understanding, autonomously invent verified facts, or train
general language-model weights.

## Public and social intelligence in both directions

The optional `public_information` input connects:
- A property to a verified owner/controller and the person's attributed statement.
- A person expressing buying interest to properties linked through ownership
  evidence, retaining the question of whether any sale is involved.

Source quotations, source locators, dates, claimed subjects, identity links, and
review attestations remain attached. Matching a name alone does not establish
identity or current control. Ambiguous links remain research. An explicit sale
statement requires a current, attributed, source-attested statement and a
specific property reference before it supports an owner-specific review.

Buying interest does not establish a sale obligation. Announced life events
and other circumstances remain context. Locations can support comparisons;
age or family attributes do not become seller-qualification rules.

The input consumes already captured public or authorized records. It does not
scrape social networks, log into accounts, fetch supplied URLs, or claim a
source has been read merely because its URL was supplied. Statement labels and
verified flags are trusted operator/source attestations, not proof created by
the parser. Free-form posts are not classified automatically by this draft.

## Learning that can be inspected

Append-only memory retains exact reasoning snapshots, review events, and
corrections. A verified finding is linked to its case revision and hypothesis.
One property contributes its latest verified outcome to a pattern, so replayed
requests or many analyses of one property cannot inflate learned counts.

Comparable reviewed cases carry their supporting observations and snapshot
references into future reasoning. Outcomes include useful investigations,
false positives, source errors, and disclosed seller reasons. Earlier success
does not establish a new owner's intent.

Pattern suggestions derive from reviewed evidence conditions and outcomes.
They remain proposals until explicitly reviewed and registered. Approved
definitions participate in later analyses; unverified proposals do not qualify
properties. Corrections preserve older definitions and findings. This makes
learning durable and reviewable rather than silent score changes.

The engine distinguishes a possible property opportunity from an attributed
expressed sale plan. Neither authorizes contact. Confirmed seller reasons in
review memory require a reviewer-attested owner disclosure.

## Running locally

Prepare all supplied profiles without writes or external calls:

    python seller_ai.py packets --input existing-find4.json --output packets.json

Analyze the full batch offline; every case is retained:

    python seller_ai.py analyze --input existing-find4.json --output results.json

Enable persistent local memory and a bounded five-property review batch:

    python seller_ai.py analyze --input existing-find4.json --memory reviews.db --review-limit 5 --output results.json

An optional `--case-id CASE_ID` limits analysis to that existing case.
`--as-of YYYY-MM-DD` makes public-statement date checks reproducible.
Overflow stays in a review backlog; weak context stays in machine research.
The five-property cap controls operator workload, not a universal signal count.

Review JSON references stored analysis/hypothesis identifiers:

    {
      "event_id": "operator-assigned-idempotency-key",
      "analysis_id": "stored-analysis-id",
      "hypothesis_id": "stored-hypothesis-id",
      "actor": "realtor",
      "outcome": "USEFUL_INVESTIGATION",
      "method": "OPERATOR_REVIEW",
      "detail": "Verified project circumstances warranted the focused inquiry.",
      "verified": true
    }

    python seller_ai.py review --input review.json --memory reviews.db
    python seller_ai.py lessons --memory reviews.db
    python seller_ai.py suggest-patterns --memory reviews.db

Pattern registration requires a reviewed structured definition and actor/event
identity. It never runs a command contained in source data. SQLite is explicit
local development storage. The PostgreSQL adapter requires the separate
migration to be applied before use and does not create production tables.

## Activation and validation limits

The reasoning core now has a protected operator integration at `/review/`.
See OPERATOR_REVIEW_GUIDE.md for activation. The workspace accepts operator-captured
facts and attributed public/authorized statements, saves case workflow separately
from verified hypothesis feedback, and uses persistent PostgreSQL in production.
Initialization creates only isolated review and memory tables through an
authenticated POST. No migration or writes happen on ordinary GET requests.
Source discovery/fetch adapters and production-memory activation remain separate
from this operator workflow; no production data migration has been applied by
the development session.

All actual FIND4 profiles are used as offline input. Actual results and owner
data stay outside the source PR and package. The current export has no public
statement records, so social paths are verified with synthetic fixtures. An
empty review batch means the implemented seller-circumstance patterns did not
match supplied evidence; it does not establish that the properties cannot sell.

    python -m unittest discover -s tests -v

Existing diagnostic routes, protected V19V, legacy evidence ledger, marketing,
outreach, and contact permissions retain their behavior. web_app.py registers
the isolated operator blueprint and adds a home navigation link.

## Verification record for this revision

All 139 offline tests passed and were independently rerun. Explicitly historical,
invalid, and other-property/market facts remain in history but cannot qualify
current opportunities. Missing dates remain visible unknowns; unknown maturity
is not silently claimed to be verified current evidence.

A reviewed negative finding holds an unchanged explanation across irrelevant
notes, duplicate copied routes, and route-order changes. A stable evidence
fingerprint retains relevant source context while ignoring array positions.
New relevant source observations or an explicit reviewed correction can reopen
an inquiry. Findings about another property never settle the new case.

Approved rules can be retired with a verified pattern registration using
`approved: false`, including the initial example. An unverified draft retirement
cannot turn off an active rule; a later verified approval can reactivate it.
History is preserved throughout.

All 194 current profiles were retained in local append-only memory. No initial
seller-circumstance pattern matched this export, and it has no public statements.
The 147 existing property investigations and 28 research hypotheses remain
available, alongside 19 closed-explanation cases. An empty new seller batch does
not dismiss those properties. Public/social behavior is tested with synthetic
fixtures. No external/model calls or production database writes occurred.

## Operator integration validation

The full offline suite passes 192 tests, including 29 persistent-workspace
checks, 21 independent authentication/HTTP checks, and three real form-to-engine
checks. Browser validation retained all 194 actual cases, bounded the research
pilot to five, preserved working notes/stages across reloads, and downloaded a
complete private workspace record. A separate synthetic browser check exercised
typed source capture, verified negative feedback, and attributed sale statements.

An isolated PostgreSQL 16 container verified durable storage, source/review
behavior, atomic import and memory rollback, enforced read-only connections,
and the five-case limit under nine concurrent writers. This validates the
PostgreSQL adapter locally; production activation still requires the operator
passphrase and authenticated initialization against the existing app database.
No production schema migration or review data was written during development.
