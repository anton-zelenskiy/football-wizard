import os

from aiogram import Bot, Dispatcher
from aiogram.client.session.aiohttp import AiohttpSession
from pydantic import BaseModel

from app.settings import settings


# Get Telegram bot token from settings
TELEGRAM_BOT_TOKEN = settings.telegram_bot_token

if not TELEGRAM_BOT_TOKEN:
    raise ValueError('TELEGRAM_BOT_TOKEN environment variable is not set')

# Generate a random secret token for webhook validation
webhook_secret_token = os.getenv('TELEGRAM_WEBHOOK_SECRET', '')

# Create a custom AioHttp session
session = AiohttpSession()

# Initialize bot and dispatcher
bot = Bot(token=TELEGRAM_BOT_TOKEN, session=session)
dp = Dispatcher()


class WebhookConfig(BaseModel):
    """Webhook configuration model"""

    url: str
    drop_pending_updates: bool = True
    secret_token: str | None = None


def get_webhook_url() -> str:
    return f'{settings.base_host}/football/api/v1/bot/webhook'
