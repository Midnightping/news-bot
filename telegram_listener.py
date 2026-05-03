from telethon import TelegramClient, events
import asyncio
import config
import logging
import os
import hashlib
import time
from normalization import normalize_telegram
from database import db
from ai_rewriter import rewrite_caption
from notifier import send_suggestion
from bot_instance import instance_id
from media_handler import cleanup_media
import x_poster

logger = logging.getLogger(__name__)

# Channels that get forwarded to your private Telegram for review
CHANNELS = ["ghonetv", "joynewsontv", "eiichaley"]

# Channels that get auto-posted directly to X (Twitter) via Playwright
X_POST_CHANNELS = ["newsfather"]

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

async def handle_new_message(event, is_history=False):
    """Callback for new messages in monitored channels."""
    try:
        if is_history:
            # When scraping history, 'event' is actually a Message object
            msg = event
            channel_username = msg.chat.username if hasattr(msg.chat, 'username') else "Unknown"
        else:
            # When live, 'event' is a NewMessage.Event
            channel_entity = await event.get_chat()
            channel_username = getattr(channel_entity, 'username', 'Unknown')
            msg = event.message
            
        logger.info(f"New message from {channel_username}")
        
        logger.debug(f"Processing message of type: {type(msg)}")
        
        if isinstance(msg, str):
            logger.error(f"⚠️ Received a string instead of a Message object: {msg[:100]}")
            return

        # 2. Normalize
        normalized = normalize_telegram(msg, channel_username)
        
        # 2. Check Duplicate
        if db.check_duplicate(normalized.content_hash):
            logger.info("Duplicate post detected. Skipping.")
            return

        # 3. Download Media if present (Full Quality)
        media_path = None
        if msg.media:
            logger.info("Downloading full-resolution media...")
            # Telethon's download_media on a message always grabs the highest quality version
            media_path = await msg.download_media(file=config.MEDIA_TEMP_DIR)

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

async def scrape_history(limit=20):
    """Scrapes the most recent messages from monitored channels to catch up."""
    logger.info(f"🕰️ Scraping last {limit} messages from channels to catch up...")
    for channel in CHANNELS:
        try:
            entity = await client.get_entity(channel)
            async for message in client.iter_messages(entity, limit=limit):
                # Only process if it's from the last 24 hours
                if message.date.timestamp() > (time.time() - 86400):
                    # Check if already processed
                    text = message.text or ""
                    content_hash = hashlib.md5(f"telegram_{channel}_{message.id}".encode()).hexdigest()
                    if not db.check_duplicate(content_hash):
                        logger.info(f"📥 Catching up on missed post from {channel}")
                        await handle_new_message(message, is_history=True)
        except Exception as e:
            logger.error(f"Error scraping history for {channel}: {e}")

async def handle_newsfather_message(event):
    """Handles new messages from @newsfather — rewrites and auto-posts to X."""
    try:
        channel_entity = await event.get_chat()
        channel_username = getattr(channel_entity, 'username', 'newsfather')
        msg = event.message

        logger.info(f"📥 New @newsfather message — queuing for X post...")

        # 1. Normalize
        normalized = normalize_telegram(msg, channel_username)

        # Skip if empty text
        if not normalized.raw_text.strip():
            logger.info("Skipping @newsfather message — no text content.")
            return

        # 2. Deduplicate
        if db.check_duplicate(normalized.content_hash):
            logger.info("Duplicate @newsfather post detected. Skipping.")
            return

        # 3. Download media if present
        media_path = None
        if msg.media:
            logger.info("📥 Downloading media from @newsfather...")
            media_path = await msg.download_media(file=config.MEDIA_TEMP_DIR)

        # 4. AI Rewrite — CRITICAL: returns None on quota errors
        logger.info("🤖 Rewriting for X...")
        rewritten = rewrite_caption(normalized.raw_text, normalized.video_link)

        if rewritten is None:
            logger.warning(
                "⚠️ Gemini quota hit — skipping X post for this @newsfather story. "
                "Saving to DB as 'skipped_quota'."
            )
            post_data = normalized.to_dict()
            post_data['rewritten_text'] = None
            post_data['status'] = 'skipped_quota'
            db.add_pending_post(post_data)
            if media_path:
                cleanup_media(media_path)
            return

        # 5. Save to DB
        post_data = normalized.to_dict()
        post_data['rewritten_text'] = rewritten
        saved = db.add_pending_post(post_data)
        post_id = saved[0]['id'] if saved else None

        # 6. Post to X via Playwright
        logger.info(f"🐦 Posting to X: {rewritten[:60]}...")
        success = await x_poster.post_to_x(
            text=rewritten,
            media_path=media_path,
            post_id=post_id
        )

        if success:
            logger.info("✅ @newsfather story posted to X successfully.")
        else:
            logger.error("❌ Failed to post @newsfather story to X.")

        # 7. Cleanup temp media
        if media_path:
            cleanup_media(media_path)

    except Exception as e:
        logger.error(f"❌ Error handling @newsfather message: {e}")


async def start_listening():
    """Start the Telegram client and listen for new messages."""
    if client is None:
        logger.error("❌ Telegram client is NOT initialized. Check your SESSION_STRING.")
        return

    try:
        logger.info("📡 Connecting to Telegram...")
        try:
            # 30 second timeout to prevent silent hangs
            await asyncio.wait_for(client.start(), timeout=30)
            logger.info("✅ Connected to Telegram.")
        except asyncio.TimeoutError:
            logger.error("❌ Telegram connection TIMED OUT after 30s! Check SESSION_STRING.")
            return
        except Exception as e:
            logger.error(f"❌ Telegram connection FAILED: {e}")
            return

        # Verify access to all channels
        logger.info("🔍 Verifying channel access...")
        all_channels = CHANNELS + X_POST_CHANNELS
        for channel in all_channels:
            try:
                entity = await client.get_entity(channel)
                label = "→ Telegram" if channel in CHANNELS else "→ X (Twitter)"
                logger.info(f"✅ Monitoring: {channel} {label} (ID: {entity.id})")
            except Exception as e:
                logger.error(f"❌ Cannot access channel '{channel}': {e}")

        # Catch up on today's news (Telegram channels only)
        await scrape_history(limit=50)

        logger.info(f"🚀 Telegram Listener ACTIVE for Instance: {instance_id}")

        # Handler for existing channels → your private Telegram
        @client.on(events.NewMessage(chats=CHANNELS))
        async def handler(event):
            await handle_new_message(event)

        # Handler for @newsfather → X (Twitter)
        @client.on(events.NewMessage(chats=X_POST_CHANNELS))
        async def x_handler(event):
            await handle_newsfather_message(event)

        await client.run_until_disconnected()

    except Exception as e:
        logger.error(f"❌ Telegram Listener crashed: {e}")

if __name__ == "__main__":
    import asyncio
    logging.basicConfig(level=logging.INFO)
    asyncio.run(start_listening())
