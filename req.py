from pyrogram import Client, filters, enums
from pyrogram.types import Message, ChatJoinRequest
from pyrogram.errors import (
    UserAlreadyParticipant,
    FloodWait,
    ChatAdminRequired,
    UserNotParticipant,
    ChannelPrivate,
    ChatWriteForbidden,
    MessageNotModified
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
BOT_TOKEN = "7526968128:AAEUgp7DeU1NYKOKfnsAgQe2wg0MKypjH2Y"
SESSION_STRING = "AgGbmwsAHX6GK-W3teadJIJY58RN55FxE1wkppU6mm7ahdtTLb5b4QlgBbuwlV8ypTkOsJ4J-AOSz0ZBgoN5Sc2W4KNB3wmgIY0CCZ26Qm84OFCwIsl7yvJ4ABvwNoDfFr5ltdZN1AZWvxvkcNHDIsgiHbcdNQ1GYSwydR9Vey0Ma12dBLgbLouQBA5ojmO9210FgUZvsgD8ekgi1-NBvSbUDxrACeWfvd47cPgNCedFcWWYFR1iTBPOd2ktIJE3EMT2ya6tI0MnhX5Xvzjikpb-EeCopvhN1Iqik9sV9gVX46txCyThKOzvzzOZCacFTfW5iq-yckj8Lb7EniKpIs2Tk5qpOQAAAAGziX6BAA"

BATCH_SIZE = 100
SLEEP_DURATION = 20

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
    
    try:
        async for request in user.get_chat_join_requests(chat_id):
            if limit and approved_count >= limit:
                break
                
            try:
                await user.approve_chat_join_request(chat_id, request.user.id)
                approved_count += 1
                batch_count += 1
                logger.info(f"Approved user {request.user.id} ({approved_count} total)")
                
            except UserAlreadyParticipant:
                skipped_count += 1
                logger.info(f"Skipped user {request.user.id} - Already a participant")
                continue
                
            except FloodWait as e:
                logger.warning(f"FloodWait detected: waiting for {e.value} seconds")
                await asyncio.sleep(e.value)
                continue
                
            except Exception as e:
                errors_count += 1
                logger.error(f"Error approving user {request.user.id}: {e}")
                if errors_count >= 10:  # Stop if too many errors occur
                    raise BotError("Too many errors occurred while processing requests")
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
    
    return approved_count, skipped_count, errors_count

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
            approved_count, skipped_count, errors_count = await process_join_requests(chat_id, limit)
            await processing_message.delete()
            
            if approved_count > 0 or skipped_count > 0:
                status_message = (
                    f"Process completed in {chat.title}:\n"
                    f"• Approved: {approved_count} user{'s' if approved_count != 1 else ''}\n"
                    f"• Skipped (already members): {skipped_count}\n"
                    f"• Errors encountered: {errors_count}\n"
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
async def handle_join_request(_, request):
    try:
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
