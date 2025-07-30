"""
Main entry point for Wake ABC Telegram Bot
Runs both the bot and monitoring service together
"""

import asyncio
import logging
import signal
import sys

from .bot import WakeABCBot
from .config import Config
from .monitor import MonitoringService

logger = logging.getLogger(__name__)


class WakeABCBotApp:
    """Main application that manages both bot and monitoring services"""

    def __init__(self):
        """Initialize the application"""
        self.bot = None
        self.monitoring_service = None
        self.bot_task = None
        self.monitor_task = None
        self.shutdown_event = asyncio.Event()
        self.running = False

    async def _start_app(self):
        # Validate configuration
        Config.validate_config()

        logger.info("Starting Wake ABC Inventory Bot Application...")

        # Initialize services
        self.bot = WakeABCBot()
        self.monitoring_service = MonitoringService(Config.TELEGRAM_BOT_TOKEN)

        # Start monitoring service first
        logger.info("Starting monitoring service...")
        await self.monitoring_service.start()

        # Start bot service in a task so it can be cancelled
        logger.info("Starting bot service...")
        self.bot_task = asyncio.create_task(self.bot.run_bot())

        logger.info("🚀 Wake ABC Inventory Bot is now running!")
        logger.info("✅ Bot is ready to receive commands")
        logger.info(
            f"⏰ Monitoring inventory every {Config.CHECK_INTERVAL_MINUTES} minutes"
        )
        logger.info("Press Ctrl+C to stop")

        self.running = True

        # Wait for shutdown signal or bot task completion
        done, pending = await asyncio.wait(
            [self.bot_task, asyncio.create_task(self.shutdown_event.wait())],
            return_when=asyncio.FIRST_COMPLETED,
        )

        # Cancel any pending tasks
        for task in pending:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass

    async def start(self):
        """Start both bot and monitoring services"""
        try:
            await self._start_app()
        except Exception as e:
            logger.error(f"Error starting application: {e}")
            raise
        finally:
            await self.stop()

    async def stop(self):
        """Stop both services gracefully"""
        if not self.running:
            return

        logger.info("Shutting down Wake ABC Inventory Bot...")
        self.running = False

        # Signal shutdown
        self.shutdown_event.set()

        # Stop bot service
        if self.bot_task and not self.bot_task.done():
            logger.info("Stopping bot service...")
            self.bot_task.cancel()
            try:
                await asyncio.wait_for(self.bot_task, timeout=5.0)
            except (asyncio.CancelledError, asyncio.TimeoutError):
                logger.info("Bot service stopped")

        # Stop monitoring service
        if self.monitoring_service:
            logger.info("Stopping monitoring service...")
            try:
                await asyncio.wait_for(self.monitoring_service.stop(), timeout=5.0)
            except asyncio.TimeoutError:
                logger.warning("Monitoring service stop timed out")

        logger.info("✅ Application stopped successfully")

    def setup_signal_handlers(self):
        """Setup signal handlers for graceful shutdown"""

        def signal_handler(signum, frame):
            logger.info(f"Received shutdown signal ({signum})")
            if self.running:
                # Set the shutdown event
                asyncio.create_task(self._trigger_shutdown())

        async def _trigger_shutdown():
            """Trigger shutdown in async context"""
            self.shutdown_event.set()

        self._trigger_shutdown = _trigger_shutdown

        # Handle SIGINT (Ctrl+C) and SIGTERM
        for sig in (signal.SIGINT, signal.SIGTERM):
            try:
                signal.signal(sig, signal_handler)
            except ValueError:
                # Some signals may not be available on all platforms
                pass


async def main():
    """Main function"""
    Config.setup_logging()

    # Create and run application
    app = WakeABCBotApp()

    try:
        # Setup signal handlers
        app.setup_signal_handlers()

        # Start the application
        await app.start()

    except KeyboardInterrupt:
        logger.info("Application interrupted by user")
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        raise
    finally:
        # Ensure cleanup
        await app.stop()


if __name__ == "__main__":
    # Run the application
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n👋 Wake ABC Bot stopped by user")
    except Exception as e:
        logger.error(f"Application failed: {e}")
        sys.exit(1)
    else:
        print("👋 Wake ABC Bot stopped gracefully")
