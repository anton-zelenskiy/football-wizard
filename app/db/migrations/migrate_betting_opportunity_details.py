#!/usr/bin/env python3
"""
Migration script to update BettingOpportunity details field:
1. Remove uncertainty_note entries
2. Remove both_teams_fit entries
3. Rename rule_type to slug
4. Remove opportunity_type field from BettingOpportunity table
"""

import json
import sqlite3
import sys


def migrate_betting_opportunity_details():
    """Migrate BettingOpportunity details field"""
    try:
        # Connect to database
        conn = sqlite3.connect('football.db')
        cursor = conn.cursor()

        # Get all BettingOpportunity records
        cursor.execute('SELECT id, details FROM BettingOpportunity')
        records = cursor.fetchall()

        updated_count = 0

        for record_id, details_json in records:
            if not details_json:
                continue

            try:
                # Parse JSON details
                details = json.loads(details_json)
                original_details = details.copy()

                # Remove uncertainty_note if it exists
                if 'uncertainty_note' in details:
                    del details['uncertainty_note']

                # Remove both_teams_fit if it exists
                if 'both_teams_fit' in details:
                    del details['both_teams_fit']

                # Rename rule_type to slug if it exists
                if 'rule_type' in details:
                    details['slug'] = details['rule_type']
                    del details['rule_type']

                # Only update if changes were made
                if details != original_details:
                    updated_json = json.dumps(details)
                    cursor.execute(
                        'UPDATE BettingOpportunity SET details = ? WHERE id = ?',
                        (updated_json, record_id),
                    )
                    updated_count += 1
                    print(f'Updated record {record_id}')

            except json.JSONDecodeError as e:
                print(f'Error parsing JSON for record {record_id}: {e}')
                continue

        # Remove opportunity_type column from BettingOpportunity table
        print('Removing opportunity_type column from BettingOpportunity table...')
        try:
            # SQLite doesn't support DROP COLUMN directly, so we need to recreate the table
            cursor.execute('''
                CREATE TABLE BettingOpportunity_new (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    match_id INTEGER,
                    rule_triggered VARCHAR(255),
                    confidence_score REAL DEFAULT 0.0,
                    details TEXT,
                    outcome VARCHAR(255),
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (match_id) REFERENCES Match(id)
                )
            ''')

            # Copy data from old table to new table
            cursor.execute('''
                INSERT INTO BettingOpportunity_new
                (id, match_id, rule_triggered, confidence_score, details, outcome, created_at)
                SELECT id, match_id, rule_triggered, confidence_score, details, outcome, created_at
                FROM BettingOpportunity
            ''')

            # Drop old table and rename new table
            cursor.execute('DROP TABLE BettingOpportunity')
            cursor.execute('ALTER TABLE BettingOpportunity_new RENAME TO BettingOpportunity')

            print('Successfully removed opportunity_type column')
        except Exception as e:
            print(f'Error removing opportunity_type column: {e}')

        # Commit changes
        conn.commit()
        print(f'Migration completed. Updated {updated_count} records.')

        conn.close()

    except Exception as e:
        print(f'Error during migration: {e}')
        sys.exit(1)


def preview_changes():
    """Preview what changes will be made without applying them"""
    try:
        conn = sqlite3.connect('football.db')
        cursor = conn.cursor()

        cursor.execute('SELECT id, details FROM BettingOpportunity')
        records = cursor.fetchall()

        print('Preview of changes:')
        print('=' * 50)

        for record_id, details_json in records:
            if not details_json:
                continue

            try:
                details = json.loads(details_json)
                changes = []

                if 'uncertainty_note' in details:
                    changes.append(
                        f"Remove uncertainty_note: '{details['uncertainty_note']}'"
                    )

                if 'both_teams_fit' in details:
                    changes.append(
                        f"Remove both_teams_fit: {details['both_teams_fit']}"
                    )

                if 'rule_type' in details:
                    changes.append(f"Rename rule_type '{details['rule_type']}' to slug")

                if changes:
                    print(f'Record {record_id}:')
                    for change in changes:
                        print(f'  - {change}')
                    print()

            except json.JSONDecodeError:
                print(f'Record {record_id}: Invalid JSON')

        conn.close()

    except Exception as e:
        print(f'Error during preview: {e}')


if __name__ == '__main__':
    if len(sys.argv) > 1 and sys.argv[1] == '--preview':
        preview_changes()
    else:
        print('Starting migration...')
        migrate_betting_opportunity_details()
