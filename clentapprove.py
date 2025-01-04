from pyrogram import Client, filters, enums
from pyrogram.types import Message, ChatJoinRequest
import asyncio

API_ID = ""
API_HASH = ""
BOT_TOKEN = ""
SESSION_STRING = ""

BATCH_SIZE = 100  
SLEEP_DURATION = 20  

bot = Client(
    "approvebot", 
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN
)

user = Client(
    "user_session",
    session_string=SESSION_STRING
)

async def is_chat_admin(client, chat_id, user_id):
    try:
        member = await user.get_chat_member(chat_id, user_id)
        is_admin = member.status in [enums.ChatMemberStatus.ADMINISTRATOR, enums.ChatMemberStatus.OWNER]
        print(f"Checked admin status for user {user_id} in chat {chat_id}: {is_admin}")
        return is_admin
    except Exception as e:
        print(f"Error checking admin status for user {user_id} in chat {chat_id}: {e}")
        return False

async def process_join_requests(chat_id, limit=None):
    approved_count = 0
    batch_count = 0
    status_message = None
    
    try:
        async for request in user.get_chat_join_requests(chat_id):
           
            if limit and approved_count >= limit:
                break
                
            try:
                await user.approve_chat_join_request(chat_id, request.user.id)
                approved_count += 1
                batch_count += 1
                print(f"Approved user {request.user.id} ({approved_count} total)")
                
               
                if batch_count >= BATCH_SIZE:
                    print(f"Batch of {BATCH_SIZE} users processed. Sleeping for {SLEEP_DURATION} seconds...")
                    if limit:
                        remaining = limit - approved_count
                        print(f"Remaining users to approve: {remaining}")
                    await asyncio.sleep(SLEEP_DURATION)
                    batch_count = 0  
                    
            except Exception as e:
                print(f"Error approving user {request.user.id}: {e}")
                continue
                
    except Exception as e:
        print(f"Error processing join requests: {e}")
    
    return approved_count

@bot.on_message(filters.command('approve') & filters.private)
async def approve_requests(client, message):
    command_parts = message.text.split()
    
   
    if len(command_parts) < 2:
        await message.reply("Please provide a channel/group ID.\nFormat: /approve <channel_id> [number_of_users]")
        return
    
    try:
        chat_id = int(command_parts[1])
    except ValueError:
        await message.reply("Please provide a valid channel/group ID.")
        return
    
   
    limit = None
    if len(command_parts) > 2:
        try:
            limit = int(command_parts[2])
            if limit <= 0:
                await message.reply("Please provide a positive number of users to approve.")
                return
        except ValueError:
            await message.reply("Please provide a valid number of users to approve.")
            return
    
    
    try:
        chat = await user.get_chat(chat_id)
        if not await is_chat_admin(client, chat_id, message.from_user.id):
            await message.reply("You don't have admin permissions in this chat.")
            return
    except Exception as e:
        await message.reply(f"Error accessing the chat: {str(e)}")
        return
    
    
    processing_message = await message.reply("Processing join requests, please wait...")
    
    try:
        approved_count = await process_join_requests(chat_id, limit)
        await processing_message.delete()
        
        
        if approved_count > 0:
            await message.reply(
                f"Successfully approved {approved_count} user{'s' if approved_count != 1 else ''} "
                f"in {chat.title}.\nProcessed in batches of {BATCH_SIZE} with {SLEEP_DURATION} "
                f"second delays between batches."
            )
        else:
            await message.reply(f"No pending join requests found in {chat.title}.")
            
    except Exception as e:
        await processing_message.edit(f"An error occurred: {str(e)}")

@bot.on_chat_join_request()
async def handle_join_request(_, request):
    await request.approve()

if __name__ == "__main__":
    user.start()
    bot.run()