import os
import asyncio
import logging
import random
import time
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import aiohttp
import telegram
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReactionTypeEmoji
from telegram.constants import ChatAction
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler, CallbackQueryHandler,
    filters, ContextTypes, Defaults
)

# Configuration
BOT_TOKEN = os.environ.get("BOT_TOKEN")
OWNER_ID = int(os.environ.get("OWNER_ID", "0"))
TRIGGER_KEYWORD = "billu"
WALLHAVEN_API_URL = "https://wallhaven.cc/api/v1/search?q=flower&ratios=16x9&sorting=random&categories=100&purity=100"

# Welcome Messages Dictionary
WELCOME_MESSAGES = [
    "Hello {mention} just wanted to share something with love 💖",
    "This is sent with care {mention} nothing more nothing less 💌",
    "Wishing you a peaceful moment {mention} 💫",
    "No reason {mention} just something warm for your heart 🌸",
    "You crossed my thoughts {mention} so here is this 🌷",
    "May this bring quiet joy to your day {mention} 🕊️",
    "No noise no rush {mention} just a soft pause 💗",
    "Take this small piece of peace {mention} 🌼",
    "You are here and that is enough {mention} 🌙",
    "For your gentle soul {mention} with kindness 💝",
    "This carries no message {mention} only warmth 💞",
    "Nothing big {mention} just a reminder you matter 🍃",
    "Let this be a calm second in your day {mention} ✨",
    "No need to smile {mention} just feel what is here 💓",
    "This is not special {mention} but it is real 💗",
    "You deserve kindness without reason {mention} 🌤️",
    "A quiet hello for your heart {mention} 🎀",
    "This carries no answers {mention} only softness 🌺",
    "Even in silence {mention} this speaks with love 🕯️",
    "This is for you {mention} without asking why 💌",
    "Not for fixing just for feeling {mention} 💮",
    "Let this rest with you {mention} no need to do anything 🧸",
    "You are not forgotten {mention} even in stillness 🌌",
    "There is nothing to prove {mention} just take this 💘",
    "Without words without reason {mention} just presence 🌷",
    "It is okay to pause {mention} let this moment be yours 🫶",
    "With no pressure no weight {mention} just love 💞",
    "This is here for you {mention} without expectation 🍥",
    "Your presence matters {mention} quietly and truly 🌈",
    "May this bring a quiet breath to your heart {mention} 🌿"
]

# Emoji Collections
SOFT_EMOJIS = [
    "⛅", "🌤️", "❣️", "💖", "🌸", "💝", "💘", "💗", "💓", "💞", 
    "❤️‍🔥", "🌹", "🌺", "🌼", "🌷", "💐", "🕊️", "🐱", "🐈", "💌"
]

REACTION_EMOJIS = [
    "👍", "❤️", "🔥", "😁", "🆒"
]

# Error Messages
ERROR_MESSAGES = {
    "image_fetch_failed": "⚠️ Failed to get anime image.",
    "broadcast_failed": "⚠️ Broadcast failed. Please try again.",
    "ping_failed": "⚠️ Ping failed. Please try again.",
    "general_error": "⚠️ Something went wrong. Please try again."
}

# Status Messages
STATUS_MESSAGES = {
    "broadcast_cancelled": "❌ Broadcast cancelled.",
    "pinging": "🛰️ Pinging...",
    "server_alive": "Sakura bot is alive!"
}

# Chat Action Mapping - All 10 available ChatActions from telegram.constants.ChatAction
MESSAGE_TYPE_ACTIONS = {
    'photo': ChatAction.UPLOAD_PHOTO,
    'video': ChatAction.UPLOAD_VIDEO,
    'document': ChatAction.UPLOAD_DOCUMENT,
    'audio': ChatAction.RECORD_VOICE,        # For audio files, use RECORD_VOICE
    'voice': ChatAction.RECORD_VOICE,        # For voice messages
    'video_note': ChatAction.RECORD_VIDEO_NOTE,  # For video notes
    'sticker': ChatAction.CHOOSE_STICKER,
    'location': ChatAction.FIND_LOCATION,
    'text': ChatAction.TYPING,
    # Additional chat actions available:
    'upload_voice': ChatAction.UPLOAD_VOICE,        # For uploading voice files
    'upload_video_note': ChatAction.UPLOAD_VIDEO_NOTE,  # For uploading video notes
    'record_video': ChatAction.RECORD_VIDEO         # For recording video
}

# Broadcast Target Mapping
BROADCAST_TARGETS = {
    "broadcast_user": {
        "target": "users",
        "answer": "Users selected ✅",
        "message": "✅ Send the message you want to broadcast to users."
    },
    "broadcast_group": {
        "target": "groups", 
        "answer": "Groups selected ✅",
        "message": "✅ Send the message you want to broadcast to groups."
    },
    "broadcast_all": {
        "target": "all",
        "answer": "All users and groups selected ✅", 
        "message": "✅ Send the message you want to broadcast to all users and groups."
    }
}

# Command Descriptions
BOT_COMMANDS = [
    ("start", "🎨 Get an image"),
    ("ping", "🏓 Check bot latency")
]

# Logging setup with clean formatting
class ColoredFormatter(logging.Formatter):
    """Custom formatter with colors and clean layout."""
    
    # ANSI color codes
    COLORS = {
        'DEBUG': '\033[36m',    # Cyan
        'INFO': '\033[32m',     # Green
        'WARNING': '\033[33m',  # Yellow
        'ERROR': '\033[31m',    # Red
        'CRITICAL': '\033[35m', # Magenta
        'RESET': '\033[0m'      # Reset
    }
    
    def format(self, record):
        # Get color for log level
        color = self.COLORS.get(record.levelname, self.COLORS['RESET'])
        reset = self.COLORS['RESET']
        
        # Format timestamp
        timestamp = self.formatTime(record, '%H:%M:%S')
        
        # Create clean log format
        log_format = f"{color}[{timestamp}] {record.levelname:<8}{reset} {record.name:<15} | {record.getMessage()}"
        
        # Handle exceptions
        if record.exc_info:
            log_format += f"\n{self.formatException(record.exc_info)}"
            
        return log_format

# Configure logging with custom formatter
logging.basicConfig(
    level=logging.INFO,
    format='%(message)s',  # We'll handle formatting in ColoredFormatter
    handlers=[
        logging.StreamHandler()
    ]
)

# Apply custom formatter to all handlers
for handler in logging.root.handlers:
    handler.setFormatter(ColoredFormatter())

logger = logging.getLogger(__name__)

# Create separate loggers for different components with clean names
loggers = {
    'reaction': logging.getLogger('REACT'),
    'echo': logging.getLogger('ECHO'),
    'broadcast': logging.getLogger('BROADCAST'),
    'image': logging.getLogger('IMAGE'),
    'api': logging.getLogger('API'),
    'chat_action': logging.getLogger('ACTION'),
    'tracking': logging.getLogger('TRACK'),
    'commands': logging.getLogger('CMD'),
    'errors': logging.getLogger('ERROR')
}

# Apply formatter to all component loggers
for component_logger in loggers.values():
    for handler in component_logger.handlers:
        handler.setFormatter(ColoredFormatter())

# Disable telegram library's debug logs to keep terminal clean
logging.getLogger('telegram').setLevel(logging.WARNING)
logging.getLogger('httpx').setLevel(logging.WARNING)
logging.getLogger('httpcore').setLevel(logging.WARNING)

# Bot state storage
user_button_state = {}
user_ids = set()
group_ids = set()
broadcast_mode = {}


async def send_chat_action(context, chat_id, action):
    """Send chat action without delay."""
    try:
        loggers['chat_action'].debug(f"Sending '{action}' to chat {chat_id}")
        await context.bot.send_chat_action(chat_id=chat_id, action=action)
        loggers['chat_action'].debug(f"Action '{action}' sent successfully")
    except telegram.error.Forbidden:
        loggers['errors'].warning(f"Forbidden to send action to chat {chat_id}")
    except telegram.error.BadRequest as e:
        loggers['errors'].warning(f"Bad request for chat {chat_id}: {str(e)[:50]}")
    except telegram.error.NetworkError:
        loggers['errors'].warning(f"Network error for chat {chat_id}")
    except Exception as e:
        loggers['errors'].error(f"Unexpected error sending action: {str(e)[:50]}")


def get_random_emoji():
    """Get a random soft emoji."""
    try:
        emoji = random.choice(SOFT_EMOJIS)
        logger.debug(f"Selected emoji: {emoji}")
        return emoji
    except Exception:
        loggers['errors'].error("Error selecting random emoji, using fallback")
        return "💖"  # fallback emoji


def get_random_reaction():
    """Get a random reaction emoji."""
    try:
        reaction = random.choice(REACTION_EMOJIS)
        logger.debug(f"Selected reaction: {reaction}")
        return reaction
    except Exception:
        loggers['errors'].error("Error selecting random reaction, using fallback")
        return "👍"  # fallback reaction


def create_user_mention(user):
    """Create a formatted mention string for a user."""
    try:
        if not user:
            loggers['errors'].warning("User object is None, using fallback")
            return "Unknown User"
        
        name = f"{user.first_name or ''} {user.last_name or ''}".strip()
        if not name:
            name = "User"
            logger.debug(f"User {user.id} has no name, using fallback")
        
        mention = f"<a href='tg://user?id={user.id}'>{name}</a>"
        logger.debug(f"Created mention for user {user.id}")
        return mention
    except Exception as e:
        loggers['errors'].error(f"Error creating user mention: {str(e)[:50]}")
        return "Unknown User"


async def fetch_image():
    """Fetch a random image from Wallhaven API."""
    try:
        loggers['api'].info("Fetching image from Wallhaven API")
        async with aiohttp.ClientSession() as session:
            async with session.get(WALLHAVEN_API_URL) as response:
                if response.status != 200:
                    loggers['api'].error(f"API returned status {response.status}")
                    return None

                data = await response.json()
                images = data.get("data", [])

                if not images:
                    loggers['api'].warning("No images found in API response")
                    return None

                selected_image = random.choice(images)["path"]
                loggers['api'].info("Successfully fetched image")
                return selected_image
    except aiohttp.ClientError:
        loggers['api'].error("Network error fetching image")
    except asyncio.TimeoutError:
        loggers['api'].error("Timeout error fetching image")
    except KeyError:
        loggers['api'].error("Invalid API response structure")
    except Exception as e:
        loggers['api'].error(f"Unexpected error: {str(e)[:50]}")
    return None


def get_message_type_and_action(message):
    """Determine message type and corresponding chat action."""
    for msg_type, action in MESSAGE_TYPE_ACTIONS.items():
        if msg_type == 'text':
            continue
        if getattr(message, msg_type, None):
            return msg_type, action
    return 'text', MESSAGE_TYPE_ACTIONS['text']


async def send_image(chat_id, user, bot, loading_msg=None, reply_to_message_id=None):
    """Send a welcome image with a personalized message."""
    try:
        loggers['image'].info(f"Starting image send for chat {chat_id}")
        
        # Show upload photo action
        try:
            await bot.send_chat_action(chat_id=chat_id, action=ChatAction.UPLOAD_PHOTO)
        except Exception:
            loggers['image'].debug("Failed to send upload photo action")
        
        image_url = await fetch_image()

        if not image_url:
            error_msg = ERROR_MESSAGES["image_fetch_failed"]
            loggers['image'].warning("No image URL available")
            
            try:
                if loading_msg:
                    await loading_msg.edit_text(error_msg)
                else:
                    await bot.send_message(chat_id=chat_id, text=error_msg)
                loggers['image'].info("Sent error message")
            except Exception as e:
                loggers['errors'].error(f"Failed to send error message: {str(e)[:50]}")
            return

        mention = create_user_mention(user)
        greeting = random.choice(WELCOME_MESSAGES).format(mention=mention)

        try:
            if loading_msg:
                await bot.edit_message_media(
                    chat_id=chat_id,
                    message_id=loading_msg.message_id,
                    media=telegram.InputMediaPhoto(
                        media=image_url,
                        caption=greeting,
                        parse_mode="HTML"
                    )
                )
                loggers['image'].info("Successfully updated loading message with image")
            else:
                await bot.send_photo(
                    chat_id=chat_id,
                    photo=image_url,
                    caption=greeting,
                    reply_to_message_id=reply_to_message_id,
                    parse_mode="HTML"
                )
                loggers['image'].info("Successfully sent new image")
        except telegram.error.BadRequest:
            loggers['image'].warning("Bad request sending image, trying fallback")
            # Try sending text fallback
            try:
                fallback_msg = f"{greeting}\n\n{ERROR_MESSAGES['image_fetch_failed']}"
                if loading_msg:
                    await loading_msg.edit_text(fallback_msg, parse_mode="HTML")
                else:
                    await bot.send_message(chat_id=chat_id, text=fallback_msg, parse_mode="HTML")
                loggers['image'].info("Sent fallback text message")
            except Exception:
                loggers['errors'].error("Fallback message also failed")
        except telegram.error.Forbidden:
            loggers['errors'].warning(f"Forbidden to send image to chat {chat_id}")
        except telegram.error.NetworkError:
            loggers['errors'].warning(f"Network error sending image to chat {chat_id}")
        except Exception as e:
            loggers['errors'].error(f"Unexpected error sending image: {str(e)[:50]}")
    except Exception as e:
        loggers['errors'].critical(f"Critical error in send_image: {str(e)[:50]}")
        raise


async def react_to_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """React to a message based on chat type and content."""
    try:
        message = update.message
        if not message:
            return

        chat_type = message.chat.type
        bot = context.bot
        emoji = get_random_reaction()
        lowered = (message.text or "").lower()
        user_id = message.from_user.id if message.from_user else None

        should_react = False

        # Always react in private chats
        if chat_type == "private":
            should_react = True
            loggers['reaction'].debug("Private chat - will react")
        # In groups, react if keyword is mentioned or replying to bot
        elif chat_type in ["group", "supergroup"]:
            if TRIGGER_KEYWORD in lowered:
                should_react = True
                loggers['reaction'].debug(f"Keyword '{TRIGGER_KEYWORD}' found - will react")
            elif message.reply_to_message and message.reply_to_message.from_user.id == bot.id:
                should_react = True
                loggers['reaction'].debug("Reply to bot - will react")

        if should_react:
            try:
                await bot.set_message_reaction(
                    chat_id=message.chat.id,
                    message_id=message.message_id,
                    reaction=[ReactionTypeEmoji(emoji=emoji)]
                )
                loggers['reaction'].info(f"Reacted with {emoji} in chat {message.chat.id}")
            except telegram.error.BadRequest:
                loggers['reaction'].debug("Bad request setting reaction")
            except telegram.error.Forbidden:
                loggers['reaction'].debug(f"Forbidden to react in chat {message.chat.id}")
            except Exception as e:
                loggers['errors'].error(f"Unexpected error setting reaction: {str(e)[:50]}")
    except Exception as e:
        loggers['errors'].critical(f"Critical error in react_to_message: {str(e)[:50]}")


def track_chat_id(chat_id, chat_type):
    """Track user and group IDs."""
    try:
        if chat_type == "private":
            if chat_id not in user_ids:
                user_ids.add(chat_id)
                loggers['tracking'].info(f"New user tracked: {chat_id} (Total: {len(user_ids)})")
        elif chat_type in ["group", "supergroup"]:
            if chat_id not in group_ids:
                group_ids.add(chat_id)
                loggers['tracking'].info(f"New group tracked: {chat_id} (Total: {len(group_ids)})")
    except Exception as e:
        loggers['errors'].error(f"Error tracking chat ID {chat_id}: {str(e)[:50]}")


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /start command."""
    try:
        user_id = update.effective_user.id if update.effective_user else None
        loggers['commands'].info(f"/start from user {user_id}")
        
        await react_to_message(update, context)
        user = update.effective_user
        chat_id = update.effective_chat.id

        if not user:
            loggers['errors'].error("No user found in /start command")
            return

        # Initialize user state
        user_button_state[user.id] = {"updates": False, "group": False, "addme": False}

        # Track chat ID
        track_chat_id(chat_id, update.effective_chat.type)

        # Send typing action before responding
        await send_chat_action(context, chat_id, ChatAction.TYPING)
        
        # Send loading message and then welcome image
        emoji_msg = get_random_emoji()
        try:
            loading_msg = await context.bot.send_message(chat_id=chat_id, text=emoji_msg)
        except Exception as e:
            loggers['errors'].error(f"Failed to send loading message: {str(e)[:50]}")
            return

        await send_image(chat_id, user, context.bot, loading_msg=loading_msg)
        loggers['commands'].info(f"/start completed for user {user.id}")
        
    except Exception as e:
        loggers['errors'].critical(f"Critical error in /start: {str(e)[:50]}")
        try:
            await update.message.reply_text(ERROR_MESSAGES["general_error"])
        except:
            pass


async def ping_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /ping command."""
    try:
        user_id = update.effective_user.id if update.effective_user else None
        loggers['commands'].info(f"/ping from user {user_id}")
        
        await react_to_message(update, context)
        
        # Show typing action before ping
        await send_chat_action(context, update.effective_chat.id, ChatAction.TYPING)
        
        start_time = time.time()
        try:
            msg = await update.message.reply_text(STATUS_MESSAGES["pinging"])
        except Exception as e:
            loggers['errors'].error(f"Failed to send ping message: {str(e)[:50]}")
            return
            
        latency = int((time.time() - start_time) * 1000)
        
        try:
            await msg.edit_text(
                f"🏓 <a href='https://t.me/SoulMeetsHQ'>PONG!</a> {latency}ms",
                parse_mode="HTML",
                disable_web_page_preview=True
            )
            loggers['commands'].info(f"/ping completed with {latency}ms latency")
        except Exception as e:
            loggers['errors'].error(f"Failed to edit ping message: {str(e)[:50]}")
            
    except Exception as e:
        loggers['errors'].critical(f"Critical error in /ping: {str(e)[:50]}")
        try:
            await update.message.reply_text(ERROR_MESSAGES["ping_failed"])
        except:
            pass


async def broadcast_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /broadcast command (owner only)."""
    try:
        user_id = update.effective_user.id if update.effective_user else None
        loggers['broadcast'].info(f"/broadcast from user {user_id}")
        
        if user_id != OWNER_ID:
            loggers['broadcast'].warning(f"Unauthorized broadcast attempt from {user_id}")
            return

        loggers['broadcast'].info("Authorized broadcast request from owner")

        # Show typing action before showing broadcast menu  
        await send_chat_action(context, update.effective_chat.id, ChatAction.TYPING)

        keyboard = [
            [InlineKeyboardButton("👤 User", callback_data="broadcast_user"), 
             InlineKeyboardButton("👥 Group", callback_data="broadcast_group")],
            [InlineKeyboardButton("🌐 All", callback_data="broadcast_all"), 
             InlineKeyboardButton("❌ Cancel", callback_data="broadcast_cancel")]
        ]
        
        try:
            await update.message.reply_text("📢 Choose broadcast target:", reply_markup=InlineKeyboardMarkup(keyboard))
            loggers['broadcast'].info("Broadcast menu sent to owner")
        except Exception as e:
            loggers['errors'].error(f"Failed to send broadcast menu: {str(e)[:50]}")
            
    except Exception as e:
        loggers['errors'].critical(f"Critical error in /broadcast: {str(e)[:50]}")


async def handle_broadcast_choice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle broadcast target selection."""
    try:
        query = update.callback_query
        user_id = query.from_user.id if query.from_user else None
        loggers['broadcast'].info(f"Broadcast choice: {query.data} from user {user_id}")
        
        if query.data == "broadcast_cancel":
            try:
                await query.answer("Broadcast cancelled!", show_alert=True)
                await query.edit_message_text(STATUS_MESSAGES["broadcast_cancelled"])
                loggers['broadcast'].info("Broadcast cancelled")
            except Exception as e:
                loggers['errors'].error(f"Failed to handle broadcast cancellation: {str(e)[:50]}")
            return

        if query.data in BROADCAST_TARGETS:
            config = BROADCAST_TARGETS[query.data]
            try:
                await query.answer(config["answer"])
                await query.edit_message_text(config["message"])
                broadcast_mode[query.from_user.id] = config["target"]
                loggers['broadcast'].info(f"Broadcast target '{config['target']}' selected")
            except Exception as e:
                loggers['errors'].error(f"Failed to handle broadcast choice: {str(e)[:50]}")
        else:
            loggers['broadcast'].warning(f"Unknown broadcast choice: {query.data}")
            
    except Exception as e:
        loggers['errors'].critical(f"Critical error in broadcast choice handler: {str(e)[:50]}")


async def handle_broadcast_content(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle broadcast message content."""
    try:
        user_id = update.effective_user.id
        loggers['broadcast'].info(f"Processing broadcast content from user {user_id}")

        # Only handle if user is in broadcast mode
        if user_id not in broadcast_mode:
            return

        target = broadcast_mode.pop(user_id)
        message = update.message
        
        if not message:
            loggers['errors'].error("No message found in broadcast content")
            return
            
        loggers['broadcast'].info(f"Broadcasting to target: {target}")
        
        # Determine message type and action
        message_type, chat_action = get_message_type_and_action(message)
        
        await send_chat_action(context, message.chat_id, chat_action)
        
        # Determine target IDs based on selection
        if target == "users":
            ids = user_ids
        elif target == "groups":
            ids = group_ids
        elif target == "all":
            ids = user_ids.union(group_ids)
        else:
            loggers['errors'].error(f"Unknown broadcast target: {target}")
            return
        
        count = 0
        failed_count = 0
        total_targets = len(ids)

        loggers['broadcast'].info(f"Starting broadcast to {total_targets} {target}")

        for cid in list(ids):
            try:
                # Send appropriate chat action for each recipient
                try:
                    await context.bot.send_chat_action(chat_id=cid, action=chat_action)
                except Exception:
                    pass  # Ignore chat action failures
                
                await context.bot.copy_message(
                    chat_id=cid,
                    from_chat_id=update.message.chat_id,
                    message_id=update.message.message_id
                )
                count += 1
                await asyncio.sleep(0.05)
                
            except telegram.error.Forbidden:
                failed_count += 1
            except telegram.error.BadRequest:
                failed_count += 1
            except telegram.error.NetworkError:
                failed_count += 1
            except Exception:
                failed_count += 1

        loggers['broadcast'].info(f"Broadcast completed: {count} successful, {failed_count} failed")
        
        # Show typing action before sending completion message
        await send_chat_action(context, message.chat_id, ChatAction.TYPING)
        
        try:
            result_text = f"📢 Broadcast sent to {count} {target}."
            if failed_count > 0:
                result_text += f"\n⚠️ {failed_count} failed to receive the message."
            await update.message.reply_text(result_text)
            loggers['broadcast'].info("Broadcast completion message sent")
        except Exception as e:
            loggers['errors'].error(f"Failed to send broadcast completion: {str(e)[:50]}")
            
    except Exception as e:
        loggers['errors'].critical(f"Critical error in broadcast content handler: {str(e)[:50]}")
        try:
            await update.message.reply_text(ERROR_MESSAGES["broadcast_failed"])
        except:
            pass


async def handle_echo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle echo feature for private chats and group replies to bot."""
    try:
        message = update.message
        chat_type = message.chat.type
        user_id = message.from_user.id if message.from_user else None

        # Echo feature for private chats
        if chat_type == "private":
            loggers['echo'].info(f"Echo triggered in private chat for user {user_id}")
            await react_to_message(update, context)
            
            # Determine message type and send appropriate action
            message_type, chat_action = get_message_type_and_action(message)
            
            await send_chat_action(context, message.chat_id, chat_action)
            
            try:
                await context.bot.copy_message(
                    chat_id=message.chat_id,
                    from_chat_id=message.chat_id,
                    message_id=message.message_id
                )
                loggers['echo'].info("Private echo successful")
            except telegram.error.BadRequest:
                loggers['echo'].debug("Bad request in private echo")
            except telegram.error.Forbidden:
                loggers['echo'].debug("Forbidden in private echo")
            except Exception as e:
                loggers['errors'].error(f"Unexpected error in private echo: {str(e)[:50]}")
            return True

        # Echo feature for group replies to bot
        if message.reply_to_message and message.reply_to_message.from_user.id == context.bot.id:
            loggers['echo'].info(f"Echo triggered in group for reply to bot from user {user_id}")
            await react_to_message(update, context)
            
            # Determine message type and send appropriate action
            message_type, chat_action = get_message_type_and_action(message)
            
            await send_chat_action(context, message.chat_id, chat_action)
            
            try:
                await context.bot.copy_message(
                    chat_id=message.chat_id,
                    from_chat_id=message.chat_id,
                    message_id=message.message_id,
                    reply_to_message_id=message.message_id
                )
                loggers['echo'].info("Group echo successful")
            except telegram.error.BadRequest:
                loggers['echo'].debug("Bad request in group echo")
            except telegram.error.Forbidden:
                loggers['echo'].debug("Forbidden in group echo")
            except Exception as e:
                loggers['errors'].error(f"Unexpected error in group echo: {str(e)[:50]}")
            return True

        return False
        
    except Exception as e:
        loggers['errors'].critical(f"Critical error in echo handler: {str(e)[:50]}")
        return False


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle all incoming messages - includes echo feature and keyword triggering."""
    try:
        user = update.effective_user
        message = update.message
        if not message:
            return

        chat_type = message.chat.type
        user_id = user.id if user else None
        chat_id = message.chat_id

        logger.info(f"📥 Message from user {user_id} in {chat_type} chat {chat_id}")

        # Track chat ID
        track_chat_id(message.chat_id, chat_type)

        text = message.text or ""
        lowered = text.lower()

        logger.debug(f"📝 Message text: '{text[:50]}{'...' if len(text) > 50 else ''}'")

        # Handle keyword trigger in any chat
        if TRIGGER_KEYWORD in lowered:
            logger.info(f"🎯 Keyword '{TRIGGER_KEYWORD}' triggered by user {user_id}")
            await react_to_message(update, context)
            reply_id = message.message_id if chat_type in ["group", "supergroup"] else None
            
            # Show typing action before sending emoji message
            await send_chat_action(context, message.chat_id, ChatAction.TYPING)
            
            try:
                emoji_msg = get_random_emoji()
                loading_msg = await context.bot.send_message(
                    chat_id=message.chat_id,
                    text=emoji_msg,
                    reply_to_message_id=reply_id
                )
                logger.debug(f"✅ Keyword response emoji sent to chat {chat_id}")
                
                await send_image(message.chat_id, user, context.bot, loading_msg=loading_msg)
                logger.info(f"✅ Keyword response completed for user {user_id}")
                
            except Exception as e:
                logger.error(f"❌ Error in keyword response: {e}")
            return

        # Handle echo feature
        echo_handled = await handle_echo(update, context)
        if echo_handled:
            logger.debug("✅ Message handled by echo feature")
        else:
            logger.debug("ℹ️ Message not handled by any feature")
            
    except Exception as e:
        logger.critical(f"💥 Critical error in message handler: {e}")


async def set_bot_commands(application):
    """Set bot commands in Telegram."""
    try:
        logger.info("⚙️ Setting bot commands")
        await application.bot.set_my_commands(BOT_COMMANDS)
        logger.info("✅ Bot commands set successfully")
    except Exception as e:
        logger.error(f"❌ Failed to set bot commands: {e}")


class BroadcastFilter(filters.MessageFilter):
    """Custom filter for broadcast messages."""

    def filter(self, message):
        try:
            if not message.from_user:
                logger.debug("❌ BroadcastFilter: No user in message")
                return False
            user_id = message.from_user.id
            is_in_broadcast_mode = user_id == OWNER_ID and user_id in broadcast_mode
            logger.debug(f"🔍 BroadcastFilter: user_id={user_id}, owner_id={OWNER_ID}, in_broadcast_mode={user_id in broadcast_mode}, result={is_in_broadcast_mode}")
            return is_in_broadcast_mode
        except Exception as e:
            logger.error(f"❌ Error in BroadcastFilter: {e}")
            return False


def setup_bot():
    """Create and configure the bot application."""
    try:
        logger.info("🤖 Setting up bot application")
        
        if not BOT_TOKEN:
            logger.critical("💥 BOT_TOKEN is not set!")
            raise ValueError("BOT_TOKEN environment variable is required")
            
        app = ApplicationBuilder().token(BOT_TOKEN).defaults(Defaults(parse_mode="HTML")).build()
        logger.info("✅ Bot application created successfully")

        logger.info("🔧 Setting up bot handlers...")

        # Add command handlers
        app.add_handler(CommandHandler("start", start_command))
        app.add_handler(CommandHandler("ping", ping_command))
        app.add_handler(CommandHandler("broadcast", broadcast_command))
        app.add_handler(CallbackQueryHandler(handle_broadcast_choice, pattern="^broadcast_"))
        logger.info("✅ Command handlers added")

        # Add broadcast handler with custom filter
        broadcast_filter = BroadcastFilter()
        app.add_handler(MessageHandler(
            filters.ALL & (~filters.COMMAND) & broadcast_filter, 
            handle_broadcast_content
        ))
        logger.info("✅ Broadcast handler added")

        # Add general message handler for echo and keyword features
        app.add_handler(MessageHandler(filters.ALL & (~filters.COMMAND), handle_message))
        logger.info("✅ Message handler added")

        app.post_init = set_bot_commands
        logger.info("✅ Bot handlers setup complete")
        return app
        
    except Exception as e:
        logger.critical(f"💥 Critical error setting up bot: {e}")
        raise


class HealthCheckHandler(BaseHTTPRequestHandler):
    """HTTP handler for health checks."""

    def do_GET(self):
        try:
            logger.debug("🌐 Health check GET request received")
            self.send_response(200)
            self.end_headers()
            self.wfile.write(STATUS_MESSAGES["server_alive"].encode())
            logger.debug("✅ Health check response sent")
        except Exception as e:
            logger.error(f"❌ Error in health check GET: {e}")

    def do_HEAD(self):
        try:
            logger.debug("🌐 Health check HEAD request received")
            self.send_response(200)
            self.end_headers()
            logger.debug("✅ Health check HEAD response sent")
        except Exception as e:
            logger.error(f"❌ Error in health check HEAD: {e}")

    def log_message(self, format, *args):
        """Suppress HTTP server logs."""
        pass


def start_health_server():
    """Start HTTP server for health checks."""
    try:
        logger.info("🌐 Starting HTTP health check server")
        port = int(os.environ.get("PORT", 5000))
        
        server = HTTPServer(("0.0.0.0", port), HealthCheckHandler)
        logger.info(f"✅ HTTP server listening on 0.0.0.0:{port}")
        server.serve_forever()
        
    except OSError as e:
        logger.error(f"❌ Failed to bind to port {port}: {e}")
        raise
    except Exception as e:
        logger.critical(f"💥 Critical error starting HTTP server: {e}")
        raise


def main():
    """Main function to run the bot."""
    try:
        print("\n" + "="*60)
        print("🌸 SAKURA BOT STARTING 🌸")
        print("="*60)
        
        if not BOT_TOKEN:
            logger.critical("💥 BOT_TOKEN environment variable is not set")
            return

        if OWNER_ID == 0:
            logger.warning("⚠️ OWNER_ID not set - broadcast functionality will be disabled")

        logger.info(f"🤖 Bot Token: {'*' * (len(BOT_TOKEN) - 8) + BOT_TOKEN[-8:]}")
        logger.info(f"👑 Owner ID: {OWNER_ID}")
        logger.info(f"🔑 Trigger Keyword: {TRIGGER_KEYWORD}")

        app = setup_bot()
        logger.info("✅ Bot is running with anime, echo, and broadcast features 👻")

        # Log initial stats
        logger.info(f"📊 Initial Stats - Users: {len(user_ids)}, Groups: {len(group_ids)}")
        
        print("="*60)
        print("✅ Bot is now running! Press Ctrl+C to stop.")
        print("="*60 + "\n")

        app.run_polling()
        
    except KeyboardInterrupt:
        print("\n" + "="*60)
        logger.info("👋 Bot stopped by user (Ctrl+C)")
        print("👋 Goodbye!")
        print("="*60)
    except telegram.error.InvalidToken:
        logger.critical("💥 Invalid bot token provided")
    except telegram.error.NetworkError as e:
        logger.critical(f"💥 Network error: {e}")
    except Exception as e:
        logger.critical(f"💥 Bot crashed with unexpected error: {e}")
        raise


if __name__ == "__main__":
    try:
        # Start HTTP server in background thread
        server_thread = threading.Thread(target=start_health_server, daemon=True)
        server_thread.start()
        logger.info("✅ HTTP server thread started")
        
        # Start main bot
        main()
        
    except Exception as e:
        logger.critical(f"💥 Critical startup error: {e}")
        exit(1)