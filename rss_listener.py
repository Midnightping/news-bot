import feedparser
import logging
import config
import time
from datetime import datetime, timedelta
from normalization import normalize_rss
from database import db

logger = logging.getLogger(__name__)

# List of RSS feeds for Ghana news
GH_RSS_FEEDS = [
    {"name": "Citi Newsroom", "url": "https://citinewsroom.com/feed/"},
    {"name": "Pulse Ghana", "url": "https://www.pulse.com.gh/rss"},
    {"name": "Joy Online", "url": "https://www.myjoyonline.com/feed/"},
    {"name": "GhanaWeb", "url": "https://www.ghanaweb.com/GhanaHomePage/rss/news.xml"},
    {"name": "Adom Online", "url": "https://www.adomonline.com/feed/"},
    {"name": "Yen.com.gh", "url": "https://yen.com.gh/rss/all.xml"},
    {"name": "Graphic Online", "url": "https://www.graphic.com.gh/news.feed?type=rss"}
]

def is_fresh(entry):
    """Checks if an RSS entry was published within the last 2 hours."""
    published = entry.get('published_parsed')
    if not published: return True # If no date, assume fresh
    
    # Convert to timestamp
    pub_time = time.mktime(published)
    now = time.time()
    
    # 2 hours = 7200 seconds
    return (now - pub_time) < 7200

def poll_rss_feeds():
    logger.info("Polling RSS feeds...")
    new_posts = []
    
    for feed in GH_RSS_FEEDS:
        try:
            d = feedparser.parse(feed['url'])
            for entry in d.entries[:10]:
                # 1. Check if it's actually current news
                if not is_fresh(entry):
                    logger.debug(f"Skipping old post: {entry.get('title')}")
                    continue
                    
                normalized = normalize_rss(entry, feed['name'])
                
                # 2. Check if duplicate
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
