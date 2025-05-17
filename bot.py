# filepath: /Users/kumarswamikallimath/NMIThacks/bot.py
import os
import logging
import json
import requests
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, CallbackContext
from analyse import analyze_news, create_news_input, extract_json_from_response, json_to_formatted_text  # Import functions from main.py
import logs.logger_config as logger_config  # Import the logging configuration
# Load environment variables from .env file
load_dotenv()
API_KEY = os.getenv("TELEGRAM_BOT_TOKEN") 
SARVAM_API_KEY = os.getenv("SARVAM_API_KEY") # Telegram bot token

d_lang = "en"
# Configure logging
logger_config.configure_logging()
logger = logging.getLogger(__name__)

# Start command
async def start(update: Update, context: CallbackContext) -> None:
    """Send a message when the command /start is issued."""
    await update.message.reply_text("Hello! Send me a news article or claim, and I'll analyze it for you.")

async def language_detection(text):
    url = "https://api.sarvam.ai/text-lid"

    payload = {"input": text}
    headers = {
        "Content-Type": "application/json",
        "api-subscription-key": SARVAM_API_KEY
    }

    response = requests.request("POST", url, json=payload, headers=headers)

    return response.json()['language_code']

async def translate_text(text, target_lang):
    url = "https://api.sarvam.ai/translate"

    payload = {
        "source_language_code": "auto",
        "target_language_code": target_lang,  # Use the passed target language parameter
        "speaker_gender": "Male",
        "mode": "classic-colloquial",
        "model": "mayura:v1",
        "enable_preprocessing": False,
        "input": text
    }
    headers = {
        "Content-Type": "application/json",
        "api-subscription-key": SARVAM_API_KEY
    }

    try:
        response = requests.request("POST", url, json=payload, headers=headers)
        response.raise_for_status()  # Raise exception for non-200 status codes
        
        try:
            resp_json = response.json()
            logger.info(f"Translation API raw response: {resp_json}")
            
            if isinstance(resp_json, dict) and 'translated_text' in resp_json:
                return resp_json['translated_text']
            else:
                logger.error(f"Translation API response format unexpected: {resp_json}")
                return text  # Fallback to original text
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON response: {e}")
            logger.error(f"Raw response: {response.text}")
            return text
    except requests.exceptions.RequestException as e:
        logger.error(f"Translation API request failed: {e}")
        return text

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

        # Set target language from text message before creating news_input
        try:
            target_lang = await language_detection(user_message)
            logger.info(f"Detected language from text: {target_lang}")
        except Exception as e:
            logger.error(f"Language detection failed: {e}")
            target_lang = "en"

        # Log image details for debugging
        logger.info(f"Received image: {image_path}")
        logger.info(f"Received text: {user_message}")

        news_input = create_news_input(user_message, image_path)  # Combine both text and image

    elif update.message.photo:
        # If only an image is received
        photo = update.message.photo[-1]
        file = await photo.get_file()
        image_path = file.file_path  # Get the path to the image

        # For image-only messages, use default language (can't detect from image)
        target_lang = "en"
        
        # Log image details for debugging
        logger.info(f"Received image: {image_path}")

        news_input = create_news_input("", image_path)  # Just use the image (no text)

    elif user_message:
        # If only text is received
        logger.info(f"Received text: {user_message}")
        news_input = user_message  # Just use the text
        
        # Set target language from text message
        try:
            target_lang = await language_detection(user_message)
            logger.info(f"Detected language from text: {target_lang}")
        except Exception as e:
            logger.error(f"Language detection failed: {e}")
            target_lang = "en"
    else:
        await update.message.reply_text("Sorry, I couldn't process your message. Please send either text or an image.")
        return

    try:
        logger.info("Processing news input")
        
        # Remove the problematic language detection on news_input
        # We've already set the target_lang above based on input type
        
        # Call the analyze_news function to analyze the input
        response_text = analyze_news(news_input)  # This will handle both text and image inputs

        # Extract the structured JSON response
        data = extract_json_from_response(response_text)

        if data:
            # Only translate verdict, confidence, and reason
            verdict = data.get("verdict", "Unknown")
            confidence = data.get("confidence", 0)
            reason = data.get("reason", "")
            sources = data.get("sources", {})

            # Convert confidence to percentage
            confidence_percent = int(confidence * 100) if isinstance(confidence, (int, float)) else confidence

            # Prepare text for translation (verdict, confidence, reason)
            to_translate = (
                f"Verdict:  {verdict} \n\n"
                f"Confidence: {confidence_percent}% \n\n"
                f"Reason: {reason} \n\n"
            )
            translated_main = await translate_text(to_translate, target_lang)

            # Prepare sources (do not translate)
            sources_text = ""
            if sources:
                sources_text += "Sources: \n"
                for title, source in sources.items():
                    # Check if source is just a number or placeholder
                    if str(source).isdigit() or not source or len(source) < 5:
                        # For numeric placeholders, format more descriptively
                        sources_text += f"- {title}\n"
                    else:
                        # For actual URLs or meaningful references
                        if not source.startswith(('http://', 'https://')):
                            # Include both source title and user query in search for better results
                            source = f"https://www.google.com/search?q={title.replace(' ', '+')}+{user_message.replace(' ', '+')}"
                        sources_text += f"- [{title}]({source})\n"

            formatted_response = translated_main + sources_text

            logger.info(f"Formatted response: {formatted_response}")

            # Translate the header text as well
            header_text = "Analysis Result:"
            translated_header = await translate_text(header_text, target_lang)
            
            await update.message.reply_text(f"{translated_header}\n\n{formatted_response}", parse_mode="Markdown")
            
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