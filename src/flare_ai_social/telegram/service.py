import time
from typing import Any, cast
from web3 import AsyncHTTPProvider, AsyncWeb3
import feedparser
from datetime import datetime
from summarizer import Summarizer
from dune_client.types import QueryParameter
from dune_client.client import DuneClient
from dune_client.query import QueryBase
import datetime
import time
import structlog
import dotenv
from telegram import Bot, Chat, Message, MessageEntity, Update, User , InlineKeyboardButton, InlineKeyboardMarkup
from telegram.error import TelegramError
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
    CallbackQueryHandler
)

from flare_ai_social.ai import BaseAIProvider

logger = structlog.get_logger(__name__)
dotenv.load_dotenv(".env")

ERR_API_TOKEN_NOT_PROVIDED = "Telegram API token not provided."
ERR_BOT_NOT_INITIALIZED = "Bot not initialized."
ERR_UPDATER_NOT_INITIALIZED = "Updater was not initialized"
NITTER_RSS_URL = "https://nitter.net/FlareNetworks/rss"  # Nitter RSS feed for @FlareNetworks
CHECK_INTERVAL = 300
FTSOV2_ADDRESS = "0x3d893C53D9e8056135C26C8c638B76C8b60Df726"
RPC_URL = "https://coston2-api.flare.network/ext/C/rpc"
# ABI for FtsoV2
ABI = '[{"inputs":[{"internalType":"address","name":"_addressUpdater","type":"address"}],"stateMutability":"nonpayable","type":"constructor"},{"inputs":[],"name":"FTSO_PROTOCOL_ID","outputs":[{"internalType":"uint256","name":"","type":"uint256"}],"stateMutability":"view","type":"function"},{"inputs":[],"name":"fastUpdater","outputs":[{"internalType":"contract IFastUpdater","name":"","type":"address"}],"stateMutability":"view","type":"function"},{"inputs":[],"name":"fastUpdatesConfiguration","outputs":[{"internalType":"contract IFastUpdatesConfiguration","name":"","type":"address"}],"stateMutability":"view","type":"function"},{"inputs":[],"name":"getAddressUpdater","outputs":[{"internalType":"address","name":"_addressUpdater","type":"address"}],"stateMutability":"view","type":"function"},{"inputs":[{"internalType":"bytes21","name":"_feedId","type":"bytes21"}],"name":"getFeedById","outputs":[{"internalType":"uint256","name":"","type":"uint256"},{"internalType":"int8","name":"","type":"int8"},{"internalType":"uint64","name":"","type":"uint64"}],"stateMutability":"payable","type":"function"},{"inputs":[{"internalType":"bytes21","name":"_feedId","type":"bytes21"}],"name":"getFeedByIdInWei","outputs":[{"internalType":"uint256","name":"_value","type":"uint256"},{"internalType":"uint64","name":"_timestamp","type":"uint64"}],"stateMutability":"payable","type":"function"},{"inputs":[{"internalType":"uint256","name":"_index","type":"uint256"}],"name":"getFeedByIndex","outputs":[{"internalType":"uint256","name":"","type":"uint256"},{"internalType":"int8","name":"","type":"int8"},{"internalType":"uint64","name":"","type":"uint64"}],"stateMutability":"payable","type":"function"},{"inputs":[{"internalType":"uint256","name":"_index","type":"uint256"}],"name":"getFeedByIndexInWei","outputs":[{"internalType":"uint256","name":"_value","type":"uint256"},{"internalType":"uint64","name":"_timestamp","type":"uint64"}],"stateMutability":"payable","type":"function"},{"inputs":[{"internalType":"uint256","name":"_index","type":"uint256"}],"name":"getFeedId","outputs":[{"internalType":"bytes21","name":"","type":"bytes21"}],"stateMutability":"view","type":"function"},{"inputs":[{"internalType":"bytes21","name":"_feedId","type":"bytes21"}],"name":"getFeedIndex","outputs":[{"internalType":"uint256","name":"","type":"uint256"}],"stateMutability":"view","type":"function"},{"inputs":[{"internalType":"bytes21[]","name":"_feedIds","type":"bytes21[]"}],"name":"getFeedsById","outputs":[{"internalType":"uint256[]","name":"","type":"uint256[]"},{"internalType":"int8[]","name":"","type":"int8[]"},{"internalType":"uint64","name":"","type":"uint64"}],"stateMutability":"payable","type":"function"},{"inputs":[{"internalType":"bytes21[]","name":"_feedIds","type":"bytes21[]"}],"name":"getFeedsByIdInWei","outputs":[{"internalType":"uint256[]","name":"_values","type":"uint256[]"},{"internalType":"uint64","name":"_timestamp","type":"uint64"}],"stateMutability":"payable","type":"function"},{"inputs":[{"internalType":"uint256[]","name":"_indices","type":"uint256[]"}],"name":"getFeedsByIndex","outputs":[{"internalType":"uint256[]","name":"","type":"uint256[]"},{"internalType":"int8[]","name":"","type":"int8[]"},{"internalType":"uint64","name":"","type":"uint64"}],"stateMutability":"payable","type":"function"},{"inputs":[{"internalType":"uint256[]","name":"_indices","type":"uint256[]"}],"name":"getFeedsByIndexInWei","outputs":[{"internalType":"uint256[]","name":"_values","type":"uint256[]"},{"internalType":"uint64","name":"_timestamp","type":"uint64"}],"stateMutability":"payable","type":"function"},{"inputs":[],"name":"relay","outputs":[{"internalType":"contract IRelay","name":"","type":"address"}],"stateMutability":"view","type":"function"},{"inputs":[{"internalType":"bytes32[]","name":"_contractNameHashes","type":"bytes32[]"},{"internalType":"address[]","name":"_contractAddresses","type":"address[]"}],"name":"updateContractAddresses","outputs":[],"stateMutability":"nonpayable","type":"function"},{"inputs":[{"components":[{"internalType":"bytes32[]","name":"proof","type":"bytes32[]"},{"components":[{"internalType":"uint32","name":"votingRoundId","type":"uint32"},{"internalType":"bytes21","name":"id","type":"bytes21"},{"internalType":"int32","name":"value","type":"int32"},{"internalType":"uint16","name":"turnoutBIPS","type":"uint16"},{"internalType":"int8","name":"decimals","type":"int8"}],"internalType":"struct FtsoV2Interface.FeedData","name":"body","type":"tuple"}],"internalType":"struct FtsoV2Interface.FeedDataWithProof","name":"_feedData","type":"tuple"}],"name":"verifyFeedData","outputs":[{"internalType":"bool","name":"","type":"bool"}],"stateMutability":"view","type":"function"}]'  # noqa: E501


class TelegramBot:
    def __init__(
        self,
        ai_provider: BaseAIProvider,
        api_token: str,
        allowed_user_ids: list[int] | None = None,
        polling_interval: int = 5,
    ) -> None:
        """
        Initialize the Telegram bot.

        Args:
            ai_provider: The AI provider to use for generating responses.
            api_token: Telegram Bot API token.
            allowed_user_ids: Optional list of allowed Telegram user.
                              If empty or None, all users are allowed.
            polling_interval: Time between update checks in seconds.
            monitor_channels: List of channel usernames to monitor (e.g., ["flarenetworks"])
            monitor_data_file: File path to store monitored messages
        """
        self.ai_provider = ai_provider
        self.api_token = api_token
        self.allowed_user_ids = (
            allowed_user_ids or []
        )  # Empty list means no restrictions
        self.polling_interval = polling_interval
        self.application: Application | None = None
        self.me: User | None = None  # Will store bot's own information
        self.active_monitor_chats = set() 
        self.last_post_id = ""


        # Track last processed update time for each chat
        self.last_processed_time: dict[int, float] = {}

        if not self.api_token:
            raise ValueError(ERR_API_TOKEN_NOT_PROVIDED)

        if self.allowed_user_ids:
            logger.info(
                "TelegramBot initialized with access restrictions",
                allowed_users_count=len(self.allowed_user_ids),
                polling_interval=polling_interval,
            )
        else:
            logger.info(
                "TelegramBot initialized without access restrictions (public bot)",
                polling_interval=polling_interval,
            )


    def _is_user_allowed(self, user_id: int) -> bool:
        """
        Check if a user is allowed to use the bot.

        Args:
            user_id: The Telegram user ID to check.

        Returns:
            True if the user is allowed, False otherwise.
        """
        if not self.allowed_user_ids:
            return True
        return user_id in self.allowed_user_ids

    def _safe_dict(self, obj: object | None) -> dict[str, Any] | str | None:
        """Convert an object to a dictionary, handling None values."""
        if obj is None:
            return None
        if hasattr(obj, "to_dict"):
            return obj.to_dict()  # type: ignore[union-attr]
        return str(obj)

    def _dump_update(self, update: Update) -> dict[str, Any]:
        """Convert update to a dictionary for debugging."""
        if not update:
            return {"error": "Update is None"}
        try:
            result: dict[str, Any] = {}
            if update.message:
                message: Message = update.message
                result["message"] = {
                    "message_id": message.message_id,
                    "from_user": self._safe_dict(message.from_user),
                    "chat": self._safe_dict(message.chat),
                    "date": str(message.date),
                    "text": message.text,
                    "has_entities": bool(message.entities),
                }
                if message.entities:
                    # Cast result["message"] to dict[str, Any] for type safety
                    msg_dict = cast(dict[str, Any], result["message"])
                    msg_dict["entities"] = [
                        {
                            "type": e.type,
                            "offset": e.offset,
                            "length": e.length,
                            "text": (
                                message.text[e.offset : e.offset + e.length]
                                if message.text
                                else None
                            ),
                        }
                        for e in message.entities
                    ]
                if message.reply_to_message:
                    reply: Message = message.reply_to_message
                    result["message"]["reply_to_message"] = {
                        "message_id": reply.message_id,
                        "from_user": self._safe_dict(reply.from_user),
                        "text": reply.text,
                    }
                return result
            return result
        except Exception as e:
            logger.exception("Error dumping update")
            return {"error": str(e)}
        else:
            return {"error": "Update is None"}
    
    def fetch_latest_posts(self):
        try:
            feed = feedparser.parse(NITTER_RSS_URL)
            if feed.entries:
                return feed.entries[0]
        except Exception as e:
            logger.error(f"Error fetching RSS feed: {e}")
            return None

    async def catch_all(
        self, update: Update, _context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        """Catch-all handler to log any received updates."""
        try:
            logger.warning(
                "Catch all received updates",
                update_type=str(type(update)),
                has_message=(update.message is not None),
                chat_type=(
                    update.effective_chat.type if update.effective_chat else None
                ),
                message_text=(update.message.text if update.message else None),
            )
        except Exception:
            logger.exception("Error in catch_all handler")

    async def raw_update_handler(
        self, update: Update, _context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        """Log raw update data for debugging."""
        try:
            _ = self._dump_update(update)
            if update.message and update.message.text and self.me and self.me.username:
                possible_mentions = [
                    f"@{self.me.username}",
                    self.me.username,
                    self.me.first_name,
                ]
                _ = any(
                    mention.lower() in update.message.text.lower()
                    for mention in possible_mentions
                )
        except Exception:
            logger.exception("Error in raw update handler")

    async def debug_command(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        """Debug command to verify bot is working."""
        if not update.effective_user or not update.message or not update.effective_chat:
            return

        if not self.me:
            try:
                self.me = await context.bot.get_me()
            except Exception:
                logger.exception("Failed to get bot info in debug command")

        chat_id = update.effective_chat.id
        chat_type = update.effective_chat.type

        logger.warning(
            "DEBUG COMMAND RECEIVED",
            chat_id=chat_id,
            chat_type=chat_type,
            user_id=update.effective_user.id,
            bot_info=self._safe_dict(self.me),
        )

        await update.message.reply_text(
            f"Debug info:\n"
            f"- Bot username: {self.me.username if self.me else 'unknown'}\n"
            f"- Bot ID: {self.me.id if self.me else 'unknown'}\n"
            f"- Chat type: {chat_type}\n"
            f"- Chat ID: {chat_id}\n"
            f"- Message received successfully!"
        )

    async def start_command(
        self, update: Update, _context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        """Handle the /start command."""
        if not update.effective_user or not update.message or not update.effective_chat:
            return

        user: User = update.effective_user
        user_id: int = user.id

        if not self._is_user_allowed(user_id):
            await update.message.reply_text(
                "Sorry, you're not authorized to use this bot."
            )
            logger.warning("Unauthorized access attempt", user_id=user_id)
            return

        await update.message.reply_text(
            f"👋 Hello {user.first_name}! I'm the Flare AI assistant. "
            f"Feel free to ask me anything about Flare Network."
        )
        logger.info("Start command handled", user_id=user_id)

    async def TVL_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """ Handle TVL related queries"""
        if not update.message or not update.effective_user or not update.effective_chat:
            logger.warning("Missing message, user, or chat; skipping")
            return
            
        user: User = update.effective_user
        user_id: int = user.id
        chat: Chat = update.effective_chat
        chat_id: int | str = chat.id
        chat_type: str = chat.type
        
        try:
            await context.bot.send_chat_action(chat_id=chat_id, action="typing")
            
            # Get current date in the format matching your data
            today = datetime.datetime.now().strftime("%Y-%m-%d 00:00:00.000 UTC")
            
            # Fetch data from Dune
            dune = DuneClient.from_env()
            query_result = dune.get_latest_result(4841961) # type: ignore
            # Extract rows from the ResultsResponse object
            all_rows = query_result.result.rows
            
            # Filter rows for today's date only
            today_rows = [row for row in all_rows if row.get("time") == today]
            
            if not today_rows:
                # If no data for today, find the most recent date with data
                available_dates = sorted(set(row.get("time") for row in all_rows), reverse=True)
                
                if not available_dates:
                    await update.message.reply_text("No price data available")
                    return
                    
                most_recent_date = available_dates[0] 
                most_recent_rows = [row for row in all_rows if row.get("time") == most_recent_date]
                
                date_obj = datetime.datetime.strptime(most_recent_date, "%Y-%m-%d 00:00:00.000 UTC")
                formatted_date = date_obj.strftime("%B %d, %Y")
                
                message = f"📊 *TVL Yield on Flare Blockchain* - {formatted_date}\n\n"
                
                # Sort by symbol for consistent output
                for row in sorted(most_recent_rows, key=lambda x: x.get("symbol", "")):
                    tvl = row.get("tvl", "")
                        
                    message += f"$*{tvl}*\n"
                    
                message += f"\nℹ️ No data available for today ({today}). Showing most recent data."
                
                await update.message.reply_text(message, parse_mode="Markdown")
            else:
                # Add this else block to handle today's data
                formatted_date = datetime.datetime.now().strftime("%B %d, %Y")
                
                message = f"📊 *TVL Yield on Flare Blockchain Today* - {formatted_date}\n\n"
                
                # Sort by symbol for consistent output
                for row in sorted(today_rows, key=lambda x: x.get("symbol", "")):
                    tvl = row.get("tvl", "")
                    message += f"$*{tvl}*\n"
                
                await update.message.reply_text(message, parse_mode="Markdown")
            
            chat_id_key = int(chat_id) if isinstance(chat_id, str) else chat_id
            self.last_processed_time[chat_id_key] = time.time()
            
        except Exception as e:
            logger.exception(f"Error processing transaction: {str(e)}")
            await update.message.reply_text(
                "I'm having trouble processing this data. Please try again later."
            )
    
    async def monitor_command(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        """Handle the /monitor command to toggle X/Twitter monitoring."""
        if not update.effective_user or not update.message or not update.effective_chat:
            return
        
        user_id: int = update.effective_user.id
        chat_id = update.effective_chat.id
        
        if not self._is_user_allowed(user_id):
            await update.message.reply_text(
                "Sorry, you're not authorized to use this bot."
            )
            logger.warning("Unauthorized monitor request", user_id=user_id)
            return
        
        # Create inline keyboard for activation/deactivation
        keyboard = [
            [
                InlineKeyboardButton("Activate", callback_data="activate_monitor"),
                InlineKeyboardButton("Deactivate", callback_data="deactivate_monitor"),
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        # Display current status
        status = "active" if chat_id in self.active_monitor_chats else "inactive"
        await update.message.reply_text(
            f"🐦 *@FlareNetworks X/Twitter Monitor*\n\n"
            f"Monitoring is currently *{status}*.\n"
            f"What would you like to do?",
            reply_markup=reply_markup,
            parse_mode="Markdown"
        )
        
        logger.info(
            "Monitor command handled", 
            user_id=user_id, 
            chat_id=chat_id, 
            current_status=status
        )
    
    # Add this method to handle callback queries from the inline keyboard
    async def button_callback(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        """Handle callback queries from inline buttons."""
        query = update.callback_query
        if not query or not update.effective_chat:
            return
            
        await query.answer()
        
        chat_id = update.effective_chat.id
        user_id = update.effective_user.id if update.effective_user else None
        
        # Handle monitor activation/deactivation
        if query.data == "activate_monitor":
            self.active_monitor_chats.add(chat_id)
            await query.edit_message_text(
                "✅ *@FlareNetworks X/Twitter monitoring activated!*\n\n"
                "You'll receive the latest posts from @FlareNetworks.",
                parse_mode="Markdown"
            )
            logger.info("Monitor activated", chat_id=chat_id, user_id=user_id)
            
        elif query.data == "deactivate_monitor":
            if chat_id in self.active_monitor_chats:
                self.active_monitor_chats.remove(chat_id)
            await query.edit_message_text(
                "❌ *@FlareNetworks X/Twitter monitoring deactivated.*\n\n"
                "You won't receive any more updates.",
                parse_mode="Markdown"
            )
            logger.info("Monitor deactivated", chat_id=chat_id, user_id=user_id)
    
    # Add this method to check for new posts and send them to active chats
    async def check_and_send_updates(self, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Check for new posts and send them to active monitoring chats."""
        if not self.active_monitor_chats:
            return  # No active chats, no need to check
        
        latest_post = self.fetch_latest_posts()
        if not latest_post:
            logger.warning("No posts found or error fetching posts")
            return
        
        # Check if this is a new post
        if latest_post.id != self.last_post_id:
            self.last_post_id = latest_post.id
            
            # Format the message
            message = (
                f"🔔 *New post from @FlareNetworks*\n\n"
                f"{latest_post.title}\n\n"
                f"[Read more]({latest_post.link})"
            )
            
            # Send to all active chats
            for chat_id in list(self.active_monitor_chats):  # Create a copy of the set to iterate
                try:
                    await context.bot.send_message(
                        chat_id=chat_id,
                        text=message,
                        parse_mode="Markdown",
                        disable_web_page_preview=False
                    )
                    logger.info("Sent X/Twitter update", chat_id=chat_id)
                except Exception as e:
                    logger.error(f"Error sending message to {chat_id}: {e}")
                    # Remove chat if we can't send messages to it
                    if chat_id in self.active_monitor_chats:
                        self.active_monitor_chats.remove(chat_id)

        
        

    async def help_command(
        self, update: Update, _context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        """Handle the /help command."""
        if not update.effective_user or not update.message or not update.effective_chat:
            return

        user_id: int = update.effective_user.id

        if not self._is_user_allowed(user_id):
            await update.message.reply_text(
                "Sorry, you're not authorized to use this bot."
            )
            logger.warning("Unauthorized help request", user_id=user_id)
            return

        help_text = (
            "🤖 *Flare AI Assistant Help*\n\n"
            "I can answer questions about Flare Network."
            "*Available commands:*\n"
            "/start - Start the conversation\n"
            "/token - Show token data"
            "/monitor - Toggle X/Twitter monitoring\n"
            "/about - Show what this bot can do\n"
            "\n\nSimply send me a message, and I'll do my best to assist you!"
        )
        await update.message.reply_text(help_text, parse_mode="Markdown")

   

    async def _process_group_chat_mention(
        self, text: str, entities: tuple[MessageEntity, ...], update: Update
    ) -> tuple[bool, str]:
        """Check if bot was mentioned in group chat and return cleaned message text."""
        if not self.me or not self.me.username:
            return False, text

        # Check direct mentions using entities
        for entity in entities:
            if entity.type == "mention":
                mention_text = text[entity.offset : entity.offset + entity.length]
                bot_username = self.me.username.lower()
                mention_without_at = (
                    mention_text[1:].lower()
                    if mention_text.startswith("@")
                    else mention_text.lower()
                )
                if mention_without_at == bot_username:
                    return True, text.replace(mention_text, "").strip()

        # Check text-based mentions
        for variation in [f"@{self.me.username}", f"@{self.me.username.lower()}"]:
            if variation.lower() in text.lower():
                idx = text.lower().find(variation.lower())
                if idx >= 0:
                    actual_length = len(variation)
                    actual_mention = text[idx : idx + actual_length]
                    return True, text.replace(actual_mention, "").strip()

        # Check if message is a reply to bot
        if (
            update.message
            and update.message.reply_to_message
            and update.message.reply_to_message.from_user
            and self.me
            and update.message.reply_to_message.from_user.id == self.me.id
        ):
            return True, text

        return False, text

    async def _handle_unauthorized_access(
        self, update: Update, chat_type: str, user_id: int, chat_id: int | str
    ) -> bool:
        """Handle unauthorized user access."""
        if chat_type == "private" and update.message:
            await update.message.reply_text(
                "Sorry, you are not authorized to use this bot."
            )
        logger.warning(
            "Unauthorized message",
            user_id=user_id,
            chat_id=chat_id,
            is_group=chat_type != "private",
        )
        return True

    async def handle_message(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        """Handle incoming messages and generate AI responses."""
        if not update.message or not update.effective_user or not update.effective_chat:
            logger.warning("Missing message, user, or chat; skipping")
            return

        self._dump_update(update)

        user: User = update.effective_user
        user_id: int = user.id
        chat: Chat = update.effective_chat
        chat_id: int | str = chat.id
        chat_type: str = chat.type

        # Get bot info if not already available
        if not self.me:
            try:
                self.me = await context.bot.get_me()
                logger.info(
                    "Bot information retrieved",
                    bot_id=self.me.id,
                    bot_username=self.me.username,
                    bot_first_name=self.me.first_name,
                )
            except Exception:
                logger.exception("Failed to get bot info")
                return

        if not update.message.text:
            logger.debug("Skipping message without text")
            return

        var_text: str = update.message.text
        if var_text and "token" in var_text.lower():
            await self.handle_token(update, context)
            return
        elif var_text and (var_text.startswith("0x") and all(c in "0123456789abcdefABCDEF" for c in var_text[2:])):
            return await self.handle_offchain(update, context)
        
        is_group_chat = chat_type in ["group", "supergroup", "channel"]

        # Log message details
        entities: tuple[MessageEntity, ...] = update.message.entities
        logger.info(
            "Received message details",
            user_id=user_id,
            chat_id=chat_id,
            chat_type=chat_type,
            message_id=update.message.message_id,
            message_text=var_text,
            has_entities=bool(entities),
            entity_count=len(entities),
            bot_username=self.me.username if self.me else "unknown",
        )

        # Handle group chat mentions
        if is_group_chat:
            is_mentioned, var_text = await self._process_group_chat_mention(
                var_text, entities, update
            )
            if not is_mentioned:
                logger.debug(
                    "Ignoring group message (not mentioned)",
                    chat_id=chat_id,
                    user_id=user_id,
                )
                return
            if not var_text:
                var_text = "Hello"
                logger.info(
                    "Empty mention received, responding with greeting",
                    chat_id=chat_id,
                    user_id=user_id,
                )

        # Check user authorization
        if not self._is_user_allowed(
            user_id
        ) and await self._handle_unauthorized_access(
            update, chat_type, user_id, chat_id
        ):
            return

        # Generate and send AI response
        logger.info(
            "Processing message",
            user_id=user_id,
            chat_id=chat_id,
            is_group=is_group_chat,
            message_text=var_text,
        )

        try:
            await context.bot.send_chat_action(chat_id=chat_id, action="typing")
            ai_response = self.ai_provider.generate_content(var_text)
            response_text = ai_response.text
            summarizer = Summarizer()
            summary = summarizer(response_text, min_length=50, max_length=150)

            chat_id_key = int(chat_id) if isinstance(chat_id, str) else chat_id
            self.last_processed_time[chat_id_key] = time.time()
            await update.message.reply_text(summary)
            logger.info(
                "Sent AI response",
                chat_id=chat_id,
                user_id=user_id,
                is_group=is_group_chat,
            )
        except Exception:
            logger.exception("Error generating AI response")
            await update.message.reply_text(
                "I'm having trouble processing your request. Please try again later."
            )

    async def handle_token(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not update.message or not update.effective_user or not update.effective_chat:
            logger.warning("Missing message, user, or chat; skipping")
            return
            
        user: User = update.effective_user
        user_id: int = user.id
        chat: Chat = update.effective_chat
        chat_id: int | str = chat.id
        chat_type: str = chat.type
        
        try:
            await context.bot.send_chat_action(chat_id=chat_id, action="typing")
            
            # Get current date in the format matching your data
            today = datetime.datetime.now().strftime("%Y-%m-%d")
            
            # Fetch data from Dune
            dune = DuneClient.from_env()
            query_result = dune.get_latest_result(4838993) # type: ignore
            
            # Extract rows from the ResultsResponse object
            all_rows = query_result.result.rows
            
            # Filter rows for today's date only
            today_rows = [row for row in all_rows if row.get("day") == today]
            
            if not today_rows:
                # If no data for today, find the most recent date with data
                available_dates = sorted(set(row.get("day") for row in all_rows), reverse=True)
                
                if not available_dates:
                    await update.message.reply_text("No price data available")
                    return
                    
                most_recent_date = available_dates[0]
                most_recent_rows = [row for row in all_rows if row.get("day") == most_recent_date]
                
                date_obj = datetime.datetime.strptime(most_recent_date, "%Y-%m-%d")
                formatted_date = date_obj.strftime("%B %d, %Y")
                
                message = f"📊 *Token Prices* - {formatted_date}\n\n"
                
                # Sort by symbol for consistent output
                for row in sorted(most_recent_rows, key=lambda x: x.get("symbol", "")):
                    symbol = row.get("symbol", "")
                    price = row.get("price", 0)
                    
                    # Format price based on typical ranges
                    if price < 0.01:
                        price_str = f"${price:.6f}"
                    elif price < 1:
                        price_str = f"${price:.4f}"
                    else:
                        price_str = f"${price:.2f}"
                        
                    message += f"*{symbol}*: {price_str}\n"
                    
                message += f"\nℹ️ No data available for today ({today}). Showing most recent data."
                
                await update.message.reply_text(message, parse_mode="Markdown")
            else:
                formatted_date = datetime.datetime.now().strftime("%B %d, %Y")
                
                message = f"📊 *Token Prices Today* - {formatted_date}\n\n"
                
                # Sort by symbol for consistent output
                for row in sorted(today_rows, key=lambda x: x.get("symbol", "")):
                    symbol = row.get("symbol", "")
                    price = row.get("price", 0)
                    
                    # Format price based on typical ranges
                    if price < 0.01:
                        price_str = f"${price:.6f}"
                    elif price < 1:
                        price_str = f"${price:.4f}"
                    else:
                        price_str = f"${price:.2f}"
                        
                    message += f"*{symbol}*: {price_str}\n"
                
                await update.message.reply_text(message, parse_mode="Markdown")
                
            chat_id_key = int(chat_id) if isinstance(chat_id, str) else chat_id
            self.last_processed_time[chat_id_key] = time.time()
            
        except Exception as e:
            logger.exception(f"Error processing transaction: {str(e)}")
            await update.message.reply_text(
                "I'm having trouble processing this data. Please try again later."
            )
    
    async def handle_offchain(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle Feed ID related queries"""
        if not update.message or not update.effective_user or not update.effective_chat:
            logger.warning("Missing message, user, or chat; skipping")
            return
                
        user: User = update.effective_user
        user_id: int = user.id
        chat: Chat = update.effective_chat
        chat_id: int | str = chat.id
        chat_type: str = chat.type

        query_text = update.message.text.strip()  # type: ignore
        
        logger.info(
            "Processing feed ID query",
            user_id=user_id,
            chat_id=chat_id,
            is_group=chat_type in ["group", "supergroup", "channel"],
            query=query_text,
        )
        
        try:
            await context.bot.send_chat_action(chat_id=chat_id, action="typing")
            
            # Extract feed ID - use the whole string if it looks like a hex string
            if query_text.startswith("0x") and all(c in "0123456789abcdefABCDEF" for c in query_text[2:]):
                feed_id_hex = query_text
            else:
                # Try to find a hex pattern in the text
                import re
                match = re.search(r'0x[0-9a-fA-F]+', query_text)
                if not match:
                    await update.message.reply_text("No valid feed ID found in message. Please provide a valid feed ID.")
                    return
                feed_id_hex = match.group(0)
            
            # Convert hex string to bytes21
            feed_id_bytes = bytes.fromhex(feed_id_hex[2:])
            
            w3 = AsyncWeb3(AsyncHTTPProvider(RPC_URL))
            ftsov2 = w3.eth.contract(address=w3.to_checksum_address(FTSOV2_ADDRESS), abi=ABI)
            
            # Call the function with a list containing one feed ID
            feeds, decimals, timestamp = await ftsov2.functions.getFeedsById([feed_id_bytes]).call()
            
            # Create response message with proper formatting
            feed_info = (
                f"🪙 *Feed Info*\n\n"
                f"*Feed ID:* `{feed_id_hex}`\n"
                f"*Value:* {feeds[0] if feeds and len(feeds) > 0 else 'N/A'}\n"
                f"*Decimals:* {decimals[0] if decimals and len(decimals) > 0 else 'N/A'}\n"
                f"*Timestamp:* {timestamp}\n"
            )
            
            await update.message.reply_text(feed_info, parse_mode="Markdown")
                    
            chat_id_key = int(chat_id) if isinstance(chat_id, str) else chat_id
            self.last_processed_time[chat_id_key] = time.time()
            
        except Exception as e:
            logger.exception(f"Error processing feed ID: {str(e)}")
            await update.message.reply_text(
                f"Error processing feed ID: {str(e)}\n\nPlease check the format and try again."
            )

    async def error_handler(
        self, update: object, context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        """Handle errors in the telegram bot."""
        logger.error("Telegram error", error=context.error, update=update)

    async def initialize(self) -> None:
        """Initialize the bot application."""
        logger.info("Initializing Telegram bot")

        # Build the application with default settings
        builder = Application.builder().token(self.api_token)
        self.application = builder.build()

        try:
            self.me = await Bot(self.api_token).get_me()
            logger.info(
                "Bot information retrieved",
                bot_id=self.me.id,
                bot_username=self.me.username,
                bot_first_name=self.me.first_name,
            )
        except TelegramError:
            logger.exception("Failed to get bot info")
            self.me = None

        # Add handlers in the correct order
        self.application.add_handler(CommandHandler("start", self.start_command))
        self.application.add_handler(CommandHandler("help", self.help_command))
        self.application.add_handler(CommandHandler("debug", self.debug_command))
        self.application.add_handler(CommandHandler("tvl", self.TVL_command))

        self.application.add_handler(CommandHandler("monitor", self.monitor_command))
        
        # Add callback query handler for inline buttons
        self.application.add_handler(CallbackQueryHandler(self.button_callback))


        # Add message handler for text messages
        self.application.add_handler(
            MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_message)
        )
      
        # Add error handler
        self.application.add_error_handler(self.error_handler)

        # Initialize the application
        await self.application.initialize()
        logger.info("Telegram bot initialized successfully")

    async def start_polling(self) -> None:
        """Start polling for updates."""
        if not self.application:
            raise RuntimeError(ERR_BOT_NOT_INITIALIZED)

        logger.info("Starting Telegram bot polling")

        await self.application.start()

        # Type assertion to help Pyright understand that updater exists
        if self.application.updater is None:
            raise RuntimeError(ERR_UPDATER_NOT_INITIALIZED)

        await self.application.updater.start_polling(
            poll_interval=self.polling_interval,
            timeout=30,
            bootstrap_retries=-1,
            read_timeout=30,
            write_timeout=30,
            connect_timeout=30,
            pool_timeout=30,
        )

    async def start(self) -> None:
        """Start the Telegram bot."""
        try:
            logger.info("Starting Telegram bot")
            await self.initialize()
            await self.start_polling()
        except KeyboardInterrupt:
            logger.info("Telegram bot stopped by user")
        except Exception:
            logger.exception("Fatal error in Telegram bot")
        finally:
            await self.shutdown()

    async def shutdown(self) -> None:
        """Shut down the bot."""
        if self.application:
            logger.info("Shutting down Telegram bot")
            await self.application.stop()
            await self.application.shutdown()