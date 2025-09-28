#!/usr/bin/env python3
"""
Migration script to update confidence scores for ConsecutiveLossesRule opportunities.

This script recalculates confidence scores for existing betting opportunities
that were created with the old confidence calculation method, which didn't include
rank-based bonuses when opponent analysis is available.

The new calculation includes:
- Base confidence calculation (existing)
- Rank-based confidence bonus when opponent analysis is available
- Rank difference bonus: 0.025 * rank_difference when team has higher rank
"""

import json
import sys
from pathlib import Path

# Add the project root to the Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import structlog
from app.db.models import BettingOpportunity, Match, Team, db
from app.bet_rules.models import ConsecutiveLossesRule
from app.bet_rules.team_analysis import TeamAnalysis, TeamAnalysisService
from app.db.storage import FootballDataStorage

logger = structlog.get_logger()


def calculate_new_confidence(opportunity: BettingOpportunity) -> float:
    """
    Calculate new confidence score using the updated ConsecutiveLossesRule logic.
    
    This replicates the logic from ConsecutiveLossesRule.calculate_confidence()
    but works with the stored opportunity data.
    """
    try:
        # Get match and team information
        match = opportunity.match
        if not match:
            logger.warning(f"Opportunity {opportunity.id} has no associated match")
            return opportunity.confidence_score
        
        # Get opportunity details
        details = opportunity.get_details()
        home_team_rank = details.get('home_team_rank')
        away_team_rank = details.get('away_team_rank')
        home_confidence = details.get('home_confidence', 0.0)
        away_confidence = details.get('away_confidence', 0.0)
        
        # Determine which team was analyzed
        home_fits = details.get('home_team_fits', False)
        away_fits = details.get('away_team_fits', False)
        
        if not home_fits and not away_fits:
            logger.warning(f"Opportunity {opportunity.id} has no team fits")
            return opportunity.confidence_score
        
        # Calculate new confidence based on which team(s) fit the rule
        if home_fits and away_fits:
            # Both teams fit - use average with rank bonus
            base_confidence = (home_confidence + away_confidence) / 2
            
            # Apply rank bonus if both teams have ranks
            if home_team_rank and away_team_rank:
                # Calculate rank difference for both teams
                home_rank_bonus = 0.0
                away_rank_bonus = 0.0
                
                if home_team_rank < away_team_rank:  # Home team has higher rank (lower number)
                    home_rank_bonus = 0.025 * (away_team_rank - home_team_rank)
                elif away_team_rank < home_team_rank:  # Away team has higher rank
                    away_rank_bonus = 0.025 * (home_team_rank - away_team_rank)
                
                # Apply the larger bonus
                rank_bonus = max(home_rank_bonus, away_rank_bonus)
                base_confidence += rank_bonus
                
        elif home_fits:
            # Only home team fits
            base_confidence = home_confidence
            
            # Apply rank bonus if both teams have ranks
            if home_team_rank and away_team_rank and home_team_rank < away_team_rank:
                rank_difference = away_team_rank - home_team_rank
                rank_bonus = 0.025 * rank_difference
                base_confidence += rank_bonus
                logger.info(f"Applied home team rank bonus: +{rank_bonus:.3f} (rank diff: {rank_difference})")
                
        else:  # away_fits
            # Only away team fits
            base_confidence = away_confidence
            
            # Apply rank bonus if both teams have ranks
            if home_team_rank and away_team_rank and away_team_rank < home_team_rank:
                rank_difference = home_team_rank - away_team_rank
                rank_bonus = 0.025 * rank_difference
                base_confidence += rank_bonus
                logger.info(f"Applied away team rank bonus: +{rank_bonus:.3f} (rank diff: {rank_difference})")
        
        # Cap at 1.0
        return min(1.0, base_confidence)
        
    except Exception as e:
        logger.error(f"Error calculating new confidence for opportunity {opportunity.id}: {e}")
        return opportunity.confidence_score


def update_consecutive_losses_confidence():
    """Update confidence scores for all ConsecutiveLossesRule opportunities."""
    
    # Get all opportunities for ConsecutiveLossesRule
    opportunities = list(
        BettingOpportunity.select()
        .where(BettingOpportunity.rule_triggered == 'Consecutive Losses Rule')
    )
    
    logger.info(f"Found {len(opportunities)} ConsecutiveLossesRule opportunities to update")
    
    updated_count = 0
    total_confidence_increase = 0.0
    
    with db.atomic():
        for opportunity in opportunities:
            old_confidence = opportunity.confidence_score
            new_confidence = calculate_new_confidence(opportunity)
            
            if abs(new_confidence - old_confidence) > 0.001:  # Only update if there's a meaningful change
                opportunity.confidence_score = new_confidence
                opportunity.save()
                
                confidence_increase = new_confidence - old_confidence
                total_confidence_increase += confidence_increase
                updated_count += 1
                
                logger.info(
                    f"Updated opportunity {opportunity.id}: "
                    f"{old_confidence:.3f} -> {new_confidence:.3f} "
                    f"(+{confidence_increase:.3f})"
                )
    
    logger.info(f"Updated {updated_count} opportunities")
    logger.info(f"Total confidence increase: {total_confidence_increase:.3f}")
    logger.info(f"Average confidence increase: {total_confidence_increase / max(updated_count, 1):.3f}")


def main():
    """Main migration function."""
    logger.info("Starting ConsecutiveLossesRule confidence migration")
    
    try:
        # Initialize database connection
        db.connect()
        
        # Run the migration
        update_consecutive_losses_confidence()
        
        logger.info("Migration completed successfully")
        
    except Exception as e:
        logger.error(f"Migration failed: {e}")
        raise
    finally:
        if not db.is_closed():
            db.close()


if __name__ == "__main__":
    main()
