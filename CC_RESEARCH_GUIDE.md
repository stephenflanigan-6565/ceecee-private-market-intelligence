# CC research for the pilot

CC checks the properties selected in **Research pilot**, up to five at a time. Your wife can continue using the review workspace while the researcher works in the background.

## What it checks

The initial researcher retrieves official Suffolk County parcel records, reported ownership, current transfer records and transfer history. It matches the exact parcel identifier already attached to the case. It does not search by a guessed owner name or scan every county property. Unsupported identifiers and unavailable sources remain visible questions.

Each check keeps the source query link, retrieval timestamp, source-record dates and content hash. Recorded document dates and the time CC checked the source have different meanings. A new content hash identifies a changed source record even when its official object ID remains the same. The first check establishes a baseline; later checks compare against that source's last complete successful retrieval. A failed check retains earlier successful evidence and labels it with its original timestamp.

The sources establish reported record information. They do not establish current occupancy, completed projects, a sale motive, true equity, or the owner's future plans. Those conclusions still need relevant evidence. A recorded transfer can resolve an old inquiry rather than create a new seller opportunity.

## How to use it

Open **Research pilot** to see research status, latest completed checks and upcoming work. Automatic checks run sequentially to keep the small app responsive. Successful checks are scheduled about every 24 hours; source problems retry after a longer pause instead of looping. The schedule is stored in PostgreSQL, and a shared lease prevents both application processes from fetching at once.

Use **Check pilot now** to queue an earlier check, then reload the page to see progress. Queuing does not block the page while sources respond. A five-minute cooldown limits repeated manual requests. On a pilot property's page, **Check this property** queues just that case. Add a property to the pilot before requesting it. Cases marked **Set aside** are skipped until their stage changes.

Use **Pause CC research** to stop new checks and **Resume CC research** to resume them. Pause survives a deployment. An already-running check may finish and retain its result. The next app process resumes due work after a restart; abandoned runs are marked interrupted and stale workers cannot overwrite later results.

## Reviewing what CC found

The case's **CC research** section shows its findings, what changed, individual source status and next useful checks. Successful and failed sources are shown independently. Retained successful records are clearly distinguished from a failed new check. Research runs also appear in **History**.

The researcher preserves operator notes, workflow stages, evidence corrections and reviewed findings. Automatically retrieving official records does not mark your wife as having verified them, change seller qualification, or confirm a reason to sell. Her review follows the existing desk reference: working notes track judgment, source capture retains specific evidence, and verified explanation-specific feedback informs CC's memory.

This phase does not automatically discover public/social posts, infer intent from life events, contact owners, or send marketing. It does not add an outside AI provider, paid source credential, or separate paid worker.

## Deployment

The existing production app starts the researcher when the private review passphrase and PostgreSQL connection are already configured. It creates only its isolated research tables after the existing review workspace is ready. Ordinary GET requests remain read-only; new authenticated controls use the same CSRF boundary as other review forms. No additional control-panel setup is needed for the already initialized pilot. `PMI_RESEARCH_ENABLED=0` disables automatic process startup if required operationally.

The public health response contains only nonidentifying process flags/timing; property evidence and owner details remain behind the review login. Monitor app memory, CPU and restart metrics under DigitalOcean Insights as use grows.
