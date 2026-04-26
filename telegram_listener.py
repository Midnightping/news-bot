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
    'joynewsontv',
    'eiichaley'
]

# Initialize Telethon Client
from telethon.sessions import StringSession

client = None
try:
    if config.TG_SESSION_STRING:
        client = TelegramClient(StringSession(config.TG_SESSION_STRING), config.TG_API_ID, config.TG_API_HASH)
        logger.info("Using StringSession for authentication.")
    else:
        client = TelegramClient('ghana_news_bot_session', config.TG_API_ID, config.TG_API_HASH)
        logger.info("Using local session file for authentication.")
except Exception as e:
    logger.error(f"FATAL: Failed to initialize Telegram client: {e}")
    logger.error("Check your TG_SESSION_STRING and API_ID (must be a number).")

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

        # 3. Download Media if present (Full Quality)
        media_path = None
        if event.message.media:
            logger.info("Downloading full-resolution media...")
            # Telethon's download_media on a message always grabs the highest quality version
            media_path = await event.message.download_media(file=config.MEDIA_TEMP_DIR)

        # 4. AI Rewrite
        logger.info("Rewriting caption with AI...")
        rewritten = rewrite_caption(normalized.raw_text, normalized.video_link)
        
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
    """Start the Telegram client and listen for new messages."""
    if client is None:
        logger.error("❌ Telegram client is NOT initialized. Check your SESSION_STRING.")
        return

    try:
        logger.info("📡 Connecting to Telegram...")
        await client.start()
        
        # Verify access to channels
        logger.info("🔍 Verifying channel access...")
        for channel in CHANNELS:
            try:
                entity = await client.get_entity(channel)
                logger.info(f"✅ Monitoring: {channel} (ID: {entity.id})")
            except Exception as e:
                logger.error(f"❌ Cannot access channel '{channel}': {e}")

        logger.info("🚀 Telegram Listener is ACTIVE and waiting for news...")
        
        @client.on(events.NewMessage(chats=CHANNELS))
        async def handler(event):
            await handle_new_message(event)
            
        await client.run_until_disconnected()
        
    except Exception as e:
        logger.error(f"❌ Telegram Listener crashed: {e}")

if __name__ == "__main__":
    import asyncio
    logging.basicConfig(level=logging.INFO)
    asyncio.run(start_listening())
