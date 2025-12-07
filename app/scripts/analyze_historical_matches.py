#!/usr/bin/env python3
"""
Script to analyze historical matches and create betting opportunities.

This script analyzes finished matches from a previous season and creates
betting opportunities based on the betting rules. It starts from a specified
round (default: 6) and iterates through all rounds, using previous rounds'
matches for analysis.

Usage:
    # Analyze single league
    python -m app.scripts.analyze_historical_matches --country England --league "Premier League" --season 2024 --start-round 6

    # Analyze all leagues for a specific season
    python -m app.scripts.analyze_historical_matches --all-leagues --season 2024

    # Analyze all leagues for all seasons (statistics only)
    python -m app.scripts.analyze_historical_matches --all-leagues
"""

import argparse
import asyncio
from typing import Any

import structlog
from app.bet_rules.bet_rules import (
    ConsecutiveDrawsRule,
    ConsecutiveLossesRule,
    Top5ConsecutiveLossesRule,
    Top5ConsecutiveNoWinsRule,
)
from app.bet_rules.rule_engine import BettingRulesEngine
from app.bet_rules.structures import MatchSummary
from app.db.repositories.betting_opportunity_repository import (
    BettingOpportunityRepository,
)
from app.db.repositories.match_repository import MatchRepository
from app.db.repositories.team_standing_repository import TeamStandingRepository
from app.db.session import get_async_db_session
from app.scraper.constants import LEAGUES_OF_INTEREST


logger = structlog.get_logger()

rules = [
    ConsecutiveLossesRule(),
    ConsecutiveDrawsRule(),
    Top5ConsecutiveLossesRule(),
    Top5ConsecutiveNoWinsRule(),
]


async def analyze_historical_matches(
    country: str,
    league_name: str,
    season: int | None,
    start_round: int = 6,
    rounds_back: int = 5,
) -> dict[str, Any]:
    """Analyze historical matches and create betting opportunities.

    Args:
        country: Country name (e.g., 'England')
        league_name: League name (e.g., 'Premier League')
        season: Season year (e.g., 2024). If None, only statistics are calculated.
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

    # If season is None, only calculate statistics, don't analyze matches
    if season is None:
        logger.info(
            'Season not provided, calculating statistics only',
            country=country,
            league=league_name,
        )
        async with get_async_db_session() as stats_session:
            stats_opp_repo = BettingOpportunityRepository(stats_session)
            season_stats = await stats_opp_repo.get_betting_statistics(season=None)
            stats_by_type = (
                await stats_opp_repo.get_betting_statistics_by_opportunity_type(
                    season=None
                )
            )
            stats_by_rule = await stats_opp_repo.get_betting_statistics_by_rule(
                season=None
            )
            stats_by_period = (
                await stats_opp_repo.get_betting_statistics_by_season_period(
                    season=None
                )
            )
            stats['season_statistics'] = season_stats
            stats['season_statistics_by_type'] = stats_by_type
            stats['season_statistics_by_rule'] = stats_by_rule
            stats['season_statistics_by_period'] = stats_by_period
        return stats

    rules_engine = BettingRulesEngine(rules=rules)

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

        # Get betting statistics for the specified season
        # Use a fresh session to avoid async context issues
        try:
            async with get_async_db_session() as stats_session:
                stats_opp_repo = BettingOpportunityRepository(stats_session)
                season_stats = await stats_opp_repo.get_betting_statistics(season=season)
                stats_by_type = (
                    await stats_opp_repo.get_betting_statistics_by_opportunity_type(
                        season=season
                    )
                )
                stats_by_rule = await stats_opp_repo.get_betting_statistics_by_rule(
                    season=season
                )
                stats_by_period = (
                    await stats_opp_repo.get_betting_statistics_by_season_period(
                        season=season
                    )
                )
                stats['season_statistics'] = season_stats
                stats['season_statistics_by_type'] = stats_by_type
                stats['season_statistics_by_rule'] = stats_by_rule
                stats['season_statistics_by_period'] = stats_by_period
                logger.info(
                    f'Betting statistics for {season} season',
                    total=season_stats['total'],
                    wins=season_stats['wins'],
                    losses=season_stats['losses'],
                    win_rate=season_stats['win_rate'],
                )
                logger.info(
                    f'Betting statistics by opportunity type for {season} season',
                    stats_by_type=stats_by_type,
                )
        except Exception as e:
            logger.error(f'Error getting betting statistics for {season} season: {e}')
            stats['season_statistics'] = None
            stats['season_statistics_by_type'] = None
            stats['season_statistics_by_rule'] = None
            stats['season_statistics_by_period'] = None

    logger.info(
        'Historical match analysis completed',
        total_rounds=stats['total_rounds_processed'],
        total_matches=stats['total_matches_analyzed'],
        total_opportunities=stats['total_opportunities_created'],
    )

    return stats


def _merge_statistics(
    stats_list: list[dict[str, Any]]
) -> dict[str, dict[str, int | float]]:
    """Merge statistics from multiple leagues.

    Args:
        stats_list: List of statistics dictionaries from multiple leagues

    Returns:
        Merged statistics dictionary
    """
    merged: dict[str, dict[str, int | float]] = {}

    for stats in stats_list:
        # Merge overall statistics
        if 'season_statistics' in stats and stats['season_statistics']:
            if 'overall' not in merged:
                merged['overall'] = {
                    'total': 0,
                    'wins': 0,
                    'losses': 0,
                    'win_rate': 0.0,
                }
            merged['overall']['total'] += stats['season_statistics']['total']
            merged['overall']['wins'] += stats['season_statistics']['wins']
            merged['overall']['losses'] += stats['season_statistics']['losses']

        # Merge statistics by opportunity type
        if 'season_statistics_by_type' in stats and stats['season_statistics_by_type']:
            if 'by_type' not in merged:
                merged['by_type'] = {}
            for opp_type, type_stats in stats['season_statistics_by_type'].items():
                if opp_type not in merged['by_type']:
                    merged['by_type'][opp_type] = {
                        'total': 0,
                        'wins': 0,
                        'losses': 0,
                        'win_rate': 0.0,
                    }
                merged['by_type'][opp_type]['total'] += type_stats['total']
                merged['by_type'][opp_type]['wins'] += type_stats['wins']
                merged['by_type'][opp_type]['losses'] += type_stats['losses']

        # Merge statistics by rule
        if 'season_statistics_by_rule' in stats and stats['season_statistics_by_rule']:
            if 'by_rule' not in merged:
                merged['by_rule'] = {}
            for rule_slug, rule_stats in stats['season_statistics_by_rule'].items():
                if rule_slug not in merged['by_rule']:
                    merged['by_rule'][rule_slug] = {
                        'rule_name': rule_stats.get('rule_name', rule_slug),
                        'total': 0,
                        'wins': 0,
                        'losses': 0,
                        'win_rate': 0.0,
                    }
                merged['by_rule'][rule_slug]['total'] += rule_stats['total']
                merged['by_rule'][rule_slug]['wins'] += rule_stats['wins']
                merged['by_rule'][rule_slug]['losses'] += rule_stats['losses']

    # Calculate win rates
    if 'overall' in merged:
        total = merged['overall']['total']
        wins = merged['overall']['wins']
        merged['overall']['win_rate'] = round(
            (wins / total * 100) if total > 0 else 0.0, 1
        )

    if 'by_type' in merged:
        for opp_type in merged['by_type']:
            total = merged['by_type'][opp_type]['total']
            wins = merged['by_type'][opp_type]['wins']
            merged['by_type'][opp_type]['win_rate'] = round(
                (wins / total * 100) if total > 0 else 0.0, 1
            )

    if 'by_rule' in merged:
        for rule_slug in merged['by_rule']:
            total = merged['by_rule'][rule_slug]['total']
            wins = merged['by_rule'][rule_slug]['wins']
            merged['by_rule'][rule_slug]['win_rate'] = round(
                (wins / total * 100) if total > 0 else 0.0, 1
            )

    return merged


async def analyze_all_leagues(
    season: int | None = None,
    start_round: int = 6,
    rounds_back: int = 5,
) -> dict[str, Any]:
    """Analyze historical matches for all leagues in LEAGUES_OF_INTEREST.

    Args:
        season: Season year (e.g., 2024). If None, only statistics are calculated.
        start_round: Starting round number (default: 6)
        rounds_back: Number of previous rounds to use for analysis (default: 5)

    Returns:
        Dictionary with aggregated statistics from all leagues
    """
    logger.info(
        'Starting analysis for all leagues',
        season=season,
        start_round=start_round,
        rounds_back=rounds_back,
    )

    # If season is None, only get statistics for all seasons
    if season is None:
        logger.info('Season not provided, calculating statistics for all seasons')
        async with get_async_db_session() as stats_session:
            stats_opp_repo = BettingOpportunityRepository(stats_session)
            season_stats = await stats_opp_repo.get_betting_statistics(season=None)
            stats_by_type = (
                await stats_opp_repo.get_betting_statistics_by_opportunity_type(
                    season=None
                )
            )
            stats_by_rule = await stats_opp_repo.get_betting_statistics_by_rule(
                season=None
            )
            stats_by_period = (
                await stats_opp_repo.get_betting_statistics_by_season_period(
                    season=None
                )
            )
            return {
                'total_rounds_processed': 0,
                'total_matches_analyzed': 0,
                'total_opportunities_created': 0,
                'season_statistics': season_stats,
                'season_statistics_by_type': stats_by_type,
                'season_statistics_by_rule': stats_by_rule,
                'season_statistics_by_period': stats_by_period,
                'leagues_processed': 0,
            }

    all_stats = []
    total_rounds = 0
    total_matches = 0
    total_opportunities = 0

    # Iterate over all countries and leagues
    for country_enum, league_enums in LEAGUES_OF_INTEREST.items():
        country = country_enum.value
        for league_enum in league_enums:
            league_name = league_enum.value
            logger.info(
                f'Processing {country} - {league_name}',
                country=country,
                league=league_name,
            )

            try:
                league_stats = await analyze_historical_matches(
                    country=country,
                    league_name=league_name,
                    season=season,
                    start_round=start_round,
                    rounds_back=rounds_back,
                )
                all_stats.append(league_stats)

                # Aggregate processing statistics
                total_rounds += league_stats.get('total_rounds_processed', 0)
                total_matches += league_stats.get('total_matches_analyzed', 0)
                total_opportunities += league_stats.get(
                    'total_opportunities_created', 0
                )

                logger.info(
                    f'Completed {country} - {league_name}',
                    rounds=league_stats.get('total_rounds_processed', 0),
                    matches=league_stats.get('total_matches_analyzed', 0),
                    opportunities=league_stats.get('total_opportunities_created', 0),
                )
            except Exception as e:
                logger.error(
                    f'Error processing {country} - {league_name}: {e}',
                    country=country,
                    league=league_name,
                )
                continue

    # Merge statistics from all leagues
    merged_stats = _merge_statistics(all_stats)

    # Get statistics by period (aggregated across all leagues)
    async with get_async_db_session() as period_session:
        period_opp_repo = BettingOpportunityRepository(period_session)
        stats_by_period = (
            await period_opp_repo.get_betting_statistics_by_season_period(
                season=season
            )
        )

    result = {
        'total_rounds_processed': total_rounds,
        'total_matches_analyzed': total_matches,
        'total_opportunities_created': total_opportunities,
        'season_statistics': merged_stats.get('overall'),
        'season_statistics_by_type': merged_stats.get('by_type'),
        'season_statistics_by_rule': merged_stats.get('by_rule'),
        'season_statistics_by_period': stats_by_period,
        'leagues_processed': len(all_stats),
    }

    logger.info(
        'Analysis for all leagues completed',
        total_rounds=total_rounds,
        total_matches=total_matches,
        total_opportunities=total_opportunities,
        leagues_processed=len(all_stats),
    )

    return result


async def main():
    """Main entry point for the script"""
    parser = argparse.ArgumentParser(
        description='Analyze historical matches and create betting opportunities'
    )
    parser.add_argument(
        '--all-leagues',
        action='store_true',
        help='Analyze all leagues from LEAGUES_OF_INTEREST',
    )
    parser.add_argument(
        '--country',
        type=str,
        help='Country name (e.g., England). Required if --all-leagues is not set.',
    )
    parser.add_argument(
        '--league',
        type=str,
        help='League name (e.g., "Premier League"). Required if --all-leagues is not set.',
    )
    parser.add_argument(
        '--season',
        type=int,
        help='Season year (e.g., 2024). If not provided, only statistics are calculated for all seasons.',
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

    # Validate arguments
    if args.all_leagues:
        stats = await analyze_all_leagues(
            season=args.season,
            start_round=args.start_round,
            rounds_back=args.rounds_back,
        )
    else:
        if not args.country or not args.league:
            parser.error(
                '--country and --league are required when --all-leagues is not set'
            )
        stats = await analyze_historical_matches(
            country=args.country,
            league_name=args.league,
            season=args.season,
            start_round=args.start_round,
            rounds_back=args.rounds_back,
        )

    print('\n=== Analysis Summary ===')
    if args.all_leagues:
        print(f'Leagues processed: {stats.get("leagues_processed", 0)}')
    print(f'Total rounds processed: {stats.get("total_rounds_processed", 0)}')
    print(f'Total matches analyzed: {stats.get("total_matches_analyzed", 0)}')
    print(f'Total opportunities created: {stats.get("total_opportunities_created", 0)}')
    if stats.get('updated_outcomes') is not None:
        print(f'Updated outcomes: {stats.get("updated_outcomes", 0)}')

    # Display opportunities by round only for single league analysis
    if not args.all_leagues and stats.get('opportunities_by_round'):
        print('\n=== Opportunities by Round ===')
        for round_num, count in sorted(stats.get('opportunities_by_round', {}).items()):
            print(f'  Round {round_num}: {count} opportunities')

    # Display season statistics
    season_stats = stats.get('season_statistics')
    season_label = f'{args.season} Season' if args.season else 'All Seasons'
    if season_stats:
        print(f'\n=== Betting Statistics for {season_label} ===')
        print(f'Total opportunities: {season_stats["total"]}')
        print(f'Wins: {season_stats["wins"]}')
        print(f'Losses: {season_stats["losses"]}')
        print(f'Win rate: {season_stats["win_rate"]}%')
    else:
        print(f'\n=== Betting Statistics for {season_label} ===')
        print('Statistics not available')

    # Display statistics by opportunity type
    stats_by_type = stats.get('season_statistics_by_type')
    if stats_by_type:
        print(f'\n=== Betting Statistics by Opportunity Type for {season_label} ===')
        for opp_type, type_stats in sorted(stats_by_type.items()):
            opp_type_display = opp_type.replace('_', ' ').title()
            print(f'\n{opp_type_display}:')
            print(f'  Total opportunities: {type_stats["total"]}')
            print(f'  Wins: {type_stats["wins"]}')
            print(f'  Losses: {type_stats["losses"]}')
            print(f'  Win rate: {type_stats["win_rate"]}%')
    else:
        print(f'\n=== Betting Statistics by Opportunity Type for {season_label} ===')
        print('Statistics not available')

    # Display statistics by rule (to identify which rules are more efficient)
    stats_by_rule = stats.get('season_statistics_by_rule')
    if stats_by_rule:
        print(f'\n=== Betting Statistics by Rule for {season_label} ===')
        # Sort by win_rate descending to show most efficient rules first
        sorted_rules = sorted(
            stats_by_rule.items(),
            key=lambda x: x[1]['win_rate'],
            reverse=True,
        )
        for rule_slug, rule_stats in sorted_rules:
            rule_name = rule_stats.get('rule_name', rule_slug)
            print(f'\n{rule_name} ({rule_slug}):')
            print(f'  Total opportunities: {rule_stats["total"]}')
            print(f'  Wins: {rule_stats["wins"]}')
            print(f'  Losses: {rule_stats["losses"]}')
            print(f'  Win rate: {rule_stats["win_rate"]}%')
    else:
        print(f'\n=== Betting Statistics by Rule for {season_label} ===')
        print('Statistics not available')

    # Display statistics by season period (early/mid/late)
    stats_by_period = stats.get('season_statistics_by_period')
    if stats_by_period:
        print(f'\n=== Betting Statistics by Season Period for {season_label} ===')
        period_names = {
            'early': 'Early Season (First Third)',
            'mid': 'Mid Season (Second Third)',
            'late': 'Late Season (Last Third)',
        }
        for period in ['early', 'mid', 'late']:
            period_stats = stats_by_period.get(period)
            if period_stats and period_stats['total'] > 0:
                print(f'\n{period_names[period]}:')
                print(f'  Total opportunities: {period_stats["total"]}')
                print(f'  Wins: {period_stats["wins"]}')
                print(f'  Losses: {period_stats["losses"]}')
                print(f'  Win rate: {period_stats["win_rate"]}%')
    else:
        print(f'\n=== Betting Statistics by Season Period for {season_label} ===')
        print('Statistics not available')


if __name__ == '__main__':
    asyncio.run(main())
