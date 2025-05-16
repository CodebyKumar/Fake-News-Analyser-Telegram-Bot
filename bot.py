# filepath: /Users/kumarswamikallimath/NMIThacks/bot.py
import os
import logging
import json
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, CallbackContext
from analyse import analyze_news, create_news_input, extract_json_from_response, json_to_formatted_text  # Import functions from main.py
import logs.logger_config as logger_config  # Import the logging configuration

# Load environment variables from .env file
load_dotenv()
API_KEY = os.getenv("TELEGRAM_BOT_TOKEN")  # Telegram bot token

# Configure logging
logger_config.configure_logging()
logger = logging.getLogger(__name__)

# Start command
async def start(update: Update, context: CallbackContext) -> None:
    """Send a message when the command /start is issued."""
    await update.message.reply_text("Hello! Send me a news article or claim, and I'll analyze it for you.")

# Function to handle incoming messages
async def analyze(update: Update, context: CallbackContext) -> None:
    """Analyze the received message and respond with the analysis."""
    user_message = update.message.text  # Get the user's message
    user = update.effective_user  # Get user information
    chat = update.message.chat

    # Log user and chat information
    user_info = f"User: {user.username or user.first_name or 'N/A'} (ID: {user.id}), " \
                f"Name: {user.first_name or 'N/A'} {user.last_name or ''}, " \
                f"Is Bot: {user.is_bot}, " \
                f"Chat ID: {chat.id}, Chat Type: {chat.type}"
    logger.info(f"Message received from: {user_info}")

    # Check if the message has both text and image
    if update.message.photo and user_message:
        # If both image and text are present
        photo = update.message.photo[-1]
        file = await photo.get_file()
        image_path = file.file_path  # Get the path to the image

        # Log image details for debugging
        logger.info(f"Received image: {image_path}")
        logger.info(f"Received text: {user_message}")

        news_input = create_news_input(user_message, image_path)  # Combine both text and image

    elif update.message.photo:
        # If only an image is received
        photo = update.message.photo[-1]
        file = await photo.get_file()
        image_path = file.file_path  # Get the path to the image

        # Log image details for debugging
        logger.info(f"Received image: {image_path}")

        news_input = create_news_input("", image_path)  # Just use the image (no text)

    elif user_message:
        # If only text is received
        logger.info(f"Received text: {user_message}")
        news_input = user_message  # Just use the text

    else:
        await update.message.reply_text("Sorry, I couldn't process your message. Please send either text or an image.")
        return

    try:
        # Log the news input for debugging
        logger.info("Processing news input")

        # Call the analyze_news function to analyze the input
        response_text = analyze_news(news_input)  # This will handle both text and image inputs

        # Extract the structured JSON response
        data = extract_json_from_response(response_text)

        if data:
            # Send back the result of the analysis as a formatted JSON response
            formatted_response = json_to_formatted_text(data)
            await update.message.reply_text(f"Analysis Result:\n\n{formatted_response}")
        else:
            await update.message.reply_text("Sorry, I couldn't analyze that at the moment. Please try again.")
    except Exception as e:
        # Log the exception for debugging
        logger.error(f"Error processing message: {e}")
        await update.message.reply_text("An error occurred while processing your request. Please try again later.")

# Main function to start the bot
def main() -> None:
    """Start the bot."""
    application = Application.builder().token(API_KEY).build()

    # Register handlers for different commands and messages
    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.TEXT | filters.PHOTO, analyze))  # Handle both text and photo messages

    # Run the bot
    application.run_polling()

if __name__ == "__main__":
    main()