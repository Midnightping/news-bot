import feedparser
import logging
import config
from normalization import normalize_rss
from database import db

logger = logging.getLogger(__name__)

# List of RSS feeds for Ghana news
GH_RSS_FEEDS = [
    {"name": "Citi Newsroom", "url": "https://citinewsroom.com/feed/"},
    {"name": "Pulse Ghana", "url": "https://www.pulse.com.gh/rss"},
    {"name": "Joy Online", "url": "https://www.myjoyonline.com/feed/"},
]

def poll_rss_feeds():
    logger.info("Polling RSS feeds...")
    new_posts = []
    
    for feed in GH_RSS_FEEDS:
        try:
            d = feedparser.parse(feed['url'])
            for entry in d.entries[:10]: # Check last 10 entries
                normalized = normalize_rss(entry, feed['name'])
                
                # Check if duplicate
                if not db.check_duplicate(normalized.content_hash):
                    logger.info(f"New RSS post found: {normalized.source_name} - {normalized.content_hash[:8]}")
                    db.add_pending_post(normalized.to_dict())
                    new_posts.append(normalized)
        except Exception as e:
            logger.error(f"Error polling RSS feed {feed['name']}: {e}")
            
    return new_posts

if __name__ == "__main__":
    # Test run
    poll_rss_feeds()
