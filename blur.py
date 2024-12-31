import os
import time
from pymongo import MongoClient
from telethon import TelegramClient, events, Button
from io import BytesIO
from PIL import Image, ImageFilter
import asyncio
from sqlite3 import connect, OperationalError

# MongoDB Setup
MONGO_URL = "mongodb+srv://manik:manik11@cluster0.iam3w.mongodb.net/?retryWrites=true&w=majority&appName=Cluster0"
client = MongoClient(MONGO_URL)
db = client['your_database_name']  # Replace with your database name
collection = db['photos_collection']  # Collection for photos
collection.create_index([("timestamp", 1)], expireAfterSeconds=2592000)  # TTL: 30 days

# Telegram Bot Setup
api_id = '26980824'
api_hash = 'fb044056059384d3bea54ab7ce915226'
bot_token = '7041654616:AAHqmt9LKjTL9lRAXj8HT_ZkjaWW9I-hz3Q'
CHANNEL_ID = -1002374330304
USER_ID = 817321875  # Replace with your user ID
BLUR_PERCENTAGE = 10
BLUR_DELAY = 60  # Delay in seconds

client = TelegramClient('bot', api_id, api_hash).start(bot_token=bot_token)

forwarded_message_ids = {}

def get_db_connection():
    conn = connect('your_database_name.db')
    conn.execute('PRAGMA journal_mode=WAL')  # Enable WAL mode
    return conn

def execute_with_retry(cursor, query, params=(), retries=5, delay=0.1):
    for attempt in range(retries):
        try:
            cursor.execute(query, params)
            return
        except OperationalError as e:
            if "database is locked" in str(e):
                if attempt < retries - 1:
                    time.sleep(delay)
                else:
                    raise
            else:
                raise

# Helper to blur images
def blur_image(image_data):
    img = Image.open(image_data)
    img = img.convert("RGB")
    blurred_image = img.filter(ImageFilter.GaussianBlur(BLUR_PERCENTAGE))
    temp_file = "temp_blurred.jpg"
    blurred_image.save(temp_file, format="JPEG")
    return temp_file

# Insert photo data into MongoDB
def insert_photo_data(message_id, delay=False, delay_time=None):
    timestamp = int(time.time())
    data = {
        "message_id": message_id,
        "media_type": "photo",
        "timestamp": timestamp,
        "status": "pending",
        "blurred_timestamp": None,
        "delay": delay,
        "delay_time": delay_time,
    }
    collection.insert_one(data)
    print(f"Inserted data for photo with message ID {message_id}")

# Update status to blurred
def update_blurred_status(message_id):
    conn = get_db_connection()
    c = conn.cursor()
    try:
        execute_with_retry(c, "UPDATE photos_collection SET status = ?, blurred_timestamp = ? WHERE message_id = ?",
                           ('blurred', int(time.time()), message_id))
        conn.commit()
    except OperationalError as e:
        print(f"Database error: {e}")
    finally:
        conn.close()
    print(f"Photo with message ID {message_id} marked as blurred")

# Delete photo data
def delete_photo_data(message_id):
    conn = get_db_connection()
    c = conn.cursor()
    try:
        execute_with_retry(c, "DELETE FROM photos_collection WHERE message_id = ?", (message_id,))
        conn.commit()
    except OperationalError as e:
        print(f"Database error: {e}")
    finally:
        conn.close()
    print(f"Photo with message ID {message_id} data deleted from database")

# Forward photo to USER_ID with buttons
@client.on(events.NewMessage(chats=CHANNEL_ID))
async def forward_media_to_user(event):
    if not event.photo:  # Ignore non-photo messages
        print(f"Ignored non-photo message (ID: {event.id})")
        return

    print(f"New photo detected in channel (ID: {event.id})")
    forwarded_msg = await client.forward_messages(USER_ID, event.message)
    print("Photo forwarded to USER_ID")

    blur_button_msg = await client.send_message(
        USER_ID,
        "Photo forwarded to you. Do you want to blur it?",
        buttons=[Button.inline("Blur", data=str(event.id)), Button.inline("Delay Blur", data=f"delay_{event.id}")]
    )

    forwarded_message_ids[event.id] = (forwarded_msg.id, blur_button_msg.id)
    insert_photo_data(event.id)
    await asyncio.sleep(1)  # Delay between sending each message to avoid flooding

# Blur photo instantly
async def blur_photo(msg_id):
    try:
        async for message in client.iter_messages(CHANNEL_ID, ids=msg_id):
            if message and message.photo:
                print(f"Blurring photo for message ID: {msg_id}")
                photo = await message.download_media(file=BytesIO())
                temp_file = blur_image(photo)

                with open(temp_file, 'rb') as f:
                    await client.edit_message(CHANNEL_ID, msg_id, file=f)
                print(f"Photo replaced in channel for message ID: {msg_id}")

                update_blurred_status(msg_id)
                if msg_id in forwarded_message_ids:
                    forwarded_id, button_id = forwarded_message_ids[msg_id]
                    await client.delete_messages(USER_ID, [forwarded_id, button_id])
                    del forwarded_message_ids[msg_id]

                delete_photo_data(msg_id)
                await asyncio.sleep(1)  # Delay between each replacement to avoid overload
            else:
                print(f"No photo found for message ID: {msg_id}")
    except Exception as e:
        print(f"Error blurring photo: {e}")

# Handle Blur button click
@client.on(events.CallbackQuery)
async def handle_callback(event):
    try:
        data = event.data.decode('utf-8')
        if data.isdigit():
            msg_id = int(data)
            print(f"Blur button clicked for message ID: {msg_id}")
            await blur_photo(msg_id)
            await event.answer("Photo blurred successfully!")
        elif data.startswith('delay_'):
            msg_id = int(data.split('_')[1])
            delay_time = int(time.time()) + BLUR_DELAY
            print(f"Delay Blur button clicked for message ID: {msg_id}, scheduled at {delay_time}")
            insert_photo_data(msg_id, delay=True, delay_time=delay_time)
            await event.answer(f"Photo will be blurred after {BLUR_DELAY} seconds!")
    except Exception as e:
        print(f"Error handling callback: {e}")
        await event.answer("Error processing your request.")

# Process delayed blur tasks in batches
async def process_delay_tasks():
    while True:
        current_time = int(time.time())
        tasks = list(collection.find({"delay": True, "delay_time": {"$lte": current_time}}).limit(10))  # Process 10 at a time
        for task in tasks:
            msg_id = task["message_id"]
            print(f"Processing delayed blur for message ID: {msg_id}")
            await blur_photo(msg_id)
            collection.update_one({"message_id": msg_id}, {"$set": {"delay": False}})
        await asyncio.sleep(30)  # Check every 30 seconds

# Start the bot and process delay tasks
async def main():
    await client.start()
    print("Bot started.")
    asyncio.create_task(process_delay_tasks())
    await client.run_until_disconnected()

# Ensure to run main inside asyncio event loop
if __name__ == "__main__":
    loop = asyncio.get_event_loop()  # Ensure the event loop is available
    loop.run_until_complete(main())  # Run the main function correctly
