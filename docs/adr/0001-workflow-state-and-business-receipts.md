# Workflow state and business receipts

A business phase commits its artifacts and StepReceipt in one PostgreSQL transaction. A graph node checks the receipt before executing. A crash after business commit but before checkpoint therefore reuses the committed output.

LangGraph1.2.15 is locked. Our async Checkpointer saves full JSON channel values, metadata and pending writes, all scoped by project/run and fenced against the current Worker owner/epoch/lease/cancellation flag. Runtime ownership is never restored from graph state. Serialization accepts JSON and an explicit trusted Interrupt envelope, never pickle or arbitrary class names.

Review decisions are authenticated API writes. The graph pauses with interrupt; a fresh Worker epoch resumes with Command from the durable decision. The Worker releases its lease after the pause/completion checkpoint, and waiting time is excluded from the active execution budget.

This does not make external model calls exactly-once. A provider response lost before durable receipt can be requested again and charged again. Model reservations are never refunded after an unknown result.
