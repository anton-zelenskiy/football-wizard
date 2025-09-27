from app.bot.core import dp
from app.bot.handlers import router


def register_handlers():
    """
    Register all handlers to the dispatcher
    """
    dp.include_router(router)
