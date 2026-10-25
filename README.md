# Database backed Job Scheduler

A multi-tenan job Scheduler application built using FastAPI, Postgres, FastAPI. 

Each tenant can create a job and schedule it to run at a specific time in future

## Features

- Multithreaded job execution in background.
- Fault tolerance with exponential backoff
- Multi-tenant fairness with round robin
- No duplicate execution

## API Layer

- The API layer has two components
    - Tenant
    - Job

- Tenant layer handles tenant CRUD operation and data models
- Job layer handles the job schema, models and controllers

<img width="679" height="514" alt="image" src="https://github.com/user-attachments/assets/3549b06a-3a41-4ec7-a7b8-c1d73c1e86c4" />


## Worker Layer

- The worker layer is used to execute a job scheduled for a particular time.
- It works by:
    - Pooling pending jobs
    - Execute the job handler on worker thread
    - Tracks status and retry with exponential back-off maximum three times before marking the job as `FAILED`
    - Save the status and the result to DB

## Job Handlers

The job scheduler currently supports 5 handlers

| Handler | Description | Example Payload |
| --- | --- | --- |
| `print` | Prints a message | `{"message": "hello world"}` |
| `fibonacci` | Calculates a Fibonacci sequence | `{"n": 10}` |
| `sleep` | Waits for a duration | `{"seconds": 5}` |
| `sleep_random_failure` | Randomly fails to simulate flaky behavior | `{"seconds": 3}` |
| `error` | Raises an exception for testing | `{"exception": "Test Exception"}` |

## Prerequisites

- Python 3.14 or newer
- PostgreSQL running locally or in a remote environment
- `uv` installed

## Configuration

- Create a .env file in the project root from `.env.example` with the following configuration:

```
DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/db_scheduler
```

Optional env variables are defined in `app/core/settings.py`:

- `MAX_RETRIES` - To set the maximum retries
- `MAX_WORKERS` - To configure the number of worker threads a process will handle
- `POLL_INTERVAL` - Configures how often the job can be polled from db in seconds
- `JOB_LEASE_DURATION` - Configures the number of seconds a worker is allowed to hold a job before it expires

The default values are: 
```
MAX_RETRIES = 3
MAX_WORKERS = 4
POLL_INTERVAL = 1
JOB_LEASE_DURATION = 60
```

## Project Setup

### Installation

```
uv sync
```

### Database Setup

```
alembic upgrade head
```

### Running the API

```
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

Swagger UI is available at: 

```
http://localhost:8000/docs
```

### Running the Worker

To start the scheduler worker:

```
uv run python -m app.worker
```

This process continuously polls for pending jobs and executes them according to the configured concurrency and lease settings.

### Seed data

Populate the database with sample tenants and jobs:

```
uv run python -m scripts.seed_jobs
```

This creates a few tenants (`TENANT_COUNT`) and randomly schedules jobs (`TOTAL_JOBS`) configured in `seed_jobs.py` against the available handlers.


## Scheduler Behavior

The scheduler does the following:

- Finds pending jobs whose `scheduled_at` is less than or equal to the current time
- Claims the next eligible job using a lease-based update pattern
- Marks the job as `RUNNING`
- Starts an async task to execute the handler
- Sends periodic heartbeat updates to maintain the active lease
- If the task succeeds, stores the result and marks the job `COMPLETED`
- If it fails, retries the job up to the configured maximum
- If the lease expires before completion, it attempts renewal or recovery
