import os
import asyncio
import logging
import random
import time
import aiohttp
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
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

welcome_messages = [
    "Hey {mention}, take a look at this masterpiece! 🎨",
    "This one's for you, {mention}. Hope you like it! 😄",
    "{mention}, here’s something special I found just for you! ✨",
    "Feast your eyes on this beauty, {mention}! 👁️",
    "A fresh anime wallpaper for you, {mention}. Enjoy! 🍥",
    "{mention}, how about this one? Looks amazing, right? 😍",
    "This one reminded me of your vibe, {mention}. 😎",
    "Another awesome pick just dropped, {mention}. Take a look! 🎴",
    "{mention}, you’ve got to see this one. It’s fire! 🔥",
    "This wallpaper screams perfection. What do you think, {mention}? 💯",
    "Get ready, {mention}. This one is absolutely stunning! 💫",
    "{mention}, you deserve the best. Check this out! 💎",
    "Let’s add some charm to your screen, {mention}. 🎇",
    "An aesthetic moment just for you, {mention}. 🖼️",
    "{mention}, catch this beauty before it disappears! 🌠",
    "Take a break and enjoy this view, {mention}. 🌄",
    "This image made me think of you, {mention}. Isn’t it awesome? 💭",
    "{mention}, you’re going to love this anime shot! 📸",
    "Dive into the anime world with this, {mention}! 🌊",
    "{mention}, this one belongs on your home screen. 📱",
    "{mention}, boost your vibe with this wallpaper! ⚡",
    "Brace yourself, {mention}. This one's stunning! 🌀",
    "A dose of anime aesthetics coming your way, {mention}! 🌸",
    "Freshly picked and pixel-perfect for you, {mention}. 🧩",
    "{mention}, your wallpaper game just got stronger! 💪",
    "Step into the scene with this one, {mention}. 🎬",
    "Feeling the anime energy with this, aren’t you {mention}? 🔋",
    "Get lost in the art, {mention}. It’s a vibe. 🎭",
    "{mention}, this one's a straight 10/10. 🌟",
    "A new masterpiece has arrived for you, {mention}. 🚀"
]

async def get_random_anime_image():
    url = "https://wallhaven.cc/api/v1/search?q=anime&ratios=16x9&sorting=random&categories=100&purity=100"
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as resp:
            if resp.status != 200:
                return None
            data = await resp.json()
            images = data.get("data", [])
            if not images:
                return None
            return random.choice(images)["path"]

async def send_start_image(chat_id, user, bot, reply_to_message_id=None):
    image_url = await get_random_anime_image()
    if not image_url:
        await bot.send_message(chat_id=chat_id, text="⚠️ Failed to get anime image.")
        return

    name = f"{user.first_name} {user.last_name or ''}".strip()
    mention = f"<a href='tg://user?id={user.id}'>{name}</a>"
    greeting = random.choice(welcome_messages).format(mention=mention)

    await bot.send_photo(
        chat_id=chat_id,
        photo=image_url,
        caption=greeting,
        reply_to_message_id=reply_to_message_id
    )

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    chat_id = update.effective_chat.id

    user_button_state[user.id] = {"updates": False, "group": False, "addme": False}

    if update.effective_chat.type == "private":
        user_ids.add(chat_id)
    elif update.effective_chat.type in ["group", "supergroup"]:
        group_ids.add(chat_id)

    await send_start_image(chat_id, user, context.bot)

async def ping_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    start_time = time.time()
    msg = await update.message.reply_text("🛰️ Pinging...")
    latency = int((time.time() - start_time) * 1000)
    await msg.edit_text(
        f"🏓 <a href='https://t.me/TheCryptoElders'>PONG!</a> Bot responded in <b>{latency}ms</b> ⚡"
    )

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
        except Exception as e:
            logger.warning(f"Broadcast to {cid} failed: {e}")

    await update.message.reply_text(f"📢 Broadcast sent to {count} {target}.")

async def message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    message = update.message

    if not message:
        return

    text = message.text or ""
    lowered = text.lower()

    if "fuckrupa" in lowered:
        await send_start_image(message.chat_id, user, context.bot)
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

async def set_commands(application):
    await application.bot.set_my_commands([
        ("start", "Start bot and get anime image")
    ])

def setup_bot():
    app = ApplicationBuilder().token(BOT_TOKEN).defaults(Defaults(parse_mode="HTML")).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("ping", ping_command))
    app.add_handler(CommandHandler("broadcast", broadcast))
    app.add_handler(CallbackQueryHandler(broadcast_choice, pattern="^broadcast_"))
    app.add_handler(MessageHandler(filters.ALL & filters.User(user_id=OWNER_ID), broadcast_content))
    app.add_handler(MessageHandler(filters.ALL & (~filters.COMMAND), message_handler))
    app.post_init = set_commands
    return app

class DummyHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        logger.debug(f"🌐 HTTP GET request from {self.client_address[0]}")
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Sakura bot is alive!")

    def do_HEAD(self):
        self.send_response(200)
        self.end_headers()

    def log_message(self, format, *args):
        pass  # silence default logs

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

def main():
    app = setup_bot()
    logger.info("✅ Bot is running with anime, echo, and broadcast 👻")
    app.run_polling()

if __name__ == "__main__":
    logger.debug("🧵 Starting health check server thread")
    threading.Thread(target=start_dummy_server, daemon=True).start()
    logger.debug("🧵 Health check server thread started")
    main()