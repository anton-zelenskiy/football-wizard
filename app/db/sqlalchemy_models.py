from datetime import datetime
import json

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    create_engine,
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
import structlog

from app.bet_rules.bet_rules import Bet
from app.bet_rules.bet_rules import BettingOpportunity as BettingOpportunityDomain
from app.bet_rules.structures import BetOutcome, MatchData, MatchSummary


logger = structlog.get_logger()

# SQLAlchemy base class
Base = declarative_base()

# Sync engine for compatibility
engine = create_engine('sqlite:///football.db', echo=False)


class League(Base):
    """SQLAlchemy League model"""

    __tablename__ = 'league'

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String, nullable=False)
    country = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)

    # Relationships
    teams = relationship('Team', back_populates='league')
    matches = relationship('Match', back_populates='league')
    team_standings = relationship('TeamStanding', back_populates='league')

    def __str__(self):
        return f'{self.name} ({self.country})'


class Team(Base):
    """SQLAlchemy Team model

    Represents a team with basic information. Season-specific statistics
    are stored in TeamStanding model.
    """

    __tablename__ = 'team'

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String, nullable=False)
    league_id = Column(Integer, ForeignKey('league.id'), nullable=False)
    # Legacy fields - kept for backward compatibility but should use TeamStanding
    rank = Column(Integer, nullable=True)
    games_played = Column(Integer, default=0)
    wins = Column(Integer, default=0)
    draws = Column(Integer, default=0)
    losses = Column(Integer, default=0)
    goals_scored = Column(Integer, default=0)
    goals_conceded = Column(Integer, default=0)
    points = Column(Integer, default=0)
    coach = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)

    # Relationships
    league = relationship('League', back_populates='teams')
    home_matches = relationship(
        'Match', foreign_keys='Match.home_team_id', back_populates='home_team'
    )
    away_matches = relationship(
        'Match', foreign_keys='Match.away_team_id', back_populates='away_team'
    )
    standings = relationship('TeamStanding', back_populates='team')

    def __str__(self):
        return f'{self.name}'


class TeamStanding(Base):
    """SQLAlchemy TeamStanding model for season-specific team statistics

    Stores team statistics for a specific season. This allows tracking
    historical data without overwriting current season statistics.
    """

    __tablename__ = 'team_standing'

    id = Column(Integer, primary_key=True, autoincrement=True)
    team_id = Column(Integer, ForeignKey('team.id'), nullable=False)
    league_id = Column(Integer, ForeignKey('league.id'), nullable=False)
    season = Column(Integer, nullable=False)
    rank = Column(Integer, nullable=True)
    games_played = Column(Integer, default=0)
    wins = Column(Integer, default=0)
    draws = Column(Integer, default=0)
    losses = Column(Integer, default=0)
    goals_scored = Column(Integer, default=0)
    goals_conceded = Column(Integer, default=0)
    points = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)

    # Unique constraint: one standing per team/league/season combination
    __table_args__ = (
        UniqueConstraint(
            'team_id', 'league_id', 'season', name='uq_team_league_season'
        ),
    )

    # Relationships
    team = relationship('Team', back_populates='standings')
    league = relationship('League')

    def __str__(self):
        return (
            f'{self.team.name} - {self.league.name} ({self.season}) - Rank {self.rank}'
        )


class Match(Base):
    """SQLAlchemy Match model"""

    __tablename__ = 'match'

    id = Column(Integer, primary_key=True, autoincrement=True)
    league_id = Column(Integer, ForeignKey('league.id'), nullable=False)
    home_team_id = Column(Integer, ForeignKey('team.id'), nullable=False)
    away_team_id = Column(Integer, ForeignKey('team.id'), nullable=False)
    home_score = Column(Integer, nullable=True)
    away_score = Column(Integer, nullable=True)
    match_date = Column(DateTime, nullable=False)
    season = Column(Integer, nullable=False)
    round = Column(Integer, nullable=True)
    status = Column(String, default='scheduled')
    minute = Column(Integer, nullable=True)
    red_cards_home = Column(Integer, default=0)
    red_cards_away = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)

    # Relationships
    league = relationship('League', back_populates='matches', lazy='selectin')
    home_team = relationship(
        'Team',
        foreign_keys=[home_team_id],
        back_populates='home_matches',
        lazy='selectin',
    )
    away_team = relationship(
        'Team',
        foreign_keys=[away_team_id],
        back_populates='away_matches',
        lazy='selectin',
    )
    betting_opportunities = relationship('BettingOpportunity', back_populates='match')

    def __str__(self):
        return f'{self.home_team.name} - {self.away_team.name} ({self.status})'

    def to_pydantic(self):
        """Convert SQLAlchemy Match model to Pydantic MatchData"""
        return MatchData(
            id=self.id,
            home_team_id=self.home_team_id,
            away_team_id=self.away_team_id,
            home_score=self.home_score,
            away_score=self.away_score,
            match_date=self.match_date.isoformat() if self.match_date else None,
            status=self.status,
        )


class BettingOpportunity(Base):
    """SQLAlchemy BettingOpportunity model"""

    __tablename__ = 'betting_opportunity'

    id = Column(Integer, primary_key=True, autoincrement=True)
    match_id = Column(Integer, ForeignKey('match.id'), nullable=True)
    rule_slug = Column(String, nullable=False)
    confidence_score = Column(Float, default=0.0)
    details = Column(Text, nullable=True)  # JSON string
    outcome = Column(
        String, nullable=False, default=BetOutcome.UNKNOWN.value
    )  # win, lose, unknown
    created_at = Column(DateTime, default=datetime.now)

    # Relationships
    match = relationship(
        'Match', back_populates='betting_opportunities', lazy='selectin'
    )
    notifications = relationship('NotificationLog', back_populates='opportunity')

    def __str__(self):
        return f'{self.match.home_team.name} - {self.match.away_team.name}; {self.rule_slug}; {self.outcome}'

    def get_details(self) -> dict:
        """Get details as dictionary"""
        if not self.details:
            return {}
        try:
            return json.loads(self.details)
        except (json.JSONDecodeError, TypeError):
            return {}

    def to_domain(self):
        """Convert BettingOpportunity database model to Bet domain model"""
        details = self.get_details()

        match_summary = MatchSummary.from_match(self.match)

        opportunity = BettingOpportunityDomain(
            slug=self.rule_slug,
            confidence=self.confidence_score,
            team_analyzed=details.get('team_analyzed', 'Unknown'),
            details=details,
        )

        return Bet(match=match_summary, opportunity=opportunity)


class TelegramUser(Base):
    """SQLAlchemy TelegramUser model"""

    __tablename__ = 'telegramuser'

    id = Column(Integer, primary_key=True, autoincrement=True)
    telegram_id = Column(Integer, unique=True, nullable=False)
    username = Column(String, nullable=True)
    first_name = Column(String, nullable=True)
    last_name = Column(String, nullable=True)
    is_active = Column(Boolean, default=True)
    daily_notifications = Column(Boolean, default=True)
    live_notifications = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)

    # Relationships
    notifications = relationship('NotificationLog', back_populates='user')

    def __str__(self):
        return f'{self.username}: {self.telegram_id}'


class NotificationLog(Base):
    """SQLAlchemy NotificationLog model"""

    __tablename__ = 'notificationlog'

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey('telegramuser.id'), nullable=False)
    opportunity_id = Column(
        Integer, ForeignKey('betting_opportunity.id'), nullable=True
    )
    message = Column(Text, nullable=False)
    sent_at = Column(DateTime, default=datetime.now)
    success = Column(Boolean, default=True)
    error_message = Column(Text, nullable=True)

    # Relationships
    user = relationship('TelegramUser', back_populates='notifications', lazy='selectin')
    opportunity = relationship(
        'BettingOpportunity', back_populates='notifications', lazy='selectin'
    )

    def __str__(self):
        return f'<NotificationLog(id={self.id}, user_id={self.user_id}, success={self.success})>'


def create_tables():
    """Create all SQLAlchemy tables"""
    Base.metadata.create_all(bind=engine)
    logger.info('SQLAlchemy tables created')
