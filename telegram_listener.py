from telethon import TelegramClient, events
import config
import logging
import os
from normalization import normalize_telegram
from database import db
from ai_rewriter import rewrite_caption
from notifier import send_suggestion
from media_handler import cleanup_media

logger = logging.getLogger(__name__)

# List of Ghana news channels to monitor
CHANNELS = [
    'ghonetv',
    'citinewsroom',
    'utvghana',
    'pulseghana',
    'joynewsontv'
]

# Initialize Telethon Client
from telethon.sessions import StringSession

if config.TG_SESSION_STRING:
    client = TelegramClient(StringSession(config.TG_SESSION_STRING), config.TG_API_ID, config.TG_API_HASH)
    logger.info("Using StringSession for authentication.")
else:
    client = TelegramClient('ghana_news_bot_session', config.TG_API_ID, config.TG_API_HASH)
    logger.info("Using local session file for authentication.")

async def handle_new_message(event):
    """Callback for new messages in monitored channels."""
    try:
        channel_entity = await event.get_chat()
        channel_username = getattr(channel_entity, 'username', 'Unknown')
        
        logger.info(f"New message from {channel_username}")
        
        # 1. Normalize
        normalized = normalize_telegram(event.message, channel_username)
        
        # 2. Check Duplicate
        if db.check_duplicate(normalized.content_hash):
            logger.info("Duplicate post detected. Skipping.")
            return

        # 3. Download Media if present
        media_path = None
        if event.message.media:
            logger.info("Downloading media...")
            media_path = await event.message.download_media(file=config.MEDIA_TEMP_DIR)

        # 4. AI Rewrite
        logger.info("Rewriting caption with AI...")
        rewritten = rewrite_caption(normalized.raw_text)
        
        # 5. Save to Database
        post_data = normalized.to_dict()
        post_data['rewritten_text'] = rewritten
        db.add_pending_post(post_data)

        # 6. Notify User (Semi-Automated Flow)
        logger.info("Sending suggestion to user...")
        success = send_suggestion(
            caption=rewritten,
            media_path=media_path,
            source_info=f"Telegram: @{channel_username}"
        )
        
        # 7. Cleanup
        if media_path:
            cleanup_media(media_path)
            
    except Exception as e:
        logger.error(f"Error handling Telegram message: {e}")

async def start_listening():
    """Starts the Telethon listener."""
    logger.info(f"Starting Telegram listener for channels: {CHANNELS}")
    
    @client.on(events.NewMessage(chats=CHANNELS))
    async def handler(event):
        await handle_new_message(event)

    await client.start(phone=config.TG_PHONE)
    logger.info("Telegram listener is online!")
    await client.run_until_disconnected()

if __name__ == "__main__":
    import asyncio
    logging.basicConfig(level=logging.INFO)
    asyncio.run(start_listening())
