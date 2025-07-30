#!/usr/bin/env python3
"""
Test script for the notification system.
Sends a test notification to verify the bot is working correctly.
"""

import asyncio
import logging
import sys

from src.wakeabcbot.config import Config
from src.wakeabcbot.monitor import MonitoringService

logger = logging.getLogger(__name__)


async def test_notification():
    """Test the notification system by sending a test notification"""
    try:
        # Set up secure logging and validate configuration
        Config.setup_logging()
        Config.validate_config()

        # Get user ID from command line argument or use a placeholder
        if len(sys.argv) > 1:
            try:
                user_id = int(sys.argv[1])
            except ValueError:
                logger.error("Invalid user ID. Please provide a numeric user ID.")
                print("Usage: python test_notification.py <USER_ID>")
                return False
        else:
            logger.error("Please provide a user ID as a command line argument.")
            print("Usage: python test_notification.py <USER_ID>")
            print("Example: python test_notification.py 123456789")
            return False

        logger.info(f"Testing notification system for user ID: {user_id}")

        # Create monitoring service instance
        service = MonitoringService(Config.TELEGRAM_BOT_TOKEN)

        # Send test notification
        await service.send_test_notification(user_id)

        logger.info("✅ Test notification sent successfully!")
        return True

    except ValueError as e:
        logger.error(f"Configuration error: {e}")
        logger.error("Please make sure your .env file contains TELEGRAM_BOT_TOKEN")
        return False
    except Exception as e:
        logger.error(f"Error sending test notification: {e}")
        return False


def main():
    """Main function"""
    print("🧪 Wake ABC Bot - Notification Test")
    print("=" * 40)

    try:
        result = asyncio.run(test_notification())
        if result:
            print("\n✅ Test completed successfully!")
        else:
            print("\n❌ Test failed!")
            sys.exit(1)
    except KeyboardInterrupt:
        print("\n👋 Test interrupted by user")
        sys.exit(0)
    except Exception as e:
        logger.error(f"Test failed with error: {e}")
        print(f"\n❌ Test failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
