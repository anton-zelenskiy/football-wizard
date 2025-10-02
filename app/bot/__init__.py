from app.bot.core import WebhookConfig, bot, dp, get_webhook_url, webhook_secret_token
from app.bot.register import register_handlers


# Register handlers when the bot module is imported
register_handlers()

__all__ = [
    'bot',
    'dp',
    'webhook_secret_token',
    'get_webhook_url',
    'WebhookConfig',
    'register_handlers',
]
