import json
import uuid
import asyncio
import redis
import time
from datetime import datetime, timedelta
import pytz
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes
from telegram.error import TelegramError
from pymongo import MongoClient
from pymongo.errors import ConnectionFailure

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

BOT_USERNAME = "Tes82u372bot"
SUDO_USERS = [7901884010]
BOT_TOKEN = "8145736202:AAEqjJa62tuj40TPaYehFkAJOVJiQk6doLw"
MONGO_URI = "mongodb+srv://desi:godfather@cluster0.lw3qhp0.mongodb.net/?retryWrites=true&w=majority&appName=Cluster0"
REDIS_HOST = "localhost"
REDIS_PORT = 6379
REDIS_DB = 0
DB_NAME = "telegram_bot"
MESSAGES_COLLECTION = "messages"
APPROVALS_COLLECTION = "approvals"
BATCH_SIZE = 100
PROGRESS_UPDATE_INTERVAL = 30

batch_data = {}
edit_data = {}
user_progress = {}
processing_lock = asyncio.Lock()

try:
    client = MongoClient(MONGO_URI)
    db = client[DB_NAME]
    messages_collection = db[MESSAGES_COLLECTION]
    approvals_collection = db[APPROVALS_COLLECTION]
except ConnectionFailure as e:
    logger.error(f"MongoDB error: {e}")
    exit(1)

try:
    redis_client = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, db=REDIS_DB, decode_responses=True)
    redis_client.ping()
except redis.ConnectionError as e:
    logger.error(f"Redis error: {e}")
    exit(1)

def save_message(unique_id, data):
    try:
        messages_collection.update_one({"_id": unique_id}, {"$set": data}, upsert=True)
        redis_client.setex(f"message:{unique_id}", 3600, json.dumps(data))
    except Exception as e:
        logger.error(f"Save message error: {e}")

def load_message(unique_id):
    try:
        cached = redis_client.get(f"message:{unique_id}")
        if cached:
            return json.loads(cached)
        data = messages_collection.find_one({"_id": unique_id})
        if data:
            redis_client.setex(f"message:{unique_id}", 3600, json.dumps(data))
        return data
    except Exception as e:
        logger.error(f"Load message error: {e}")
        return None

def save_approval(user_id, unique_id):
    try:
        approvals_collection.update_one(
            {"_id": unique_id},
            {"$addToSet": {"users": {"user_id": user_id, "restrict": None}}},
            upsert=True
        )
    except Exception as e:
        logger.error(f"Save approval error: {e}")

def update_restriction(unique_id, user_id, restrict):
    try:
        approvals_collection.update_one(
            {"_id": unique_id, "users.user_id": user_id},
            {"$set": {"users.$.restrict": restrict}}
        )
    except Exception as e:
        logger.error(f"Update restriction error: {e}")

def check_approval(user_id, unique_id):
    try:
        result = approvals_collection.find_one({"_id": unique_id})
        if result:
            for user in result.get("users", []):
                if user["user_id"] == user_id:
                    restrict = user.get("restrict", False)
                    approvals_collection.update_one(
                        {"_id": unique_id},
                        {"$pull": {"users": {"user_id": user_id}}}
                    )
                    if not approvals_collection.find_one({"_id": unique_id})["users"]:
                        approvals_collection.delete_one({"_id": unique_id})
                    return True, restrict
        return False, False
    except Exception as e:
        logger.error(f"Check approval error: {e}")
        return False, False

def is_sudo_user(user_id):
    return user_id in SUDO_USERS

def format_time_ist(seconds):
    ist = pytz.timezone("Asia/Kolkata")
    now = datetime.now(ist)
    future = now + timedelta(seconds=seconds)
    return future.strftime("%I:%M %p")

def get_progress_message(total, sent):
    percentage = (sent / total) * 100 if total > 0 else 0
    remaining = total - sent
    est_time = remaining * 0.1
    time_str = format_time_ist(est_time)
    return f"Total: {total}\nSent: {sent} ({percentage:.1f}%)\nTime left: {est_time:.0f}s ({time_str} IST)"

def get_user_id(update: Update):
    if update.message and update.message.from_user:
        return update.message.from_user.id
    elif update.edited_message and update.edited_message.from_user:
        return update.edited_message.from_user.id
    logger.warning("No user ID")
    return None

def get_all_links():
    try:
        return list(messages_collection.find())
    except Exception as e:
        logger.error(f"Fetch links error: {e}")
        return []

def format_media_count(count):
    if count >= 1000:
        return f"{count // 1000}k"
    return str(count)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = get_user_id(update)
    if not user_id:
        return
    args = context.args
    message = update.message or update.edited_message
    if not args:
        return
    unique_id = args[0]
    if is_sudo_user(user_id):
        approved, restrict = True, False
    else:
        approved, restrict = check_approval(user_id, unique_id)
        if not approved:
            keyboard = [[InlineKeyboardButton("Plan Type", callback_data="plan_type"), InlineKeyboardButton("Buy", callback_data="buy")]]
            await message.reply_text("You need approval.", reply_markup=InlineKeyboardMarkup(keyboard))
            return
    data = load_message(unique_id)
    if not data:
        keyboard = [[InlineKeyboardButton("Plan Type", callback_data="plan_type"), InlineKeyboardButton("Buy", callback_data="buy")]]
        await message.reply_text("Link expired!", reply_markup=InlineKeyboardMarkup(keyboard))
        return
    async with processing_lock:
        user_progress[user_id] = {"sent": 0, "last_update": 0}
    if data.get("type") == "batch":
        content = data.get("content", [])
        total = len(content)
        sent = 0
        base_delay = 0.1
        retry_count = 0
        max_retries = 5
        for i in range(0, total, BATCH_SIZE):
            batch = content[i:i + BATCH_SIZE]
            for item in batch:
                content_type = item.get("type")
                content = item.get("content")
                caption = item.get("caption", "")
                try:
                    if content_type == "photo":
                        await message.reply_photo(photo=content, caption=caption, protect_content=restrict)
                    elif content_type == "video":
                        await message.reply_video(video=content, caption=caption, protect_content=restrict)
                    elif content_type == "audio":
                        await message.reply_audio(audio=content, caption=caption, protect_content=restrict)
                    elif content_type == "document":
                        await message.reply_document(document=content, caption=caption, protect_content=restrict)
                    sent += 1
                    user_progress[user_id]["sent"] = sent
                    retry_count = 0
                except TelegramError as e:
                    if "429" in str(e):
                        retry_count += 1
                        if retry_count > max_retries:
                            return
                        backoff = base_delay * (2 ** retry_count)
                        await asyncio.sleep(backoff)
                        continue
                    logger.error(f"Send media error: {e}")
                    continue
                await asyncio.sleep(base_delay)
    else:
        content_type = data.get("type")
        content = data.get("content")
        caption = data.get("caption", "")
        try:
            if content_type == "text":
                await message.reply_text(content)
            elif content_type == "photo":
                await message.reply_photo(photo=content, caption=caption, protect_content=restrict)
            elif content_type == "video":
                await message.reply_video(video=content, caption=caption, protect_content=restrict)
            elif content_type == "audio":
                await message.reply_audio(audio=content, caption=caption, protect_content=restrict)
            elif content_type == "document":
                await message.reply_document(document=content, caption=caption, protect_content=restrict)
        except TelegramError as e:
            logger.error(f"Send content error: {e}")
    async with processing_lock:
        if user_id in user_progress:
            del user_progress[user_id]

async def generate_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = get_user_id(update)
    if not user_id or not is_sudo_user(user_id):
        return
    message = update.message or update.edited_message
    if not context.args:
        await message.reply_text("Provide message: /generate <message>")
        return
    content = " ".join(context.args)
    unique_id = str(uuid.uuid4())
    data = {"_id": unique_id, "type": "text", "content": content}
    save_message(unique_id, data)
    link = f"https://t.me/{BOT_USERNAME}?start={unique_id}"
    await message.reply_text(f"Link: {link}")

async def batch(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = get_user_id(update)
    if not user_id or not is_sudo_user(user_id):
        return
    message = update.message or update.edited_message
    if not context.args:
        await message.reply_text("Provide batch name: /batch <name>")
        return
    batch_name = context.args[0]
    batch_data[user_id] = {"name": batch_name, "items": []}
    await message.reply_text(f"Batch '{batch_name}' started. Upload media and /make.")

async def make(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = get_user_id(update)
    if not user_id or not is_sudo_user(user_id):
        return
    message = update.message or update.edited_message
    if user_id in batch_data and batch_data[user_id]["items"]:
        unique_id = str(uuid.uuid4())
        data = {"_id": unique_id, "type": "batch", "content": batch_data[user_id]["items"], "name": batch_data[user_id]["name"]}
        save_message(unique_id, data)
        link = f"https://t.me/{BOT_USERNAME}?start={unique_id}"
        await message.reply_text(f"Batch link: {link}")
        del batch_data[user_id]
    elif user_id in edit_data and edit_data[user_id]["items"]:
        unique_id = edit_data[user_id]["unique_id"]
        existing_data = load_message(unique_id)
        existing_items = existing_data.get("content", []) if existing_data and existing_data.get("type") == "batch" else []
        updated_items = existing_items + edit_data[user_id]["items"]
        data = {"_id": unique_id, "type": "batch", "content": updated_items, "name": existing_data.get("name", "")}
        save_message(unique_id, data)
        link = f"https://t.me/{BOT_USERNAME}?start={unique_id}"
        await message.reply_text(f"Link updated: {len(updated_items)} items\n{link}")
        del edit_data[user_id]
    else:
        await message.reply_text("No batch/edit started. Use /batch or /edit.")

async def edit(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = get_user_id(update)
    if not user_id or not is_sudo_user(user_id):
        return
    message = update.message or update.edited_message
    links = get_all_links()
    if not links:
        await message.reply_text("No links! Use /generate or /batch.")
        return
    keyboard = []
    for link in links:
        unique_id = link["_id"]
        count = len(link.get("content", [])) if link.get("type") == "batch" else 1
        button_text = format_media_count(count)
        keyboard.append([InlineKeyboardButton(button_text, callback_data=f"edit_{unique_id}")])
    await message.reply_text("Select link to edit:", reply_markup=InlineKeyboardMarkup(keyboard))

async def approve(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = get_user_id(update)
    if not user_id or not is_sudo_user(user_id):
        return
    message = update.message or update.edited_message
    if context.args:
        try:
            target_user_id = int(context.args[0])
        except ValueError:
            await message.reply_text("Invalid UserID!")
            return
    elif message.forward_from:
        target_user_id = message.forward_from.id
    else:
        await message.reply_text("Provide UserID or forward message!")
        return
    links = get_all_links()
    if not links:
        await message.reply_text("No links available!")
        return
    keyboard = []
    for link in links:
        unique_id = link["_id"]
        count = len(link.get("content", [])) if link.get("type") == "batch" else 1
        button_text = format_media_count(count)
        keyboard.append([InlineKeyboardButton(button_text, callback_data=f"approve_{unique_id}_{target_user_id}")])
    await message.reply_text(f"Select link for user {target_user_id}:", reply_markup=InlineKeyboardMarkup(keyboard))

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data.split("_")
    action = data[0]
    if action == "edit":
        unique_id = data[1]
        user_id = query.from_user.id
        if not is_sudo_user(user_id):
            await query.message.edit_text("Only sudo users can edit!")
            return
        existing_data = load_message(unique_id)
        if not existing_data:
            await query.message.edit_text("Link expired!")
            return
        edit_data[user_id] = {"unique_id": unique_id, "items": []}
        await query.message.edit_text(f"Editing link {unique_id}. Upload media and /make.")
    elif action == "approve":
        unique_id = data[1]
        target_user_id = int(data[2])
        user_id = query.from_user.id
        if not is_sudo_user(user_id):
            await query.message.edit_text("Only sudo users can approve!")
            return
        if not load_message(unique_id):
            await query.message.edit_text("Link expired!")
            return
        save_approval(target_user_id, unique_id)
        keyboard = [
            [InlineKeyboardButton("Yes", callback_data=f"allow_{unique_id}_{target_user_id}"),
             InlineKeyboardButton("No", callback_data=f"restrict_{unique_id}_{target_user_id}")],
            [InlineKeyboardButton("Share Link", callback_data=f"share_{unique_id}")]
        ]
        await query.message.edit_text(f"User {target_user_id} approved. Allow forwarding?", reply_markup=InlineKeyboardMarkup(keyboard))
    elif action in ("allow", "restrict"):
        unique_id = data[1]
        target_user_id = int(data[2])
        restrict = action == "restrict"
        update_restriction(unique_id, target_user_id, restrict)
        status = "restricted" if restrict else "allowed"
        keyboard = [[InlineKeyboardButton("Share Link", callback_data=f"share_{unique_id}")]]
        await query.message.edit_text(f"Forwarding {status} for user {target_user_id}.", reply_markup=InlineKeyboardMarkup(keyboard))
    elif action == "share":
        unique_id = data[1]
        share_url = f"https://telegram.me/share/url?url=https://t.me/{BOT_USERNAME}?start={unique_id}"
        await query.message.edit_text(f"Share this link: https://t.me/{BOT_USERNAME}?start={unique_id}", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Share Link", url=share_url)]]))
    elif action in ("plan_type", "buy"):
        await query.message.edit_text(f"Clicked {action}. Contact admin.")

async def handle_media(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = get_user_id(update)
    if not user_id or not is_sudo_user(user_id):
        return
    message = update.message or update.edited_message
    caption = message.caption or ""
    data = None
    if message.photo:
        file_id = message.photo[-1].file_id
        data = {"type": "photo", "content": file_id, "caption": caption}
    elif message.video:
        file_id = message.video.file_id
        data = {"type": "video", "content": file_id, "caption": caption}
    elif message.audio:
        file_id = message.audio.file_id
        data = {"type": "audio", "content": file_id, "caption": caption}
    elif message.document:
        file_id = message.document.file_id
        data = {"type": "document", "content": file_id, "caption": caption}
    else:
        return
    if user_id in batch_data:
        batch_data[user_id]["items"].append(data)
    elif user_id in edit_data:
        edit_data[user_id]["items"].append(data)
    else:
        unique_id = str(uuid.uuid4())
        save_message(unique_id, {"_id": unique_id, "type": data["type"], "content": data["content"], "caption": caption})
        link = f"https://t.me/{BOT_USERNAME}?start={unique_id}"
        await message.reply_text(f"Link: {link}")

async def handle_non_sudo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = get_user_id(update)
    if not user_id or not is_sudo_user(user_id):
        return

async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.error(f"Error: {context.error}")
    error_msg = "Something went wrong."
    if update and (update.message or update.edited_message):
        await (update.message.reply_text(error_msg) if update.message else update.edited_message.reply_text(error_msg))

def main():
    application = Application.builder().token(BOT_TOKEN).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("generate", generate_text))
    application.add_handler(CommandHandler("batch", batch))
    application.add_handler(CommandHandler("make", make))
    application.add_handler(CommandHandler("edit", edit))
    application.add_handler(CommandHandler("a", approve))
    application.add_handler(CallbackQueryHandler(button_callback))
    application.add_handler(MessageHandler(filters.PHOTO | filters.VIDEO | filters.AUDIO | filters.Document.ALL, handle_media))
    application.add_handler(MessageHandler(filters.ALL & ~filters.COMMAND, handle_non_sudo))
    application.add_error_handler(error_handler)
    logger.info("Bot running...")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
