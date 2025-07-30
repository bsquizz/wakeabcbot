"""
Database module for Wake ABC Telegram Bot
Handles SQLite database operations for storing user watchlists and preferences
"""

import json
import logging
import sqlite3
from typing import Any, Dict, List, Optional, Tuple

from .config import Config
from .inventory_scraper import InventoryItem

logger = logging.getLogger(__name__)


class Database:
    """Database handler for the Wake ABC bot"""

    def __init__(self, db_path: str = None):
        """Initialize database connection"""
        self.db_path = db_path or Config.DATABASE_PATH
        self.init_database()

    def init_database(self):
        """Initialize database tables"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()

                # Create users table
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS users (
                        user_id INTEGER PRIMARY KEY,
                        username TEXT,
                        first_name TEXT,
                        last_name TEXT,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        is_active BOOLEAN DEFAULT 1
                    )
                """)

                # Create watchlist table
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS watchlist (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        user_id INTEGER,
                        keyword TEXT NOT NULL,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        is_active BOOLEAN DEFAULT 1,
                        FOREIGN KEY (user_id) REFERENCES users (user_id)
                    )
                """)

                # Create notifications table to track what we've already notified about
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS notifications (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        user_id INTEGER,
                        keyword TEXT,
                        product_name TEXT,
                        product_code TEXT,
                        notified_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (user_id) REFERENCES users (user_id)
                    )
                """)

                # Create item_snapshots table to track detailed item state for change detection
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS item_snapshots (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        user_id INTEGER,
                        keyword TEXT,
                        product_name TEXT,
                        product_code TEXT,
                        price TEXT,
                        availability TEXT,
                        total_stock INTEGER DEFAULT 0,
                        store_locations TEXT,
                        snapshot_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (user_id) REFERENCES users (user_id),
                        UNIQUE(user_id, keyword, product_name, product_code)
                    )
                """)

                conn.commit()
                logger.info("Database initialized successfully")
        except sqlite3.Error as e:
            logger.error(f"Database initialization error: {e}")
            raise

    def add_user(
        self,
        user_id: int,
        username: str = None,
        first_name: str = None,
        last_name: str = None,
    ):
        """Add or update a user in the database"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute(
                    """
                    INSERT OR REPLACE INTO users (user_id, username, first_name, last_name)
                    VALUES (?, ?, ?, ?)
                """,
                    (user_id, username, first_name, last_name),
                )
                conn.commit()
                logger.info(f"User {user_id} added/updated in database")
        except sqlite3.Error as e:
            logger.error(f"Error adding user {user_id}: {e}")
            raise

    def add_watchlist_keyword(self, user_id: int, keyword: str) -> bool:
        """Add a keyword to user's watchlist"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()

                # Check if keyword already exists for this user
                cursor.execute(
                    """
                    SELECT id FROM watchlist
                    WHERE user_id = ? AND LOWER(keyword) = LOWER(?) AND is_active = 1
                """,
                    (user_id, keyword),
                )

                if cursor.fetchone():
                    return False  # Keyword already exists

                # Add new keyword
                cursor.execute(
                    """
                    INSERT INTO watchlist (user_id, keyword)
                    VALUES (?, ?)
                """,
                    (user_id, keyword),
                )
                conn.commit()
                logger.info(
                    f"Added keyword '{keyword}' to watchlist for user {user_id}"
                )
                return True
        except sqlite3.Error as e:
            logger.error(f"Error adding keyword '{keyword}' for user {user_id}: {e}")
            raise

    def remove_watchlist_keyword(self, user_id: int, keyword: str) -> bool:
        """Remove a keyword from user's watchlist"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute(
                    """
                    UPDATE watchlist
                    SET is_active = 0
                    WHERE user_id = ? AND LOWER(keyword) = LOWER(?) AND is_active = 1
                """,
                    (user_id, keyword),
                )

                if cursor.rowcount > 0:
                    conn.commit()
                    logger.info(
                        f"Removed keyword '{keyword}' from watchlist for user {user_id}"
                    )
                    return True
                return False
        except sqlite3.Error as e:
            logger.error(f"Error removing keyword '{keyword}' for user {user_id}: {e}")
            raise

    def clear_user_watchlist(self, user_id: int) -> int:
        """Clear all keywords from user's watchlist. Returns number of items cleared."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute(
                    """
                    UPDATE watchlist
                    SET is_active = 0
                    WHERE user_id = ? AND is_active = 1
                """,
                    (user_id,),
                )

                cleared_count = cursor.rowcount
                if cleared_count > 0:
                    conn.commit()
                    logger.info(
                        f"Cleared {cleared_count} keywords from watchlist for user {user_id}"
                    )
                return cleared_count
        except sqlite3.Error as e:
            logger.error(f"Error clearing watchlist for user {user_id}: {e}")
            raise

    def get_user_watchlist(self, user_id: int) -> List[str]:
        """Get all active watchlist keywords for a user"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute(
                    """
                    SELECT keyword FROM watchlist
                    WHERE user_id = ? AND is_active = 1
                    ORDER BY created_at
                """,
                    (user_id,),
                )

                return [row[0] for row in cursor.fetchall()]
        except sqlite3.Error as e:
            logger.error(f"Error getting watchlist for user {user_id}: {e}")
            raise

    def get_all_watchlist_keywords(self) -> List[Tuple[int, str]]:
        """Get all active watchlist keywords from all users"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT DISTINCT user_id, keyword FROM watchlist
                    WHERE is_active = 1
                """)

                return cursor.fetchall()
        except sqlite3.Error as e:
            logger.error(f"Error getting all watchlist keywords: {e}")
            raise

    def add_notification(
        self, user_id: int, keyword: str, product_name: str, product_code: str = None
    ):
        """Record that we've notified a user about a product"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute(
                    """
                    INSERT INTO notifications (user_id, keyword, product_name, product_code)
                    VALUES (?, ?, ?, ?)
                """,
                    (user_id, keyword, product_name, product_code),
                )
                conn.commit()
                logger.info(
                    f"Recorded notification for user {user_id} about '{product_name}'"
                )
        except sqlite3.Error as e:
            logger.error(f"Error recording notification: {e}")
            raise

    def was_recently_notified(
        self, user_id: int, keyword: str, product_name: str, hours: int = 24
    ) -> bool:
        """Check if user was recently notified about this product"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute(
                    """
                    SELECT id FROM notifications
                    WHERE user_id = ? AND keyword = ? AND product_name = ?
                    AND notified_at > datetime('now', '-{} hours')
                """.format(hours),
                    (user_id, keyword, product_name),
                )

                return cursor.fetchone() is not None
        except sqlite3.Error as e:
            logger.error(f"Error checking notification history: {e}")
            raise

    def get_active_users(self) -> List[int]:
        """Get list of all active users"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT DISTINCT user_id FROM users
                    WHERE is_active = 1
                """)

                return [row[0] for row in cursor.fetchall()]
        except sqlite3.Error as e:
            logger.error(f"Error getting active users: {e}")
            raise

    def save_item_snapshot(self, user_id: int, keyword: str, item: InventoryItem):
        """Save or update an item snapshot for change detection"""
        try:
            # Calculate total stock across all locations
            total_stock = 0
            for location in item.locations:
                # Extract stock number from location string
                parts = location.split(" - ")
                if len(parts) == 2:
                    quantity_str = parts[1].lower()
                    if "in stock" in quantity_str:
                        import re

                        numbers = re.findall(r"\d+", parts[1])
                        if numbers:
                            total_stock += int(numbers[0])

            # Convert locations to JSON for storage
            store_locations = json.dumps(item.locations)

            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute(
                    """
                    INSERT OR REPLACE INTO item_snapshots
                    (user_id, keyword, product_name, product_code, price, availability, total_stock, store_locations)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                    (
                        user_id,
                        keyword,
                        item.name,
                        item.code or "",
                        item.price or "",
                        item.availability or "",
                        total_stock,
                        store_locations,
                    ),
                )
                conn.commit()
                logger.debug(f"Saved snapshot for user {user_id}: {item.name}")
        except sqlite3.Error as e:
            logger.error(f"Error saving item snapshot: {e}")
            raise

    def get_previous_item_snapshot(
        self, user_id: int, keyword: str, product_name: str, product_code: str = ""
    ) -> Optional[Dict[str, Any]]:
        """Get the previous snapshot of an item for comparison"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute(
                    """
                    SELECT product_name, product_code, price, availability, total_stock, store_locations, snapshot_at
                    FROM item_snapshots
                    WHERE user_id = ? AND keyword = ? AND product_name = ? AND product_code = ?
                """,
                    (user_id, keyword, product_name, product_code or ""),
                )

                row = cursor.fetchone()
                if row:
                    return {
                        "product_name": row[0],
                        "product_code": row[1],
                        "price": row[2],
                        "availability": row[3],
                        "total_stock": row[4],
                        "store_locations": json.loads(row[5]) if row[5] else [],
                        "snapshot_at": row[6],
                    }
                return None
        except sqlite3.Error as e:
            logger.error(f"Error getting item snapshot: {e}")
            return None

    def should_notify_about_item(
        self, user_id: int, keyword: str, current_item: InventoryItem
    ) -> Tuple[bool, List[str]]:
        """
        Determine if we should notify about an item based on changes from previous snapshot.
        Returns (should_notify, list_of_reasons)
        """
        try:
            previous = self.get_previous_item_snapshot(
                user_id, keyword, current_item.name, current_item.code or ""
            )
        except Exception as e:
            logger.error(f"Error checking notification conditions: {e}")
            return False, []

        # If no previous snapshot, this is a new item - notify if available
        if not previous:
            if (
                current_item.availability
                and "in stock" in current_item.availability.lower()
            ):
                return True, ["Item is now available"]
            return False, []

        reasons = []

        # Extract current state
        current_locations = set(current_item.locations)
        previous_locations = set(previous["store_locations"])

        # Calculate current total stock
        current_total_stock = 0
        for location in current_item.locations:
            parts = location.split(" - ")
            if len(parts) == 2:
                quantity_str = parts[1].lower()
                if "in stock" in quantity_str:
                    import re

                    numbers = re.findall(r"\d+", parts[1])
                    if numbers:
                        current_total_stock += int(numbers[0])

        # Check notification conditions

        # 1. Item is now in stock at a new store
        new_stores = current_locations - previous_locations
        if new_stores:
            reasons.append(f"Now available at {len(new_stores)} new store(s)")

        # 2. Item was completely unavailable but now is available
        was_unavailable = (
            not previous_locations or previous["availability"] != "In Stock"
        )
        is_now_available = (
            current_item.availability
            and "in stock" in current_item.availability.lower()
        )
        if was_unavailable and is_now_available:
            reasons.append("Item is now available (was previously unavailable)")

        # 3. Price has dropped
        if (
            previous["price"]
            and current_item.price
            and previous["price"] != current_item.price
        ):
            # Simple string comparison for now - could be enhanced with price parsing
            prev_price_str = previous["price"].replace("$", "").replace(",", "")
            curr_price_str = current_item.price.replace("$", "").replace(",", "")
            try:
                if (
                    prev_price_str.replace(".", "").isdigit()
                    and curr_price_str.replace(".", "").isdigit()
                ):
                    prev_price = float(prev_price_str)
                    curr_price = float(curr_price_str)
                    if curr_price < prev_price:
                        reasons.append(
                            f"Price dropped from {previous['price']} to {current_item.price}"
                        )
            except ValueError:
                pass  # Could not parse prices

        # 4. Inventory is getting very low (less than 10 items total)
        if current_total_stock > 0 and current_total_stock < 10:
            if previous["total_stock"] >= 10:
                reasons.append(
                    f"Low stock alert: Only {current_total_stock} items left"
                )

        # 5. Item becomes unavailable
        was_available = previous_locations and previous["availability"] == "In Stock"
        is_now_unavailable = not current_locations or (
            current_item.availability
            and "out of stock" in current_item.availability.lower()
        )
        if was_available and is_now_unavailable:
            reasons.append("Item is no longer available")

        return len(reasons) > 0, reasons
