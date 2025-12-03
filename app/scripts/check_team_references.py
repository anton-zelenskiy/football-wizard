"""Script to check if a team is referenced in other tables before deletion."""
import asyncio
from sqlalchemy import select, func
from sqlalchemy.orm import selectinload

from app.db.sqlalchemy_models import Team, Match, TeamStanding, BettingOpportunity, League
from app.db.session import get_async_db_session


async def check_team_references(team_name: str):
    """Check if a team is referenced in Match, TeamStanding, or BettingOpportunity tables."""
    session = get_async_db_session()
    try:
        # Find the team with league eagerly loaded
        result = await session.execute(
            select(Team)
            .options(selectinload(Team.league))
            .where(Team.name == team_name)
        )
        team = result.scalar_one_or_none()

        if not team:
            print(f"Team '{team_name}' not found in database")
            return None

        # Get league name
        league_result = await session.execute(
            select(League).where(League.id == team.league_id)
        )
        league = league_result.scalar_one()

        print(f"\nFound team: {team.name} (ID: {team.id}, League: {league.name})")

        # Check Match references
        home_matches_result = await session.execute(
            select(func.count(Match.id)).where(Match.home_team_id == team.id)
        )
        away_matches_result = await session.execute(
            select(func.count(Match.id)).where(Match.away_team_id == team.id)
        )
        home_matches_count = home_matches_result.scalar() or 0
        away_matches_count = away_matches_result.scalar() or 0
        total_matches = home_matches_count + away_matches_count

        print(f"\nMatch references:")
        print(f"  - Home matches: {home_matches_count}")
        print(f"  - Away matches: {away_matches_count}")
        print(f"  - Total matches: {total_matches}")

        # Check TeamStanding references
        standings_result = await session.execute(
            select(func.count(TeamStanding.id)).where(TeamStanding.team_id == team.id)
        )
        standings_count = standings_result.scalar() or 0
        print(f"\nTeamStanding references: {standings_count}")

        # Check BettingOpportunity references (through Match)
        if total_matches > 0:
            betting_opps_result = await session.execute(
                select(func.count(BettingOpportunity.id))
                .join(Match, BettingOpportunity.match_id == Match.id)
                .where(
                    (Match.home_team_id == team.id) | (Match.away_team_id == team.id)
                )
            )
            betting_opps_count = betting_opps_result.scalar() or 0
            print(f"\nBettingOpportunity references (through matches): {betting_opps_count}")
        else:
            print(f"\nBettingOpportunity references: 0 (no matches)")

        # Summary
        print(f"\n{'='*50}")
        if total_matches == 0 and standings_count == 0:
            print(f"✅ Team '{team_name}' can be safely deleted (no references found)")
            return team
        else:
            print(f"❌ Team '{team_name}' CANNOT be safely deleted (has references)")
            print(f"   Please handle references before deletion")
            return None
    finally:
        await session.close()


if __name__ == '__main__':
    asyncio.run(check_team_references('R. Oviedo'))
