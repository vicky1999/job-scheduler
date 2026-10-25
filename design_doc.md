# DB Job Scheduler Design

## Overview
The DB backed Job Scheduler is a background job execution system built with FastAPI, SQLAlchemy, and PostgreSQL. It allows clients to create tenant-scoped jobs, schedule them for a future time, and process them asynchronously through a worker. The design aims to outline the flow and process of the scheduler.

## Problem and Goal
Applications need background jobs that need to be ran asynchronously in future such as notifications, data cleanup, and tenant-specific automation. 

This project solves that by storing jobs in a database and allowing workers to claim and execute them safely.

The core goals are to:
- Thousands of scheduled jobs sitting in the database at any time
- **Multiple consumer processes running concurrently (horizontally
scaled)**, each pulling due jobs and dispatching them to worker threads
- **No duplicate execution** — two consumers must never pick up the same job
- **Fault tolerance** — if a consumer or worker crashes mid-execution, the
job must not be lost
- Multi-tenant fairness

## Architecture
The system has three main components:
1. **API layer** for creating, updating, and listing tenants and jobs
2. **PostgreSQL** database for durable job state
3. **Scheduler worker** that polls for due jobs and executes them

The runtime flow is:
- A client submits a job through the API
- The job is inserted into the database with a status such as `PENDING`
- The scheduler polls for jobs whose scheduled time has arrived
- A worker claims a job by updating its status and lease metadata
- The worker executes the job handler and records the result
- If the handler fails, the system retries based on defined rules or marks the job failed

## Data Model
The main entities are Tenant and Job.


Tenant
- unique ID
- tenant name
- soft-delete support

Job
- ID, timestamps, and audit fields
- tenant_id
- scheduled_at
- handler
- payload
- status (PENDING, RUNNING, COMPLETED, FAILED, SKIPPED)
- retry_count
- last_error
- started_at / completed_at
- locked_by
- lease_expires_at

The shared Base model includes creation and update timestamps and soft-delete flags so the system can safely hide records without permanently deleting them.

## Scheduling Model
Jobs are eligible when they are pending, not deleted, and scheduled_at is less than or equal to the current time. The scheduler runs on a configurable poll interval and may process multiple jobs concurrently up to MAX_WORKERS.

Execution uses a lease-based claim pattern:
- when a worker selects a job, it marks it RUNNING
- the row stores the worker identity and a lease expiry timestamp
- the worker heartbeats to extend the lease while still processing
- if a worker crashes or stops heartbeating, the lease expires and the job can be recovered

This design prevents duplicate processing in the common failure scenario where a worker dies mid-job.

## Retry and Recovery
Failed handlers trigger a retry decision. The retry logic uses a simple exponential backoff pattern based on the retry count. If the retry budget is exhausted, the job is marked failed and the final error is stored. Expired leases are also recovered by resetting or re-queuing jobs depending on retry availability.

This gives the system resilience without requiring a full distributed queueing platform.

## Handlers
Each job points to a named handler in a registry. The registry maps a handler string to an async function. For example, handlers may print a message, compute Fibonacci values, sleep for a duration, or simulate a failure. This makes the scheduler flexible while keeping execution logic isolated and easy to test.

## API
The API exposes CRUD operations for tenants and jobs:
- GET /api/tenant/
- GET /api/tenant/{tenant_id}
- POST /api/tenant/
- PUT /api/tenant/{tenant_id}
- DELETE /api/tenant/{tenant_id}

- GET /api/job/
- GET /api/job/{job_id}
- POST /api/job/
- PUT /api/job/{job_id}
- DELETE /api/job/{job_id}

The API is intentionally straightforward and suitable for internal tools and integration with other services.

## Operational Notes
The system is designed for a single PostgreSQL-backed deployment with one or more worker processes. It is best suited for small-to-medium workloads and internal background processing use cases. The design is intentionally simple and maintainable, but it does not attempt to provide full distributed queue semantics or advanced orchestration.

## Risks and Future Improvements
The main risks are duplicate processing under extreme edge cases, local fairness being process-scoped, and loosely validated JSON payloads. Future work could include stricter payload validation, priority queues, dead-letter handling, richer monitoring, and more robust distributed scheduling.

## Summary
The DB Scheduler provides a practical way to schedule and execute background jobs using a database as the source of truth. Its combination of durable storage, async workers, lease-based execution, and retry logic makes it a solid foundation for lightweight job processing and tenant-aware automation.

- `GET /api/job/` - list jobs, optional tenant filter
- `GET /api/job/{job_id}` - fetch a job
- `POST /api/job/` - create a job
- `PUT /api/job/{job_id}` - update a pending job only
- `DELETE /api/job/{job_id}` - soft delete a job

### 9.3 Request Model example
```json
{
  "tenant_id": "9d0cc1ca-6d7e-4d57-8485-fd2d3a7d78e1",
  "name": "Send welcome email",
  "description": "Send onboarding email to the tenant",
  "scheduled_at": "2026-10-25T15:00:00Z",
  "handler": "print",
  "payload": {
    "message": "Welcome! Your job was scheduled successfully."
  }
}
```

## 10. Scheduler Design

### 10.1 Core scheduler class
The worker is implemented as `JobScheduler` and is responsible for:
- job claim selection
- execution orchestration
- lease heartbeat
- retry handling
- expired job recovery

### 10.2 Claiming strategy
The scheduler selects a single eligible job using a SQL `UPDATE ... RETURNING` pattern with `FOR UPDATE SKIP LOCKED`-style semantics. The worker ensures that:
- only jobs with `status = PENDING`
- scheduled_at <= now
- not soft deleted
- and valid tenant state are considered

It then updates the row to `RUNNING` and stores:
- `locked_by`
- `lease_expires_at`
- `started_at`

### 10.3 Lease design
A lease gives the scheduler a bounded execution window. While running, the job heartbeat renews the lease periodically. If the process dies or the heartbeat stops, the lease expires and the job can be recovered.

This pattern reduces duplicate processing in cases where a worker crashes in the middle of execution.

### 10.4 Execution strategy
Once a job is claimed, the worker creates two tasks:
- one task executes the handler
- one task performs heartbeat renewal until a stop signal is sent

The worker waits for whichever finishes first:
- if the heartbeat stops first, the handler is cancelled and the job is treated as lost or failed
- if the handler finishes first, the worker stops the heartbeat and commits final success state

### 10.5 Retry policy
The retry mechanism follows a simple exponential backoff model:

```python
retry_delay = 2 ** (retry_count + 1)
```

This means retry intervals grow quickly for transient failures, reducing overload on a flaky worker.

### 10.6 Recovery logic
Expired jobs are identified with:
- status = RUNNING
- lease_expires_at <= now

These jobs are reset to `PENDING` or `FAILED`, depending on whether more retries remain. This ensures jobs can recover after crashes or long-running processing delays.

## 11. Handler Model

The execution layer uses a handler registry to map a string job type to an async callable.

Example registries:
- `print`
- `fibonacci`
- `sleep`
- `sleep_random_failure`
- `error`

Each handler receives the job payload and returns either:
- a result payload to be stored in `result`
- or an exception if execution fails

### Handler contract
- input: `payload: dict`
- output: `dict` or any JSON-compatible structured result
- exceptions should surface to the scheduler
- unsupported handlers should raise `ValueError`

## 12. Concurrency Model

The scheduler supports a configurable maximum number of worker tasks:
- `MAX_WORKERS` controls concurrent job processing
- `POLL_INTERVAL` determines how frequently the scheduler checks for work

This is a simple concurrency pattern suitable for single-node or small multi-node deployments where a single DB remains the source of truth.

## 13. Data Integrity and Consistency

### Transaction boundaries
- Creating a job is transactional
- Claiming a job is transactional
- Lease renewal is transactional
- Completion updates are transactional
- Recovery uses transactional updates to requeue or mark failure

### Safety guarantees
- Only one worker should win a claim at a time because the claim update validates the current database state
- Jobs are not deleted permanently; soft deletion avoids accidental data loss
- The scheduler validates job state before completion to prevent overwriting newer work

## 14. Failure Handling

### Common failure modes
- handler throws exception
- worker crashes during execution
- DB connection issue during lease renewal
- lease expires while task still runs
- unsupported handler name

### Behavior
- transient handler exceptions trigger retry logic
- lease expiry triggers recovery
- unsupported handlers fail fast with a clear error
- DB errors are logged and surfaced appropriately

## 15. Security Considerations

- API should validate tenant creation and job payloads
- Prevent arbitrary handler names from bypassing the registry
- Use environment-based secrets for database credentials
- Treat payloads as untrusted input until validated
- Consider limiting the size of job payload fields and error messages

## 16. Operational Considerations

### Logging
- Log every job claim, completion, retry, and failure
- Include job_id, tenant_id, worker_id, and reason for failure

### Monitoring
Recommended operational metrics:
- jobs queued
- jobs processed per minute
- retries per job
- failed job count
- expired lease count
- average handler execution time

### Backups
- Since job state is stored in PostgreSQL, standard database backups are required for recovery

## 17. Deployment Model

The application is expected to run as:
- one API service
- one or more scheduler worker processes
- one PostgreSQL database

For production use, the following should be added:
- process supervisor or container management
- health checks
- metrics collection
- structured logging
- environment-specific configuration

## 18. Risks and Trade-offs

### Risk: duplicate processing under worker crash
Mitigation: lease renewal and expired-job recovery minimize this risk, though not perfect.

### Risk: local tenant fairness is process-scoped
The current implementation keeps a local in-memory cursor for fairness, which may not be globally fair across multiple workers. A database-backed strategy would be stronger in a distributed deployment.

### Risk: job payloads are too loosely typed
JSON payloads are flexible but weakly validated; stronger schema validation would improve safety and debuggability.

### Risk: single-node deployment assumptions
The current design is intentionally simple but is not a full distributed queueing system.

## 19. Future Enhancements

- priority-based scheduling
- exponential backoff with jitter
- dead-letter queue support
- richer job analytics and dashboards
- support for cron-like scheduling
- per-handler validation schemas
- event-driven execution triggers
- job cancellation and pause/resume behavior
- job execution history and audit timeline

## 20. Summary

The DB Scheduler is a small but useful background processing system built around a durable queue stored in PostgreSQL. Its key strengths are simple persistence, clear job lifecycle management, lease-based execution safety, and built-in retries. It is well suited for internal use cases and as a foundation for more advanced scheduling systems.

This design intentionally keeps the system simple and maintainable. It favors a single source of truth in the database, explicit scheduling logic, and pluggable handlers rather than a highly abstract distributed queue architecture.
