from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Database
    database_url: str = 'sqlite:///./football.db'

    # Redis
    redis_url: str = 'redis://redis:6379/0'

    # Telegram Bot
    telegram_bot_token: str = ''
    telegram_webhook_secret: str = ''
    base_host: str = 'http://localhost:8000'

    # App Configuration
    app_name: str = 'Football Betting Analysis'
    debug: bool = False

    # Task Configuration
    live_check_interval: int = 180  # 3 minutes in seconds
    daily_analysis_hour: int = 9  # Hour to run daily analysis (UTC)

    # Betting Rules Configuration
    rounds_back: int = 5
    top_teams_count: int = 8  # Number of teams considered "top"
    min_consecutive_losses: int = 3
    min_consecutive_draws: int = 3
    min_consecutive_losses_top5: int = 2
    min_no_goals_matches: int = 2
    live_draw_minute_threshold: int = 70

    # Admin Configuration
    admin_secret_key: str = 'your-secret-key-change-in-production'
    admin_session_secret: str = 'your-session-secret-change-in-production'
    admin_token_expire_minutes: int = 30
    admin_username: str = 'superadmin'
    admin_password: str = 'strong_secret_123'  # noqa: S105
    admin_email: str = 'admin@example.com'

    class Config:
        env_file = '.env'
        env_prefix = ''


settings = Settings()
