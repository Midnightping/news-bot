from supabase import create_client, Client
import config
import logging

# Configure logging
logging.basicConfig(level=logging.INFO if not config.DEBUG else logging.DEBUG)
logger = logging.getLogger(__name__)

class Database:
    def __init__(self):
        if not config.SUPABASE_URL or not config.SUPABASE_SERVICE_ROLE_KEY:
            logger.error("Supabase credentials missing!")
            self.client = None
        else:
            self.client: Client = create_client(config.SUPABASE_URL, config.SUPABASE_SERVICE_ROLE_KEY)
            logger.info("Supabase client initialized.")

    def add_pending_post(self, post_data):
        """
        post_data should be a dict matching the 'posts' table schema.
        """
        if not self.client: return None
        
        try:
            result = self.client.table("posts").insert(post_data).execute()
            return result.data
        except Exception as e:
            # If video_link column is missing, retry without it
            if "video_link" in str(e) and "video_link" in post_data:
                logger.warning("⚠️ 'video_link' column missing in Supabase. Saving without it.")
                temp_data = post_data.copy()
                temp_data.pop("video_link")
                try:
                    result = self.client.table("posts").insert(temp_data).execute()
                    return result.data
                except Exception as retry_e:
                    logger.error(f"Retry failed: {retry_e}")
            else:
                logger.error(f"Error adding post: {e}")
            return None

    def check_duplicate(self, content_hash):
        if not self.client: return False
        
        try:
            result = self.client.table("posts").select("id").eq("content_hash", content_hash).execute()
            return len(result.data) > 0
        except Exception as e:
            logger.error(f"Error checking duplicate: {e}")
            return False

    def get_recent_posts(self, limit=50):
        if not self.client: return []
        
        try:
            result = self.client.table("posts").select("original_text").order("created_at", desc=True).limit(limit).execute()
            return [p['original_text'] for p in result.data if p['original_text']]
        except Exception as e:
            logger.error(f"Error fetching recent posts: {e}")
            return []

    def update_post_status(self, post_id, status, tweet_id=None, error_message=None):
        if not self.client: return
        
        update_data = {"status": status}
        if tweet_id: update_data["tweet_id"] = tweet_id
        if error_message: update_data["error_message"] = error_message
        if status == "posted":
            from datetime import datetime
            update_data["posted_at"] = datetime.now().isoformat()

        try:
            self.client.table("posts").update(update_data).eq("id", post_id).execute()
        except Exception as e:
            logger.error(f"Error updating post status: {e}")

# Global instance
db = Database()
