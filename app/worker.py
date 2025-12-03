#!/usr/bin/env python3
"""
ARQ Worker for Football Betting Analysis
Runs background tasks for league scraping, data refresh, and betting analysis
"""

from typing import Any

from arq.connections import RedisSettings
from arq.cron import cron
import structlog

from app.settings import settings
from app.tasks import (
    daily_scheduled_analysis,
    live_matches_analysis,
    refresh_league_data,
)


logger = structlog.get_logger()


async def heartbeat(ctx: dict[str, Any]) -> str:
    """Simple heartbeat function to test if worker is working"""
    logger.info('💓 Heartbeat: Worker is alive and working!')
    return 'Worker heartbeat successful'


# ARQ worker configuration
class WorkerSettings:
    functions = [
        # Betting analysis tasks
        daily_scheduled_analysis,
        live_matches_analysis,
        refresh_league_data,
        # Test functions
        heartbeat,
    ]
    redis_settings = RedisSettings.from_dsn(settings.redis_url)

    # Schedule tasks using cron with unique job IDs to prevent duplicates
    cron_jobs = [
        # Daily scheduled analysis at 9 AM UTC
        cron(
            daily_scheduled_analysis,
            hour=9,
            minute=0,
            unique=True,
            job_id='daily_scheduled_analysis',
        ),
        # League data refresh daily at 10 AM UTC
        cron(
            refresh_league_data,
            hour=10,
            minute=0,
            unique=True,
            job_id='refresh_league_data',
        ),
        # Live matches analysis every 3 minutes (includes scraping and analysis)
        # cron(
        #     live_matches_analysis,
        #     minute=list(range(0, 60, 3)),
        #     unique=True,
        #     job_id='live_matches_analysis',
        # ),
        # Heartbeat every minute for testing
        cron(heartbeat, minute=list(range(60)), unique=True, job_id='heartbeat'),
    ]
