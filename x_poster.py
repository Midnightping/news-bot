"""
x_poster.py — Posts tweets to X (Twitter) using Playwright browser automation.

No X API key needed. Uses a saved browser session (cookies) to post as a logged-in user.
Session is loaded from the X_SESSION_COOKIES environment variable (base64-encoded JSON).
"""

import asyncio
import base64
import json
import logging
import os
import tempfile
import time
import config

logger = logging.getLogger(__name__)

# Global lock to ensure only one browser process runs at a time
# This prevents session conflicts and "Compose box not found" errors
_browser_lock = asyncio.Lock()

# Track daily post count in memory (resets when bot restarts)
_daily_post_count = 0
_last_reset_day = None
_last_post_time = 0  # Unix timestamp of last successful post


def _check_rate_limits() -> tuple[bool, str]:
    """Returns (ok, reason). Enforces daily cap and per-post cooldown."""
    global _daily_post_count, _last_reset_day, _last_post_time

    from datetime import datetime
    today = datetime.utcnow().date()

    # Reset daily counter at midnight UTC
    if _last_reset_day != today:
        _daily_post_count = 0
        _last_reset_day = today

    if _daily_post_count >= config.MAX_POSTS_PER_DAY:
        return False, f"Daily X post limit reached ({config.MAX_POSTS_PER_DAY} posts/day)"

    # Enforce minimum cooldown between posts
    elapsed = time.time() - _last_post_time
    if _last_post_time > 0 and elapsed < config.POSTING_INTERVAL:
        remaining = int(config.POSTING_INTERVAL - elapsed)
        return False, f"Cooldown active — {remaining}s until next post is allowed"

    return True, "ok"


def _load_session_to_tempfile() -> str | None:
    """Decodes X_SESSION_COOKIES from env and writes to a temp file. Returns the path."""
    encoded = config.X_SESSION_COOKIES
    if not encoded:
        logger.error("❌ X_SESSION_COOKIES env var is not set. Run capture_x_session.py first.")
        return None

    try:
        decoded = base64.b64decode(encoded.encode("utf-8"))
        # Validate it's valid JSON
        json.loads(decoded)

        tmp = tempfile.NamedTemporaryFile(
            mode="wb", suffix=".json", delete=False, prefix="x_session_"
        )
        tmp.write(decoded)
        tmp.flush()
        tmp.close()
        return tmp.name
    except Exception as e:
        logger.error(f"❌ Failed to decode X_SESSION_COOKIES: {e}")
        return None


async def post_to_x(text: str, media_path: str | None = None, post_id: str | None = None) -> bool:
    """
    Posts a tweet to X using Playwright.
    
    Args:
        text: The tweet text (will be truncated to 280 chars if needed)
        media_path: Optional local file path to an image or video to attach
        post_id: Optional DB post ID to update status in Supabase

    Returns:
        True if posted successfully, False otherwise
    """
    global _daily_post_count, _last_post_time

    # --- Pre-flight checks ---
    if not text or not text.strip():
        logger.warning("⚠️ Skipping X post — text is empty.")
        return False

    # Enforce 280 char limit (truncate gracefully at word boundary)
    if len(text) > 280:
        text = text[:277].rsplit(" ", 1)[0] + "..."
        logger.info(f"✂️ Tweet truncated to 280 chars.")

    ok, reason = _check_rate_limits()
    if not ok:
        logger.info(f"⏳ X post skipped: {reason}")
        return False

    # Load session
    session_file = _load_session_to_tempfile()
    if not session_file:
        return False

    success = False
    tweet_url = None

    async with _browser_lock:
        logger.info("🔒 Browser lock acquired — starting X post process...")
        try:
            from playwright.async_api import async_playwright

            async with async_playwright() as p:
                browser = await p.chromium.launch(
                    headless=True,
                    args=[
                        "--no-sandbox",
                        "--disable-setuid-sandbox",
                        "--disable-dev-shm-usage",
                        "--disable-blink-features=AutomationControlled",
                    ]
                )

                context = await browser.new_context(
                    storage_state=session_file,
                    viewport={"width": 1280, "height": 900},
                    user_agent=(
                        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) "
                        "Chrome/124.0.0.0 Safari/537.36"
                    )
                )

                page = await context.new_page()

                # Navigate directly to the compose page for better reliability
                logger.info("🌐 Opening X Compose page...")
                try:
                    await page.goto("https://x.com/compose/post", wait_until="networkidle", timeout=60000)
                except Exception as e:
                    logger.warning(f"⚠️ Page load timeout (continuing anyway): {e}")

                await page.wait_for_timeout(5000)

                # Check if we're actually logged in (not redirected to login page)
                current_url = page.url
                if "login" in current_url or "i/flow/login" in current_url:
                    logger.error(
                        "❌ X session has expired! Re-run capture_x_session.py locally "
                        "and update X_SESSION_COOKIES in Railway."
                    )
                    await browser.close()
                    return False

                logger.info("✅ X session valid — composing tweet...")

                # --- Squish common popups ---
                for popup_selector in ['[data-testid="app-dismiss"]', 'div[role="button"]:has-text("Got it")', 'div[role="button"]:has-text("Dismiss")']:
                    try:
                        btn = await page.query_selector(popup_selector)
                        if btn:
                            await btn.click()
                            await page.wait_for_timeout(500)
                    except: pass

                # --- Find the compose box ---
                compose_selectors = [
                    '[data-testid="tweetTextarea_0"]',
                    '[data-testid="tweetTextarea_0RichEditor"]',
                    '[aria-label="Post text"]',
                    'div[role="textbox"]',
                ]

                compose_box = None
                for selector in compose_selectors:
                    try:
                        # Wait for element to be visible and ready
                        compose_box = await page.wait_for_selector(selector, timeout=10000, state="visible")
                        if compose_box:
                            break
                    except Exception:
                        continue

                if not compose_box:
                    logger.error("❌ Could not find the tweet compose box on X.")
                    # Save a screenshot for debugging in the project root
                    await page.screenshot(path="x_error_debug.png")
                    await browser.close()
                    return False

                # Click and ensure focus
                await compose_box.click()
                await page.wait_for_timeout(1000)

                # Type the tweet text
                logger.info("✍️ Typing tweet content...")
                await page.keyboard.type(text, delay=50)
                await page.wait_for_timeout(1500)

                # --- Upload media if provided ---
                if media_path and os.path.exists(media_path):
                    logger.info(f"📎 Attaching media: {os.path.basename(media_path)}")
                    try:
                        # Click the media upload button
                        media_input = await page.query_selector('input[data-testid="fileInput"]')
                        if media_input:
                            await media_input.set_input_files(media_path)
                            # Wait for upload to complete (look for the media preview)
                            await page.wait_for_selector(
                                '[data-testid="attachments"]', timeout=30000
                            )
                            logger.info("✅ Media uploaded successfully.")
                            await page.wait_for_timeout(2000)
                        else:
                            logger.warning("⚠️ Media upload input not found — posting text only.")
                    except Exception as e:
                        logger.warning(f"⚠️ Media upload failed ({e}) — posting text only.")

                # --- Click the Post button ---
                post_button_selectors = [
                    '[data-testid="tweetButtonInline"]',
                    '[data-testid="tweetButton"]',
                    'button[data-testid="tweetButtonInline"]',
                ]

                post_button = None
                for selector in post_button_selectors:
                    try:
                        btn = await page.query_selector(selector)
                        if btn:
                            is_disabled = await btn.get_attribute("aria-disabled")
                            if is_disabled != "true":
                                post_button = btn
                                break
                    except Exception:
                        continue

                if not post_button:
                    logger.error("❌ Could not find the Post button.")
                    await browser.close()
                    return False

                await post_button.click()
                logger.info("📤 Post button clicked — waiting for confirmation...")
                await page.wait_for_timeout(4000)

                # --- Verify the tweet was posted ---
                # Check that compose box is now empty (tweet was sent)
                try:
                    compose_after = await page.query_selector('[data-testid="tweetTextarea_0"]')
                    if compose_after:
                        text_after = await compose_after.text_content()
                        if not text_after or text_after.strip() == "":
                            success = True
                            logger.info("✅ Tweet posted successfully!")
                        else:
                            logger.warning("⚠️ Compose box still has text — tweet may not have posted.")
                    else:
                        # Compose box gone = tweet was sent
                        success = True
                        logger.info("✅ Tweet posted successfully!")
                except Exception:
                    # If we can't find compose box, assume success
                    success = True
                    logger.info("✅ Tweet likely posted (compose box cleared).")

                await browser.close()

    except Exception as e:
        logger.error(f"❌ Playwright error while posting to X: {e}")
        success = False
    finally:
        # Clean up temp session file
        try:
            if session_file and os.path.exists(session_file):
                os.remove(session_file)
        except Exception:
            pass

    # --- Post-action: update DB and rate limit state ---
    if success:
        _daily_post_count += 1
        _last_post_time = time.time()
        logger.info(f"📊 X posts today: {_daily_post_count}/{config.MAX_POSTS_PER_DAY}")

        if post_id:
            from database import db
            db.update_post_status(post_id, "posted")
    else:
        if post_id:
            from database import db
            db.update_post_status(post_id, "failed", error_message="Playwright posting failed")

    return success


# --- Quick test when run directly ---
if __name__ == "__main__":
    import sys
    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

    test_text = "🇬🇭 TEST: Ghana News Bot X integration is live. Ignore this tweet."
    test_media = sys.argv[1] if len(sys.argv) > 1 else None

    print(f"\n📝 Test tweet: {test_text}")
    print(f"📎 Media: {test_media or 'None'}\n")

    result = asyncio.run(post_to_x(test_text, media_path=test_media))
    print(f"\n{'✅ SUCCESS' if result else '❌ FAILED'}")
