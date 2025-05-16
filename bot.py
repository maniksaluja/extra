import json
import uuid
import asyncio
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes
from pymongo import MongoClient
from pymongo.errors import ConnectionError

# Configuration Section
BOT_USERNAME = "Tes82u372bot"  # Replace with your bot's username
SUDO_USERS = [7901884010]  # Replace with your sudo user IDs
BOT_TOKEN = "8145736202:AAEqjJa62tuj40TPaYehFkAJOVJiQk6doLw"  # Replace with your bot token
MONGO_URI = "mongodb+srv://desi:godfather@cluster0.lw3qhp0.mongodb.net/?retryWrites=true&w=majority&appName=Cluster0"  # Replace with your MongoDB URI (e.g., MongoDB Atlas URI)
DB_NAME = "telegram_bot"
MESSAGES_COLLECTION = "messages"
APPROVALS_COLLECTION = "approvals"

# Temporary storage for batch and edit
batch_data = {}
edit_data = {}

# MongoDB client setup
try:
    client = MongoClient(MONGO_URI)
    db = client[DB_NAME]
    messages_collection = db[MESSAGES_COLLECTION]
    approvals_collection = db[APPROVALS_COLLECTION]
except ConnectionError as e:
    print(f"Error connecting to MongoDB: {e}")
    exit(1)

# Save message or media with unique ID
def save_message(unique_id, data):
    try:
        messages_collection.update_one(
            {"_id": unique_id},
            {"$set": data},
            upsert=True
        )
    except Exception as e:
        print(f"Error saving message: {e}")

# Load message or media by unique ID
def load_message(unique_id):
    try:
        return messages_collection.find_one({"_id": unique_id})
    except Exception as e:
        print(f"Error loading message: {e}")
        return None

# Save approval for user and link
def save_approval(user_id, unique_id):
    try:
        approvals_collection.update_one(
            {"_id": unique_id},
            {"$addToSet": {"users": {"user_id": user_id, "restrict": None}}},
            upsert=True
        )
    except Exception as e:
        print(f"Error saving approval: {e}")

# Update restriction setting
def update_restriction(unique_id, user_id, restrict):
    try:
        approvals_collection.update_one(
            {"_id": unique_id, "users.user_id": user_id},
            {"$set": {"users.$.restrict": restrict}}
        )
    except Exception as e:
        print(f"Error updating restriction: {e}")

# Check and remove approval after use (one-time)
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
        print(f"Error checking approval: {e}")
        return False, False

# Check if user is sudo
def is_sudo_user(user_id):
    return user_id in SUDO_USERS

# /start command handler with rate limiting
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    args = context.args
    if args:
        unique_id = args[0]
        # Check approval and restriction
        approved, restrict = check_approval(user_id, unique_id)
        if not approved:
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
                try:
                    if content_type == "photo":
                        await update.message.reply_photo(
                            photo=content, caption=caption, protect_content=restrict
                        )
                    elif content_type == "video":
                        await update.message.reply_video(
                            video=content, caption=caption, protect_content=restrict
                        )
                    elif content_type == "audio":
                        await update.message.reply_audio(
                            audio=content, caption=caption, protect_content=restrict
                        )
                    elif content_type == "document":
                        await update.message.reply_document(
                            document=content, caption=caption, protect_content=restrict
                        )
                    # Add delay to prevent flood wait
                    await asyncio.sleep(0.1)  # 100ms delay between messages
                except Exception as e:
                    print(f"Error sending media: {e}")
                    await update.message.reply_text("Error sending some media.")
        else:
            content_type = data.get("type")
            content = data.get("content")
            caption = data.get("caption", "")
            try:
                if content_type == "text":
                    await update.message.reply_text(content)
                elif content_type == "photo":
                    await update.message.reply_photo(
                        photo=content, caption=caption, protect_content=restrict
                    )
                elif content_type == "video":
                    await update.message.reply_video(
                        video=content, caption=caption, protect_content=restrict
                    )
                elif content_type == "audio":
                    await update.message.reply_audio(
                        audio=content, caption=caption, protect_content=restrict
                    )
                elif content_type == "document":
                    await update.message.reply_document(
                        document=content, caption=caption, protect_content=restrict
                    )
                else:
                    await update.message.reply_text("Unsupported content type!")
            except Exception as e:
                print(f"Error sending content: {e}")
                await update.message.reply_text("Error sending content.")
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
    data = {"_id": unique_id, "type": "text", "content": message}
    save_message(unique_id, data)

    link = f"https://t.me/{BOT_USERNAME}?start={unique_id}"
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
    await update.message.reply_text(f"Batch '{batch_name}' started. Upload media and use /make to generate the link.")

# /make command handler
async def make(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    if not is_sudo_user(user_id):
        return  # Ignore non-sudo users

    if user_id in batch_data and batch_data[user_id]["items"]:
        unique_id = str(uuid.uuid4())
        data = {"_id": unique_id, "type": "batch", "content": batch_data[user_id]["items"]}
        save_message(unique_id, data)
        link = f"https://t.me/{BOT_USERNAME}?start={unique_id}"
        await update.message.reply_text(f"Batch link generated:\n{link}")
        del batch_data[user_id]
    elif user_id in edit_data and edit_data[user_id]["items"]:
        unique_id = edit_data[user_id]["unique_id"]
        data = {"_id": unique_id, "type": "batch", "content": edit_data[user_id]["items"]}
        save_message(unique_id, data)
        link = f"https://t.me/{BOT_USERNAME}?start={unique_id}"
        await update.message.reply_text(f"Link updated:\n{link}")
        del edit_data[user_id]
    else:
        await update.message.reply_text("No batch or edit started, or no media uploaded. Use /batch or /edit first.")

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
    await update.message.reply_text(f"Editing link {bot_link}. Upload media and use /make to update.")

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

        # Send message to approved user with buttons
        keyboard = [
            [
                InlineKeyboardButton("Yes", callback_data=f"allow_{unique_id}_{target_user_id}"),
                InlineKeyboardButton("No", callback_data=f"restrict_{unique_id}_{target_user_id}")
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await context.bot.send_message(
            chat_id=target_user_id,
            text="You have been approved for a link. Do you want to allow forwarding and downloading?",
            reply_markup=reply_markup
        )
    except ValueError:
        await update.message.reply_text("Invalid user ID format!")
    except Exception as e:
        print(f"Error sending approval message: {e}")
        await update.message.reply_text("Error notifying the user.")

# Callback query handler for Yes/No buttons
async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    data = query.data.split("_")
    action, unique_id, user_id = data[0], data[1], int(data[2])

    if action == "allow":
        update_restriction(unique_id, user_id, False)
        await query.message.edit_text("You allowed forwarding and downloading for this link.")
    elif action == "restrict":
        update_restriction(unique_id, user_id, True)
        await query.message.edit_text("Forwarding, downloading, and saving are restricted for this link.")

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
        return  # Ignore unsupported media types

    # Add to batch or edit data
    if user_id in batch_data:
        batch_data[user_id]["items"].append(data)
    elif user_id in edit_data:
        edit_data[user_id]["items"].append(data)
    else:
        # Single media link generation
        unique_id = str(uuid.uuid4())
        save_message(unique_id, {"_id": unique_id, "type": data["type"], "content": data["content"], "caption": caption})
        link = f"https://t.me/{BOT_USERNAME}?start={unique_id}"
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
    # Create the Application with rate limiting
    application = Application.builder().token(BOT_TOKEN).build()

    # Add handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("generate", generate_text))
    application.add_handler(CommandHandler("batch", batch))
    application.add_handler(CommandHandler("make", make))
    application.add_handler(CommandHandler("edit", edit))
    application.add_handler(CommandHandler("a", approve))
    application.add_handler(CallbackQueryHandler(button_callback))
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
