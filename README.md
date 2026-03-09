# Football Betting Analysis App

Football betting analysis application that uses historical data and live match monitoring to identify betting opportunities. The app combines free API data from livesport.com with live scraping to provide real-time betting insights.

## Features

### Betting Analysis
- **Historical Analysis**: Analyzes team performance patterns and recent form
- **Live Match Monitoring**: Real-time analysis of ongoing matches
- **Automated Notifications**: Telegram bot notifications for betting opportunities
- **Confidence Scoring**: Each opportunity includes a confidence score (0-100%)

### Data Sources
- **Live Scraping**: Real-time match data from livesport.com and other sources
- **League Scraping**: Comprehensive league standings, team statistics, and match data from livesport.com
- **Monitored Leagues**: Top-7 European leagues + Champions League, Europa League, Conference League, Russian Premier League

### Telegram Bot
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

## Acknowledgments

- [Livesport.com](https://www.livesport.com/) for live match data
- [Nginx](https://nginx.org/) for reverse proxy and SSL
- [FastAPI](https://fastapi.tiangolo.com/) for the web framework
