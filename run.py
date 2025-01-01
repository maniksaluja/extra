from pyrogram import Client

# Replace with your actual API credentials
api_id = 24417722  # Replace with your API ID
api_hash = "68c75f726da6bd11acda8d7cd03e89f3"  # Replace with your API Hash

app = Client("my_account", api_id=api_id, api_hash=api_hash)

with app:
    print("Session string:", app.export_session_string())
