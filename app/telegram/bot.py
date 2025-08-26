import asyncio

import structlog
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder

from app.betting_rules import BettingOpportunity as RuleOpportunity
from app.db.models import NotificationLog, TelegramUser
from app.settings import settings

logger = structlog.get_logger()


class BettingBot:
    def __init__(self) -> None:
        self.bot = Bot(token=settings.telegram_bot_token)
        self.dp = Dispatcher()
        self._setup_handlers()

    def _setup_handlers(self) -> None:
        """Setup all bot handlers"""
        self.dp.message.register(self.start_command, Command("start"))
        self.dp.message.register(self.help_command, Command("help"))
        self.dp.message.register(self.status_command, Command("status"))
        self.dp.message.register(self.settings_command, Command("settings"))
        self.dp.message.register(self.unsubscribe_command, Command("unsubscribe"))
        self.dp.message.register(self.subscribe_command, Command("subscribe"))
        self.dp.callback_query.register(self.handle_callback)

    async def start_command(self, message: types.Message) -> None:
        """Handle /start command"""
        user_id = message.from_user.id
        username = message.from_user.username
        first_name = message.from_user.first_name
        last_name = message.from_user.last_name

        # Check if user already exists
        user, created = TelegramUser.get_or_create(
            telegram_id=user_id,
            defaults={
                'username': username,
                'first_name': first_name,
                'last_name': last_name,
                'is_active': True,
                'notification_frequency': 'daily'
            }
        )

        if not created:
            # Update user info
            user.username = username
            user.first_name = first_name
            user.last_name = last_name
            user.is_active = True
            user.save()

        welcome_text = (
            f"🎯 Welcome to Football Betting Analysis Bot!\n\n"
            f"Hi {first_name or 'there'}! I'll help you find betting opportunities "
            f"based on team statistics and live match analysis.\n\n"
            f"📊 I monitor:\n"
            f"• Top-7 European leagues\n"
            f"• Champions League, Europa League, Conference League\n"
            f"• Russian Premier League\n\n"
            f"🔍 I look for:\n"
            f"• Teams with poor recent form\n"
            f"• Live match opportunities (red cards, draws)\n"
            f"• Historical patterns and trends\n\n"
            f"Use /help to see all available commands."
        )

        keyboard = InlineKeyboardBuilder()
        keyboard.add(InlineKeyboardButton(text="📊 View Settings", callback_data="settings"))
        keyboard.add(InlineKeyboardButton(text="❓ Help", callback_data="help"))

        await message.answer(welcome_text, reply_markup=keyboard.as_markup())
        logger.info(f"User {user_id} started the bot")

    async def help_command(self, message: types.Message) -> None:
        """Handle /help command"""
        help_text = (
            "🤖 Football Betting Analysis Bot - Commands\n\n"
            "/start - Start the bot and subscribe to notifications\n"
            "/help - Show this help message\n"
            "/status - Check your subscription status\n"
            "/settings - Configure notification preferences\n"
            "/subscribe - Subscribe to notifications\n"
            "/unsubscribe - Unsubscribe from notifications\n\n"
            "📱 You can also use the inline buttons for quick access.\n\n"
            "💡 The bot will automatically notify you about:\n"
            "• Daily betting opportunities\n"
            "• Live match opportunities (every 3 minutes)\n"
            "• Special alerts for high-confidence bets"
        )

        await message.answer(help_text)

    async def status_command(self, message: types.Message) -> None:
        """Handle /status command"""
        user_id = message.from_user.id

        try:
            user = TelegramUser.get(TelegramUser.telegram_id == user_id)

            status_text = (
                f"📊 Your Subscription Status\n\n"
                f"✅ Status: {'Active' if user.is_active else 'Inactive'}\n"
                f"🔔 Notifications: {user.notification_frequency}\n"
                f"📅 Joined: {user.created_at.strftime('%Y-%m-%d %H:%M')}\n"
                f"🔄 Last Updated: {user.updated_at.strftime('%Y-%m-%d %H:%M')}\n\n"
            )

            if user.is_active:
                status_text += "🎯 You'll receive betting opportunities based on your settings."
            else:
                status_text += "❌ You're not receiving notifications. Use /subscribe to start."

            keyboard = InlineKeyboardBuilder()
            if user.is_active:
                keyboard.add(InlineKeyboardButton(text="⚙️ Settings", callback_data="settings"))
                keyboard.add(InlineKeyboardButton(text="🔕 Unsubscribe", callback_data="unsubscribe"))
            else:
                keyboard.add(InlineKeyboardButton(text="✅ Subscribe", callback_data="subscribe"))

            await message.answer(status_text, reply_markup=keyboard.as_markup())

        except TelegramUser.DoesNotExist:
            await message.answer(
                "❌ You're not registered. Use /start to subscribe to notifications."
            )

    async def settings_command(self, message: types.Message) -> None:
        """Handle /settings command"""
        await self._show_settings(message.from_user.id, message.chat.id)

    async def subscribe_command(self, message: types.Message) -> None:
        """Handle /subscribe command"""
        user_id = message.from_user.id

        try:
            user = TelegramUser.get(TelegramUser.telegram_id == user_id)
            user.is_active = True
            user.save()

            await message.answer(
                "✅ Successfully subscribed to betting notifications!\n\n"
                "You'll now receive:\n"
                "• Daily betting opportunities\n"
                "• Live match alerts\n"
                "• Special high-confidence bets\n\n"
                "Use /settings to customize your preferences."
            )
            logger.info(f"User {user_id} subscribed to notifications")

        except TelegramUser.DoesNotExist:
            await message.answer(
                "❌ You're not registered. Use /start to subscribe to notifications."
            )

    async def unsubscribe_command(self, message: types.Message) -> None:
        """Handle /unsubscribe command"""
        user_id = message.from_user.id

        try:
            user = TelegramUser.get(TelegramUser.telegram_id == user_id)
            user.is_active = False
            user.save()

            await message.answer(
                "🔕 Successfully unsubscribed from notifications.\n\n"
                "You can resubscribe anytime using /subscribe"
            )
            logger.info(f"User {user_id} unsubscribed from notifications")

        except TelegramUser.DoesNotExist:
            await message.answer(
                "❌ You're not registered. Use /start to subscribe to notifications."
            )

    async def handle_callback(self, callback_query: types.CallbackQuery) -> None:
        """Handle inline keyboard callbacks"""
        await callback_query.answer()

        if callback_query.data == "settings":
            await self._show_settings(callback_query.from_user.id, callback_query.message.chat.id)
        elif callback_query.data == "help":
            await self._show_help(callback_query.message.chat.id)
        elif callback_query.data == "subscribe":
            await self._handle_subscribe_callback(callback_query)
        elif callback_query.data == "unsubscribe":
            await self._handle_unsubscribe_callback(callback_query)
        elif callback_query.data.startswith("freq_"):
            await self._handle_frequency_change(callback_query)
        elif callback_query.data == "back_to_settings":
            await self._show_settings(callback_query.from_user.id, callback_query.message.chat.id)

    async def _show_settings(self, user_id: int, chat_id: int) -> None:
        """Show settings menu"""
        try:
            user = TelegramUser.get(TelegramUser.telegram_id == user_id)

            settings_text = (
                f"⚙️ Notification Settings\n\n"
                f"🔔 Frequency: {user.notification_frequency.title()}\n"
                f"✅ Status: {'Active' if user.is_active else 'Inactive'}\n\n"
                f"Choose your notification frequency:"
            )

            keyboard = InlineKeyboardBuilder()
            keyboard.add(InlineKeyboardButton(
                text="📅 Daily (Recommended)", 
                callback_data="freq_daily"
            ))
            keyboard.add(InlineKeyboardButton(
                text="⏰ Hourly", 
                callback_data="freq_hourly"
            ))
            keyboard.add(InlineKeyboardButton(
                text="🔴 Live (Every 3 min)", 
                callback_data="freq_live"
            ))
            keyboard.add(InlineKeyboardButton(
                text="🔕 Unsubscribe", 
                callback_data="unsubscribe"
            ))

            await self.bot.send_message(chat_id, settings_text, reply_markup=keyboard.as_markup())

        except TelegramUser.DoesNotExist:
            await self.bot.send_message(
                chat_id, 
                "❌ You're not registered. Use /start to subscribe to notifications."
            )

    async def _show_help(self, chat_id: int) -> None:
        """Show help message"""
        help_text = (
            "🤖 Football Betting Analysis Bot - Help\n\n"
            "This bot analyzes football matches to find betting opportunities.\n\n"
            "📊 Analysis Types:\n"
            "• Historical analysis (team form, patterns)\n"
            "• Live match analysis (red cards, draws)\n\n"
            "🎯 Betting Rules:\n"
            "• Top teams with poor recent form\n"
            "• Teams with consecutive losses/draws\n"
            "• Live matches with red cards and draws\n"
            "• Teams with no goals in recent matches\n\n"
            "Use /settings to customize your notifications."
        )
        await self.bot.send_message(chat_id, help_text)

    async def _handle_subscribe_callback(self, callback_query: types.CallbackQuery) -> None:
        """Handle subscribe callback"""
        user_id = callback_query.from_user.id

        try:
            user = TelegramUser.get(TelegramUser.telegram_id == user_id)
            user.is_active = True
            user.save()

            await callback_query.message.edit_text(
                "✅ Successfully subscribed to betting notifications!"
            )
            logger.info(f"User {user_id} subscribed via callback")

        except TelegramUser.DoesNotExist:
            await callback_query.message.edit_text(
                "❌ You're not registered. Use /start to subscribe."
            )

    async def _handle_unsubscribe_callback(self, callback_query: types.CallbackQuery) -> None:
        """Handle unsubscribe callback"""
        user_id = callback_query.from_user.id

        try:
            user = TelegramUser.get(TelegramUser.telegram_id == user_id)
            user.is_active = False
            user.save()

            await callback_query.message.edit_text(
                "🔕 Successfully unsubscribed from notifications."
            )
            logger.info(f"User {user_id} unsubscribed via callback")

        except TelegramUser.DoesNotExist:
            await callback_query.message.edit_text(
                "❌ You're not registered. Use /start to subscribe."
            )

    async def _handle_frequency_change(self, callback_query: types.CallbackQuery) -> None:
        """Handle frequency change callback"""
        user_id = callback_query.from_user.id
        frequency = callback_query.data.replace("freq_", "")

        try:
            user = TelegramUser.get(TelegramUser.telegram_id == user_id)
            user.notification_frequency = frequency
            user.save()

            frequency_names = {
                "daily": "Daily",
                "hourly": "Hourly", 
                "live": "Live (Every 3 minutes)"
            }

            await callback_query.message.edit_text(
                f"✅ Notification frequency changed to: {frequency_names.get(frequency, frequency.title())}"
            )
            logger.info(f"User {user_id} changed frequency to {frequency}")

        except TelegramUser.DoesNotExist:
            await callback_query.message.edit_text(
                "❌ You're not registered. Use /start to subscribe."
            )

    async def send_betting_opportunity(self, opportunity: RuleOpportunity) -> None:
        """Send betting opportunity to all subscribed users"""
        try:
            # Get all active users
            users = TelegramUser.select().where(TelegramUser.is_active)

            message_text = self._format_opportunity_message(opportunity)

            for user in users:
                try:
                    await self.bot.send_message(
                        user.telegram_id,
                        message_text,
                        parse_mode="HTML"
                    )

                    # Log the notification
                    NotificationLog.create(
                        user=user,
                        opportunity=None,  # Will be set when we have DB opportunity
                        message=message_text,
                        success=True
                    )

                    # Add delay to avoid rate limiting
                    await asyncio.sleep(0.1)

                except Exception as e:
                    logger.error(f"Failed to send notification to user {user.telegram_id}", error=str(e))

                    # Log the failed notification
                    NotificationLog.create(
                        user=user,
                        opportunity=None,
                        message=message_text,
                        success=False,
                        error_message=str(e)
                    )

            logger.info(f"Sent betting opportunity to {len(users)} users")

        except Exception as e:
            logger.error("Error sending betting opportunities", error=str(e))

    def _format_opportunity_message(self, opportunity: RuleOpportunity) -> str:
        """Format betting opportunity as Telegram message"""
        confidence_emoji = "🟢" if opportunity.confidence >= 0.8 else "🟡" if opportunity.confidence >= 0.6 else "🔴"

        message = (
            f"🎯 <b>Betting Opportunity</b>\n\n"
            f"🏆 <b>{opportunity.rule_name}</b>\n"
            f"⚽ <b>{opportunity.home_team}</b> vs <b>{opportunity.away_team}</b>\n"
            f"🏟️ {opportunity.league} ({opportunity.country})\n"
            f"{confidence_emoji} <b>Confidence: {opportunity.confidence:.1%}</b>\n\n"
            f"💡 <b>Reasoning:</b>\n{opportunity.reasoning}\n\n"
            f"💰 <b>Recommendation:</b>\n{opportunity.recommended_bet}\n\n"
            f"📊 Type: {opportunity.opportunity_type.replace('_', ' ').title()}"
        )

        return message

    async def send_daily_summary(self, opportunities: list[RuleOpportunity]) -> None:
        """Send daily summary of betting opportunities"""
        if not opportunities:
            return

        try:
            users = TelegramUser.select().where(
                (TelegramUser.is_active) & 
                (TelegramUser.notification_frequency == 'daily')
            )

            summary_text = self._format_daily_summary(opportunities)

            for user in users:
                try:
                    await self.bot.send_message(
                        user.telegram_id,
                        summary_text,
                        parse_mode="HTML"
                    )
                    await asyncio.sleep(0.1)

                except Exception as e:
                    logger.error(f"Failed to send daily summary to user {user.telegram_id}", error=str(e))

            logger.info(f"Sent daily summary to {len(users)} users")

        except Exception as e:
            logger.error("Error sending daily summary", error=str(e))

    def _format_daily_summary(self, opportunities: list[RuleOpportunity]) -> str:
        """Format daily summary message"""
        message = (
            f"📊 <b>Daily Betting Opportunities Summary</b>\n\n"
            f"Found {len(opportunities)} opportunities today:\n\n"
        )

        for i, opp in enumerate(opportunities[:10], 1):  # Limit to 10
            confidence_emoji = "🟢" if opp.confidence >= 0.8 else "🟡" if opp.confidence >= 0.6 else "🔴"
            message += (
                f"{i}. {confidence_emoji} <b>{opp.rule_name}</b>\n"
                f"   {opp.home_team} vs {opp.away_team}\n"
                f"   Confidence: {opp.confidence:.1%}\n\n"
            )

        if len(opportunities) > 10:
            message += f"... and {len(opportunities) - 10} more opportunities\n\n"

        message += "Use /settings to adjust your notification preferences."

        return message

    async def start(self) -> None:
        """Start the bot"""
        logger.info("Starting Telegram bot...")
        await self.dp.start_polling(self.bot)

    async def stop(self) -> None:
        """Stop the bot"""
        logger.info("Stopping Telegram bot...")
        await self.bot.session.close()


# Global bot instance
bot_instance: BettingBot | None = None


def get_bot() -> BettingBot:
    """Get or create bot instance"""
    global bot_instance
    if bot_instance is None:
        bot_instance = BettingBot()
    return bot_instance 
