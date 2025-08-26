from dataclasses import dataclass
from typing import Any

import structlog

from app.db.models import BettingOpportunity as DBBettingOpportunity
from app.db.models import Match, Team
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
    reasoning: str
    recommended_bet: str
    opportunity_type: str  # historical_analysis, live_opportunity
    details: dict[str, Any]


class BettingRulesEngine:
    def __init__(self) -> None:
        self.top_teams_count = settings.top_teams_count
        self.min_consecutive_losses = settings.min_consecutive_losses
        self.min_consecutive_draws = settings.min_consecutive_draws
        self.min_consecutive_losses_top5 = settings.min_consecutive_losses_top5
        self.min_no_goals_matches = settings.min_no_goals_matches
        self.live_draw_minute_threshold = settings.live_draw_minute_threshold

    def analyze_historical_matches(self) -> list[BettingOpportunity]:
        """Analyze historical matches for betting opportunities"""
        opportunities: list[BettingOpportunity] = []

        # Get all teams
        teams = Team.select()

        for team in teams:
            try:
                # Apply historical betting rules
                team_opportunities = self._apply_historical_rules(team)
                opportunities.extend(team_opportunities)
            except Exception as e:
                logger.error(f"Error analyzing team {team.name}", error=str(e))

        return opportunities

    def analyze_live_matches(self, live_matches: list[dict[str, Any]]) -> list[BettingOpportunity]:
        """Analyze live matches for betting opportunities"""
        opportunities: list[BettingOpportunity] = []

        for match_data in live_matches:
            try:
                # Apply live betting rules
                match_opportunities = self._apply_live_rules(match_data)
                opportunities.extend(match_opportunities)
            except Exception as e:
                logger.error(f"Error analyzing live match {match_data.get('home_team', '')} vs {match_data.get('away_team', '')}", error=str(e))

        return opportunities

    def _apply_historical_rules(self, team: Team) -> list[BettingOpportunity]:
        """Apply all historical betting rules to a team"""
        opportunities = []

        # Rule 1: Top-10 team with 3+ consecutive losses
        opportunity = self._rule_top_team_losing_streak(team)
        if opportunity:
            opportunities.append(opportunity)

        # Rule 2: Top-10 team with 3+ consecutive draws
        opportunity = self._rule_top_team_drawing_streak(team)
        if opportunity:
            opportunities.append(opportunity)

        # Rule 3: Top-5 team with 2+ consecutive losses
        opportunity = self._rule_top5_team_losing_streak(team)
        if opportunity:
            opportunities.append(opportunity)

        # Rule 4: Top-8 team with no goals in last 2+ matches
        opportunity = self._rule_top_team_no_goals(team)
        if opportunity:
            opportunities.append(opportunity)

        # Rule 5: Coach change
        opportunity = self._rule_coach_change(team)
        if opportunity:
            opportunities.append(opportunity)

        return opportunities

    def _apply_live_rules(self, match_data: dict[str, Any]) -> list[BettingOpportunity]:
        """Apply all live betting rules to a match"""
        opportunities = []

        # Rule 1: Red card + draw + second half
        opportunity = self._rule_live_red_card_draw_second_half(match_data)
        if opportunity:
            opportunities.append(opportunity)

        # Rule 2: Draw until 70+ minutes with top-5 vs below top-5
        opportunity = self._rule_live_draw_top5_vs_below(match_data)
        if opportunity:
            opportunities.append(opportunity)

        return opportunities

    def _rule_top_team_losing_streak(self, team: Team) -> BettingOpportunity | None:
        """Rule: Top-10 team with 3+ consecutive losses"""
        if team.rank > self.top_teams_count:
            return None

        recent_matches = self._get_recent_matches(team, self.min_consecutive_losses)
        if len(recent_matches) < self.min_consecutive_losses:
            return None

        # Check for consecutive losses
        consecutive_losses = 0
        for match in recent_matches[:self.min_consecutive_losses]:
            if self._team_lost(match, team):
                consecutive_losses += 1
            else:
                break

        if consecutive_losses >= self.min_consecutive_losses:
            return BettingOpportunity(
                match_id=None,
                home_team=team.name,
                away_team="",
                league=team.league,
                country=team.country,
                rule_name="Top Team Losing Streak",
                confidence=0.75,
                reasoning=f"Top-{self.top_teams_count} team {team.name} has lost {consecutive_losses} consecutive matches",
                recommended_bet="Bet against this team in next match",
                opportunity_type="historical_analysis",
                details={
                    "team_rank": team.rank,
                    "consecutive_losses": consecutive_losses,
                    "last_matches": [self._match_to_dict(m) for m in recent_matches[:consecutive_losses]]
                }
            )

        return None

    def _rule_top_team_drawing_streak(self, team: Team) -> BettingOpportunity | None:
        """Rule: Top-10 team with 3+ consecutive draws"""
        if team.rank > self.top_teams_count:
            return None

        recent_matches = self._get_recent_matches(team, self.min_consecutive_draws)
        if len(recent_matches) < self.min_consecutive_draws:
            return None

        # Check for consecutive draws
        consecutive_draws = 0
        for match in recent_matches[:self.min_consecutive_draws]:
            if self._team_drew(match, team):
                consecutive_draws += 1
            else:
                break

        if consecutive_draws >= self.min_consecutive_draws:
            return BettingOpportunity(
                match_id=None,
                home_team=team.name,
                away_team="",
                league=team.league,
                country=team.country,
                rule_name="Top Team Drawing Streak",
                confidence=0.70,
                reasoning=f"Top-{self.top_teams_count} team {team.name} has drawn {consecutive_draws} consecutive matches",
                recommended_bet="Bet on draw or under 2.5 goals in next match",
                opportunity_type="historical_analysis",
                details={
                    "team_rank": team.rank,
                    "consecutive_draws": consecutive_draws,
                    "last_matches": [self._match_to_dict(m) for m in recent_matches[:consecutive_draws]]
                }
            )

        return None

    def _rule_top5_team_losing_streak(self, team: Team) -> BettingOpportunity | None:
        """Rule: Top-5 team with 2+ consecutive losses"""
        if team.rank > 5:
            return None

        recent_matches = self._get_recent_matches(team, self.min_consecutive_losses_top5)
        if len(recent_matches) < self.min_consecutive_losses_top5:
            return None

        # Check for consecutive losses
        consecutive_losses = 0
        for match in recent_matches[:self.min_consecutive_losses_top5]:
            if self._team_lost(match, team):
                consecutive_losses += 1
            else:
                break

        if consecutive_losses >= self.min_consecutive_losses_top5:
            return BettingOpportunity(
                match_id=None,
                home_team=team.name,
                away_team="",
                league=team.league,
                country=team.country,
                rule_name="Top-5 Team Losing Streak",
                confidence=0.80,
                reasoning=f"Top-5 team {team.name} has lost {consecutive_losses} consecutive matches",
                recommended_bet="Strong bet against this team in next match",
                opportunity_type="historical_analysis",
                details={
                    "team_rank": team.rank,
                    "consecutive_losses": consecutive_losses,
                    "last_matches": [self._match_to_dict(m) for m in recent_matches[:consecutive_losses]]
                }
            )

        return None

    def _rule_top_team_no_goals(self, team: Team) -> BettingOpportunity | None:
        """Rule: Top-8 team with no goals in last 2+ matches"""
        if team.rank > 8:
            return None

        recent_matches = self._get_recent_matches(team, self.min_no_goals_matches)
        if len(recent_matches) < self.min_no_goals_matches:
            return None

        # Check for no goals in consecutive matches
        no_goals_matches = 0
        for match in recent_matches[:self.min_no_goals_matches]:
            if self._team_goals_scored(match, team) == 0:
                no_goals_matches += 1
            else:
                break

        if no_goals_matches >= self.min_no_goals_matches:
            return BettingOpportunity(
                match_id=None,
                home_team=team.name,
                away_team="",
                league=team.league,
                country=team.country,
                rule_name="Top Team No Goals",
                confidence=0.75,
                reasoning=f"Top-8 team {team.name} has scored 0 goals in {no_goals_matches} consecutive matches",
                recommended_bet="Bet on under 2.5 goals or against this team",
                opportunity_type="historical_analysis",
                details={
                    "team_rank": team.rank,
                    "no_goals_matches": no_goals_matches,
                    "last_matches": [self._match_to_dict(m) for m in recent_matches[:no_goals_matches]]
                }
            )

        return None

    def _rule_coach_change(self, team: Team) -> BettingOpportunity | None:
        """Rule: Recent coach change (this would need additional data)"""
        # This rule requires coach change data from API
        # For now, we'll implement a placeholder
        # TODO: Implement when coach change data is available

        # Check if team has poor recent form (potential indicator of coach change)
        recent_matches = self._get_recent_matches(team, 5)
        if len(recent_matches) < 3:
            return None

        losses = sum(1 for match in recent_matches[:3] if self._team_lost(match, team))
        draws = sum(1 for match in recent_matches[:3] if self._team_drew(match, team))

        # If team has very poor form, it might indicate coaching issues
        if losses >= 2 and team.rank <= self.top_teams_count:
            return BettingOpportunity(
                match_id=None,
                home_team=team.name,
                away_team="",
                league=team.league,
                country=team.country,
                rule_name="Potential Coaching Issues",
                confidence=0.60,
                reasoning=f"Top team {team.name} has poor recent form ({losses} losses, {draws} draws in last 3 matches)",
                recommended_bet="Monitor for coaching changes, bet against if confirmed",
                opportunity_type="historical_analysis",
                details={
                    "team_rank": team.rank,
                    "recent_losses": losses,
                    "recent_draws": draws,
                    "last_matches": [self._match_to_dict(m) for m in recent_matches[:3]]
                }
            )

        return None

    def _rule_live_red_card_draw_second_half(self, match_data: dict[str, Any]) -> BettingOpportunity | None:
        """Rule: Red card + draw + second half"""
        minute = match_data.get('minute', 0)
        home_score = match_data.get('home_score', 0)
        away_score = match_data.get('away_score', 0)
        red_cards_home = match_data.get('red_cards_home', 0)
        red_cards_away = match_data.get('red_cards_away', 0)

        # Check conditions
        has_red_card = red_cards_home > 0 or red_cards_away > 0
        is_draw = home_score == away_score
        is_second_half = minute >= 45

        if has_red_card and is_draw and is_second_half:
            team_with_red = match_data.get('home_team', '') if red_cards_home > 0 else match_data.get('away_team', '')
            return BettingOpportunity(
                match_id=None,
                home_team=match_data.get('home_team', ''),
                away_team=match_data.get('away_team', ''),
                league=match_data.get('league', ''),
                country=match_data.get('country', ''),
                rule_name="Live Red Card + Draw + Second Half",
                confidence=0.85,
                reasoning=f"Red card for {team_with_red} with draw at {minute} minutes - high chance of goals",
                recommended_bet="Bet on over 2.5 goals or goals in second half",
                opportunity_type="live_opportunity",
                details={
                    "minute": minute,
                    "score": f"{home_score}-{away_score}",
                    "red_cards_home": red_cards_home,
                    "red_cards_away": red_cards_away,
                    "team_with_red": team_with_red
                }
            )

        return None

    def _rule_live_draw_top5_vs_below(self, match_data: dict[str, Any]) -> BettingOpportunity | None:
        """Rule: Draw until 70+ minutes with top-5 vs below top-5"""
        minute = match_data.get('minute', 0)
        home_score = match_data.get('home_score', 0)
        away_score = match_data.get('away_score', 0)

        # Check if it's a draw and past the threshold
        is_draw = home_score == away_score
        is_past_threshold = minute >= self.live_draw_minute_threshold

        if is_draw and is_past_threshold:
            # This rule requires team ranking data
            # For now, we'll create a generic opportunity
            return BettingOpportunity(
                match_id=None,
                home_team=match_data.get('home_team', ''),
                away_team=match_data.get('away_team', ''),
                league=match_data.get('league', ''),
                country=match_data.get('country', ''),
                rule_name="Live Draw Past 70 Minutes",
                confidence=0.70,
                reasoning=f"Draw at {minute} minutes - potential for late goals",
                recommended_bet="Bet on over 1.5 goals or late goals",
                opportunity_type="live_opportunity",
                details={
                    "minute": minute,
                    "score": f"{home_score}-{away_score}",
                    "threshold": self.live_draw_minute_threshold
                }
            )

        return None

    def _get_recent_matches(self, team: Team, limit: int) -> list[Match]:
        """Get recent matches for a team"""
        return (Match.select()
                .where((Match.home_team == team) | (Match.away_team == team))
                .where(Match.status == 'finished')
                .order_by(Match.match_date.desc())
                .limit(limit))

    def _team_won(self, match: Match, team: Team) -> bool:
        """Check if team won the match"""
        if match.home_team == team:
            return match.home_score > match.away_score
        else:
            return match.away_score > match.home_score

    def _team_lost(self, match: Match, team: Team) -> bool:
        """Check if team lost the match"""
        if match.home_team == team:
            return match.home_score < match.away_score
        else:
            return match.away_score < match.home_score

    def _team_drew(self, match: Match, team: Team) -> bool:
        """Check if team drew the match"""
        return match.home_score == match.away_score

    def _team_goals_scored(self, match: Match, team: Team) -> int:
        """Get goals scored by team in match"""
        if match.home_team == team:
            return match.home_score or 0
        else:
            return match.away_score or 0

    def _match_to_dict(self, match: Match) -> dict[str, Any]:
        """Convert match to dictionary for details"""
        return {
            "date": match.match_date.isoformat() if match.match_date else None,
            "home_team": match.home_team.name if match.home_team else "",
            "away_team": match.away_team.name if match.away_team else "",
            "home_score": match.home_score,
            "away_score": match.away_score,
            "status": match.status
        }

    def save_opportunity(self, opportunity: BettingOpportunity) -> DBBettingOpportunity:
        """Save betting opportunity to database"""
        db_opportunity = DBBettingOpportunity(
            match_id=opportunity.match_id,
            live_match_id=None,  # Will be set if it's a live opportunity
            opportunity_type=opportunity.opportunity_type,
            rule_triggered=opportunity.rule_name,
            confidence_score=opportunity.confidence,
            is_active=True
        )
        db_opportunity.set_details(opportunity.details)
        db_opportunity.save()
        return db_opportunity
