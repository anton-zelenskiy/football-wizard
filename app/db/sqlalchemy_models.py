from datetime import datetime

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    create_engine,
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
import structlog


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

    def __repr__(self):
        return f"<League(id={self.id}, name='{self.name}', country='{self.country}')>"


class Team(Base):
    """SQLAlchemy Team model"""

    __tablename__ = 'team'

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String, nullable=False)
    league_id = Column(Integer, ForeignKey('league.id'), nullable=False)
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

    # Relationships
    league = relationship('League', back_populates='teams')
    home_matches = relationship(
        'Match', foreign_keys='Match.home_team_id', back_populates='home_team'
    )
    away_matches = relationship(
        'Match', foreign_keys='Match.away_team_id', back_populates='away_team'
    )

    def __repr__(self):
        return f"<Team(id={self.id}, name='{self.name}', league_id={self.league_id})>"


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
    league = relationship('League', back_populates='matches')
    home_team = relationship(
        'Team', foreign_keys=[home_team_id], back_populates='home_matches'
    )
    away_team = relationship(
        'Team', foreign_keys=[away_team_id], back_populates='away_matches'
    )
    betting_opportunities = relationship('BettingOpportunity', back_populates='match')

    def __repr__(self):
        return f"<Match(id={self.id}, home_team_id={self.home_team_id}, away_team_id={self.away_team_id}, status='{self.status}')>"

    def to_pydantic(self):
        """Convert SQLAlchemy Match model to Pydantic MatchData"""
        from app.bet_rules.team_analysis import MatchData

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

    __tablename__ = 'BettingOpportunity'

    id = Column(Integer, primary_key=True, autoincrement=True)
    match_id = Column(Integer, ForeignKey('match.id'), nullable=True)
    rule_slug = Column(String, nullable=False)
    confidence_score = Column(Float, default=0.0)
    details = Column(Text, nullable=True)  # JSON string
    outcome = Column(String, nullable=True)  # win, lose, pending, cancelled
    created_at = Column(DateTime, default=datetime.now)

    # Relationships
    match = relationship('Match', back_populates='betting_opportunities')
    notifications = relationship('NotificationLog', back_populates='opportunity')

    def __repr__(self):
        return f"<BettingOpportunity(id={self.id}, rule_slug='{self.rule_slug}', outcome='{self.outcome}')>"

    def get_details(self) -> dict:
        """Get details as dictionary"""
        if not self.details:
            return {}
        try:
            import json

            return json.loads(self.details)
        except (json.JSONDecodeError, TypeError):
            return {}

    def to_domain(self):
        """Convert BettingOpportunity database model to Bet domain model"""
        from app.bet_rules.structures import Bet, BettingOpportunity, MatchSummary

        details = self.get_details()

        match_summary = MatchSummary.from_match(self.match)

        opportunity = BettingOpportunity(
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

    def __repr__(self):
        return f"<TelegramUser(id={self.id}, telegram_id={self.telegram_id}, username='{self.username}')>"


class NotificationLog(Base):
    """SQLAlchemy NotificationLog model"""

    __tablename__ = 'notificationlog'

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey('telegramuser.id'), nullable=False)
    opportunity_id = Column(Integer, ForeignKey('BettingOpportunity.id'), nullable=True)
    message = Column(Text, nullable=False)
    sent_at = Column(DateTime, default=datetime.now)
    success = Column(Boolean, default=True)
    error_message = Column(Text, nullable=True)

    # Relationships
    user = relationship('TelegramUser', back_populates='notifications')
    opportunity = relationship('BettingOpportunity', back_populates='notifications')

    def __repr__(self):
        return f'<NotificationLog(id={self.id}, user_id={self.user_id}, success={self.success})>'


def create_tables():
    """Create all SQLAlchemy tables"""
    Base.metadata.create_all(bind=engine)
    logger.info('SQLAlchemy tables created')
