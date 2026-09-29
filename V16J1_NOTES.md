# V16J1 — Investigation Inbox HTML Route Repair

## LOCK
V16I and the proven V16J JSON/API behavior remain protected.

## FAILURE
`/api/intelligence/investigation-inbox-v16j` returned `status: ok`, while the human-facing `/investigations` route returned HTTP 500.

## ISOLATED CHANGE
Presentation only. `/investigations` now renders escaped plain HTML from the already-proven V16J payload without Jinja/template evaluation. No intelligence, database, state, contact, scoring, or outreach logic changed.

## VERIFY
1. `/api/intelligence/investigation-inbox-v16j` remains `status: ok`.
2. `/investigations` returns an HTML page instead of HTTP 500.
3. With zero INVESTIGATE records, page says `No properties require investigation.`
