from datetime import datetime

from fastapi import APIRouter
import structlog

from app.settings import settings


logger = structlog.get_logger()
router = APIRouter()


@router.get('/')
async def index():
    """Root endpoint"""
    return {
        'app': settings.app_name,
        'version': '1.0.0',
        'status': 'running',
        'timestamp': datetime.now().isoformat(),
    }


@router.get('/health')
async def health_check():
    """Health check endpoint"""
    return {
        'status': 'healthy',
        'timestamp': datetime.now().isoformat(),
        'database': 'connected',
        'redis': 'connected',
    }
