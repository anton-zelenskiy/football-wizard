import os
import tempfile
from datetime import datetime

import pytest

from app.db.models import League, Match, Team, db, init_db
from app.db.storage import FootballDataStorage


@pytest.fixture(scope="function")
def temp_db():
    """Create a temporary database for testing"""
    # Create temporary database file
    temp_db_file = tempfile.NamedTemporaryFile(delete=False, suffix='.db')
    temp_db_file.close()

    # Configure database to use temp file
    db.init(temp_db_file.name)
    init_db()

    yield db

    # Cleanup
    db.close()
    os.unlink(temp_db_file.name)

@pytest.fixture
def storage(temp_db):
    return FootballDataStorage()

def test_create_league(temp_db) -> None:
    league = League.create(name="Premier League", country="England")
    assert league.id is not None
    assert league.name == "Premier League"
    assert league.country == "England"

def test_create_team(temp_db) -> None:
    league = League.create(name="Premier League", country="England")
    team = Team.create(
        name="Manchester United",
        league=league,
        rank=1,
        points=50
    )
    assert team.id is not None
    assert team.name == "Manchester United"
    assert team.league == league

def test_create_match(temp_db) -> None:
    league = League.create(name="Premier League", country="England")
    home_team = Team.create(name="Manchester United", league=league)
    away_team = Team.create(name="Liverpool", league=league)

    match = Match.create(
        league=league,
        home_team=home_team,
        away_team=away_team,
        home_score=2,
        away_score=1,
        match_date=datetime.now(),
        season=2024
    )
    assert match.id is not None
    assert match.home_score == 2
    assert match.away_score == 1

def test_create_live_match(temp_db) -> None:
    league = League.create(name="Premier League", country="England")
    home_team = Team.create(name="Manchester United", league=league)
    away_team = Team.create(name="Liverpool", league=league)

    match = Match.create(
        league=league,
        home_team=home_team,
        away_team=away_team,
        home_score=2,
        away_score=1,
        match_date=datetime.now(),
        season=2024,
        status='live',
        minute=75,
        red_cards_home=1,
        red_cards_away=0
    )
    assert match.id is not None
    assert match.status == 'live'
    assert match.red_cards_home == 1

def test_save_leagues(storage) -> None:
    leagues_data = [
        {
            "league": {"name": "Premier League"},
            "country": {"name": "England"}
        }
    ]
    storage.save_leagues(leagues_data)

    league = League.get(League.name == "Premier League")
    assert league.name == "Premier League"
    assert league.country == "England"

def test_save_live_matches(storage) -> None:
    # First create league and teams
    league = League.create(name="Premier League", country="England")
    Team.create(name="Manchester United", league=league)
    Team.create(name="Liverpool", league=league)

    live_matches_data = [
        {
            "league": "Premier League",
            "home_team": "Manchester United",
            "away_team": "Liverpool",
            "home_score": 2,
            "away_score": 1,
            "minute": 75,
            "red_cards_home": 1,
            "red_cards_away": 0
        }
    ]
    storage.save_live_matches(live_matches_data)

    live_matches = Match.select().where(Match.status == 'live')
    assert len(live_matches) == 1
    assert live_matches[0].home_team.name == "Manchester United"

def test_get_recent_live_matches(storage) -> None:
    # Create a live match
    league = League.create(name="Premier League", country="England")
    home_team = Team.create(name="Manchester United", league=league)
    away_team = Team.create(name="Liverpool", league=league)

    Match.create(
        league=league,
        home_team=home_team,
        away_team=away_team,
        home_score=2,
        away_score=1,
        match_date=datetime.now(),
        season=2024,
        status='live',
        minute=75,
        red_cards_home=0,
        red_cards_away=0
    )

    recent_matches = storage.get_recent_live_matches(minutes=5)
    assert len(recent_matches) >= 1
