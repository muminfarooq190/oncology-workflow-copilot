# ADR 0004: Use a transactional outbox with Redis Streams

- Status: Accepted
- Date: 2026-08-12

## Context

Workflow intake must persist both the clinical workflow and the request for long-running normalization. Writing PostgreSQL and Redis independently creates a dual-write gap: a process can commit the workflow but fail to enqueue it, or enqueue work whose database transaction later rolls back.

Worker crashes also require redelivery without producing duplicate terminal transitions or audit events.

## Decision

PostgreSQL is the source of truth. Intake and retry transactions write a tenant-scoped outbox row alongside workflow and audit changes. A separate dispatcher publishes due rows to a Redis Stream, and workers consume through a Redis consumer group.

Delivery is at least once. Workers acknowledge entries only after a database transition commits. A persisted outbox ID identifies the active attempt; locked transitions and terminal-state checks make duplicate delivery idempotent. Idle pending entries are reclaimed. Transient failures create delayed outbox rows with a bounded exponential retry budget, followed by a dead-letter state that requires an explicit requeue command.

## Consequences

- A committed workflow cannot be silently lost between PostgreSQL and Redis.
- Duplicate publication or redelivery is expected and tested.
- PostgreSQL remains sufficient to reconstruct workflow state and audit history; Redis is replaceable delivery infrastructure.
- Dispatch briefly holds row locks while publishing and needs throughput monitoring before production-scale use.
- Outbox retention and archival require an operational policy before launch.
