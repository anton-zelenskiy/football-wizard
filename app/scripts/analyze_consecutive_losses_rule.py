#!/usr/bin/env python3
"""
Script to analyze ConsecutiveLossesRule performance and identify improvement opportunities.

This script examines completed betting opportunities for consecutive_losses rule
to understand patterns in wins/losses based on:
- Home vs away team performance
- Team rank differences
- Team rank positions
- Other factors

Usage:
    python -m app.scripts.analyze_consecutive_losses_rule
"""

import asyncio
import json
from collections import defaultdict
from typing import Any

from sqlalchemy import text
import structlog

from app.bet_rules.structures import BetOutcome
from app.db.repositories.betting_opportunity_repository import (
    BettingOpportunityRepository,
)
from app.db.repositories.team_standing_repository import TeamStandingRepository
from app.db.session import get_async_db_session


logger = structlog.get_logger()


async def analyze_consecutive_losses_rule():
    """Analyze ConsecutiveLossesRule outcomes to identify improvement patterns."""
    logger.info('Starting analysis of ConsecutiveLossesRule')

    async with get_async_db_session() as session:
        opp_repo = BettingOpportunityRepository(session)
        standing_repo = TeamStandingRepository(session)

        # Get all completed opportunities for consecutive_losses rule
        query_result = await session.execute(
            text("""
            SELECT
                bo.id,
                bo.rule_slug,
                bo.outcome,
                bo.details,
                bo.confidence_score,
                m.id as match_id,
                m.home_score,
                m.away_score,
                m.season,
                ht.id as home_team_id,
                ht.name as home_team_name,
                at.id as away_team_id,
                at.name as away_team_name,
                l.id as league_id,
                l.name as league_name,
                l.country
            FROM betting_opportunity bo
            JOIN match m ON bo.match_id = m.id
            JOIN team ht ON m.home_team_id = ht.id
            JOIN team at ON m.away_team_id = at.id
            JOIN league l ON m.league_id = l.id
            WHERE bo.rule_slug = 'consecutive_losses'
            AND bo.outcome != 'unknown'
            AND m.status = 'finished'
            AND m.home_score IS NOT NULL
            AND m.away_score IS NOT NULL
            """)
        )
        rows = query_result.all()

        logger.info(f'Found {len(rows)} completed opportunities for consecutive_losses rule')

        # Data structures for analysis
        home_team_stats = {'total': 0, 'wins': 0, 'losses': 0}
        away_team_stats = {'total': 0, 'wins': 0, 'losses': 0}

        rank_diff_stats: dict[int, dict[str, int]] = defaultdict(
            lambda: {'total': 0, 'wins': 0, 'losses': 0}
        )
        team_rank_stats: dict[int, dict[str, int]] = defaultdict(
            lambda: {'total': 0, 'wins': 0, 'losses': 0}
        )
        opponent_rank_stats: dict[int, dict[str, int]] = defaultdict(
            lambda: {'total': 0, 'wins': 0, 'losses': 0}
        )

        # Rank ranges for analysis
        rank_range_stats: dict[str, dict[str, int]] = defaultdict(
            lambda: {'total': 0, 'wins': 0, 'losses': 0}
        )

        confidence_stats: dict[str, dict[str, int]] = defaultdict(
            lambda: {'total': 0, 'wins': 0, 'losses': 0}
        )

        # Process each opportunity
        for row in rows:
            opp_id, rule_slug, outcome, details_json, confidence, match_id, home_score, away_score, season, home_team_id, home_team_name, away_team_id, away_team_name, league_id, league_name, country = row

            # Parse details
            try:
                details = json.loads(details_json) if details_json else {}
            except Exception:
                details = {}

            team_analyzed = details.get('team_analyzed', '')
            home_rank_from_details = details.get('home_team_rank')
            away_rank_from_details = details.get('away_team_rank')

            # Get actual ranks from TeamStanding
            home_rank = None
            away_rank = None
            if season:
                home_standing = await standing_repo.get_by_team_league_season(
                    home_team_id, league_id, season
                )
                away_standing = await standing_repo.get_by_team_league_season(
                    away_team_id, league_id, season
                )
                if home_standing:
                    home_rank = home_standing.rank
                if away_standing:
                    away_rank = away_standing.rank

            # Fallback to details if standing not available
            if home_rank is None:
                home_rank = home_rank_from_details
            if away_rank is None:
                away_rank = away_rank_from_details

            is_win = outcome == BetOutcome.WIN.value
            is_loss = outcome == BetOutcome.LOSE.value

            # Determine which team was analyzed
            is_home_team = team_analyzed == home_team_name

            # Home vs Away analysis
            if is_home_team:
                home_team_stats['total'] += 1
                if is_win:
                    home_team_stats['wins'] += 1
                else:
                    home_team_stats['losses'] += 1
            else:
                away_team_stats['total'] += 1
                if is_win:
                    away_team_stats['wins'] += 1
                else:
                    away_team_stats['losses'] += 1

            # Rank difference analysis
            if home_rank and away_rank:
                if is_home_team:
                    rank_diff = away_rank - home_rank  # Positive = opponent is weaker
                    team_rank = home_rank
                    opponent_rank = away_rank
                else:
                    rank_diff = home_rank - away_rank  # Positive = opponent is weaker
                    team_rank = away_rank
                    opponent_rank = home_rank

                # Rank difference buckets
                rank_diff_bucket = None
                if rank_diff <= -5:
                    rank_diff_bucket = 'opponent_much_stronger'
                elif rank_diff <= -2:
                    rank_diff_bucket = 'opponent_stronger'
                elif rank_diff <= 2:
                    rank_diff_bucket = 'similar_rank'
                elif rank_diff <= 5:
                    rank_diff_bucket = 'opponent_weaker'
                else:
                    rank_diff_bucket = 'opponent_much_weaker'

                rank_diff_stats[rank_diff_bucket]['total'] += 1
                if is_win:
                    rank_diff_stats[rank_diff_bucket]['wins'] += 1
                else:
                    rank_diff_stats[rank_diff_bucket]['losses'] += 1

                # Team rank analysis
                rank_range = None
                if team_rank <= 5:
                    rank_range = 'top5'
                elif team_rank <= 10:
                    rank_range = 'top10'
                elif team_rank <= 15:
                    rank_range = 'mid_table'
                else:
                    rank_range = 'bottom'

                team_rank_stats[team_rank]['total'] += 1
                if is_win:
                    team_rank_stats[team_rank]['wins'] += 1
                else:
                    team_rank_stats[team_rank]['losses'] += 1

                rank_range_stats[rank_range]['total'] += 1
                if is_win:
                    rank_range_stats[rank_range]['wins'] += 1
                else:
                    rank_range_stats[rank_range]['losses'] += 1

                # Opponent rank analysis
                opponent_rank_range = None
                if opponent_rank <= 5:
                    opponent_rank_range = 'opponent_top5'
                elif opponent_rank <= 10:
                    opponent_rank_range = 'opponent_top10'
                elif opponent_rank <= 15:
                    opponent_rank_range = 'opponent_mid_table'
                else:
                    opponent_rank_range = 'opponent_bottom'

                opponent_rank_stats[opponent_rank]['total'] += 1
                if is_win:
                    opponent_rank_stats[opponent_rank]['wins'] += 1
                else:
                    opponent_rank_stats[opponent_rank]['losses'] += 1

            # Confidence score analysis
            if confidence is not None:
                conf_bucket = None
                if confidence < 0.6:
                    conf_bucket = 'low_confidence'
                elif confidence < 0.7:
                    conf_bucket = 'medium_confidence'
                else:
                    conf_bucket = 'high_confidence'

                confidence_stats[conf_bucket]['total'] += 1
                if is_win:
                    confidence_stats[conf_bucket]['wins'] += 1
                else:
                    confidence_stats[conf_bucket]['losses'] += 1

        # Print analysis results
        print('\n' + '=' * 80)
        print('CONSECUTIVE LOSSES RULE ANALYSIS')
        print('=' * 80)

        # Home vs Away
        print('\n--- Home Team vs Away Team Performance ---')
        if home_team_stats['total'] > 0:
            home_win_rate = (home_team_stats['wins'] / home_team_stats['total']) * 100
            print(f'Home Team: {home_team_stats["wins"]}W / {home_team_stats["losses"]}L / {home_team_stats["total"]}T = {home_win_rate:.1f}%')
        if away_team_stats['total'] > 0:
            away_win_rate = (away_team_stats['wins'] / away_team_stats['total']) * 100
            print(f'Away Team: {away_team_stats["wins"]}W / {away_team_stats["losses"]}L / {away_team_stats["total"]}T = {away_win_rate:.1f}%')

        # Rank difference analysis
        print('\n--- Rank Difference Analysis (Team Rank - Opponent Rank) ---')
        for bucket in ['opponent_much_stronger', 'opponent_stronger', 'similar_rank', 'opponent_weaker', 'opponent_much_weaker']:
            stats = rank_diff_stats[bucket]
            if stats['total'] > 0:
                win_rate = (stats['wins'] / stats['total']) * 100
                print(f'{bucket.replace("_", " ").title()}: {stats["wins"]}W / {stats["losses"]}L / {stats["total"]}T = {win_rate:.1f}%')

        # Team rank range analysis
        print('\n--- Team Rank Range Analysis ---')
        for rank_range in ['top5', 'top10', 'mid_table', 'bottom']:
            stats = rank_range_stats[rank_range]
            if stats['total'] > 0:
                win_rate = (stats['wins'] / stats['total']) * 100
                print(f'{rank_range.replace("_", " ").title()}: {stats["wins"]}W / {stats["losses"]}L / {stats["total"]}T = {win_rate:.1f}%')

        # Individual team rank analysis (top and bottom)
        print('\n--- Individual Team Rank Analysis (Top Performers) ---')
        sorted_ranks = sorted([(rank, stats) for rank, stats in team_rank_stats.items() if stats['total'] >= 10],
                            key=lambda x: (x[1]['wins'] / x[1]['total'] if x[1]['total'] > 0 else 0), reverse=True)
        for rank, stats in sorted_ranks[:10]:
            win_rate = (stats['wins'] / stats['total']) * 100
            print(f'Rank {rank}: {stats["wins"]}W / {stats["losses"]}L / {stats["total"]}T = {win_rate:.1f}%')

        print('\n--- Individual Team Rank Analysis (Bottom Performers) ---')
        sorted_ranks_bottom = sorted([(rank, stats) for rank, stats in team_rank_stats.items() if stats['total'] >= 10],
                                    key=lambda x: (x[1]['wins'] / x[1]['total'] if x[1]['total'] > 0 else 0))
        for rank, stats in sorted_ranks_bottom[:10]:
            win_rate = (stats['wins'] / stats['total']) * 100
            print(f'Rank {rank}: {stats["wins"]}W / {stats["losses"]}L / {stats["total"]}T = {win_rate:.1f}%')

        # Confidence analysis
        print('\n--- Confidence Score Analysis ---')
        for conf_bucket in ['low_confidence', 'medium_confidence', 'high_confidence']:
            stats = confidence_stats[conf_bucket]
            if stats['total'] > 0:
                win_rate = (stats['wins'] / stats['total']) * 100
                print(f'{conf_bucket.replace("_", " ").title()}: {stats["wins"]}W / {stats["losses"]}L / {stats["total"]}T = {win_rate:.1f}%')

        print('\n' + '=' * 80)
        print('RECOMMENDATIONS')
        print('=' * 80)

        # Generate recommendations
        recommendations = []

        if home_team_stats['total'] > 0 and away_team_stats['total'] > 0:
            home_win_rate = (home_team_stats['wins'] / home_team_stats['total']) * 100
            away_win_rate = (away_team_stats['wins'] / away_team_stats['total']) * 100
            if abs(home_win_rate - away_win_rate) > 5:
                if home_win_rate > away_win_rate:
                    recommendations.append(f'Home teams perform better ({home_win_rate:.1f}% vs {away_win_rate:.1f}%). Consider favoring home teams.')
                else:
                    recommendations.append(f'Away teams perform better ({away_win_rate:.1f}% vs {home_win_rate:.1f}%). Consider favoring away teams.')

        # Check rank difference patterns
        if rank_diff_stats['opponent_much_weaker']['total'] > 0:
            win_rate = (rank_diff_stats['opponent_much_weaker']['wins'] / rank_diff_stats['opponent_much_weaker']['total']) * 100
            if win_rate > 65:
                recommendations.append(f'Strong performance when opponent is much weaker ({win_rate:.1f}%). This is good.')

        if rank_diff_stats['opponent_much_stronger']['total'] > 0:
            win_rate = (rank_diff_stats['opponent_much_stronger']['wins'] / rank_diff_stats['opponent_much_stronger']['total']) * 100
            if win_rate < 50:
                recommendations.append(f'Weak performance when opponent is much stronger ({win_rate:.1f}%). Consider excluding these cases.')

        # Check bottom teams
        if rank_range_stats['bottom']['total'] > 0:
            win_rate = (rank_range_stats['bottom']['wins'] / rank_range_stats['bottom']['total']) * 100
            if win_rate < 55:
                recommendations.append(f'Bottom teams have low win rate ({win_rate:.1f}%). Consider excluding bottom 3-5 teams.')

        # Check top teams
        if rank_range_stats['top5']['total'] > 0:
            win_rate = (rank_range_stats['top5']['wins'] / rank_range_stats['top5']['total']) * 100
            if win_rate > 70:
                recommendations.append(f'Top 5 teams perform well ({win_rate:.1f}%). This is good.')

        for rec in recommendations:
            print(f'  • {rec}')

        if not recommendations:
            print('  No specific recommendations based on current data.')


async def main():
    """Main entry point"""
    await analyze_consecutive_losses_rule()


if __name__ == '__main__':
    asyncio.run(main())
