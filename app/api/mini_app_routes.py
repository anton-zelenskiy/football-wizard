"""
Telegram Mini App API routes for Football Betting Analysis
"""

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse
import structlog

from app.api.security import (
    TelegramWebAppData,
    check_rate_limit,
    get_client_ip,
    get_telegram_webapp_data_optional,
    validate_request_origin,
)
from app.db.storage import FootballDataStorage


logger = structlog.get_logger()

# Create router
router = APIRouter()

# Initialize storage
storage = FootballDataStorage()


@router.get('/betting-opportunities')
async def get_betting_opportunities(
    request: Request,
    webapp_data: TelegramWebAppData | None = None,
):
    """Get active betting opportunities for Mini App (authenticated or debug)"""
    try:
        # Get webapp data if not provided
        if webapp_data is None:
            webapp_data = get_telegram_webapp_data_optional(request)
        # Check if debug mode is enabled
        from app.settings import settings

        debug_mode = settings.debug

        if debug_mode and webapp_data is None:
            # Debug mode: no authentication required
            logger.info('Debug mode: Skipping authentication for betting opportunities')
            client_ip = get_client_ip(request)
            logger.info(f'Debug API access: ip={client_ip}')
        else:
            # Production mode or authenticated debug mode: full authentication
            if webapp_data is None:
                raise HTTPException(status_code=401, detail='Authentication required')

            validate_request_origin(request)
            check_rate_limit(webapp_data.user_id)

            # Log access
            client_ip = get_client_ip(request)
            logger.info(
                f'Mini App API access: user_id={webapp_data.user_id}, '
                f'ip={client_ip}, username={webapp_data.username}'
            )

        opportunities = storage.get_active_betting_opportunities()

        result = []
        for opp in opportunities:
            match = opp.match
            details = opp.get_details()

            opportunity_data = {
                'id': opp.id,
                'rule_slug': opp.rule_slug,
                'confidence_score': opp.confidence_score,
                'outcome': opp.outcome,
                'created_at': opp.created_at.isoformat(),
                'details': details,
            }

            if match:
                opportunity_data['match'] = {
                    'id': match.id,
                    'home_team': {
                        'id': match.home_team.id,
                        'name': match.home_team.name,
                        'rank': match.home_team.rank,
                    },
                    'away_team': {
                        'id': match.away_team.id,
                        'name': match.away_team.name,
                        'rank': match.away_team.rank,
                    },
                    'league': {
                        'id': match.league.id,
                        'name': match.league.name,
                        'country': match.league.country,
                    },
                    'home_score': match.home_score,
                    'away_score': match.away_score,
                    'match_date': match.match_date.isoformat(),
                    'status': match.status,
                    'minute': match.minute,
                    'red_cards_home': match.red_cards_home,
                    'red_cards_away': match.red_cards_away,
                }
            else:
                opportunity_data['match'] = None

            result.append(opportunity_data)

        return {'success': True, 'data': result, 'count': len(result)}

    except HTTPException as e:
        # Re-raise HTTP exceptions (like 401, 429) to preserve status codes
        logger.error(f'HTTP error in betting opportunities: {e.detail}')
        raise e
    except Exception as e:
        logger.error(f'Error getting betting opportunities: {e}')
        raise HTTPException(status_code=500, detail='Internal server error') from e


@router.get('/', response_class=HTMLResponse)
async def mini_app_index():
    """Serve the Mini App HTML page"""
    html_content = """
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Football Betting Analysis</title>
        <script src="https://telegram.org/js/telegram-web-app.js"></script>
        <style>
            * {
                margin: 0;
                padding: 0;
                box-sizing: border-box;
            }

            body {
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
                background: var(--tg-theme-bg-color, #ffffff);
                color: var(--tg-theme-text-color, #000000);
                line-height: 1.6;
            }

            .container {
                max-width: 100%;
                margin: 0 auto;
                padding: 20px;
            }

            .header {
                text-align: center;
                margin-bottom: 30px;
                padding: 20px 0;
                border-bottom: 2px solid var(--tg-theme-button-color, #2481cc);
            }

            .header h1 {
                color: var(--tg-theme-text-color, #000000);
                font-size: 24px;
                margin-bottom: 10px;
            }

            .header p {
                color: var(--tg-theme-hint-color, #999999);
                font-size: 16px;
            }

            .loading {
                text-align: center;
                padding: 40px;
                color: var(--tg-theme-hint-color, #999999);
            }

            .error {
                background: #ff4444;
                color: white;
                padding: 15px;
                border-radius: 8px;
                margin: 20px 0;
                text-align: center;
            }

            .opportunities-list {
                display: flex;
                flex-direction: column;
                gap: 15px;
            }

            .opportunity-card {
                background: var(--tg-theme-secondary-bg-color, #f8f9fa);
                border-radius: 12px;
                padding: 20px;
                border: 1px solid var(--tg-theme-button-color, #2481cc);
                box-shadow: 0 2px 8px rgba(0,0,0,0.1);
            }

            .opportunity-header {
                display: flex;
                justify-content: space-between;
                align-items: center;
                margin-bottom: 15px;
            }

            .rule-name {
                font-weight: bold;
                font-size: 18px;
                color: var(--tg-theme-text-color, #000000);
            }

            .confidence-badge {
                background: var(--tg-theme-button-color, #2481cc);
                color: white;
                padding: 6px 12px;
                border-radius: 20px;
                font-weight: bold;
                font-size: 14px;
            }

            .match-info {
                margin-bottom: 15px;
            }

            .teams {
                display: flex;
                justify-content: space-between;
                align-items: center;
                font-size: 16px;
                font-weight: bold;
                margin-bottom: 10px;
            }

            .team {
                text-align: center;
                flex: 1;
            }

            .vs {
                margin: 0 15px;
                color: var(--tg-theme-hint-color, #999999);
                font-size: 14px;
            }

            .match-details {
                display: flex;
                justify-content: space-between;
                font-size: 14px;
                color: var(--tg-theme-hint-color, #999999);
            }

            .league {
                font-weight: bold;
            }

            .match-date {
                text-align: right;
            }

            .status {
                display: inline-block;
                padding: 4px 8px;
                border-radius: 12px;
                font-size: 12px;
                font-weight: bold;
                text-transform: uppercase;
            }

            .status.scheduled {
                background: #e3f2fd;
                color: #1976d2;
            }

            .status.live {
                background: #ffebee;
                color: #d32f2f;
            }

            .status.finished {
                background: #e8f5e8;
                color: #2e7d32;
            }

            .no-opportunities {
                text-align: center;
                padding: 40px 20px;
                color: var(--tg-theme-hint-color, #999999);
            }

            .refresh-btn {
                background: var(--tg-theme-button-color, #2481cc);
                color: white;
                border: none;
                padding: 12px 24px;
                border-radius: 8px;
                font-size: 16px;
                cursor: pointer;
                margin: 20px auto;
                display: block;
            }

            .refresh-btn:hover {
                opacity: 0.9;
            }

            .refresh-btn:disabled {
                opacity: 0.5;
                cursor: not-allowed;
            }
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>🎯 Betting Opportunities</h1>
                <p>AI-powered football betting analysis</p>
            </div>

            <div id="loading" class="loading">
                Loading opportunities...
            </div>

            <div id="error" class="error" style="display: none;">
                Failed to load opportunities. Please try again.
            </div>

            <div id="opportunities" class="opportunities-list" style="display: none;">
                <!-- Opportunities will be loaded here -->
            </div>

            <div id="no-opportunities" class="no-opportunities" style="display: none;">
                <h3>No Active Opportunities</h3>
                <p>Check back later for new betting opportunities!</p>
            </div>

            <button id="refresh-btn" class="refresh-btn" onclick="loadOpportunities()">
                Refresh
            </button>
        </div>

        <script>
            // Initialize Telegram WebApp
            const tg = window.Telegram.WebApp;
            tg.ready();
            tg.expand();

            // Set theme colors
            document.documentElement.style.setProperty('--tg-theme-bg-color', tg.themeParams.bg_color || '#ffffff');
            document.documentElement.style.setProperty('--tg-theme-text-color', tg.themeParams.text_color || '#000000');
            document.documentElement.style.setProperty('--tg-theme-button-color', tg.themeParams.button_color || '#2481cc');
            document.documentElement.style.setProperty('--tg-theme-hint-color', tg.themeParams.hint_color || '#999999');
            document.documentElement.style.setProperty('--tg-theme-secondary-bg-color', tg.themeParams.secondary_bg_color || '#f8f9fa');

            async function loadOpportunities() {
                const loading = document.getElementById('loading');
                const error = document.getElementById('error');
                const opportunities = document.getElementById('opportunities');
                const noOpportunities = document.getElementById('no-opportunities');
                const refreshBtn = document.getElementById('refresh-btn');

                loading.style.display = 'block';
                error.style.display = 'none';
                opportunities.style.display = 'none';
                noOpportunities.style.display = 'none';
                refreshBtn.disabled = true;

                try {
                    // Try authenticated endpoint first
                    let response;
                    let data;

                    try {
                        // Get Telegram WebApp init data for authentication
                        const initData = tg.initData;
                        if (!initData) {
                            throw new Error('Telegram WebApp not initialized');
                        }

                        response = await fetch('/football/api/v1/mini-app/betting-opportunities', {
                            headers: {
                                'Authorization': `Bearer ${initData}`,
                                'Content-Type': 'application/json'
                            }
                        });

                        if (!response.ok) {
                            if (response.status === 401) {
                                throw new Error('Authentication failed. Check if debug mode is enabled.');
                            } else if (response.status === 429) {
                                throw new Error('Rate limit exceeded. Please try again later.');
                            } else {
                                throw new Error(`Server error: ${response.status}`);
                            }
                        }

                        data = await response.json();

                    } catch (authError) {
                        console.log('Authentication failed:', authError.message);
                        throw new Error('Failed to load opportunities. Please check your connection and try again.');
                    }

                    loading.style.display = 'none';

                    if (data.success && data.data.length > 0) {
                        displayOpportunities(data.data);
                        opportunities.style.display = 'block';
                    } else {
                        noOpportunities.style.display = 'block';
                    }
                } catch (err) {
                    console.error('Error loading opportunities:', err);
                    loading.style.display = 'none';
                    error.style.display = 'block';
                } finally {
                    refreshBtn.disabled = false;
                }
            }

            function displayOpportunities(opportunities) {
                const container = document.getElementById('opportunities');
                container.innerHTML = '';

                opportunities.forEach(opp => {
                    const card = createOpportunityCard(opp);
                    container.appendChild(card);
                });
            }

            function createOpportunityCard(opportunity) {
                const card = document.createElement('div');
                card.className = 'opportunity-card';

                const match = opportunity.match;
                const details = opportunity.details || {};

                let matchInfo = '';
                let statusClass = 'scheduled';
                let statusText = 'Scheduled';

                if (match) {
                    const homeTeam = match.home_team.name;
                    const awayTeam = match.away_team.name;
                    const league = match.league.name;
                    const matchDate = new Date(match.match_date).toLocaleString();

                    if (match.status === 'live') {
                        statusClass = 'live';
                        statusText = `Live ${match.minute || 0}'`;
                    } else if (match.status === 'finished') {
                        statusClass = 'finished';
                        statusText = 'Finished';
                    }

                    matchInfo = `
                        <div class="match-info">
                            <div class="teams">
                                <div class="team">${homeTeam}</div>
                                <div class="vs">vs</div>
                                <div class="team">${awayTeam}</div>
                            </div>
                            <div class="match-details">
                                <span class="league">${league}</span>
                                <span class="match-date">${matchDate}</span>
                            </div>
                        </div>
                    `;
                }

                const confidencePercent = Math.round(opportunity.confidence_score * 100);

                card.innerHTML = `
                    <div class="opportunity-header">
                        <div class="rule-name">${opportunity.rule_slug}</div>
                        <div class="confidence-badge">${confidencePercent}%</div>
                    </div>
                    ${matchInfo}
                    <div class="status ${statusClass}">${statusText}</div>
                `;

                return card;
            }

            // Load opportunities on page load
            document.addEventListener('DOMContentLoaded', loadOpportunities);
        </script>
    </body>
    </html>
    """
    return HTMLResponse(content=html_content)
