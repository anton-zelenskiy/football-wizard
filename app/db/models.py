from datetime import datetime
import json

from peewee import (
    AutoField,
    BooleanField,
    CharField,
    DateTimeField,
    FloatField,
    ForeignKeyField,
    IntegerField,
    Model,
    SqliteDatabase,
    TextField,
)
import structlog


logger = structlog.get_logger()

# SQLite database
db = SqliteDatabase('football.db')


class BaseModel(Model):
    class Meta:
        database = db


class League(BaseModel):
    id = AutoField()
    name = CharField()
    country = CharField(null=True)
    created_at = DateTimeField(default=datetime.now)
    updated_at = DateTimeField(default=datetime.now)

    class Meta:
        indexes = ((('name', 'country'), True),)


class Team(BaseModel):
    id = AutoField()
    name = CharField()
    league = ForeignKeyField(League, backref='teams')
    rank = IntegerField(null=True)
    games_played = IntegerField(default=0)
    wins = IntegerField(default=0)
    draws = IntegerField(default=0)
    losses = IntegerField(default=0)
    goals_scored = IntegerField(default=0)
    goals_conceded = IntegerField(default=0)
    points = IntegerField(default=0)
    created_at = DateTimeField(default=datetime.now)
    updated_at = DateTimeField(default=datetime.now)

    class Meta:
        indexes = ((('name', 'league'), True),)


class Match(BaseModel):
    id = AutoField()
    league = ForeignKeyField(League, backref='matches')
    home_team = ForeignKeyField(Team, backref='home_matches')
    away_team = ForeignKeyField(Team, backref='away_matches')
    home_score = IntegerField(null=True)
    away_score = IntegerField(null=True)
    match_date = DateTimeField()
    season = IntegerField()
    round = IntegerField(null=True)
    status = CharField(default='scheduled')
    minute = IntegerField(null=True)  # Current minute for live matches
    red_cards_home = IntegerField(default=0)
    red_cards_away = IntegerField(default=0)
    created_at = DateTimeField(default=datetime.now)
    updated_at = DateTimeField(default=datetime.now)

    class Meta:
        indexes = ((('league', 'home_team', 'away_team', 'season'), True),)


class BettingOpportunity(BaseModel):
    id = AutoField()
    match = ForeignKeyField(Match, backref='betting_opportunities', null=True)
    rule_triggered = CharField()  # Which betting rule was triggered
    confidence_score = FloatField(default=0.0)  # 0.0 to 1.0
    details = TextField()  # JSON string with additional details
    outcome = CharField(null=True)  # win, lose, pending, cancelled
    created_at = DateTimeField(default=datetime.now)

    def get_details(self) -> dict:
        """Parse and return details as dict"""
        if self.details:
            return json.loads(self.details)
        return {}

    def set_details(self, details_dict: dict) -> None:
        """Set details as JSON string"""
        self.details = json.dumps(details_dict)


class TelegramUser(BaseModel):
    id = AutoField()
    telegram_id = IntegerField(unique=True)
    username = CharField(null=True)
    first_name = CharField(null=True)
    last_name = CharField(null=True)
    is_active = BooleanField(default=True)
    daily_notifications = BooleanField(default=True)
    live_notifications = BooleanField(default=True)
    created_at = DateTimeField(default=datetime.now)
    updated_at = DateTimeField(default=datetime.now)


class NotificationLog(BaseModel):
    id = AutoField()
    user = ForeignKeyField(TelegramUser, backref='notifications')
    opportunity = ForeignKeyField(BettingOpportunity, backref='notifications')
    message = TextField()
    sent_at = DateTimeField(default=datetime.now)
    success = BooleanField(default=True)
    error_message = TextField(null=True)


# Create tables
def create_tables() -> None:
    """Create all database tables"""
    with db:
        db.create_tables(
            [League, Team, Match, BettingOpportunity, TelegramUser, NotificationLog]
        )
        logger.info('Database tables created')


# Initialize database
def init_db() -> None:
    create_tables()
