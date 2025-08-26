# Football Betting Analysis App

A comprehensive football betting analysis application that uses historical data and live match monitoring to identify betting opportunities. The app combines free API data from TheSportsDB with live scraping to provide real-time betting insights.

## Features

### 🎯 Betting Analysis
- **Historical Analysis**: Analyzes team performance patterns and recent form
- **Live Match Monitoring**: Real-time analysis of ongoing matches
- **Automated Notifications**: Telegram bot notifications for betting opportunities
- **Confidence Scoring**: Each opportunity includes a confidence score (0-100%)

### 📊 Data Sources
- **TheSportsDB**: Free historical match data, team statistics, and standings
- **Live Scraping**: Real-time match data from livesport.com and other sources
- **League Scraping**: Comprehensive league standings, team statistics, and match data from livesport.com
- **Monitored Leagues**: Top-7 European leagues + Champions League, Europa League, Conference League, Russian Premier League

### 🤖 Telegram Bot
- User subscription management
- Configurable notification frequencies (daily, hourly, live)
- Interactive settings and help commands
- Real-time betting opportunity alerts

## Betting Rules

### Historical Analysis Rules
1. **Top-10 Team Losing Streak**: Teams in top-10 with 3+ consecutive losses
2. **Top-10 Team Drawing Streak**: Teams in top-10 with 3+ consecutive draws  
3. **Top-5 Team Losing Streak**: Teams in top-5 with 2+ consecutive losses
4. **Top-8 Team No Goals**: Teams in top-8 with no goals in last 2+ matches
5. **Coach Change Detection**: Teams with poor recent form (potential coaching issues)

### Live Match Rules
1. **Red Card + Draw + Second Half**: High probability of goals when a team gets a red card while drawing in second half
2. **Draw Past 70 Minutes**: Potential for late goals in drawn matches past 70 minutes

## Project Structure

```
app/
├── api/
│   ├── thesportsdb_client.py    # TheSportsDB API client
│   ├── live_scraper.py          # Live match scraping
│   ├── league_scraper.py        # League standings and team statistics scraping
│   ├── web.py                   # FastAPI web endpoints
│   └── constants.py             # API constants
├── db/
│   ├── models.py                # Database models
│   └── storage.py               # Database storage operations
├── telegram/
│   └── bot.py                   # Telegram bot implementation
├── tasks/
│   ├── betting_tasks.py         # Background tasks (arq)
│   └── league_tasks.py          # League scraping background tasks
├── betting_rules.py             # Betting rules engine
├── settings.py                  # Application settings
├── main.py                      # FastAPI application
└── worker.py                    # ARQ worker script
```

## Quick Start

### Prerequisites
- Docker and Docker Compose
- Telegram Bot Token (optional, for notifications)

### 1. Environment Setup

Create a `.env` file:

```bash
# Telegram Bot (optional)
TELEGRAM_BOT_TOKEN=your_telegram_bot_token_here

# App Configuration
APP_NAME="Football Betting Analysis"
DEBUG=false

# Database
DATABASE_URL=sqlite:///./football.db

# Redis
REDIS_URL=redis://redis:6379/0

# Domain (for nginx)
DOMAIN=football-betting.yourdomain.com
```

**Note**: TheSportsDB API is completely free and doesn't require an API key!

### 2. Generate SSL Certificates (Optional)

For HTTPS support, generate self-signed certificates:

```bash
# Generate development SSL certificates
./generate-ssl-certs.sh
```

**Note**: For production, use proper SSL certificates from a trusted CA.

### 3. Start the Application

```bash
# Use the startup script (automatically generates SSL certs if needed)
./start.sh

# Or manually
docker-compose up -d
```

### 4. Test League Scraping

```bash
# Test the league scraper functionality
python test_league_scraper.py

# Test Russian Premier League scraping specifically
curl -X POST http://localhost:8000/scrape/russian-premier-league
```

### 5. API Endpoints

The application provides comprehensive API endpoints for league data:

#### League Data
- `GET /leagues` - Get all available leagues
- `GET /leagues/{league_name}/teams` - Get teams for a specific league
- `GET /leagues/{league_name}/matches` - Get matches for a specific league
- `GET /matches/live` - Get all currently live matches
- `GET /stats/leagues` - Get statistics about all leagues

#### Scraping Endpoints
- `POST /scrape/russian-premier-league` - Manually trigger Russian Premier League scraping
- `POST /scrape/all-leagues` - Manually trigger scraping for all monitored leagues

#### Legacy Endpoints
- `GET /api/teams` - Get teams (legacy)
- `GET /api/matches` - Get matches (legacy)
- `GET /api/live-matches` - Get live matches (legacy)

### 6. Background Tasks

The application runs several background tasks using ARQ:

- **Live matches refresh**: Every 3 minutes
- **League data refresh**: Every 6 hours  
- **Daily team statistics**: Every day at 9 AM UTC

To run the background worker manually:

```bash
python run_worker.py
```

### 7. Test TheSportsDB API

```bash
# Test the API functionality
python test_thesportsdb.py
```

### 8. Access the Application

- **API Documentation**: http://localhost:8000/docs
- **Health Check**: http://localhost:8000/health
- **Nginx**: http://localhost (port 80) and https://localhost (port 443)

### 9. Set up Telegram bot (optional)

- Create a bot with @BotFather
- Add your bot token to .env
- Users can start the bot with `/start`

## API Endpoints

### Core Endpoints
- `GET /` - Application status
- `GET /health` - Health check
- `GET /api/stats` - Application statistics

### Data Endpoints
- `GET /api/teams` - Get teams (with optional league filter)
- `GET /api/matches` - Get matches (with optional filters)
- `GET /api/live-matches` - Get current live matches
- `GET /api/betting-opportunities` - Get betting opportunities

### TheSportsDB Endpoints
- `GET /api/thesportsdb/teams/{league_name}` - Get teams from TheSportsDB
- `GET /api/thesportsdb/standings/{league_name}` - Get standings from TheSportsDB
- `GET /api/thesportsdb/team-form/{team_name}` - Get team form from TheSportsDB

### Analysis Endpoints
- `POST /api/analyze-live` - Manually trigger live match analysis
- `POST /api/analyze-historical` - Manually trigger historical analysis

### Admin Endpoints
- `GET /api/telegram-users` - Get Telegram user statistics

## Background Tasks

The application uses `arq` for background task processing:

### Scheduled Tasks
- **Daily Analysis**: Runs at 9 AM UTC daily
- **Data Sync**: Runs every 6 hours
- **Live Match Monitoring**: Runs every 3 minutes
- **Cleanup**: Runs daily at 2 AM UTC

### Manual Task Execution

```bash
# Start arq worker
arq app.tasks.betting_tasks.TaskSettings

# Enqueue tasks manually
arq app.tasks.betting_tasks.TaskSettings --function daily_analysis
```

## Telegram Bot Commands

### User Commands
- `/start` - Start the bot and subscribe to notifications
- `/help` - Show help message
- `/status` - Check subscription status
- `/settings` - Configure notification preferences
- `/subscribe` - Subscribe to notifications
- `/unsubscribe` - Unsubscribe from notifications

### Notification Frequencies
- **Daily**: Daily summary of betting opportunities
- **Hourly**: Hourly updates on new opportunities
- **Live**: Real-time notifications (every 3 minutes)

## Configuration

### Settings (`app/settings.py`)

```python
# Monitored Leagues
monitored_leagues = [
    'Premier League', 'LaLiga', 'Bundesliga', 'Serie A', 
    'Ligue 1', 'Eredivisie', 'Primeira Liga', 'Russian Premier League',
    'Champions League', 'Europa League', 'Conference League'
]

# TheSportsDB League Names
thesportsdb_league_names = {
    'Premier League': 'English Premier League',
    'LaLiga': 'Spanish La Liga',
    'Bundesliga': 'German Bundesliga',
    'Serie A': 'Italian Serie A',
    'Ligue 1': 'French Ligue 1',
    'Eredivisie': 'Dutch Eredivisie',
    'Primeira Liga': 'Portuguese Primeira Liga',
    'Russian Premier League': 'Russian Premier League',
    'Champions League': 'UEFA Champions League',
    'Europa League': 'UEFA Europa League',
    'Conference League': 'UEFA Europa Conference League',
}

# Betting Rules Configuration
top_teams_count = 10
min_consecutive_losses = 3
min_consecutive_draws = 3
min_consecutive_losses_top5 = 2
min_no_goals_matches = 2
live_draw_minute_threshold = 70
```

## TheSportsDB API

### Features
- **Completely Free**: No API key required for basic usage
- **Rate Limits**: 30 requests per minute for free users
- **Data Coverage**: Teams, matches, standings, player information
- **Multiple Sports**: Football, basketball, baseball, and more

### API Endpoints Used
- `searchteams.php` - Search for teams
- `lookup_all_teams.php` - Get all teams in a league
- `lookuptable.php` - Get league standings
- `eventslast.php` - Get recent matches
- `eventsnext.php` - Get upcoming matches
- `lookup_all_players.php` - Get team players

### Rate Limiting
The application respects TheSportsDB's rate limits:
- **Free Tier**: 30 requests per minute
- **Premium Tier**: 100 requests per minute
- Automatic delays between requests to avoid hitting limits

## Database Schema

### Core Tables
- **Team**: Team information and statistics
- **Match**: Historical match data
- **Match**: All matches (scheduled, live, finished) - combines previous Match and LiveMatch models
- **BettingOpportunity**: Identified betting opportunities
- **TelegramUser**: Bot user management
- **NotificationLog**: Notification delivery tracking

## Development

### Running Tests

```bash
# Test TheSportsDB API
python test_thesportsdb.py

# Run all tests
pytest

# Run specific test file
pytest app/api/live_scraper_tests.py

# Run with coverage
pytest --cov=app
```

### Adding New Betting Rules

1. Add rule method to `BettingRulesEngine` class
2. Update `_apply_historical_rules` or `_apply_live_rules` methods
3. Add rule configuration to settings
4. Test with sample data

### Adding New Data Sources

1. Create new scraper class in `app/api/`
2. Implement scraping methods
3. Add to `LiveMatchScraper.scrape_all_sources()` (for live matches)
4. Update error handling and logging

## Monitoring and Logging

### Logs
- Application logs are structured using `structlog`
- Log levels: DEBUG, INFO, WARNING, ERROR
- Logs include correlation IDs for request tracking

### Health Checks
- Database connectivity
- Redis connectivity
- TheSportsDB API status
- Telegram bot status

### Metrics
- Number of active users
- Opportunities found per day
- Notification delivery rates
- API response times

## Deployment

### Production Considerations
- Use PostgreSQL instead of SQLite for production
- Configure proper SSL certificates
- Set up monitoring and alerting
- Implement rate limiting
- Configure backup strategies

### Scaling
- Multiple arq workers for task processing
- Redis clustering for high availability
- Load balancing for API endpoints
- Database read replicas

## Troubleshooting

### Common Issues

1. **TheSportsDB Rate Limits**
   - Check if you're hitting the 30 requests/minute limit
   - Implement proper rate limiting
   - Monitor API usage

2. **Scraping Failures**
   - Check website structure changes
   - Update selectors if needed
   - Monitor for CAPTCHA/blocking

3. **Telegram Bot Issues**
   - Verify bot token
   - Check bot permissions
   - Monitor message delivery

4. **Database Issues**
   - Check database connectivity
   - Verify table creation
   - Monitor disk space

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests
5. Submit a pull request

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Support

For support and questions:
- Create an issue on GitHub
- Check the documentation
- Review the logs for error details

## Acknowledgments

- [TheSportsDB](https://www.thesportsdb.com/) for providing free sports data
- [Livesport.com](https://www.livesport.com/) for live match data
- [Nginx](https://nginx.org/) for reverse proxy and SSL
- [FastAPI](https://fastapi.tiangolo.com/) for the web framework