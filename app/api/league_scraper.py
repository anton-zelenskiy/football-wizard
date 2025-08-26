import asyncio
from datetime import datetime
from typing import Any

import structlog
from playwright.async_api import TimeoutError, async_playwright

from app.api.constants import LEAGUES_OF_INTEREST

logger = structlog.get_logger()


class LeagueScraper:
    def __init__(self) -> None:
        self.monitored_leagues = LEAGUES_OF_INTEREST

    async def scrape_league_standings(self, country: str, league_name: str) -> list[dict[str, Any]]:
        """Scrape league standings from livesport.com"""
        # Construct URL for the specific league
        country_lower = country.lower().replace(' ', '-')
        league_lower = league_name.lower().replace(' ', '-')
        url = f'https://www.livesport.com/soccer/{country_lower}/{league_lower}/standings/'

        logger.info(f'Scraping league standings from: {url}')

        async with async_playwright() as p:
            browser = await p.chromium.launch(
                headless=True,
                args=[
                    '--no-sandbox',
                    '--disable-setuid-sandbox',
                    '--disable-dev-shm-usage',
                    '--disable-accelerated-2d-canvas',
                    '--no-first-run',
                    '--no-zygote',
                    '--disable-gpu',
                ],
            )

            try:
                page = await browser.new_page()
                await page.set_extra_http_headers(
                    {
                        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
                        'Accept-Language': 'en-US,en;q=0.9',
                        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                    }
                )

                logger.info(f'Navigating to {url}')
                await page.goto(url, wait_until='domcontentloaded', timeout=60000)
                logger.info('Page loaded successfully')

                # Close cookie banner if present
                try:
                    await page.wait_for_selector('button:has-text("I Accept")', timeout=5000)
                    cookie_button = await page.query_selector('button:has-text("I Accept")')
                    if cookie_button:
                        await cookie_button.click()
                        logger.info('Closed cookie banner')
                except Exception as e:
                    logger.info(f'No cookie banner to close: {e}')

                # We're already on the standings page, no need to click anything
                logger.info('Already on standings page, waiting for table to load')

                # Wait for standings data to load
                try:
                    await page.wait_for_selector('a[href*="/team/"]', timeout=10000)
                except TimeoutError:
                    logger.error('Standings data not found')
                    return []

                # Use optimized selectors to get table rows directly
                table_rows = await page.query_selector_all('.ui-table__row')
                standings_data = []

                for row in table_rows:
                    try:
                        # Extract team name from the participant cell
                        team_element = await row.query_selector('.table__cell--participant')
                        if not team_element:
                            continue

                        team_name = await team_element.inner_text()
                        team_name = team_name.strip()

                        if not team_name or len(team_name) < 2:
                            continue

                        # Extract rank from the rank cell
                        rank_element = await row.query_selector('.table__cell--rank')
                        rank = None
                        if rank_element:
                            rank_text = await rank_element.inner_text()
                            if rank_text and '.' in rank_text:
                                rank = int(rank_text.replace('.', '').strip())

                        # Extract stats using specific cell selectors
                        played = wins = draws = losses = goals_for = goals_against = points = 0

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
                                        int(goals_parts[0]) if goals_parts[0].isdigit() else 0
                                    )
                                    goals_against = (
                                        int(goals_parts[1]) if goals_parts[1].isdigit() else 0
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
                        }

                        standings_data.append(team_data)
                        logger.debug(f'Extracted team: {team_name} (rank {rank})')

                    except Exception as e:
                        logger.error(f'Error parsing standings row: {e}')
                        continue

                logger.info(f'Scraped {len(standings_data)} teams from {league_name}')
                return standings_data

            except TimeoutError as e:
                logger.error(f'Timeout error while scraping standings: {e}')
                return []
            except Exception as e:
                logger.error(f'Unexpected error while scraping standings: {e}')
                return []
            finally:
                await browser.close()

    async def scrape_league_matches(self, country: str, league_name: str) -> list[dict[str, Any]]:
        """Scrape league matches from livesport.com"""
        country_lower = country.lower().replace(' ', '-')
        league_lower = league_name.lower().replace(' ', '-')
        url = f'https://www.livesport.com/soccer/{country_lower}/{league_lower}/results/'

        logger.info(f'Scraping league matches from: {url}')

        async with async_playwright() as p:
            browser = await p.chromium.launch(
                headless=True,
                args=[
                    '--no-sandbox',
                    '--disable-setuid-sandbox',
                    '--disable-dev-shm-usage',
                    '--disable-accelerated-2d-canvas',
                    '--no-first-run',
                    '--no-zygote',
                    '--disable-gpu',
                ],
            )

            try:
                page = await browser.new_page()
                await page.set_extra_http_headers(
                    {
                        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
                        'Accept-Language': 'en-US,en;q=0.9',
                        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                    }
                )

                logger.info(f'Navigating to {url}')
                await page.goto(url, wait_until='domcontentloaded', timeout=60000)
                logger.info('Page loaded successfully')

                # Close cookie banner if present
                try:
                    await page.wait_for_selector('button:has-text("I Accept")', timeout=5000)
                    cookie_button = await page.query_selector('button:has-text("I Accept")')
                    if cookie_button:
                        await cookie_button.click()
                        logger.info('Closed cookie banner')
                except Exception as e:
                    logger.info(f'No cookie banner to close: {e}')

                # We're already on the results page, no need to click anything
                logger.info('Already on results page, waiting for matches to load')

                # Wait for matches to load
                try:
                    await page.wait_for_selector('a[href*="/game/soccer/"]', timeout=10000)
                except TimeoutError:
                    logger.error('Matches not found')
                    return []

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
                                time_element = await match_container.query_selector('.event__time')
                                match_date = None
                                if time_element:
                                    date_text = await time_element.inner_text()
                                    if date_text:
                                        match_date = self._parse_match_date(date_text)

                                # Extract status - assume finished for results page
                                status = 'FT'

                                match_data = {
                                    'fixture': {
                                        'date': match_date.isoformat() if match_date else None,
                                        'status': {'short': status},
                                    },
                                    'teams': {
                                        'home': {'name': home_team},
                                        'away': {'name': away_team},
                                    },
                                    'goals': {'home': home_score, 'away': away_score},
                                    'league': {'season': 2025},
                                    'round': round_info,
                                }

                                matches_data.append(match_data)
                                logger.debug(
                                    f'Extracted match: {home_team} vs {away_team} ({home_score}:{away_score}) - {round_info}'
                                )

                            except Exception as e:
                                logger.error(f'Error parsing individual match: {e}')
                                continue

                    except Exception as e:
                        logger.error(f'Error parsing round: {e}')
                        continue

                logger.info(f'Scraped {len(matches_data)} matches from {league_name}')
                return matches_data

            except TimeoutError as e:
                logger.error(f'Timeout error while scraping matches: {e}')
                return []
            except Exception as e:
                logger.error(f'Unexpected error while scraping matches: {e}')
                return []
            finally:
                await browser.close()

    def _parse_score(self, score_text: str) -> tuple[int, int]:
        """Parse score text like '2:1' into home and away scores"""
        try:
            if ':' in score_text:
                home, away = score_text.split(':')
                return int(home.strip()), int(away.strip())
            return 0, 0
        except (ValueError, IndexError):
            return 0, 0

    def _parse_match_date(self, date_text: str) -> datetime | None:
        """Parse match date from text like 'Aug 25\n12:00 AM'"""
        try:
            import re
            from datetime import datetime

            # Clean the text and split by newline
            lines = date_text.strip().split('\n')
            if len(lines) < 2:
                return None

            date_part = lines[0].strip()  # "Aug 25"
            time_part = lines[1].strip()  # "12:00 AM"

            # Parse the date part (e.g., "Aug 25")
            date_match = re.match(r'(\w+)\s+(\d+)', date_part)
            if not date_match:
                return None

            month_name = date_match.group(1)
            day = int(date_match.group(2))

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
            year = 2025  # Assuming current season

            # Parse the time part (e.g., "12:00 AM")
            time_match = re.match(r'(\d+):(\d+)\s+(AM|PM)', time_part)
            if not time_match:
                return None

            hour = int(time_match.group(1))
            minute = int(time_match.group(2))
            ampm = time_match.group(3)

            # Convert to 24-hour format
            if ampm == 'PM' and hour != 12:
                hour += 12
            elif ampm == 'AM' and hour == 12:
                hour = 0

            return datetime(year, month, day, hour, minute)

        except Exception as e:
            logger.error(f'Error parsing date "{date_text}": {e}')
            return None

    def _parse_status(self, status_text: str) -> str:
        """Parse match status from text"""
        status_text = status_text.lower()
        if 'ft' in status_text or 'finished' in status_text:
            return 'FT'
        elif 'live' in status_text:
            return 'LIVE'
        else:
            return 'SCHEDULED'

    async def scrape_russian_premier_league(self) -> dict[str, Any]:
        """Scrape Russian Premier League data as entry point"""
        logger.info('Starting Russian Premier League scraping')

        standings = await self.scrape_league_standings('Russia', 'Premier League')
        matches = await self.scrape_league_matches('Russia', 'Premier League')

        return {
            'league': 'Russian Premier League',
            'country': 'Russia',
            'standings': standings,
            'matches': matches,
        }

    async def scrape_all_monitored_leagues(self) -> list[dict[str, Any]]:
        """Scrape all monitored leagues"""
        all_data = []

        for country, leagues in self.monitored_leagues.items():
            for league in leagues:
                try:
                    logger.info(f'Scraping {country}: {league}')
                    standings = await self.scrape_league_standings(country, league)
                    matches = await self.scrape_league_matches(country, league)

                    league_data = {
                        'league': league,
                        'country': country,
                        'standings': standings,
                        'matches': matches,
                    }
                    all_data.append(league_data)

                except Exception as e:
                    logger.error(f'Error scraping {country}: {league}: {e}')
                    continue

        return all_data


# Legacy function for backward compatibility
async def scrape_league_standings(country: str, league_name: str) -> list[dict[str, Any]]:
    """Legacy function - use LeagueScraper.scrape_league_standings() instead"""
    scraper = LeagueScraper()
    return await scraper.scrape_league_standings(country, league_name)


# Legacy function for backward compatibility
async def scrape_league_matches() -> list[dict[str, Any]]:
    scraper = LeagueScraper()
    return await scraper.scrape_league_matches('Russia', 'Premier League')


if __name__ == '__main__':
    import asyncio

    async def test_scraping() -> None:
        scraper = LeagueScraper()
        await scraper.scrape_russian_premier_league()

    asyncio.run(test_scraping())
