from datetime import datetime
import re
from typing import Any

from playwright.async_api import (
    Browser,
    ElementHandle,
    Page,
    Playwright,
    TimeoutError,
    async_playwright,
)
from pydantic import BaseModel, Field
import structlog

from .constants import DEFAULT_SEASON, LEAGUES_OF_INTEREST


logger = structlog.get_logger()


class CommonMatchData(BaseModel):
    """Common match data structure for all match types"""

    home_team: str
    away_team: str
    league: str
    country: str
    home_score: int | None = None
    away_score: int | None = None
    status: str = Field(default='scheduled', pattern='^(live|finished|scheduled)$')
    round_number: int | None = None
    match_date: datetime | None = None
    minute: int | None = None
    red_cards_home: int = 0
    red_cards_away: int = 0
    season: int = DEFAULT_SEASON


class LivesportScraper:
    """Unified scraper for livesport.com with common functionality for live matches and league data"""

    DEFAULT_SEASON = DEFAULT_SEASON

    def __init__(self, scrape_coaches: bool = False) -> None:
        self.monitored_leagues = LEAGUES_OF_INTEREST
        self.browser_args = [
            '--no-sandbox',
            '--disable-setuid-sandbox',
            '--disable-dev-shm-usage',
            '--disable-accelerated-2d-canvas',
            '--no-first-run',
            '--no-zygote',
            '--disable-gpu',
        ]
        self.headers = {
            'User-Agent': (
                'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
                '(KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
            ),
            'Accept-Language': 'en-US,en;q=0.9',
            'Accept': (
                'text/html,application/xhtml+xml,application/xml;q=0.9,'
                'image/webp,*/*;q=0.8'
            ),
        }
        self._playwright: Playwright | None = None
        self._browser: Browser | None = None
        self._cookie_banner_closed: bool = False

        self._scrape_coaches = scrape_coaches

    async def __aenter__(self) -> 'LivesportScraper':
        """Async context manager entry"""
        logger.info('Starting LivesportScraper context manager')
        self._playwright = await async_playwright().start()
        self._browser = await self._playwright.chromium.launch(
            headless=True,
            args=self.browser_args,
        )
        return self

    async def __aexit__(
        self, exc_type: type | None, exc_val: Exception | None, exc_tb: Any
    ) -> None:
        """Async context manager exit - cleanup resources"""
        logger.info('Cleaning up LivesportScraper resources')
        try:
            if self._browser:
                await self._browser.close()
                self._browser = None
        except Exception as e:
            logger.error(f'Error closing browser: {e}')

        try:
            if self._playwright:
                await self._playwright.stop()
                self._playwright = None
        except Exception as e:
            logger.error(f'Error stopping playwright: {e}')

        logger.info('LivesportScraper resources cleaned up')

    async def _setup_browser(self) -> Browser:
        """Setup and return a browser instance with common configuration"""
        if self._browser is None:
            raise RuntimeError(
                'Browser not initialized. Use LivesportScraper as context manager.'
            )
        return self._browser

    async def _setup_page(self, browser: Browser) -> Page:
        """Setup and return a page instance with common configuration"""
        page = await browser.new_page()
        await page.set_extra_http_headers(self.headers)
        return page

    async def _handle_cookie_banner(self, page: Page) -> None:
        """Handle cookie banner if present"""
        if self._cookie_banner_closed:
            return

        try:
            await page.wait_for_selector('button:has-text("I Accept")', timeout=3000)
            cookie_button = await page.query_selector('button:has-text("I Accept")')
            if cookie_button:
                await cookie_button.click()
                self._cookie_banner_closed = True
                logger.info('Closed cookie banner')
        except Exception as e:
            logger.info(f'No cookie banner to close: {e}')

    async def _navigate_and_wait(
        self, page: Page, url: str, selector: str, timeout: int = 10000
    ) -> bool:
        """Navigate to URL and wait for specific selector to load"""
        try:
            logger.info(f'Navigating to {url}')
            await page.goto(url, wait_until='domcontentloaded', timeout=timeout)
            logger.info('Page loaded successfully')

            await self._handle_cookie_banner(page)

            if selector:
                await page.wait_for_selector(selector, timeout=10000)
                logger.info(f'Found expected content: {selector}')

            return True
        except TimeoutError as e:
            logger.error(f'Timeout error while navigating to {url}: {e}')
            return False
        except Exception as e:
            logger.error(f'Unexpected error while navigating to {url}: {e}')
            return False

    async def scrape_live_matches(self) -> list[CommonMatchData]:
        """Scrape live matches from livesport.com using iterative approach"""
        url = 'https://www.livesport.com/soccer/'

        browser = await self._setup_browser()

        try:
            page = await self._setup_page(browser)

            if not await self._navigate_and_wait(page, url, '.event__match', 60000):
                return []

            # Parse season from the page
            season = await self._parse_season_from_page(page)
            logger.info(f'Using season: {season}')

            # Click LIVE tab
            try:
                await page.wait_for_selector('text=LIVE', timeout=30000)
                live_tab = page.get_by_text('LIVE', exact=True)
            except TimeoutError:
                logger.warning('LIVE tab not found, trying alternative selectors')
                live_tab = await page.query_selector(
                    'div.filters__text.filters__text--short:text("LIVE")'
                )
                if not live_tab:
                    logger.error('Could not find LIVE tab with any selector')
                    return []

            if live_tab:
                await live_tab.click()
                logger.info('Clicked LIVE tab')
                await page.wait_for_timeout(5000)
            else:
                logger.warning('LIVE tab not found')

            # Wait for live matches to appear
            try:
                await page.wait_for_selector('.event__match--live', timeout=2000)
            except TimeoutError:
                logger.warning('No live matches found or selector changed')
                return []

            # Get the main container that holds all leagues and matches
            main_container = await page.query_selector('.sportName.soccer')
            if not main_container:
                logger.error('Main container not found')
                return []

            # Get all direct children of the main container
            all_elements = await main_container.query_selector_all(':scope > *')
            logger.info(f'Found {len(all_elements)} elements in main container')

            results = []
            current_league = None
            current_country = None

            # Process elements iteratively
            for i, element in enumerate(all_elements):
                try:
                    class_name = await element.get_attribute('class')
                    if not class_name:
                        continue

                    # Check if this is a league header
                    if 'headerLeague' in class_name:
                        # Extract league information
                        country_el = await element.query_selector(
                            '.headerLeague__category-text'
                        )
                        league_el = await element.query_selector(
                            '.headerLeague__title-text'
                        )

                        if country_el and league_el:
                            country = await country_el.inner_text()
                            league = await league_el.inner_text()

                            # Check if this is a monitored league
                            if self._is_monitored_league(league, country):
                                current_league = league
                                current_country = country
                                logger.debug(
                                    f'Found monitored league: {country} - {league}'
                                )
                            else:
                                current_league = None
                                current_country = None
                                logger.debug(
                                    f'Skipping non-monitored league: {country} - {league}'
                                )

                    # Check if this is a live match
                    elif 'event__match--live' in class_name:
                        # Only process matches if we have a current monitored league
                        if not current_league:
                            logger.debug('Skipping match: no monitored league context')
                            continue

                        # Extract match data
                        home_el = await element.query_selector(
                            '.event__homeParticipant span[data-testid="wcl-scores-simple-text-01"]'
                        )
                        away_el = await element.query_selector(
                            '.event__awayParticipant span[data-testid="wcl-scores-simple-text-01"]'
                        )

                        home = await home_el.inner_text() if home_el else ''
                        away = await away_el.inner_text() if away_el else ''

                        if not home or not away:
                            logger.debug('Skipping match: missing team names')
                            continue

                        # Extract scores
                        score_home_el = await element.query_selector(
                            'span[data-testid="wcl-matchRowScore"][data-side="1"]'
                        )
                        score_away_el = await element.query_selector(
                            'span[data-testid="wcl-matchRowScore"][data-side="2"]'
                        )
                        score_home = (
                            await score_home_el.inner_text() if score_home_el else ''
                        )
                        score_away = (
                            await score_away_el.inner_text() if score_away_el else ''
                        )

                        # Extract minute
                        minute_el = await element.query_selector('.event__stage')
                        minute_text = await minute_el.inner_text() if minute_el else ''
                        minute = self._extract_minute(minute_text)

                        # Extract red cards from SVG elements with data-testid="wcl-icon-incidents-red-card"
                        red_card_home = await element.query_selector(
                            '.event__homeParticipant svg[data-testid="wcl-icon-incidents-red-card"]'
                        )
                        red_card_away = await element.query_selector(
                            '.event__awayParticipant svg[data-testid="wcl-icon-incidents-red-card"]'
                        )
                        red_cards_home = 1 if red_card_home else 0
                        red_cards_away = 1 if red_card_away else 0

                        # Convert scores to integers
                        home_score = int(score_home) if score_home.isdigit() else 0
                        away_score = int(score_away) if score_away.isdigit() else 0

                        # Create common match format
                        match_data = self._create_common_match_data(
                            home_team=home,
                            away_team=away,
                            league=current_league,
                            country=current_country.title(),  # Normalize country name
                            home_score=home_score,
                            away_score=away_score,
                            status='live',
                            match_date=datetime.now(),  # Set current time for live matches
                            minute=minute,
                            red_cards_home=red_cards_home,
                            red_cards_away=red_cards_away,
                            season=season,
                        )

                        results.append(match_data)
                        logger.info(
                            f'Scraped match: {home} vs {away} ({current_country}: {current_league})'
                        )

                except Exception as e:
                    logger.error(f'Error processing element {i}', error=str(e))
                    continue

            logger.info(f'Scraped {len(results)} live matches')
            return results

        except Exception as e:
            logger.error(f'Unexpected error while scraping live matches: {e}')
            return []

    async def scrape_league_standings(
        self, country: str, league_name: str, season: int | None = None
    ) -> list[dict[str, Any]]:
        """Scrape league standings from livesport.com

        Args:
            country: Country name (e.g., 'England')
            league_name: League name (e.g., 'Premier League')
            season: Optional season year (e.g., 2024). If None, parses season from page.
                    If provided, constructs URL for archived season (e.g., -2024-2025)
        """
        # Track if we're scraping an archived season (season parameter was provided)
        is_archived_season = season is not None

        # Construct URL for the specific league
        country_lower = country.lower().replace(' ', '-')
        league_lower = league_name.lower().replace(' ', '-')

        # Add season suffix for archived seasons (e.g., premier-league-2024-2025)
        if season is not None:
            season_suffix = f'-{season}-{season + 1}'
            url = f'https://www.livesport.com/soccer/{country_lower}/{league_lower}{season_suffix}/standings/'
        else:
            url = f'https://www.livesport.com/soccer/{country_lower}/{league_lower}/standings/'

        logger.info(f'Scraping league standings from: {url} (season: {season})')

        browser = await self._setup_browser()

        try:
            page = await self._setup_page(browser)

            if not await self._navigate_and_wait(page, url, '.ui-table__body', 60000):
                return []

            # Parse season from page if not provided
            if season is None:
                parsed_season = await self._parse_season_from_page(page)
                logger.info(f'Parsed season from page: {parsed_season}')
            else:
                parsed_season = season

            # Use optimized selectors to get table rows directly
            table_rows = await page.query_selector_all('.ui-table__row')
            logger.info(f'Found {len(table_rows)} table rows')
            standings_data = []
            team_urls = []  # Store team URLs for coach scraping

            # First pass: extract all team data and URLs
            for row in table_rows:
                try:
                    # Extract team name from the participant cell
                    team_element = await row.query_selector('.table__cell--participant')
                    if not team_element:
                        continue

                    # Find the team link element with class "tableCellParticipant__name"
                    team_link = await team_element.query_selector(
                        'a.tableCellParticipant__name'
                    )

                    team_name = await team_element.inner_text()
                    team_name = team_name.strip()

                    if not team_name or len(team_name) < 2:
                        continue

                    # Extract team URL if link exists
                    team_url = None
                    if team_link:
                        team_link_href = await team_link.get_attribute('href')
                        if team_link_href:
                            if team_link_href.startswith('/'):
                                team_url = f'https://www.livesport.com{team_link_href}'
                            else:
                                team_url = team_link_href

                    # Extract rank from the rank cell
                    rank_element = await row.query_selector('.table__cell--rank')
                    rank = None
                    if rank_element:
                        rank_text = await rank_element.inner_text()
                        if rank_text and '.' in rank_text:
                            rank = int(rank_text.replace('.', '').strip())

                    # Extract stats using specific cell selectors
                    played = (
                        wins
                    ) = draws = losses = goals_for = goals_against = points = 0

                    # Get all value cells in the row
                    value_cells = await row.query_selector_all('.table__cell--value')

                    if len(value_cells) >= 6:
                        # GP (Games Played) - first value cell
                        gp_text = await value_cells[0].inner_text()
                        if gp_text.isdigit():
                            played = int(gp_text)

                        # W (Wins) - second value cell
                        w_text = await value_cells[1].inner_text()
                        if w_text.isdigit():
                            wins = int(w_text)

                        # T (Draws) - third value cell
                        t_text = await value_cells[2].inner_text()
                        if t_text.isdigit():
                            draws = int(t_text)

                        # L (Losses) - fourth value cell
                        l_text = await value_cells[3].inner_text()
                        if l_text.isdigit():
                            losses = int(l_text)

                        # G (Goals - format "17:3") - fifth value cell
                        g_text = await value_cells[4].inner_text()
                        if ':' in g_text:
                            goals_parts = g_text.split(':')
                            if len(goals_parts) == 2:
                                goals_for = (
                                    int(goals_parts[0])
                                    if goals_parts[0].isdigit()
                                    else 0
                                )
                                goals_against = (
                                    int(goals_parts[1])
                                    if goals_parts[1].isdigit()
                                    else 0
                                )

                        # Pts (Points) - seventh value cell (skip GD)
                        if len(value_cells) >= 7:
                            pts_text = await value_cells[6].inner_text()
                            if pts_text.isdigit():
                                points = int(pts_text)

                    team_data = {
                        'team': {'name': team_name},
                        'rank': rank,
                        'all': {
                            'played': played,
                            'win': wins,
                            'draw': draws,
                            'lose': losses,
                            'goals': {'for': goals_for, 'against': goals_against},
                        },
                        'points': points,
                        'coach': None,  # Will be filled in second pass
                    }

                    standings_data.append(team_data)
                    team_urls.append(team_url)  # Store URL for coach scraping
                    logger.debug(f'Extracted team: {team_name} (rank {rank})')

                except Exception as e:
                    logger.error(f'Error parsing standings row: {e}')
                    standings_data.append(None)  # Placeholder for failed row
                    team_urls.append(None)
                    continue

            # Second pass: scrape coaches for each team (only for current season)
            if not is_archived_season and self._scrape_coaches:
                logger.info('Scraping coaches for current season')
                for team_data, team_url in zip(standings_data, team_urls, strict=True):
                    if team_data is None or team_url is None:
                        continue

                    try:
                        coach = await self._scrape_team_coach_by_url(page, team_url)
                        if coach:
                            team_data['coach'] = coach
                            logger.debug(
                                f'Scraped coach for {team_data["team"]["name"]}: {coach}'
                            )
                    except Exception as e:
                        logger.warning(
                            f'Error scraping coach for {team_data["team"]["name"]}: {e}'
                        )
            else:
                logger.info(
                    f'Skipping coach scraping for archived season {parsed_season}'
                )

            # Filter out None entries
            standings_data = [data for data in standings_data if data is not None]

            logger.info(f'Scraped {len(standings_data)} teams from {league_name}')
            return standings_data

        except Exception as e:
            logger.error(f'Unexpected error while scraping standings: {e}')
            return []

    async def _scrape_team_coach_by_url(self, page: Page, team_url: str) -> str | None:
        """Scrape coach name from team page using URL"""
        try:
            logger.debug(f'Navigating to team page: {team_url}')

            # Navigate to team page
            if not await self._navigate_and_wait(page, team_url, '.tabs__tab', 30000):
                logger.warning(f'Failed to load team page: {team_url}')
                return None

            # Click on Squad tab
            try:
                squad_tab = await page.query_selector('a.tabs__tab[title="Squad"]')
                if not squad_tab:
                    logger.warning('Squad tab not found on team page')
                    return None

                await squad_tab.click()
                logger.debug('Clicked Squad tab')
                await page.wait_for_timeout(3000)  # Wait for content to load

            except Exception as e:
                logger.warning(f'Error clicking Squad tab: {e}')
                return None

            # Find all lineupTable elements
            lineup_tables = await page.query_selector_all(
                '.lineupTable.lineupTable--soccer'
            )

            coach_name = None
            # Find the table with title "Coach"
            for table in lineup_tables:
                try:
                    title_element = await table.query_selector('.lineupTable__title')
                    if not title_element:
                        continue

                    title_text = await title_element.inner_text()
                    if title_text and title_text.strip() == 'Coach':
                        # Found the coach table, now extract coach name
                        coach_link = await table.query_selector(
                            'a.lineupTable__cell--name'
                        )
                        if coach_link:
                            coach_name = await coach_link.inner_text()
                            if coach_name:
                                logger.debug(f'Found coach: {coach_name}')
                                coach_name = coach_name.strip()
                                break
                except Exception as e:
                    logger.debug(f'Error checking lineup table: {e}')
                    continue

            if not coach_name:
                logger.warning('Coach table not found on squad page')
                return None

            return coach_name

        except Exception as e:
            logger.error(f'Error scraping team coach: {e}')
            return None

    async def scrape_league_matches(
        self, country: str, league_name: str, season: int | None = None
    ) -> list[CommonMatchData]:
        """Scrape league matches from livesport.com

        Args:
            country: Country name (e.g., 'England')
            league_name: League name (e.g., 'Premier League')
            season: Optional season year (e.g., 2024). If None, parses season from page.
                    If provided, constructs URL for archived season (e.g., -2024-2025)
        """
        country_lower = country.lower().replace(' ', '-')
        league_lower = league_name.lower().replace(' ', '-')

        is_archived_season = season is not None

        # Add season suffix for archived seasons (e.g., premier-league-2024-2025)
        if season is not None:
            season_suffix = f'-{season}-{season + 1}'
            url = f'https://www.livesport.com/soccer/{country_lower}/{league_lower}{season_suffix}/results/'
        else:
            url = f'https://www.livesport.com/soccer/{country_lower}/{league_lower}/results/'

        logger.info(f'Scraping league matches from: {url} (season: {season})')

        browser = await self._setup_browser()

        try:
            page = await self._setup_page(browser)

            if not await self._navigate_and_wait(
                page, url, '.event__round--static', 60000
            ):
                return []

            # When scraping historical data, Livesport only shows the last N rounds by
            # default and provides a "Show more games" control that loads additional
            # rounds. To ensure we scrape a complete season, iteratively click this
            # control until no more rounds are available.
            if is_archived_season:
                await self._load_all_results_rounds(page)

            # Parse season from page if not provided
            if season is None:
                parsed_season = await self._parse_season_from_page(page)
                logger.info(f'Parsed season from page: {parsed_season}')
                season = parsed_season
            else:
                logger.info(f'Using provided season: {season}')

            # Use the correct selectors based on the HTML structure
            matches_data = []
            processed_matches = set()

            # Find all round containers
            round_containers = await page.query_selector_all(
                '.event__round.event__round--static'
            )
            logger.info(f'Found {len(round_containers)} round containers')

            for round_container in round_containers:
                try:
                    # Get round information
                    round_text = await round_container.inner_text()
                    round_info = round_text.strip() if round_text else None

                    # Extract round number from round text
                    round_number = None
                    if round_info:
                        match = re.search(r'(\d+)', round_info)
                        if match:
                            round_number = int(match.group(1))
                            round_info = f'Round {round_number}'

                    if not round_number:
                        logger.warning(
                            'Cannot parse Round number. Probably match is not regular round'
                        )
                        continue

                    # Find matches that belong to this specific round
                    # We need to iterate through siblings until we hit the next round
                    current_element = await round_container.query_selector(
                        'xpath=following-sibling::*[1]'
                    )
                    match_containers = []

                    while current_element:
                        # Check if this is a match container
                        class_name = await current_element.get_attribute('class')
                        if (
                            class_name
                            and 'event__match' in class_name
                            and 'event__match--withRowLink' in class_name
                        ):
                            match_containers.append(current_element)
                        # Check if we hit the next round (stop here)
                        elif class_name and 'event__round' in class_name:
                            break

                        # Move to next sibling
                        current_element = await current_element.query_selector(
                            'xpath=following-sibling::*[1]'
                        )

                    for match_container in match_containers:
                        try:
                            # Extract home team
                            home_participant = await match_container.query_selector(
                                '.event__homeParticipant'
                            )
                            if not home_participant:
                                continue

                            home_team_element = await home_participant.query_selector(
                                'span, strong'
                            )
                            if not home_team_element:
                                continue
                            home_team = await home_team_element.inner_text()

                            # Extract away team
                            away_participant = await match_container.query_selector(
                                '.event__awayParticipant'
                            )
                            if not away_participant:
                                continue

                            away_team_element = await away_participant.query_selector(
                                'span, strong'
                            )
                            if not away_team_element:
                                continue
                            away_team = await away_team_element.inner_text()

                            # Skip if we already processed this match
                            match_key = f'{home_team}_{away_team}'
                            if match_key in processed_matches:
                                continue
                            processed_matches.add(match_key)

                            # Extract scores
                            home_score_element = await match_container.query_selector(
                                '.event__score.event__score--home'
                            )
                            away_score_element = await match_container.query_selector(
                                '.event__score.event__score--away'
                            )

                            home_score = 0
                            away_score = 0

                            if home_score_element:
                                home_score_text = await home_score_element.inner_text()
                                if home_score_text and home_score_text.isdigit():
                                    home_score = int(home_score_text)

                            if away_score_element:
                                away_score_text = await away_score_element.inner_text()
                                if away_score_text and away_score_text.isdigit():
                                    away_score = int(away_score_text)

                            # Extract match date
                            time_element = await match_container.query_selector(
                                '.event__time'
                            )
                            match_date = None
                            if time_element:
                                date_text = await time_element.inner_text()
                                if date_text:
                                    match_date = self._parse_match_date(
                                        date_text, season
                                    )

                            # Create common match format
                            match_data = self._create_common_match_data(
                                home_team=home_team,
                                away_team=away_team,
                                league=league_name,
                                country=country.title(),  # Normalize country name
                                home_score=home_score,
                                away_score=away_score,
                                status='finished',
                                match_date=match_date,
                                round_number=round_number,
                                season=season,
                            )

                            matches_data.append(match_data)
                            logger.debug(
                                f'Extracted match: {home_team} vs {away_team} '
                                f'({home_score}:{away_score}) - {round_info}'
                            )

                        except Exception as e:
                            logger.error(f'Error parsing individual match: {e}')
                            continue

                except Exception as e:
                    logger.error(f'Error parsing round: {e}')
                    continue

            logger.info(f'Scraped {len(matches_data)} matches from {league_name}')
            return matches_data

        except Exception as e:
            logger.error(f'Unexpected error while scraping matches: {e}')
            return []

    async def _load_all_results_rounds(self, page: Page) -> None:
        """Click 'Show more games' until all historical rounds are loaded.

        Livesport shows only a subset of recent rounds in the results view and
        exposes a "Show more games" button at the bottom of the page that loads
        additional historical rounds. For accurate historical scraping we need to
        expand all available rounds before parsing the table.
        """
        try:
            while True:
                try:
                    # Look for the "Show more games" caption by its data-testid
                    button = await page.query_selector(
                        'span[data-testid="wcl-scores-caption-05"]'
                    )
                    if not button:
                        logger.debug('No "Show more games" button found')
                        break

                    text = (await button.inner_text()).strip()
                    if 'Show more games' not in text:
                        logger.debug(
                            '"Show more games" caption not present, stopping expansion',
                        )
                        break

                    logger.info('Clicking "Show more games" to load additional rounds')
                    await button.click()
                    # Give the page some time to load additional content
                    await page.wait_for_timeout(2000)
                except TimeoutError:
                    logger.debug(
                        'Timeout while looking for "Show more games" button; '
                        'assuming all rounds are loaded'
                    )
                    break
                except Exception as e:
                    logger.warning(
                        'Error while expanding additional results rounds, '
                        'continuing with currently loaded data',
                        error=str(e),
                    )
                    break
        except Exception as e:
            logger.error(
                f'Unexpected error while loading all results rounds: {e}',
            )

    def _is_monitored_league(self, league_name: str, country: str = None) -> bool:
        """Check if the league is in our monitored list"""
        if not league_name:
            return False

        # If country is provided, check for exact match with country
        if country:
            for monitored_country, leagues in self.monitored_leagues.items():
                if monitored_country.lower() == country.lower():
                    for league in leagues:
                        if league.lower() == league_name.lower():
                            return True
            return False

        # Fallback: check for exact matches without country (for backward compatibility)
        if league_name in self.monitored_leagues:
            return True

        # Check for partial matches (e.g., "Premier League" matches "English Premier League")
        for _, leagues in self.monitored_leagues.items():
            for league in leagues:
                if league.lower() == league_name.lower():
                    return True

        return False

    def _extract_minute(self, minute_text: str) -> int | None:
        """Extract minute from text like '2' or '45+2'"""
        if not minute_text:
            return None

        try:
            # Remove any non-numeric characters except '+'
            clean_text = ''.join(c for c in minute_text if c.isdigit() or c == '+')

            if '+' in clean_text:
                # Handle injury time like "45+2"
                parts = clean_text.split('+')
                if len(parts) == 2:
                    return int(parts[0]) + int(parts[1])

            return int(clean_text)
        except (ValueError, IndexError):
            return None

    async def _parse_season_from_page(self, page: Page) -> int:
        """Parse season from heading__info div (e.g., '2025/2026' -> 2025)"""
        try:
            # Look for the season info div
            season_element = await page.query_selector('.heading__info')
            if not season_element:
                logger.debug('No season info found, using default season')
                return self.DEFAULT_SEASON

            season_text = await season_element.inner_text()
            if not season_text:
                logger.debug('Empty season text, using default season')
                return self.DEFAULT_SEASON

            # Extract first number before "/" from text like "2025/2026"
            season_match = re.search(r'^(\d+)', season_text.strip())
            if season_match:
                season = int(season_match.group(1))
                logger.debug(f'Parsed season: {season} from text: {season_text}')
                return season
            else:
                logger.debug(
                    f'Could not parse season from: {season_text}, using default'
                )
                return self.DEFAULT_SEASON

        except Exception as e:
            logger.error(
                f'Error parsing season: {e}, using default {self.DEFAULT_SEASON}'
            )
            return self.DEFAULT_SEASON

    def _parse_datetime(
        self, date_text: str, season: int | None = None
    ) -> datetime | None:
        """Parse datetime from text in various formats:
        - 'Aug 25\n12:00 AM' (newline-separated)
        - 'Aug 30 06:00 PM' (space-separated)

        Args:
            date_text: Date text to parse
            season: Optional season year. If None, uses DEFAULT_SEASON
        """
        try:
            # Use provided season or default
            if season is None:
                season = self.DEFAULT_SEASON

            # Replace newlines with spaces and normalize whitespace
            normalized_text = ' '.join(date_text.strip().split())

            # Match pattern: "Month Day HH:MM AM/PM"
            # e.g., "Aug 25 12:00 AM" or "Aug 30 06:00 PM"
            pattern = r'(\w+)\s+(\d+)\s+(\d+):(\d+)\s+(AM|PM)'
            match = re.match(pattern, normalized_text)
            if not match:
                return None

            month_name = match.group(1)
            day = int(match.group(2))
            hour = int(match.group(3))
            minute = int(match.group(4))
            ampm = match.group(5)

            # Convert month name to number
            month_map = {
                'Jan': 1,
                'Feb': 2,
                'Mar': 3,
                'Apr': 4,
                'May': 5,
                'Jun': 6,
                'Jul': 7,
                'Aug': 8,
                'Sep': 9,
                'Oct': 10,
                'Nov': 11,
                'Dec': 12,
            }

            if month_name not in month_map:
                return None

            month = month_map[month_name]
            year = season

            # Convert to 24-hour format
            if ampm == 'PM' and hour != 12:
                hour += 12
            elif ampm == 'AM' and hour == 12:
                hour = 0

            return datetime(year, month, day, hour, minute)

        except Exception as e:
            logger.error(f'Error parsing datetime "{date_text}": {e}')
            return None

    def _parse_match_date(
        self, date_text: str, season: int | None = None
    ) -> datetime | None:
        """Parse match date from text like 'Aug 25\n12:00 AM'

        Args:
            date_text: Date text to parse
            season: Optional season year. If None, uses DEFAULT_SEASON
        """
        return self._parse_datetime(date_text, season)

    async def scrape_league_fixtures(
        self, country: str, league_name: str, season: int | None = None
    ) -> list[CommonMatchData]:
        """Scrape scheduled fixtures for a specific league

        Args:
            country: Country name (e.g., 'England')
            league_name: League name (e.g., 'Premier League')
            season: Optional season year (e.g., 2024). If None, parses season from page.
                    If provided, constructs URL for archived season (e.g., -2024-2025)
        """
        if season is not None:
            logger.error('No fixtures for historical seasons are available')
            return []

        logger.info(
            f'Scraping fixtures for {country}: {league_name} (season: {season})'
        )

        try:
            # Build the fixtures URL
            country_slug = country.lower()
            league_slug = league_name.lower().replace(' ', '-')

            # Add season suffix for archived seasons (e.g., premier-league-2024-2025)
            if season is not None:
                season_suffix = f'-{season}-{season + 1}'
                fixtures_url = f'https://www.livesport.com/soccer/{country_slug}/{league_slug}{season_suffix}/fixtures/'
            else:
                fixtures_url = f'https://www.livesport.com/soccer/{country_slug}/{league_slug}/fixtures/'

            logger.info(f'Navigating to fixtures URL: {fixtures_url}')

            # Setup browser and page
            browser = await self._setup_browser()
            page = await self._setup_page(browser)

            # Navigate to fixtures page
            success = await self._navigate_and_wait(
                page, fixtures_url, '.event__round--static', 10000
            )
            if not success:
                logger.error(f'Failed to load fixtures page: {fixtures_url}')
                return []

            # Parse season from page if not provided
            if season is None:
                parsed_season = await self._parse_season_from_page(page)
                logger.info(f'Parsed season from page: {parsed_season}')
                season = parsed_season
            else:
                logger.info(f'Using provided season: {season}')

            # Handle cookie banner if present
            await self._handle_cookie_banner(page)

            # Extract the first scheduled match only
            fixtures = await self._extract_fixtures(page, country, league_name, season)

            return fixtures

        except Exception as e:
            logger.error(f'Error scraping fixtures for {country}: {league_name}: {e}')
            return []

    async def _extract_fixtures(
        self, page: 'Page', country: str, league_name: str, season: int
    ) -> list[CommonMatchData]:
        """Extract fixture data from the page - find first scheduled round and scrape all its matches"""
        try:
            # Find all round elements with class "event__round--static"
            round_elements = await page.query_selector_all('.event__round--static')

            if not round_elements:
                logger.warning('No scheduled rounds found on fixtures page')
                return []

            # Get the first scheduled round
            first_round = round_elements[0]
            round_text = await first_round.text_content()
            logger.info(f'Found first scheduled round: {round_text}')

            # Extract round number from round text
            round_number = None
            if round_text:
                match = re.search(r'(\d+)', round_text)
                if match:
                    round_number = int(match.group(1))
                    round_text = f'Round {round_number}'

            # Find all match elements that belong to this round
            # Get the parent container and iterate through its children
            # to find matches after the first round
            parent_container = await page.query_selector('.sportName.soccer')
            if not parent_container:
                logger.warning('Parent container not found')
                return []

            all_elements = await parent_container.query_selector_all(':scope > *')

            fixtures = []
            found_first_round = False
            collecting_matches = False

            for element in all_elements:
                element_text = await element.text_content()
                if not element_text:
                    continue

                # Check if this is the first round we're looking for
                if (
                    not found_first_round
                    and 'Round' in element_text
                    and element_text.strip() == round_text.strip()
                ):
                    found_first_round = True
                    collecting_matches = True
                    logger.info(f'Starting to collect matches for round: {round_text}')
                    continue

                # If we're collecting matches and hit another round, stop
                if (
                    collecting_matches
                    and 'Round' in element_text
                    and element_text.strip() != round_text.strip()
                ):
                    logger.info(
                        f'Found next round, stopping collection: {element_text}'
                    )
                    break

                # If we're collecting matches and this looks like a match element
                if collecting_matches and await self._is_match_element(element):
                    fixture = await self._extract_single_fixture(
                        element, country, league_name, round_number, season
                    )
                    if fixture:
                        fixtures.append(fixture)
                        logger.info(
                            f'Extracted fixture: {fixture.home_team} vs '
                            f'{fixture.away_team} on {fixture.match_date}'
                        )

            logger.info(f'Total fixtures extracted for {round_text}: {len(fixtures)}')
            return fixtures

        except Exception as e:
            logger.error(f'Error extracting fixtures: {e}')
            return []

    async def _is_match_element(self, element: ElementHandle) -> bool:
        """Check if an element represents a match (has the correct class structure)"""
        try:
            # Check if element has the match class structure
            class_name = await element.get_attribute('class')
            if not class_name:
                return False

            # Check if it has the required match classes
            has_match_classes = (
                'event__match' in class_name
                and 'event__match--withRowLink' in class_name
                and 'event__match--static' in class_name
                and 'event__match--scheduled' in class_name
            )

            if not has_match_classes:
                return False

            # Also check if it has time and team elements
            has_time = await element.query_selector('.event__time') is not None
            has_home_team = (
                await element.query_selector('.event__homeParticipant') is not None
            )
            has_away_team = (
                await element.query_selector('.event__awayParticipant') is not None
            )

            return has_time and has_home_team and has_away_team

        except Exception as e:
            logger.error(f'Error checking if element is match: {e}')
            return False

    async def _extract_single_fixture(
        self,
        element: ElementHandle,
        country: str,
        league_name: str,
        round_number: int = None,
        season: int | None = None,
    ) -> CommonMatchData | None:
        """Extract a single fixture from a match element"""
        try:
            # Use DEFAULT_SEASON if season is not provided
            if season is None:
                season = self.DEFAULT_SEASON
            # Extract date and time from the event__time element
            time_element = await element.query_selector('.event__time')
            if not time_element:
                logger.warning('No time element found in match')
                return None

            time_text = await time_element.text_content()
            if not time_text:
                logger.warning('No time text found in time element')
                return None

            # Parse the date and time (format: "Aug 30\n06:00 PM" or "Aug 3006:00 PM")
            # First try to split by newline
            lines = time_text.strip().split('\n')
            if len(lines) >= 2:
                # Format: "Aug 30\n06:00 PM"
                date_part = lines[0].strip()  # "Aug 30"
                time_part = lines[1].strip()  # "06:00 PM"
            else:
                # Format: "Aug 3006:00 PM" - need to separate date and time
                # Find where the time pattern starts (HH:MM)
                time_match = re.search(r'(\d{1,2}:\d{2}\s+(AM|PM))', time_text)
                if not time_match:
                    logger.warning(f'Could not find time pattern in: {time_text}')
                    return None

                time_part = time_match.group(1)  # "06:00 PM"
                # Extract date part (everything before the time)
                date_part = time_text[: time_match.start()].strip()  # "Aug 30"

            # Extract home team
            home_element = await element.query_selector(
                '.event__homeParticipant span[data-testid="wcl-scores-simple-text-01"]'
            )
            if not home_element:
                logger.warning('No home team element found')
                return None

            home_team = await home_element.text_content()
            if not home_team:
                logger.warning('No home team text found')
                return None

            # Extract away team
            away_element = await element.query_selector(
                '.event__awayParticipant span[data-testid="wcl-scores-simple-text-01"]'
            )
            if not away_element:
                logger.warning('No away team element found')
                return None

            away_team = await away_element.text_content()
            if not away_team:
                logger.warning('No away team text found')
                return None

            # Combine date and time for parsing
            date_time_text = f'{date_part} {time_part}'

            # Parse the date and time
            match_datetime = self._parse_fixture_datetime(date_time_text, season)

            if not match_datetime:
                logger.warning(f'Could not parse datetime from: {date_time_text}')
                return None

            # Create common match format for fixture
            fixture = self._create_common_match_data(
                home_team=home_team.strip(),
                away_team=away_team.strip(),
                league=league_name,  # Will be set by caller
                country=country.title(),  # Normalize country name
                home_score=None,
                away_score=None,
                status='scheduled',
                match_date=match_datetime,
                round_number=round_number,
                season=season,
            )

            logger.debug(
                f'Extracted fixture: {home_team} vs {away_team} on {date_part} at {time_part}'
            )
            return fixture

        except Exception as e:
            logger.error(f'Error extracting single fixture: {e}')
            return None

    def _parse_fixture_datetime(
        self, date_text: str, season: int | None = None
    ) -> datetime | None:
        """Parse fixture datetime from text like 'Aug 30 06:00 PM'

        Args:
            date_text: Date text to parse
            season: Optional season year. If None, uses DEFAULT_SEASON
        """
        return self._parse_datetime(date_text, season)

    def _create_common_match_data(
        self,
        home_team: str,
        away_team: str,
        league: str,
        country: str,
        home_score: int = None,
        away_score: int = None,
        status: str = 'scheduled',
        match_date: datetime = None,
        minute: int = None,
        red_cards_home: int = 0,
        red_cards_away: int = 0,
        round_number: int = None,
        season: int = DEFAULT_SEASON,
    ) -> CommonMatchData:
        """Create a common match data structure for all match types"""
        return CommonMatchData(
            home_team=home_team,
            away_team=away_team,
            league=league,
            country=country.title() if country else country,  # Normalize country name
            home_score=home_score,
            away_score=away_score,
            status=status,
            round_number=round_number,
            match_date=match_date,
            minute=minute,
            red_cards_home=red_cards_home,
            red_cards_away=red_cards_away,
            season=season,
        )
