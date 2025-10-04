from pydantic import BaseModel, Field, computed_field


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


class TeamAnalysisService:
    """Service for analyzing team performance"""

    def __init__(
        self, top_teams_count: int = 8, min_consecutive_losses: int = 3
    ) -> None:
        self.top_teams_count = top_teams_count
        self.min_consecutive_losses = min_consecutive_losses

    def analyze_team_performance(
        self, team: TeamData, recent_matches: list[MatchData]
    ) -> TeamAnalysis:
        """Analyze a team's recent performance comprehensively"""

        # Create base analysis
        analysis = TeamAnalysis(
            team=team,
            rank=team.rank,
            recent_matches=recent_matches,
            total_matches=len(recent_matches),
        )

        if not recent_matches:
            return analysis

        # Calculate consecutive streaks
        analysis.consecutive_wins = self._calculate_consecutive_streak(
            recent_matches, team, 'win'
        )
        analysis.consecutive_losses = self._calculate_consecutive_streak(
            recent_matches, team, 'loss'
        )
        analysis.consecutive_draws = self._calculate_consecutive_streak(
            recent_matches, team, 'draw'
        )
        analysis.consecutive_no_goals = self._calculate_consecutive_streak(
            recent_matches, team, 'no_goals'
        )
        analysis.consecutive_goals = self._calculate_consecutive_streak(
            recent_matches, team, 'goals'
        )

        # Calculate match results
        wins = sum(1 for match in recent_matches if self._team_won(match, team))
        draws = sum(1 for match in recent_matches if self._team_drew(match, team))
        losses = len(recent_matches) - wins - draws

        analysis.wins = wins
        analysis.draws = draws
        analysis.losses = losses

        return analysis

    def _calculate_consecutive_streak(
        self, matches: list[MatchData], team: TeamData, streak_type: str
    ) -> int:
        """Calculate consecutive streak for a specific type (win, loss, draw, no_goals, goals)"""
        streak = 0

        for match in matches:
            if streak_type == 'win' and self._team_won(match, team):
                streak += 1
            elif streak_type == 'loss' and self._team_lost(match, team):
                streak += 1
            elif streak_type == 'draw' and self._team_drew(match, team):
                streak += 1
            elif streak_type == 'no_goals' and self._team_no_goals(match, team):
                streak += 1
            elif streak_type == 'goals' and not self._team_no_goals(match, team):
                streak += 1
            else:
                break

        return streak

    def _team_won(self, match: MatchData, team: TeamData) -> bool:
        """Check if team won the match"""
        if match.home_score is None or match.away_score is None:
            return False

        if match.home_team_id == team.id:
            return match.home_score > match.away_score
        else:
            return match.away_score > match.home_score

    def _team_lost(self, match: MatchData, team: TeamData) -> bool:
        """Check if team lost the match"""
        if match.home_score is None or match.away_score is None:
            return False

        if match.home_team_id == team.id:
            return match.home_score < match.away_score
        else:
            return match.away_score < match.home_score

    def _team_drew(self, match: MatchData, team: TeamData) -> bool:
        """Check if team drew the match"""
        if match.home_score is None or match.away_score is None:
            return False

        return match.home_score == match.away_score

    def _team_no_goals(self, match: MatchData, team: TeamData) -> bool:
        """Check if team scored no goals in the match"""
        if match.home_score is None or match.away_score is None:
            return False

        if match.home_team_id == team.id:
            return match.home_score == 0
        else:
            return match.away_score == 0
