from pyrogram import Client, filters, enums
from pyrogram.types import Message, ChatJoinRequest
from pyrogram.errors import (
    UserAlreadyParticipant,
    FloodWait,
    ChatAdminRequired,
    UserNotParticipant,
    ChannelPrivate,
    ChatWriteForbidden,
    MessageNotModified,
    UserChannelsTooMuch,
    InputUserDeactivated
)
import asyncio
import logging
from datetime import datetime

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('bot.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

API_ID = "26974987"
API_HASH = "449b9bb5b57b6f91410031c806036a27"
BOT_TOKEN = "8007555138:AAHxjbAAxy4dxXnMGIQEBIYf4GKqto7MxPs"
SESSION_STRING = "AgGbmwsABk8FEjWZErZQEbgSRtH-blZgasvUgGdkSqM2OmT_P_GyIzicaEHMccrgkhMd_WARbQXZGQkx-I6Q2MXr6aT0s7-WcGW7ThyvfRUJkXGlOnVCtQJDvql6t3IVpEJbqPYNtu1qqFhdKdsoYyBKnNMF5tJrE8cSshnVCFSjNmYgOpNZ-dRFiMi5GJ5KH2GIaDbL7WdbgJrxtkJBeAtpgrx9MLio54mG_rCzV58Y4vPOEg5_olJRgmGq_YjC-baU49rAvxY7AyP_rJUNBQbqKvm1epEFnyhJghJZp-fzIjZurkRXEaNalQygGPhgh5dBJO6RbnjBPqU8Ayw_cG3WyCXNvgAAAAGziX6BAA"

BATCH_SIZE = 100
SLEEP_DURATION = 20
MAX_RETRIES = 3
ERROR_THRESHOLD = 20  # Increased threshold for errors

class BotError(Exception):
    """Base exception class for bot-related errors"""
    pass

class ChatAccessError(BotError):
    """Exception raised for errors related to chat access"""
    pass

class AdminPermissionError(BotError):
    """Exception raised for errors related to admin permissions"""
    pass

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
        logger.info(f"Checked admin status for user {user_id} in chat {chat_id}: {is_admin}")
        return is_admin
    except UserNotParticipant:
        logger.error(f"User {user_id} is not a member of chat {chat_id}")
        raise AdminPermissionError("User is not a member of this chat")
    except ChatAdminRequired:
        logger.error(f"Bot requires admin privileges in chat {chat_id}")
        raise AdminPermissionError("Bot requires admin privileges")
    except Exception as e:
        logger.error(f"Error checking admin status for user {user_id} in chat {chat_id}: {e}")
        raise BotError(f"Failed to check admin status: {str(e)}")

async def process_join_requests(chat_id, limit=None):
    approved_count = 0
    skipped_count = 0
    batch_count = 0
    errors_count = 0
    too_many_channels_count = 0
    deactivated_count = 0
    
    try:
        async for request in user.get_chat_join_requests(chat_id):
            if limit and approved_count >= limit:
                break
                
            try:
                # Skip deactivated users
                if not request.user:
                    deactivated_count += 1
                    continue

                retry_count = 0
                while retry_count < MAX_RETRIES:
                    try:
                        await user.approve_chat_join_request(chat_id, request.user.id)
                        approved_count += 1
                        batch_count += 1
                        logger.info(f"Approved user {request.user.id} ({approved_count} total)")
                        break
                    except FloodWait as e:
                        logger.warning(f"FloodWait detected: waiting for {e.value} seconds")
                        await asyncio.sleep(e.value)
                        retry_count += 1
                    except Exception as e:
                        retry_count += 1
                        if retry_count >= MAX_RETRIES:
                            raise e
                        await asyncio.sleep(1)
                
            except UserAlreadyParticipant:
                skipped_count += 1
                logger.info(f"Skipped user {request.user.id} - Already a participant")
                continue
                
            except UserChannelsTooMuch:
                too_many_channels_count += 1
                logger.warning(f"User {request.user.id} is in too many channels")
                continue
                
            except InputUserDeactivated:
                deactivated_count += 1
                logger.warning(f"User {request.user.id} is deactivated")
                continue
                
            except Exception as e:
                errors_count += 1
                logger.error(f"Error approving user {request.user.id}: {e}")
                if errors_count >= ERROR_THRESHOLD:
                    raise BotError(f"Too many errors occurred while processing requests ({errors_count} errors)")
                continue
                
            if batch_count >= BATCH_SIZE:
                logger.info(f"Batch of {BATCH_SIZE} users processed. Sleeping for {SLEEP_DURATION} seconds...")
                if limit:
                    remaining = limit - approved_count
                    logger.info(f"Remaining users to approve: {remaining}")
                await asyncio.sleep(SLEEP_DURATION)
                batch_count = 0
                    
    except ChannelPrivate:
        logger.error(f"Cannot access private channel {chat_id}")
        raise ChatAccessError("Cannot access this private channel")
    except Exception as e:
        logger.error(f"Error processing join requests: {e}")
        raise BotError(f"Failed to process join requests: {str(e)}")
    
    return {
        "approved": approved_count,
        "skipped": skipped_count,
        "errors": errors_count,
        "too_many_channels": too_many_channels_count,
        "deactivated": deactivated_count
    }

@bot.on_message(filters.command('approve') & filters.private)
async def approve_requests(client, message):
    try:
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
        except AdminPermissionError as e:
            await message.reply(f"Permission error: {str(e)}")
            return
        except ChatAccessError as e:
            await message.reply(f"Access error: {str(e)}")
            return
        except Exception as e:
            await message.reply(f"Error accessing the chat: {str(e)}")
            return
        
        processing_message = await message.reply("Processing join requests, please wait...")
        
        try:
            results = await process_join_requests(chat_id, limit)
            await processing_message.delete()
            
            if sum(results.values()) > 0:
                status_message = (
                    f"Process completed in {chat.title}:\n"
                    f"• Approved: {results['approved']} user{'s' if results['approved'] != 1 else ''}\n"
                    f"• Skipped (already members): {results['skipped']}\n"
                    f"• Users in too many channels: {results['too_many_channels']}\n"
                    f"• Deactivated users: {results['deactivated']}\n"
                    f"• Other errors: {results['errors']}\n"
                    f"Processed in batches of {BATCH_SIZE} with {SLEEP_DURATION} second delays."
                )
                await message.reply(status_message)
            else:
                await message.reply(f"No pending join requests found in {chat.title}.")
                
        except MessageNotModified:
            logger.warning("Message was not modified")
        except ChatWriteForbidden:
            logger.error("Bot cannot write messages in this chat")
            await message.reply("Bot cannot send messages in this chat. Please check permissions.")
        except Exception as e:
            error_message = f"An error occurred while processing requests: {str(e)}"
            logger.error(error_message)
            try:
                await processing_message.edit(error_message)
            except:
                await message.reply(error_message)
                
    except Exception as e:
        logger.error(f"Unexpected error in approve_requests: {e}")
        await message.reply("An unexpected error occurred. Please try again later.")

@bot.on_chat_join_request()
async def handle_join_request(_, request: ChatJoinRequest):
    try:
        if not hasattr(request, 'user') or not request.user:
            logger.error("Join request has no valid user attribute")
            return
            
        await request.approve()
        logger.info(f"Approved join request for user {request.user.id}")
    except UserAlreadyParticipant:
        logger.info(f"User {request.user.id} is already a participant - skipping")
    except FloodWait as e:
        logger.warning(f"FloodWait detected in join request handler: waiting for {e.value} seconds")
        await asyncio.sleep(e.value)
    except Exception as e:
        logger.error(f"Error handling join request: {e}")

if __name__ == "__main__":
    try:
        logger.info("Starting bot...")
        user.start()
        bot.run()
    except Exception as e:
        logger.critical(f"Critical error starting bot: {e}")
        raise
