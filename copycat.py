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
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler, CallbackQueryHandler,
    filters, ContextTypes, Defaults
)

# Configuration
BOT_TOKEN = os.environ.get("BOT_TOKEN")
OWNER_ID = int(os.environ.get("OWNER_ID", "0"))

# Logging setup
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Bot state storage
user_button_state = {}
user_ids = set()
group_ids = set()
broadcast_mode = {}

# Constants
SOFT_EMOJIS = [
    "⛅", "🌤️", "❣️", "💖", "🌸", "💝", "💘", "💗", "💓", "💞", 
    "❤️‍🔥", "🌹", "🌺", "🌼", "🌷", "💐", "🕊️", "🐱", "🐈", "💌"
]

REACTION_EMOJIS = ["👍", "❤️", "🔥", "😁", "🆒"]

TRIGGER_KEYWORD = "billu"  # Group triggering keyword

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

WALLHAVEN_API_URL = "https://wallhaven.cc/api/v1/search?q=flower&ratios=16x9&sorting=random&categories=100&purity=100"


def get_random_emoji():
    """Get a random soft emoji."""
    return random.choice(SOFT_EMOJIS)


def get_random_reaction():
    """Get a random reaction emoji."""
    return random.choice(REACTION_EMOJIS)


def create_user_mention(user):
    """Create a formatted mention string for a user."""
    name = f"{user.first_name} {user.last_name or ''}".strip()
    return f"<a href='tg://user?id={user.id}'>{name}</a>"


async def get_random_anime_image():
    """Fetch a random image from Wallhaven API."""
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(WALLHAVEN_API_URL) as response:
                if response.status != 200:
                    logger.warning(f"API returned status {response.status}")
                    return None
                
                data = await response.json()
                images = data.get("data", [])
                
                if not images:
                    logger.warning("No images found in API response")
                    return None
                
                return random.choice(images)["path"]
    except Exception as e:
        logger.error(f"Error fetching image: {e}")
        return None


async def send_start_image(chat_id, user, bot, loading_msg=None, reply_to_message_id=None):
    """Send a welcome image with a personalized message."""
    image_url = await get_random_anime_image()
    
    if not image_url:
        error_msg = "⚠️ Failed to get anime image."
        if loading_msg:
            await loading_msg.edit_text(error_msg)
        else:
            await bot.send_message(chat_id=chat_id, text=error_msg)
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
        else:
            await bot.send_photo(
                chat_id=chat_id,
                photo=image_url,
                caption=greeting,
                reply_to_message_id=reply_to_message_id,
                parse_mode="HTML"
            )
    except Exception as e:
        logger.error(f"Error sending welcome image: {e}")


async def react_to_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """React to a message based on chat type and content."""
    message = update.message
    if not message:
        return

    chat_type = message.chat.type
    bot = context.bot
    emoji = get_random_reaction()
    lowered = (message.text or "").lower()

    should_react = False

    # Always react in private chats
    if chat_type == "private":
        should_react = True
    # In groups, react if keyword is mentioned or replying to bot
    elif chat_type in ["group", "supergroup"]:
        if TRIGGER_KEYWORD in lowered:
            should_react = True
        elif message.reply_to_message and message.reply_to_message.from_user.id == bot.id:
            should_react = True

    if should_react:
        try:
            await bot.set_message_reaction(
                chat_id=message.chat.id,
                message_id=message.message_id,
                reaction=[ReactionTypeEmoji(emoji=emoji)]
            )
        except Exception as e:
            logger.warning(f"React failed: {e}")


def track_chat_id(chat_id, chat_type):
    """Track user and group IDs."""
    if chat_type == "private":
        user_ids.add(chat_id)
    elif chat_type in ["group", "supergroup"]:
        group_ids.add(chat_id)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /start command."""
    await react_to_message(update, context)
    user = update.effective_user
    chat_id = update.effective_chat.id

    # Initialize user state
    user_button_state[user.id] = {"updates": False, "group": False, "addme": False}

    # Track chat ID
    track_chat_id(chat_id, update.effective_chat.type)

    # Send loading message and then welcome image
    emoji_msg = get_random_emoji()
    loading_msg = await context.bot.send_message(chat_id=chat_id, text=emoji_msg)
    await send_start_image(chat_id, user, context.bot, loading_msg=loading_msg)


async def ping_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /ping command."""
    await react_to_message(update, context)
    start_time = time.time()
    msg = await update.message.reply_text("🛰️ Pinging...")
    latency = int((time.time() - start_time) * 1000)
    await msg.edit_text(
        f"🏓 <a href='https://t.me/SoulMeetsHQ'>PONG!</a> {latency}ms",
        parse_mode="HTML",
        disable_web_page_preview=True
    )


async def broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /broadcast command (owner only)."""
    if update.effective_user.id != OWNER_ID:
        return
    
    keyboard = [
        [InlineKeyboardButton("📬 To Users", callback_data="broadcast_users")],
        [InlineKeyboardButton("👥 To Groups", callback_data="broadcast_groups")],
        [InlineKeyboardButton("❌ Cancel", callback_data="broadcast_cancel")]
    ]
    await update.message.reply_text("📢 Choose broadcast target:", reply_markup=InlineKeyboardMarkup(keyboard))


async def broadcast_choice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle broadcast target selection."""
    query = update.callback_query
    await query.answer()
    
    if query.data == "broadcast_cancel":
        await query.edit_message_text("❌ Broadcast cancelled.")
        return
    
    target = "users" if query.data == "broadcast_users" else "groups"
    broadcast_mode[query.from_user.id] = target
    await query.edit_message_text(f"✅ Send the message you want to broadcast to {target}.")


async def broadcast_content(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle broadcast message content."""
    user_id = update.effective_user.id
    
    # Only handle if user is in broadcast mode
    if user_id not in broadcast_mode:
        return
    
    target = broadcast_mode.pop(user_id)
    ids = user_ids if target == "users" else group_ids
    count = 0
    
    for cid in list(ids):
        try:
            await context.bot.copy_message(
                chat_id=cid,
                from_chat_id=update.message.chat_id,
                message_id=update.message.message_id
            )
            count += 1
            await asyncio.sleep(0.05)
        except Exception as e:
            logger.warning(f"Broadcast to {cid} failed: {e}")
    
    await update.message.reply_text(f"📢 Broadcast sent to {count} {target}.")


async def handle_echo_feature(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle echo feature for private chats and group replies to bot."""
    message = update.message
    chat_type = message.chat.type
    
    # Echo feature for private chats
    if chat_type == "private":
        await react_to_message(update, context)
        try:
            await context.bot.copy_message(
                chat_id=message.chat_id,
                from_chat_id=message.chat_id,
                message_id=message.message_id
            )
        except Exception as e:
            logger.warning(f"Echo failed in private: {e}")
        return True

    # Echo feature for group replies to bot
    if message.reply_to_message and message.reply_to_message.from_user.id == context.bot.id:
        await react_to_message(update, context)
        try:
            await context.bot.copy_message(
                chat_id=message.chat_id,
                from_chat_id=message.chat_id,
                message_id=message.message_id,
                reply_to_message_id=message.message_id
            )
        except Exception as e:
            logger.warning(f"Echo failed in group: {e}")
        return True
    
    return False


async def message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle all incoming messages - includes echo feature and keyword triggering."""
    user = update.effective_user
    message = update.message
    if not message:
        return

    chat_type = message.chat.type
    
    # Track chat ID
    track_chat_id(message.chat_id, chat_type)
    
    text = message.text or ""
    lowered = text.lower()

    # Handle keyword trigger in any chat
    if TRIGGER_KEYWORD in lowered:
        await react_to_message(update, context)
        reply_id = message.message_id if chat_type in ["group", "supergroup"] else None
        emoji_msg = get_random_emoji()
        loading_msg = await context.bot.send_message(
            chat_id=message.chat_id,
            text=emoji_msg,
            reply_to_message_id=reply_id
        )
        await send_start_image(message.chat_id, user, context.bot, loading_msg=loading_msg)
        return

    # Handle echo feature
    await handle_echo_feature(update, context)


async def set_commands(application):
    """Set bot commands in Telegram."""
    await application.bot.set_my_commands([
        ("start", "🎨 Get an image"),
        ("ping", "🏓 Check bot latency")
    ])


def setup_bot():
    """Create and configure the bot application."""
    app = ApplicationBuilder().token(BOT_TOKEN).defaults(Defaults(parse_mode="HTML")).build()
    
    # Add command handlers
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("ping", ping_command))
    app.add_handler(CommandHandler("broadcast", broadcast))
    app.add_handler(CallbackQueryHandler(broadcast_choice, pattern="^broadcast_"))
    
    # Add broadcast handler with specific condition to avoid conflicts
    def broadcast_filter(update):
        """Filter for broadcast content - only when user is in broadcast mode."""
        user_id = update.effective_user.id if update.effective_user else None
        return user_id == OWNER_ID and user_id in broadcast_mode
    
    app.add_handler(MessageHandler(
        filters.ALL & (~filters.COMMAND) & filters.UpdateType.MESSAGE & broadcast_filter, 
        broadcast_content
    ))
    
    # Add general message handler for echo and keyword features
    app.add_handler(MessageHandler(filters.ALL & (~filters.COMMAND), message_handler))
    
    app.post_init = set_commands
    return app


class DummyHandler(BaseHTTPRequestHandler):
    """HTTP handler for health checks."""
    
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Sakura bot is alive!")

    def do_HEAD(self):
        self.send_response(200)
        self.end_headers()

    def log_message(self, format, *args):
        """Suppress HTTP server logs."""
        pass


def start_dummy_server():
    """Start HTTP server for health checks."""
    logger.info("🌐 Starting HTTP health check server")
    port = int(os.environ.get("PORT", 5000))
    try:
        server = HTTPServer(("0.0.0.0", port), DummyHandler)
        logger.info(f"✅ HTTP server listening on 0.0.0.0:{port}")
        server.serve_forever()
    except Exception as e:
        logger.error(f"❌ Failed to start HTTP server: {e}")
        raise


def main():
    """Main function to run the bot."""
    if not BOT_TOKEN:
        logger.error("❌ BOT_TOKEN environment variable is not set")
        return
    
    app = setup_bot()
    logger.info("✅ Bot is running with anime, echo, and broadcast 👻")
    
    try:
        app.run_polling()
    except KeyboardInterrupt:
        logger.info("👋 Bot stopped by user")
    except Exception as e:
        logger.error(f"❌ Bot crashed: {e}")
        raise


if __name__ == "__main__":
    threading.Thread(target=start_dummy_server, daemon=True).start()
    main()