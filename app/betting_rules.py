from dataclasses import dataclass
from typing import Any

import structlog

from app.db.models import BettingOpportunity as DBBettingOpportunity
from app.db.models import Match, Team
from app.db.storage import FootballDataStorage
from app.settings import settings

logger = structlog.get_logger()


@dataclass
class BettingOpportunity:
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

    def analyze_scheduled_matches(self) -> list[BettingOpportunity]:
        """Analyze scheduled matches for betting opportunities based on team history"""
        opportunities: list[BettingOpportunity] = []
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

    def analyze_live_matches(self) -> list[BettingOpportunity]:
        """Analyze live matches for betting opportunities"""
        opportunities: list[BettingOpportunity] = []

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

    def _analyze_scheduled_match(self, match: Match) -> BettingOpportunity | None:
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
        """Analyze a team's recent performance"""
        analysis = {
            'team': team,
            'team_type': team_type,
            'rank': team.rank,
            'consecutive_losses': 0,
            'consecutive_draws': 0,
            'consecutive_no_goals': 0,
            'recent_matches': [],
            'is_top_team': False,
            'is_top5_team': False,
        }

        if not team.rank:
            return analysis

        analysis['is_top_team'] = team.rank <= self.top_teams_count
        analysis['is_top5_team'] = team.rank <= 5

        # Get recent matches
        recent_matches = self._get_recent_matches(team, max(5, self.min_consecutive_losses))
        analysis['recent_matches'] = recent_matches

        if not recent_matches:
            return analysis

        # Calculate consecutive losses
        consecutive_losses = 0
        for match_history in recent_matches:
            if self._team_lost(match_history, team):
                consecutive_losses += 1
            else:
                break
        analysis['consecutive_losses'] = consecutive_losses

        # Calculate consecutive draws
        consecutive_draws = 0
        for match_history in recent_matches:
            if self._team_drew(match_history, team):
                consecutive_draws += 1
            else:
                break
        analysis['consecutive_draws'] = consecutive_draws

        # Calculate consecutive no-goals matches
        consecutive_no_goals = 0
        for match_history in recent_matches:
            if self._team_no_goals(match_history, team):
                consecutive_no_goals += 1
            else:
                break
        analysis['consecutive_no_goals'] = consecutive_no_goals

        return analysis

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
    ) -> BettingOpportunity | None:
        """Apply betting rules considering both teams and their relative strength"""

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

        return None

    def _rule_strong_vs_weak_poor_form(
        self,
        match: Match,
        home_analysis: dict[str, Any],
        away_analysis: dict[str, Any],
        strength_diff: int,
    ) -> BettingOpportunity | None:
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

        # Check if weak team has poor form (2+ consecutive losses or no goals in 2+ matches)
        weak_team_poor_form = (
            weak_team_analysis['consecutive_losses'] >= 2
            or weak_team_analysis['consecutive_no_goals'] >= 2
        )

        if weak_team_poor_form:
            strong_team = strong_team_analysis['team']
            weak_team = weak_team_analysis['team']

            confidence = 0.75
            if abs(strength_diff) >= 10:  # Very strong vs very weak
                confidence = 0.85

            return BettingOpportunity(
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
                    'weak_team_consecutive_losses': weak_team_analysis['consecutive_losses'],
                    'weak_team_consecutive_no_goals': weak_team_analysis['consecutive_no_goals'],
                    'expected_outcome': f'{strong_team.name} to win'
                }
            )

        return None

    def _rule_both_teams_poor_form(
        self, match: Match, home_analysis: dict[str, Any], away_analysis: dict[str, Any]
    ) -> BettingOpportunity | None:
        """Rule: Both teams in poor form (draw likely)"""

        # Check if both teams have poor form
        home_poor_form = (
            home_analysis['consecutive_losses'] >= 2 or home_analysis['consecutive_no_goals'] >= 2
        )
        away_poor_form = (
            away_analysis['consecutive_losses'] >= 2 or away_analysis['consecutive_no_goals'] >= 2
        )

        if home_poor_form and away_poor_form:
            return BettingOpportunity(
                match_id=match.id,
                home_team=match.home_team.name,
                away_team=match.away_team.name,
                league=match.league.name,
                country=match.league.country,
                rule_name='Both Teams Poor Form',
                confidence=0.70,
                details={
                    'home_team': match.home_team.name,
                    'away_team': match.away_team.name,
                    'home_consecutive_losses': home_analysis['consecutive_losses'],
                    'home_consecutive_no_goals': home_analysis['consecutive_no_goals'],
                    'away_consecutive_losses': away_analysis['consecutive_losses'],
                    'away_consecutive_no_goals': away_analysis['consecutive_no_goals'],
                    'expected_outcome': 'draw'
                }
            )

        return None

    def _rule_top_team_losing_vs_strong(
        self,
        match: Match,
        home_analysis: dict[str, Any],
        away_analysis: dict[str, Any],
        strength_diff: int,
    ) -> BettingOpportunity | None:
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
            confidence = 0.80 if top_team_analysis['is_top5_team'] else 0.75

            return BettingOpportunity(
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
                    'team_type': top_team_type,
                    'expected_outcome': f'{opponent_analysis["team"].name} to win'
                }
            )

        return None

    def _rule_top_team_drawing_streak(
        self, match: Match, home_analysis: dict[str, Any], away_analysis: dict[str, Any]
    ) -> BettingOpportunity | None:
        """Rule: Top team drawing streak"""

        # Check for top team with drawing streak - prioritize home team if both have drawing streaks
        if (
            home_analysis['is_top_team']
            and home_analysis['consecutive_draws'] >= self.min_consecutive_draws
        ):
            return BettingOpportunity(
                match_id=match.id,
                home_team=match.home_team.name,
                away_team=match.away_team.name,
                league=match.league.name,
                country=match.league.country,
                rule_name='Top Team Drawing Streak',
                confidence=0.70,
                details={
                    'top_team': match.home_team.name,
                    'team_rank': match.home_team.rank,
                    'consecutive_draws': home_analysis['consecutive_draws'],
                    'team_type': 'home',
                    'expected_outcome': 'draw'
                }
            )
        elif (
            away_analysis['is_top_team']
            and away_analysis['consecutive_draws'] >= self.min_consecutive_draws
        ):
            return BettingOpportunity(
                match_id=match.id,
                home_team=match.home_team.name,
                away_team=match.away_team.name,
                league=match.league.name,
                country=match.league.country,
                rule_name='Top Team Drawing Streak',
                confidence=0.70,
                details={
                    'top_team': match.away_team.name,
                    'team_rank': match.away_team.rank,
                    'consecutive_draws': away_analysis['consecutive_draws'],
                    'team_type': 'away',
                    'expected_outcome': 'draw'
                }
            )

        return None

    def _rule_top_team_no_goals_vs_strong(
        self,
        match: Match,
        home_analysis: dict[str, Any],
        away_analysis: dict[str, Any],
        strength_diff: int,
    ) -> BettingOpportunity | None:
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
            return BettingOpportunity(
                match_id=match.id,
                home_team=match.home_team.name,
                away_team=match.away_team.name,
                league=match.league.name,
                country=match.league.country,
                rule_name='Top Team No Goals vs Strong',
                confidence=0.75,
                details={
                    'top_team': top_team_analysis['team'].name,
                    'top_team_rank': top_team_rank,
                    'opponent': opponent_analysis['team'].name,
                    'opponent_rank': opponent_rank,
                    'consecutive_no_goals': top_team_analysis['consecutive_no_goals'],
                    'expected_outcome': f'{opponent_analysis["team"].name} to win'
                }
            )

        return None

    def _apply_live_rules(self, match: Match) -> list[BettingOpportunity]:
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

    def _rule_live_red_card_draw_second_half(self, match: Match) -> BettingOpportunity | None:
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

            return BettingOpportunity(
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
                    'expected_outcome': f'{team_against} to win'
                }
            )

        return None

    def _rule_live_draw_top5_vs_below(self, match: Match) -> BettingOpportunity | None:
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

                return BettingOpportunity(
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
                        'expected_outcome': f'{top5_team} to win'
                    }
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
            return list(matches)
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

    def save_opportunity(self, opportunity: BettingOpportunity) -> DBBettingOpportunity:
        """Save betting opportunity to database"""
        match = None
        if opportunity.match_id:
            try:
                match = Match.get(Match.id == opportunity.match_id)
            except Match.DoesNotExist:
                logger.warning(f'Match {opportunity.match_id} not found for betting opportunity')

        # Determine opportunity type based on rule name
        opportunity_type = 'live_opportunity' if 'Live' in opportunity.rule_name else 'historical_analysis'

        db_opportunity = DBBettingOpportunity(
            match=match,
            opportunity_type=opportunity_type,
            rule_triggered=opportunity.rule_name,
            confidence_score=opportunity.confidence,
        )
        db_opportunity.set_details(opportunity.details)
        db_opportunity.save()
        return db_opportunity
