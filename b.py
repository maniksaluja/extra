from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Updater, CommandHandler

# Replace this with your bot's token
TOKEN = '8122078973:AAHFIdC-3qQg8f_ZxNpDgHJNasxTiOrtysk'

# Define button names and URLs as variables
BUTTON_1_NAME = "Button 1"
BUTTON_2_NAME = "Button 2"
BUTTON_3_NAME = "Button 3"

BUTTON_1_URL = "https://example.com"
BUTTON_2_URL = "https://example2.com"
BUTTON_3_URL = "https://example3.com"

# Start command handler
def start(update, context):
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
    update.message.reply_text('Welcome! Click a button:', reply_markup=reply_markup)

# Set up the bot and the updater
def main():
    # Set up the Updater and pass it your bot's token
    updater = Updater(TOKEN, use_context=True)
    
    # Get the dispatcher to register handlers
    dispatcher = updater.dispatcher
    
    # Register the start command handler
    dispatcher.add_handler(CommandHandler('start', start))
    
    # Start the bot
    updater.start_polling()
    updater.idle()

if __name__ == '__main__':
    main()
