import telebot
import config
import logging
import os

logger = logging.getLogger(__name__)

# Initialize Bot
bot = telebot.TeleBot(config.NOTIFIER_BOT_TOKEN)
USER_CHAT_ID = os.getenv("USER_CHAT_ID")

def send_suggestion(caption, media_path=None, source_info="Unknown"):
    """Sends a news suggestion to the user's private Telegram chat."""
    full_caption = f"{caption}\n\n🔗 **Source**: {source_info}"
    
    try:
        if media_path and os.path.exists(media_path):
            with open(media_path, 'rb') as photo:
                bot.send_photo(
                    config.USER_CHAT_ID, 
                    photo, 
                    caption=full_caption, 
                    parse_mode='Markdown'
                )
        else:
            bot.send_message(
                config.USER_CHAT_ID, 
                full_caption, 
                parse_mode='Markdown'
            )
        
        logger.info("✅ News suggestion sent to user.")
        return True
            
    except Exception as e:
        logger.error(f"❌ Error sending notification: {e}")
        return False
