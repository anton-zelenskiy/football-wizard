from typing import Any

from aiogram.webhook.aiohttp_server import SimpleRequestHandler
from fastapi import APIRouter, HTTPException, Request, Response, status

from app.bot import bot, dp, get_webhook_url, webhook_secret_token


router = APIRouter()


@router.post('/webhook', include_in_schema=False)
async def webhook_handler(request: Request):
    """
    Handle Telegram webhook requests
    """
    try:
        # Get the update from the request body
        update = await request.json()

        # Create a SimpleRequestHandler instance
        webhook_request_handler = SimpleRequestHandler(
            dispatcher=dp,
            bot=bot,
            secret_token=webhook_secret_token,
        )

        # Process the update directly
        await webhook_request_handler.dispatcher.feed_webhook_update(
            bot=bot, update=update
        )
        return Response(status_code=status.HTTP_200_OK)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f'Failed to process webhook update: {str(e)}',
        )


@router.get(
    '/set-webhook', status_code=status.HTTP_200_OK, response_model=dict[str, Any]
)
async def set_webhook() -> Any:
    """
    Set a webhook for the Telegram bot.

    Args:
        config: Webhook configuration (URL, settings)

    Returns:
        Success response
    """
    webhook_url = get_webhook_url()

    try:
        # Set webhook
        webhook_info = await bot.set_webhook(
            url=webhook_url,
            drop_pending_updates=True,
            secret_token=webhook_secret_token if webhook_secret_token else None,
        )

        # Get current webhook info
        webhook_info = await bot.get_webhook_info()

        return {
            'success': True,
            'webhook_url': webhook_url,
            'webhook_info': webhook_info.model_dump(),
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f'Failed to set webhook: {str(e)}',
        )


@router.post(
    '/delete-webhook', status_code=status.HTTP_200_OK, response_model=dict[str, Any]
)
async def delete_webhook(drop_pending: bool = True) -> Any:
    """
    Delete the Telegram bot webhook.

    Args:
        drop_pending: Whether to drop pending updates

    Returns:
        Success response
    """
    try:
        # Delete webhook
        await bot.delete_webhook(drop_pending_updates=drop_pending)

        # Get current webhook info
        webhook_info = await bot.get_webhook_info()

        return {
            'success': True,
            'webhook_deleted': True,
            'webhook_info': webhook_info.model_dump(),
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f'Failed to delete webhook: {str(e)}',
        )


@router.get(
    '/webhook-info', status_code=status.HTTP_200_OK, response_model=dict[str, Any]
)
async def get_webhook_info() -> Any:
    """
    Get current webhook information.

    Returns:
        Webhook information
    """
    try:
        # Get current webhook info
        webhook_info = await bot.get_webhook_info()

        return {
            'success': True,
            'webhook_info': webhook_info.model_dump(),
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f'Failed to get webhook info: {str(e)}',
        )
