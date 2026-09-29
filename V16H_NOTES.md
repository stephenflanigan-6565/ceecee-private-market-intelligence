# V16H — Attention-Only Delivery Payload

Protected base: V16G.

Purpose: turn one proven pipeline run into a delivery decision without yet connecting an external notification service.

Behavior:
- quiet successful run -> send=false, QUIET_NO_ACTION
- INVESTIGATE present -> send=true, AGENT, explainable queue payload from locked V16D
- pipeline failure -> send=true, OPERATOR, failure payload
- no external message is sent in this build
- no contact authorization, outreach, seller scoring, probability, or inferred seller intent

After this endpoint is verified, connect the scheduler and notification transport to this contract.
