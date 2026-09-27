# V15M1 — PostgreSQL LIKE Literal Percent Repair

Surgical repair only.

- Root cause: psycopg interprets `%` in SQL query text as placeholder syntax.
- Repair: escape literal LIKE wildcards as `%%` for PostgreSQL/psycopg parameter handling.
- No schema changes.
- No persistence changes.
- No seller scoring, signals, opportunities, or outreach.
- V15M derived-intelligence logic otherwise unchanged.
