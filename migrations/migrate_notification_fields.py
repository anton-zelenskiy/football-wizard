#!/usr/bin/env python3
"""
Migration script to update TelegramUser table:
1. Add daily_notifications and live_notifications columns
2. Remove notification_frequency column
3. Migrate existing data
"""

import os
import sys
import sqlite3
from pathlib import Path

# Add the app directory to the Python path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.db.models import db, TelegramUser
import structlog

logger = structlog.get_logger()


def migrate_database():
    """Migrate the database to add new notification fields and remove old ones"""

    # Connect to the database
    db_path = 'football.db'
    if not os.path.exists(db_path):
        logger.error(f"Database file {db_path} not found")
        return False

    try:
        # Connect to SQLite database
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # Check if the new columns already exist
        cursor.execute("PRAGMA table_info(telegramuser)")
        columns = [column[1] for column in cursor.fetchall()]

        # Add new columns if they don't exist
        if 'daily_notifications' not in columns:
            logger.info("Adding daily_notifications column...")
            cursor.execute("ALTER TABLE telegramuser ADD COLUMN daily_notifications BOOLEAN DEFAULT 1")

        if 'live_notifications' not in columns:
            logger.info("Adding live_notifications column...")
            cursor.execute("ALTER TABLE telegramuser ADD COLUMN live_notifications BOOLEAN DEFAULT 1")

        # Migrate existing data from notification_frequency to new columns
        if 'notification_frequency' in columns:
            logger.info("Migrating notification_frequency data...")

            # Get all users with their notification_frequency
            cursor.execute("SELECT id, notification_frequency FROM telegramuser WHERE notification_frequency IS NOT NULL")
            users = cursor.fetchall()

            for user_id, frequency in users:
                # Map old frequency to new boolean fields
                if frequency == 'daily':
                    daily_notifications = True
                    live_notifications = False
                elif frequency == 'hourly':
                    daily_notifications = True
                    live_notifications = True
                elif frequency == 'live':
                    daily_notifications = False
                    live_notifications = True
                else:
                    # Default to daily notifications
                    daily_notifications = True
                    live_notifications = False

                # Update the user's notification preferences
                cursor.execute(
                    "UPDATE telegramuser SET daily_notifications = ?, live_notifications = ? WHERE id = ?",
                    (daily_notifications, live_notifications, user_id)
                )

            logger.info(f"Migrated {len(users)} users' notification preferences")

            # Drop the old notification_frequency column
            logger.info("Removing notification_frequency column...")
            # SQLite doesn't support DROP COLUMN directly, so we need to recreate the table
            cursor.execute("""
                CREATE TABLE telegramuser_new (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    telegram_id INTEGER UNIQUE NOT NULL,
                    username VARCHAR(255),
                    first_name VARCHAR(255),
                    last_name VARCHAR(255),
                    is_active BOOLEAN DEFAULT 1,
                    daily_notifications BOOLEAN DEFAULT 1,
                    live_notifications BOOLEAN DEFAULT 1,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Copy data from old table to new table
            cursor.execute("""
                INSERT INTO telegramuser_new (
                    id, telegram_id, username, first_name, last_name,
                    is_active, daily_notifications, live_notifications,
                    created_at, updated_at
                )
                SELECT
                    id, telegram_id, username, first_name, last_name,
                    is_active, daily_notifications, live_notifications,
                    created_at, updated_at
                FROM telegramuser
            """)

            # Drop old table and rename new table
            cursor.execute("DROP TABLE telegramuser")
            cursor.execute("ALTER TABLE telegramuser_new RENAME TO telegramuser")

            logger.info("Successfully removed notification_frequency column")

        # Commit changes
        conn.commit()
        logger.info("Database migration completed successfully")
        return True

    except Exception as e:
        logger.error(f"Migration failed: {e}")
        conn.rollback()
        return False
    finally:
        conn.close()


def verify_migration():
    """Verify that the migration was successful"""
    try:
        # Test that we can create a TelegramUser with the new fields
        with db:
            # Check if we can query the new columns
            users = list(TelegramUser.select().limit(1))
            if users:
                user = users[0]
                logger.info(f"Sample user: daily_notifications={user.daily_notifications}, live_notifications={user.live_notifications}")

            logger.info("Migration verification successful")
            return True
    except Exception as e:
        logger.error(f"Migration verification failed: {e}")
        return False


if __name__ == "__main__":
    logger.info("Starting database migration...")

    if migrate_database():
        logger.info("Migration completed successfully")

        if verify_migration():
            logger.info("Migration verification passed")
        else:
            logger.error("Migration verification failed")
            sys.exit(1)
    else:
        logger.error("Migration failed")
        sys.exit(1)
