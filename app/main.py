"""
Main FastAPI application for Football Betting Analysis
"""

from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.legacy_routes import router as legacy_router
from app.api.root import router as root_router
from app.api.routes import router as api_router
from app.betting_rules import BettingRulesEngine
from app.db.models import create_tables
from app.db.storage import FootballDataStorage
from app.scraper.livesport_scraper import LivesportScraper
from app.settings import settings
from app.telegram.bot import get_bot

logger = structlog.get_logger()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager"""
    # Startup
    logger.info('Starting Football Betting Analysis App')

    # Create database tables
    create_tables()
    logger.info('Database tables created')

    # Initialize components
    app.state.scraper = LivesportScraper()
    app.state.storage = FootballDataStorage()
    app.state.rules_engine = BettingRulesEngine()
    app.state.bot = get_bot()

    logger.info('App startup completed')

    yield

    # Shutdown
    logger.info('Shutting down Football Betting Analysis App')


app = FastAPI(
    title=settings.app_name,
    description='Football Betting Analysis API',
    version='1.0.0',
    lifespan=lifespan,
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=['*'],
    allow_credentials=True,
    allow_methods=['*'],
    allow_headers=['*'],
)

# Include routers
app.include_router(api_router, prefix='/football')
app.include_router(legacy_router, prefix='/football')
app.include_router(root_router, prefix='/football')
