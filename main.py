import asyncio
import logging
import config
from telegram_listener import start_listening, client
from rss_listener import poll_rss_feeds
from ai_rewriter import rewrite_caption
from notifier import send_suggestion
from database import db
from media_handler import download_media_from_url, cleanup_media

# Configure Logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("MainOrchestrator")

async def rss_task():
    """Background task to poll RSS feeds periodically."""
    while True:
        try:
            logger.info("Starting scheduled RSS poll...")
            new_rss_posts = poll_rss_feeds()
            
            for post in new_rss_posts:
                # Process each new RSS post
                logger.info(f"Processing RSS post: {post.source_name}")
                
                # 1. AI Rewrite
                rewritten = rewrite_caption(post.raw_text)
                
                # 2. Try to get media if RSS has it
                media_path = None
                if post.media_urls:
                    logger.info(f"Downloading RSS media: {post.media_urls[0]}")
                    media_path = download_media_from_url(post.media_urls[0])
                
                # 3. Update DB...
                
                # 4. Notify User
                send_suggestion(
                    caption=rewritten,
                    media_path=media_path,
                    source_info=f"Website: {post.source_name}"
                )
                
                # 5. Cleanup
                if media_path:
                    cleanup_media(media_path)
            
            logger.info(f"RSS poll complete. Sleeping for {config.POLLING_INTERVAL // 60} minutes.")
        except Exception as e:
            logger.error(f"Error in RSS task: {e}")
            
        await asyncio.sleep(config.POLLING_INTERVAL)

async def main():
    logger.info("🚀 Starting Ghana News Bot (Semi-Automated Mode)...")
    
    # Run Telegram listener and RSS poller concurrently
    await asyncio.gather(
        start_listening(),
        rss_task()
    )

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Bot stopped by user.")
