# V16E4c — Transfer Unique-Key Repair

Observed V16E4b failure: PostgreSQL rejected a transfer insert on the existing unique constraint
`transfers_parcel_id_history_sequence_document_number_source_key`.

Allowed change only: deduplicate against the database's actual business key:
`(parcel_id, history_sequence, document_number, source)`, including within the incoming batch.

Retained: proven acquisition, ownership source_object_id repair, transfer observed_at repair,
atomic rollback, and all no-contact/no-scoring safeguards.
