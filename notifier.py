import requests
import config
import logging
import os

logger = logging.getLogger(__name__)

# Note: You need a Bot Token from @BotFather for this
BOT_TOKEN = os.getenv("NOTIFIER_BOT_TOKEN")
USER_CHAT_ID = os.getenv("USER_CHAT_ID")

def send_suggestion(caption, media_path=None, source_info=""):
    if not BOT_TOKEN or not USER_CHAT_ID:
        logger.error("Notifier Bot credentials missing.")
        return False

    base_url = f"https://api.telegram.org/bot{BOT_TOKEN}"
    
    # Header for the message
    header = f"📣 **New X Suggestion!**\n\n"
    footer = f"\n\n🔗 Source: {source_info}"
    full_text = f"{header}{caption}{footer}"

    try:
        if media_path and os.path.exists(media_path):
            # Send with media
            file_extension = os.path.splitext(media_path)[1].lower()
            
            if file_extension in ['.jpg', '.jpeg', '.png']:
                method = "sendPhoto"
                files = {'photo': open(media_path, 'rb')}
            elif file_extension in ['.mp4', '.mov']:
                method = "sendVideo"
                files = {'video': open(media_path, 'rb')}
            else:
                method = "sendDocument"
                files = {'document': open(media_path, 'rb')}
                
            payload = {
                'chat_id': USER_CHAT_ID,
                'caption': full_text,
                'parse_mode': 'Markdown'
            }
            response = requests.post(f"{base_url}/{method}", data=payload, files=files)
        else:
            # Text only
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
