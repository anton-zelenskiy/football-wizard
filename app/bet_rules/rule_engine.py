import structlog

from app.db.models import Match
from app.db.storage import FootballDataStorage
from app.settings import settings

from .models import (
    Bet,
    BettingRule,
    ConsecutiveDrawsRule,
    ConsecutiveLossesRule,
    LiveMatchRedCardRule,
    Top5ConsecutiveLossesRule,
)
from .team_analysis import TeamAnalysis, TeamAnalysisService

logger = structlog.get_logger()


class BettingRulesEngine:
    """Betting rules engine with configurable rules"""

    def __init__(self) -> None:
        self.storage = FootballDataStorage()
        self.top_teams_count = settings.top_teams_count
        self.team_analysis_service = TeamAnalysisService(
            top_teams_count=self.top_teams_count, min_consecutive_losses=3
        )

        self.rules: list[BettingRule] = [
            ConsecutiveLossesRule(),
            ConsecutiveDrawsRule(),
            Top5ConsecutiveLossesRule(),
            LiveMatchRedCardRule(),
        ]
        self.live_rule = LiveMatchRedCardRule()

    def get_rule_by_type(self, rule_type: str) -> BettingRule | None:
        """Get a rule by its type"""
        for rule in self.rules:
            if rule.rule_type == rule_type:
                return rule
        return None

    def analyze_scheduled_matches(self) -> list[Bet]:
        """Analyze scheduled matches for betting opportunities"""
        opportunities: list[Bet] = []
        processed_matches = set()

        # Get all scheduled matches
        scheduled_matches = self.storage.get_scheduled_matches(days_ahead=7)

        for match in scheduled_matches:
            try:
                # Create a unique match identifier
                match_id = f'{match.home_team.name}_{match.away_team.name}'

                # Skip if we've already processed this match
                if match_id in processed_matches:
                    continue

                # Analyze the match
                match_opportunities = self._analyze_match(match)
                opportunities.extend(match_opportunities)
                processed_matches.add(match_id)

            except Exception as e:
                logger.error(
                    f'Error analyzing scheduled match {match.home_team.name} vs '
                    f'{match.away_team.name}',
                    error=str(e),
                )

        return opportunities

    def _analyze_match(self, match: Match) -> list[Bet]:
        """Analyze a single match for betting opportunities"""
        opportunities: list[Bet] = []

        # Get recent matches for both teams
        home_recent_matches = self.storage.get_team_recent_finished_matches(
            match.home_team, count=5
        )
        away_recent_matches = self.storage.get_team_recent_finished_matches(
            match.away_team, count=5
        )

        # Analyze both teams
        home_analysis = self.team_analysis_service.analyze_team_performance(
            match.home_team, 'home', home_recent_matches
        )
        away_analysis = self.team_analysis_service.analyze_team_performance(
            match.away_team, 'away', away_recent_matches
        )

        # Check each rule for both teams and create one opportunity per rule
        for rule in self.rules:
            opportunity = self._check_rule_for_match(match, rule, home_analysis, away_analysis)
            if opportunity:
                opportunities.append(opportunity)

        return opportunities

    def _check_rule_for_match(
        self,
        match: Match,
        rule: BettingRule,
        home_analysis: TeamAnalysis,
        away_analysis: TeamAnalysis,
    ) -> Bet | None:
        """Check a specific rule for both teams and create one opportunity per match"""
        home_confidence = rule.calculate_confidence(home_analysis, away_analysis)
        away_confidence = rule.calculate_confidence(away_analysis, home_analysis)

        # If neither team fits the rule, no opportunity
        if home_confidence == 0 and away_confidence == 0:
            return None

        # Determine which team(s) fit the rule
        home_fits = home_confidence > 0
        away_fits = away_confidence > 0
        both_fit = home_fits and away_fits

        # Calculate final confidence
        if both_fit:
            # Both teams fit the rule - use average confidence but mark as uncertain
            final_confidence = (home_confidence + away_confidence) / 2
            team_analyzed = f'{match.home_team.name} & {match.away_team.name}'
            uncertainty_note = 'Both teams fit rule - high uncertainty'
        elif home_fits:
            final_confidence = home_confidence
            team_analyzed = match.home_team.name
            uncertainty_note = None
        else:  # away_fits
            final_confidence = away_confidence
            team_analyzed = match.away_team.name
            uncertainty_note = None

        # Create opportunity details
        details = {
            'home_team_fits': home_fits,
            'away_team_fits': away_fits,
            'both_teams_fit': both_fit,
            'home_confidence': home_confidence,
            'away_confidence': away_confidence,
            'home_team_rank': home_analysis.team.rank,
            'away_team_rank': away_analysis.team.rank,
            'home_consecutive_losses': home_analysis.consecutive_losses,
            'away_consecutive_losses': away_analysis.consecutive_losses,
            'home_consecutive_draws': home_analysis.consecutive_draws,
            'away_consecutive_draws': away_analysis.consecutive_draws,
            'home_consecutive_no_goals': home_analysis.consecutive_no_goals,
            'away_consecutive_no_goals': away_analysis.consecutive_no_goals,
            'home_is_top_5': home_analysis.is_top5_team,
            'away_is_top_5': away_analysis.is_top5_team,
        }

        if uncertainty_note:
            details['uncertainty_note'] = uncertainty_note

        return Bet(
            match_id=match.id,
            home_team=match.home_team.name,
            away_team=match.away_team.name,
            league=match.league.name,
            country=match.league.country,
            match_date=match.match_date.strftime('%Y-%m-%d %H:%M') if match.match_date else None,
            rule_name=rule.name,
            rule_type=rule.rule_type,
            bet_type=rule.bet_type,
            confidence=final_confidence,
            team_analyzed=team_analyzed,
            opportunity_type='historical_analysis',  # Scheduled matches are historical analysis
            details=details,
        )

    def analyze_live_matches(self) -> list[Bet]:
        """Analyze live matches for betting opportunities"""
        opportunities: list[Bet] = []
        processed_matches = set()

        # Get all live matches
        live_matches = self.storage.get_live_matches()

        for match in live_matches:
            try:
                # Create a unique match identifier
                match_id = f'{match.home_team.name}_{match.away_team.name}'

                # Skip if we've already processed this match
                if match_id in processed_matches:
                    continue

                # Analyze the live match
                match_opportunities = self._analyze_live_match(match)
                opportunities.extend(match_opportunities)
                processed_matches.add(match_id)

            except Exception as e:
                logger.error(
                    f'Error analyzing live match {match.home_team.name} vs {match.away_team.name}',
                    error=str(e),
                )

        return opportunities

    def _analyze_live_match(self, match: Match) -> list[Bet]:
        """Analyze a single live match for betting opportunities"""
        opportunities: list[Bet] = []

        # Get recent matches for both teams
        home_recent_matches = self.storage.get_team_recent_finished_matches(
            match.home_team, count=5
        )
        away_recent_matches = self.storage.get_team_recent_finished_matches(
            match.away_team, count=5
        )

        # Analyze both teams
        home_analysis = self.team_analysis_service.analyze_team_performance(
            match.home_team, 'home', home_recent_matches
        )
        away_analysis = self.team_analysis_service.analyze_team_performance(
            match.away_team, 'away', away_recent_matches
        )

        # Check live match rule
        confidence, team_analyzed = self.live_rule.calculate_live_confidence(
            home_analysis=home_analysis,
            away_analysis=away_analysis,
            red_cards_home=match.red_cards_home,
            red_cards_away=match.red_cards_away,
            home_score=match.home_score or 0,
            away_score=match.away_score or 0
        )

        if confidence > 0:
            # Create opportunity details
            details = {
                'live_match': True,
                'red_cards_home': match.red_cards_home,
                'red_cards_away': match.red_cards_away,
                'current_score': f'{match.home_score or 0}-{match.away_score or 0}',
                'minute': match.minute,
                'home_team_rank': home_analysis.team.rank,
                'away_team_rank': away_analysis.team.rank,
                'home_consecutive_no_goals': home_analysis.consecutive_no_goals,
                'away_consecutive_no_goals': away_analysis.consecutive_no_goals,
                'home_consecutive_draws': home_analysis.consecutive_draws,
                'away_consecutive_draws': away_analysis.consecutive_draws,
                'home_consecutive_losses': home_analysis.consecutive_losses,
                'away_consecutive_losses': away_analysis.consecutive_losses,
            }

            opportunity = Bet(
                match_id=match.id,
                home_team=match.home_team.name,
                away_team=match.away_team.name,
                league=match.league.name,
                country=match.league.country,
                match_date=(
                    match.match_date.strftime('%Y-%m-%d %H:%M') 
                    if match.match_date else None
                ),
                rule_name=self.live_rule.name,
                rule_type=self.live_rule.rule_type,
                bet_type=self.live_rule.bet_type,
                confidence=confidence,
                team_analyzed=team_analyzed,
                opportunity_type='live_opportunity',  # Live matches are live opportunities
                details=details,
            )

            opportunities.append(opportunity)

        return opportunities
