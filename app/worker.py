#!/usr/bin/env python3
"""
ARQ Worker for Football Betting Analysis
Runs background tasks for league scraping and data refresh
"""

import asyncio

import structlog

from app.tasks.league_tasks import schedule_periodic_tasks

logger = structlog.get_logger()


async def main() -> None:
    """Main worker function"""
    logger.info("Starting ARQ worker for Football Betting Analysis")

    # Schedule periodic tasks
    await schedule_periodic_tasks()

    # Keep the worker running
    while True:
        await asyncio.sleep(60)  # Check every minute


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Worker stopped by user")
    except Exception as e:
        logger.error(f"Worker error: {e}")
        raise 
