import asyncio
from typing import Any

import structlog
from playwright.async_api import TimeoutError, async_playwright

from app.api.constants import LEAGUES_OF_INTEREST

logger = structlog.get_logger()


class LiveMatchScraper:
    def __init__(self) -> None:
        self.monitored_leagues = LEAGUES_OF_INTEREST

    async def scrape(self) -> list[dict[str, Any]]:
        """Scrape live matches from livesport.com"""
        url = 'https://www.livesport.com/soccer/'
        async with async_playwright() as p:
            browser = await p.chromium.launch(
                headless=True,  # Set to False for debugging
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

                # Click LIVE tab
                try:
                    await page.wait_for_selector('text=LIVE', timeout=30000)
                    live_tab = page.get_by_text('LIVE', exact=True)
                    logger.info('Found LIVE tab')
                except TimeoutError:
                    logger.warning('LIVE tab not found, trying alternative selectors')
                    live_tab = await page.query_selector(
                        'div.filters__text.filters__text--short:text("LIVE")'
                    )
                    if not live_tab:
                        logger.error('Could not find LIVE tab with any selector')
                        return []

                if live_tab:
                    logger.info('Clicking LIVE tab')
                    await live_tab.click()
                    logger.info('Clicked LIVE tab')
                    await page.wait_for_timeout(5000)
                else:
                    logger.warning('LIVE tab not found')

                # Wait for live matches to appear
                try:
                    await page.wait_for_selector('.event__match', timeout=2000)
                except TimeoutError:
                    logger.warning('No live matches found or selector changed')
                    return []

                # Get all event titles and matches in order
                all_elements = await page.query_selector_all('.event__title, .event__match')

                results = []
                current_country = ''
                current_league = ''

                for i, element in enumerate(all_elements):
                    try:
                        # Check if this is an event title (league header)
                        is_title = await element.evaluate(
                            '(el) => el.classList.contains("event__title")'
                        )

                        if is_title:
                            # Extract country from span with data-testid="wcl-scores-overline-05"
                            country_el = await element.query_selector(
                                'span[data-testid="wcl-scores-overline-05"]'
                            )
                            if country_el:
                                current_country = await country_el.inner_text()
                                logger.debug(f'Found country: {current_country}')

                            # Extract league from strong with data-testid="wcl-scores-simpleText-01"
                            league_el = await element.query_selector(
                                'strong[data-testid="wcl-scores-simpleText-01"]'
                            )
                            if league_el:
                                current_league = await league_el.inner_text()
                                logger.debug(f'Found league: {current_league}')

                        else:
                            # This is a match, extract match data
                            match = element

                            # Check if this league is in our monitored list
                            if not self._is_monitored_league(current_league):
                                continue

                            # Debug: log outer HTML/text of the match element
                            try:
                                outer_html = await match.evaluate('(el) => el.outerHTML')
                                logger.debug(f'Match {len(results)} outer HTML', html=outer_html)
                            except Exception as e:
                                logger.warning(
                                    f'Could not get outer HTML for match {len(results)}',
                                    error=str(e),
                                )

                            # Extract home team name
                            home_el = await match.query_selector(
                                '.event__homeParticipant span[data-testid="wcl-scores-simpleText-01"]'
                            )
                            home = await home_el.inner_text() if home_el else ''
                            logger.debug(f'Match {len(results)} home team', value=home)

                            # Extract away team name
                            away_el = await match.query_selector(
                                '.event__awayParticipant span[data-testid="wcl-scores-simpleText-01"]'
                            )
                            away = await away_el.inner_text() if away_el else ''
                            logger.debug(f'Match {len(results)} away team', value=away)

                            # Scores
                            score_home_el = await match.query_selector(
                                'span[data-testid="wcl-matchRowScore"][data-side="1"]'
                            )
                            score_away_el = await match.query_selector(
                                'span[data-testid="wcl-matchRowScore"][data-side="2"]'
                            )
                            score_home = await score_home_el.inner_text() if score_home_el else ''
                            score_away = await score_away_el.inner_text() if score_away_el else ''
                            score = (
                                f'{score_home}:{score_away}' if score_home and score_away else ''
                            )
                            logger.debug(
                                f'Match {len(results)} score',
                                home=score_home,
                                away=score_away,
                                score=score,
                            )

                            # Minute: try to extract from .event__stage or similar
                            minute_el = await match.query_selector('.event__stage')
                            minute_text = await minute_el.inner_text() if minute_el else ''
                            minute = self._extract_minute(minute_text)
                            logger.debug(f'Match {len(results)} minute', value=minute)

                            # Red card: look for red card icon in home or away
                            red_card_home = await match.query_selector(
                                '.event__icon--redCard.event__icon--home'
                            )
                            red_card_away = await match.query_selector(
                                '.event__icon--redCard.event__icon--away'
                            )
                            red_cards_home = 1 if red_card_home else 0
                            red_cards_away = 1 if red_card_away else 0
                            logger.debug(
                                f'Match {len(results)} red cards',
                                home=red_cards_home,
                                away=red_cards_away,
                            )

                            # Convert scores to integers
                            home_score = int(score_home) if score_home.isdigit() else 0
                            away_score = int(score_away) if score_away.isdigit() else 0

                            match_data = {
                                'home_team': home,
                                'away_team': away,
                                'league': current_league,
                                'country': current_country,
                                'home_score': home_score,
                                'away_score': away_score,
                                'minute': minute,
                                'red_cards_home': red_cards_home,
                                'red_cards_away': red_cards_away,
                                'status': 'live',
                            }

                            results.append(match_data)
                            logger.info(
                                f'Scraped match: {home} vs {away} ({current_country}: {current_league})'
                            )

                    except Exception as e:
                        logger.error(f'Error parsing element {i}', error=str(e))

                logger.info(f'Scraped {len(results)} live matches')
                return results

            except TimeoutError as e:
                logger.error(f'Timeout error while scraping: {e}')
                return []
            except Exception as e:
                logger.error(f'Unexpected error while scraping: {e}')
                return []
            finally:
                await browser.close()

    def _is_monitored_league(self, league_name: str) -> bool:
        """Check if the league is in our monitored list"""
        if not league_name:
            return False

        # Check for exact matches
        if league_name in self.monitored_leagues:
            return True

        # Check for partial matches (e.g., "Premier League" matches "English Premier League")
        for _, leagues in self.monitored_leagues.items():
            for league in leagues:
                if (
                    league.lower() in league_name.lower()
                    or league_name.lower() in league.lower()
                ):
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



# Legacy function for backward compatibility
async def scrape_livesport_live_matches() -> list[dict[str, Any]]:
    """Legacy function - use LiveMatchScraper.scrape() instead"""
    scraper = LiveMatchScraper()
    return await scraper.scrape()


if __name__ == '__main__':
    import asyncio

    asyncio.run(scrape_livesport_live_matches())
