"""Tests for LivesportScraper context manager functionality"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.scraper.livesport_scraper import LivesportScraper


class TestLivesportScraperContextManager:
    """Test the context manager functionality of LivesportScraper"""

    @pytest.mark.asyncio
    async def test_context_manager_initialization(self):
        """Test that the context manager properly initializes resources"""
        with patch('app.scraper.livesport_scraper.async_playwright') as mock_playwright:
            # Mock the playwright instance
            mock_playwright_instance = AsyncMock()
            mock_browser = AsyncMock()
            mock_playwright_instance.chromium.launch = AsyncMock(return_value=mock_browser)
            mock_playwright.return_value.start = AsyncMock(return_value=mock_playwright_instance)

            scraper = LivesportScraper()

            # Test context manager entry
            async with scraper as scraper_instance:
                assert scraper_instance is scraper
                assert scraper._playwright is not None
                assert scraper._browser is not None

                # Verify playwright was started
                mock_playwright.return_value.start.assert_called_once()

                # Verify browser was launched
                mock_playwright_instance.chromium.launch.assert_called_once()

            # Test context manager exit - resources should be cleaned up
            mock_browser.close.assert_called_once()
            mock_playwright_instance.stop.assert_called_once()

    @pytest.mark.asyncio
    async def test_context_manager_cleanup_on_exception(self):
        """Test that resources are cleaned up even when an exception occurs"""
        with patch('app.scraper.livesport_scraper.async_playwright') as mock_playwright:
            # Mock the playwright instance
            mock_playwright_instance = AsyncMock()
            mock_browser = AsyncMock()
            mock_playwright_instance.chromium.launch = AsyncMock(return_value=mock_browser)
            mock_playwright.return_value.start = AsyncMock(return_value=mock_playwright_instance)

            scraper = LivesportScraper()

            # Test that cleanup happens even with exceptions
            try:
                async with scraper:
                    raise ValueError('Test exception')
            except ValueError:
                pass

            # Verify cleanup was called
            mock_browser.close.assert_called_once()
            mock_playwright_instance.stop.assert_called_once()

    @pytest.mark.asyncio
    async def test_setup_browser_without_context_manager(self):
        """Test that _setup_browser raises error when not used as context manager"""
        scraper = LivesportScraper()

        with pytest.raises(
            RuntimeError, match='Browser not initialized. Use LivesportScraper as context manager.'
        ):
            await scraper._setup_browser()

    @pytest.mark.asyncio
    async def test_context_manager_reuse(self):
        """Test that the context manager can be reused"""
        with patch('app.scraper.livesport_scraper.async_playwright') as mock_playwright:
            # Mock the playwright instance
            mock_playwright_instance = AsyncMock()
            mock_browser = AsyncMock()
            mock_playwright_instance.chromium.launch = AsyncMock(return_value=mock_browser)
            mock_playwright.return_value.start = AsyncMock(return_value=mock_playwright_instance)

            scraper = LivesportScraper()

            # First use
            async with scraper:
                assert scraper._playwright is not None
                assert scraper._browser is not None

            # Second use - create new mocks for the second context manager use
            mock_playwright_instance2 = AsyncMock()
            mock_browser2 = AsyncMock()
            mock_playwright_instance2.chromium.launch = AsyncMock(return_value=mock_browser2)
            mock_playwright.return_value.start = AsyncMock(return_value=mock_playwright_instance2)

            async with scraper:
                assert scraper._playwright is not None
                assert scraper._browser is not None

            # Verify cleanup was called for both instances
            assert mock_browser.close.call_count == 1
            assert mock_browser2.close.call_count == 1
            assert mock_playwright_instance.stop.call_count == 1
            assert mock_playwright_instance2.stop.call_count == 1

    @pytest.mark.asyncio
    async def test_scrape_methods_with_context_manager(self):
        """Test that scraping methods work with context manager"""
        with patch('app.scraper.livesport_scraper.async_playwright') as mock_playwright:
            # Mock the playwright instance
            mock_playwright_instance = AsyncMock()
            mock_browser = AsyncMock()
            mock_page = AsyncMock()

            # Mock page methods
            mock_page.goto = AsyncMock()
            mock_page.wait_for_selector = AsyncMock()
            mock_page.query_selector_all = AsyncMock(return_value=[])
            mock_page.get_by_text = MagicMock()
            mock_page.wait_for_timeout = AsyncMock()

            mock_browser.new_page = AsyncMock(return_value=mock_page)
            mock_playwright_instance.chromium.launch = AsyncMock(return_value=mock_browser)
            mock_playwright.return_value.start = AsyncMock(return_value=mock_playwright_instance)

            scraper = LivesportScraper()

            # Test that scraping methods work within context manager
            async with scraper:
                # This should not raise an error
                result = await scraper.scrape_live_matches()
                assert isinstance(result, list)

            # Verify cleanup was called
            mock_browser.close.assert_called_once()
            mock_playwright_instance.stop.assert_called_once()
