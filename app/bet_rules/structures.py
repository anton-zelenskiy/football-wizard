from enum import Enum

from pydantic import BaseModel, Field, computed_field


class BetType(str, Enum):
    """Betting outcome types"""

    WIN = 'win'
    DRAW = 'draw'
    LOSE = 'lose'
    DRAW_OR_WIN = 'draw_or_win'
    WIN_OR_LOSE = 'win_or_lose'
    GOAL = 'goal'


class MatchResult(str, Enum):
    """Match result from a team's perspective"""

    WIN = 'win'
    LOSE = 'lose'
    DRAW = 'draw'


class BetOutcome(str, Enum):
    """Betting prediction result outcomes"""

    WIN = 'win'
    LOSE = 'lose'
    UNKNOWN = 'unknown'


class OpportunityType(str, Enum):
    """Opportunity type for betting rules"""

    HISTORICAL_ANALYSIS = BASE = 'historical_analysis'
    LIVE_OPPORTUNITY = 'live_opportunity'


class LeagueData(BaseModel):
    """Pydantic model for league data in analysis"""

    id: int
    name: str
    teams_count: int


class TeamData(BaseModel):
    """Pydantic model for team data in analysis"""

    id: int
    name: str
    rank: int | None = None


class MatchData(BaseModel):
    """Pydantic model for match data in analysis"""

    id: int
    home_team_id: int
    away_team_id: int
    home_score: int | None = None
    away_score: int | None = None
    match_date: str | None = None
    status: str


class TeamAnalysis(BaseModel):
    """Comprehensive team performance analysis"""

    # Core team info
    team: TeamData
    rank: int | None = Field(default=None, description='Team rank in league')

    # Consecutive streaks
    consecutive_wins: int = Field(default=0, ge=0, description='Consecutive wins')
    consecutive_losses: int = Field(default=0, ge=0, description='Consecutive losses')
    consecutive_draws: int = Field(default=0, ge=0, description='Consecutive draws')
    consecutive_no_goals: int = Field(
        default=0, ge=0, description='Consecutive matches without goals'
    )
    consecutive_goals: int = Field(
        default=0, ge=0, description='Consecutive matches with goals'
    )

    # Match statistics
    recent_matches: list[MatchData] = Field(
        default_factory=list, description='Recent matches for analysis'
    )
    total_matches: int = Field(
        default=0, ge=0, description='Total recent matches analyzed'
    )
    wins: int = Field(default=0, ge=0, description='Number of wins')
    draws: int = Field(default=0, ge=0, description='Number of draws')
    losses: int = Field(default=0, ge=0, description='Number of losses')

    # Computed rates
    @computed_field
    @property
    def win_rate(self) -> float:
        """Win rate as percentage"""
        return self.wins / self.total_matches if self.total_matches > 0 else 0.0

    @computed_field
    @property
    def draw_rate(self) -> float:
        """Draw rate as percentage"""
        return self.draws / self.total_matches if self.total_matches > 0 else 0.0

    @computed_field
    @property
    def loss_rate(self) -> float:
        """Loss rate as percentage"""
        return self.losses / self.total_matches if self.total_matches > 0 else 0.0

    @computed_field
    @property
    def goals_scored(self) -> int:
        """Total goals scored in recent matches"""
        return sum(
            match.home_score if match.home_team_id == self.team.id else match.away_score
            for match in self.recent_matches
            if match.home_score is not None and match.away_score is not None
        )

    @computed_field
    @property
    def goals_conceded(self) -> int:
        """Total goals conceded in recent matches"""
        return sum(
            match.away_score if match.home_team_id == self.team.id else match.home_score
            for match in self.recent_matches
            if match.home_score is not None and match.away_score is not None
        )

    @computed_field
    @property
    def is_top_team(self) -> bool:
        """Is team in top teams (rank <= 8)"""
        return self.rank is not None and self.rank <= 8

    @computed_field
    @property
    def is_top5_team(self) -> bool:
        """Is team in top 5 (rank <= 5)"""
        return self.rank is not None and self.rank <= 5

    @classmethod
    def analyze_team_performance(
        cls, team: TeamData, recent_matches: list[MatchData]
    ) -> 'TeamAnalysis':
        """Analyze a team's recent performance comprehensively"""

        # Create base analysis
        analysis = cls(
            team=team,
            rank=team.rank,
            recent_matches=recent_matches,
            total_matches=len(recent_matches),
        )

        if not recent_matches:
            return analysis

        # Calculate consecutive streaks
        analysis.consecutive_wins = cls._calculate_consecutive_streak(
            recent_matches, team, 'win'
        )
        analysis.consecutive_losses = cls._calculate_consecutive_streak(
            recent_matches, team, 'loss'
        )
        analysis.consecutive_draws = cls._calculate_consecutive_streak(
            recent_matches, team, 'draw'
        )
        analysis.consecutive_no_goals = cls._calculate_consecutive_streak(
            recent_matches, team, 'no_goals'
        )
        analysis.consecutive_goals = cls._calculate_consecutive_streak(
            recent_matches, team, 'goals'
        )

        # Calculate match results
        wins = sum(1 for match in recent_matches if cls._team_won(match, team))
        draws = sum(1 for match in recent_matches if cls._team_drew(match, team))
        losses = len(recent_matches) - wins - draws

        analysis.wins = wins
        analysis.draws = draws
        analysis.losses = losses

        return analysis

    @staticmethod
    def _calculate_consecutive_streak(
        matches: list[MatchData], team: TeamData, streak_type: str
    ) -> int:
        """Calculate consecutive streak for a specific type (win, loss, draw, no_goals, goals)"""
        streak = 0

        for match in matches:
            if streak_type == 'win' and TeamAnalysis._team_won(match, team):
                streak += 1
            elif streak_type == 'loss' and TeamAnalysis._team_lost(match, team):
                streak += 1
            elif streak_type == 'draw' and TeamAnalysis._team_drew(match, team):
                streak += 1
            elif streak_type == 'no_goals' and TeamAnalysis._team_no_goals(match, team):
                streak += 1
            elif streak_type == 'goals' and not TeamAnalysis._team_no_goals(
                match, team
            ):
                streak += 1
            else:
                break

        return streak

    @staticmethod
    def _team_won(match: MatchData, team: TeamData) -> bool:
        """Check if team won the match"""
        if match.home_score is None or match.away_score is None:
            return False

        if match.home_team_id == team.id:
            return match.home_score > match.away_score
        else:
            return match.away_score > match.home_score

    @staticmethod
    def _team_lost(match: MatchData, team: TeamData) -> bool:
        """Check if team lost the match"""
        if match.home_score is None or match.away_score is None:
            return False

        if match.home_team_id == team.id:
            return match.home_score < match.away_score
        else:
            return match.away_score < match.home_score

    @staticmethod
    def _team_drew(match: MatchData, team: TeamData) -> bool:
        """Check if team drew the match"""
        if match.home_score is None or match.away_score is None:
            return False

        return match.home_score == match.away_score

    @staticmethod
    def _team_no_goals(match: MatchData, team: TeamData) -> bool:
        """Check if team scored no goals in the match"""
        if match.home_score is None or match.away_score is None:
            return False

        if match.home_team_id == team.id:
            return match.home_score == 0
        else:
            return match.away_score == 0


class MatchSummary(BaseModel):
    """Comprehensive match information for betting contexts and outcome determination"""

    match_id: int | None = Field(default=None, description='Match ID')
    home_team_data: 'TeamData' = Field(
        default=None, description='Home team data for analysis'
    )
    away_team_data: 'TeamData' = Field(
        default=None, description='Away team data for analysis'
    )
    league: 'LeagueData' = Field(description='League data including teams count')
    country: str = Field(description='Country name')
    match_date: str | None = Field(default=None, description='Match date and time')
    home_score: int | None = Field(default=None, description='Home team score')
    away_score: int | None = Field(default=None, description='Away team score')
    red_cards_home: int = Field(default=0, description='Home team red cards')
    red_cards_away: int = Field(default=0, description='Away team red cards')
    minute: int | None = Field(
        default=None, description='Current minute for live matches'
    )
    season: int | None = Field(default=None, description='Season year')
    round: int | None = Field(default=None, description='Round number')
    home_recent_matches: list['MatchData'] = Field(
        default_factory=list, description='Home team recent matches for analysis'
    )
    away_recent_matches: list['MatchData'] = Field(
        default_factory=list, description='Away team recent matches for analysis'
    )

    @property
    def is_complete(self) -> bool:
        """Check if the match is complete (has final scores)"""
        return self.home_score is not None and self.away_score is not None

    def get_team_result(self, team_name: str) -> MatchResult | None:
        """Get the match result for a specific team (WIN/LOSE/DRAW) or None if incomplete"""
        if not self.is_complete:
            return None

        if team_name == self.home_team_data.name:
            if self.home_score > self.away_score:
                return MatchResult.WIN
            elif self.home_score < self.away_score:
                return MatchResult.LOSE
            else:
                return MatchResult.DRAW
        elif team_name == self.away_team_data.name:
            if self.away_score > self.home_score:
                return MatchResult.WIN
            elif self.away_score < self.home_score:
                return MatchResult.LOSE
            else:
                return MatchResult.DRAW

        return None  # Team not found

    @classmethod
    def from_match(
        cls,
        match,
        home_team_rank: int | None = None,
        away_team_rank: int | None = None,
        teams_count: int | None = None,
    ) -> 'MatchSummary':
        """Create MatchSummary from Match database model

        Args:
            match: Match database model
            home_team_rank: Optional rank for home team (from TeamStanding)
            away_team_rank: Optional rank for away team (from TeamStanding)
            teams_count: Optional teams count (to avoid lazy loading issues)
        """
        # Calculate teams count from league relationship if not provided
        if teams_count is None:
            try:
                teams_count = len(match.league.teams) if match.league.teams else 0
            except Exception:
                # Fallback if lazy loading fails
                teams_count = 0

        return cls(
            match_id=match.id,
            home_team_data=TeamData(
                id=match.home_team.id,
                name=match.home_team.name,
                rank=home_team_rank,
            ),
            away_team_data=TeamData(
                id=match.away_team.id,
                name=match.away_team.name,
                rank=away_team_rank,
            ),
            league=LeagueData(
                id=match.league.id,
                name=match.league.name,
                teams_count=teams_count,
            ),
            country=match.league.country,
            match_date=(
                match.match_date.strftime('%Y-%m-%d %H:%M')
                if match.match_date
                else None
            ),
            home_score=match.home_score,
            away_score=match.away_score,
            red_cards_home=match.red_cards_home,
            red_cards_away=match.red_cards_away,
            minute=match.minute,
            season=match.season,
            round=match.round,
        )
