import re
import sys
from os import getenv
from pyrogram import filters
from dotenv import load_dotenv

load_dotenv()


API_ID = int(getenv("API_ID", "28070245"))
API_ID2 = int(getenv("API_ID2", "20886865"))
API_HASH = getenv("API_HASH", "c436fc81a842d159c75e1e212b7f6e7c")
API_HASH2 = getenv("API_HASH2", "754d23c04f9244762390c095d5d8fe2b")
BOT_TOKEN = getenv("BOT_TOKEN", "8122078973:AAHD8OJBXghpuWI3N48-CJubM3PInyMe1C0")
BOT_TOKEN2 = getenv("BOT_TOKEN2","7348838977:AAEh-lq3jud1VTe79zm6EScmJG63Rio2L3g")
STRING1=getenv("STRING_SESSION", "")
STRING2 =getenv("STRING_SESSION2" , "BQE-tVEALzZ5ur4DNaQ9H0DcamIviYM1fcI0zqDpCUGKFv7gxA90AMcojJBRfrnz3ku9qMu_hJaUFG514_Ad_eGPx4ep836xhWgFYLABI2UrHXsYxMVYur_0lSy2mi2ixLY_V5Rq5iZyjFfwFjiurtpqPgQoH5KIvGa6ZnmoD_OCAGlGwJsTa8hg7TG0efkeNMJlNGyBsfADe-jQeeI7FBkAuz5Ic5ZA__7Ky_Q7IwsPK4IlwLymDWonEqhuz1EvV3A4LFwa5_bOMTarhzWqQbtuTixxh7nP6Ym-Tx7FXhxNS1JslpVWkAjQvPEyNAmpkyTyoGad7WR0-OV6NlMVslSYv2rnPgAAAAGfEYMRAA")

OWNER_ID = list(
    map(int, getenv("OWNER_ID", "1234567890").split())
)

# This is important to keep communication between the bots
BCAST_CHANNEL = int(getenv("BCAST_CHANNEL"), -1002358061049) 

#Your db channel Id
DATABASE_1 = int(getenv("DATABASE_CHANNEL_1",0)) 
DATABASE_2 = int(getenv("DATABASE_CHANNEL_2",0))
BACKUP_DATABASE_1 = int(getenv("BACKUP_DATABASE_1",0))
BACKUP_DATABASE_2 = int(getenv("BACKUP_DATABASE_2",0))
POSTING_CHANNEL_1= int(getenv("POSTING_CHANNEL_1",-1002470977842))
POSTING_CHANNEL_2 = int(getenv("POSTING_CHANNEL_2",-1002469220386))
LOGS_CHANNEL_1 = int(getenv("LOGS_CHANNEL_1",-1002469220386))
LOGS_CHANNEL_2 = int(getenv("LOGS_CHANNEL_2",-1002469220386))
USELESS_CHANNEL = int(getenv("USELESS_CHANNEL", -1002358061049))
FEEDBACK_CHANNEL = int(getenv("FEEDBACK_CHANNEL",-1002277059467))

#mongo database URI
DB_URI = getenv("DATABASE_URL", "")
DB_NAME = getenv("DATABASE_NAME", "Stranger")

RFSUB = {-1002085702527:"Announcment"}
FSUB = {}
# PENDING_REQUEST = {-1002341255671:"PENDING1" , -1002273566865: "PENDING2"}
PENDING_REQUEST = {-1002488026231:"BackUP"}
REACTION_CHANNEL = int(-1002085702527)


SHORTLINK_URL = getenv("SHORTLINK_URL", "api.shareus.io")
SHORTLINK_API = getenv("SHORTLINK_API", "PUIAQBIFrydvLhIzAOeGV8yZppu2")

# set auto delete time for content in seconds , keep it 0 to disable
AUTO_DELETE_CONTENT = int(getenv('AUTO_DELETE_CONTENT', 3600))
AUTO_DELETE_POST = int(getenv("AUTO_DELETE_POST" , 0))

ACCESS_TOKEN_PLAN_1 = int(getenv("ACCESS_TOKEN_PLAN_1" , 60*60*24)) # 1 day
ACCESS_TOKEN_PLAN_2 = int(getenv("ACCESS_TOKEN_PLAN_2" , 60*60*24*30)) # 30 days
DOWNLOAD_PLAN_1 = int(getenv("DOWNLOAD_PLAN_1" , 60*60*12)) # 12 hours
DOWNLOAD_PLAN_2 = int(getenv("DOWNLOAD_PLAN_2" , 60*60*24*30)) # 30 days
ACCESS_TOKEN_PLAN_1_PRICE = int(getenv("ACCESS_TOKEN_PLAN_1_PRICE", 1)) 
ACCESS_TOKEN_PLAN_2_PRICE = int(getenv("ACCESS_TOKEN_PLAN_2_PRICE", 1))
DOWNLOAD_PLAN_1_PRICE = int(getenv("DOWNLOAD_PLAN_1_PRICE", 1))
DOWNLOAD_PLAN_2_PRICE = int(getenv("DOWNLOAD_PLAN_2_PRICE", 1))

PAYTM_API_KEY = getenv("PAYTM_API_KEY","")

THUMBNAIL_PIC_1 = getenv("THUMBNAIL_PIC_1", "https://graph.org/file/e677ea79ecbdae5b8dbaa.jpg")
THUMBNAIL_PIC_2 = getenv("THUMBNAIL_PIC_2", "https://graph.org/file/5f3d0d2c8e35a037e4663.jpg")

DAILY_FREE_CONTENT = getenv("DAILY_FREE_CONTENT",5)

# ================================================================================================================================================================================================================================================================================================================================================================================================================================================================================================================================================================================================================================================================================================================================================================================================================
### DONT TOUCH or EDIT codes after this line

BANNED_USERS = filters.user()
LOG_FILE_NAME = "Strangerlogs.txt"
RFSUB_CHAT_LINKS={}
FSUB_CHAT_LINKS={}
PENDING_REQUEST_LINKS={}
RFSUB_CHATS = filters.chat()
for chat_id in RFSUB:
    RFSUB_CHATS.add(chat_id)


temp = {**RFSUB, **FSUB, **PENDING_REQUEST}
temp_channels = [key for key in temp]
ALL_CHANNELS = temp_channels
BOT_ALL_CHANNELS = [x for x in temp_channels]

BOT_ALL_CHANNELS.append(DATABASE_1)
BOT_ALL_CHANNELS.append(DATABASE_2)
BOT_ALL_CHANNELS.append(BACKUP_DATABASE_1)
BOT_ALL_CHANNELS.append(BACKUP_DATABASE_2)
BOT_ALL_CHANNELS.append(POSTING_CHANNEL_1)
BOT_ALL_CHANNELS.append(POSTING_CHANNEL_2)
BOT_ALL_CHANNELS.append(LOGS_CHANNEL_1)
BOT_ALL_CHANNELS.append(LOGS_CHANNEL_2)
BOT_ALL_CHANNELS.append(USELESS_CHANNEL)
BOT_ALL_CHANNELS.append(FEEDBACK_CHANNEL)

TOKEN_SECRET_EXPIRY_TIME =86400

emoji = {
    "emoji_1":"👍🏻",
    "emoji_2":"❤️",
    "emoji_3":"😂",
    "emoji_4":"🤤",
    "emoji_5":"👎🏻",
    "emoji_6":"💔",
    "emoji_7":"😭",
    "emoji_8":"🤬",
}

PAYMENT_HOST = "https://api-pay.wansaw.com/"

BASE_GIF = getenv(
    "BASE_GIF",
    "assets/base.gif.mp4",
)

BASE_IMAGE = getenv(
    "BASE_IMAGE",
    "assets/base_pic.jpg",
    )


START_GIF = getenv(
    "START_GIF",
    "assets/start.gif.mp4",
    )
START_IMG = getenv(
    "START_IMG",
    "assets/START_IMG.jpg",
)

DOWNLOAD_AUDIO = getenv(
    "DOWNLOAD_AUDIO",
    "assets/download_audio.ogg",
)
WARNING_AUDIO = getenv(
    "WARNING_AUDIO",
    "assets/warning_audio.ogg",
)

IMPORTANT_AUDIO = getenv(
    "IMPORTANT_AUDIO",
    "assets/SendRequest.ogg"
)

JOIN_IMAGE = getenv(
    'JOIN_IMAGE',
    'assets/join_image.jpg'
    )

LEAVE_VOICE = getenv(
    "LEAVE_VOICE",
    "assets/leave_voice.ogg"
)

INFO_PIC = getenv(
    "INFO_PIC",
    "assets/info_pic.jpg",
)

if BASE_GIF:
    if BASE_GIF != "assets/base.gif.mp4":
        if not re.match("(?:http|https)://", BASE_GIF):
            print(
                "[ERROR] - Your BASE_GIF url is wrong. Please ensure that it starts with https://"
            )
            sys.exit()

if BASE_IMAGE:
    if BASE_IMAGE != "assets/base_pic.jpg":
        if not re.match("(?:http|https)://", BASE_IMAGE):
            print(
                "[ERROR] - Your BASE_IMAGE url is wrong. Please ensure that it starts with https://"
            )
            sys.exit()

if START_GIF:
    if START_GIF != "assets/start.gif.mp4":
        if not re.match("(?:http|https)://", START_GIF):
            print(
                "[ERROR] - Your START_GIF url is wrong. Please ensure that it starts with https://"
                )
            sys.exit()

if START_IMG:
    if START_IMG != "assets/START_IMG.jpg":
        if not re.match("(?:http|https)://", START_IMG):
            print(
                "[ERROR] - Your START_IMG url is wrong. Please ensure that it starts with https://"
            )
            sys.exit()

if DOWNLOAD_AUDIO:
    if DOWNLOAD_AUDIO != "assets/download_audio.ogg":
        print(
            "[ERROR] - Your Download audio name is invalid."
            )
        sys.exit()

if WARNING_AUDIO:
    if WARNING_AUDIO != "assets/warning_audio.ogg":
        print(
            "[ERROR] - Your warning audio name is invalid."
            )
        sys.exit()

if IMPORTANT_AUDIO:
    if IMPORTANT_AUDIO != "assets/SendRequest.ogg":
        print(
            "[ERROR] - Your important audio name is invalid."
            )
        sys.exit()
        
if JOIN_IMAGE:
    if JOIN_IMAGE != "assets/join_image.jpg":
        if not re.match("(?:http|https)://", JOIN_IMAGE):
            print(
                "[ERROR] - Your JOIN_IMAGE url is wrong. Please ensure that it starts with https://"
                )
            sys.exit()

if LEAVE_VOICE:
    if LEAVE_VOICE != "assets/leave_voice.ogg":
        print("[ERROR] - Your leave voice name is invalid.")
        sys.exit()

if INFO_PIC:
    if INFO_PIC != "assets/info_pic.jpg":
        if not re.match("(?:http|https)://", INFO_PIC):
            print(
                "[ERROR] - Your INFO_PIC url is wrong. Please ensure that it starts with https")
            sys.exit()
            

