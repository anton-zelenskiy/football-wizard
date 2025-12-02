from datetime import datetime
import json

from sqlalchemy import and_, case, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
import structlog

from app.bet_rules.bet_rules import Bet
from app.bet_rules.structures import BetOutcome, LeagueData, MatchSummary, TeamData
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

    async def get_betting_statistics(self) -> dict[str, int | float]:
        """Return counts for total, wins, losses, and win_rate (%)."""
        result = await self.session.execute(
            select(
                func.count(BettingOpportunity.id),
                func.sum(
                    case(
                        (BettingOpportunity.outcome == BetOutcome.WIN.value, 1), else_=0
                    )
                ),
                func.sum(
                    case(
                        (BettingOpportunity.outcome == BetOutcome.LOSE.value, 1),
                        else_=0,
                    )
                ),
            ).where(BettingOpportunity.outcome != BetOutcome.UNKNOWN.value)
        )
        total, wins, losses = result.one()
        total = int(total or 0)
        wins = int(wins or 0)
        losses = int(losses or 0)
        win_rate = round((wins / total * 100) if total > 0 else 0.0, 1)
        return {'total': total, 'wins': wins, 'losses': losses, 'win_rate': win_rate}

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

        # Build MatchSummary compatible with rules
        # Calculate teams count from league relationship
        teams_count = len(match.league.teams) if match.league.teams else 0

        match_summary = MatchSummary(
            match_id=match.id,
            home_team_data=TeamData(
                id=match.home_team.id,
                name=match.home_team.name,
                rank=match.home_team.rank,
            ),
            away_team_data=TeamData(
                id=match.away_team.id,
                name=match.away_team.name,
                rank=match.away_team.rank,
            ),
            league=LeagueData(
                id=match.league.id,
                name=match.league.name,
                teams_count=teams_count,
            ),
            country=match.league.country,
            match_date=match.match_date.strftime('%Y-%m-%d %H:%M')
            if match.match_date
            else None,
            home_score=match.home_score,
            away_score=match.away_score,
        )

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
        pending = result.scalars().all()

        updated = 0
        for opp in pending:
            outcome = await self._determine_betting_outcome(opp, opp.match)
            if outcome is not None:
                opp.outcome = outcome.value
                updated += 1
        if updated:
            await self.session.commit()
        logger.info('Updated betting outcomes', count=updated)
        return updated
