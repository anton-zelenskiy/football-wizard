"""
SQLAdmin Authentication Backend for Football Betting Analysis
"""

from sqladmin.authentication import AuthenticationBackend
from starlette.requests import Request
import structlog

from app.admin.models import AdminUser
from app.db.session import get_sync_session_local


logger = structlog.get_logger()


class SQLAdminAuth(AuthenticationBackend):
    """Custom authentication backend for SQLAdmin using AdminUser model"""

    async def login(self, request: Request) -> bool:
        """Handle login form submission"""
        try:
            form = await request.form()
            username = form.get('username')
            password = form.get('password')

            if not username or not password:
                logger.warning('Login attempt with missing credentials')
                return False

            # Get database session
            session_local = get_sync_session_local()
            db = session_local()

            try:
                # Find user by username or email
                user = (
                    db.query(AdminUser)
                    .filter(
                        (AdminUser.username == username) | (AdminUser.email == username)
                    )
                    .first()
                )

                if not user:
                    logger.warning(f'Login attempt with non-existent user: {username}')
                    return False

                if not user.is_active:
                    logger.warning(f'Login attempt with inactive user: {username}')
                    return False

                # Verify password
                if not user.verify_password(password):
                    logger.warning(
                        f'Login attempt with invalid password for user: {username}'
                    )
                    return False

                # Update session with user info
                request.session.update(
                    {
                        'user_id': user.id,
                        'username': user.username,
                        'email': user.email,
                        'is_superuser': user.is_superuser,
                        'is_active': user.is_active,
                    }
                )

                logger.info(f'Successful login for user: {username}')
                return True

            finally:
                db.close()

        except Exception as e:
            logger.error(f'Error during login: {e}')
            return False

    async def logout(self, request: Request) -> bool:
        """Handle logout"""
        try:
            username = request.session.get('username', 'unknown')
            request.session.clear()
            logger.info(f'User logged out: {username}')
            return True
        except Exception as e:
            logger.error(f'Error during logout: {e}')
            return False

    async def authenticate(self, request: Request) -> bool:
        """Check if user is authenticated"""
        try:
            # Check if user session exists
            user_id = request.session.get('user_id')
            is_active = request.session.get('is_active')

            if not user_id or not is_active:
                return False

            # Optionally verify user still exists and is active in database
            # This adds extra security but requires a DB query on each request
            session_local = get_sync_session_local()
            db = session_local()

            try:
                user = (
                    db.query(AdminUser)
                    .filter(AdminUser.id == user_id, AdminUser.is_active is True)
                    .first()
                )

                if not user:
                    # User no longer exists or is inactive, clear session
                    request.session.clear()
                    return False

                return True

            finally:
                db.close()

        except Exception as e:
            logger.error(f'Error during authentication: {e}')
            return False
