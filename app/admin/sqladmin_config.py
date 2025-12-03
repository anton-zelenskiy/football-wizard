from sqladmin import Admin, ModelView
from sqladmin.filters import (
    AllUniqueStringValuesFilter,
    BooleanFilter,
    ForeignKeyFilter,
)
from sqlalchemy import create_engine
from starlette.requests import Request

from app.admin.models import AdminUser
from app.admin.sqladmin_auth import SQLAdminAuth
from app.db.sqlalchemy_models import (
    BettingOpportunity,
    League,
    Match,
    NotificationLog,
    Team,
    TelegramUser,
)


class LeagueAdmin(ModelView, model=League):
    """Admin view for League model"""

    name = 'League'
    name_plural = 'Leagues'
    icon = 'fa fa-trophy'

    # Display columns
    column_list = [League.id, League.name, League.country, League.created_at]
    column_details_list = [
        League.id,
        League.name,
        League.country,
        League.created_at,
        League.updated_at,
    ]

    # Search and filter capabilities
    column_searchable_list = [League.name, League.country]
    column_sortable_list = [League.id, League.name, League.country, League.created_at]

    # Form configuration
    form_columns = [League.name, League.country]


class TeamAdmin(ModelView, model=Team):
    """Admin view for Team model"""

    name = 'Team'
    name_plural = 'Teams'
    icon = 'fa fa-users'

    # Display columns
    column_list = [Team.id, Team.name, Team.league, Team.coach]
    column_details_list = [
        Team.id,
        Team.name,
        Team.league,
        Team.coach,
        Team.created_at,
        Team.updated_at,
    ]

    # Search and filter capabilities - this is where foreign key filtering works!
    column_searchable_list = [Team.name]
    column_sortable_list = [Team.id, Team.name]
    column_filters = [
        ForeignKeyFilter(Team.league_id, League.name, title='League'),
    ]

    # Form configuration
    form_columns = [Team.name, Team.league, Team.coach]

    def is_accessible(self, request: Request) -> bool:
        """Check if user is authenticated"""
        return bool(request.session.get('user_id'))

    def is_visible(self, request: Request) -> bool:
        """Check if user is authenticated"""
        return bool(request.session.get('user_id'))


class MatchAdmin(ModelView, model=Match):
    """Admin view for Match model"""

    name = 'Match'
    name_plural = 'Matches'
    icon = 'fa fa-futbol'

    # Display columns
    column_list = [
        Match.id,
        Match.league,
        Match.home_team,
        Match.away_team,
        Match.match_date,
        Match.status,
    ]
    column_details_list = [
        Match.id,
        Match.league,
        Match.home_team,
        Match.away_team,
        Match.home_score,
        Match.away_score,
        Match.match_date,
        Match.season,
        Match.round,
        Match.status,
        Match.minute,
        Match.red_cards_home,
        Match.red_cards_away,
        Match.created_at,
        Match.updated_at,
    ]

    # Search and filter capabilities with foreign key filtering
    column_searchable_list = [Match.status]
    column_sortable_list = [Match.id, Match.match_date, Match.status]
    column_filters = [
        ForeignKeyFilter(Match.league_id, League.name, title='League'),
        ForeignKeyFilter(Match.home_team_id, Team.name, title='Home Team'),
        ForeignKeyFilter(Match.away_team_id, Team.name, title='Away Team'),
        AllUniqueStringValuesFilter(Match.status, title='Status'),
        AllUniqueStringValuesFilter(Match.season, title='Season'),
    ]

    # Form configuration
    form_columns = [
        Match.league,
        Match.home_team,
        Match.away_team,
        Match.match_date,
        Match.season,
        Match.round,
        Match.status,
    ]


class BettingOpportunityAdmin(ModelView, model=BettingOpportunity):
    """Admin view for BettingOpportunity model"""

    name = 'Betting Opportunity'
    name_plural = 'Betting Opportunities'
    icon = 'fa fa-chart-line'

    # Display columns
    column_list = [
        BettingOpportunity.id,
        BettingOpportunity.match,
        BettingOpportunity.rule_slug,
        BettingOpportunity.confidence_score,
        BettingOpportunity.outcome,
        BettingOpportunity.created_at,
    ]
    column_details_list = [
        BettingOpportunity.id,
        BettingOpportunity.match,
        BettingOpportunity.rule_slug,
        BettingOpportunity.confidence_score,
        BettingOpportunity.details,
        BettingOpportunity.outcome,
        BettingOpportunity.created_at,
    ]

    # Search and filter capabilities
    column_searchable_list = [BettingOpportunity.rule_slug, BettingOpportunity.outcome]
    column_sortable_list = [
        BettingOpportunity.id,
        BettingOpportunity.confidence_score,
        BettingOpportunity.created_at,
    ]
    column_filters = [
        AllUniqueStringValuesFilter(BettingOpportunity.rule_slug, title='Rule Slug'),
        AllUniqueStringValuesFilter(BettingOpportunity.outcome, title='Outcome'),
    ]

    # Form configuration
    form_columns = [
        BettingOpportunity.match,
        BettingOpportunity.rule_slug,
        BettingOpportunity.confidence_score,
        BettingOpportunity.details,
        BettingOpportunity.outcome,
    ]


class TelegramUserAdmin(ModelView, model=TelegramUser):
    """Admin view for TelegramUser model"""

    name = 'Telegram User'
    name_plural = 'Telegram Users'
    icon = 'fa fa-telegram'

    # Display columns
    column_list = [
        TelegramUser.id,
        TelegramUser.telegram_id,
        TelegramUser.username,
        TelegramUser.first_name,
        TelegramUser.is_active,
    ]
    column_details_list = [
        TelegramUser.id,
        TelegramUser.telegram_id,
        TelegramUser.username,
        TelegramUser.first_name,
        TelegramUser.last_name,
        TelegramUser.is_active,
        TelegramUser.daily_notifications,
        TelegramUser.live_notifications,
        TelegramUser.created_at,
        TelegramUser.updated_at,
    ]

    # Search and filter capabilities
    column_searchable_list = [
        TelegramUser.username,
        TelegramUser.first_name,
        TelegramUser.last_name,
    ]
    column_sortable_list = [
        TelegramUser.id,
        TelegramUser.telegram_id,
        TelegramUser.username,
        TelegramUser.created_at,
    ]
    column_filters = [
        BooleanFilter(TelegramUser.is_active, title='Active'),
        BooleanFilter(TelegramUser.daily_notifications, title='Daily Notifications'),
        BooleanFilter(TelegramUser.live_notifications, title='Live Notifications'),
    ]

    # Form configuration
    form_columns = [
        TelegramUser.telegram_id,
        TelegramUser.username,
        TelegramUser.first_name,
        TelegramUser.last_name,
        TelegramUser.is_active,
        TelegramUser.daily_notifications,
        TelegramUser.live_notifications,
    ]


class NotificationLogAdmin(ModelView, model=NotificationLog):
    """Admin view for NotificationLog model"""

    name = 'Notification Log'
    name_plural = 'Notification Logs'
    icon = 'fa fa-bell'

    # Display columns
    column_list = [
        NotificationLog.id,
        NotificationLog.user,
        NotificationLog.opportunity,
        NotificationLog.sent_at,
        NotificationLog.success,
    ]
    column_details_list = [
        NotificationLog.id,
        NotificationLog.user,
        NotificationLog.opportunity,
        NotificationLog.message,
        NotificationLog.sent_at,
        NotificationLog.success,
        NotificationLog.error_message,
    ]

    # Search and filter capabilities with foreign key filtering
    column_searchable_list = [NotificationLog.message]
    column_sortable_list = [
        NotificationLog.id,
        NotificationLog.sent_at,
        NotificationLog.success,
    ]
    column_filters = [
        ForeignKeyFilter(
            NotificationLog.user_id, TelegramUser.telegram_id, title='User'
        ),
        ForeignKeyFilter(
            NotificationLog.opportunity_id,
            BettingOpportunity.rule_slug,
            title='Opportunity',
        ),
        BooleanFilter(NotificationLog.success, title='Success'),
    ]

    # Form configuration
    form_columns = [
        NotificationLog.user,
        NotificationLog.opportunity,
        NotificationLog.message,
        NotificationLog.success,
        NotificationLog.error_message,
    ]


class AdminUserAdmin(ModelView, model=AdminUser):
    """Admin view for AdminUser model"""

    name = 'Admin User'
    name_plural = 'Admin Users'
    icon = 'fa fa-user-shield'

    # Display columns
    column_list = [
        AdminUser.id,
        AdminUser.username,
        AdminUser.email,
        AdminUser.is_active,
        AdminUser.is_superuser,
    ]
    column_details_list = [
        AdminUser.id,
        AdminUser.username,
        AdminUser.email,
        AdminUser.is_active,
        AdminUser.is_superuser,
        AdminUser.created_at,
        AdminUser.updated_at,
        AdminUser.last_login,
    ]

    # Search and filter capabilities
    column_searchable_list = [AdminUser.username, AdminUser.email]
    column_sortable_list = [
        AdminUser.id,
        AdminUser.username,
        AdminUser.email,
        AdminUser.created_at,
    ]
    column_filters = [
        BooleanFilter(AdminUser.is_active, title='Active'),
        BooleanFilter(AdminUser.is_superuser, title='Superuser'),
    ]

    # Form configuration
    form_columns = [
        AdminUser.username,
        AdminUser.email,
        AdminUser.is_active,
        AdminUser.is_superuser,
    ]

    def is_accessible(self, request: Request) -> bool:
        """Only superusers can access admin user management"""
        return request.session.get('is_superuser', False)

    def is_visible(self, request: Request) -> bool:
        """Only superusers can see admin user management in menu"""
        return request.session.get('is_superuser', False)


def create_admin_app(app):
    """Create and configure SQLAdmin application"""
    # Use the same database URL as the main application
    database_url = 'sqlite:///./football.db'
    engine = create_engine(database_url, echo=False)

    # Ensure tables exist before creating admin
    from app.db.sqlalchemy_models import create_tables

    create_tables()

    # Create authentication backend
    from app.settings import settings

    authentication_backend = SQLAdminAuth(secret_key=settings.admin_session_secret)

    # Create admin instance with authentication
    admin = Admin(
        app=app,
        engine=engine,
        title='Football Wizard',
        authentication_backend=authentication_backend,
    )

    # Add all admin views
    admin.add_view(LeagueAdmin)
    admin.add_view(TeamAdmin)
    admin.add_view(MatchAdmin)
    admin.add_view(BettingOpportunityAdmin)
    admin.add_view(TelegramUserAdmin)
    admin.add_view(NotificationLogAdmin)
    admin.add_view(AdminUserAdmin)

    return admin
