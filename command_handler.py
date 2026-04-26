import config
import logging
from datetime import datetime
from bot_instance import bot, instance_id

logger = logging.getLogger(__name__)

@bot.message_handler(commands=['start', 'status', 'ping'])
def send_status(message):
    # Only respond to YOU
    if str(message.chat.id) == str(config.USER_CHAT_ID):
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        status_msg = (
            "✅ **News Bot Status: ONLINE**\n"
            f"🕒 Server Time: `{now}`\n"
            "📡 Monitoring: 5 Telegram Channels, 3 RSS Feeds\n"
            "🚀 Deploy: Railway Cloud"
        )
        bot.reply_to(message, status_msg, parse_mode='Markdown')
    else:
        logger.warning(f"Unauthorized access attempt from Chat ID: {message.chat.id}")

def start_command_listener():
    import time
    import os
    import telebot
    
    logger.info(f"Bot command listener starting for Instance: {instance_id}...")
    # 10 second delay to give Railway time to start the new process
    time.sleep(10)
    
    logger.info(f"Bot command listener ACTIVE (Instance: {instance_id})")
    
    try:
        # We use polling instead of infinity_polling so we can catch the exception
        bot.polling(non_stop=True, skip_pending=True, timeout=60)
    except telebot.apihelper.ApiTelegramException as e:
        if e.error_code == 409:
            logger.warning(f"⚠️ Conflict (409) detected for Instance {instance_id}. A newer instance is likely running. Shutting down old instance.")
            # os._exit(0) ensures the entire process dies immediately
            os._exit(0)
        else:
            logger.error(f"Telegram API Error: {e}")
            raise
    except Exception as e:
        logger.error(f"Command listener crashed: {e}")
        raise
