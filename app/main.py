"""
Main FastAPI application for Football Betting Analysis
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import structlog

from app.admin.init_admin import init_admin
from app.admin.routes import router as admin_router
from app.admin.starlette_admin_config import create_admin_app
from app.api.bot_routes import router as bot_router
from app.api.middleware import MiniAppSecurityMiddleware, SecurityMiddleware
from app.api.mini_app_routes import router as mini_app_router
from app.api.root import router as root_router
from app.bet_rules.rule_engine import BettingRulesEngine
from app.db.sqlalchemy_models import create_tables
from app.settings import settings


logger = structlog.get_logger()


@asynccontextmanager
async def lifespan(app: FastAPI) -> None:
    """Application lifespan manager"""
    # Startup
    logger.info('Starting Football Betting Analysis App')

    # Create database tables
    create_tables()
    logger.info('Database tables created')

    # Initialize admin system
    init_admin()
    logger.info('Admin system initialized')

    # Initialize components
    app.state.rules_engine = BettingRulesEngine()

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

# Add security middleware
app.add_middleware(SecurityMiddleware, max_requests_per_minute=60)
app.add_middleware(MiniAppSecurityMiddleware)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=['*'],
    allow_credentials=True,
    allow_methods=['*'],
    allow_headers=['*'],
)

# Include routers
app.include_router(root_router, prefix='/football')
app.include_router(bot_router, prefix='/football/api/v1/bot')
app.include_router(mini_app_router, prefix='/football/api/v1/mini-app')
app.include_router(admin_router, prefix='/football/api/v1/admin')

# Mount starlette-admin
admin_app = create_admin_app()
admin_app.mount_to(app)
