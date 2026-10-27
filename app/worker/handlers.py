import os
import logging
import asyncio
from typing import Any
import random

logger = logging.getLogger(__name__)

async def print_handler(payload: dict[str, Any]) -> dict[str, Any]:
    print(payload.get("message"))
    return {"message": payload.get("message")}


async def fibonacci_handler(payload: dict[str, Any]):
    n = payload.get("n")

    if n is None:
        raise ValueError("n is required")
    
    if n <= 0:
        return []
    elif n == 1:
        return [0]

    res = [0, 1]
    for _ in range(2, n):
        res.append(res[-1] + res[-2])

    return res


async def sleep_handler(payload: dict[str, Any]) -> dict[str, Any]:
    seconds = float(payload.get("seconds", 1))
    if not 0 <= seconds <= 60:
        raise ValueError("seconds must be between 0 and 60")

    await asyncio.sleep(seconds)
    return {"slept_seconds": seconds}

async def sleep_random_failure_handler(payload: dict[str, Any]) -> dict[str, Any]:
    val = random.randint(0, 1)

    if val == 1:
        raise Exception("Exception: Random value is 1")
    
    seconds = float(payload.get("seconds", 1))
    if not 0 <= seconds <= 60:
        raise ValueError("seconds must be between 0 and 60")

    await asyncio.sleep(seconds)
    return {"slept_seconds": seconds}

async def error_handler(payload: dict[str, Any]) -> dict[str, Any]:
    raise Exception(f"Exception Handler: {payload.get("exception", "Exception")}")



HANDLERS = {
    "print": print_handler,
    "fibonacci": fibonacci_handler,
    "sleep": sleep_handler,
    "sleep_random_failure": sleep_random_failure_handler,
    "error": error_handler
}


async def execute_handler(
    tenant_id: str,
    job_id: str,
    job_type: str,
    payload: dict[str, Any],
) -> dict[str, Any]:
    logger.info(f"[PID {os.getpid()}] Executing Handler for Tenant: {tenant_id} with job_id: {job_id}: {job_type}")
    handler = HANDLERS.get(job_type)

    if handler is None:
        raise ValueError(f"Unsupported job type: {job_type}")

    return await handler(payload)
