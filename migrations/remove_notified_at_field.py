#!/usr/bin/env python3
"""
Migration to remove the 'notified_at' field from BettingOpportunity table
"""

import sqlite3
import structlog
from pathlib import Path

logger = structlog.get_logger()

def migrate():
    """Remove notified_at field from BettingOpportunity table"""
    db_path = Path("football.db")
    
    if not db_path.exists():
        logger.error("Database file not found: football.db")
        return False
    
    try:
        conn = sqlite3.connect(str(db_path))
        cursor = conn.cursor()
        
        # Check if the column exists
        cursor.execute("PRAGMA table_info(bettingopportunity)")
        columns = [column[1] for column in cursor.fetchall()]
        
        if 'notified_at' in columns:
            logger.info("Removing 'notified_at' column from BettingOpportunity table")
            
            # SQLite doesn't support DROP COLUMN directly, so we need to recreate the table
            # First, create a backup table with the new structure
            cursor.execute("""
                CREATE TABLE bettingopportunity_new (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    match_id INTEGER,
                    opportunity_type VARCHAR(255),
                    rule_triggered VARCHAR(255),
                    confidence_score REAL DEFAULT 0.0,
                    details TEXT,
                    outcome VARCHAR(255),
                    created_at DATETIME,
                    FOREIGN KEY (match_id) REFERENCES match (id)
                )
            """)
            
            # Copy data from old table to new table (excluding notified_at)
            cursor.execute("""
                INSERT INTO bettingopportunity_new 
                (id, match_id, opportunity_type, rule_triggered, confidence_score, details, outcome, created_at)
                SELECT id, match_id, opportunity_type, rule_triggered, confidence_score, details, outcome, created_at
                FROM bettingopportunity
            """)
            
            # Drop the old table
            cursor.execute("DROP TABLE bettingopportunity")
            
            # Rename the new table
            cursor.execute("ALTER TABLE bettingopportunity_new RENAME TO bettingopportunity")
            
            # Recreate indexes
            cursor.execute("CREATE INDEX bettingopportunity_match_id ON bettingopportunity (match_id)")
            
            conn.commit()
            logger.info("Successfully removed 'notified_at' column from BettingOpportunity table")
            
        else:
            logger.info("'notified_at' column not found in BettingOpportunity table - migration not needed")
        
        conn.close()
        return True
        
    except Exception as e:
        logger.error(f"Error during migration: {e}")
        if 'conn' in locals():
            conn.rollback()
            conn.close()
        return False

if __name__ == "__main__":
    migrate()
