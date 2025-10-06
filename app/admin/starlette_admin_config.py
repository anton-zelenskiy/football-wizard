"""
Starlette-admin configuration for Football Betting Analysis
"""

from sqlalchemy import create_engine
from starlette_admin.contrib.sqla import Admin, ModelView

from app.admin.models import AdminUser
from app.admin.starlette_admin_auth import StarletteAdminAuthProvider
from app.db.sqlalchemy_models import (
    BettingOpportunity,
    League,
    Match,
    NotificationLog,
    Team,
    TelegramUser,
)


class LeagueAdmin(ModelView):
    """Admin view for League model"""

    def __init__(self):
        super().__init__(League)
        self.name = 'League'
        self.name_plural = 'Leagues'
        self.icon = 'fa fa-trophy'
        self.label = 'Leagues'


class TeamAdmin(ModelView):
    """Admin view for Team model"""

    def __init__(self):
        super().__init__(Team)
        self.name = 'Team'
        self.name_plural = 'Teams'
        self.icon = 'fa fa-users'
        self.label = 'Teams'


class MatchAdmin(ModelView):
    """Admin view for Match model"""

    def __init__(self):
        super().__init__(Match)
        self.name = 'Match'
        self.name_plural = 'Matches'
        self.icon = 'fa fa-futbol'
        self.label = 'Matches'


class BettingOpportunityAdmin(ModelView):
    """Admin view for BettingOpportunity model"""

    def __init__(self):
        super().__init__(BettingOpportunity)
        self.name = 'Betting Opportunity'
        self.name_plural = 'Betting Opportunities'
        self.icon = 'fa fa-chart-line'
        self.label = 'Betting Opportunities'


class TelegramUserAdmin(ModelView):
    """Admin view for TelegramUser model"""

    def __init__(self):
        super().__init__(TelegramUser)
        self.name = 'Telegram User'
        self.name_plural = 'Telegram Users'
        self.icon = 'fa fa-telegram'
        self.label = 'Telegram Users'


class NotificationLogAdmin(ModelView):
    """Admin view for NotificationLog model"""

    def __init__(self):
        super().__init__(NotificationLog)
        self.name = 'Notification Log'
        self.name_plural = 'Notification Logs'
        self.icon = 'fa fa-bell'
        self.label = 'Notification Logs'


class AdminUserAdmin(ModelView):
    """Admin view for AdminUser model"""

    def __init__(self):
        super().__init__(AdminUser)
        self.name = 'Admin User'
        self.name_plural = 'Admin Users'
        self.icon = 'fa fa-user-shield'
        self.label = 'Admin Users'


def create_admin_app():
    """Create and configure starlette-admin application"""
    # Use the same database URL as the main application
    database_url = 'sqlite:///./football.db'
    engine = create_engine(database_url, echo=False)

    # Ensure tables exist before creating admin
    from app.db.sqlalchemy_models import create_tables

    create_tables()

    # Create admin instance
    admin = Admin(
        engine=engine,
        title='Football Wizard',
        base_url='/admin',
        auth_provider=StarletteAdminAuthProvider(),
    )

    # Add all admin views
    admin.add_view(LeagueAdmin())
    admin.add_view(TeamAdmin())
    admin.add_view(MatchAdmin())
    admin.add_view(BettingOpportunityAdmin())
    admin.add_view(TelegramUserAdmin())
    admin.add_view(NotificationLogAdmin())
    admin.add_view(AdminUserAdmin())

    return admin
