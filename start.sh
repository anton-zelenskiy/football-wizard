#!/bin/bash

# Football Betting Analysis App - Startup Script

set -e

echo "🎯 Football Betting Analysis App - Startup Script"
echo "=================================================="

# Check if .env file exists
if [ ! -f .env ]; then
    echo "❌ .env file not found!"
    echo "Please create a .env file with the following variables:"
    echo ""
    echo "API_FOOTBALL_KEY=your_api_football_key_here"
    echo "TELEGRAM_BOT_TOKEN=your_telegram_bot_token_here"
    echo "APP_NAME=\"Football Betting Analysis\""
    echo "DEBUG=false"
    echo "DATABASE_URL=sqlite:///./football.db"
    echo "REDIS_URL=redis://redis:6379/0"
    echo "DOMAIN=football-betting.yourdomain.com"
    echo ""
    echo "You can get your API keys from:"
    echo "- API-Football: https://www.api-football.com/"
    echo "- Telegram Bot: https://t.me/BotFather"
    echo ""
    exit 1
fi

# Check if SSL certificates exist
if [ ! -f infra-nginx/cert.pem ] || [ ! -f infra-nginx/private.key ]; then
    echo "🔐 SSL certificates not found!"
    echo "Generating self-signed certificates for development..."
    ./generate-ssl-certs.sh
    echo ""
fi

# Check if Docker is running
if ! docker info > /dev/null 2>&1; then
    echo "❌ Docker is not running!"
    echo "Please start Docker and try again."
    exit 1
fi

# Check if Docker Compose is available
if ! command -v docker-compose &> /dev/null; then
    echo "❌ Docker Compose is not installed!"
    echo "Please install Docker Compose and try again."
    exit 1
fi

echo "✅ Environment check passed"
echo ""

# Build and start services
echo "🚀 Starting Football Betting Analysis App..."
echo ""

# Stop any existing containers
echo "🛑 Stopping existing containers..."
docker-compose down

# Build and start services
echo "🔨 Building and starting services..."
docker-compose up -d --build

# Wait for services to be ready
echo "⏳ Waiting for services to be ready..."
sleep 10

# Check if services are running
echo "🔍 Checking service status..."
if docker-compose ps | grep -q "Up"; then
    echo "✅ Services are running!"
else
    echo "❌ Some services failed to start"
    echo "Check logs with: docker-compose logs"
    exit 1
fi

echo ""
echo "🎉 Football Betting Analysis App is now running!"
echo ""
echo "📊 Access points:"
echo "- API Documentation: http://localhost:8000/docs"
echo "- Health Check: http://localhost:8000/health"
echo "- Nginx: http://localhost (port 80) and https://localhost (port 443)"
echo ""
echo "⚽ League Scraping Features:"
echo "- Get all leagues: GET /leagues"
echo "- Get league teams: GET /leagues/{league_name}/teams"
echo "- Get league matches: GET /leagues/{league_name}/matches"
echo "- Get live matches: GET /matches/live"
echo "- Scrape Russian Premier League: POST /scrape/russian-premier-league"
echo "- Scrape all leagues: POST /scrape/all-leagues"
echo "- Get league stats: GET /stats/leagues"
echo ""
echo "🔄 Background Tasks:"
echo "- Live matches refresh: Every 3 minutes"
echo "- League data refresh: Every 6 hours"
echo "- Daily team statistics: Every day at 9 AM UTC"
echo ""
echo "📝 Next steps:"
echo "1. Set up your Telegram bot with /start command"
echo "2. Configure your domain in nginx configuration (infra-nginx/data/conf/app.conf)"
echo "3. Monitor logs: docker-compose logs -f"
echo "4. Start scraping: curl -X POST http://localhost:8000/scrape/russian-premier-league"
echo ""
echo "🔧 Useful commands:"
echo "- View logs: docker-compose logs -f"
echo "- Stop app: docker-compose down"
echo "- Restart app: docker-compose restart"
echo "- Update app: git pull && docker-compose up -d --build"
echo "- Run worker manually: python run_worker.py"
echo ""
echo "📚 For more information, see README.md" 