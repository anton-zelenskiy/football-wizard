#!/usr/bin/env python3
"""
Script to analyze historical matches and create betting opportunities.

This script analyzes finished matches from a previous season and creates
betting opportunities based on the betting rules. It starts from a specified
round (default: 6) and iterates through all rounds, using previous rounds'
matches for analysis.

Usage:
    python -m app.scripts.analyze_historical_matches --country England --league "Premier League" --season 2024 --start-round 6
"""

import argparse
import asyncio
from typing import Any

import structlog

from app.bet_rules.rule_engine import BettingRulesEngine
from app.bet_rules.structures import MatchSummary
from app.db.repositories.betting_opportunity_repository import (
    BettingOpportunityRepository,
)
from app.db.repositories.match_repository import MatchRepository
from app.db.repositories.team_standing_repository import TeamStandingRepository
from app.db.session import get_async_db_session


logger = structlog.get_logger()


async def analyze_historical_matches(
    country: str,
    league_name: str,
    season: int,
    start_round: int = 6,
    rounds_back: int = 5,
) -> dict[str, Any]:
    """Analyze historical matches and create betting opportunities.

    Args:
        country: Country name (e.g., 'England')
        league_name: League name (e.g., 'Premier League')
        season: Season year (e.g., 2024)
        start_round: Starting round number (default: 6)
        rounds_back: Number of previous rounds to use for analysis (default: 5)

    Returns:
        Dictionary with statistics about the analysis
    """
    logger.info(
        'Starting historical match analysis',
        country=country,
        league=league_name,
        season=season,
        start_round=start_round,
        rounds_back=rounds_back,
    )

    stats = {
        'total_rounds_processed': 0,
        'total_matches_analyzed': 0,
        'total_opportunities_created': 0,
        'opportunities_by_round': {},
    }

    rules_engine = BettingRulesEngine()

    async with get_async_db_session() as session:
        match_repo = MatchRepository(session)
        opp_repo = BettingOpportunityRepository(session)
        standing_repo = TeamStandingRepository(session)

        # Get league
        league = await match_repo.get_league_by_name_and_country(
            league_name, country
        )
        if not league:
            logger.error(f'League not found: {country} - {league_name}')
            return stats

        # Get maximum round number for this league/season
        max_round = await match_repo.get_max_round_by_league_season(
            league.id, season
        )
        if not max_round:
            logger.error(
                f'No finished matches found for {country} - {league_name} season {season}'
            )
            return stats

        if start_round > max_round:
            logger.error(
                f'Start round {start_round} is greater than max round {max_round}'
            )
            return stats

        logger.info(
            f'Processing rounds {start_round} to {max_round} for {country} - {league_name} season {season}'
        )

        # Iterate through rounds from start_round to max_round
        for round_num in range(start_round, max_round + 1):
            logger.info(f'Processing Round {round_num}')

            # Get all matches for this round
            round_matches = await match_repo.get_matches_by_league_season_round(
                league.id, season, round_num
            )

            if not round_matches:
                logger.warning(f'No matches found for Round {round_num}')
                continue

            logger.info(f'Found {len(round_matches)} matches in Round {round_num}')

            round_opportunities = 0

            # Analyze each match in this round
            for match in round_matches:
                try:
                    # Get recent matches for both teams before this match's date
                    # This handles cases where matches from higher rounds may be played earlier
                    home_recent_matches = (
                        await match_repo.get_team_matches_by_season_and_rounds(
                            match.home_team.id,
                            season,
                            before_date=match.match_date,
                            limit=rounds_back,
                        )
                    )
                    away_recent_matches = (
                        await match_repo.get_team_matches_by_season_and_rounds(
                            match.away_team.id,
                            season,
                            before_date=match.match_date,
                            limit=rounds_back,
                        )
                    )

                    # Get team ranks from TeamStanding
                    home_rank = None
                    away_rank = None
                    home_standing = await standing_repo.get_by_team_league_season(
                        match.home_team.id, league.id, season
                    )
                    away_standing = await standing_repo.get_by_team_league_season(
                        match.away_team.id, league.id, season
                    )
                    if home_standing:
                        home_rank = home_standing.rank
                    if away_standing:
                        away_rank = away_standing.rank

                    logger.info(f'Home rank: {home_rank}, Away rank: {away_rank}')

                    # Get teams count from TeamStanding for this season (more accurate than league.teams)
                    # This avoids lazy loading issues
                    teams_count_result = await standing_repo.get_standings_by_league_season(
                        league.id, season
                    )
                    teams_count = len(teams_count_result) if teams_count_result else 0

                    # Create MatchSummary with teams_count to avoid lazy loading
                    try:
                        match_summary = MatchSummary.from_match(
                            match, home_rank, away_rank, teams_count=teams_count
                        )
                    except Exception as e:
                        logger.error(f'Error creating match summary: {e}')
                        continue

                    logger.info(f'Match summary: {match_summary}')

                    # Convert recent matches to Pydantic models
                    home_matches_data = [m.to_pydantic() for m in home_recent_matches]
                    away_matches_data = [m.to_pydantic() for m in away_recent_matches]

                    match_summary.home_recent_matches = home_matches_data
                    match_summary.away_recent_matches = away_matches_data

                    # Analyze match using rules engine
                    match_opportunities = rules_engine.analyze_match(match_summary)

                    logger.info(f'Match opportunities: {match_opportunities}')

                    if match_opportunities:
                        # Save opportunities
                        for opp in match_opportunities:
                            try:
                                await opp_repo.save_opportunity(opp)
                                round_opportunities += 1
                                stats['total_opportunities_created'] += 1
                                logger.debug(
                                    f'Created opportunity: {opp.slug} for '
                                    f'{match.home_team.name} vs {match.away_team.name}'
                                )
                            except Exception as e:
                                logger.error(
                                    f'Error saving opportunity: {e}',
                                    match_id=match.id,
                                    rule_slug=opp.slug,
                                )

                    stats['total_matches_analyzed'] += 1

                except Exception as e:
                    logger.error(
                        f'Error analyzing match {match.home_team.name} vs '
                        f'{match.away_team.name} in Round {round_num}: {e}'
                    )
                    continue

            stats['opportunities_by_round'][round_num] = round_opportunities
            stats['total_rounds_processed'] += 1

            logger.info(
                f'Round {round_num} completed: {len(round_matches)} matches analyzed, '
                f'{round_opportunities} opportunities created'
            )

        # After processing all rounds, update betting outcomes for finished matches
        # Use a fresh session to avoid async context issues
        try:
            async with get_async_db_session() as update_session:
                update_opp_repo = BettingOpportunityRepository(update_session)
                updated_outcomes = await update_opp_repo.update_betting_outcomes()
                stats['updated_outcomes'] = updated_outcomes
                logger.info(
                    'Updated betting outcomes after historical analysis',
                    updated_outcomes=updated_outcomes,
                )
        except Exception as e:
            logger.error(f'Error updating betting outcomes: {e}')
            stats['updated_outcomes'] = 0

        # Get betting statistics for 2024 season
        # Use a fresh session to avoid async context issues
        try:
            async with get_async_db_session() as stats_session:
                stats_opp_repo = BettingOpportunityRepository(stats_session)
                season_2024_stats = await stats_opp_repo.get_betting_statistics(season=2024)
                stats['season_2024_statistics'] = season_2024_stats
                logger.info(
                    'Betting statistics for 2024 season',
                    total=season_2024_stats['total'],
                    wins=season_2024_stats['wins'],
                    losses=season_2024_stats['losses'],
                    win_rate=season_2024_stats['win_rate'],
                )
        except Exception as e:
            logger.error(f'Error getting betting statistics for 2024 season: {e}')
            stats['season_2024_statistics'] = None

    logger.info(
        'Historical match analysis completed',
        total_rounds=stats['total_rounds_processed'],
        total_matches=stats['total_matches_analyzed'],
        total_opportunities=stats['total_opportunities_created'],
    )

    return stats


async def main():
    """Main entry point for the script"""
    parser = argparse.ArgumentParser(
        description='Analyze historical matches and create betting opportunities'
    )
    parser.add_argument(
        '--country',
        type=str,
        required=True,
        help='Country name (e.g., England)',
    )
    parser.add_argument(
        '--league',
        type=str,
        required=True,
        help='League name (e.g., "Premier League")',
    )
    parser.add_argument(
        '--season',
        type=int,
        required=True,
        help='Season year (e.g., 2024)',
    )
    parser.add_argument(
        '--start-round',
        type=int,
        default=6,
        help='Starting round number (default: 6)',
    )
    parser.add_argument(
        '--rounds-back',
        type=int,
        default=5,
        help='Number of previous rounds to use for analysis (default: 5)',
    )

    args = parser.parse_args()

    stats = await analyze_historical_matches(
        country=args.country,
        league_name=args.league,
        season=args.season,
        start_round=args.start_round,
        rounds_back=args.rounds_back,
    )

    print('\n=== Analysis Summary ===')
    print(f'Total rounds processed: {stats.get("total_rounds_processed", 0)}')
    print(f'Total matches analyzed: {stats.get("total_matches_analyzed", 0)}')
    print(f'Total opportunities created: {stats.get("total_opportunities_created", 0)}')
    if stats.get('updated_outcomes') is not None:
        print(f'Updated outcomes: {stats.get("updated_outcomes", 0)}')

    print('\n=== Opportunities by Round ===')
    for round_num, count in sorted(stats.get('opportunities_by_round', {}).items()):
        print(f'  Round {round_num}: {count} opportunities')

    # Display 2024 season statistics
    season_2024_stats = stats.get('season_2024_statistics')
    if season_2024_stats:
        print('\n=== Betting Statistics for 2024 Season ===')
        print(f'Total opportunities: {season_2024_stats["total"]}')
        print(f'Wins: {season_2024_stats["wins"]}')
        print(f'Losses: {season_2024_stats["losses"]}')
        print(f'Win rate: {season_2024_stats["win_rate"]}%')
    else:
        print('\n=== Betting Statistics for 2024 Season ===')
        print('Statistics not available')


if __name__ == '__main__':
    asyncio.run(main())
