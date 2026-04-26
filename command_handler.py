import config
import logging
from datetime import datetime
from bot_instance import bot

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
    logger.info("Bot command listener starting in 5 seconds...")
    import time
    # Small delay to let old Railway containers shut down
    time.sleep(5)
    
    logger.info("Bot command listener ACTIVE (Waiting for /status)...")
    # skip_pending=True ignores old messages sent while bot was down
    # timeout=20 is standard, logger_level to avoid polling noise
    bot.infinity_polling(skip_pending=True, timeout=60, long_polling_timeout=60)
