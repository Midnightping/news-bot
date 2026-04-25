import requests
import os
import config
import logging
import uuid

logger = logging.getLogger(__name__)

def download_media_from_url(url):
    """
    Downloads media from a URL and saves it to the temp directory.
    Returns the local path.
    """
    if not url: return None
    
    try:
        response = requests.get(url, stream=True, timeout=30)
        if response.status_code == 200:
            # Determine extension
            content_type = response.headers.get('content-type', '')
            ext = ".jpg" # Default
            if 'video' in content_type: ext = ".mp4"
            elif 'png' in content_type: ext = ".png"
            elif 'gif' in content_type: ext = ".gif"
            
            filename = f"{uuid.uuid4()}{ext}"
            filepath = os.path.join(config.MEDIA_TEMP_DIR, filename)
            
            with open(filepath, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
            
            logger.info(f"Media downloaded to {filepath}")
            return filepath
        else:
            logger.error(f"Failed to download media: {response.status_code}")
            return None
    except Exception as e:
        logger.error(f"Error downloading media: {e}")
        return None

def cleanup_media(filepath):
    """Deletes a local file."""
    try:
        if filepath and os.path.exists(filepath):
            os.remove(filepath)
            logger.debug(f"Deleted temp file: {filepath}")
    except Exception as e:
        logger.error(f"Error deleting file {filepath}: {e}")
