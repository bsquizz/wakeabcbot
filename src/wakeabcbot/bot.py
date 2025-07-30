"""
Main Telegram bot module for Wake ABC Inventory Bot
Handles bot commands and user interactions
"""

import asyncio
import logging

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.constants import ParseMode
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from .config import Config
from .database import Database
from .inventory_scraper import WakeABCInventoryScraper
from .message_loader import message_loader

logger = logging.getLogger(__name__)


class WakeABCBot:
    """Main bot class"""

    def __init__(self):
        """Initialize the bot"""
        self.db = Database()
        self.scraper = WakeABCInventoryScraper()
        self.application = None

    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /start command"""
        user = update.effective_user

        # Add user to database
        try:
            self.db.add_user(
                user_id=user.id,
                username=user.username,
                first_name=user.first_name,
                last_name=user.last_name,
            )
        except Exception as e:
            logger.error(f"Error adding user {user.id} to database: {e}")
            await update.message.reply_text(
                "❌ Sorry, there was an error adding you to the database. Please try again later."
            )
            return

        welcome_message = message_loader.get_welcome_message(user.first_name)
        await update.message.reply_text(welcome_message, parse_mode=ParseMode.MARKDOWN)

    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /help command"""
        help_message = message_loader.get_help_message()

        await update.message.reply_text(help_message, parse_mode=ParseMode.MARKDOWN)

    async def search_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /search command"""
        if not context.args:
            await update.message.reply_text(
                "Please provide a search query.\nExample: `/search bourbon`",
                parse_mode=ParseMode.MARKDOWN,
            )
            return

        query = " ".join(context.args)
        user = update.effective_user

        logger.info(f"User {user.id} searching for: {query}")

        # Send "searching" message
        searching_msg = await update.message.reply_text(
            f"🔍 Searching for '{query}'...", parse_mode=ParseMode.MARKDOWN
        )

        # Use helper method to perform search
        items, results_message, reply_markup = await self._search_inventory_helper(
            keyword=query, max_results=10, include_watchlist_button=True
        )

        # Update the searching message with results
        parse_mode = ParseMode.MARKDOWN if not items else ParseMode.MARKDOWN_V2
        await searching_msg.edit_text(
            results_message,
            parse_mode=parse_mode,
            reply_markup=reply_markup,
        )

    async def watchlist_command(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ):
        """Handle /watchlist command"""
        user = update.effective_user

        # Use helper method to get watchlist display
        keywords, message, reply_markup, error = await self._get_watchlist_display(
            user_id=user.id, include_tips=True, include_buttons=True
        )

        if error:
            # Error occurred, message contains error text
            await update.message.reply_text(message)
            return

        await update.message.reply_text(
            message, parse_mode=ParseMode.MARKDOWN, reply_markup=reply_markup
        )

    async def _search_inventory_helper(
        self,
        keyword: str,
        max_results: int = 10,
        include_watchlist_button: bool = False,
    ):
        """
        Helper method to search inventory and format results.
        Returns tuple of (items, formatted_message, reply_markup)
        """
        try:
            items = self.scraper.search_inventory(keyword, max_results=max_results)
        except Exception as e:
            logger.error(f"Error during search for '{keyword}': {e}")
            error_message = "❌ Sorry, there was an error searching the inventory. Please try again later."
            return [], error_message, None

        if not items:
            if include_watchlist_button:
                # More detailed no-results message for search command
                message = f"❌ No items found for '{keyword}'.\n\nTry:\n• Different keywords\n• Brand names\n• General categories like 'whiskey' or 'vodka'"
            else:
                # Simple no-results message for callbacks
                message = f"❌ No items found for '{keyword}'."
            return [], message, None

        # Format results message
        if include_watchlist_button:
            # MarkdownV2 format for search command (with escaping)
            results_message = f"🔍 *Search Results for '{keyword}':*\n\n"
            display_limit = 5
            for i, item in enumerate(items[:display_limit], 1):
                results_message += (
                    f"*{i}\\.* {self.scraper.format_item_for_display(item)}\n\n"
                )

            if len(items) > display_limit:
                results_message += f"_\\.\\.\\. and {len(items) - display_limit} more result{'s' if len(items) - display_limit != 1 else ''}_\n\n"

            # Add watchlist suggestion and button
            keyboard = [
                [
                    InlineKeyboardButton(
                        f"🔔 Add '{keyword}' to Watchlist",
                        callback_data=f"add_watch:{keyword}",
                    )
                ]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            results_message += "💡 *Tip:* Add this search to your watchlist to get notified when new items become available\\!"
        else:
            # Regular Markdown format for callbacks (no escaping needed)
            results_message = f"🔍 **Search Results for '{keyword}':**\n\n"
            for i, item in enumerate(items, 1):
                results_message += (
                    f"**{i}.** {self.scraper.format_item_for_display(item)}\n\n"
                )
            reply_markup = None

        return items, results_message, reply_markup

    async def _get_watchlist_display(
        self, user_id: int, include_tips: bool = False, include_buttons: bool = False
    ):
        """
        Helper method to get watchlist and format display.
        Returns tuple of (keywords, formatted_message, reply_markup, error)
        """
        try:
            keywords = self.db.get_user_watchlist(user_id)
        except Exception as e:
            logger.error(f"Error getting watchlist for user {user_id}: {e}")
            error_message = "❌ Sorry, there was an error retrieving your watchlist. Please try again later."
            return [], error_message, None, e

        if not keywords:
            if include_tips:
                # Full empty message for watchlist command
                message = message_loader.get_watchlist_empty_message()
            else:
                # Simple empty message for callbacks
                message = "📝 **Your watchlist is empty.**"
        else:
            message = f"📝 **Your Watchlist ({len(keywords)} items):**\n\n"
            for i, keyword in enumerate(keywords, 1):
                message += f"{i}. `{keyword}`\n"

            if include_tips:
                message += f"\n{message_loader.get_watchlist_tips(Config.CHECK_INTERVAL_MINUTES)}"

        # Create buttons if requested
        reply_markup = None
        if include_buttons:
            keyboard = []
            if keywords:  # Only show "Clear All" if there are items
                keyboard.append(
                    [
                        InlineKeyboardButton(
                            "🗑️ Clear All", callback_data="clear_watchlist"
                        )
                    ]
                )

            keyboard.append(
                [InlineKeyboardButton("➕ Add Item", callback_data="show_add_help")]
            )

            reply_markup = InlineKeyboardMarkup(keyboard)

        return keywords, message, reply_markup, None

    async def _add_keyword_to_watchlist(self, user_id: int, keyword: str):
        """
        Helper method to add a keyword to watchlist and return result info.
        Returns tuple of (success, message, reply_markup)
        """
        try:
            success = self.db.add_watchlist_keyword(user_id, keyword)
        except Exception as e:
            logger.error(f"Error adding keyword '{keyword}' for user {user_id}: {e}")
            error_message = "❌ Sorry, there was an error adding the keyword. Please try again later."
            return False, error_message, None

        if success:
            message = message_loader.get_add_success_message(keyword)
            # Add quick action buttons for successful additions
            keyboard = [
                [
                    InlineKeyboardButton(
                        "📝 View Watchlist", callback_data="show_watchlist"
                    ),
                    InlineKeyboardButton(
                        f"🔍 Search '{keyword}'", callback_data=f"search:{keyword}"
                    ),
                ]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
        else:
            message = f"ℹ️ '**{keyword}**' is already in your watchlist.\n\nUse `/watchlist` to see all your watched items."
            reply_markup = None

        return success, message, reply_markup

    async def add_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /add command"""
        if not context.args:
            await update.message.reply_text(
                "Please provide a keyword to add.\nExample: `/add bourbon`",
                parse_mode=ParseMode.MARKDOWN,
            )
            return

        keyword = " ".join(context.args).strip().lower()
        user = update.effective_user

        success, message, reply_markup = await self._add_keyword_to_watchlist(
            user.id, keyword
        )

        await update.message.reply_text(
            message, parse_mode=ParseMode.MARKDOWN, reply_markup=reply_markup
        )

    async def remove_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /remove command"""
        if not context.args:
            await update.message.reply_text(
                "Please provide a keyword to remove.\nExample: `/remove bourbon`",
                parse_mode=ParseMode.MARKDOWN,
            )
            return

        keyword = " ".join(context.args).strip().lower()
        user = update.effective_user

        try:
            success = self.db.remove_watchlist_keyword(user.id, keyword)
        except Exception as e:
            logger.error(f"Error removing keyword '{keyword}' for user {user.id}: {e}")
            await update.message.reply_text(
                "❌ Sorry, there was an error removing the keyword. Please try again later."
            )
            return

        if success:
            message = message_loader.get_remove_success_message(keyword)
        else:
            message = message_loader.get_remove_not_found_message(keyword)

        await update.message.reply_text(message, parse_mode=ParseMode.MARKDOWN)

    async def clear_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /clear command to clear entire watchlist"""
        user = update.effective_user

        # First, check if user has any watchlist items
        try:
            current_keywords = self.db.get_user_watchlist(user.id)
        except Exception as e:
            logger.error(f"Error getting watchlist for user {user.id}: {e}")
            await update.message.reply_text(
                "❌ Sorry, there was an error accessing your watchlist. Please try again later."
            )
            return

        if not current_keywords:
            await update.message.reply_text(
                "📭 Your watchlist is already empty!\n\nUse `/add <keyword>` to add items to watch.",
                parse_mode=ParseMode.MARKDOWN,
            )
            return

        # Show confirmation with inline buttons
        keyboard = [
            [
                InlineKeyboardButton(
                    "✅ Yes, clear all", callback_data="confirm_clear_watchlist"
                ),
                InlineKeyboardButton(
                    "❌ Cancel", callback_data="cancel_clear_watchlist"
                ),
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        message = (
            f"⚠️ **Clear Watchlist Confirmation**\n\n"
            f"Are you sure you want to clear your entire watchlist?\n\n"
            f"This will remove **{len(current_keywords)} item{'s' if len(current_keywords) != 1 else ''}**:\n"
            f"• {', '.join(current_keywords)}\n\n"
            f"This action cannot be undone."
        )

        await update.message.reply_text(
            message, parse_mode=ParseMode.MARKDOWN, reply_markup=reply_markup
        )

    async def button_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle inline button callbacks"""
        query = update.callback_query
        await query.answer()

        user = update.effective_user
        data = query.data

        if data.startswith("add_watch:"):
            keyword = data.replace("add_watch:", "")
            success, message, reply_markup = await self._add_keyword_to_watchlist(
                user.id, keyword
            )

            # For callback queries, we edit the message instead of replying
            await query.edit_message_text(
                message, parse_mode=ParseMode.MARKDOWN, reply_markup=reply_markup
            )

        elif data.startswith("search:"):
            keyword = data.replace("search:", "")
            await query.edit_message_text(f"🔍 Searching for '{keyword}'...")

            # Use helper method to perform search
            items, results_message, reply_markup = await self._search_inventory_helper(
                keyword=keyword, max_results=5, include_watchlist_button=False
            )

            await query.edit_message_text(
                results_message,
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=reply_markup,
            )

        elif data == "show_watchlist":
            # Use helper method to get watchlist display
            keywords, message, reply_markup, error = await self._get_watchlist_display(
                user_id=user.id, include_tips=False, include_buttons=False
            )

            if error:
                # Error occurred, show error message
                await query.edit_message_text(message)
            else:
                await query.edit_message_text(message, parse_mode=ParseMode.MARKDOWN)

        elif data == "show_add_help":
            await query.edit_message_text(
                message_loader.get_add_help_message(), parse_mode=ParseMode.MARKDOWN
            )

        elif data == "clear_watchlist":
            # Check if user has any watchlist items
            try:
                current_keywords = self.db.get_user_watchlist(user.id)
            except Exception as e:
                logger.error(f"Error getting watchlist for user {user.id}: {e}")
                await query.edit_message_text(
                    "❌ Sorry, there was an error accessing your watchlist. Please try again later."
                )
                return

            if not current_keywords:
                await query.edit_message_text(
                    "📭 Your watchlist is already empty!\n\nUse `/add <keyword>` to add items to watch.",
                    parse_mode=ParseMode.MARKDOWN,
                )
                return

            # Show confirmation with inline buttons
            keyboard = [
                [
                    InlineKeyboardButton(
                        "✅ Yes, clear all", callback_data="confirm_clear_watchlist"
                    ),
                    InlineKeyboardButton(
                        "❌ Cancel", callback_data="cancel_clear_watchlist"
                    ),
                ]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)

            message = (
                f"⚠️ **Clear Watchlist Confirmation**\n\n"
                f"Are you sure you want to clear your entire watchlist?\n\n"
                f"This will remove **{len(current_keywords)} item{'s' if len(current_keywords) != 1 else ''}**:\n"
                f"• {', '.join(current_keywords)}\n\n"
                f"This action cannot be undone."
            )

            await query.edit_message_text(
                message, parse_mode=ParseMode.MARKDOWN, reply_markup=reply_markup
            )

        elif data == "confirm_clear_watchlist":
            # Actually clear the watchlist
            try:
                cleared_count = self.db.clear_user_watchlist(user.id)
            except Exception as e:
                logger.error(f"Error clearing watchlist for user {user.id}: {e}")
                await query.edit_message_text(
                    "❌ Sorry, there was an error clearing your watchlist. Please try again later."
                )
                return

            if cleared_count > 0:
                message = (
                    f"✅ **Watchlist Cleared Successfully**\n\n"
                    f"Removed **{cleared_count} item{'s' if cleared_count != 1 else ''}** from your watchlist.\n\n"
                    f"Use `/add <keyword>` to start building your watchlist again!"
                )
            else:
                message = "📭 Your watchlist was already empty!"

            await query.edit_message_text(message, parse_mode=ParseMode.MARKDOWN)

        elif data == "cancel_clear_watchlist":
            # User cancelled, show watchlist again
            keywords, message, reply_markup, error = await self._get_watchlist_display(
                user_id=user.id, include_tips=False, include_buttons=True
            )

            if error:
                await query.edit_message_text(message)
            else:
                await query.edit_message_text(
                    message, parse_mode=ParseMode.MARKDOWN, reply_markup=reply_markup
                )

    async def handle_text_message(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ):
        """Handle plain text messages"""
        text = update.message.text.strip()

        # Simple responses for common queries
        if any(word in text.lower() for word in ["help", "how", "what"]):
            await update.message.reply_text(
                "ℹ️ Type `/help` to see all available commands!",
                parse_mode=ParseMode.MARKDOWN,
            )
        else:
            # Suggest using the search command
            await update.message.reply_text(
                f"💡 Try searching for that: `/search {text}`\n\nOr type `/help` for all commands.",
                parse_mode=ParseMode.MARKDOWN,
            )

    async def error_handler(self, update: object, context: ContextTypes.DEFAULT_TYPE):
        """Handle errors"""
        logger.error(f"Exception while handling an update: {context.error}")

        # Try to send error message to user if possible
        if isinstance(update, Update) and update.effective_message:
            try:
                await update.effective_message.reply_text(
                    "❌ Sorry, something went wrong. Please try again later."
                )
            except Exception:
                pass  # If we can't send the error message, just log it

    def setup_handlers(self):
        """Set up bot command handlers"""
        app = self.application

        # Command handlers
        app.add_handler(CommandHandler("start", self.start_command))
        app.add_handler(CommandHandler("help", self.help_command))
        app.add_handler(CommandHandler("search", self.search_command))
        app.add_handler(CommandHandler("watchlist", self.watchlist_command))
        app.add_handler(CommandHandler("add", self.add_command))
        app.add_handler(CommandHandler("remove", self.remove_command))
        app.add_handler(CommandHandler("clear", self.clear_command))

        # Callback query handler for inline buttons
        app.add_handler(CallbackQueryHandler(self.button_callback))

        # Text message handler (for non-command messages)
        app.add_handler(
            MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_text_message)
        )

        # Error handler
        app.add_error_handler(self.error_handler)

    async def _run(self):
        # Validate configuration
        Config.validate_config()

        # Create application with proper timeout configuration
        self.application = (
            Application.builder()
            .token(Config.TELEGRAM_BOT_TOKEN)
            .get_updates_read_timeout(10)
            .get_updates_write_timeout(10)
            .get_updates_connect_timeout(10)
            .get_updates_pool_timeout(10)
            .build()
        )

        # Set up handlers
        self.setup_handlers()

        logger.info("Starting Wake ABC Inventory Bot...")

        # Initialize the application
        await self.application.initialize()
        await self.application.start()

        # Start polling
        await self.application.updater.start_polling(
            poll_interval=1.0,
            timeout=10,
            bootstrap_retries=-1,
        )

        logger.info("Bot is now polling for updates...")

        # Keep running until cancelled
        try:
            while True:
                await asyncio.sleep(1)
        except asyncio.CancelledError:
            logger.info("Bot polling cancelled")
            raise

    async def run_bot(self):
        """Run the bot"""
        try:
            await self._run()
        except asyncio.CancelledError:
            logger.info("Bot run cancelled")
            raise
        except Exception as e:
            logger.error(f"Error running bot: {e}")
            raise
        finally:
            # Clean shutdown
            if hasattr(self, "application") and self.application:
                try:
                    if self.application.updater.running:
                        await self.application.updater.stop()
                    await self.application.stop()
                    await self.application.shutdown()
                except Exception as e:
                    logger.error(f"Error during bot shutdown: {e}")


def main():
    """Main function"""
    bot = WakeABCBot()

    try:
        asyncio.run(bot.run_bot())
    except KeyboardInterrupt:
        logger.info("Bot stopped by user")
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        raise


if __name__ == "__main__":
    main()
