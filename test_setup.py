#!/usr/bin/env python3
"""
Test script to verify Wake ABC Telegram Bot setup
"""

import asyncio
import os
import sys
from pathlib import Path


def test_python_version():
    """Test if Python version is 3.12 or higher"""
    print("🐍 Testing Python version...")
    version = sys.version_info
    if version.major == 3 and version.minor >= 12:
        print(f"✅ Python {version.major}.{version.minor}.{version.micro} - OK")
        return True
    else:
        print(f"❌ Python {version.major}.{version.minor}.{version.micro} - Need 3.12+")
        return False


def test_dependencies():
    """Test if all required dependencies are installed"""
    print("\n📦 Testing dependencies...")
    required_modules = [
        "telegram",
        "requests",
        "bs4",
        "lxml",
        "schedule",
        "dotenv",
        "aiohttp",
    ]

    all_ok = True
    for module in required_modules:
        try:
            __import__(module)
            print(f"✅ {module} - OK")
        except ImportError:
            print(f"❌ {module} - Missing")
            all_ok = False

    return all_ok


def test_config_file():
    """Test if configuration file exists"""
    print("\n⚙️  Testing configuration...")
    env_file = Path(".env")

    if not env_file.exists():
        print("❌ .env file not found")
        print("   Please copy env.example to .env and configure it")
        return False

    print("✅ .env file found")

    # Test if bot token is configured
    from dotenv import load_dotenv

    load_dotenv()

    bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not bot_token or bot_token == "your_bot_token_here":
        print("❌ TELEGRAM_BOT_TOKEN not configured")
        print("   Please set your bot token in .env file")
        return False

    print("✅ Bot token configured")
    return True


async def test_bot_connection():
    """Test if bot can connect to Telegram"""
    print("\n🤖 Testing bot connection...")

    try:
        from telegram import Bot

        from wakeabcbot.config import Config

        if (
            not Config.TELEGRAM_BOT_TOKEN
            or Config.TELEGRAM_BOT_TOKEN == "your_bot_token_here"
        ):
            print("❌ Bot token not configured")
            return False

        bot = Bot(token=Config.TELEGRAM_BOT_TOKEN)
        me = await bot.get_me()
        print(f"✅ Connected to bot: @{me.username} ({me.first_name})")
        return True

    except Exception as e:
        print(f"❌ Bot connection failed: {e}")
        return False


def test_scraper():
    """Test if inventory scraper works"""
    print("\n🔍 Testing inventory scraper...")

    try:
        from wakeabcbot.inventory_scraper import WakeABCInventoryScraper

        scraper = WakeABCInventoryScraper()
        print("✅ Scraper initialized")

        # Try a simple search
        results = scraper.search_inventory("whiskey", max_results=1)
        if results:
            print(f"✅ Search test successful - found {len(results)} result(s)")
        else:
            print("⚠️  Search returned no results (may be normal)")

        return True

    except Exception as e:
        print(f"❌ Scraper test failed: {e}")
        return False


def test_database():
    """Test if database operations work"""
    print("\n🗄️  Testing database...")

    try:
        from wakeabcbot.database import Database

        db = Database(":memory:")  # Use in-memory database for testing

        # Test basic operations
        db.add_user(12345, "testuser")
        db.add_watchlist_keyword(12345, "test")
        keywords = db.get_user_watchlist(12345)

        if "test" in keywords:
            print("✅ Database operations working")
            return True
        else:
            print("❌ Database test failed")
            return False

    except Exception as e:
        print(f"❌ Database test failed: {e}")
        return False


async def main():
    """Run all tests"""
    print("🧪 Wake ABC Telegram Bot - Setup Test\n")

    tests = [
        ("Python Version", test_python_version),
        ("Dependencies", test_dependencies),
        ("Configuration", test_config_file),
        ("Database", test_database),
        ("Scraper", test_scraper),
        ("Bot Connection", test_bot_connection),
    ]

    results = []
    for test_name, test_func in tests:
        try:
            if asyncio.iscoroutinefunction(test_func):
                result = await test_func()
            else:
                result = test_func()
            results.append((test_name, result))
        except Exception as e:
            print(f"❌ {test_name} test crashed: {e}")
            results.append((test_name, False))

    print("\n" + "=" * 50)
    print("📊 Test Results Summary:")
    print("=" * 50)

    all_passed = True
    for test_name, passed in results:
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{status} - {test_name}")
        if not passed:
            all_passed = False

    print("=" * 50)
    if all_passed:
        print("🎉 All tests passed! Your bot is ready to run.")
        print("   Start it with: python3 main.py or ./run.sh")
    else:
        print("⚠️  Some tests failed. Please fix the issues above.")
        print("   Check the README.md for setup instructions.")

    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
