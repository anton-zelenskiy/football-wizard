from datetime import datetime

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
import structlog

from app.db.sqlalchemy_models import NotificationLog, TelegramUser

from .base_repository import BaseRepository


logger = structlog.get_logger()


class TelegramUserRepository(BaseRepository[TelegramUser]):
    """Repository for TelegramUser operations using async SQLAlchemy"""

    def __init__(self, session: AsyncSession):
        super().__init__(session, TelegramUser)

    async def get_or_create(
        self,
        telegram_id: int,
        username: str | None = None,
        first_name: str | None = None,
        last_name: str | None = None,
    ) -> tuple[TelegramUser, bool]:
        """Get or create a Telegram user"""
        try:
            # Try to get existing user
            result = await self.session.execute(
                select(TelegramUser).where(TelegramUser.telegram_id == telegram_id)
            )
            user = result.scalar_one_or_none()

            if user:
                # Update user info if not newly created
                user.username = username
                user.first_name = first_name
                user.last_name = last_name
                user.is_active = True
                user.updated_at = datetime.now()
                await self.session.commit()
                logger.info(f'Updated existing user: {telegram_id}')
                return user, False
            else:
                # Create new user
                user = TelegramUser(
                    telegram_id=telegram_id,
                    username=username,
                    first_name=first_name,
                    last_name=last_name,
                    is_active=True,
                )
                self.session.add(user)
                await self.session.commit()
                await self.session.refresh(user)
                logger.info(f'Created new user: {telegram_id}')
                return user, True

        except IntegrityError as e:
            await self.session.rollback()
            logger.error(f'Integrity error creating user {telegram_id}: {e}')
            raise
        except Exception as e:
            await self.session.rollback()
            logger.error(f'Error getting/creating user {telegram_id}: {e}')
            raise

    async def get_by_telegram_id(self, telegram_id: int) -> TelegramUser | None:
        """Get a Telegram user by telegram_id"""
        try:
            result = await self.session.execute(
                select(TelegramUser).where(TelegramUser.telegram_id == telegram_id)
            )
            return result.scalar_one_or_none()
        except Exception as e:
            logger.error(f'Error getting user {telegram_id}: {e}')
            raise

    async def get_by_id(self, user_id: int) -> TelegramUser | None:
        """Get a Telegram user by internal ID"""
        try:
            result = await self.session.execute(
                select(TelegramUser).where(TelegramUser.id == user_id)
            )
            return result.scalar_one_or_none()
        except Exception as e:
            logger.error(f'Error getting user by ID {user_id}: {e}')
            raise

    async def update_notifications(
        self,
        telegram_id: int,
        daily_notifications: bool | None = None,
        live_notifications: bool | None = None,
        is_active: bool | None = None,
    ) -> TelegramUser | None:
        """Update Telegram user notification settings"""
        try:
            user = await self.get_by_telegram_id(telegram_id)
            if not user:
                logger.warning(f'User {telegram_id} not found for notification update')
                return None

            if daily_notifications is not None:
                user.daily_notifications = daily_notifications
            if live_notifications is not None:
                user.live_notifications = live_notifications
            if is_active is not None:
                user.is_active = is_active

            user.updated_at = datetime.now()
            await self.session.commit()
            logger.info(f'Updated notifications for user {telegram_id}')
            return user

        except Exception as e:
            await self.session.rollback()
            logger.error(f'Error updating notifications for user {telegram_id}: {e}')
            raise

    async def toggle_daily_notifications(self, telegram_id: int) -> TelegramUser | None:
        """Toggle daily notifications for a Telegram user"""
        try:
            user = await self.get_by_telegram_id(telegram_id)
            if not user:
                logger.warning(f'User {telegram_id} not found for toggle')
                return None

            user.daily_notifications = not user.daily_notifications
            user.updated_at = datetime.now()
            await self.session.commit()
            logger.info(
                f'Toggled daily notifications for user {telegram_id}: {user.daily_notifications}'
            )
            return user

        except Exception as e:
            await self.session.rollback()
            logger.error(
                f'Error toggling daily notifications for user {telegram_id}: {e}'
            )
            raise

    async def toggle_live_notifications(self, telegram_id: int) -> TelegramUser | None:
        """Toggle live notifications for a Telegram user"""
        try:
            user = await self.get_by_telegram_id(telegram_id)
            if not user:
                logger.warning(f'User {telegram_id} not found for toggle')
                return None

            user.live_notifications = not user.live_notifications
            user.updated_at = datetime.now()
            await self.session.commit()
            logger.info(
                f'Toggled live notifications for user {telegram_id}: {user.live_notifications}'
            )
            return user

        except Exception as e:
            await self.session.rollback()
            logger.error(
                f'Error toggling live notifications for user {telegram_id}: {e}'
            )
            raise

    async def subscribe_user(self, telegram_id: int) -> TelegramUser | None:
        """Subscribe user to all notifications"""
        return await self.update_notifications(
            telegram_id=telegram_id,
            daily_notifications=True,
            live_notifications=True,
            is_active=True,
        )

    async def unsubscribe_user(self, telegram_id: int) -> TelegramUser | None:
        """Unsubscribe user from all notifications"""
        return await self.update_notifications(
            telegram_id=telegram_id,
            daily_notifications=False,
            live_notifications=False,
            is_active=False,
        )

    async def get_users_for_live_notifications(self) -> list[TelegramUser]:
        """Get users subscribed to live notifications"""
        try:
            result = await self.session.execute(
                select(TelegramUser).where(
                    TelegramUser.is_active.is_(True),
                    TelegramUser.live_notifications.is_(True),
                )
            )
            return result.scalars().all()
        except Exception as e:
            logger.error(f'Error getting users for live notifications: {e}')
            return []

    async def get_users_for_daily_notifications(self) -> list[TelegramUser]:
        """Get users subscribed to daily notifications"""
        try:
            result = await self.session.execute(
                select(TelegramUser).where(
                    TelegramUser.is_active.is_(True),
                    TelegramUser.daily_notifications.is_(True),
                )
            )
            return result.scalars().all()
        except Exception as e:
            logger.error(f'Error getting users for daily notifications: {e}')
            return []

    async def get_all_active_users(self) -> list[TelegramUser]:
        """Get all active users"""
        try:
            result = await self.session.execute(
                select(TelegramUser).where(TelegramUser.is_active.is_(True))
            )
            return result.scalars().all()
        except Exception as e:
            logger.error(f'Error getting all active users: {e}')
            return []

    async def delete_user(self, telegram_id: int) -> bool:
        """Delete a Telegram user"""
        try:
            user = await self.get_by_telegram_id(telegram_id)
            if not user:
                logger.warning(f'User {telegram_id} not found for deletion')
                return False

            await self.session.delete(user)
            await self.session.commit()
            logger.info(f'Deleted user {telegram_id}')
            return True

        except Exception as e:
            await self.session.rollback()
            logger.error(f'Error deleting user {telegram_id}: {e}')
            raise

    async def log_notification(
        self,
        user: TelegramUser,
        opportunity_id: int | None = None,
        message: str = '',
        success: bool = True,
        error_message: str | None = None,
    ) -> NotificationLog:
        """Log a notification attempt"""
        try:
            notification_log = NotificationLog(
                user_id=user.id,
                opportunity_id=opportunity_id,
                message=message,
                success=success,
                error_message=error_message,
            )
            self.session.add(notification_log)
            await self.session.commit()
            await self.session.refresh(notification_log)
            logger.info(f'Logged notification for user {user.telegram_id}')
            return notification_log

        except Exception as e:
            await self.session.rollback()
            logger.error(f'Error logging notification: {e}')
            raise

    async def has_notification_been_sent(
        self, user: TelegramUser, opportunity_id: int
    ) -> bool:
        """Check if a notification has already been sent to a user for a specific opportunity"""
        try:
            result = await self.session.execute(
                select(NotificationLog).where(
                    NotificationLog.user_id == user.id,
                    NotificationLog.opportunity_id == opportunity_id,
                    NotificationLog.success.is_(True),
                )
            )
            return result.scalar_one_or_none() is not None
        except Exception as e:
            logger.error(f'Error checking notification history: {e}')
            return False

    async def get_users_for_live_notifications_with_duplicate_check(
        self, opportunity_id: int
    ) -> list[TelegramUser]:
        """Get users subscribed to live notifications who haven't received this opportunity yet"""
        try:
            # Get all users subscribed to live notifications
            result = await self.session.execute(
                select(TelegramUser).where(
                    TelegramUser.is_active.is_(True),
                    TelegramUser.live_notifications.is_(True),
                )
            )
            all_users = result.scalars().all()

            # Filter out users who have already received this opportunity
            users_to_notify = []
            for user in all_users:
                if not await self.has_notification_been_sent(user, opportunity_id):
                    users_to_notify.append(user)

            return users_to_notify
        except Exception as e:
            logger.error(
                f'Error getting users for live notifications with duplicate check: {e}'
            )
            return []
