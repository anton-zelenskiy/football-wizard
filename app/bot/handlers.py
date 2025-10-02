from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
    WebAppInfo,
)
import structlog

from app.bot.notifications import (
    format_completed_opportunities_message,
    format_opportunities_message,
)
from app.db.storage import FootballDataStorage
from app.settings import settings


logger = structlog.get_logger()

router = Router()


@router.message(Command('start'))
async def start_command(message: Message) -> None:
    """Handle /start command"""
    user_id = message.from_user.id
    username = message.from_user.username
    first_name = message.from_user.first_name
    last_name = message.from_user.last_name

    # Get or create user using storage
    storage = FootballDataStorage()
    user, created = storage.get_or_create_telegram_user(
        telegram_id=user_id,
        username=username,
        first_name=first_name,
        last_name=last_name,
    )

    welcome_text = (
        f'🎯 Welcome to Football Betting Analysis Bot!\n\n'
        f"Hi {first_name or 'there'}! I'll help you find betting opportunities "
        f'based on team statistics and live match analysis.\n\n'
        f'📊 I monitor:\n'
        f'• Top-7 European leagues\n'
        f'• Champions League, Europa League, Conference League\n'
        f'• Russian Premier League\n\n'
        f'🔍 I look for:\n'
        f'• Teams with poor recent form\n'
        f'• Live match opportunities (red cards, draws)\n'
        f'• Historical patterns and trends\n\n'
        f'Use /help to see all available commands.'
    )

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text='🎯 Betting Opportunities',
                    web_app=WebAppInfo(
                        url=f'{settings.base_host}/football/api/v1/mini-app/'
                    ),
                )
            ],
            [InlineKeyboardButton(text='📊 View Settings', callback_data='settings')],
            [InlineKeyboardButton(text='❓ Help', callback_data='help')],
        ]
    )

    await message.answer(welcome_text, reply_markup=keyboard)
    logger.info(f'User {user_id} started the bot')


@router.message(Command('bettings'))
async def bettings_command(message: Message) -> None:
    """Handle /bettings command - open Mini App"""
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text='🎯 Open Betting Opportunities',
                    web_app=WebAppInfo(
                        url=f'{settings.base_host}/football/api/v1/mini-app/'
                    ),
                )
            ]
        ]
    )

    await message.answer(
        '🎯 <b>Betting Opportunities</b>\n\n'
        'Click the button below to open the interactive betting opportunities interface!',
        reply_markup=keyboard,
        parse_mode='HTML',
    )
    logger.info(f'User {message.from_user.id} requested betting opportunities Mini App')


@router.message(Command('help'))
async def help_command(message: Message) -> None:
    """Handle /help command"""
    help_text = (
        '🤖 Football Betting Analysis Bot - Commands\n\n'
        '📊 Main Commands:\n'
        '/start - Start the bot and subscribe to notifications\n'
        '/help - Show this help message\n'
        '/status - Check your subscription status\n'
        '/settings - Configure notification preferences\n'
        '/opportunities - Show all available betting opportunities\n'
        '/completed - Show completed betting opportunities with statistics\n'
        '/bettings - Open interactive betting opportunities web app\n\n'
        '🔔 Notification Commands:\n'
        '/subscribe - Subscribe to all notifications\n'
        '/unsubscribe - Unsubscribe from all notifications\n'
        '/daily_on - Enable daily betting opportunities\n'
        '/daily_off - Disable daily betting opportunities\n'
        '/live_on - Enable live match notifications\n'
        '/live_off - Disable live match notifications\n\n'
        '📱 You can also use the inline buttons for quick access.\n\n'
        '💡 The bot will automatically notify you about:\n'
        '• Daily betting opportunities (if enabled)\n'
        '• Live match opportunities (if enabled)\n'
        '• Special alerts for high-confidence bets'
    )

    await message.answer(help_text)


@router.message(Command('status'))
async def status_command(message: Message) -> None:
    """Handle /status command"""
    user_id = message.from_user.id

    try:
        storage = FootballDataStorage()
        user = storage.get_telegram_user(user_id)

        status_text = (
            f'📊 Your Subscription Status\n\n'
            f'✅ Status: {"Active" if user.is_active else "Inactive"}\n'
            f'📅 Daily Notifications: '
            f'{"✅ Enabled" if user.daily_notifications else "❌ Disabled"}\n'
            f'🔴 Live Notifications: '
            f'{"✅ Enabled" if user.live_notifications else "❌ Disabled"}\n'
            f'📅 Joined: {user.created_at.strftime("%Y-%m-%d %H:%M")}\n'
            f'🔄 Last Updated: {user.updated_at.strftime("%Y-%m-%d %H:%M")}\n\n'
        )

        if user.is_active:
            status_text += (
                "🎯 You'll receive betting opportunities based on your settings."
            )
        else:
            status_text += (
                "❌ You're not receiving notifications. Use /subscribe to start."
            )

        keyboard_buttons = []
        if user.is_active:
            keyboard_buttons.append(
                [InlineKeyboardButton(text='⚙️ Settings', callback_data='settings')]
            )
            keyboard_buttons.append(
                [
                    InlineKeyboardButton(
                        text='🔕 Unsubscribe', callback_data='unsubscribe'
                    )
                ]
            )
        else:
            keyboard_buttons.append(
                [InlineKeyboardButton(text='✅ Subscribe', callback_data='subscribe')]
            )

        keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)
        await message.answer(status_text, reply_markup=keyboard)

    except Exception:
        await message.answer(
            "❌ You're not registered. Use /start to subscribe to notifications."
        )


@router.message(Command('settings'))
async def settings_command(message: Message) -> None:
    """Handle /settings command"""
    await _show_settings(message.from_user.id, message.chat.id)


@router.message(Command('subscribe'))
async def subscribe_command(message: Message) -> None:
    """Handle /subscribe command - enable all notifications"""
    user_id = message.from_user.id

    try:
        storage = FootballDataStorage()
        storage.subscribe_telegram_user(user_id)

        await message.answer(
            '✅ Successfully subscribed to all notifications!\n\n'
            "You'll now receive:\n"
            '• Daily betting opportunities\n'
            '• Live match alerts\n'
            '• Special high-confidence bets\n\n'
            'Use /settings to customize your preferences.'
        )
        logger.info(f'User {user_id} subscribed to all notifications')

    except Exception:
        await message.answer(
            "❌ You're not registered. Use /start to subscribe to notifications."
        )


@router.message(Command('unsubscribe'))
async def unsubscribe_command(message: Message) -> None:
    """Handle /unsubscribe command - disable all notifications"""
    user_id = message.from_user.id

    try:
        storage = FootballDataStorage()
        storage.unsubscribe_telegram_user(user_id)

        await message.answer(
            '🔕 Successfully unsubscribed from all notifications.\n\n'
            'You can resubscribe anytime using /subscribe'
        )
        logger.info(f'User {user_id} unsubscribed from all notifications')

    except Exception:
        await message.answer(
            "❌ You're not registered. Use /start to subscribe to notifications."
        )


@router.message(Command('daily_on'))
async def daily_on_command(message: Message) -> None:
    """Handle /daily_on command - enable daily notifications"""
    user_id = message.from_user.id

    try:
        storage = FootballDataStorage()
        storage.update_telegram_user_notifications(
            telegram_id=user_id, daily_notifications=True
        )

        await message.answer(
            '✅ Daily notifications enabled!\n\n'
            "You'll receive daily summaries of betting opportunities."
        )
        logger.info(f'User {user_id} enabled daily notifications')

    except Exception:
        await message.answer(
            "❌ You're not registered. Use /start to subscribe to notifications."
        )


@router.message(Command('daily_off'))
async def daily_off_command(message: Message) -> None:
    """Handle /daily_off command - disable daily notifications"""
    user_id = message.from_user.id

    try:
        storage = FootballDataStorage()
        storage.update_telegram_user_notifications(
            telegram_id=user_id, daily_notifications=False
        )

        await message.answer(
            '🔕 Daily notifications disabled.\n\n'
            "You won't receive daily summaries anymore."
        )
        logger.info(f'User {user_id} disabled daily notifications')

    except Exception:
        await message.answer(
            "❌ You're not registered. Use /start to subscribe to notifications."
        )


@router.message(Command('live_on'))
async def live_on_command(message: Message) -> None:
    """Handle /live_on command - enable live notifications"""
    user_id = message.from_user.id

    try:
        storage = FootballDataStorage()
        storage.update_telegram_user_notifications(
            telegram_id=user_id, live_notifications=True
        )

        await message.answer(
            '✅ Live notifications enabled!\n\n'
            "You'll receive immediate alerts for live match opportunities."
        )
        logger.info(f'User {user_id} enabled live notifications')

    except Exception:
        await message.answer(
            "❌ You're not registered. Use /start to subscribe to notifications."
        )


@router.message(Command('live_off'))
async def live_off_command(message: Message) -> None:
    """Handle /live_off command - disable live notifications"""
    user_id = message.from_user.id

    try:
        storage = FootballDataStorage()
        storage.update_telegram_user_notifications(
            telegram_id=user_id, live_notifications=False
        )

        await message.answer(
            '🔕 Live notifications disabled.\n\n'
            "You won't receive live match alerts anymore."
        )
        logger.info(f'User {user_id} disabled live notifications')

    except Exception:
        await message.answer(
            "❌ You're not registered. Use /start to subscribe to notifications."
        )


@router.message(Command('opportunities'))
async def opportunities_command(message: Message) -> None:
    """Handle /opportunities command - show all available betting opportunities"""
    user_id = message.from_user.id

    try:
        # Check if user is registered
        storage = FootballDataStorage()
        storage.get_telegram_user(user_id)

        # Get all active betting opportunities
        opportunities = storage.get_active_betting_opportunities()

        # Format and send the message
        opportunities_text = format_opportunities_message(opportunities)
        await message.answer(opportunities_text, parse_mode='HTML')

        logger.info(
            f'User {user_id} requested betting opportunities, '
            f'found {len(opportunities)} opportunities'
        )

    except Exception as e:
        if 'not registered' in str(e).lower():
            await message.answer(
                "❌ You're not registered. Use /start to subscribe to notifications."
            )
        else:
            logger.error(f'Error getting opportunities for user {user_id}: {e}')
            await message.answer(
                '❌ Error retrieving betting opportunities. Please try again later.'
            )


@router.message(Command('completed'))
async def completed_command(message: Message) -> None:
    """Handle /completed command - show completed betting opportunities with statistics"""
    user_id = message.from_user.id

    try:
        # Check if user is registered
        storage = FootballDataStorage()
        storage.get_telegram_user(user_id)

        # Get completed betting opportunities and statistics
        opportunities = storage.get_completed_betting_opportunities(limit=20)
        statistics = storage.get_betting_statistics()

        # Format and send the message
        completed_text = format_completed_opportunities_message(
            opportunities, statistics
        )
        await message.answer(completed_text, parse_mode='HTML')

        logger.info(
            f'User {user_id} requested completed betting opportunities, '
            f'found {len(opportunities)} opportunities, '
            f'statistics: {statistics["wins"]}W/{statistics["losses"]}L ({statistics["win_rate"]}%)'
        )

    except Exception as e:
        if 'not registered' in str(e).lower():
            await message.answer(
                "❌ You're not registered. Use /start to subscribe to notifications."
            )
        else:
            logger.error(
                f'Error getting completed opportunities for user {user_id}: {e}'
            )
            await message.answer(
                '❌ Error retrieving completed betting opportunities. Please try again later.'
            )


@router.callback_query(F.data == 'settings')
async def handle_settings_callback(callback: CallbackQuery) -> None:
    """Handle settings callback"""
    await callback.answer()
    await _show_settings(callback.from_user.id, callback.message.chat.id)


@router.callback_query(F.data == 'help')
async def handle_help_callback(callback: CallbackQuery) -> None:
    """Handle help callback"""
    await callback.answer()
    await _show_help(callback.message.chat.id)


@router.callback_query(F.data == 'subscribe')
async def handle_subscribe_callback(callback: CallbackQuery) -> None:
    """Handle subscribe callback - enable all notifications"""
    await callback.answer()
    user_id = callback.from_user.id

    try:
        storage = FootballDataStorage()
        storage.subscribe_telegram_user(user_id)

        await callback.message.edit_text(
            '✅ Successfully subscribed to all notifications!'
        )
        logger.info(f'User {user_id} subscribed to all notifications via callback')

    except Exception:
        await callback.message.edit_text(
            "❌ You're not registered. Use /start to subscribe."
        )


@router.callback_query(F.data == 'unsubscribe')
async def handle_unsubscribe_callback(callback: CallbackQuery) -> None:
    """Handle unsubscribe callback - disable all notifications"""
    await callback.answer()
    user_id = callback.from_user.id

    try:
        storage = FootballDataStorage()
        storage.unsubscribe_telegram_user(user_id)

        await callback.message.edit_text(
            '🔕 Successfully unsubscribed from all notifications.'
        )
        logger.info(f'User {user_id} unsubscribed from all notifications via callback')

    except Exception:
        await callback.message.edit_text(
            "❌ You're not registered. Use /start to subscribe."
        )


@router.callback_query(F.data.startswith('toggle_daily'))
async def handle_toggle_daily(callback: CallbackQuery) -> None:
    """Handle toggle daily notifications callback"""
    await callback.answer()
    user_id = callback.from_user.id

    try:
        storage = FootballDataStorage()
        user = storage.toggle_telegram_user_daily_notifications(user_id)

        status = 'enabled' if user.daily_notifications else 'disabled'
        await callback.message.edit_text(f'✅ Daily notifications {status}!')
        logger.info(
            f'User {user_id} toggled daily notifications: {user.daily_notifications}'
        )

    except Exception:
        await callback.message.edit_text(
            "❌ You're not registered. Use /start to subscribe."
        )


@router.callback_query(F.data.startswith('toggle_live'))
async def handle_toggle_live(callback: CallbackQuery) -> None:
    """Handle toggle live notifications callback"""
    await callback.answer()
    user_id = callback.from_user.id

    try:
        storage = FootballDataStorage()
        user = storage.toggle_telegram_user_live_notifications(user_id)

        status = 'enabled' if user.live_notifications else 'disabled'
        await callback.message.edit_text(f'✅ Live notifications {status}!')
        logger.info(
            f'User {user_id} toggled live notifications: {user.live_notifications}'
        )

    except Exception:
        await callback.message.edit_text(
            "❌ You're not registered. Use /start to subscribe."
        )


async def _show_settings(user_id: int, chat_id: int) -> None:
    """Show settings menu"""
    try:
        storage = FootballDataStorage()
        user = storage.get_telegram_user(user_id)

        settings_text = (
            f'⚙️ Notification Settings\n\n'
            f'📅 Daily Notifications: '
            f'{"✅ Enabled" if user.daily_notifications else "❌ Disabled"}\n'
            f'🔴 Live Notifications: '
            f'{"✅ Enabled" if user.live_notifications else "❌ Disabled"}\n'
            f'✅ Status: {"Active" if user.is_active else "Inactive"}\n\n'
            f'Choose your notification preferences:'
        )

        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text=f'📅 Daily: {"ON" if user.daily_notifications else "OFF"}',
                        callback_data='toggle_daily',
                    )
                ],
                [
                    InlineKeyboardButton(
                        text=f'🔴 Live: {"ON" if user.live_notifications else "OFF"}',
                        callback_data='toggle_live',
                    )
                ],
                [
                    InlineKeyboardButton(
                        text='✅ Subscribe All', callback_data='subscribe'
                    )
                ],
                [
                    InlineKeyboardButton(
                        text='🔕 Unsubscribe All', callback_data='unsubscribe'
                    )
                ],
            ]
        )

        from app.bot.core import bot

        await bot.send_message(chat_id, settings_text, reply_markup=keyboard)

    except Exception:
        from app.bot.core import bot

        await bot.send_message(
            chat_id,
            "❌ You're not registered. Use /start to subscribe to notifications.",
        )


async def _show_help(chat_id: int) -> None:
    """Show help message"""
    help_text = (
        '🤖 Football Betting Analysis Bot - Help\n\n'
        'This bot analyzes football matches to find betting opportunities.\n\n'
        '📊 Analysis Types:\n'
        '• Historical analysis (team form, patterns)\n'
        '• Live match analysis (red cards, draws)\n\n'
        '🎯 Betting Rules:\n'
        '• Top teams with poor recent form\n'
        '• Teams with consecutive losses/draws\n'
        '• Live matches with red cards and draws\n'
        '• Teams with no goals in recent matches\n\n'
        'Use /settings to customize your notifications.'
    )
    from app.bot.core import bot

    await bot.send_message(chat_id, help_text)
