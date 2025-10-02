"""
Security utilities for Mini App API authentication and validation
"""

import hashlib
import hmac
import json
import time
import urllib.parse

from fastapi import HTTPException, Request
from pydantic import BaseModel
import structlog


logger = structlog.get_logger()


class TelegramWebAppData(BaseModel):
    """Telegram WebApp authentication data"""

    user_id: int
    username: str | None = None
    first_name: str | None = None
    last_name: str | None = None
    auth_date: int
    hash: str


class SecurityConfig:
    """Security configuration for Mini App"""

    # Telegram Bot Token (used for WebApp validation)
    BOT_TOKEN: str = ''

    # Rate limiting
    RATE_LIMIT_REQUESTS: int = 100  # requests per window
    RATE_LIMIT_WINDOW: int = 3600  # 1 hour in seconds

    # Request timeout
    REQUEST_TIMEOUT: int = 30  # seconds


def validate_telegram_webapp_data(init_data: str, bot_token: str) -> TelegramWebAppData:
    """
    Validate Telegram WebApp init data to ensure request is from Telegram

    Args:
        init_data: Raw init data from Telegram WebApp
        bot_token: Your bot token for validation

    Returns:
        Parsed and validated WebApp data

    Raises:
        HTTPException: If validation fails
    """
    try:
        # Parse init data (URL decode first)
        parsed_data = {}
        for item in init_data.split('&'):
            if '=' in item:
                key, value = item.split('=', 1)
                # URL decode the value
                parsed_data[key] = urllib.parse.unquote(value)

        # Extract hash
        received_hash = parsed_data.pop('hash', '')
        if not received_hash:
            raise HTTPException(status_code=401, detail='Missing hash in init data')

        # Create data string for validation (sorted by key, excluding hash)
        # Telegram sends additional fields like chat_instance, chat_type, signature
        data_check_string = '\n'.join(
            [
                f'{key}={value}'
                for key, value in sorted(parsed_data.items())
                if key != 'hash'
            ]
        )

        # Create secret key using Telegram's method
        # Secret key = HMAC-SHA256("WebAppData", bot_token)
        secret_key = hmac.new(
            b'WebAppData', bot_token.encode(), hashlib.sha256
        ).digest()

        # Calculate hash
        calculated_hash = hmac.new(
            secret_key, data_check_string.encode('utf-8'), hashlib.sha256
        ).hexdigest()

        logger.info(f'Data check string: {data_check_string}')
        logger.info(f'Received hash: {received_hash}')
        logger.info(f'Calculated hash: {calculated_hash}')
        logger.info(f'Bot token (first 10 chars): {bot_token[:10]}...')

        # Verify hash
        if not hmac.compare_digest(received_hash, calculated_hash):
            raise HTTPException(status_code=401, detail='Invalid hash')

        # Check auth_date (should be within last 24 hours)
        auth_date = int(parsed_data.get('auth_date', 0))
        current_time = int(time.time())
        if current_time - auth_date > 86400:  # 24 hours
            raise HTTPException(status_code=401, detail='Auth data expired')

        # Parse user data
        user_data = {}
        if 'user' in parsed_data:
            try:
                user_data = json.loads(parsed_data['user'])
            except json.JSONDecodeError:
                logger.warning('Failed to parse user data as JSON')
                user_data = {}

        return TelegramWebAppData(
            user_id=int(user_data.get('id', 0)),
            username=user_data.get('username'),
            first_name=user_data.get('first_name'),
            last_name=user_data.get('last_name'),
            auth_date=auth_date,
            hash=received_hash,
        )

    except (ValueError, KeyError, json.JSONDecodeError) as e:
        logger.error(f'Error parsing WebApp data: {e}')
        raise HTTPException(status_code=400, detail='Invalid init data format') from e
    except Exception as e:
        logger.error(f'WebApp validation error: {e}')
        raise HTTPException(status_code=401, detail='Authentication failed') from e


def get_telegram_webapp_data_optional(request: Request) -> TelegramWebAppData | None:
    """
    Extract and validate Telegram WebApp data from request headers (optional for debug mode)

    Args:
        request: FastAPI request object

    Returns:
        Validated WebApp data or None if debug mode and no auth data
    """
    # Check if debug mode is enabled
    from app.settings import settings

    debug_mode = settings.debug

    # Get init data from Authorization header
    auth_header = request.headers.get('Authorization', '')
    if not auth_header.startswith('Bearer '):
        if debug_mode:
            logger.info(
                'Debug mode: No authentication data provided, skipping validation'
            )
            return None
        raise HTTPException(
            status_code=401, detail='Missing or invalid Authorization header'
        )

    init_data = auth_header[7:]  # Remove 'Bearer ' prefix

    # Get bot token from environment or settings
    from app.settings import settings

    bot_token = settings.telegram_bot_token

    if not bot_token:
        if debug_mode:
            logger.info('Debug mode: No bot token configured, skipping validation')
            return None
        raise HTTPException(status_code=500, detail='Bot token not configured')

    return validate_telegram_webapp_data(init_data, bot_token)


def get_telegram_webapp_data(request: Request) -> TelegramWebAppData:
    """
    Extract and validate Telegram WebApp data from request headers

    Args:
        request: FastAPI request object

    Returns:
        Validated WebApp data

    Raises:
        HTTPException: If validation fails
    """
    # Get init data from Authorization header
    auth_header = request.headers.get('Authorization', '')
    if not auth_header.startswith('Bearer '):
        raise HTTPException(
            status_code=401, detail='Missing or invalid Authorization header'
        )

    init_data = auth_header[7:]  # Remove 'Bearer ' prefix

    # Get bot token from environment or settings
    from app.settings import settings

    bot_token = settings.telegram_bot_token

    if not bot_token:
        raise HTTPException(status_code=500, detail='Bot token not configured')

    return validate_telegram_webapp_data(init_data, bot_token)


class RateLimiter:
    """Simple in-memory rate limiter"""

    def __init__(self) -> None:
        self.requests = {}  # {user_id: [timestamps]}

    def is_allowed(
        self, user_id: int, max_requests: int = 100, window: int = 3600
    ) -> bool:
        """Check if user is within rate limits"""
        current_time = time.time()

        # Clean old requests
        if user_id in self.requests:
            self.requests[user_id] = [
                timestamp
                for timestamp in self.requests[user_id]
                if current_time - timestamp < window
            ]
        else:
            self.requests[user_id] = []

        # Check if under limit
        if len(self.requests[user_id]) >= max_requests:
            return False

        # Add current request
        self.requests[user_id].append(current_time)
        return True


# Global rate limiter instance
rate_limiter = RateLimiter()


def check_rate_limit(user_id: int) -> None:
    """Check if user is within rate limits"""
    if not rate_limiter.is_allowed(
        user_id, SecurityConfig.RATE_LIMIT_REQUESTS, SecurityConfig.RATE_LIMIT_WINDOW
    ):
        raise HTTPException(
            status_code=429, detail='Rate limit exceeded. Please try again later.'
        )


def validate_request_origin(request: Request) -> None:
    """Validate that request comes from Telegram WebApp"""
    # Check User-Agent
    user_agent = request.headers.get('User-Agent', '').lower()
    if 'telegram' not in user_agent and 'webapp' not in user_agent:
        logger.warning(f'Suspicious User-Agent: {user_agent}')
        # Don't block, but log for monitoring

    # Check Referer (optional additional check)
    referer = request.headers.get('Referer', '')
    if referer and 'telegram' not in referer.lower():
        logger.warning(f'Suspicious Referer: {referer}')
        # Don't block, but log for monitoring


def get_client_ip(request: Request) -> str:
    """Get client IP address"""
    # Check for forwarded headers (common in production)
    forwarded_for = request.headers.get('X-Forwarded-For')
    if forwarded_for:
        return forwarded_for.split(',')[0].strip()

    real_ip = request.headers.get('X-Real-IP')
    if real_ip:
        return real_ip

    # Fallback to direct connection
    return request.client.host if request.client else 'unknown'
