import os
import asyncio
import logging
import random
import time
import aiohttp
import telegram
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReactionTypeEmoji
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler, CallbackQueryHandler,
    filters, ContextTypes, Defaults
)

# Load sensitive values from environment
BOT_TOKEN = os.environ.get("BOT_TOKEN")
OWNER_ID = int(os.environ.get("OWNER_ID", "0"))

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

user_button_state = {}
user_ids = set()
group_ids = set()
broadcast_mode = {}

# Emoji list
soft_emojis = ["⛅", "🌤️", "❣️", "💖", "🌸", "💝", "💘", "💗", "💓", "💞", "❤️‍🔥", "🌹", "🌺", "🌼", "🌷", "💐", "🕊️", "🐱", "🐈", "💌"]

def get_random_emojis(count=1):
    return random.choice(soft_emojis)

# Welcome messages
welcome_messages = [
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

# Fetch random anime image
async def get_random_anime_image():
    url = "https://wallhaven.cc/api/v1/search?q=flower&ratios=16x9&sorting=random&categories=100&purity=100"
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as resp:
            if resp.status != 200:
                return None
            data = await resp.json()
            images = data.get("data", [])
            if not images:
                return None
            return random.choice(images)["path"]

# Send anime wallpaper
async def send_start_image(chat_id, user, bot, loading_msg=None, reply_to_message_id=None):
    image_url = await get_random_anime_image()
    if not image_url:
        if loading_msg:
            await loading_msg.edit_text("⚠️ Failed to get anime image.")
        else:
            await bot.send_message(chat_id=chat_id, text="⚠️ Failed to get anime image.")
        return

    name = f"{user.first_name} {user.last_name or ''}".strip()
    mention = f"<a href='tg://user?id={user.id}'>{name}</a>"
    greeting = random.choice(welcome_messages).format(mention=mention)

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

# React to messages
async def react_to_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.message
    if not message:
        return

    chat_type = message.chat.type
    bot = context.bot
    emoji = get_random_emojis()

    if chat_type == "private":
        try:
            await bot.set_message_reaction(
                chat_id=message.chat.id,
                message_id=message.message_id,
                reaction=[ReactionTypeEmoji(emoji=emoji)]
            )
        except Exception as e:
            logger.warning(f"React failed in private: {e}")
        return

    if chat_type in ["group", "supergroup"] and message.reply_to_message and message.reply_to_message.from_user.id == bot.id:
        try:
            await bot.set_message_reaction(
                chat_id=message.chat.id,
                message_id=message.message_id,
                reaction=[ReactionTypeEmoji(emoji=emoji)]
            )
        except Exception as e:
            logger.warning(f"React failed in group: {e}")

# /start command
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    chat_id = update.effective_chat.id

    user_button_state[user.id] = {"updates": False, "group": False, "addme": False}

    if update.effective_chat.type == "private":
        user_ids.add(chat_id)
    elif update.effective_chat.type in ["group", "supergroup"]:
        group_ids.add(chat_id)

    emoji_msg = get_random_emojis()
    loading_msg = await context.bot.send_message(chat_id=chat_id, text=emoji_msg)
    await send_start_image(chat_id, user, context.bot, loading_msg=loading_msg)

# /ping
async def ping_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    start_time = time.time()
    msg = await update.message.reply_text("🛰️ Pinging...")
    latency = int((time.time() - start_time) * 1000)
    await msg.edit_text(
        f"🏓 <a href='https://t.me/SoulMeetsHQ'>PONG!</a> {latency}ms",
        disable_web_page_preview=True
    )

# /broadcast
async def broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != OWNER_ID:
        return
    keyboard = [
        [InlineKeyboardButton("📬 To Users", callback_data="broadcast_users")],
        [InlineKeyboardButton("👥 To Groups", callback_data="broadcast_groups")],
        [InlineKeyboardButton("❌ Cancel", callback_data="broadcast_cancel")]
    ]
    await update.message.reply_text("📢 Choose broadcast target:", reply_markup=InlineKeyboardMarkup(keyboard))

async def broadcast_choice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if query.data == "broadcast_cancel":
        await query.edit_message_text("❌ Broadcast cancelled.")
        return
    target = "users" if query.data == "broadcast_users" else "groups"
    broadcast_mode[query.from_user.id] = target
    await query.edit_message_text(f"✅ Send the message you want to broadcast to {target}.")

async def broadcast_content(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
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

# Handles incoming messages
async def message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    message = update.message
    if not message:
        return
    if message.chat.type == "private":
        user_ids.add(message.chat_id)
    elif message.chat.type in ["group", "supergroup"]:
        group_ids.add(message.chat_id)
    text = message.text or ""
    lowered = text.lower()
    if "billu" in lowered:
        reply_id = message.message_id if message.chat.type in ["group", "supergroup"] else None
        emoji_msg = get_random_emojis()
        loading_msg = await context.bot.send_message(
            chat_id=message.chat_id,
            text=emoji_msg,
            reply_to_message_id=reply_id
        )
        await send_start_image(message.chat_id, user, context.bot, loading_msg=loading_msg)
        return
    if message.chat.type == "private":
        try:
            await context.bot.copy_message(
                chat_id=message.chat_id,
                from_chat_id=message.chat_id,
                message_id=message.message_id
            )
        except Exception as e:
            logger.warning(f"Echo failed in private: {e}")
        await react_to_message(update, context)
        return
    if message.reply_to_message and message.reply_to_message.from_user.id == context.bot.id:
        try:
            await context.bot.copy_message(
                chat_id=message.chat_id,
                from_chat_id=message.chat_id,
                message_id=message.message_id,
                reply_to_message_id=message.message_id
            )
        except Exception as e:
            logger.warning(f"Echo failed in group: {e}")
    await react_to_message(update, context)

# Set bot commands
async def set_commands(application):
    await application.bot.set_my_commands([
        ("start", "🎨 Get an image")
    ])

# Setup bot
def setup_bot():
    app = ApplicationBuilder().token(BOT_TOKEN).defaults(Defaults(parse_mode="HTML")).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("ping", ping_command))
    app.add_handler(CommandHandler("broadcast", broadcast))
    app.add_handler(CallbackQueryHandler(broadcast_choice, pattern="^broadcast_"))
    app.add_handler(MessageHandler(filters.ALL & (~filters.COMMAND), message_handler))
    app.add_handler(MessageHandler(filters.ALL & filters.User(user_id=OWNER_ID), broadcast_content))
    app.post_init = set_commands
    return app

# Dummy HTTP server
class DummyHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Sakura bot is alive!")

    def do_HEAD(self):
        self.send_response(200)
        self.end_headers()

    def log_message(self, format, *args):
        pass

# Start dummy server
def start_dummy_server():
    logger.info("🌐 Starting HTTP health check server")
    port = int(os.environ.get("PORT", 5000))
    try:
        server = HTTPServer(("0.0.0.0", port), DummyHandler)
        logger.info(f"✅ HTTP server listening on 0.0.0.0:{port}")
        server.serve_forever()
    except Exception as e:
        logger.error(f"❌ Failed to start HTTP server: {e}")
        raise

# Main
def main():
    app = setup_bot()
    logger.info("✅ Bot is running with anime, echo, and broadcast 👻")
    app.run_polling()

if __name__ == "__main__":
    threading.Thread(target=start_dummy_server, daemon=True).start()
    main()
