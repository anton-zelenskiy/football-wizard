#!/usr/bin/env python3
"""
Run ARQ Worker for Football Betting Analysis
"""

import asyncio

import structlog
from app.tasks.league_tasks import WorkerSettings
from arq import run_worker

logger = structlog.get_logger()


async def main():
    """Run the ARQ worker"""
    logger.info("Starting ARQ worker")

    # Run the worker
    await run_worker(WorkerSettings)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Worker stopped by user")
    except Exception as e:
        logger.error(f"Worker error: {e}")
        raise 
