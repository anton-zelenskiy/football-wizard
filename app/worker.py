#!/usr/bin/env python3
"""
ARQ Worker for Football Betting Analysis
Runs background tasks for league scraping, data refresh, and betting analysis
"""

import structlog
from arq.connections import RedisSettings
from arq.cron import cron

from app.settings import settings
from app.tasks import (
    daily_scheduled_analysis,
    live_matches_analysis,
    refresh_league_data,
    refresh_live_matches,
)

logger = structlog.get_logger()


async def heartbeat(ctx):
    """Simple heartbeat function to test if worker is working"""
    logger.info('💓 Heartbeat: Worker is alive and working!')

    await ctx['redis'].enqueue_job(
        'heartbeat',
        _defer_by=10,
    )

    return 'Worker heartbeat successful'


async def enqueue_live_matches_analysis(ctx):
    """Enqueue live matches analysis and schedule next run"""
    try:
        logger.info('🔍 Running live matches analysis...')
        await live_matches_analysis(ctx)
        logger.info('✅ Live matches analysis completed')

        # Schedule next run in 3 minutes
        await ctx['redis'].enqueue_job(
            'enqueue_live_matches_analysis',
            _defer_by=180,  # 180 seconds for testing
        )
        logger.info('📅 Scheduled next live matches analysis in 180 seconds')
    except Exception as e:
        logger.error(f'❌ Error in live matches analysis: {e}')
        # Still schedule next run even if this one failed
        await ctx['redis'].enqueue_job('enqueue_live_matches_analysis', _defer_by=180)


async def enqueue_refresh_live_matches(ctx):
    """Enqueue live matches refresh and schedule next run"""
    try:
        logger.info('🔄 Running live matches refresh...')
        await refresh_live_matches(ctx)
        logger.info('✅ Live matches refresh completed')

        # Schedule next run in 5 minutes
        await ctx['redis'].enqueue_job('enqueue_refresh_live_matches', _defer_by=300)
        logger.info('📅 Scheduled next live matches refresh in 5 minutes')
    except Exception as e:
        logger.error(f'❌ Error in live matches refresh: {e}')
        # Still schedule next run even if this one failed
        await ctx['redis'].enqueue_job('enqueue_refresh_live_matches', _defer_by=300)


async def startup(ctx):
    """Startup function to enqueue recurring jobs"""
    logger.info('🚀 Starting up ARQ worker and enqueuing recurring jobs')

    try:
        # Enqueue heartbeat for testing
        await ctx['redis'].enqueue_job(
            'heartbeat',
            _defer_by=10,  # Start in 10 seconds
        )
        logger.info('✅ Heartbeat job enqueued (10 seconds)')

        # Enqueue live matches analysis to run every 3 minutes
        await ctx['redis'].enqueue_job(
            'enqueue_live_matches_analysis',
            _defer_by=180,  # 3 minutes
        )
        logger.info('✅ Live matches analysis job enqueued (3 minutes)')

        # Enqueue live matches refresh to run every 5 minutes
        await ctx['redis'].enqueue_job(
            'enqueue_refresh_live_matches',
            _defer_by=300,  # 5 minutes
        )
        logger.info('✅ Live matches refresh job enqueued (5 minutes)')

        logger.info('🎉 All recurring jobs enqueued successfully!')
    except Exception as e:
        logger.error(f'❌ Error enqueuing recurring jobs: {e}')
        # Don't raise the exception to allow worker to continue


# ARQ worker configuration
class WorkerSettings:
    functions = [
        # Betting analysis tasks
        daily_scheduled_analysis,
        live_matches_analysis,
        refresh_league_data,
        refresh_live_matches,
        # Test functions
        heartbeat,
        # Recurring job enqueuers
        enqueue_live_matches_analysis,
        enqueue_refresh_live_matches,
    ]
    redis_settings = RedisSettings.from_dsn(settings.redis_url)
    on_startup = startup

    # Schedule tasks using cron (only for daily/hourly tasks)
    cron_jobs = [
        # Daily scheduled analysis at 9 AM UTC
        cron(daily_scheduled_analysis, hour=9, minute=0),
        # League data refresh daily at 10 AM UTC
        cron(refresh_league_data, hour=10, minute=0),
    ]
