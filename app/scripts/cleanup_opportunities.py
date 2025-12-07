#!/usr/bin/env python3
"""
Script to clean up betting opportunities by rule_slug.

This is useful when rules are updated and you want to remove old opportunities
created with the previous rule logic.

Usage:
    python -m app.scripts.cleanup_opportunities --rule-slug consecutive_losses
    python -m app.scripts.cleanup_opportunities --rule-slug consecutive_losses --season 2024
"""

import argparse
import asyncio

from sqlalchemy import text
import structlog

from app.db.session import get_async_db_session


logger = structlog.get_logger()


async def cleanup_opportunities(rule_slug: str, season: int | None = None) -> int:
    """Delete betting opportunities by rule_slug.

    Args:
        rule_slug: Rule slug to delete opportunities for
        season: Optional season to filter by

    Returns:
        Number of deleted opportunities
    """
    logger.info(
        'Starting cleanup of betting opportunities',
        rule_slug=rule_slug,
        season=season,
    )

    async with get_async_db_session() as session:
        if season is not None:
            query = text("""
                DELETE FROM betting_opportunity
                WHERE rule_slug = :rule_slug
                AND match_id IN (
                    SELECT id FROM match WHERE season = :season
                )
            """)
            result = await session.execute(
                query, {'rule_slug': rule_slug, 'season': season}
            )
        else:
            query = text("""
                DELETE FROM betting_opportunity
                WHERE rule_slug = :rule_slug
            """)
            result = await session.execute(query, {'rule_slug': rule_slug})

        await session.commit()
        deleted_count = result.rowcount

        logger.info(
            'Cleanup completed',
            rule_slug=rule_slug,
            season=season,
            deleted_count=deleted_count,
        )

        return deleted_count


async def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description='Clean up betting opportunities by rule_slug'
    )
    parser.add_argument(
        '--rule-slug',
        type=str,
        required=True,
        help='Rule slug to delete opportunities for (e.g., consecutive_losses)',
    )
    parser.add_argument(
        '--season',
        type=int,
        help='Optional season to filter by',
    )
    parser.add_argument(
        '--confirm',
        action='store_true',
        help='Confirm deletion (required for safety)',
    )

    args = parser.parse_args()

    if not args.confirm:
        print(
            f'\n⚠️  WARNING: This will delete all opportunities for rule "{args.rule_slug}"'
        )
        if args.season:
            print(f'   for season {args.season}')
        else:
            print('   for ALL seasons')
        print('\n   Use --confirm flag to proceed with deletion.')
        return

    deleted_count = await cleanup_opportunities(
        rule_slug=args.rule_slug, season=args.season
    )

    print(f'\n✅ Deleted {deleted_count} opportunities for rule "{args.rule_slug}"')
    if args.season:
        print(f'   (season {args.season})')
    else:
        print('   (all seasons)')


if __name__ == '__main__':
    asyncio.run(main())
