#!/usr/bin/env python3
"""
Migration script to rename rule_triggered field to rule_slug and convert rule names to slugs
"""

import sqlite3
import sys

# Mapping from rule names to slugs
RULE_NAME_TO_SLUG = {
    'Consecutive Losses Rule': 'consecutive_losses',
    'Consecutive Draws Rule': 'consecutive_draws',
    'Top 5 Consecutive Losses Rule': 'top5_consecutive_losses',
    'Live Match Red Card Rule': 'live_red_card',
}


def migrate_rule_triggered_to_slug():
    """Rename rule_triggered field to rule_slug and convert rule names to slugs"""
    try:
        # Connect to database
        conn = sqlite3.connect('football.db')
        cursor = conn.cursor()

        print('Renaming rule_triggered field to rule_slug and converting rule names to slugs...')

        # SQLite doesn't support DROP COLUMN directly, so we need to recreate the table
        cursor.execute('''
            CREATE TABLE BettingOpportunity_new (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                match_id INTEGER,
                rule_slug VARCHAR(255),
                confidence_score REAL DEFAULT 0.0,
                details TEXT,
                outcome VARCHAR(255),
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (match_id) REFERENCES Match(id)
            )
        ''')

        # Get all records to convert rule names to slugs
        cursor.execute('SELECT id, match_id, rule_triggered, confidence_score, details, outcome, created_at FROM BettingOpportunity')
        records = cursor.fetchall()

        converted_count = 0
        for record in records:
            record_id, match_id, rule_triggered, confidence_score, details, outcome, created_at = record

            # Convert rule name to slug
            rule_slug = RULE_NAME_TO_SLUG.get(rule_triggered, rule_triggered)
            if rule_triggered != rule_slug:
                print(f'Converting rule name "{rule_triggered}" to slug "{rule_slug}" for record {record_id}')
                converted_count += 1

            # Insert into new table
            cursor.execute('''
                INSERT INTO BettingOpportunity_new
                (id, match_id, rule_slug, confidence_score, details, outcome, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (record_id, match_id, rule_slug, confidence_score, details, outcome, created_at))

        # Drop old table and rename new table
        cursor.execute('DROP TABLE BettingOpportunity')
        cursor.execute('ALTER TABLE BettingOpportunity_new RENAME TO BettingOpportunity')

        # Commit changes
        conn.commit()
        print(f'Migration completed. Converted {converted_count} rule names to slugs.')

        conn.close()

    except Exception as e:
        print(f'Error during migration: {e}')
        sys.exit(1)


def preview_changes():
    """Preview what changes will be made without applying them"""
    try:
        conn = sqlite3.connect('football.db')
        cursor = conn.cursor()

        cursor.execute('SELECT id, rule_triggered FROM BettingOpportunity')
        records = cursor.fetchall()

        print('Preview of changes:')
        print('=' * 50)

        for record_id, rule_triggered in records:
            rule_slug = RULE_NAME_TO_SLUG.get(rule_triggered, rule_triggered)
            if rule_triggered != rule_slug:
                print(f'Record {record_id}: "{rule_triggered}" -> "{rule_slug}"')
            else:
                print(f'Record {record_id}: "{rule_triggered}" (no change needed)')

        conn.close()

    except Exception as e:
        print(f'Error during preview: {e}')


if __name__ == '__main__':
    if len(sys.argv) > 1 and sys.argv[1] == '--preview':
        preview_changes()
    else:
        print('Starting migration...')
        migrate_rule_triggered_to_slug()
