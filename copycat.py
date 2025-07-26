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


async def fetch_random_image():
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


async def send_welcome_image(chat_id, user, bot, loading_msg=None, reply_to_message_id=None):
    """Send a welcome image with a personalized message."""
    image_url = await fetch_random_image()
    
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


async def add_reaction_to_message(message, bot):
    """Add a random reaction to a message."""
    try:
        emoji = get_random_reaction()
        await bot.set_message_reaction(
            chat_id=message.chat.id,
            message_id=message.message_id,
            reaction=[ReactionTypeEmoji(emoji=emoji)]
        )
    except Exception as e:
        logger.warning(f"Failed to add reaction: {e}")


def should_react_to_message(message, bot_id):
    """Determine if the bot should react to a message."""
    if not message or not message.text:
        return False
    
    chat_type = message.chat.type
    text_lower = message.text.lower()
    
    # Always react in private chats
    if chat_type == "private":
        return True
    
    # In groups, react if message contains "billu" or is a reply to bot
    if chat_type in ["group", "supergroup"]:
        if "billu" in text_lower:
            return True
        if message.reply_to_message and message.reply_to_message.from_user.id == bot_id:
            return True
    
    return False


def track_chat_id(chat_id, chat_type):
    """Track user and group IDs."""
    if chat_type == "private":
        user_ids.add(chat_id)
    elif chat_type in ["group", "supergroup"]:
        group_ids.add(chat_id)


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /start command."""
    user = update.effective_user
    chat_id = update.effective_chat.id
    chat_type = update.effective_chat.type

    # Initialize user state
    user_button_state[user.id] = {"updates": False, "group": False, "addme": False}
    
    # Track chat ID
    track_chat_id(chat_id, chat_type)
    
    # React to the command
    if should_react_to_message(update.message, context.bot.id):
        await add_reaction_to_message(update.message, context.bot)

    # Send loading message and then welcome image
    loading_msg = await context.bot.send_message(chat_id=chat_id, text=get_random_emoji())
    await send_welcome_image(chat_id, user, context.bot, loading_msg=loading_msg)


async def ping_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /ping command."""
    if should_react_to_message(update.message, context.bot.id):
        await add_reaction_to_message(update.message, context.bot)
    
    start_time = time.time()
    msg = await update.message.reply_text("🛰️ Pinging...")
    latency = int((time.time() - start_time) * 1000)
    
    await msg.edit_text(
        f"🏓 <a href='https://t.me/SoulMeetsHQ'>PONG!</a> {latency}ms",
        parse_mode="HTML",
        disable_web_page_preview=True
    )


async def broadcast_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /broadcast command (owner only)."""
    if update.effective_user.id != OWNER_ID:
        return
    
    keyboard = [
        [InlineKeyboardButton("📬 To Users", callback_data="broadcast_users")],
        [InlineKeyboardButton("👥 To Groups", callback_data="broadcast_groups")],
        [InlineKeyboardButton("❌ Cancel", callback_data="broadcast_cancel")]
    ]
    
    await update.message.reply_text(
        "📢 Choose broadcast target:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


async def handle_broadcast_choice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle broadcast target selection."""
    query = update.callback_query
    await query.answer()
    
    if query.data == "broadcast_cancel":
        await query.edit_message_text("❌ Broadcast cancelled.")
        return
    
    target = "users" if query.data == "broadcast_users" else "groups"
    broadcast_mode[query.from_user.id] = target
    
    await query.edit_message_text(f"✅ Send the message you want to broadcast to {target}.")


async def handle_broadcast_content(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle broadcast message content."""
    user_id = update.effective_user.id
    
    if user_id not in broadcast_mode:
        return
    
    target = broadcast_mode.pop(user_id)
    target_ids = user_ids if target == "users" else group_ids
    
    success_count = 0
    
    for chat_id in list(target_ids):
        try:
            await context.bot.copy_message(
                chat_id=chat_id,
                from_chat_id=update.message.chat_id,
                message_id=update.message.message_id
            )
            success_count += 1
            await asyncio.sleep(0.05)  # Rate limiting
        except Exception as e:
            logger.warning(f"Broadcast to {chat_id} failed: {e}")

    await update.message.reply_text(f"📢 Broadcast sent to {success_count} {target}.")


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle all incoming messages."""
    message = update.message
    if not message:
        return

    user = update.effective_user
    chat_type = message.chat.type
    text_lower = (message.text or "").lower()
    
    # Track chat ID
    track_chat_id(message.chat_id, chat_type)
    
    # Handle "billu" mentions
    if "billu" in text_lower:
        await add_reaction_to_message(message, context.bot)
        
        reply_id = message.message_id if chat_type in ["group", "supergroup"] else None
        loading_msg = await context.bot.send_message(
            chat_id=message.chat_id,
            text=get_random_emoji(),
            reply_to_message_id=reply_id
        )
        await send_welcome_image(message.chat_id, user, context.bot, loading_msg=loading_msg)
        return

    # Handle private messages
    if chat_type == "private":
        if should_react_to_message(message, context.bot.id):
            await add_reaction_to_message(message, context.bot)
        
        try:
            await context.bot.copy_message(
                chat_id=message.chat_id,
                from_chat_id=message.chat_id,
                message_id=message.message_id
            )
        except Exception as e:
            logger.warning(f"Echo failed in private chat: {e}")
        return

    # Handle replies to bot in groups
    if (message.reply_to_message and 
        message.reply_to_message.from_user.id == context.bot.id):
        
        await add_reaction_to_message(message, context.bot)
        
        try:
            await context.bot.copy_message(
                chat_id=message.chat_id,
                from_chat_id=message.chat_id,
                message_id=message.message_id,
                reply_to_message_id=message.message_id
            )
        except Exception as e:
            logger.warning(f"Echo failed in group: {e}")


async def set_bot_commands(application):
    """Set bot commands in Telegram."""
    await application.bot.set_my_commands([
        ("start", "🎨 Get an image"),
        ("ping", "🏓 Check bot latency")
    ])


def create_bot_application():
    """Create and configure the bot application."""
    app = ApplicationBuilder().token(BOT_TOKEN).defaults(Defaults(parse_mode="HTML")).build()
    
    # Add handlers
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("ping", ping_command))
    app.add_handler(CommandHandler("broadcast", broadcast_command))
    app.add_handler(CallbackQueryHandler(handle_broadcast_choice, pattern="^broadcast_"))
    
    # Message handlers
    app.add_handler(MessageHandler(
        filters.ALL & (~filters.COMMAND) & filters.User(user_id=OWNER_ID), 
        handle_broadcast_content
    ))
    app.add_handler(MessageHandler(filters.ALL & (~filters.COMMAND), handle_message))
    
    # Set post-init hook
    app.post_init = set_bot_commands
    
    return app


class HealthCheckHandler(BaseHTTPRequestHandler):
    """HTTP handler for health checks."""
    
    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-type', 'text/plain')
        self.end_headers()
        self.wfile.write(b"Sakura bot is alive!")

    def do_HEAD(self):
        self.send_response(200)
        self.end_headers()

    def log_message(self, format, *args):
        """Suppress HTTP server logs."""
        pass


def start_health_check_server():
    """Start HTTP server for health checks."""
    port = int(os.environ.get("PORT", 5000))
    
    try:
        server = HTTPServer(("0.0.0.0", port), HealthCheckHandler)
        logger.info(f"✅ Health check server started on port {port}")
        server.serve_forever()
    except Exception as e:
        logger.error(f"❌ Failed to start health check server: {e}")
        raise


def main():
    """Main function to run the bot."""
    if not BOT_TOKEN:
        logger.error("❌ BOT_TOKEN environment variable is not set")
        return
    
    # Start health check server in background
    threading.Thread(target=start_health_check_server, daemon=True).start()
    
    # Create and run bot
    app = create_bot_application()
    logger.info("✅ Bot is running with anime, echo, and broadcast features 👻")
    
    try:
        app.run_polling()
    except KeyboardInterrupt:
        logger.info("👋 Bot stopped by user")
    except Exception as e:
        logger.error(f"❌ Bot crashed: {e}")
        raise


if __name__ == "__main__":
    main()