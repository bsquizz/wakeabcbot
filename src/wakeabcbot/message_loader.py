"""
Message loader utility for Wake ABC Telegram Bot
Uses importlib.resources to load large text templates from the messages folder
"""

import logging
from importlib import resources

logger = logging.getLogger(__name__)


class MessageLoader:
    """Utility class for loading large message templates"""

    def __init__(self):
        """Initialize the message loader"""
        self._cache = {}

    def _load_template(self, filename: str) -> str:
        """Load a message template from file using importlib.resources"""
        if filename in self._cache:
            return self._cache[filename]

        try:
            # Load the text file from the messages package
            with resources.open_text("wakeabcbot.messages", filename) as f:
                content = f.read().strip()
                self._cache[filename] = content
                return content
        except FileNotFoundError:
            logger.error(f"Message template file not found: {filename}")
            return f"[Template {filename} not found]"
        except Exception as e:
            logger.error(f"Error loading message template {filename}: {e}")
            return f"[Error loading template {filename}]"

    def get_welcome_message(self, first_name: str) -> str:
        """Get formatted welcome message"""
        template = self._load_template("welcome.txt")
        return template.format(first_name=first_name)

    def get_help_message(self) -> str:
        """Get help message"""
        return self._load_template("help.txt")

    def get_watchlist_empty_message(self) -> str:
        """Get empty watchlist message"""
        return self._load_template("watchlist_empty.txt")

    def get_add_help_message(self) -> str:
        """Get add keyword help message"""
        return self._load_template("add_help.txt")

    def get_add_success_message(self, keyword: str) -> str:
        """Get add keyword success message"""
        template = self._load_template("add_success.txt")
        return template.format(keyword=keyword)

    def get_remove_success_message(self, keyword: str) -> str:
        """Get remove keyword success message"""
        template = self._load_template("remove_success.txt")
        return template.format(keyword=keyword)

    def get_remove_not_found_message(self, keyword: str) -> str:
        """Get remove keyword not found message"""
        template = self._load_template("remove_not_found.txt")
        return template.format(keyword=keyword)

    def get_notification_footer(self, keyword: str) -> str:
        """Get notification footer with tips"""
        template = self._load_template("notification_footer.txt")
        return template.format(keyword=keyword)

    def get_watchlist_tips(self, check_interval: int) -> str:
        """Get watchlist tips section"""
        template = self._load_template("watchlist_tips.txt")
        return template.format(check_interval=check_interval)


# Create a global instance for easy access
message_loader = MessageLoader()
