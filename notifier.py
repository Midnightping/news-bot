import telebot
import config
import logging
import os

logger = logging.getLogger(__name__)

# Initialize Bot
bot = telebot.TeleBot(config.NOTIFIER_BOT_TOKEN)
USER_CHAT_ID = os.getenv("USER_CHAT_ID")

def send_suggestion(caption, media_path=None, source_info="Unknown"):
    full_caption = f"{caption}\n\n🔗 Source: {source_info}"
    
    try:
        if media_path and os.path.exists(media_path):
            payload = {
                'chat_id': USER_CHAT_ID,
                'text': full_text,
                'parse_mode': 'Markdown'
            }
            response = requests.post(f"{base_url}/sendMessage", data=payload)
            
        if response.status_code == 200:
            logger.info("Notification sent successfully.")
            return True
        else:
            logger.error(f"Failed to send notification: {response.text}")
            return False
            
    except Exception as e:
        logger.error(f"Error sending notification: {e}")
        return False
