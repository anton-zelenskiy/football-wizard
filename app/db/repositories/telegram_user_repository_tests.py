import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.db.repositories.telegram_user_repository import TelegramUserRepository
from app.db.sqlalchemy_models import Base


@pytest_asyncio.fixture
async def db_session():
    """Create a database session for testing."""
    # Create in-memory SQLite database for testing
    engine = create_async_engine('sqlite+aiosqlite:///:memory:', echo=False)

    # Create tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # Create session
    session_local = async_sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )
    session = session_local()

    try:
        yield session
    finally:
        await session.close()
        await engine.dispose()


@pytest.mark.asyncio
async def test_create_new_user(db_session):
    """Test creating a new user"""
    repo = TelegramUserRepository(db_session)
    user, created = await repo.get_or_create(
        telegram_id=12345, username='testuser', first_name='Test', last_name='User'
    )

    assert created is True
    assert user.telegram_id == 12345
    assert user.username == 'testuser'
    assert user.first_name == 'Test'
    assert user.last_name == 'User'
    assert user.is_active is True
    assert user.daily_notifications is True
    assert user.live_notifications is True


@pytest.mark.asyncio
async def test_get_existing_user(db_session):
    """Test getting an existing user"""
    repo = TelegramUserRepository(db_session)

    # Create user first
    await repo.get_or_create(
        telegram_id=12345, username='testuser', first_name='Test', last_name='User'
    )

    # Get the same user
    user, created = await repo.get_or_create(
        telegram_id=12345,
        username='updateduser',
        first_name='Updated',
        last_name='User',
    )

    assert created is False
    assert user.telegram_id == 12345
    assert user.username == 'updateduser'  # Should be updated
    assert user.first_name == 'Updated'  # Should be updated


@pytest.mark.asyncio
async def test_get_by_telegram_id(db_session):
    """Test getting user by telegram_id"""
    repo = TelegramUserRepository(db_session)

    # Create user
    await repo.get_or_create(telegram_id=12345, username='testuser')

    # Get user
    user = await repo.get_by_telegram_id(12345)
    assert user is not None
    assert user.telegram_id == 12345
    assert user.username == 'testuser'

    # Get non-existent user
    user = await repo.get_by_telegram_id(99999)
    assert user is None


@pytest.mark.asyncio
async def test_update_notifications(db_session):
    """Test updating user notification settings"""
    repo = TelegramUserRepository(db_session)

    # Create user
    user, _ = await repo.get_or_create(telegram_id=12345)

    # Update notifications
    updated_user = await repo.update_notifications(
        telegram_id=12345,
        daily_notifications=False,
        live_notifications=False,
        is_active=False,
    )

    assert updated_user is not None
    assert updated_user.daily_notifications is False
    assert updated_user.live_notifications is False
    assert updated_user.is_active is False


@pytest.mark.asyncio
async def test_toggle_daily_notifications(db_session):
    """Test toggling daily notifications"""
    repo = TelegramUserRepository(db_session)

    # Create user
    user, _ = await repo.get_or_create(telegram_id=12345)
    initial_value = user.daily_notifications

    # Toggle notifications
    updated_user = await repo.toggle_daily_notifications(12345)

    assert updated_user is not None
    assert updated_user.daily_notifications != initial_value


@pytest.mark.asyncio
async def test_toggle_live_notifications(db_session):
    """Test toggling live notifications"""
    repo = TelegramUserRepository(db_session)

    # Create user
    user, _ = await repo.get_or_create(telegram_id=12345)
    initial_value = user.live_notifications

    # Toggle notifications
    updated_user = await repo.toggle_live_notifications(12345)

    assert updated_user is not None
    assert updated_user.live_notifications != initial_value


@pytest.mark.asyncio
async def test_subscribe_user(db_session):
    """Test subscribing user to all notifications"""
    repo = TelegramUserRepository(db_session)

    # Create user
    await repo.get_or_create(telegram_id=12345)

    # Subscribe user
    user = await repo.subscribe_user(12345)

    assert user is not None
    assert user.daily_notifications is True
    assert user.live_notifications is True
    assert user.is_active is True


@pytest.mark.asyncio
async def test_unsubscribe_user(db_session):
    """Test unsubscribing user from all notifications"""
    repo = TelegramUserRepository(db_session)

    # Create user
    await repo.get_or_create(telegram_id=12345)

    # Unsubscribe user
    user = await repo.unsubscribe_user(12345)

    assert user is not None
    assert user.daily_notifications is False
    assert user.live_notifications is False
    assert user.is_active is False


@pytest.mark.asyncio
async def test_get_users_for_live_notifications(db_session):
    """Test getting users for live notifications"""
    repo = TelegramUserRepository(db_session)

    # Create users with different notification settings
    await repo.get_or_create(telegram_id=12345)
    await repo.get_or_create(telegram_id=12346)
    await repo.get_or_create(telegram_id=12347)

    # Update one user to not receive live notifications
    await repo.update_notifications(12346, live_notifications=False)
    # Deactivate one user
    await repo.update_notifications(12347, is_active=False)

    # Get users for live notifications
    users = await repo.get_users_for_live_notifications()

    # Should return only active users with live notifications enabled
    telegram_ids = [user.telegram_id for user in users]
    assert 12345 in telegram_ids
    assert 12346 not in telegram_ids  # Live notifications disabled
    assert 12347 not in telegram_ids  # User inactive


@pytest.mark.asyncio
async def test_get_users_for_daily_notifications(db_session):
    """Test getting users for daily notifications"""
    repo = TelegramUserRepository(db_session)

    # Create users with different notification settings
    await repo.get_or_create(telegram_id=12345)
    await repo.get_or_create(telegram_id=12346)
    await repo.get_or_create(telegram_id=12347)

    # Update one user to not receive daily notifications
    await repo.update_notifications(12346, daily_notifications=False)
    # Deactivate one user
    await repo.update_notifications(12347, is_active=False)

    # Get users for daily notifications
    users = await repo.get_users_for_daily_notifications()

    # Should return only active users with daily notifications enabled
    telegram_ids = [user.telegram_id for user in users]
    assert 12345 in telegram_ids
    assert 12346 not in telegram_ids  # Daily notifications disabled
    assert 12347 not in telegram_ids  # User inactive


@pytest.mark.asyncio
async def test_get_all_active_users(db_session):
    """Test getting all active users"""
    repo = TelegramUserRepository(db_session)

    # Create users
    await repo.get_or_create(telegram_id=12345)
    await repo.get_or_create(telegram_id=12346)
    await repo.get_or_create(telegram_id=12347)

    # Deactivate one user
    await repo.update_notifications(12347, is_active=False)

    # Get all active users
    users = await repo.get_all_active_users()

    # Should return only active users
    telegram_ids = [user.telegram_id for user in users]
    assert 12345 in telegram_ids
    assert 12346 in telegram_ids
    assert 12347 not in telegram_ids  # User inactive


@pytest.mark.asyncio
async def test_delete_user(db_session):
    """Test deleting a user"""
    repo = TelegramUserRepository(db_session)

    # Create user
    await repo.get_or_create(telegram_id=12345)

    # Verify user exists
    user = await repo.get_by_telegram_id(12345)
    assert user is not None

    # Delete user
    result = await repo.delete_user(12345)
    assert result is True

    # Verify user is deleted
    user = await repo.get_by_telegram_id(12345)
    assert user is None


@pytest.mark.asyncio
async def test_delete_nonexistent_user(db_session):
    """Test deleting a non-existent user"""
    repo = TelegramUserRepository(db_session)

    result = await repo.delete_user(99999)
    assert result is False


@pytest.mark.asyncio
async def test_log_notification(db_session):
    """Test logging a notification"""
    repo = TelegramUserRepository(db_session)

    # Create user
    user, _ = await repo.get_or_create(telegram_id=12345)

    # Log notification
    notification = await repo.log_notification(
        user=user, message='Test notification', success=True
    )

    assert notification is not None
    assert notification.user_id == user.id
    assert notification.message == 'Test notification'
    assert notification.success is True
    assert notification.error_message is None


@pytest.mark.asyncio
async def test_log_notification_with_error(db_session):
    """Test logging a failed notification"""
    repo = TelegramUserRepository(db_session)

    # Create user
    user, _ = await repo.get_or_create(telegram_id=12345)

    # Log failed notification
    notification = await repo.log_notification(
        user=user,
        message='Test notification',
        success=False,
        error_message='Test error',
    )

    assert notification is not None
    assert notification.user_id == user.id
    assert notification.message == 'Test notification'
    assert notification.success is False
    assert notification.error_message == 'Test error'
