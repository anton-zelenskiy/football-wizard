"""
Tests for Mini App security implementation
"""

import hashlib
import hmac
import json
import time
from unittest.mock import Mock
import urllib.parse

from fastapi import HTTPException
import pytest

from app.api.security import (
    RateLimiter,
    SecurityConfig,
    TelegramWebAppData,
    check_rate_limit,
    get_client_ip,
    get_telegram_webapp_data,
    validate_request_origin,
    validate_telegram_webapp_data,
)


@pytest.fixture
def f_bot_token():
    """Fixture for bot token"""
    return "1234567890:ABCDEFGHIJKLMNOPQRSTUVWXYZ"


def create_mock_telegram_data(
    bot_token: str, user_id: int = 12345, username: str = "testuser"
) -> tuple[str, dict, int]:
    """Create mock Telegram WebApp init data for testing"""

    # Create user data
    user_data = {
        "id": user_id,
        "first_name": "Test",
        "last_name": "User",
        "username": username,
    }

    # Create auth data
    auth_date = int(time.time())

    # Create data string (without hash)
    data_items = {"user": json.dumps(user_data), "auth_date": str(auth_date)}

    # Create data check string (sorted by key)
    data_check_string = "\n".join(
        [f"{key}={value}" for key, value in sorted(data_items.items())]
    )

    # Create secret key
    secret_key = hmac.new(b"WebAppData", bot_token.encode(), hashlib.sha256).digest()

    # Calculate hash
    calculated_hash = hmac.new(
        secret_key, data_check_string.encode("utf-8"), hashlib.sha256
    ).hexdigest()

    # Create final init data
    init_data = f"user={urllib.parse.quote(json.dumps(user_data))}&auth_date={auth_date}&hash={calculated_hash}"

    return init_data, user_data, auth_date


def test_telegram_webapp_data_model() -> None:
    """Test TelegramWebAppData model"""
    data = TelegramWebAppData(
        user_id=12345,
        username="testuser",
        first_name="Test",
        last_name="User",
        auth_date=1640995200,
        hash="test_hash",
    )

    assert data.user_id == 12345
    assert data.username == "testuser"
    assert data.first_name == "Test"
    assert data.last_name == "User"
    assert data.auth_date == 1640995200
    assert data.hash == "test_hash"


def test_security_config():
    """Test SecurityConfig defaults"""
    config = SecurityConfig()

    assert config.RATE_LIMIT_REQUESTS == 100
    assert config.RATE_LIMIT_WINDOW == 3600
    assert config.REQUEST_TIMEOUT == 30


def test_validate_telegram_webapp_data_valid(f_bot_token):
    """Test valid Telegram WebApp data validation"""
    bot_token = f_bot_token
    init_data, user_data, auth_date = create_mock_telegram_data(bot_token)

    result = validate_telegram_webapp_data(init_data, bot_token)

    assert result.user_id == user_data["id"]
    assert result.username == user_data["username"]
    assert result.first_name == user_data["first_name"]
    assert result.last_name == user_data["last_name"]
    assert result.auth_date == auth_date


def test_validate_telegram_webapp_data_invalid_hash(f_bot_token):
    """Test invalid hash validation"""
    bot_token = f_bot_token
    invalid_data = "user=%7B%22id%22%3A12345%7D&auth_date=1640995200&hash=invalid_hash"

    with pytest.raises(HTTPException) as exc_info:
        validate_telegram_webapp_data(invalid_data, bot_token)

    assert exc_info.value.status_code == 401
    assert "Authentication failed" in str(exc_info.value.detail)


def test_validate_telegram_webapp_data_missing_hash(f_bot_token):
    """Test missing hash validation"""
    bot_token = f_bot_token
    data_without_hash = "user=%7B%22id%22%3A12345%7D&auth_date=1640995200"

    with pytest.raises(HTTPException) as exc_info:
        validate_telegram_webapp_data(data_without_hash, bot_token)

    assert exc_info.value.status_code == 401
    assert "Authentication failed" in str(exc_info.value.detail)


def test_validate_telegram_webapp_data_expired(f_bot_token):
    """Test expired auth data validation"""
    bot_token = f_bot_token

    # Create data with old timestamp (more than 24 hours ago)
    old_timestamp = int(time.time()) - 86401  # 24 hours + 1 second
    user_data = {"id": 12345, "first_name": "Test"}

    data_items = {"user": json.dumps(user_data), "auth_date": str(old_timestamp)}

    data_check_string = "\n".join(
        [f"{key}={value}" for key, value in sorted(data_items.items())]
    )

    secret_key = hmac.new(bot_token.encode(), b"WebAppData", hashlib.sha256).digest()

    calculated_hash = hmac.new(
        secret_key, data_check_string.encode("utf-8"), hashlib.sha256
    ).hexdigest()

    expired_data = f"user={urllib.parse.quote(json.dumps(user_data))}&auth_date={old_timestamp}&hash={calculated_hash}"

    with pytest.raises(HTTPException) as exc_info:
        validate_telegram_webapp_data(expired_data, bot_token)

    assert exc_info.value.status_code == 401
    assert "Authentication failed" in str(exc_info.value.detail)


def test_validate_telegram_webapp_data_invalid_format(f_bot_token):
    """Test invalid data format"""
    bot_token = f_bot_token
    invalid_format = "not_a_valid_format"

    with pytest.raises(HTTPException) as exc_info:
        validate_telegram_webapp_data(invalid_format, bot_token)

    assert exc_info.value.status_code == 401
    assert "Authentication failed" in str(exc_info.value.detail)


def test_get_telegram_webapp_data_missing_header():
    """Test missing Authorization header"""
    request = Mock()
    request.headers = {}

    with pytest.raises(HTTPException) as exc_info:
        get_telegram_webapp_data(request)

    assert exc_info.value.status_code == 401
    assert "Missing or invalid Authorization header" in str(exc_info.value.detail)


def test_get_telegram_webapp_data_invalid_header():
    """Test invalid Authorization header format"""
    request = Mock()
    request.headers = {"Authorization": "InvalidFormat token"}

    with pytest.raises(HTTPException) as exc_info:
        get_telegram_webapp_data(request)

    assert exc_info.value.status_code == 401
    assert "Missing or invalid Authorization header" in str(exc_info.value.detail)


def test_rate_limiter_allows_requests():
    """Test rate limiter allows requests within limits"""
    limiter = RateLimiter()
    user_id = 12345

    # First few requests should be allowed
    for _ in range(5):
        assert limiter.is_allowed(user_id, max_requests=10, window=60) is True


def test_rate_limiter_blocks_excessive_requests():
    """Test rate limiter blocks excessive requests"""
    limiter = RateLimiter()
    user_id = 12345

    # Exceed the limit
    for _ in range(3):  # 3 requests
        limiter.is_allowed(user_id, max_requests=2, window=60)

    # Next request should be blocked
    assert limiter.is_allowed(user_id, max_requests=2, window=60) is False


def test_rate_limiter_cleans_old_requests():
    """Test rate limiter cleans old requests"""
    limiter = RateLimiter()
    user_id = 12345

    # Add some old requests
    limiter.requests[user_id] = [time.time() - 100, time.time() - 50]

    # Should allow new request (old ones are cleaned)
    assert limiter.is_allowed(user_id, max_requests=2, window=60) is True


def test_check_rate_limit_allows_normal_usage():
    """Test check_rate_limit allows normal usage"""
    # This should not raise an exception
    check_rate_limit(12345)


def test_check_rate_limit_blocks_excessive_usage():
    """Test check_rate_limit blocks excessive usage"""
    user_id = 12345

    # Exceed the rate limit
    from app.api.security import rate_limiter

    for _ in range(101):  # Exceed default limit of 100
        rate_limiter.is_allowed(user_id, max_requests=100, window=3600)

    with pytest.raises(HTTPException) as exc_info:
        check_rate_limit(user_id)

    assert exc_info.value.status_code == 429
    assert "Rate limit exceeded" in str(exc_info.value.detail)


def test_validate_request_origin_telegram_user_agent():
    """Test validate_request_origin with Telegram User-Agent"""
    request = Mock()
    request.headers = {"User-Agent": "TelegramBot (like TwitterBot)"}

    # Should not raise exception
    validate_request_origin(request)


def test_validate_request_origin_webapp_user_agent():
    """Test validate_request_origin with WebApp User-Agent"""
    request = Mock()
    request.headers = {"User-Agent": "TelegramWebApp/1.0"}

    # Should not raise exception
    validate_request_origin(request)


def test_validate_request_origin_suspicious_user_agent():
    """Test validate_request_origin with suspicious User-Agent"""
    request = Mock()
    request.headers = {"User-Agent": "curl/7.68.0"}

    # Should not raise exception (just logs warning)
    validate_request_origin(request)


def test_get_client_ip_direct_connection():
    """Test get_client_ip with direct connection"""
    request = Mock()
    request.headers = {}
    request.client = Mock()
    request.client.host = "192.168.1.100"

    ip = get_client_ip(request)
    assert ip == "192.168.1.100"


def test_get_client_ip_forwarded_for():
    """Test get_client_ip with X-Forwarded-For header"""
    request = Mock()
    request.headers = {"X-Forwarded-For": "203.0.113.195, 70.41.3.18, 150.172.238.178"}
    request.client = Mock()
    request.client.host = "192.168.1.100"

    ip = get_client_ip(request)
    assert ip == "203.0.113.195"


def test_get_client_ip_real_ip():
    """Test get_client_ip with X-Real-IP header"""
    request = Mock()
    request.headers = {"X-Real-IP": "203.0.113.195"}
    request.client = Mock()
    request.client.host = "192.168.1.100"

    ip = get_client_ip(request)
    assert ip == "203.0.113.195"


def test_get_client_ip_no_client():
    """Test get_client_ip with no client"""
    request = Mock()
    request.headers = {}
    request.client = None

    ip = get_client_ip(request)
    assert ip == "unknown"
