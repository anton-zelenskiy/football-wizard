"""Tests for BettingTasks refactored methods"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.tasks.betting_tasks import BettingTasks


class TestBettingTasksRefactored:
    """Test the refactored BettingTasks methods"""

    @pytest.mark.asyncio
    async def test_refresh_league_data_task_uses_individual_context_managers(self):
        """Test that refresh_league_data_task uses context manager for each league individually"""
        with patch('app.tasks.betting_tasks.LivesportScraper') as mock_scraper_class:
            # Mock the scraper instances
            mock_scraper_instance = AsyncMock()
            mock_scraper_class.return_value = mock_scraper_instance

            # Mock the monitored leagues
            mock_scraper_instance.monitored_leagues = {
                'England': ['Premier League'],
                'Spain': ['La Liga'],
            }

            # Mock the _process_single_league method
            betting_tasks = BettingTasks()
            betting_tasks._process_single_league = AsyncMock(
                return_value={
                    'standings_count': 5,
                    'matches_count': 10,
                    'fixtures_count': 8,
                }
            )
            betting_tasks.storage = MagicMock()
            betting_tasks.storage.update_betting_outcomes = MagicMock()

            # Test the method
            result = await betting_tasks.refresh_league_data_task({})

            # Verify that context manager was used for each league
            # Should be called twice (once for each league)
            assert mock_scraper_class.call_count == 3  # 1 temp + 2 for each league

            # Verify the result
            assert 'Refreshed data for 2 leagues' in result
            assert '10 standings' in result  # 5 * 2 leagues
            assert '20 matches' in result  # 10 * 2 leagues
            assert '16 fixtures' in result  # 8 * 2 leagues

            # Verify _process_single_league was called for each league
            assert betting_tasks._process_single_league.call_count == 2

    @pytest.mark.asyncio
    async def test_refresh_league_data_task_handles_errors_gracefully(self):
        """Test that refresh_league_data_task handles errors for individual leagues"""
        with patch('app.tasks.betting_tasks.LivesportScraper') as mock_scraper_class:
            # Mock the scraper instances
            mock_scraper_instance = AsyncMock()
            mock_scraper_class.return_value = mock_scraper_instance

            # Mock the monitored leagues
            mock_scraper_instance.monitored_leagues = {
                'England': ['Premier League'],
                'Spain': ['La Liga'],
            }

            # Mock the _process_single_league method to fail for one league
            betting_tasks = BettingTasks()
            betting_tasks._process_single_league = AsyncMock(
                side_effect=[
                    {
                        'standings_count': 5,
                        'matches_count': 10,
                        'fixtures_count': 8,
                    },  # Success
                    Exception('Test error'),  # Failure
                ]
            )
            betting_tasks.storage = MagicMock()
            betting_tasks.storage.update_betting_outcomes = MagicMock()

            # Test the method - should not raise exception
            result = await betting_tasks.refresh_league_data_task({})

            # Verify that it processed one league successfully
            assert 'Refreshed data for 1 leagues' in result

            # Verify _process_single_league was called for both leagues
            assert betting_tasks._process_single_league.call_count == 2

    @pytest.mark.asyncio
    async def test_refresh_league_data_task_memory_efficiency(self):
        """Test that the refactored method is more memory efficient"""
        with patch('app.tasks.betting_tasks.LivesportScraper') as mock_scraper_class:
            # Mock the scraper instances
            mock_scraper_instance = AsyncMock()
            mock_scraper_class.return_value = mock_scraper_instance

            # Mock the monitored leagues with multiple leagues
            mock_scraper_instance.monitored_leagues = {
                'England': ['Premier League', 'Championship'],
                'Spain': ['La Liga', 'Segunda Division'],
            }

            # Mock the _process_single_league method
            betting_tasks = BettingTasks()
            betting_tasks._process_single_league = AsyncMock(
                return_value={
                    'standings_count': 5,
                    'matches_count': 10,
                    'fixtures_count': 8,
                }
            )
            betting_tasks.storage = MagicMock()
            betting_tasks.storage.update_betting_outcomes = MagicMock()

            # Test the method
            result = await betting_tasks.refresh_league_data_task({})

            # Verify that context manager was used for each individual league
            # Should be called 5 times: 1 temp + 4 for each league
            assert mock_scraper_class.call_count == 5

            # Verify the result
            assert 'Refreshed data for 4 leagues' in result

            # Verify _process_single_league was called for each league
            assert betting_tasks._process_single_league.call_count == 4
