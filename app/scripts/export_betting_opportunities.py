"""Script to export completed betting opportunities to CSV"""

import csv
from pathlib import Path
import sys

import structlog

from app.bet_rules.rule_engine import BettingRulesEngine
from app.bet_rules.structures import BetOutcome
from app.db.session import get_sync_session_local
from app.db.sqlalchemy_models import BettingOpportunity


logger = structlog.get_logger()


def export_betting_opportunities_to_csv(output_file: str = 'betting_opportunities.csv'):
    """Export all completed betting opportunities to CSV file"""
    session_local = get_sync_session_local()
    db = session_local()

    try:
        # Query all completed betting opportunities (outcome != 'unknown')
        opportunities = (
            db.query(BettingOpportunity)
            .filter(BettingOpportunity.outcome != BetOutcome.UNKNOWN.value)
            .join(BettingOpportunity.match)
            .order_by(BettingOpportunity.created_at.desc())
            .all()
        )

        logger.info(f'Found {len(opportunities)} completed betting opportunities')

        if not opportunities:
            logger.warning('No completed betting opportunities found')
            return

        # Initialize rule engine to get rule information
        rule_engine = BettingRulesEngine()

        # Prepare CSV data
        csv_rows = []

        for opp in opportunities:
            match = opp.match
            details = opp.get_details()

            # Get rule information
            rule = rule_engine.get_rule_by_slug(opp.rule_slug)
            rule_name = rule.name if rule else 'Unknown Rule'
            bet_type = rule.bet_type.value if rule else 'Unknown'
            opportunity_type = rule.opportunity_type.value if rule else 'Unknown'

            # Format match date
            match_date_str = (
                match.match_date.strftime('%Y-%m-%d %H:%M')
                if match.match_date
                else 'N/A'
            )

            # Format created_at
            created_at_str = (
                opp.created_at.strftime('%Y-%m-%d %H:%M:%S')
                if opp.created_at
                else 'N/A'
            )

            # Extract additional details from JSON
            home_confidence = details.get('home_confidence', 'N/A')
            away_confidence = details.get('away_confidence', 'N/A')
            home_team_rank = details.get('home_team_rank', 'N/A')
            away_team_rank = details.get('away_team_rank', 'N/A')
            home_consecutive_losses = details.get('home_consecutive_losses', 'N/A')
            away_consecutive_losses = details.get('away_consecutive_losses', 'N/A')
            home_consecutive_draws = details.get('home_consecutive_draws', 'N/A')
            away_consecutive_draws = details.get('away_consecutive_draws', 'N/A')
            home_consecutive_no_goals = details.get('home_consecutive_no_goals', 'N/A')
            away_consecutive_no_goals = details.get('away_consecutive_no_goals', 'N/A')
            red_cards_home = details.get('red_cards_home', match.red_cards_home)
            red_cards_away = details.get('red_cards_away', match.red_cards_away)
            minute = details.get('minute', match.minute)

            row = {
                'opportunity_id': opp.id,
                'match_id': match.id,
                'match_date': match_date_str,
                'league': match.league.name,
                'country': match.league.country,
                'home_team': match.home_team.name,
                'away_team': match.away_team.name,
                'home_score': match.home_score
                if match.home_score is not None
                else 'N/A',
                'away_score': match.away_score
                if match.away_score is not None
                else 'N/A',
                'match_status': match.status,
                'minute': minute if minute is not None else 'N/A',
                'red_cards_home': red_cards_home,
                'red_cards_away': red_cards_away,
                'season': match.season,
                'round': match.round if match.round is not None else 'N/A',
                'rule_slug': opp.rule_slug,
                'rule_name': rule_name,
                'bet_type': bet_type,
                'opportunity_type': opportunity_type,
                'confidence_score': opp.confidence_score,
                'team_analyzed': details.get('team_analyzed', 'N/A'),
                'outcome': opp.outcome,
                'home_team_rank': home_team_rank,
                'away_team_rank': away_team_rank,
                'home_confidence': home_confidence,
                'away_confidence': away_confidence,
                'home_consecutive_losses': home_consecutive_losses,
                'away_consecutive_losses': away_consecutive_losses,
                'home_consecutive_draws': home_consecutive_draws,
                'away_consecutive_draws': away_consecutive_draws,
                'home_consecutive_no_goals': home_consecutive_no_goals,
                'away_consecutive_no_goals': away_consecutive_no_goals,
                'created_at': created_at_str,
            }

            csv_rows.append(row)

        # Write to CSV
        if csv_rows:
            fieldnames = [
                'opportunity_id',
                'match_id',
                'match_date',
                'league',
                'country',
                'home_team',
                'away_team',
                'home_score',
                'away_score',
                'match_status',
                'minute',
                'red_cards_home',
                'red_cards_away',
                'season',
                'round',
                'rule_slug',
                'rule_name',
                'bet_type',
                'opportunity_type',
                'confidence_score',
                'team_analyzed',
                'outcome',
                'home_team_rank',
                'away_team_rank',
                'home_confidence',
                'away_confidence',
                'home_consecutive_losses',
                'away_consecutive_losses',
                'home_consecutive_draws',
                'away_consecutive_draws',
                'home_consecutive_no_goals',
                'away_consecutive_no_goals',
                'created_at',
            ]

            output_path = Path(output_file)
            with open(output_path, 'w', newline='', encoding='utf-8') as csvfile:
                writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerows(csv_rows)

            logger.info(
                f'Exported {len(csv_rows)} betting opportunities to {output_path.absolute()}'
            )
        else:
            logger.warning('No data to export')

    except Exception as e:
        logger.error(f'Error exporting betting opportunities: {e}', exc_info=True)
        raise
    finally:
        db.close()


if __name__ == '__main__':
    output_file = sys.argv[1] if len(sys.argv) > 1 else 'betting_opportunities.csv'
    export_betting_opportunities_to_csv(output_file)
