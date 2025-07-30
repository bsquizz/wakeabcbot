"""
Configuration module for Wake ABC Telegram Bot
"""

import logging
import os
import re

from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()


def _redact_sensitive_info(message):
    # Redact bot tokens from URLs
    if "api.telegram.org/bot" in message:
        # Replace the token part with [REDACTED]
        message = re.sub(r"(api\.telegram\.org/bot)[^/\s]+", r"\1[REDACTED]", message)

    # Redact any Bearer tokens or Authorization headers
    if "Authorization:" in message or "Bearer " in message:
        message = re.sub(
            r"(Authorization:\s*Bearer\s+)[^\s]+", r"\1[REDACTED]", message
        )
        message = re.sub(r"(Bearer\s+)[A-Za-z0-9:_-]+", r"\1[REDACTED]", message)

    # Redact any tokens that look like bot tokens (long alphanumeric strings)
    if len(message) > 20:  # Only check longer messages
        # Look for patterns like bot123456:ABC-DEF...
        message = re.sub(r"\b\d{8,}:[A-Za-z0-9_-]{20,}\b", "[REDACTED_TOKEN]", message)

    return message


class SensitiveInfoFilter(logging.Filter):
    """Filter to remove or redact sensitive information from logs"""

    def filter(self, record):
        # Get the formatted message - this is what actually gets logged
        try:
            message = record.getMessage()
        except Exception:
            # Fallback to record.msg if getMessage() fails
            message = str(getattr(record, "msg", ""))

        record.msg = _redact_sensitive_info(message)
        record.args = ()

        return True


class Config:
    """Configuration class for the bot"""

    # Telegram Bot Configuration
    TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

    # Database Configuration
    DATABASE_PATH = os.getenv("DATABASE_PATH", "wakeabc_bot.db")

    # Monitoring Configuration
    CHECK_INTERVAL_MINUTES = int(os.getenv("CHECK_INTERVAL_MINUTES", "30"))

    # Wake ABC Site Configuration
    WAKE_ABC_SEARCH_URL = os.getenv(
        "WAKE_ABC_SEARCH_URL", "https://wakeabc.com/search-our-inventory/"
    )

    # Logging Configuration
    LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")

    @classmethod
    def validate_config(cls):
        """Validate that required configuration is present"""
        if not cls.TELEGRAM_BOT_TOKEN:
            raise ValueError(
                "TELEGRAM_BOT_TOKEN is required. Please set it in your .env file."
            )

        return True

    @classmethod
    def setup_logging(cls):
        """
        Set up logging configuration that prevents sensitive information
        from being logged by HTTP libraries like httpx, urllib3, etc.
        """
        # Configure basic logging
        logging.basicConfig(
            format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
            level=getattr(logging, cls.LOG_LEVEL.upper()),
            handlers=[logging.StreamHandler()],
        )

        # Apply the filter to multiple loggers to catch HTTP library logs
        sensitive_filter = SensitiveInfoFilter()

        # Apply to specific HTTP libraries that might log sensitive info
        http_loggers = [
            "urllib3",
            "urllib3.connectionpool",
            "requests",
            "requests.packages.urllib3",
            "httpx",
            "aiohttp",
            "telegram",
            "telegram.ext",
            "httpcore",
        ]

        for logger_name in http_loggers:
            logger = logging.getLogger(logger_name)
            logger.addFilter(sensitive_filter)

        return True
