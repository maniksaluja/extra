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

logging.basicConfig(
    format='%(asctime)s - %(levelname)s - User: %(user_id)s - Action: %(action)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)
logging.getLogger().handlers[0].setFormatter(
    logging.Formatter('%(asctime)s - %(levelname)s - User: %(user_id)s - Action: %(action)s - %(message)s')
)

BOT_USERNAME = "Tes82u372bot"
SUDO_USERS = [7901884010]
BOT_TOKEN = "7739730998:AAENcYZ9QKYb5VeeW9mF746TJO1aje2KdOA"
MONGO_URI = "mongodb+srv://desi:godfather@cluster0.lw3qhp0.mongodb.net/?retryWrites=true&w=majority&appName=Cluster0"
REDIS_HOST = "localhost"
REDIS_PORT = 6379
REDIS_DB = 0
DB_NAME = "telegram_bot"
MESSAGES_COLLECTION = "messages"
APPROVALS_COLLECTION = "approvals"
SETTINGS_COLLECTION = "settings"
BATCH_SIZE = 100
PROGRESS_UPDATE_INTERVAL = 30
VIDEO_SEND_DELAY = 0.5
DEFAULT_WORKERS = 3

batch_data = {}
edit_data = {}
user_progress = {}
processing_lock = asyncio.Lock()
worker_semaphore = None
pending_messages = {}

try:
    client = MongoClient(MONGO_URI)
    db = client[DB_NAME]
    messages_collection = db[MESSAGES_COLLECTION]
    approvals_collection = db[APPROVALS_COLLECTION]
    settings_collection = db[SETTINGS_COLLECTION]
except ConnectionFailure as e:
    logger.error("MongoDB connection failed", extra={"user_id": "N/A", "action": "db_connect"})
    exit(1)

try:
    redis_client = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, db=REDIS_DB, decode_responses=True)
    redis_client.ping()
except redis.ConnectionError as e:
    logger.error("Redis connection failed", extra={"user_id": "N/A", "action": "db_connect"})
    exit(1)

def init_worker_semaphore():
    global worker_semaphore
    try:
        settings = settings_collection.find_one({"_id": "worker_limit"})
        worker_limit = settings.get("workers", DEFAULT_WORKERS) if settings else DEFAULT_WORKERS
        worker_semaphore = asyncio.Semaphore(worker_limit)
        logger.info(f"Initialized worker semaphore with {worker_limit} workers", extra={"user_id": "N/A", "action": "init_workers"})
    except Exception as e:
        logger.error(f"Init worker semaphore failed: {e}", extra={"user_id": "N/A", "action": "init_workers"})
        worker_semaphore = asyncio.Semaphore(DEFAULT_WORKERS)

init_worker_semaphore()

def save_message(unique_id, data):
    try:
        messages_collection.update_one({"_id": unique_id}, {"$set": data}, upsert=True)
        redis_client.setex(f"message:{unique_id}", 3600, json.dumps(data))
        logger.info(f"Saved message {unique_id}", extra={"user_id": "N/A", "action": "save_message"})
    except Exception as e:
        logger.error(f"Save message failed: {e}", extra={"user_id": "N/A", "action": "save_message"})

def load_message(unique_id):
    try:
        cached = redis_client.get(f"message:{unique_id}")
        if cached:
            return json.loads(cached)
        data = messages_collection.find_one({"_id": unique_id})
        if data:
            redis_client.setex(f"message:{unique_id}", 3600, json.dumps(data))
            logger.info(f"Loaded message {unique_id} from MongoDB", extra={"user_id": "N/A", "action": "load_message"})
        return data
    except Exception as e:
        logger.error(f"Load message failed: {e}", extra={"user_id": "N/A", "action": "load_message"})
        return None

def save_approval(user_id, unique_id):
    try:
        approvals_collection.update_one(
            {"_id": unique_id},
            {"$addToSet": {"users": {"user_id": user_id, "restrict": None}}},
            upsert=True
        )
        logger.info(f"Saved approval for user {user_id} on {unique_id}", extra={"user_id": user_id, "action": "save_approval"})
    except Exception as e:
        logger.error(f"Save approval failed: {e}", extra={"user_id": user_id, "action": "save_approval"})

def save_global_approval(unique_id):
    try:
        approvals_collection.update_one(
            {"_id": unique_id},
            {"$set": {"global_approval": True}},
            upsert=True
        )
        logger.info(f"Saved global approval for {unique_id}", extra={"user_id": "N/A", "action": "save_global_approval"})
    except Exception as e:
        logger.error(f"Save global approval failed: {e}", extra={"user_id": "N/A", "action": "save_global_approval"})

def update_restriction(unique_id, user_id, restrict):
    try:
        approvals_collection.update_one(
            {"_id": unique_id, "users.user_id": user_id},
            {"$set": {"users.$.restrict": restrict}}
        )
        logger.info(f"Updated restriction for user {user_id} on {unique_id}: {restrict}", extra={"user_id": user_id, "action": "update_restriction"})
    except Exception as e:
        logger.error(f"Update restriction failed: {e}", extra={"user_id": user_id, "action": "update_restriction"})

def check_approval(user_id, unique_id):
    try:
        result = approvals_collection.find_one({"_id": unique_id})
        if result:
            if result.get("global_approval", False):
                user_restriction = result.get("default_restrict", False)
                for user in result.get("users", []):
                    if user["user_id"] == user_id:
                        user_restriction = user.get("restrict", False)
                        break
                logger.info(f"Global approval check for user {user_id} on {unique_id}: approved", extra={"user_id": user_id, "action": "check_approval"})
                return True, user_restriction
            for user in result.get("users", []):
                if user["user_id"] == user_id:
                    restrict = user.get("restrict", False)
                    approvals_collection.update_one(
                        {"_id": unique_id},
                        {"$pull": {"users": {"user_id": user_id}}}
                    )
                    if not approvals_collection.find_one({"_id": unique_id})["users"] and not result.get("global_approval", False):
                        approvals_collection.delete_one({"_id": unique_id})
                    logger.info(f"User-specific approval check for user {user_id} on {unique_id}: approved", extra={"user_id": user_id, "action": "check_approval"})
                    return True, restrict
        logger.info(f"No approval for user {user_id} on {unique_id}", extra={"user_id": user_id, "action": "check_approval"})
        return False, False
    except Exception as e:
        logger.error(f"Check approval failed: {e}", extra={"user_id": user_id, "action": "check_approval"})
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
    est_time = remaining * VIDEO_SEND_DELAY
    time_str = format_time_ist(est_time)
    return f"Total: {total}\nSent: {sent} ({percentage:.1f}%)\nTime left: {est_time:.0f}s ({time_str} IST)"

def get_user_id(update: Update):
    if update.message and update.message.from_user:
        return update.message.from_user.id
    elif update.edited_message and update.edited_message.from_user:
        return update.edited_message.from_user.id
    logger.warning("No user ID found", extra={"user_id": "N/A", "action": "get_user_id"})
    return None

def get_all_links():
    try:
        return list(messages_collection.find())
    except Exception as e:
        logger.error(f"Fetch links failed: {e}", extra={"user_id": "N/A", "action": "get_all_links"})
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
    logger.info(f"Link access attempt for {unique_id}", extra={"user_id": user_id, "action": "start"})
    if is_sudo_user(user_id):
        approved, restrict = True, False
    else:
        approved, restrict = check_approval(user_id, unique_id)
        if not approved:
            keyboard = [[InlineKeyboardButton("Plan Type", callback_data="plan_type"), InlineKeyboardButton("Buy", callback_data="buy")]]
            await message.reply_text("You need approval.", reply_markup=InlineKeyboardMarkup(keyboard))
            logger.info("Access denied: not approved", extra={"user_id": user_id, "action": "start"})
            return
    data = load_message(unique_id)
    if not data:
        keyboard = [[InlineKeyboardButton("Plan Type", callback_data="plan_type"), InlineKeyboardButton("Buy", callback_data="buy")]]
        await message.reply_text("Link expired!", reply_markup=InlineKeyboardMarkup(keyboard))
        logger.info("Access denied: link expired", extra={"user_id": user_id, "action": "start"})
        return
    async with processing_lock:
        user_progress[user_id] = {"sent": 0, "last_update": 0}
    pending_msg = None
    if worker_semaphore.locked():
        pending_msg = await message.reply_text("Please wait, processing your request...")
        pending_messages[user_id] = pending_msg.message_id
        logger.info("User queued due to worker limit", extra={"user_id": user_id, "action": "start"})
    async with worker_semaphore:
        logger.info("Worker acquired", extra={"user_id": user_id, "action": "start"})
        if user_id in pending_messages:
            try:
                await context.bot.delete_message(chat_id=message.chat_id, message_id=pending_messages[user_id])
                del pending_messages[user_id]
            except TelegramError as e:
                logger.error(f"Failed to delete pending message: {e}", extra={"user_id": user_id, "action": "start"})
        if data.get("type") == "batch":
            content = data.get("content", [])
            total = len(content)
            sent = 0
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
                        logger.info(f"Sent {content_type} {sent}/{total}", extra={"user_id": user_id, "action": "start"})
                    except TelegramError as e:
                        if "429" in str(e):
                            retry_count += 1
                            if retry_count > max_retries:
                                await message.reply_text("Rate limit exceeded. Please try again later.")
                                logger.error("Rate limit exceeded", extra={"user_id": user_id, "action": "start"})
                                return
                            backoff = VIDEO_SEND_DELAY * (2 ** retry_count)
                            await asyncio.sleep(backoff)
                            continue
                        logger.error(f"Send media failed: {e}", extra={"user_id": user_id, "action": "start"})
                        continue
                    await asyncio.sleep(VIDEO_SEND_DELAY)
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
                logger.info(f"Sent single {content_type}", extra={"user_id": user_id, "action": "start"})
            except TelegramError as e:
                logger.error(f"Send content failed: {e}", extra={"user_id": user_id, "action": "start"})
        async with processing_lock:
            if user_id in user_progress:
                del user_progress[user_id]
        logger.info("Worker released", extra={"user_id": user_id, "action": "start"})

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
    logger.info(f"Generated text link {unique_id}", extra={"user_id": user_id, "action": "generate_text"})

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
    logger.info(f"Started batch {batch_name}", extra={"user_id": user_id, "action": "batch"})

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
        logger.info(f"Created batch link {unique_id}", extra={"user_id": user_id, "action": "make"})
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
        logger.info(f"Updated link {unique_id} with {len(updated_items)} items", extra={"user_id": user_id, "action": "make"})
    else:
        await message.reply_text("No batch/edit started. Use /batch or /edit.")
        logger.info("No batch/edit to make", extra={"user_id": user_id, "action": "make"})

async def edit(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = get_user_id(update)
    if not user_id or not is_sudo_user(user_id):
        return
    message = update.message or update.edited_message
    links = get_all_links()
    if not links:
        await message.reply_text("No links! Use /generate or /batch.")
        logger.info("No links to edit", extra={"user_id": user_id, "action": "edit"})
        return
    keyboard = []
    for link in links:
        unique_id = link["_id"]
        count = len(link.get("content", [])) if link.get("type") == "batch" else 1
        button_text = format_media_count(count)
        keyboard.append([InlineKeyboardButton(button_text, callback_data=f"edit_{unique_id}")])
    await message.reply_text("Select link to edit:", reply_markup=InlineKeyboardMarkup(keyboard))
    logger.info("Displayed links for editing", extra={"user_id": user_id, "action": "edit"})

async def setworkers(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = get_user_id(update)
    if not user_id or not is_sudo_user(user_id):
        return
    message = update.message or update.edited_message
    if not context.args:
        await message.reply_text("Provide number of workers: /setworkers <number>")
        logger.info("No worker number provided", extra={"user_id": user_id, "action": "setworkers"})
        return
    try:
        workers = int(context.args[0])
        if workers < 1:
            await message.reply_text("Number of workers must be at least 1!")
            logger.info("Invalid worker number: less than 1", extra={"user_id": user_id, "action": "setworkers"})
            return
        settings_collection.update_one(
            {"_id": "worker_limit"},
            {"$set": {"workers": workers}},
            upsert=True
        )
        global worker_semaphore
        worker_semaphore = asyncio.Semaphore(workers)
        await message.reply_text(f"Set worker limit to {workers} concurrent users.")
        logger.info(f"Set worker limit to {workers}", extra={"user_id": user_id, "action": "setworkers"})
    except ValueError:
        await message.reply_text("Invalid number! Use /setworkers <number>")
        logger.info("Invalid worker number: not an integer", extra={"user_id": user_id, "action": "setworkers"})

async def approve(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = get_user_id(update)
    if not user_id or not is_sudo_user(user_id):
        return
    message = update.message or update.edited_message
    if not context.args:
        await message.reply_text("Provide UserID or link!")
        logger.info("No UserID or link provided", extra={"user_id": user_id, "action": "approve"})
        return
    arg = context.args[0]
    is_link = arg.startswith(f"https://t.me/{BOT_USERNAME}?start=")
    if is_link:
        try:
            unique_id = arg.split("start=")[1]
            if not load_message(unique_id):
                await message.reply_text("Invalid or expired link!")
                logger.info("Invalid or expired link", extra={"user_id": user_id, "action": "approve"})
                return
            save_global_approval(unique_id)
            keyboard = [
                [InlineKeyboardButton("Yes", callback_data=f"allow_{unique_id}_0"),
                 InlineKeyboardButton("No", callback_data=f"restrict_{unique_id}_0")],
                [InlineKeyboardButton("Share Link", callback_data=f"share_{unique_id}")]
            ]
            await message.reply_text(f"Link approved for all users. Allow forwarding?", reply_markup=InlineKeyboardMarkup(keyboard))
            logger.info(f"Approved link {unique_id} for all users", extra={"user_id": user_id, "action": "approve"})
        except (IndexError, ValueError):
            await message.reply_text("Invalid link format!")
            logger.info("Invalid link format", extra={"user_id": user_id, "action": "approve"})
            return
    else:
        try:
            target_user_id = int(arg)
        except ValueError:
            await message.reply_text("Invalid UserID or link!")
            logger.info("Invalid UserID or link", extra={"user_id": user_id, "action": "approve"})
            return
        links = get_all_links()
        if not links:
            await message.reply_text("No links available!")
            logger.info("No links available", extra={"user_id": user_id, "action": "approve"})
            return
        keyboard = []
        for link in links:
            unique_id = link["_id"]
            count = len(link.get("content", [])) if link.get("type") == "batch" else 1
            button_text = format_media_count(count)
            keyboard.append([InlineKeyboardButton(button_text, callback_data=f"approve_{unique_id}_{target_user_id}")])
        await message.reply_text(f"Select link for user {target_user_id}:", reply_markup=InlineKeyboardMarkup(keyboard))
        logger.info(f"Displayed links for user {target_user_id}", extra={"user_id": user_id, "action": "approve"})

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    await query.answer()
    data = query.data.split("_")
    action = data[0]
    if action == "edit":
        unique_id = data[1]
        if not is_sudo_user(user_id):
            await query.message.edit_text("Only sudo users can edit!")
            logger.info("Edit denied: not sudo user", extra={"user_id": user_id, "action": "button_callback"})
            return
        existing_data = load_message(unique_id)
        if not existing_data:
            await query.message.edit_text("Link expired!")
            logger.info("Edit denied: link expired", extra={"user_id": user_id, "action": "button_callback"})
            return
        edit_data[user_id] = {"unique_id": unique_id, "items": []}
        await query.message.edit_text(f"Editing link {unique_id}. Upload media and /make.")
        logger.info(f"Started editing link {unique_id}", extra={"user_id": user_id, "action": "button_callback"})
    elif action == "approve":
        unique_id = data[1]
        target_user_id = int(data[2])
        if not is_sudo_user(user_id):
            await query.message.edit_text("Only sudo users can approve!")
            logger.info("Approve denied: not sudo user", extra={"user_id": user_id, "action": "button_callback"})
            return
        if not load_message(unique_id):
            await query.message.edit_text("Link expired!")
            logger.info("Approve denied: link expired", extra={"user_id": user_id, "action": "button_callback"})
            return
        save_approval(target_user_id, unique_id)
        keyboard = [
            [InlineKeyboardButton("Yes", callback_data=f"allow_{unique_id}_{target_user_id}"),
             InlineKeyboardButton("No", callback_data=f"restrict_{unique_id}_{target_user_id}")],
            [InlineKeyboardButton("Share Link", callback_data=f"share_{unique_id}")]
        ]
        await query.message.edit_text(f"User {target_user_id} approved. Allow forwarding?", reply_markup=InlineKeyboardMarkup(keyboard))
        logger.info(f"Approved user {target_user_id} for {unique_id}", extra={"user_id": user_id, "action": "button_callback"})
    elif action in ("allow", "restrict"):
        unique_id = data[1]
        target_user_id = int(data[2])
        restrict = action == "restrict"
        if not is_sudo_user(user_id):
            await query.message.edit_text("Only sudo users can modify restrictions!")
            logger.info("Restriction change denied: not sudo user", extra={"user_id": user_id, "action": "button_callback"})
            return
        if target_user_id == 0:
            approvals_collection.update_one(
                {"_id": unique_id},
                {"$set": {"default_restrict": restrict}}
            )
            status = "restricted" if restrict else "allowed"
            keyboard = [[InlineKeyboardButton("Share Link", callback_data=f"share_{unique_id}")]]
            await query.message.edit_text(f"Forwarding {status} for all users.", reply_markup=InlineKeyboardMarkup(keyboard))
            logger.info(f"Set global forwarding {status} for {unique_id}", extra={"user_id": user_id, "action": "button_callback"})
        else:
            update_restriction(unique_id, target_user_id, restrict)
            status = "restricted" if restrict else "allowed"
            keyboard = [[InlineKeyboardButton("Share Link", callback_data=f"share_{unique_id}")]]
            await query.message.edit_text(f"Forwarding {status} for user {target_user_id}.", reply_markup=InlineKeyboardMarkup(keyboard))
            logger.info(f"Set forwarding {status} for user {target_user_id} on {unique_id}", extra={"user_id": user_id, "action": "button_callback"})
    elif action == "share":
        unique_id = data[1]
        share_url = f"https://telegram.me/share/url?url=https://t.me/{BOT_USERNAME}?start={unique_id}"
        await query.message.edit_text(f"Share this link: https://t.me/{BOT_USERNAME}?start={unique_id}", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Share Link", url=share_url)]]))
        logger.info(f"Shared link {unique_id}", extra={"user_id": user_id, "action": "button_callback"})
    elif action in ("plan_type", "buy"):
        await query.message.edit_text(f"Clicked {action}. Contact admin.")
        logger.info(f"Clicked {action}", extra={"user_id": user_id, "action": "button_callback"})

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
    logger.info(f"Handled media upload: {data['type']}", extra={"user_id": user_id, "action": "handle_media"})

async def handle_non_sudo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = get_user_id(update)
    if not user_id or not is_sudo_user(user_id):
        return
    logger.info("Non-sudo message ignored", extra={"user_id": user_id, "action": "handle_non_sudo"})

async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = get_user_id(update) if update else "N/A"
    logger.error(f"Bot error: {context.error}", extra={"user_id": user_id, "action": "error_handler"})
    error_msg = "Something went wrong."
    if update and (update.message or update.edited_message):
        await (update.message.reply_text(error_msg) if update.message else update.edited_message.reply_text(error_msg))

def main():
    try:
        application = Application.builder().token(BOT_TOKEN).read_timeout(30).build()
        application.add_handler(CommandHandler("start", start))
        application.add_handler(CommandHandler("generate", generate_text))
        application.add_handler(CommandHandler("batch", batch))
        application.add_handler(CommandHandler("make", make))
        application.add_handler(CommandHandler("edit", edit))
        application.add_handler(CommandHandler("setworkers", setworkers))
        application.add_handler(CommandHandler("a", approve))
        application.add_handler(CallbackQueryHandler(button_callback))
        application.add_handler(MessageHandler(filters.PHOTO | filters.VIDEO | filters.AUDIO | filters.Document.ALL, handle_media))
        application.add_handler(MessageHandler(filters.ALL & ~filters.COMMAND, handle_non_sudo))
        application.add_error_handler(error_handler)
        logger.info("Bot started", extra={"user_id": "N/A", "action": "main"})
        application.run_polling(allowed_updates=Update.ALL_TYPES)
    except Exception as e:
        logger.error(f"Polling failed: {e}", extra={"user_id": "N/A", "action": "main"})
        time.sleep(5)
        main()

if __name__ == "__main__":
    main()
