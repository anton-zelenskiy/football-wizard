from dataclasses import dataclass
from typing import Any

import structlog

from app.db.models import BettingOpportunity, Match, Team
from app.db.storage import FootballDataStorage
from app.settings import settings

logger = structlog.get_logger()


@dataclass
class BetRule:
    match_id: int | None
    home_team: str
    away_team: str
    league: str
    country: str
    rule_name: str
    confidence: float
    details: dict[str, Any]


class BettingRulesEngine:
    def __init__(self) -> None:
        self.storage = FootballDataStorage()
        self.top_teams_count = settings.top_teams_count
        self.min_consecutive_losses = settings.min_consecutive_losses
        self.min_consecutive_draws = settings.min_consecutive_draws
        self.min_consecutive_losses_top5 = settings.min_consecutive_losses_top5
        self.min_no_goals_matches = settings.min_no_goals_matches
        self.live_draw_minute_threshold = settings.live_draw_minute_threshold

    def analyze_scheduled_matches(self) -> list[BetRule]:
        """Analyze scheduled matches for betting opportunities based on team history"""
        opportunities: list[BetRule] = []
        processed_matches = set()  # Track processed matches to avoid duplicates

        # Get all scheduled matches
        scheduled_matches = self.storage.get_scheduled_matches(days_ahead=7)

        for match in scheduled_matches:
            try:
                # Create a unique match identifier
                match_id = f'{match.home_team.name}_{match.away_team.name}'

                # Skip if we've already processed this match
                if match_id in processed_matches:
                    continue

                # Analyze the match as a whole, considering both teams
                match_opportunity = self._analyze_scheduled_match(match)
                if match_opportunity:
                    opportunities.append(match_opportunity)
                    processed_matches.add(match_id)

            except Exception as e:
                logger.error(
                    f'Error analyzing scheduled match {match.home_team.name} vs {match.away_team.name}',
                    error=str(e),
                )

        return opportunities

    def analyze_live_matches(self) -> list[BetRule]:
        """Analyze live matches for betting opportunities"""
        opportunities: list[BetRule] = []

        # Get recent live matches
        live_matches = self.storage.get_recent_live_matches(minutes=10)

        for match in live_matches:
            try:
                # Apply live betting rules
                match_opportunities = self._apply_live_rules(match)
                opportunities.extend(match_opportunities)

            except Exception as e:
                logger.error(
                    f'Error analyzing live match {match.home_team.name} vs {match.away_team.name}',
                    error=str(e),
                )

        return opportunities

    def _analyze_scheduled_match(self, match: Match) -> BetRule | None:
        """Analyze a scheduled match considering both teams and their relative strength"""

        # Get team analysis for both teams
        home_analysis = self._analyze_team_performance(match.home_team, 'home')
        away_analysis = self._analyze_team_performance(match.away_team, 'away')

        # Calculate team strength difference
        strength_diff = self._calculate_team_strength_difference(match.home_team, match.away_team)

        # Apply betting rules considering both teams
        opportunity = self._apply_scheduled_rules(
            match, home_analysis, away_analysis, strength_diff
        )

        return opportunity

    def _analyze_team_performance(self, team: Team, team_type: str) -> dict[str, Any]:
        """Analyze a team's recent performance comprehensively"""
        analysis = {
            'team': team,
            'team_type': team_type,
            'rank': team.rank,
            'consecutive_wins': 0,
            'consecutive_losses': 0,
            'consecutive_draws': 0,
            'consecutive_no_goals': 0,
            'consecutive_goals': 0,
            'recent_matches': [],
            'is_top_team': False,
            'is_top5_team': False,
            'total_matches': 0,
            'wins': 0,
            'draws': 0,
            'losses': 0,
            'goals_scored': 0,
            'goals_conceded': 0,
            'win_rate': 0,
            'draw_rate': 0,
            'loss_rate': 0,
        }

        if not team.rank:
            logger.warning(f'Team {team.name} has no rank, returning default analysis')
            return analysis

        analysis['is_top_team'] = team.rank <= self.top_teams_count
        analysis['is_top5_team'] = team.rank <= 5

        # Get recent matches for streak analysis
        recent_matches = self._get_recent_matches(team, max(10, self.min_consecutive_losses * 2))
        analysis['recent_matches'] = recent_matches

        logger.info(f'Team {team.name}: Found {len(recent_matches)} recent matches')

        if not recent_matches:
            logger.warning(f'Team {team.name}: No recent matches found, returning default analysis')
            return analysis

        # Calculate consecutive streaks
        analysis['consecutive_wins'] = self._calculate_consecutive_streak(
            recent_matches, team, 'win'
        )
        analysis['consecutive_losses'] = self._calculate_consecutive_streak(
            recent_matches, team, 'loss'
        )
        analysis['consecutive_draws'] = self._calculate_consecutive_streak(
            recent_matches, team, 'draw'
        )
        analysis['consecutive_no_goals'] = self._calculate_consecutive_streak(
            recent_matches, team, 'no_goals'
        )
        analysis['consecutive_goals'] = self._calculate_consecutive_streak(
            recent_matches, team, 'goals'
        )

        # Calculate overall stats from recent matches
        total_matches = len(recent_matches)
        wins = sum(1 for match in recent_matches if self._team_won(match, team))
        draws = sum(1 for match in recent_matches if self._team_drew(match, team))
        losses = total_matches - wins - draws

        analysis.update(
            {
                'total_matches': total_matches,
                'wins': wins,
                'draws': draws,
                'losses': losses,
                'win_rate': wins / total_matches if total_matches > 0 else 0,
                'draw_rate': draws / total_matches if total_matches > 0 else 0,
                'loss_rate': losses / total_matches if total_matches > 0 else 0,
            }
        )

        return analysis

    def _calculate_consecutive_streak(
        self, matches: list[Match], team: Team, streak_type: str
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

    def _calculate_team_strength_difference(self, home_team: Team, away_team: Team) -> int:
        """Calculate the strength difference between teams based on rank"""
        home_rank = home_team.rank or 20  # Default to 20 if no rank
        away_rank = away_team.rank or 20

        # Lower rank = better team (rank 1 is strongest, rank 20 is weakest)
        # We want to show which team is stronger
        # Positive = away team is stronger (away_rank < home_rank)
        # Negative = home team is stronger (home_rank < away_rank)
        # Add small home advantage (equivalent to 1 rank position)
        strength_diff = home_rank - away_rank + 1

        return strength_diff

    def _apply_scheduled_rules(
        self,
        match: Match,
        home_analysis: dict[str, Any],
        away_analysis: dict[str, Any],
        strength_diff: int,
    ) -> BetRule | None:
        """
        Apply betting rules considering both teams and their relative strength

        Possible outcomes:
        - win
        - lose




        - team from top-10 and 3 and more last matches - losses -> 1x
            -no goals in the last matches mustt increase confidence
        - team from top-10 and 3 and more draws -> 12 (win or lose)
        - team from top-5 and >= 2 losses in a row -> 1x
        - team from top-10 and no goals in the last 2 and more matches
        - team from out of top 10 and 3 and more last matches - wins -> ?????

        """

        # Rule 1: Strong team vs weak team with poor form
        opportunity = self._rule_strong_vs_weak_poor_form(
            match, home_analysis, away_analysis, strength_diff
        )
        if opportunity:
            return opportunity

        # Rule 2: Both teams in poor form (draw likely)
        opportunity = self._rule_both_teams_poor_form(match, home_analysis, away_analysis)
        if opportunity:
            return opportunity

        # Rule 3: Top team losing streak vs strong opponent
        opportunity = self._rule_top_team_losing_vs_strong(
            match, home_analysis, away_analysis, strength_diff
        )
        if opportunity:
            return opportunity

        # Rule 4: Top team drawing streak
        opportunity = self._rule_top_team_drawing_streak(match, home_analysis, away_analysis)
        if opportunity:
            return opportunity

        # Rule 5: Top team no goals vs strong opponent
        opportunity = self._rule_top_team_no_goals_vs_strong(
            match, home_analysis, away_analysis, strength_diff
        )
        if opportunity:
            return opportunity

        # Rule 6: Team on winning streak vs team on losing streak
        opportunity = self._rule_winning_streak_vs_losing_streak(
            match, home_analysis, away_analysis
        )
        if opportunity:
            return opportunity

        # Rule 7: High-scoring team vs low-scoring team
        opportunity = self._rule_high_scoring_vs_low_scoring(match, home_analysis, away_analysis)
        if opportunity:
            return opportunity

        # Rule 8: Both teams in good form (high-scoring match likely)
        opportunity = self._rule_both_teams_good_form(match, home_analysis, away_analysis)
        if opportunity:
            return opportunity

        return None

    def _rule_strong_vs_weak_poor_form(
        self,
        match: Match,
        home_analysis: dict[str, Any],
        away_analysis: dict[str, Any],
        strength_diff: int,
    ) -> BetRule | None:
        """Rule: Strong team vs weak team with poor form"""
        # Check if there's a significant strength difference
        if abs(strength_diff) < 5:  # Less than 5 rank difference
            return None

        # Determine which team is strong and which is weak
        if strength_diff < 0:  # Away team is stronger
            strong_team_analysis = away_analysis
            weak_team_analysis = home_analysis
        else:  # Home team is stronger (or equal)
            strong_team_analysis = home_analysis
            weak_team_analysis = away_analysis

        # Check if weak team has poor form (multiple indicators)
        weak_team_poor_form = (
            weak_team_analysis['consecutive_losses'] >= 2
            or weak_team_analysis['consecutive_no_goals'] >= 2
            or weak_team_analysis['win_rate'] < 0.3
        )

        # Check if strong team is in good form
        strong_team_good_form = (
            strong_team_analysis['consecutive_wins'] >= 2 or strong_team_analysis['win_rate'] >= 0.6
        )

        if weak_team_poor_form and strong_team_good_form:
            strong_team = strong_team_analysis['team']
            weak_team = weak_team_analysis['team']

            # Calculate confidence based on multiple factors
            base_confidence = 0.75

            # Boost confidence for very strong vs very weak
            if abs(strength_diff) >= 10:
                base_confidence += 0.10

            # Boost confidence for strong team in good form
            if strong_team_analysis['consecutive_wins'] >= 3:
                base_confidence += 0.05

            # Boost confidence for weak team in very poor form
            if weak_team_analysis['consecutive_losses'] >= 3:
                base_confidence += 0.05

            confidence = min(0.90, base_confidence)

            return BetRule(
                match_id=match.id,
                home_team=match.home_team.name,
                away_team=match.away_team.name,
                league=match.league.name,
                country=match.league.country,
                rule_name='Strong vs Weak Poor Form',
                confidence=confidence,
                details={
                    'strong_team': strong_team.name,
                    'weak_team': weak_team.name,
                    'strength_difference': strength_diff,
                    'strong_team_win_rate': strong_team_analysis['win_rate'],
                    'strong_team_consecutive_wins': strong_team_analysis['consecutive_wins'],
                    'weak_team_consecutive_losses': weak_team_analysis['consecutive_losses'],
                    'weak_team_consecutive_no_goals': weak_team_analysis['consecutive_no_goals'],
                    'weak_team_win_rate': weak_team_analysis['win_rate'],
                    'expected_outcome': f'{strong_team.name} to win',
                },
            )

        return None

    def _rule_both_teams_poor_form(
        self, match: Match, home_analysis: dict[str, Any], away_analysis: dict[str, Any]
    ) -> BetRule | None:
        """Rule: Both teams in poor form (draw likely)"""
        # Check if both teams have poor form using multiple indicators
        home_poor_form = (
            home_analysis['consecutive_losses'] >= 2
            or home_analysis['consecutive_no_goals'] >= 2
            or home_analysis['win_rate'] < 0.3
        )
        away_poor_form = (
            away_analysis['consecutive_losses'] >= 2
            or away_analysis['consecutive_no_goals'] >= 2
            or away_analysis['win_rate'] < 0.3
        )

        if home_poor_form and away_poor_form:
            # Calculate confidence based on how poor both teams are
            home_poor_score = (
                home_analysis['consecutive_losses'] * 0.3
                + home_analysis['consecutive_no_goals'] * 0.2
                + (0.5 - home_analysis['win_rate']) * 0.5
            )
            away_poor_score = (
                away_analysis['consecutive_losses'] * 0.3
                + away_analysis['consecutive_no_goals'] * 0.2
                + (0.5 - away_analysis['win_rate']) * 0.5
            )

            # Higher confidence when both teams are clearly struggling
            confidence = min(0.80, 0.60 + (home_poor_score + away_poor_score) * 0.1)

            return BetRule(
                match_id=match.id,
                home_team=match.home_team.name,
                away_team=match.away_team.name,
                league=match.league.name,
                country=match.league.country,
                rule_name='Both Teams Poor Form',
                confidence=confidence,
                details={
                    'home_team': match.home_team.name,
                    'away_team': match.away_team.name,
                    'home_consecutive_losses': home_analysis['consecutive_losses'],
                    'home_consecutive_no_goals': home_analysis['consecutive_no_goals'],
                    'home_win_rate': home_analysis['win_rate'],
                    'away_consecutive_losses': away_analysis['consecutive_losses'],
                    'away_consecutive_no_goals': away_analysis['consecutive_no_goals'],
                    'away_win_rate': away_analysis['win_rate'],
                    'expected_outcome': 'draw',
                },
            )

        return None

    def _rule_top_team_losing_vs_strong(
        self,
        match: Match,
        home_analysis: dict[str, Any],
        away_analysis: dict[str, Any],
        strength_diff: int,
    ) -> BetRule | None:
        """Rule: Top team losing streak vs strong opponent"""
        # Check for top team with losing streak
        top_team_analysis = None
        opponent_analysis = None
        top_team_type = None

        if (
            home_analysis['is_top_team']
            and home_analysis['consecutive_losses'] >= self.min_consecutive_losses
        ):
            top_team_analysis = home_analysis
            opponent_analysis = away_analysis
            top_team_type = 'home'
        elif (
            away_analysis['is_top_team']
            and away_analysis['consecutive_losses'] >= self.min_consecutive_losses
        ):
            top_team_analysis = away_analysis
            opponent_analysis = home_analysis
            top_team_type = 'away'

        if not top_team_analysis:
            return None

        # Check if opponent is strong (within 5 ranks or better)
        opponent_rank = opponent_analysis['team'].rank or 20
        top_team_rank = top_team_analysis['team'].rank or 20

        if opponent_rank <= top_team_rank + 5:  # Opponent is strong
            # Calculate confidence based on multiple factors
            base_confidence = 0.75 if top_team_analysis['is_top5_team'] else 0.70

            # Boost confidence for longer losing streaks
            if top_team_analysis['consecutive_losses'] >= 4:
                base_confidence += 0.05

            # Boost confidence if opponent is in good form
            if opponent_analysis['consecutive_wins'] >= 2:
                base_confidence += 0.05

            # Boost confidence if top team is also not scoring
            if top_team_analysis['consecutive_no_goals'] >= 2:
                base_confidence += 0.05

            confidence = min(0.90, base_confidence)

            return BetRule(
                match_id=match.id,
                home_team=match.home_team.name,
                away_team=match.away_team.name,
                league=match.league.name,
                country=match.league.country,
                rule_name='Top Team Losing vs Strong',
                confidence=confidence,
                details={
                    'top_team': top_team_analysis['team'].name,
                    'top_team_rank': top_team_rank,
                    'opponent': opponent_analysis['team'].name,
                    'opponent_rank': opponent_rank,
                    'consecutive_losses': top_team_analysis['consecutive_losses'],
                    'consecutive_no_goals': top_team_analysis['consecutive_no_goals'],
                    'opponent_consecutive_wins': opponent_analysis['consecutive_wins'],
                    'team_type': top_team_type,
                    'expected_outcome': f'{opponent_analysis["team"].name} to win',
                },
            )

        return None

    def _rule_top_team_drawing_streak(
        self, match: Match, home_analysis: dict[str, Any], away_analysis: dict[str, Any]
    ) -> BetRule | None:
        """Rule: Top team drawing streak"""

        # Check for top team with drawing streak - prioritize home team if both have drawing streaks
        if (
            home_analysis['is_top_team']
            and home_analysis['consecutive_draws'] >= self.min_consecutive_draws
        ):
            # Calculate confidence based on drawing streak length and team performance
            base_confidence = 0.70
            if home_analysis['consecutive_draws'] >= 4:
                base_confidence += 0.05
            if home_analysis['consecutive_no_goals'] >= 2:
                base_confidence += 0.05

            confidence = min(0.85, base_confidence)

            return BetRule(
                match_id=match.id,
                home_team=match.home_team.name,
                away_team=match.away_team.name,
                league=match.league.name,
                country=match.league.country,
                rule_name='Top Team Drawing Streak',
                confidence=confidence,
                details={
                    'top_team': match.home_team.name,
                    'team_rank': match.home_team.rank,
                    'consecutive_draws': home_analysis['consecutive_draws'],
                    'consecutive_no_goals': home_analysis['consecutive_no_goals'],
                    'team_type': 'home',
                    'expected_outcome': 'draw',
                },
            )
        elif (
            away_analysis['is_top_team']
            and away_analysis['consecutive_draws'] >= self.min_consecutive_draws
        ):
            # Calculate confidence based on drawing streak length and team performance
            base_confidence = 0.70
            if away_analysis['consecutive_draws'] >= 4:
                base_confidence += 0.05
            if away_analysis['consecutive_no_goals'] >= 2:
                base_confidence += 0.05

            confidence = min(0.85, base_confidence)

            return BetRule(
                match_id=match.id,
                home_team=match.home_team.name,
                away_team=match.away_team.name,
                league=match.league.name,
                country=match.league.country,
                rule_name='Top Team Drawing Streak',
                confidence=confidence,
                details={
                    'top_team': match.away_team.name,
                    'team_rank': match.away_team.rank,
                    'consecutive_draws': away_analysis['consecutive_draws'],
                    'consecutive_no_goals': away_analysis['consecutive_no_goals'],
                    'team_type': 'away',
                    'expected_outcome': 'draw',
                },
            )

        return None

    def _rule_top_team_no_goals_vs_strong(
        self,
        match: Match,
        home_analysis: dict[str, Any],
        away_analysis: dict[str, Any],
        strength_diff: int,
    ) -> BetRule | None:
        """Rule: Top team no goals vs strong opponent"""
        # Check for top team with no goals
        top_team_analysis = None
        opponent_analysis = None

        if (
            home_analysis['is_top_team']
            and home_analysis['consecutive_no_goals'] >= self.min_no_goals_matches
        ):
            top_team_analysis = home_analysis
            opponent_analysis = away_analysis
        elif (
            away_analysis['is_top_team']
            and away_analysis['consecutive_no_goals'] >= self.min_no_goals_matches
        ):
            top_team_analysis = away_analysis
            opponent_analysis = home_analysis

        if not top_team_analysis:
            return None

        # Check if opponent is strong (within 8 ranks)
        opponent_rank = opponent_analysis['team'].rank or 20
        top_team_rank = top_team_analysis['team'].rank or 20

        if opponent_rank <= top_team_rank + 8:  # Opponent is strong
            # Calculate confidence based on multiple factors
            base_confidence = 0.75

            # Boost confidence for longer no-goals streaks
            if top_team_analysis['consecutive_no_goals'] >= 4:
                base_confidence += 0.05

            # Boost confidence if opponent is in good form
            if opponent_analysis['consecutive_wins'] >= 2:
                base_confidence += 0.05

            # Boost confidence if top team is also on losing streak
            if top_team_analysis['consecutive_losses'] >= 2:
                base_confidence += 0.05

            confidence = min(0.90, base_confidence)

            return BetRule(
                match_id=match.id,
                home_team=match.home_team.name,
                away_team=match.away_team.name,
                league=match.league.name,
                country=match.league.country,
                rule_name='Top Team No Goals vs Strong',
                confidence=confidence,
                details={
                    'top_team': top_team_analysis['team'].name,
                    'top_team_rank': top_team_rank,
                    'opponent': opponent_analysis['team'].name,
                    'opponent_rank': opponent_rank,
                    'consecutive_no_goals': top_team_analysis['consecutive_no_goals'],
                    'consecutive_losses': top_team_analysis['consecutive_losses'],
                    'opponent_consecutive_wins': opponent_analysis['consecutive_wins'],
                    'expected_outcome': f'{opponent_analysis["team"].name} to win',
                },
            )

        return None

    def _rule_winning_streak_vs_losing_streak(
        self, match: Match, home_analysis: dict[str, Any], away_analysis: dict[str, Any]
    ) -> BetRule | None:
        """Rule: Team on winning streak vs team on losing streak"""
        # Check if one team has a significant winning streak and other has losing streak
        home_winning_streak = home_analysis['consecutive_wins']
        away_winning_streak = away_analysis['consecutive_wins']
        home_losing_streak = home_analysis['consecutive_losses']
        away_losing_streak = away_analysis['consecutive_losses']

        # Home team winning streak vs away team losing streak
        if home_winning_streak >= 3 and away_losing_streak >= 2:
            confidence = min(0.80, 0.65 + (home_winning_streak * 0.05))
            return BetRule(
                match_id=match.id,
                home_team=match.home_team.name,
                away_team=match.away_team.name,
                league=match.league.name,
                country=match.league.country,
                rule_name='Winning Streak vs Losing Streak',
                confidence=confidence,
                details={
                    'winning_team': match.home_team.name,
                    'losing_team': match.away_team.name,
                    'winning_streak': home_winning_streak,
                    'losing_streak': away_losing_streak,
                    'expected_outcome': f'{match.home_team.name} to win',
                },
            )

        # Away team winning streak vs home team losing streak
        elif away_winning_streak >= 3 and home_losing_streak >= 2:
            confidence = min(0.80, 0.65 + (away_winning_streak * 0.05))
            return BetRule(
                match_id=match.id,
                home_team=match.home_team.name,
                away_team=match.away_team.name,
                league=match.league.name,
                country=match.league.country,
                rule_name='Winning Streak vs Losing Streak',
                confidence=confidence,
                details={
                    'winning_team': match.away_team.name,
                    'losing_team': match.home_team.name,
                    'winning_streak': away_winning_streak,
                    'losing_streak': home_losing_streak,
                    'expected_outcome': f'{match.away_team.name} to win',
                },
            )

        return None

    def _rule_high_scoring_vs_low_scoring(
        self, match: Match, home_analysis: dict[str, Any], away_analysis: dict[str, Any]
    ) -> BetRule | None:
        """Rule: High-scoring team vs low-scoring team (over/under betting)"""

        # Check if one team consistently scores and other doesn't
        home_goals_streak = home_analysis['consecutive_goals']
        away_goals_streak = away_analysis['consecutive_goals']
        home_no_goals_streak = home_analysis['consecutive_no_goals']
        away_no_goals_streak = away_analysis['consecutive_no_goals']

        # High-scoring home team vs low-scoring away team
        if home_goals_streak >= 3 and away_no_goals_streak >= 2:
            return BetRule(
                match_id=match.id,
                home_team=match.home_team.name,
                away_team=match.away_team.name,
                league=match.league.name,
                country=match.league.country,
                rule_name='High Scoring vs Low Scoring',
                confidence=0.75,
                details={
                    'high_scoring_team': match.home_team.name,
                    'low_scoring_team': match.away_team.name,
                    'home_goals_streak': home_goals_streak,
                    'away_no_goals_streak': away_no_goals_streak,
                    'expected_outcome': f'{match.home_team.name} to win with goals',
                },
            )

        # High-scoring away team vs low-scoring home team
        elif away_goals_streak >= 3 and home_no_goals_streak >= 2:
            return BetRule(
                match_id=match.id,
                home_team=match.home_team.name,
                away_team=match.away_team.name,
                league=match.league.name,
                country=match.league.country,
                rule_name='High Scoring vs Low Scoring',
                confidence=0.75,
                details={
                    'high_scoring_team': match.away_team.name,
                    'low_scoring_team': match.home_team.name,
                    'away_goals_streak': away_goals_streak,
                    'home_no_goals_streak': home_no_goals_streak,
                    'expected_outcome': f'{match.away_team.name} to win with goals',
                },
            )

        return None

    def _rule_both_teams_good_form(
        self, match: Match, home_analysis: dict[str, Any], away_analysis: dict[str, Any]
    ) -> BetRule | None:
        """Rule: Both teams in good form (high-scoring match likely)"""

        # Check if both teams are performing well
        home_good_form = home_analysis['consecutive_wins'] >= 2 or home_analysis['win_rate'] >= 0.6
        away_good_form = away_analysis['consecutive_wins'] >= 2 or away_analysis['win_rate'] >= 0.6

        # Both teams scoring consistently
        both_scoring = (
            home_analysis['consecutive_goals'] >= 2 and away_analysis['consecutive_goals'] >= 2
        )

        if home_good_form and away_good_form and both_scoring:
            return BetRule(
                match_id=match.id,
                home_team=match.home_team.name,
                away_team=match.away_team.name,
                league=match.league.name,
                country=match.league.country,
                rule_name='Both Teams Good Form',
                confidence=0.70,
                details={
                    'home_team': match.home_team.name,
                    'away_team': match.away_team.name,
                    'home_win_rate': home_analysis['win_rate'],
                    'away_win_rate': away_analysis['win_rate'],
                    'home_goals_streak': home_analysis['consecutive_goals'],
                    'away_goals_streak': away_analysis['consecutive_goals'],
                    'expected_outcome': 'high-scoring match (over 2.5 goals)',
                },
            )

        return None

    def _apply_live_rules(self, match: Match) -> list[BetRule]:
        """Apply live betting rules to a match"""
        opportunities = []

        # Rule 1: Red card + draw + second half
        opportunity = self._rule_live_red_card_draw_second_half(match)
        if opportunity:
            opportunities.append(opportunity)

        # Rule 2: Draw until 70+ minutes with top-5 vs below top-5
        opportunity = self._rule_live_draw_top5_vs_below(match)
        if opportunity:
            opportunities.append(opportunity)

        return opportunities

    def _rule_live_red_card_draw_second_half(self, match: Match) -> BetRule | None:
        """Rule: Red card + draw + second half"""
        if match.status != 'live':
            return None

        minute = match.minute or 0
        home_score = match.home_score or 0
        away_score = match.away_score or 0
        red_cards_home = match.red_cards_home or 0
        red_cards_away = match.red_cards_away or 0

        # Check conditions: second half, draw, and red card
        if minute >= 45 and home_score == away_score and (red_cards_home > 0 or red_cards_away > 0):
            team_with_red = match.home_team.name if red_cards_home > 0 else match.away_team.name
            team_against = match.away_team.name if red_cards_home > 0 else match.home_team.name

            return BetRule(
                match_id=match.id,
                home_team=match.home_team.name,
                away_team=match.away_team.name,
                league=match.league.name,
                country=match.league.country,
                rule_name='Live Red Card Draw Second Half',
                confidence=0.85,
                details={
                    'minute': minute,
                    'score': f'{home_score}-{away_score}',
                    'team_with_red': team_with_red,
                    'team_against': team_against,
                    'red_cards_home': red_cards_home,
                    'red_cards_away': red_cards_away,
                    'expected_outcome': f'{team_against} to win',
                },
            )

        return None

    def _rule_live_draw_top5_vs_below(self, match: Match) -> BetRule | None:
        """Rule: Draw until 70+ minutes with top-5 vs below top-5"""
        if match.status != 'live':
            return None

        minute = match.minute or 0
        home_score = match.home_score or 0
        away_score = match.away_score or 0

        # Check if it's a draw past 70 minutes
        if minute >= self.live_draw_minute_threshold and home_score == away_score:
            home_rank = match.home_team.rank or 20
            away_rank = match.away_team.rank or 20

            # Check if one team is top-5 and other is below
            home_top5 = home_rank <= 5
            away_top5 = away_rank <= 5

            if home_top5 != away_top5:  # One is top-5, other is not
                top5_team = match.home_team.name if home_top5 else match.away_team.name
                other_team = match.away_team.name if home_top5 else match.home_team.name

                return BetRule(
                    match_id=match.id,
                    home_team=match.home_team.name,
                    away_team=match.away_team.name,
                    league=match.league.name,
                    country=match.league.country,
                    rule_name='Live Draw Top5 vs Below',
                    confidence=0.75,
                    details={
                        'minute': minute,
                        'score': f'{home_score}-{away_score}',
                        'top5_team': top5_team,
                        'other_team': other_team,
                        'home_rank': home_rank,
                        'away_rank': away_rank,
                        'expected_outcome': f'{top5_team} to win',
                    },
                )

        return None

    def _get_recent_matches(self, team: Team, count: int) -> list[Match]:
        """Get recent matches for a team"""
        try:
            # Get matches where team participated
            matches = (
                Match.select()
                .where(
                    ((Match.home_team == team) | (Match.away_team == team))
                    & (Match.status == 'finished')
                )
                .order_by(Match.match_date.desc())
                .limit(count)
            )
            match_list = list(matches)
            logger.debug(
                f'Found {len(match_list)} recent matches for {team.name} (requested: {count})'
            )
            if match_list:
                logger.debug(
                    f'Most recent match: {match_list[0].home_team.name} vs {match_list[0].away_team.name} on {match_list[0].match_date}'
                )
            return match_list
        except Exception as e:
            logger.error(f'Error getting recent matches for {team.name}: {e}')
            return []

    def _team_won(self, match: Match, team: Team) -> bool:
        """Check if team won the match"""
        if match.home_score is None or match.away_score is None:
            return False

        if match.home_team == team:
            return match.home_score > match.away_score
        else:
            return match.away_score > match.home_score

    def _team_lost(self, match: Match, team: Team) -> bool:
        """Check if team lost the match"""
        if match.home_score is None or match.away_score is None:
            return False

        if match.home_team == team:
            return match.home_score < match.away_score
        else:
            return match.away_score < match.home_score

    def _team_drew(self, match: Match, team: Team) -> bool:
        """Check if team drew the match"""
        if match.home_score is None or match.away_score is None:
            return False

        return match.home_score == match.away_score

    def _team_no_goals(self, match: Match, team: Team) -> bool:
        """Check if team scored no goals in the match"""
        if match.home_score is None or match.away_score is None:
            return False

        if match.home_team == team:
            return match.home_score == 0
        else:
            return match.away_score == 0

    def _match_to_dict(self, match: Match) -> dict[str, Any]:
        """Convert match to dictionary for details"""
        return {
            'date': match.match_date.isoformat() if match.match_date else None,
            'home_team': match.home_team.name,
            'away_team': match.away_team.name,
            'home_score': match.home_score,
            'away_score': match.away_score,
            'status': match.status,
        }

    def save_opportunity(self, opportunity: BetRule) -> BettingOpportunity:
        """Save betting opportunity to database"""
        match = None
        if opportunity.match_id:
            try:
                match = Match.get(Match.id == opportunity.match_id)
            except Match.DoesNotExist:
                logger.warning(f'Match {opportunity.match_id} not found for betting opportunity')

        # Determine opportunity type based on rule name
        opportunity_type = (
            'live_opportunity' if 'Live' in opportunity.rule_name else 'historical_analysis'
        )

        db_opportunity = BettingOpportunity(
            match=match,
            opportunity_type=opportunity_type,
            rule_triggered=opportunity.rule_name,
            confidence_score=opportunity.confidence,
        )
        db_opportunity.set_details(opportunity.details)
        db_opportunity.save()
        return db_opportunity
