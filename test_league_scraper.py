#!/usr/bin/env python3
"""
Test script for League Scraper
"""

import asyncio

import structlog
from app.api.league_scraper import LeagueScraper
from app.db.models import init_db
from app.db.storage import FootballDataStorage

logger = structlog.get_logger()


async def test_russian_premier_league():
    """Test Russian Premier League scraping"""
    print("🧪 Testing Russian Premier League scraping...")

    # Initialize database
    init_db()

    # Create scrapers
    scraper = LeagueScraper()
    storage = FootballDataStorage()

    try:
        # Scrape Russian Premier League
        print("📡 Scraping Russian Premier League...")
        league_data = await scraper.scrape_russian_premier_league()

        print("✅ Scraped data:")
        print(f"   League: {league_data['league']}")
        print(f"   Country: {league_data['country']}")
        print(f"   Teams: {len(league_data['standings'])}")
        print(f"   Matches: {len(league_data['matches'])}")

        # Save to database
        print("💾 Saving to database...")
        league_name = league_data['league']
        country = league_data['country']
        standings = league_data['standings']
        matches = league_data['matches']

        # Save league
        storage.save_leagues([{
            'league': {'name': league_name},
            'country': {'name': country}
        }])

        # Save standings
        if standings:
            storage.save_league_standings(standings, league_name)
            print(f"   ✅ Saved {len(standings)} team standings")

        # Save matches
        if matches:
            storage.save_matches(matches, league_name)
            print(f"   ✅ Saved {len(matches)} matches")

        # Verify data in database
        print("🔍 Verifying data in database...")
        leagues = storage.get_all_leagues()
        print(f"   Leagues in DB: {len(leagues)}")

        if leagues:
            league = leagues[0]
            teams = storage.get_league_teams(league.name)
            matches = storage.get_league_matches(league.name, limit=10)
            print(f"   Teams in {league.name}: {len(teams)}")
            print(f"   Recent matches: {len(matches)}")

        print("✅ Test completed successfully!")

    except Exception as e:
        print(f"❌ Test failed: {e}")
        logger.error(f"Test failed: {e}")
        raise


async def test_live_matches():
    """Test live matches scraping"""
    print("\n🧪 Testing live matches scraping...")

    from app.api.live_scraper import LiveMatchScraper

    scraper = LiveMatchScraper()

    try:
        # Scrape live matches
        print("📡 Scraping live matches...")
        live_matches = await scraper.scrape()

        print(f"✅ Found {len(live_matches)} live matches")

        if live_matches:
            for match in live_matches[:3]:  # Show first 3
                print(f"   {match['home_team']} vs {match['away_team']} ({match['league']})")
                print(f"     Score: {match['home_score']}-{match['away_score']}")
                print(f"     Minute: {match['minute']}")

        print("✅ Live matches test completed!")

    except Exception as e:
        print(f"❌ Live matches test failed: {e}")
        logger.error(f"Live matches test failed: {e}")


async def main():
    """Main test function"""
    print("🚀 Starting League Scraper Tests")
    print("=" * 50)

    # Test Russian Premier League scraping
    await test_russian_premier_league()

    # Test live matches scraping
    await test_live_matches()

    print("\n🎉 All tests completed!")


if __name__ == "__main__":
    asyncio.run(main()) 
