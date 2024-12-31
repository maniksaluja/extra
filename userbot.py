import math
import asyncio

from pyrogram import Client, filters, idle
from pyrogram.types import Message
from pyrogram.enums import ParseMode

API_ID = 24417722
API_HASH = "68c75f726da6bd11acda8d7cd03e89f3"
SESSION = "BQF0lboAcW3xr4pSLlwcg35NnGhsrXIFNoMVEyftP9M5m5mrN_WhmhhqVNWS2MiTBUsj34EykN_ENQ4Kgm8IuFVMRCae-6mlpM1m3zYLPd6Pn6gaet-aNgEtbedXrjOLRSMXCcwn6_ujVVIi2GBn9nQDNj_J6c527rvmIJ6LYra8MOoBk90T6E_me95ORsOfeyKaDyY_GMzK_Q7VRRv2IUwmH9HAm6SG4FBUerOpB5oVoVEqKXYAT8WbGZs3FsfP2Hr91mqQNs4tcv-6jfKPkuA9t4etrqC-Rqe6Awm5ezOPYIjy-r-CrkvpFTLRe_vsT2h12abCs826-bX3eV09hsI4UjNJjwAAAAF9OlgPAA"
BOT_TOKEN = "7817008049:AAFfkbla_c5G8nit5drmu2P9nAPcX4Qgek8"
SUDOS = [6604279354, 6552451274]

client = Client(
    "Approve Bot",
    api_id=API_ID,
    api_hash=API_HASH,
    session_string=SESSION.strip()
)

@client.on_message(
    filters.command("ap") & filters.user(SUDOS)
)
async def approve(_, message: Message):
    if len(message.command) != 3:
        return await message.reply("Must Share chat ID/username and limit of requests on channel")

    try:
        chatID = str(message.command[1])
        args2 = float(message.command[2])
        request_loop = math.ceil((args2/100))
        wait = await message.reply("__approving.......__")
        for _ in range(request_loop):
            await client.approve_all_chat_join_requests(chatID)
            await asyncio.sleep(0.5)
        try:
            await wait.edit("**All Approved!**")
        except:
            await wait.edit("**All Approved!**")
            await wait.delete()
    except Exception as error:
        await message.reply("**ERROR:** " + str(error))

@client.on_message(
    filters.command("replace") & filters.user(SUDOS)
)
async def replace(_, message: Message):
    if len(message.command) != 4:
        return await message.reply("Must Share chat ID/username, from text and to text \n\nSyntax: /replace (chat id) (from) (to) \n\nPlease share as it it place message e.g if you want to place 'HelperBot' then type **HelperBot** not helperbot ot helperBot")

    chatID = str(message.command[1])
    from_text = str(message.command[2])
    to_text = str(message.command[3])

    wait = await message.reply("processing....")
    try:
        success = 0
        failed = 0
        repost = 0
        none = 0
        async for history in client.get_chat_history(chatID):
            history: Message
            if history.text and from_text in history.text :
                new_message = str(history.text).replace(from_text, to_text)
                try:
                    await history.edit_text(
                        new_message,
                        parse_mode=ParseMode.MARKDOWN
                    )
                    success += 1
                    await asyncio.sleep(0.3)
                except:
                    try:
                        await client.send_message(
                            chatID,
                            new_message,
                            parse_mode=ParseMode.MARKDOWN
                        )
                        try:
                            await history.delete()
                        except:
                            pass
                        repost += 1
                        await asyncio.sleep(0.3)
                    except Exception as er:
                        failed += 1
                        print("Error while edit:", str(er))

            # in case message with media!
            elif history.caption and from_text in history.caption :
                new_message = str(history.caption).replace(from_text, to_text)
                try:
                    await history.edit_caption(
                        caption=new_message,
                        parse_mode=ParseMode.DEFAULT
                    )
                    success += 1
                    await asyncio.sleep(1)
                except:
                    try:
                        if history.photo:
                            await client.send_photo(
                                chatID,
                                history.photo.file_id,
                                caption=new_message,
                                parse_mode=ParseMode.MARKDOWN
                            )
                        elif history.video:
                            await client.send_video(
                                chatID,
                                history.video.file_id,
                                caption=new_message,
                                parse_mode=ParseMode.MARKDOWN
                            )
                        elif history.animation:
                            await client.send_animation(
                                chatID,
                                history.animation.file_id,
                                caption=new_message,
                                parse_mode=ParseMode.MARKDOWN
                            )
                        try:
                            await history.delete()
                        except:
                            pass
                        repost += 1
                        await asyncio.sleep(1)
                    except Exception as er:
                        failed += 1
                        print("Error while edit:", str(er))
            else:
                none += 1
        await wait.reply(
            f"**Replacing Done!** \n - Total Messages: {success + failed + repost + none} \n - Success: {success} \n - Failed: {failed} \n - Repost: {repost} \n - None: {none} \n - From: {from_text} \n - To: {to_text}"
        )
    except Exception as er:
        await wait.reply(f"Error: {str(er)}")
    await wait.delete()

async def main():
    await client.start()
    async for v in client.get_dialogs():
        pass
    print("Bot Started")
    await idle()
    print("Bot Stopped")
    await client.stop()

if __name__ == "__main__":
    client.run(main())
