import asyncio
import logging
import config
from telegram_listener import start_listening, client
from command_handler import start_command_listener
from rss_listener import poll_rss_feeds
from ai_rewriter import rewrite_caption
from notifier import send_suggestion
from bot_instance import bot
from database import db
from media_handler import download_media_from_url, cleanup_media
from datetime import datetime

# Configure Logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("MainOrchestrator")

# Silence noisy libraries
logging.getLogger('httpx').setLevel(logging.WARNING)
logging.getLogger('httpcore').setLevel(logging.WARNING)
logging.getLogger('telethon').setLevel(logging.WARNING)
logging.getLogger('hpack').setLevel(logging.WARNING)
logging.getLogger('google').setLevel(logging.WARNING)

async def rss_task():
    """Background task to poll RSS feeds periodically."""
    while True:
        try:
            logger.info("💓 Heartbeat: Checking RSS feeds for new stories...")
            logger.info("Starting scheduled RSS poll...")
            new_rss_posts = poll_rss_feeds()
            total_new = len(new_rss_posts)
            
            if total_new > 0:
                logger.info(f"✨ Found {total_new} new stories to process.")
                
            for i, post in enumerate(new_rss_posts, 1):
                # Process each new RSS post
                logger.info(f"📝 Processing story {i}/{total_new}: {post.source_name}")
                
                # 1. AI Rewrite
                rewritten = rewrite_caption(post.raw_text, post.video_link)
                
                # 2. Try to get media if RSS has it
                media_path = None
                if post.media_urls:
                    logger.info(f"📥 Downloading media for story {i}...")
                    media_path = download_media_from_url(post.media_urls[0])
                
                # 4. Notify User
                logger.info(f"📤 Sending suggestion for story {i} to Telegram...")
                send_suggestion(
                    caption=rewritten,
                    media_path=media_path,
                    source_info=f"Website: {post.source_name}"
                )
                
                # 5. Cleanup
                if media_path:
                    cleanup_media(media_path)
            
            if total_new > 0:
                logger.info(f"✅ Finished processing {total_new} stories.")
            else:
                logger.info("😴 No new stories found this time.")
                
            logger.info(f"💤 Sleeping for {config.POLLING_INTERVAL // 60} minutes.")
        except Exception as e:
            logger.error(f"Error in RSS task: {e}")
            
        await asyncio.sleep(config.POLLING_INTERVAL)

async def heartbeat_task():
    """Sends a 'Still Alive' message to the user once a day at 8 AM."""
    logger.info("Heartbeat task started.")
    while True:
        now = datetime.now()
        # Check if it's 6:00 AM GMT
        if now.hour == 6 and now.minute == 0:
            status_msg = "🫡 **Daily Heartbeat**: News Bot is active and monitoring Ghana news."
            try:
                bot.send_message(config.USER_CHAT_ID, status_msg, parse_mode='Markdown')
                logger.info("Daily heartbeat sent.")
            except Exception as e:
                logger.error(f"Failed to send heartbeat: {e}")
            await asyncio.sleep(60) # Wait a minute so we don't send it twice
        await asyncio.sleep(30) # Check every 30 seconds

async def main():
    logger.info("🚀 Starting Ghana News Bot (Semi-Automated Mode)...")
    
    # Run the Command Listener in a separate thread to not block asyncio
    loop = asyncio.get_event_loop()
    loop.run_in_executor(None, start_command_listener)
    
    # Run Telegram listener, RSS poller, and heartbeat task concurrently
    await asyncio.gather(
        start_listening(),
        rss_task(),
        heartbeat_task()
    )

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Bot stopped by user.")
