"""
Monitoring module for Wake ABC Telegram Bot
Handles periodic inventory checks and notifications for watchlist items
"""

import asyncio
import logging
from typing import Dict, List

from telegram import Bot
from telegram.constants import ParseMode

from .config import Config
from .database import Database
from .inventory_scraper import InventoryItem, WakeABCInventoryScraper
from .message_loader import message_loader
from .utils import WakeABCCityCache, escape_markdown, extract_city_and_stock

logger = logging.getLogger(__name__)


class InventoryMonitor:
    """Monitors inventory for watchlist items and sends notifications"""

    def __init__(self, bot_token: str):
        """Initialize the monitor"""
        self.bot = Bot(token=bot_token)
        self.db = Database()
        self.scraper = WakeABCInventoryScraper()
        self.is_running = False
        self.check_interval = Config.CHECK_INTERVAL_MINUTES * 60  # Convert to seconds

        # Initialize city cache
        self.city_cache = WakeABCCityCache()

    async def start_monitoring(self):
        """Start the monitoring loop"""
        if self.is_running:
            logger.warning("Monitor is already running")
            return

        self.is_running = True
        logger.info(
            f"Starting inventory monitoring (checking every {Config.CHECK_INTERVAL_MINUTES} minutes)"
        )

        try:
            while self.is_running:
                await self._check_watchlist_items()

                # Wait for the next check
                if self.is_running:
                    # Check again in case we were stopped during the check
                    await asyncio.sleep(self.check_interval)

        except Exception as e:
            logger.error(f"Error in monitoring loop: {e}")
            self.is_running = False
            raise

    def stop_monitoring(self):
        """Stop the monitoring loop"""
        logger.info("Stopping inventory monitoring")
        self.is_running = False

    async def _check_watchlist_items(self):
        """Check all watchlist items for availability"""
        logger.info("Starting watchlist check")

        # Get all watchlist keywords from all users
        try:
            watchlist_items = self.db.get_all_watchlist_keywords()
        except Exception as e:
            logger.error(f"Error getting watchlist items: {e}")
            return

        if not watchlist_items:
            logger.info("No watchlist items to check")
            return

        logger.info(f"Checking {len(watchlist_items)} watchlist items")

        # Group by keyword to avoid duplicate searches
        keyword_to_users = {}
        for user_id, keyword in watchlist_items:
            if keyword not in keyword_to_users:
                keyword_to_users[keyword] = []
            keyword_to_users[keyword].append(user_id)

        # Check each unique keyword
        for keyword, user_ids in keyword_to_users.items():
            try:
                await self._check_keyword_for_users(keyword, user_ids)

                # Small delay between searches to be respectful to the server
                await asyncio.sleep(2)

            except Exception as e:
                logger.error(f"Error checking keyword '{keyword}': {e}")
                continue

        logger.info("Completed watchlist check")

    async def _check_keyword_for_users(self, keyword: str, user_ids: List[int]):
        """Check a keyword and notify relevant users if items are found"""
        logger.debug(f"Checking keyword '{keyword}' for {len(user_ids)} users")

        # Search for available items matching the keyword
        try:
            available_items = self.scraper.check_keyword_availability(keyword)
        except Exception as e:
            logger.error(f"Error checking keyword '{keyword}': {e}")
            return

        if not available_items:
            logger.debug(f"No available items found for keyword '{keyword}'")
            return

        logger.info(
            f"Found {len(available_items)} available items for keyword '{keyword}'"
        )

        # Notify each user who has this keyword in their watchlist
        for user_id in user_ids:
            try:
                await self._notify_user_about_items(user_id, keyword, available_items)
            except Exception as e:
                logger.error(f"Error notifying user {user_id} about '{keyword}': {e}")
                continue

    async def _notify_user_about_items(
        self, user_id: int, keyword: str, items: List[InventoryItem]
    ):
        """Notify a specific user about available items based on changes from previous snapshots"""
        # Check each item for significant changes
        items_to_notify = []
        notification_reasons = []

        for item in items:
            should_notify, reasons = self.db.should_notify_about_item(
                user_id, keyword, item
            )
            if should_notify:
                items_to_notify.append(item)
                notification_reasons.append(reasons)

            # Save the current snapshot for future comparison
            self.db.save_item_snapshot(user_id, keyword, item)

        if not items_to_notify:
            logger.debug(
                f"No items with significant changes to notify user {user_id} about for keyword '{keyword}'"
            )
            return

        logger.info(
            f"Notifying user {user_id} about {len(items_to_notify)} changed items for keyword '{keyword}'"
        )

        # Create notification message with change reasons
        message = self._create_change_notification_message(
            keyword, items_to_notify, notification_reasons
        )

        # Send notification to user
        await self.bot.send_message(
            chat_id=user_id, text=message, parse_mode=ParseMode.MARKDOWN_V2
        )

        # Record notifications in database
        for item in items_to_notify:
            self.db.add_notification(user_id, keyword, item.name, item.code)

        logger.info(
            f"Successfully notified user {user_id} about '{keyword}' item changes"
        )

    def _create_notification_message(
        self, keyword: str, items: List[InventoryItem]
    ) -> str:
        """Create a formatted notification message"""

        keyword_escaped = escape_markdown(keyword)

        if len(items) == 1:
            header = f"🔔 *New Item Available\\!*\n\nYour watchlist keyword '*{keyword_escaped}*' has a match:\n\n"
        else:
            header = f"🔔 *New Items Available\\!*\n\nYour watchlist keyword '*{keyword_escaped}*' has {len(items)} matches:\n\n"

        message = header

        for i, item in enumerate(
            items[:5], 1
        ):  # Limit to 5 items to avoid message length issues
            formatted_item = self._format_item_for_notification(item)
            message += f"*{i}\\.* {formatted_item}\n\n"

        if len(items) > 5:
            message += f"_\\.\\.\\. and {len(items) - 5} more item{'s' if len(items) - 5 != 1 else ''}_\n\n"

        # Add footer with helpful information
        message += message_loader.get_notification_footer(keyword_escaped)

        return message

    def _create_change_notification_message(
        self, keyword: str, items: List[InventoryItem], reasons_list: List[List[str]]
    ) -> str:
        """Create a notification message for items with change reasons"""
        from .utils import escape_markdown

        keyword_escaped = escape_markdown(keyword)

        if len(items) == 1:
            header = f"🔔 *Item Update\\!*\n\nYour watchlist keyword '*{keyword_escaped}*' has changes:\n\n"
        else:
            header = f"🔔 *Item Updates\\!*\n\nYour watchlist keyword '*{keyword_escaped}*' has {len(items)} items with changes:\n\n"

        message = header

        for i, (item, reasons) in enumerate(
            zip(items[:5], reasons_list[:5]), 1
        ):  # Limit to 5 items to avoid message length issues
            formatted_item = self._format_item_for_notification(item)

            # Add the change reasons
            reasons_text = ""
            if reasons:
                escaped_reasons = [escape_markdown(reason) for reason in reasons]
                reasons_text = f"\n📌 *Changes:* {', '.join(escaped_reasons)}"

            message += f"*{i}\\.* {formatted_item}{reasons_text}\n\n"

        if len(items) > 5:
            message += f"_\\.\\.\\. and {len(items) - 5} more item{'s' if len(items) - 5 != 1 else ''}_\n\n"

        # Add footer with helpful information
        message += message_loader.get_notification_footer(keyword_escaped)

        return message

    def _format_item_for_notification(self, item: InventoryItem) -> str:
        """Format an item for notification (more compact than search results)"""
        lines = []

        # Add basic item information
        lines.extend(self._format_notification_basic_info(item))

        # Add location information (compact version for notifications)
        lines.extend(self._format_notification_locations(item))

        return "\n".join(lines)

    def _format_notification_basic_info(self, item: InventoryItem) -> List[str]:
        """Format basic item information for notifications"""
        lines = []

        name = escape_markdown(item.name)
        lines.append(f"🍾 *{name}*")

        details = []
        if item.size:
            size = escape_markdown(item.size)
            details.append(f"📏 {size}")
        if item.price:
            price = escape_markdown(item.price)
            details.append(f"💰 {price}")

        if details:
            lines.append(" • ".join(details))

        return lines

    def _format_notification_locations(self, item: InventoryItem) -> List[str]:
        """Format location information for notifications"""
        lines = []

        if not item.locations:
            return lines

        if len(item.locations) == 1:
            lines.extend(self._format_notification_single_location(item.locations[0]))
        else:
            city_groups = self._group_notification_locations_by_city(item.locations)
            if city_groups:
                lines.extend(
                    self._format_notification_multiple_locations(
                        city_groups, item.locations
                    )
                )

        return lines

    def _format_notification_single_location(self, location: str) -> List[str]:
        """Format a single location for notifications"""
        lines = []

        city, stock_num, formatted_location = extract_city_and_stock(location)
        if city:
            formatted_location = escape_markdown(formatted_location)
            lines.append(f"📍 {formatted_location}")
        else:
            location_escaped = escape_markdown(location)
            lines.append(f"📍 {location_escaped}")

        return lines

    def _group_notification_locations_by_city(self, locations: List[str]) -> dict:
        """Group locations by city for notifications"""
        city_groups = {}

        for location in locations:
            city, stock_num, formatted_location = extract_city_and_stock(location)
            if city:
                if city not in city_groups:
                    city_groups[city] = []
                city_groups[city].append((stock_num, formatted_location))

        return city_groups

    def _format_notification_multiple_locations(
        self, city_groups: dict, all_locations: List[str]
    ) -> List[str]:
        """Format multiple locations for notifications with city grouping"""
        lines = []

        # Sort cities by total stock and show top 2 cities for notifications
        city_totals = {
            city: sum(stock for stock, _ in stores)
            for city, stores in city_groups.items()
        }
        sorted_cities = sorted(
            city_groups.keys(), key=lambda c: city_totals[c], reverse=True
        )

        if len(sorted_cities) == 1:
            lines.extend(
                self._format_notification_single_city(
                    sorted_cities[0], city_groups, all_locations
                )
            )
        else:
            lines.extend(
                self._format_notification_multiple_cities(sorted_cities, city_groups)
            )

        return lines

    def _format_notification_single_city(
        self, city: str, city_groups: dict, all_locations: List[str]
    ) -> List[str]:
        """Format notification for items available in a single city"""
        lines = []

        stores = city_groups[city]
        stores.sort(key=lambda x: x[0], reverse=True)
        top_store = stores[0][1]
        remaining = len(all_locations) - 1

        store_escaped = escape_markdown(top_store)
        if remaining > 0:
            lines.append(f"📍 {store_escaped} \\(\\+{remaining} more\\)")
        else:
            lines.append(f"📍 {store_escaped}")

        return lines

    def _format_notification_multiple_cities(
        self, sorted_cities: List[str], city_groups: dict
    ) -> List[str]:
        """Format notification for items available in multiple cities"""
        lines = ["📍 Available in:"]

        # Show top 2 cities with their best store
        for i, city in enumerate(sorted_cities[:2]):
            stores = city_groups[city]
            stores.sort(key=lambda x: x[0], reverse=True)
            top_store = stores[0][1]

            city_escaped = escape_markdown(city)
            store_escaped = escape_markdown(top_store)
            lines.append(f"  *• {city_escaped}*: {store_escaped}")

        # Show remaining cities if any
        if len(sorted_cities) > 2:
            remaining_cities = len(sorted_cities) - 2
            total_remaining = sum(len(city_groups[city]) for city in sorted_cities[2:])
            lines.append(
                f"  _\\.\\.\\. and {remaining_cities} more cit{'ies' if remaining_cities != 1 else 'y'} \\({total_remaining} stores\\)_"
            )

        return lines

    async def send_test_notification(self, user_id: int):
        """Send a test notification to verify the system is working"""
        try:
            test_item = InventoryItem(
                name="Test Notification Item",
                code="TEST001",
                size="750ml",
                price="$25.99",
                availability="Available",
                locations=["Test Store"],
            )

            message = self._create_notification_message("test", [test_item])
            message = f"🧪 *Test Notification*\n\n{message}"

            await self.bot.send_message(
                chat_id=user_id, text=message, parse_mode=ParseMode.MARKDOWN_V2
            )

            logger.info(f"Sent test notification to user {user_id}")
            return True

        except Exception as e:
            logger.error(f"Error sending test notification to user {user_id}: {e}")
            return False

    async def get_monitoring_status(self) -> Dict:
        """Get current monitoring status"""
        try:
            watchlist_items = self.db.get_all_watchlist_keywords()
            active_users = self.db.get_active_users()

            # Group watchlist items by keyword
            unique_keywords = set(keyword for _, keyword in watchlist_items)

            return {
                "is_running": self.is_running,
                "check_interval_minutes": Config.CHECK_INTERVAL_MINUTES,
                "total_watchlist_items": len(watchlist_items),
                "unique_keywords": len(unique_keywords),
                "active_users": len(active_users),
                "keywords": list(unique_keywords),
            }

        except Exception as e:
            logger.error(f"Error getting monitoring status: {e}")
            return {"is_running": self.is_running, "error": str(e)}


class MonitoringService:
    """Service for monitoring inventory and sending notifications"""

    def __init__(self, bot_token: str):
        """Initialize the monitoring service"""
        self.monitor = InventoryMonitor(bot_token)
        self.monitor_task = None

    async def start(self):
        """Start the monitoring service"""
        if self.monitor_task and not self.monitor_task.done():
            logger.warning("Monitoring service is already running")
            return

        logger.info("Starting monitoring service")
        self.monitor_task = asyncio.create_task(self.monitor.start_monitoring())

    async def stop(self):
        """Stop the monitoring service"""
        logger.info("Stopping monitoring service")

        if self.monitor:
            self.monitor.stop_monitoring()

        if self.monitor_task and not self.monitor_task.done():
            self.monitor_task.cancel()
            try:
                await self.monitor_task
            except asyncio.CancelledError:
                pass

    async def get_status(self) -> Dict:
        """Get monitoring service status"""
        if self.monitor:
            return await self.monitor.get_monitoring_status()
        return {"error": "Monitor not initialized"}

    async def send_test_notification(self, user_id: int) -> bool:
        """Send a test notification"""
        if self.monitor:
            return await self.monitor.send_test_notification(user_id)
        return False


async def main():
    """Main function for running the monitor standalone"""
    try:
        # Validate configuration
        Config.validate_config()

        # Create and start monitoring service
        service = MonitoringService(Config.TELEGRAM_BOT_TOKEN)

        logger.info("Starting Wake ABC Inventory Monitor...")
        await service.start()

        # Keep running until interrupted
        try:
            while True:
                await asyncio.sleep(60)  # Check every minute if we should keep running

                status = await service.get_status()
                if not status.get("is_running", False):
                    logger.error("Monitor stopped unexpectedly")
                    break

        except KeyboardInterrupt:
            logger.info("Monitor stopped by user")
        finally:
            await service.stop()

    except Exception as e:
        logger.error(f"Fatal error in monitor: {e}")
        raise


if __name__ == "__main__":
    # Set up secure logging for standalone execution
    Config.setup_logging()

    asyncio.run(main())
