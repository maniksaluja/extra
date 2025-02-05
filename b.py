from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler

# Replace this with your bot's token
TOKEN = '8108094028:AAHE8BfBW1KvOLb-zQmBe_pj2c_KgZrRWvo'

# Define button names and URLs as variables
BUTTON_1_NAME = "𝘋𝘪𝘴𝘢𝘣𝘭𝘦"
BUTTON_2_NAME = "≼•1𝘋𝘢𝘺𝘴•≽"
BUTTON_3_NAME = "30𝘋𝘢𝘺𝘴"

BUTTON_1_URL = "https://pay?pa=paytmqr2810050501011cgu66ncd772@paytm&pn=PAYTM_MERCHANT&tid=ORDER5ac1eca5c8&tn=ORDER5ac1eca5c8&am=1&cu=INR&tr=ORDER5ac1eca5c8"
BUTTON_2_URL = "upi://pay?pa=paytmqr2810050501011cgu66ncd772@paytm&pn=PAYTM_MERCHANT&tid=ORDER5ac1eca5c8&tn=ORDER5ac1eca5c8&am=1&cu=INR&tr=ORDER5ac1eca5c8"
BUTTON_3_URL = "https://example3.com"

# Start command handler
async def start(update, context):
    # Define inline keyboard with buttons using the variables
    keyboard = [
        [
            InlineKeyboardButton(BUTTON_1_NAME, url=BUTTON_1_URL),
            InlineKeyboardButton(BUTTON_2_NAME, url=BUTTON_2_URL),
            InlineKeyboardButton(BUTTON_3_NAME, url=BUTTON_3_URL),
        ]
    ]
    
    # Create inline keyboard markup
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    # Send a welcome message with the buttons
    await update.message.reply_text('Welcome! Click a button:', reply_markup=reply_markup)

# Set up the bot and the updater
def main():
    # Set up the Application and pass it your bot's token
    application = Application.builder().token(TOKEN).build()
    
    # Register the start command handler
    start_handler = CommandHandler('start', start)
    application.add_handler(start_handler)
    
    # Start the bot
    application.run_polling()

if __name__ == '__main__':
    main()
