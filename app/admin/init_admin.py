"""
Initialize admin user and setup
"""

import os

import structlog

from app.admin.models import AdminUser


logger = structlog.get_logger()


def create_default_admin_user():
    """Create default admin user if none exists"""
    from app.db.session import get_sync_session_local

    session_local = get_sync_session_local()
    db = session_local()
    try:
        # Environment overrides for initial credentials
        env_username = os.getenv('ADMIN_USERNAME')
        env_password = os.getenv('ADMIN_PASSWORD')
        env_email = os.getenv('ADMIN_EMAIL')

        # Check if any admin users exist
        existing_user = db.query(AdminUser).first()
        if existing_user:
            # If env overrides provided, update the first admin user
            if env_username and env_password:
                logger.info('Updating existing admin user credentials from environment')
                existing_user.username = env_username
                existing_user.email = env_email
                existing_user.hashed_password = AdminUser.hash_password(env_password)
                db.add(existing_user)
                db.commit()
                logger.info('Admin user credentials updated')
            else:
                logger.info('Admin users already exist, skipping default user creation')
            return

        # Create default superuser (use env if provided)
        username = env_username
        password = env_password
        email = env_email

        default_user = AdminUser(
            username=username,
            email=email,
            hashed_password=AdminUser.hash_password(password),
            is_superuser=True,
            is_active=True,
        )

        db.add(default_user)
        db.commit()

        logger.info(f'Default admin user created: username={username}')
        if not env_password:
            logger.warning(
                'IMPORTANT: Change the default admin password in production!'
            )

    except Exception as e:
        logger.error(f'Error creating default admin user: {e}')
        db.rollback()
    finally:
        db.close()


def init_admin():
    """Initialize admin system"""
    create_default_admin_user()
