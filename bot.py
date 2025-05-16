import json
import uuid
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

# File to store messages, media, and approvals
MESSAGE_FILE = "messages.json"
APPROVAL_FILE = "approvals.json"

# Sudo users (replace with actual Telegram user IDs)
SUDO_USERS = [7901884010]  # Add your sudo user IDs here

# Temporary storage for batch and edit
batch_data = {}
edit_data = {}

# Initialize JSON files if they don't exist
def init_storage():
    try:
        with open(MESSAGE_FILE, "x") as f:
            json.dump({}, f)
    except FileExistsError:
        pass
    try:
        with open(APPROVAL_FILE, "x") as f:
            json.dump({}, f)
    except FileExistsError:
        pass

# Save message or media with unique ID
def save_message(unique_id, data):
    try:
        with open(MESSAGE_FILE, "r+") as f:
            db = json.load(f)
            db[unique_id] = data
            f.seek(0)
            f.truncate()
            json.dump(db, f, indent=4)
    except Exception as e:
        print(f"Error saving message: {e}")

# Load message or media by unique ID
def load_message(unique_id):
    try:
        with open(MESSAGE_FILE, "r") as f:
            db = json.load(f)
            return db.get(unique_id, None)
    except Exception as e:
        print(f"Error loading message: {e}")
        return None

# Save approval for user and link
def save_approval(user_id, unique_id):
    try:
        with open(APPROVAL_FILE, "r+") as f:
            db = json.load(f)
            if unique_id not in db:
                db[unique_id] = []
            if user_id not in db[unique_id]:
                db[unique_id].append(user_id)
                f.seek(0)
                f.truncate()
                json.dump(db, f, indent=4)
    except Exception as e:
        print(f"Error saving approval: {e}")

# Check and remove approval after use (one-time)
def check_approval(user_id, unique_id):
    try:
        with open(APPROVAL_FILE, "r+") as f:
            db = json.load(f)
            if unique_id in db and user_id in db[unique_id]:
                db[unique_id].remove(user_id)
                if not db[unique_id]:
                    del db[unique_id]
                f.seek(0)
                f.truncate()
                json.dump(db, f, indent=4)
                return True
            return False
    except Exception as e:
        print(f"Error checking approval: {e}")
        return False

# Check if user is sudo
def is_sudo_user(user_id):
    return user_id in SUDO_USERS

# /start command handler
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    args = context.args
    if args:
        unique_id = args[0]
        # Check approval
        if not check_approval(user_id, unique_id):
            await update.message.reply_text("You are not approved to access this link!")
            return

        data = load_message(unique_id)
        if not data:
            await update.message.reply_text("Message or media not found or expired!")
            return

        # Handle batch or single media
        if data.get("type") == "batch":
            for item in data.get("content", []):
                content_type = item.get("type")
                content = item.get("content")
                caption = item.get("caption", "")
                if content_type == "photo":
                    await update.message.reply_photo(photo=content, caption=caption)
                elif content_type == "video":
                    await update.message.reply_video(video=content, caption=caption)
                elif content_type == "audio":
                    await update.message.reply_audio(audio=content, caption=caption)
                elif content_type == "document":
                    await update.message.reply_document(document=content, caption=caption)
        else:
            content_type = data.get("type")
            content = data.get("content")
            caption = data.get("caption", "")
            if content_type == "text":
                await update.message.reply_text(content)
            elif content_type == "photo":
                await update.message.reply_photo(photo=content, caption=caption)
            elif content_type == "video":
                await update.message.reply_video(video=content, caption=caption)
            elif content_type == "audio":
                await update.message.reply_audio(audio=content, caption=caption)
            elif content_type == "document":
                await update.message.reply_document(document=content, caption=caption)
            else:
                await update.message.reply_text("Unsupported content type!")
    else:
        await update.message.reply_text(
            "Welcome! Only approved links can be accessed. Contact a sudo user for approval."
        )

# /generate command handler for text
async def generate_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    if not is_sudo_user(user_id):
        return  # Ignore non-sudo users

    if not context.args:
        await update.message.reply_text("Please provide a message: /generate <message>")
        return

    message = " ".join(context.args)
    unique_id = str(uuid.uuid4())
    data = {"type": "text", "content": message}
    save_message(unique_id, data)

    bot_username = "@YourBot"  # Replace with your bot's username
    link = f"https://t.me/{bot_username}?start={unique_id}"
    await update.message.reply_text(f"Here is your unique link:\n{link}")

# /batch command handler
async def batch(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    if not is_sudo_user(user_id):
        return  # Ignore non-sudo users

    if not context.args:
        await update.message.reply_text("Please provide a batch name: /batch <name>")
        return

    batch_name = context.args[0]
    batch_data[user_id] = {"name": batch_name, "items": []}
    await update.message.reply_text(f"Batch '{batch_name}' started. Upload media and use /makeit to generate the link.")

# /makeit command handler
async def makeit(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    if not is_sudo_user(user_id):
        return  # Ignore non-sudo users

    if user_id not in batch_data or not batch_data[user_id]["items"]:
        await update.message.reply_text("No batch started or no media uploaded. Use /batch first.")
        return

    unique_id = str(uuid.uuid4())
    data = {"type": "batch", "content": batch_data[user_id]["items"]}
    save_message(unique_id, data)

    bot_username = "@YourBot"  # Replace with your bot's username
    link = f"https://t.me/{bot_username}?start={unique_id}"
    await update.message.reply_text(f"Batch link generated:\n{link}")

    # Clear batch data
    del batch_data[user_id]

# /edit command handler
async def edit(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    if not is_sudo_user(user_id):
        return  # Ignore non-sudo users

    if not context.args:
        await update.message.reply_text("Please provide a bot link: /edit <botlink>")
        return

    bot_link = context.args[0]
    unique_id = bot_link.split("start=")[-1]
    if not load_message(unique_id):
        await update.message.reply_text("Invalid or expired link!")
        return

    edit_data[user_id] = {"unique_id": unique_id, "items": []}
    await update.message.reply_text(f"Editing link {bot_link}. Upload media and use /makeit to update.")

# /a command handler for approval
async def approve(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    if not is_sudo_user(user_id):
        return  # Ignore non-sudo users

    if len(context.args) < 2:
        await update.message.reply_text("Please provide a user ID and bot link: /a <UserID> <botlink>")
        return

    try:
        target_user_id = int(context.args[0])
        bot_link = context.args[1]
        unique_id = bot_link.split("start=")[-1]
        if not load_message(unique_id):
            await update.message.reply_text("Invalid or expired link!")
            return

        save_approval(target_user_id, unique_id)
        await update.message.reply_text(f"User {target_user_id} approved for link {bot_link}.")
    except ValueError:
        await update.message.reply_text("Invalid user ID format!")

# Handler for media (photo, video, audio, document)
async def handle_media(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    if not is_sudo_user(user_id):
        return  # Ignore non-sudo users

    message = update.message
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
        await message.reply_text("Unsupported media type!")
        return

    # Check if user is in batch or edit mode
    if user_id in batch_data:
        batch_data[user_id]["items"].append(data)
        await message.reply_text(f"Media added to batch '{batch_data[user_id]['name']}'. Use /makeit to generate the link.")
    elif user_id in edit_data:
        edit_data[user_id]["items"].append(data)
        await message.reply_text(f"Media added to edit queue. Use /makeit to update the link.")
    else:
        # Single media link generation
        unique_id = str(uuid.uuid4())
        save_message(unique_id, data)
        bot_username = "Tes82u372bot"  # Replace with your bot's username
        link = f"https://t.me/{bot_username}?start={unique_id}"
        await message.reply_text(f"Here is your unique link:\n{link}")

# Handler for non-sudo user messages
async def handle_non_sudo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    if not is_sudo_user(user_id):
        return  # Ignore all non-link-related messages from non-sudo users

# Error handler
async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    print(f"Update {update} caused error {context.error}")
    if update and update.message:
        await update.message.reply_text("An error occurred. Please try again.")

def main():
    # Replace with your bot token from BotFather
    BOT_TOKEN = "8145736202:AAEqjJa62tuj40TPaYehFkAJOVJiQk6doLw"

    # Initialize storage
    init_storage()

    # Create the Application
    application = Application.builder().token(BOT_TOKEN).build()

    # Add handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("generate", generate_text))
    application.add_handler(CommandHandler("batch", batch))
    application.add_handler(CommandHandler("makeit", makeit))
    application.add_handler(CommandHandler("edit", edit))
    application.add_handler(CommandHandler("a", approve))
    application.add_handler(
        MessageHandler(
            filters.PHOTO | filters.VIDEO | filters.AUDIO | filters.Document.ALL,
            handle_media
        )
    )
    application.add_handler(MessageHandler(filters.ALL & ~filters.COMMAND, handle_non_sudo))

    # Add error handler
    application.add_error_handler(error_handler)

    # Start the bot
    print("Bot is running...")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
