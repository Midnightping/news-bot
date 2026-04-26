import hashlib
import re

class NormalizedPost:
    def __init__(self, source_type, source_name, source_id, raw_text, media_urls=None, media_type='none', video_link=None):
        self.source_type = source_type # 'telegram', 'rss', 'x'
        self.source_name = source_name
        self.source_id = str(source_id)
        self.raw_text = raw_text
        self.media_urls = media_urls or []
        self.media_type = media_type # 'image', 'video', 'none'
        self.video_link = video_link
        self.content_hash = self._generate_hash()

    def _generate_hash(self):
        # Normalize text: lowercase and remove extra whitespace
        clean_text = re.sub(r'\s+', ' ', self.raw_text).strip().lower()
        return hashlib.sha256(clean_text.encode()).hexdigest()

    def to_dict(self):
        return {
            "source_channel": self.source_name,
            "source_message_id": self.source_id if self.source_id.isdigit() else None,
            "original_text": self.raw_text,
            "content_hash": self.content_hash,
            "media_type": self.media_type,
            "video_link": self.video_link,
            "status": "pending"
        }

def normalize_telegram(message, channel_name):
    # Defensive check: if message is a string, handle it
    if isinstance(message, str):
        text = message
        media_type = 'none'
        msg_id = "unknown"
    else:
        text = getattr(message, 'text', getattr(message, 'message', "")) or message.caption or ""
        media_type = 'none'
        if getattr(message, 'photo', None): media_type = 'image'
        elif getattr(message, 'video', None): media_type = 'video'
        msg_id = getattr(message, 'id', 'unknown')
    
    video_link = None
    if any(site in text for site in ["tiktok.com", "instagram.com", "youtube.com", "youtu.be"]):
        links = re.findall(r'(https?://\S+)', text)
        for l in links:
            if any(x in l for x in ["tiktok", "instagram", "youtube", "youtu.be"]):
                video_link = l
                break
    
    return NormalizedPost(
        source_type='telegram',
        source_name=channel_name,
        source_id=msg_id,
        raw_text=text,
        media_type=media_type,
        video_link=video_link
    )

def normalize_rss(entry, source_name):
    text = entry.get('summary', entry.get('title', ''))
    source_id = entry.get('id', entry.get('link', ''))
    
    # Try to find an image in enclosures or media:content
    media_url = None
    if 'links' in entry:
        for link in entry.links:
            if 'image' in link.get('type', ''):
                media_url = link.get('href')
                break
    
    if not media_url and 'media_content' in entry:
        media_url = entry.media_content[0].get('url')

    video_link = None
    all_text = f"{entry.get('title', '')} {text}"
    if any(site in all_text for site in ["tiktok.com", "instagram.com", "youtube.com", "youtu.be"]):
        links = re.findall(r'(https?://\S+)', all_text)
        for l in links:
            if any(x in l for x in ["tiktok", "instagram", "youtube", "youtu.be"]):
                video_link = l
                break
        
    return NormalizedPost(
        source_type='rss',
        source_name=source_name,
        source_id=source_id,
        raw_text=text,
        media_urls=[media_url] if media_url else [],
        media_type='image' if media_url else 'none',
        video_link=video_link
    )
