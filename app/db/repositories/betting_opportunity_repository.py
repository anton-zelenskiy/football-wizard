from datetime import datetime
import json

from sqlalchemy import and_, case, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
import structlog

from app.bet_rules.bet_rules import Bet
from app.bet_rules.structures import BetOutcome, MatchSummary, OpportunityType
from app.db.sqlalchemy_models import BettingOpportunity, Match

from .base_repository import BaseRepository


logger = structlog.get_logger()


class BettingOpportunityRepository(BaseRepository[BettingOpportunity]):
    """Repository for BettingOpportunity operations using async SQLAlchemy."""

    def __init__(self, session: AsyncSession):
        super().__init__(session, BettingOpportunity)

    async def get_by_id(self, id: int):
        """Get entity by ID"""
        try:
            result = await self.session.execute(
                select(self.model_class)
                .options(
                    selectinload(BettingOpportunity.match).selectinload(
                        Match.home_team
                    ),
                    selectinload(BettingOpportunity.match).selectinload(
                        Match.away_team
                    ),
                    selectinload(BettingOpportunity.match).selectinload(Match.league),
                )
                .join(Match, BettingOpportunity.match_id == Match.id)
                .where(self.model_class.id == id)
            )
            return result.scalar_one_or_none()
        except Exception as e:
            logger.error(f'Error getting {self.model_class.__name__} by ID {id}: {e}')
            raise

    async def _find_existing_opportunity(
        self, match_id: int | None, rule_slug: str
    ) -> BettingOpportunity | None:
        if not match_id:
            return None
        result = await self.session.execute(
            select(BettingOpportunity).where(
                and_(
                    BettingOpportunity.match_id == match_id,
                    BettingOpportunity.rule_slug == rule_slug,
                    BettingOpportunity.outcome == BetOutcome.UNKNOWN.value,
                )
            )
        )
        return result.scalar_one_or_none()

    async def _find_existing_opportunity_by_bet(
        self, opportunity: Bet
    ) -> BettingOpportunity | None:
        """Find existing betting opportunity by match_id and rule_slug from Bet object"""
        if not opportunity.match_id:
            return None
        result = await self.session.execute(
            select(BettingOpportunity).where(
                and_(
                    BettingOpportunity.match_id == opportunity.match_id,
                    BettingOpportunity.rule_slug == opportunity.slug,
                    BettingOpportunity.outcome == BetOutcome.UNKNOWN.value,
                )
            )
        )
        return result.scalar_one_or_none()

    async def save_opportunity(self, opportunity: Bet) -> BettingOpportunity:
        """Save betting opportunity to database with duplicate prevention."""
        # Add team_analyzed to details for outcome determination
        details = opportunity.details.copy()
        details['team_analyzed'] = opportunity.team_analyzed

        # Prevent duplicates for pending opportunities
        existing = await self._find_existing_opportunity_by_bet(opportunity)
        if existing:
            logger.debug(
                'Opportunity already exists',
                match_id=opportunity.match_id,
                rule=opportunity.slug,
            )
            return existing

        record = BettingOpportunity(
            match_id=opportunity.match_id,
            rule_slug=opportunity.slug,
            confidence_score=opportunity.confidence,
            details=json.dumps(details),
            outcome=BetOutcome.UNKNOWN.value,
            created_at=datetime.now(),
        )
        self.session.add(record)
        await self.session.commit()
        await self.session.refresh(record)
        logger.info(
            'Created new betting opportunity', id=record.id, rule=opportunity.slug
        )
        return record

    async def get_active_betting_opportunities(self) -> list[BettingOpportunity]:
        """Get active (pending) opportunities for future matches."""
        now = datetime.now()
        result = await self.session.execute(
            select(BettingOpportunity)
            .options(
                selectinload(BettingOpportunity.match).selectinload(Match.home_team),
                selectinload(BettingOpportunity.match).selectinload(Match.away_team),
                selectinload(BettingOpportunity.match).selectinload(Match.league),
            )
            .join(Match, BettingOpportunity.match_id == Match.id)
            .where(
                and_(
                    BettingOpportunity.outcome == BetOutcome.UNKNOWN.value,
                    Match.match_date > now,
                )
            )
            .order_by(BettingOpportunity.confidence_score.desc())
        )
        return result.scalars().all()

    async def get_completed_betting_opportunities(
        self, limit: int = 50
    ) -> list[BettingOpportunity]:
        """Get completed opportunities (have an outcome) for past matches."""
        now = datetime.now()
        result = await self.session.execute(
            select(BettingOpportunity)
            .options(
                selectinload(BettingOpportunity.match).selectinload(Match.home_team),
                selectinload(BettingOpportunity.match).selectinload(Match.away_team),
                selectinload(BettingOpportunity.match).selectinload(Match.league),
            )
            .join(Match, BettingOpportunity.match_id == Match.id)
            .where(
                and_(
                    BettingOpportunity.outcome != BetOutcome.UNKNOWN.value,
                    Match.match_date <= now,
                )
            )
            .order_by(Match.match_date.desc())
            .limit(limit)
        )
        return result.scalars().all()

    async def get_betting_statistics(
        self, season: int | None = None
    ) -> dict[str, int | float]:
        """Return counts for total, wins, losses, and win_rate (%).

        Optionally filters by season and excludes deprecated rules such as
        'live_red_card'.
        """
        try:
            query = (
                select(
                    func.count(BettingOpportunity.id),
                    func.sum(
                        case(
                            (BettingOpportunity.outcome == BetOutcome.WIN.value, 1),
                            else_=0,
                        )
                    ),
                    func.sum(
                        case(
                            (BettingOpportunity.outcome == BetOutcome.LOSE.value, 1),
                            else_=0,
                        )
                    ),
                )
                .select_from(BettingOpportunity)
                .join(Match, BettingOpportunity.match_id == Match.id)
                .where(
                    and_(
                        BettingOpportunity.outcome != BetOutcome.UNKNOWN.value,
                        BettingOpportunity.rule_slug != 'live_red_card',
                    )
                )
            )

            if season is not None:
                query = query.where(Match.season == season)

            result = await self.session.execute(query)
            total, wins, losses = result.one()
            total = int(total or 0)
            wins = int(wins or 0)
            losses = int(losses or 0)
            win_rate = round((wins / total * 100) if total > 0 else 0.0, 1)
            return {
                'total': total,
                'wins': wins,
                'losses': losses,
                'win_rate': win_rate,
            }
        except Exception as e:
            logger.error(f'Error getting betting statistics: {e}', season=season)
            return {'total': 0, 'wins': 0, 'losses': 0, 'win_rate': 0.0}

    async def get_betting_statistics_by_opportunity_type(
        self, season: int | None = None
    ) -> dict[str, dict[str, int | float]]:
        """Return statistics grouped by opportunity_type.

        Returns a dictionary where keys are opportunity_type values and values
        are dictionaries with 'total', 'wins', 'losses', and 'win_rate' keys.

        Optionally filters by season and excludes deprecated rules such as
        'live_red_card'.
        """
        from app.bet_rules.rule_engine import BettingRulesEngine

        try:
            # Query opportunities grouped by rule_slug
            query = (
                select(
                    BettingOpportunity.rule_slug,
                    func.count(BettingOpportunity.id).label('total'),
                    func.sum(
                        case(
                            (BettingOpportunity.outcome == BetOutcome.WIN.value, 1),
                            else_=0,
                        )
                    ).label('wins'),
                    func.sum(
                        case(
                            (BettingOpportunity.outcome == BetOutcome.LOSE.value, 1),
                            else_=0,
                        )
                    ).label('losses'),
                )
                .select_from(BettingOpportunity)
                .join(Match, BettingOpportunity.match_id == Match.id)
                .where(
                    and_(
                        BettingOpportunity.outcome != BetOutcome.UNKNOWN.value,
                        BettingOpportunity.rule_slug != 'live_red_card',
                    )
                )
                .group_by(BettingOpportunity.rule_slug)
            )

            if season is not None:
                query = query.where(Match.season == season)

            result = await self.session.execute(query)
            rows = result.all()

            # Map rule_slug to opportunity_type and aggregate statistics
            engine = BettingRulesEngine()
            stats_by_type: dict[str, dict[str, int | float]] = {}

            for row in rows:
                rule_slug, total, wins, losses = row
                total = int(total or 0)
                wins = int(wins or 0)
                losses = int(losses or 0)

                # Get opportunity_type from rule
                rule = engine.get_rule_by_slug(rule_slug)
                if rule:
                    opp_type = rule.opportunity_type.value
                else:
                    # Default to historical_analysis if rule not found
                    opp_type = OpportunityType.HISTORICAL_ANALYSIS.value

                # Aggregate statistics by opportunity_type
                if opp_type not in stats_by_type:
                    stats_by_type[opp_type] = {
                        'total': 0,
                        'wins': 0,
                        'losses': 0,
                        'win_rate': 0.0,
                    }

                stats_by_type[opp_type]['total'] += total
                stats_by_type[opp_type]['wins'] += wins
                stats_by_type[opp_type]['losses'] += losses

            # Calculate win_rate for each opportunity_type
            for opp_type in stats_by_type:
                total = stats_by_type[opp_type]['total']
                wins = stats_by_type[opp_type]['wins']
                stats_by_type[opp_type]['win_rate'] = round(
                    (wins / total * 100) if total > 0 else 0.0, 1
                )

            return stats_by_type
        except Exception as e:
            logger.error(
                f'Error getting betting statistics by opportunity type: {e}',
                season=season,
            )
            return {}

    async def get_betting_statistics_by_rule(
        self, season: int | None = None
    ) -> dict[str, dict[str, int | float]]:
        """Return statistics grouped by rule_slug.

        Returns a dictionary where keys are rule_slug values and values
        are dictionaries with 'total', 'wins', 'losses', and 'win_rate' keys.

        Optionally filters by season and excludes deprecated rules such as
        'live_red_card'.
        """
        from app.bet_rules.rule_engine import BettingRulesEngine

        try:
            # Query opportunities grouped by rule_slug
            query = (
                select(
                    BettingOpportunity.rule_slug,
                    func.count(BettingOpportunity.id).label('total'),
                    func.sum(
                        case(
                            (BettingOpportunity.outcome == BetOutcome.WIN.value, 1),
                            else_=0,
                        )
                    ).label('wins'),
                    func.sum(
                        case(
                            (BettingOpportunity.outcome == BetOutcome.LOSE.value, 1),
                            else_=0,
                        )
                    ).label('losses'),
                )
                .select_from(BettingOpportunity)
                .join(Match, BettingOpportunity.match_id == Match.id)
                .where(
                    and_(
                        BettingOpportunity.outcome != BetOutcome.UNKNOWN.value,
                        BettingOpportunity.rule_slug != 'live_red_card',
                    )
                )
                .group_by(BettingOpportunity.rule_slug)
            )

            if season is not None:
                query = query.where(Match.season == season)

            result = await self.session.execute(query)
            rows = result.all()

            # Build statistics by rule_slug
            engine = BettingRulesEngine()
            stats_by_rule: dict[str, dict[str, int | float]] = {}

            for row in rows:
                rule_slug, total, wins, losses = row
                total = int(total or 0)
                wins = int(wins or 0)
                losses = int(losses or 0)

                # Get rule name for display
                rule = engine.get_rule_by_slug(rule_slug)
                rule_name = rule.name if rule else rule_slug

                stats_by_rule[rule_slug] = {
                    'rule_name': rule_name,
                    'total': total,
                    'wins': wins,
                    'losses': losses,
                    'win_rate': round((wins / total * 100) if total > 0 else 0.0, 1),
                }

            return stats_by_rule
        except Exception as e:
            logger.error(
                f'Error getting betting statistics by rule: {e}',
                season=season,
            )
            return {}

    async def get_betting_statistics_by_season_period(
        self, season: int | None = None
    ) -> dict[str, dict[str, int | float]]:
        """Return statistics grouped by season period (early/mid/late).

        Divides the season into thirds based on round numbers:
        - Early: first third of rounds
        - Mid: second third of rounds
        - Late: last third of rounds

        Returns a dictionary where keys are period names and values
        are dictionaries with 'total', 'wins', 'losses', and 'win_rate' keys.

        Optionally filters by season and excludes deprecated rules such as
        'live_red_card'.
        """
        from sqlalchemy import text

        try:
            # First, get the max round for each league/season to determine thirds
            if season is not None:
                max_rounds_query = text(
                    """
                    SELECT DISTINCT m.league_id, MAX(m.round) as max_round
                    FROM match m
                    WHERE m.season = :season
                    GROUP BY m.league_id
                """
                )
                result = await self.session.execute(
                    max_rounds_query, {'season': season}
                )
                max_rounds_by_league = {row[0]: row[1] for row in result.all()}
            else:
                max_rounds_query = text(
                    """
                    SELECT DISTINCT m.league_id, m.season, MAX(m.round) as max_round
                    FROM match m
                    GROUP BY m.league_id, m.season
                """
                )
                result = await self.session.execute(max_rounds_query)
                max_rounds_by_league = {
                    (row[0], row[1]): row[2] for row in result.all()
                }

            # Query opportunities with round information
            base_query = """
                SELECT
                    bo.outcome,
                    m.round,
                    m.league_id,
                    m.season
                FROM betting_opportunity bo
                JOIN match m ON bo.match_id = m.id
                WHERE bo.outcome != 'unknown'
                AND bo.rule_slug != 'live_red_card'
            """

            if season is not None:
                query = text(f'{base_query} AND m.season = :season')
                result = await self.session.execute(query, {'season': season})
            else:
                query = text(base_query)
                result = await self.session.execute(query)

            rows = result.all()

            # Group by period
            period_stats: dict[str, dict[str, int]] = {
                'early': {'total': 0, 'wins': 0, 'losses': 0},
                'mid': {'total': 0, 'wins': 0, 'losses': 0},
                'late': {'total': 0, 'wins': 0, 'losses': 0},
            }

            for row in rows:
                outcome, round_num, league_id, match_season = row

                if round_num is None:
                    continue

                # Determine max round for this league/season
                if season is not None:
                    max_round = max_rounds_by_league.get(league_id)
                else:
                    max_round = max_rounds_by_league.get((league_id, match_season))

                if max_round is None or max_round == 0:
                    continue

                # Determine period based on round number
                third = max_round / 3
                if round_num <= third:
                    period = 'early'
                elif round_num <= third * 2:
                    period = 'mid'
                else:
                    period = 'late'

                period_stats[period]['total'] += 1
                if outcome == BetOutcome.WIN.value:
                    period_stats[period]['wins'] += 1
                elif outcome == BetOutcome.LOSE.value:
                    period_stats[period]['losses'] += 1

            # Calculate win rates
            result_stats: dict[str, dict[str, int | float]] = {}
            for period, stats in period_stats.items():
                total = stats['total']
                wins = stats['wins']
                result_stats[period] = {
                    'total': total,
                    'wins': wins,
                    'losses': stats['losses'],
                    'win_rate': round((wins / total * 100) if total > 0 else 0.0, 1),
                }

            return result_stats
        except Exception as e:
            logger.error(
                f'Error getting betting statistics by season period: {e}',
                season=season,
            )
            return {}

    async def _determine_betting_outcome(
        self, opportunity: BettingOpportunity, match: Match
    ) -> BetOutcome | None:
        """Determine outcome using rules engine for finished matches only."""
        from app.bet_rules.rule_engine import BettingRulesEngine

        # Only evaluate completed matches
        if (
            match.status != 'finished'
            or match.home_score is None
            or match.away_score is None
        ):
            return None

        # Get team ranks from TeamStanding
        from app.db.repositories.team_standing_repository import TeamStandingRepository

        home_rank = None
        away_rank = None
        if match.season:
            standing_repo = TeamStandingRepository(self.session)
            home_standing = await standing_repo.get_by_team_league_season(
                match.home_team.id, match.league.id, match.season
            )
            away_standing = await standing_repo.get_by_team_league_season(
                match.away_team.id, match.league.id, match.season
            )
            if home_standing:
                home_rank = home_standing.rank
            if away_standing:
                away_rank = away_standing.rank

        # Build MatchSummary compatible with rules
        match_summary = MatchSummary.from_match(match, home_rank, away_rank)

        # Extract team_analyzed from JSON details
        try:
            details = json.loads(opportunity.details) if opportunity.details else {}
        except Exception:
            details = {}
        team_analyzed = details.get('team_analyzed')

        engine = BettingRulesEngine()
        rule = engine.get_rule_by_slug(opportunity.rule_slug)
        if not rule:
            return None
        return rule.determine_outcome(match_summary, team_analyzed)

    async def update_betting_outcomes(self) -> int:
        """Evaluate and fill outcomes for pending opportunities when matches finished."""
        # Select pending opportunities with finished matches having scores
        result = await self.session.execute(
            select(BettingOpportunity)
            .options(
                selectinload(BettingOpportunity.match).selectinload(Match.home_team),
                selectinload(BettingOpportunity.match).selectinload(Match.away_team),
                selectinload(BettingOpportunity.match).selectinload(Match.league),
            )
            .join(Match, BettingOpportunity.match_id == Match.id)
            .where(
                and_(
                    BettingOpportunity.outcome == BetOutcome.UNKNOWN.value,
                    Match.status == 'finished',
                    Match.home_score.is_not(None),
                    Match.away_score.is_not(None),
                )
            )
        )
        pending = list(result.scalars().all())

        updated = 0
        for opp in pending:
            # Ensure match relationship is accessible
            match = opp.match
            if not match:
                logger.warning(f'Match not found for opportunity {opp.id}')
                continue

            outcome = await self._determine_betting_outcome(opp, match)
            if outcome is not None:
                opp.outcome = outcome.value
                updated += 1

        if updated:
            await self.session.commit()
        logger.info('Updated betting outcomes', count=updated)
        return updated
