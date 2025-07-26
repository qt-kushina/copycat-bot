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

# Logging setup
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Create separate loggers for different components
reaction_logger = logging.getLogger('reactions')
echo_logger = logging.getLogger('echo')
broadcast_logger = logging.getLogger('broadcast')
image_logger = logging.getLogger('image')
api_logger = logging.getLogger('api')

# Enable debug logging for development (comment out for production)
# logging.getLogger().setLevel(logging.DEBUG)

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


async def sendchataction(context, chat_id, action):
    """Send chat action without delay."""
    try:
        logger.debug(f"🎭 Sending chat action '{action}' to chat {chat_id}")
        await context.bot.send_chat_action(chat_id=chat_id, action=action)
        logger.debug(f"✅ Chat action '{action}' sent successfully to chat {chat_id}")
    except telegram.error.Forbidden as e:
        logger.error(f"❌ Forbidden to send chat action to chat {chat_id}: {e}")
    except telegram.error.BadRequest as e:
        logger.error(f"❌ Bad request for chat action to chat {chat_id}: {e}")
    except telegram.error.NetworkError as e:
        logger.error(f"❌ Network error sending chat action to chat {chat_id}: {e}")
    except Exception as e:
        logger.error(f"❌ Unexpected error sending chat action '{action}' to chat {chat_id}: {e}")


def randomemoji():
    """Get a random soft emoji."""
    try:
        emoji = random.choice(SOFT_EMOJIS)
        logger.debug(f"🎲 Selected random emoji: {emoji}")
        return emoji
    except Exception as e:
        logger.error(f"❌ Error selecting random emoji: {e}")
        return "💖"  # fallback emoji


def randomreaction():
    """Get a random reaction emoji."""
    try:
        reaction = random.choice(REACTION_EMOJIS)
        logger.debug(f"🎲 Selected random reaction: {reaction}")
        return reaction
    except Exception as e:
        logger.error(f"❌ Error selecting random reaction: {e}")
        return "👍"  # fallback reaction


def usermention(user):
    """Create a formatted mention string for a user."""
    try:
        if not user:
            logger.warning("⚠️ User object is async def broadcastcontent(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle broadcast message content."""
    try:
        user_id = update.effective_user.id
        broadcast_logger.info(f"📡 Processing broadcast content from user {user_id}")

        # Only handle if user is in broadcast mode
        if user_id not in broadcast_mode:
            broadcast_logger.warning(f"❌ User {user_id} not in broadcast mode")
            return

        target = broadcast_mode.pop(user_id)
        message = update.message
        
        if not message:
            broadcast_logger.error("❌ No message found in broadcast content")
            return
            
        broadcast_logger.info(f"📤 Broadcasting to target: {target}")
        
        # Show different chat actions based on message type
        action_map = {
            'photo': ChatAction.UPLOAD_PHOTO,
            'video': ChatAction.UPLOAD_VIDEO,
            'document': ChatAction.UPLOAD_DOCUMENT,
            'audio': ChatAction.UPLOAD_AUDIO,
            'voice': ChatAction.UPLOAD_VOICE,
            'video_note': ChatAction.UPLOAD_VIDEO_NOTE,
            'sticker': ChatAction.CHOOSE_STICKER,
            'location': ChatAction.FIND_LOCATION
        }
        
        # Determine message type and action
        message_type = "text"
        for msg_type in action_map:
            if getattr(message, msg_type, None):
                message_type = msg_type
                break
                
        chat_action = action_map.get(message_type, ChatAction.TYPING)
        broadcast_logger.debug(f"🎭 Detected message type: {message_type}, using action: {chat_action}")
        
        await sendchataction(context, message.chat_id, chat_action)
        
        # Determine target IDs based on selection
        if target == ", cannot create mention")
            return "Unknown User"
        
        name = f"{user.first_name or ''} {user.last_name or ''}".strip()
        if not name:
            name = "User"
            logger.warning(f"⚠️ User {user.id} has no name, using fallback")
        
        mention = f"<a href='tg://user?id={user.id}'>{name}</a>"
        logger.debug(f"👤 Created mention for user {user.id}: {name}")
        return mention
    except Exception as e:
        logger.error(f"❌ Error creating user mention: {e}")
        return "Unknown User"


async def fetchimage():
    """Fetch a random image from Wallhaven API."""
    try:
        api_logger.info("🌐 Fetching image from Wallhaven API")
        async with aiohttp.ClientSession() as session:
            async with session.get(WALLHAVEN_API_URL) as response:
                if response.status != 200:
                    api_logger.error(f"❌ API returned status {response.status}")
                    return None

                data = await response.json()
                images = data.get("data", [])

                if not images:
                    api_logger.warning("⚠️ No images found in API response")
                    return None

                selected_image = random.choice(images)["path"]
                api_logger.info(f"✅ Successfully fetched image: {selected_image}")
                return selected_image
    except aiohttp.ClientError as e:
        api_logger.error(f"❌ Network error fetching image: {e}")
    except asyncio.TimeoutError as e:
        api_logger.error(f"❌ Timeout error fetching image: {e}")
    except KeyError as e:
        api_logger.error(f"❌ Invalid API response structure: {e}")
    except Exception as e:
        api_logger.error(f"❌ Unexpected error fetching image: {e}")
    return None


async def sendimage(chat_id, user, bot, loading_msg=None, reply_to_message_id=None):
    """Send a welcome image with a personalized message."""
    try:
        image_logger.info(f"📸 Starting image send process for chat {chat_id}, user {user.id if user else 'None'}")
        
        # Show upload photo action
        try:
            await bot.send_chat_action(chat_id=chat_id, action=ChatAction.UPLOAD_PHOTO)
            image_logger.debug(f"✅ Upload photo action sent to chat {chat_id}")
        except Exception as e:
            image_logger.warning(f"⚠️ Failed to send upload photo action to chat {chat_id}: {e}")
        
        image_url = await fetchimage()

        if not image_url:
            error_msg = "⚠️ Failed to get anime image."
            image_logger.error(f"❌ No image URL available for chat {chat_id}")
            
            try:
                if loading_msg:
                    await loading_msg.edit_text(error_msg)
                    image_logger.info(f"✅ Updated loading message with error for chat {chat_id}")
                else:
                    await bot.send_message(chat_id=chat_id, text=error_msg)
                    image_logger.info(f"✅ Sent error message to chat {chat_id}")
            except Exception as e:
                image_logger.error(f"❌ Failed to send error message to chat {chat_id}: {e}")
            return

        mention = usermention(user)
        greeting = random.choice(WELCOME_MESSAGES).format(mention=mention)
        image_logger.debug(f"📝 Generated greeting for user {user.id if user else 'None'}: {greeting[:50]}...")

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
                image_logger.info(f"✅ Successfully updated loading message with image for chat {chat_id}")
            else:
                await bot.send_photo(
                    chat_id=chat_id,
                    photo=image_url,
                    caption=greeting,
                    reply_to_message_id=reply_to_message_id,
                    parse_mode="HTML"
                )
                image_logger.info(f"✅ Successfully sent new image to chat {chat_id}")
        except telegram.error.BadRequest as e:
            image_logger.error(f"❌ Bad request sending image to chat {chat_id}: {e}")
            # Try sending text fallback
            try:
                fallback_msg = f"{greeting}\n\n⚠️ Image failed to load."
                if loading_msg:
                    await loading_msg.edit_text(fallback_msg, parse_mode="HTML")
                else:
                    await bot.send_message(chat_id=chat_id, text=fallback_msg, parse_mode="HTML")
                image_logger.info(f"✅ Sent fallback text message to chat {chat_id}")
            except Exception as fallback_error:
                image_logger.error(f"❌ Fallback message also failed for chat {chat_id}: {fallback_error}")
        except telegram.error.Forbidden as e:
            image_logger.error(f"❌ Forbidden to send image to chat {chat_id}: {e}")
        except telegram.error.NetworkError as e:
            image_logger.error(f"❌ Network error sending image to chat {chat_id}: {e}")
        except Exception as e:
            image_logger.error(f"❌ Unexpected error sending image to chat {chat_id}: {e}")
    except Exception as e:
        image_logger.critical(f"💥 Critical error in sendimage function: {e}")
        raise


async def react(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """React to a message based on chat type and content."""
    try:
        message = update.message
        if not message:
            reaction_logger.warning("⚠️ No message found in update for reaction")
            return

        chat_type = message.chat.type
        bot = context.bot
        emoji = randomreaction()
        lowered = (message.text or "").lower()
        user_id = message.from_user.id if message.from_user else None

        reaction_logger.debug(f"🔍 Checking reaction conditions: chat_type={chat_type}, user_id={user_id}")

        should_react = False

        # Always react in private chats
        if chat_type == "private":
            should_react = True
            reaction_logger.debug("✅ Private chat - will react")
        # In groups, react if keyword is mentioned or replying to bot
        elif chat_type in ["group", "supergroup"]:
            if TRIGGER_KEYWORD in lowered:
                should_react = True
                reaction_logger.debug(f"✅ Keyword '{TRIGGER_KEYWORD}' found - will react")
            elif message.reply_to_message and message.reply_to_message.from_user.id == bot.id:
                should_react = True
                reaction_logger.debug("✅ Reply to bot - will react")

        if should_react:
            try:
                await bot.set_message_reaction(
                    chat_id=message.chat.id,
                    message_id=message.message_id,
                    reaction=[ReactionTypeEmoji(emoji=emoji)]
                )
                reaction_logger.info(f"✅ Reacted with {emoji} to message {message.message_id} in chat {message.chat.id}")
            except telegram.error.BadRequest as e:
                reaction_logger.error(f"❌ Bad request setting reaction: {e}")
            except telegram.error.Forbidden as e:
                reaction_logger.error(f"❌ Forbidden to set reaction in chat {message.chat.id}: {e}")
            except Exception as e:
                reaction_logger.error(f"❌ Unexpected error setting reaction: {e}")
        else:
            reaction_logger.debug("❌ No reaction conditions met")
    except Exception as e:
        reaction_logger.critical(f"💥 Critical error in react function: {e}")


def trackid(chat_id, chat_type):
    """Track user and group IDs."""
    try:
        logger.debug(f"📊 Tracking chat_id={chat_id}, chat_type={chat_type}")
        
        if chat_type == "private":
            if chat_id not in user_ids:
                user_ids.add(chat_id)
                logger.info(f"👤 New user tracked: {chat_id} (Total users: {len(user_ids)})")
            else:
                logger.debug(f"👤 User {chat_id} already tracked")
        elif chat_type in ["group", "supergroup"]:
            if chat_id not in group_ids:
                group_ids.add(chat_id)
                logger.info(f"👥 New group tracked: {chat_id} (Total groups: {len(group_ids)})")
            else:
                logger.debug(f"👥 Group {chat_id} already tracked")
        else:
            logger.warning(f"⚠️ Unknown chat type: {chat_type} for chat {chat_id}")
    except Exception as e:
        logger.error(f"❌ Error tracking chat ID {chat_id}: {e}")


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /start command."""
    try:
        logger.info(f"🚀 /start command received from user {update.effective_user.id}")
        
        await react(update, context)
        user = update.effective_user
        chat_id = update.effective_chat.id

        if not user:
            logger.error("❌ No user found in /start command")
            return

        logger.debug(f"👤 Processing /start for user {user.id} in chat {chat_id}")

        # Initialize user state
        user_button_state[user.id] = {"updates": False, "group": False, "addme": False}
        logger.debug(f"✅ Initialized user state for {user.id}")

        # Track chat ID
        trackid(chat_id, update.effective_chat.type)

        # Send typing action before responding
        await sendchataction(context, chat_id, ChatAction.TYPING)
        
        # Send loading message and then welcome image
        emoji_msg = randomemoji()
        try:
            loading_msg = await context.bot.send_message(chat_id=chat_id, text=emoji_msg)
            logger.debug(f"✅ Sent loading emoji message to chat {chat_id}")
        except Exception as e:
            logger.error(f"❌ Failed to send loading message to chat {chat_id}: {e}")
            return

        await sendimage(chat_id, user, context.bot, loading_msg=loading_msg)
        logger.info(f"✅ /start command completed for user {user.id}")
        
    except Exception as e:
        logger.critical(f"💥 Critical error in /start command: {e}")
        try:
            await update.message.reply_text("⚠️ Something went wrong. Please try again.")
        except:
            pass


async def ping(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /ping command."""
    try:
        user_id = update.effective_user.id if update.effective_user else None
        logger.info(f"🏓 /ping command received from user {user_id}")
        
        await react(update, context)
        
        # Show typing action before ping
        await sendchataction(context, update.effective_chat.id, ChatAction.TYPING)
        
        start_time = time.time()
        try:
            msg = await update.message.reply_text("🛰️ Pinging...")
            logger.debug(f"✅ Sent ping message to chat {update.effective_chat.id}")
        except Exception as e:
            logger.error(f"❌ Failed to send ping message: {e}")
            return
            
        latency = int((time.time() - start_time) * 1000)
        logger.debug(f"📊 Calculated latency: {latency}ms")
        
        try:
            await msg.edit_text(
                f"🏓 <a href='https://t.me/SoulMeetsHQ'>PONG!</a> {latency}ms",
                parse_mode="HTML",
                disable_web_page_preview=True
            )
            logger.info(f"✅ /ping completed with {latency}ms latency for user {user_id}")
        except Exception as e:
            logger.error(f"❌ Failed to edit ping message: {e}")
            
    except Exception as e:
        logger.critical(f"💥 Critical error in /ping command: {e}")
        try:
            await update.message.reply_text("⚠️ Ping failed. Please try again.")
        except:
            pass


async def broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /broadcast command (owner only)."""
    try:
        user_id = update.effective_user.id if update.effective_user else None
        broadcast_logger.info(f"📢 /broadcast command received from user {user_id}")
        
        if user_id != OWNER_ID:
            broadcast_logger.warning(f"⚠️ Unauthorized broadcast attempt from user {user_id}")
            return

        broadcast_logger.info(f"✅ Authorized broadcast request from owner {OWNER_ID}")

        # Show typing action before showing broadcast menu  
        await sendchataction(context, update.effective_chat.id, ChatAction.TYPING)

        keyboard = [
            [InlineKeyboardButton("👤 User", callback_data="broadcast_user"), InlineKeyboardButton("👥 Group", callback_data="broadcast_group")],
            [InlineKeyboardButton("🌐 All", callback_data="broadcast_all"), InlineKeyboardButton("❌ Cancel", callback_data="broadcast_cancel")]
        ]
        
        try:
            await update.message.reply_text("📢 Choose broadcast target:", reply_markup=InlineKeyboardMarkup(keyboard))
            broadcast_logger.info(f"✅ Broadcast menu sent to owner {OWNER_ID}")
        except Exception as e:
            broadcast_logger.error(f"❌ Failed to send broadcast menu: {e}")
            
    except Exception as e:
        broadcast_logger.critical(f"💥 Critical error in /broadcast command: {e}")


async def broadcastchoice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle broadcast target selection."""
    try:
        query = update.callback_query
        user_id = query.from_user.id if query.from_user else None
        broadcast_logger.info(f"🎯 Broadcast choice received: {query.data} from user {user_id}")
        
        if query.data == "broadcast_cancel":
            try:
                await query.answer("Broadcast cancelled!", show_alert=True)
                await query.edit_message_text("❌ Broadcast cancelled.")
                broadcast_logger.info(f"✅ Broadcast cancelled by user {user_id}")
            except Exception as e:
                broadcast_logger.error(f"❌ Failed to handle broadcast cancellation: {e}")
            return

        target_map = {
            "broadcast_user": ("users", "Users selected ✅", "✅ Send the message you want to broadcast to users."),
            "broadcast_group": ("groups", "Groups selected ✅", "✅ Send the message you want to broadcast to groups."),
            "broadcast_all": ("all", "All users and groups selected ✅", "✅ Send the message you want to broadcast to all users and groups.")
        }
        
        if query.data in target_map:
            target, answer_text, edit_text = target_map[query.data]
            try:
                await query.answer(answer_text)
                await query.edit_message_text(edit_text)
                broadcast_mode[query.from_user.id] = target
                broadcast_logger.info(f"✅ Broadcast target '{target}' selected by user {user_id}")
            except Exception as e:
                broadcast_logger.error(f"❌ Failed to handle broadcast choice '{query.data}': {e}")
        else:
            broadcast_logger.warning(f"⚠️ Unknown broadcast choice: {query.data}")
            
    except Exception as e:
        broadcast_logger.critical(f"💥 Critical error in broadcast choice handler: {e}")


async def broadcastcontent(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle broadcast message content."""
    try:
        user_id = update.effective_user.id
        broadcast_logger.info(f"📡 Processing broadcast content from user {user_id}")

        # Only handle if user is in broadcast mode
        if user_id not in broadcast_mode:
            broadcast_logger.warning(f"❌ User {user_id} not in broadcast mode")
            return

        target = broadcast_mode.pop(user_id)
        message = update.message
        
        if not message:
            broadcast_logger.error("❌ No message found in broadcast content")
            return
            
        broadcast_logger.info(f"📤 Broadcasting to target: {target}")
        
        # Show different chat actions based on message type
        action_map = {
            'photo': ChatAction.UPLOAD_PHOTO,
            'video': ChatAction.UPLOAD_VIDEO,
            'document': ChatAction.UPLOAD_DOCUMENT,
            'audio': ChatAction.UPLOAD_AUDIO,
            'voice': ChatAction.UPLOAD_VOICE,
            'video_note': ChatAction.UPLOAD_VIDEO_NOTE,
            'sticker': ChatAction.CHOOSE_STICKER,
            'location': ChatAction.FIND_LOCATION
        }
        
        # Determine message type and action
        message_type = "text"
        for msg_type in action_map:
            if getattr(message, msg_type, None):
                message_type = msg_type
                break
                
        chat_action = action_map.get(message_type, ChatAction.TYPING)
        broadcast_logger.debug(f"🎭 Detected message type: {message_type}, using action: {chat_action}")
        
        await sendchataction(context, message.chat_id, chat_action)
        
        # Determine target IDs based on selection
        if target == "users":
            ids = user_ids
        elif target == "groups":
            ids = group_ids
        elif target == "all":
            ids = user_ids.union(group_ids)
        else:
            broadcast_logger.error(f"❌ Unknown broadcast target: {target}")
            return
        
        count = 0
        failed_count = 0
        total_targets = len(ids)

        broadcast_logger.info(f"📡 Starting broadcast to {total_targets} {target}")

        for cid in list(ids):
            try:
                # Send appropriate chat action for each recipient based on message type
                try:
                    await context.bot.send_chat_action(chat_id=cid, action=chat_action)
                    broadcast_logger.debug(f"✅ Chat action sent to {cid}")
                except Exception as action_error:
                    broadcast_logger.debug(f"⚠️ Chat action failed for {cid}: {action_error}")
                
                await context.bot.copy_message(
                    chat_id=cid,
                    from_chat_id=update.message.chat_id,
                    message_id=update.message.message_id
                )
                count += 1
                broadcast_logger.debug(f"✅ Message sent to {cid} ({count}/{total_targets})")
                await asyncio.sleep(0.05)
                
            except telegram.error.Forbidden as e:
                failed_count += 1
                broadcast_logger.warning(f"❌ Forbidden to send to {cid}: {e}")
            except telegram.error.BadRequest as e:
                failed_count += 1
                broadcast_logger.warning(f"❌ Bad request for {cid}: {e}")
            except telegram.error.NetworkError as e:
                failed_count += 1
                broadcast_logger.warning(f"❌ Network error for {cid}: {e}")
            except Exception as e:
                failed_count += 1
                broadcast_logger.error(f"❌ Unexpected error broadcasting to {cid}: {e}")

        broadcast_logger.info(f"✅ Broadcast completed: {count} successful, {failed_count} failed out of {total_targets}")
        
        # Show typing action before sending completion message
        await sendchataction(context, message.chat_id, ChatAction.TYPING)
        
        try:
            result_text = f"📢 Broadcast sent to {count} {target}."
            if failed_count > 0:
                result_text += f"\n⚠️ {failed_count} failed to receive the message."
            await update.message.reply_text(result_text)
            broadcast_logger.info(f"✅ Broadcast completion message sent")
        except Exception as e:
            broadcast_logger.error(f"❌ Failed to send broadcast completion message: {e}")
            
    except Exception as e:
        broadcast_logger.critical(f"💥 Critical error in broadcast content handler: {e}")
        try:
            await update.message.reply_text("⚠️ Broadcast failed. Please try again.")
        except:
            pass


async def handleecho(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle echo feature for private chats and group replies to bot."""
    try:
        message = update.message
        chat_type = message.chat.type
        user_id = message.from_user.id if message.from_user else None

        echo_logger.debug(f"🔍 Echo check: chat_type={chat_type}, user_id={user_id}")

        # Echo feature for private chats
        if chat_type == "private":
            echo_logger.info(f"🔄 Echo triggered in private chat for user {user_id}")
            await react(update, context)
            
            # Send appropriate chat action based on message type before echoing
            action_map = {
                'photo': ChatAction.UPLOAD_PHOTO,
                'video': ChatAction.UPLOAD_VIDEO,
                'document': ChatAction.UPLOAD_DOCUMENT,
                'audio': ChatAction.UPLOAD_AUDIO,
                'voice': ChatAction.UPLOAD_VOICE,
                'video_note': ChatAction.UPLOAD_VIDEO_NOTE,
                'sticker': ChatAction.CHOOSE_STICKER,
                'location': ChatAction.FIND_LOCATION
            }
            
            # Determine message type and send appropriate action
            message_type = "text"
            for msg_type in action_map:
                if getattr(message, msg_type, None):
                    message_type = msg_type
                    break
                    
            chat_action = action_map.get(message_type, ChatAction.TYPING)
            echo_logger.debug(f"🎭 Private echo: message_type={message_type}, action={chat_action}")
            
            await sendchataction(context, message.chat_id, chat_action)
            
            try:
                await context.bot.copy_message(
                    chat_id=message.chat_id,
                    from_chat_id=message.chat_id,
                    message_id=message.message_id
                )
                echo_logger.info(f"✅ Private echo successful for user {user_id}")
            except telegram.error.BadRequest as e:
                echo_logger.error(f"❌ Bad request in private echo: {e}")
            except telegram.error.Forbidden as e:
                echo_logger.error(f"❌ Forbidden in private echo: {e}")
            except Exception as e:
                echo_logger.error(f"❌ Unexpected error in private echo: {e}")
            return True

        # Echo feature for group replies to bot
        if message.reply_to_message and message.reply_to_message.from_user.id == context.bot.id:
            echo_logger.info(f"🔄 Echo triggered in group for reply to bot from user {user_id}")
            await react(update, context)
            
            # Send appropriate chat action based on message type before echoing
            action_map = {
                'photo': ChatAction.UPLOAD_PHOTO,
                'video': ChatAction.UPLOAD_VIDEO,
                'document': ChatAction.UPLOAD_DOCUMENT,
                'audio': ChatAction.UPLOAD_AUDIO,
                'voice': ChatAction.UPLOAD_VOICE,
                'video_note': ChatAction.UPLOAD_VIDEO_NOTE,
                'sticker': ChatAction.CHOOSE_STICKER,
                'location': ChatAction.FIND_LOCATION
            }
            
            # Determine message type and send appropriate action
            message_type = "text"
            for msg_type in action_map:
                if getattr(message, msg_type, None):
                    message_type = msg_type
                    break
                    
            chat_action = action_map.get(message_type, ChatAction.TYPING)
            echo_logger.debug(f"🎭 Group echo: message_type={message_type}, action={chat_action}")
            
            await sendchataction(context, message.chat_id, chat_action)
            
            try:
                await context.bot.copy_message(
                    chat_id=message.chat_id,
                    from_chat_id=message.chat_id,
                    message_id=message.message_id,
                    reply_to_message_id=message.message_id
                )
                echo_logger.info(f"✅ Group echo successful for user {user_id}")
            except telegram.error.BadRequest as e:
                echo_logger.error(f"❌ Bad request in group echo: {e}")
            except telegram.error.Forbidden as e:
                echo_logger.error(f"❌ Forbidden in group echo: {e}")
            except Exception as e:
                echo_logger.error(f"❌ Unexpected error in group echo: {e}")
            return True

        echo_logger.debug("❌ No echo conditions met")
        return False
        
    except Exception as e:
        echo_logger.critical(f"💥 Critical error in echo handler: {e}")
        return False


async def messagehandler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle all incoming messages - includes echo feature and keyword triggering."""
    try:
        user = update.effective_user
        message = update.message
        if not message:
            logger.debug("❌ No message in update")
            return

        chat_type = message.chat.type
        user_id = user.id if user else None
        chat_id = message.chat_id

        logger.info(f"📥 Message from user {user_id} in {chat_type} chat {chat_id}")

        # Track chat ID
        trackid(message.chat_id, chat_type)

        text = message.text or ""
        lowered = text.lower()

        logger.debug(f"📝 Message text: '{text[:50]}{'...' if len(text) > 50 else ''}'")

        # Handle keyword trigger in any chat
        if TRIGGER_KEYWORD in lowered:
            logger.info(f"🎯 Keyword '{TRIGGER_KEYWORD}' triggered by user {user_id}")
            await react(update, context)
            reply_id = message.message_id if chat_type in ["group", "supergroup"] else None
            
            # Show typing action before sending emoji message
            await sendchataction(context, message.chat_id, ChatAction.TYPING)
            
            try:
                emoji_msg = randomemoji()
                loading_msg = await context.bot.send_message(
                    chat_id=message.chat_id,
                    text=emoji_msg,
                    reply_to_message_id=reply_id
                )
                logger.debug(f"✅ Keyword response emoji sent to chat {chat_id}")
                
                await sendimage(message.chat_id, user, context.bot, loading_msg=loading_msg)
                logger.info(f"✅ Keyword response completed for user {user_id}")
                
            except Exception as e:
                logger.error(f"❌ Error in keyword response: {e}")
            return

        # Handle echo feature
        echo_handled = await handleecho(update, context)
        if echo_handled:
            logger.debug("✅ Message handled by echo feature")
        else:
            logger.debug("ℹ️ Message not handled by any feature")
            
    except Exception as e:
        logger.critical(f"💥 Critical error in message handler: {e}")


async def setcommands(application):
    """Set bot commands in Telegram."""
    try:
        logger.info("⚙️ Setting bot commands")
        await application.bot.set_my_commands([
            ("start", "🎨 Get an image"),
            ("ping", "🏓 Check bot latency")
        ])
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


def setupbot():
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
        app.add_handler(CommandHandler("start", start))
        app.add_handler(CommandHandler("ping", ping))
        app.add_handler(CommandHandler("broadcast", broadcast))
        app.add_handler(CallbackQueryHandler(broadcastchoice, pattern="^broadcast_"))
        logger.info("✅ Command handlers added")

        # Add broadcast handler with custom filter
        broadcast_filter = BroadcastFilter()
        app.add_handler(MessageHandler(
            filters.ALL & (~filters.COMMAND) & broadcast_filter, 
            broadcastcontent
        ))
        logger.info("✅ Broadcast handler added")

        # Add general message handler for echo and keyword features
        app.add_handler(MessageHandler(filters.ALL & (~filters.COMMAND), messagehandler))
        logger.info("✅ Message handler added")

        app.post_init = setcommands
        logger.info("✅ Bot handlers setup complete")
        return app
        
    except Exception as e:
        logger.critical(f"💥 Critical error setting up bot: {e}")
        raise


class DummyHandler(BaseHTTPRequestHandler):
    """HTTP handler for health checks."""

    def do_GET(self):
        try:
            logger.debug("🌐 Health check GET request received")
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"Sakura bot is alive!")
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


def startserver():
    """Start HTTP server for health checks."""
    try:
        logger.info("🌐 Starting HTTP health check server")
        port = int(os.environ.get("PORT", 5000))
        
        server = HTTPServer(("0.0.0.0", port), DummyHandler)
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
        logger.info("🚀 Starting Sakura Bot")
        
        if not BOT_TOKEN:
            logger.critical("💥 BOT_TOKEN environment variable is not set")
            return

        if OWNER_ID == 0:
            logger.warning("⚠️ OWNER_ID not set - broadcast functionality will be disabled")

        logger.info(f"🤖 Bot Token: {'*' * (len(BOT_TOKEN) - 8) + BOT_TOKEN[-8:]}")
        logger.info(f"👑 Owner ID: {OWNER_ID}")
        logger.info(f"🔑 Trigger Keyword: {TRIGGER_KEYWORD}")

        app = setupbot()
        logger.info("✅ Bot is running with anime, echo, and broadcast features 👻")

        # Log initial stats
        logger.info(f"📊 Initial Stats - Users: {len(user_ids)}, Groups: {len(group_ids)}")

        app.run_polling()
        
    except KeyboardInterrupt:
        logger.info("👋 Bot stopped by user (Ctrl+C)")
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
        server_thread = threading.Thread(target=startserver, daemon=True)
        server_thread.start()
        logger.info("✅ HTTP server thread started")
        
        # Start main bot
        main()
        
    except Exception as e:
        logger.critical(f"💥 Critical startup error: {e}")
        exit(1)()
        self.wfile.write(b"Sakura bot is alive!")

    def do_HEAD(self):
        self.send_response(200)
        self.end_headers()

    def log_message(self, format, *args):
        """Suppress HTTP server logs."""
        pass


def startserver():
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

    app = setupbot()
    logger.info("✅ Bot is running with anime, echo, and broadcast 👻")

    try:
        app.run_polling()
    except KeyboardInterrupt:
        logger.info("👋 Bot stopped by user")
    except Exception as e:
        logger.error(f"❌ Bot crashed: {e}")
        raise


if __name__ == "__main__":
    threading.Thread(target=startserver, daemon=True).start()
    main()