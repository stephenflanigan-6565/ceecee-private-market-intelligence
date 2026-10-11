# Review learning

PMI analyzes saved operator work inside the existing app and database. Open **Review learning** in the workspace navigation to see properties reviewed, notes, formal findings, verified outcomes, evidence, and the next useful checks. No file transfer is needed for this workflow.

The existing background worker builds the first analysis after deployment and checks for changes every two minutes. Saving a stage/note, evidence, or a formal finding also refreshes the analysis after that save succeeds. **Check saved reviews** refreshes the report immediately. Refreshing does not contact source websites or change a property's stage, evidence, seller status, or pilot membership.

The report preserves working notes and displays them as context. Formal verified findings contribute lessons and proposed evidence combinations through the existing internal memory. A useful property investigation is different from an owner-confirmed selling reason. Corrections and negative results remain in history; the report counts the latest verified outcome for each property/explanation and does not double-count a review mirrored in memory.

Pattern suggestions show what the reviewed sample supports and where it failed. They are candidates for further testing; generating the report does not adopt a new rule or automatically add properties. Finding new properties from adopted discovery rules remains a later development step.

Each changed input produces an append-only analysis in the existing review memory table. Unchanged inputs reuse the same report. The report is included in the ordinary workspace backup. The initial report may be preparing briefly after deployment. Its counts describe the actual saved database records, not the number someone remembers reviewing.

This release adds no database schema, service subscription, external model, or worker process. Existing automatic pilot research continues separately, and its source retrievals are not counted as the operator's reviews.
