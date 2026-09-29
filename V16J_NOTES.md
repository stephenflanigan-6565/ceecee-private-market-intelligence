# V16J — Investigation Inbox

Protected source: V16I / V16H chain.

Allowed change: add a read-only human-facing Investigation Inbox and JSON endpoint over durable V16D investigation state. Also remove the old CEECEE branding from the root page heading.

New routes:
- `/investigations`
- `/api/intelligence/investigation-inbox-v16j`

Guards: no seller scoring, no seller-intent inference, no contact authorization, no outreach, no external messaging, no opportunity creation, no database writes by the inbox.

Expected current result: 0 INVESTIGATE items and a clean quiet inbox.
