import asyncio
from typing import Any

import structlog

from app.bet_rules.structures import Bet
from app.db.models import BettingOpportunity
from app.db.storage import FootballDataStorage


logger = structlog.get_logger()


# Global bot instance for sending messages
_bot_instance = None


def get_bot_instance() -> Any:
    """Get or create bot instance for sending messages"""
    global _bot_instance
    if _bot_instance is None:
        from app.bot.core import bot

        _bot_instance = bot
    return _bot_instance


async def send_betting_opportunity(opportunity: Bet) -> None:
    """Send betting opportunity to users subscribed to live notifications"""
    try:
        # Get users subscribed to live notifications
        storage = FootballDataStorage()
        users = storage.get_users_for_live_notifications()
        bot = get_bot_instance()

        message_text = _format_opportunity_message(opportunity)

        for user in users:
            try:
                await bot.send_message(
                    user.telegram_id, message_text, parse_mode='HTML'
                )

                # Log the notification
                storage.log_notification(
                    user=user,
                    opportunity=None,  # Will be set when we have DB opportunity
                    message=message_text,
                    success=True,
                )

                # Add delay to avoid rate limiting
                await asyncio.sleep(0.1)

            except Exception as e:
                logger.error(
                    f'Failed to send notification to user {user.telegram_id}',
                    error=str(e),
                )

                # Log the failed notification
                storage.log_notification(
                    user=user,
                    opportunity=None,
                    message=message_text,
                    success=False,
                    error_message=str(e),
                )

        logger.info(f'Sent live betting opportunity to {len(users)} users')

    except Exception as e:
        logger.error('Error sending betting opportunities', error=str(e))


def _format_opportunity_message(opportunity: Bet) -> str:
    """Format betting opportunity as Telegram message"""
    confidence_emoji = (
        '🟢'
        if opportunity.confidence >= 0.8
        else '🟡'
        if opportunity.confidence >= 0.6
        else '🔴'
    )

    message = (
        f"🎯 <b>Betting Opportunity</b>\n\n"
        f"🏆 <b>{opportunity.rule_name}</b>\n"
        f"⚽ <b>{opportunity.home_team}</b> vs <b>{opportunity.away_team}</b>\n"
        f"🏟️ {opportunity.league} ({opportunity.country})\n"
        f"{confidence_emoji} <b>Confidence: {opportunity.confidence:.1%}</b>\n\n"
        f"💡 <b>Bet Type:</b> {opportunity.bet_type.value.replace('_', ' ').title()}\n"
        f"🎯 <b>Team Analyzed:</b> {opportunity.team_analyzed}\n\n"
        f"📊 Rule Type: {opportunity.slug.replace('_', ' ').title()}"
    )

    return message


async def send_daily_summary(opportunities: list[Bet]) -> None:
    """Send daily summary of betting opportunities to users subscribed to daily notifications"""
    if not opportunities:
        return

    try:
        storage = FootballDataStorage()
        users = storage.get_users_for_daily_notifications()
        bot = get_bot_instance()

        # Sort opportunities by confidence (highest first)
        sorted_opportunities = sorted(
            opportunities, key=lambda x: x.confidence, reverse=True
        )
        summary_text = _format_daily_summary(sorted_opportunities)

        for user in users:
            try:
                await bot.send_message(
                    user.telegram_id, summary_text, parse_mode='HTML'
                )
                await asyncio.sleep(0.1)

            except Exception as e:
                logger.error(
                    f'Failed to send daily summary to user {user.telegram_id}',
                    error=str(e),
                )

        logger.info(f'Sent daily summary to {len(users)} users')

    except Exception as e:
        logger.error('Error sending daily summary', error=str(e))


def _format_daily_summary(opportunities: list[Bet]) -> str:
    """Format daily summary message"""
    message = (
        f'📊 <b>Daily Betting Opportunities Summary</b>\n\n'
        f'Found {len(opportunities)} opportunities today:\n\n'
    )

    for i, opp in enumerate(opportunities, 1):  # Show all opportunities
        confidence_emoji = (
            '🟢' if opp.confidence >= 0.8 else '🟡' if opp.confidence >= 0.6 else '🔴'
        )

        # Format bet type for display
        bet_type_display = opp.bet_type.value.replace('_', ' ').title()

        # Determine which team to bet on based on team_analyzed
        if opp.team_analyzed == opp.home_team:
            bet_team = f'🏠 {opp.home_team}'
        elif opp.team_analyzed == opp.away_team:
            bet_team = f'✈️ {opp.away_team}'
        else:
            # Both teams or unclear - show both
            bet_team = f'🏠 {opp.home_team} or ✈️ {opp.away_team}'

        # Format match date if available
        match_date_display = f'📅 {opp.match_date}' if opp.match_date else '📅 Date TBD'
        message += (
            f'{i}. {confidence_emoji} <b>{opp.rule_name}</b>\n'
            f'   ⚽ {opp.home_team} vs {opp.away_team}\n'
            f'   🎯 Bet: {bet_type_display} on {bet_team}\n'
            f'   📊 Confidence: {opp.confidence:.1%}\n'
            f'   🏟️ {opp.league} ({opp.country})\n'
            f'   {match_date_display}\n\n'
        )

    message += 'Use /settings to adjust your notification preferences.'

    return message


def format_opportunities_message(opportunities: list[BettingOpportunity]) -> str:
    """Format betting opportunities message for display"""
    if not opportunities:
        return (
            '📊 <b>Current Betting Opportunities</b>\n\n'
            '❌ No active betting opportunities found at the moment.\n\n'
            'The bot continuously analyzes matches and will notify you when new '
            'opportunities are discovered.'
        )

    message = (
        f'📊 <b>Current Betting Opportunities</b>\n\n'
        f'Found {len(opportunities)} active opportunities:\n\n'
    )

    for i, opp in enumerate(opportunities, 1):
        # Convert BettingOpportunity to Bet to access opportunity_type
        bet = opp.to_domain()

        confidence_emoji = (
            '🟢' if bet.confidence >= 0.8 else '🟡' if bet.confidence >= 0.6 else '🔴'
        )

        # Get match information if available
        match_info = ''
        if opp.match:
            match_info = f'⚽ {opp.match.home_team.name} vs {opp.match.away_team.name}'
            if opp.match.match_date:
                match_date = opp.match.match_date.strftime('%Y-%m-%d %H:%M')
                match_info += f'\n📅 {match_date}'
        else:
            match_info = '⚽ Match details not available'

        message += (
            f"{i}. {confidence_emoji} <b>{bet.rule_name}</b>\n"
            f"   {match_info}\n"
            f"   🎯 Team Analyzed: {bet.team_analyzed}\n"
            f"   📊 Confidence: {bet.confidence:.1%}\n"
            f"   🏟️ Type: {bet.opportunity_type.value.replace('_', ' ').title()}\n"
        )

    message += 'Use /settings to adjust your notification preferences.'

    return message


def format_completed_opportunities_message(
    opportunities: list[BettingOpportunity], statistics: dict
) -> str:
    """Format completed betting opportunities message with statistics"""
    if not opportunities:
        return (
            '📊 <b>Completed Betting Opportunities</b>\n\n'
            '❌ No completed betting opportunities found.\n\n'
            'Completed opportunities will appear here once matches finish and outcomes are determined.'
        )

    # Statistics header
    stats_text = (
        f"📊 <b>Betting Performance Statistics</b>\n\n"
        f"🎯 Total Opportunities: {statistics['total']}\n"
        f"✅ Wins: {statistics['wins']}\n"
        f"❌ Losses: {statistics['losses']}\n"
        f"📈 Win Rate: {statistics['win_rate']}%\n\n"
    )

    # Recent completed opportunities
    message = (
        f'{stats_text}'
        f'📋 <b>Recent Completed Opportunities</b>\n\n'
        f'Showing last {len(opportunities)} completed opportunities:\n\n'
    )

    for i, opp in enumerate(opportunities, 1):
        # Convert BettingOpportunity to Bet to access opportunity_type
        bet = opp.to_domain()

        # Outcome emoji
        outcome_emoji = (
            '✅' if opp.outcome == 'win' else '❌' if opp.outcome == 'lose' else '⏳'
        )

        # Confidence emoji
        confidence_emoji = (
            '🟢' if bet.confidence >= 0.8 else '🟡' if bet.confidence >= 0.6 else '🔴'
        )

        # Get match information
        match_info = ''
        if opp.match:
            match_info = f'⚽ {opp.match.home_team.name} vs {opp.match.away_team.name}'
            if opp.match.home_score is not None and opp.match.away_score is not None:
                match_info += f' ({opp.match.home_score}-{opp.match.away_score})'
            if opp.match.match_date:
                match_date = opp.match.match_date.strftime('%Y-%m-%d %H:%M')
                match_info += f'\n📅 {match_date}'
        else:
            match_info = '⚽ Match details not available'

        message += (
            f"{i}. {outcome_emoji} <b>{bet.rule_name}</b>\n"
            f"   {match_info}\n"
            f"   🎯 Team Analyzed: {bet.team_analyzed}\n"
            f"   {confidence_emoji} Confidence: {bet.confidence:.1%}\n"
            f"   🏟️ Type: {bet.opportunity_type.value.replace('_', ' ').title()}\n"
            f"   📅 Created: {opp.created_at.strftime('%Y-%m-%d %H:%M')}\n\n"
        )

    message += 'Use /opportunities to see active opportunities.'

    return message
