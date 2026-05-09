"""
x_poster.py - Posts to X using Playwright browser automation.

No X API key needed. Uses a saved browser session from X_SESSION_COOKIES
(base64-encoded Playwright storage_state JSON).
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

# Global lock to ensure only one browser process runs at a time.
_browser_lock = asyncio.Lock()

# Track daily post count in memory (resets when bot restarts).
_daily_post_count = 0
_last_reset_day = None
_last_post_time = 0
MAX_X_POST_CHARS = 280


def _check_rate_limits() -> tuple[bool, str]:
    """Returns (ok, reason). Enforces daily cap and per-post cooldown."""
    global _daily_post_count, _last_reset_day, _last_post_time

    from datetime import datetime

    today = datetime.utcnow().date()

    if _last_reset_day != today:
        _daily_post_count = 0
        _last_reset_day = today

    if _daily_post_count >= config.MAX_POSTS_PER_DAY:
        return False, f"Daily X post limit reached ({config.MAX_POSTS_PER_DAY} posts/day)"

    elapsed = time.time() - _last_post_time
    if _last_post_time > 0 and elapsed < config.POSTING_INTERVAL:
        remaining = int(config.POSTING_INTERVAL - elapsed)
        return False, f"Cooldown active - {remaining}s until next post is allowed"

    return True, "ok"


def _load_session_to_tempfile() -> str | None:
    """Decodes X_SESSION_COOKIES and writes it to a temp storage_state file."""
    encoded = config.X_SESSION_COOKIES
    if not encoded:
        logger.error("X_SESSION_COOKIES env var is not set. Run capture_x_session.py first.")
        return None

    try:
        decoded = base64.b64decode(encoded.encode("utf-8"))
        json.loads(decoded)

        tmp = tempfile.NamedTemporaryFile(
            mode="wb", suffix=".json", delete=False, prefix="x_session_"
        )
        tmp.write(decoded)
        tmp.flush()
        tmp.close()
        return tmp.name
    except Exception as e:
        logger.error(f"Failed to decode X_SESSION_COOKIES: {e}")
        return None


def _split_plain_text(text: str, limit: int) -> list[str]:
    """Splits text into chunks at readable boundaries without exceeding limit."""
    clean = " ".join(text.split())
    chunks: list[str] = []

    while clean:
        if len(clean) <= limit:
            chunks.append(clean)
            break

        boundary = -1
        for marker in [". ", "? ", "! ", "; ", ": ", ", ", " "]:
            candidate = clean.rfind(marker, 0, limit + 1)
            if candidate > boundary:
                boundary = candidate + (1 if marker == " " else 2)

        if boundary < int(limit * 0.55):
            boundary = limit

        chunks.append(clean[:boundary].strip())
        clean = clean[boundary:].strip()

    return [chunk for chunk in chunks if chunk]


def _split_thread_text(text: str) -> list[str]:
    """Returns one or more X post bodies, adding counters when a thread is needed."""
    clean = " ".join(text.split())
    if len(clean) <= MAX_X_POST_CHARS:
        return [clean]

    max_posts = max(1, config.X_THREAD_MAX_POSTS)
    reserve = len(f"\n\n{max_posts}/{max_posts}")
    body_limit = MAX_X_POST_CHARS - reserve
    parts = _split_plain_text(clean, body_limit)

    if len(parts) > max_posts:
        logger.warning(
            f"Long X text needed {len(parts)} thread posts; limiting to {max_posts}."
        )
        parts = parts[:max_posts]

    total = len(parts)
    if total == 1:
        return parts

    return [f"{part}\n\n{i}/{total}" for i, part in enumerate(parts, start=1)]


async def _find_compose_box(page, index: int):
    """Finds the compose textbox for the given thread index."""
    indexed_selectors = [
        f'[data-testid="tweetTextarea_{index}"]',
        f'[data-testid="tweetTextarea_{index}RichEditor"]',
    ]

    if index == 0:
        indexed_selectors.extend(
            [
                '[aria-label="Post text"]',
                'div[role="textbox"]',
            ]
        )

    for selector in indexed_selectors:
        try:
            box = await page.wait_for_selector(selector, timeout=10000, state="visible")
            if box:
                logger.info(f"Compose box {index + 1} found with selector: {selector}")
                return box
        except Exception:
            continue

    try:
        boxes = await page.query_selector_all('div[role="textbox"]')
        if boxes and len(boxes) > index:
            logger.info(f"Compose box {index + 1} found from textbox list.")
            return boxes[index]
        if boxes:
            logger.info(f"Compose box {index + 1} using last textbox fallback.")
            return boxes[-1]
    except Exception:
        pass

    return None


async def _click_add_post(page) -> bool:
    """Clicks X's add-post control to extend the current compose into a thread."""
    add_selectors = [
        '[data-testid="addButton"]',
        'button[aria-label="Add post"]',
        'div[aria-label="Add post"]',
        'button[aria-label="Add another post"]',
        'div[aria-label="Add another post"]',
        'button:has-text("Add")',
        'div[role="button"]:has-text("Add")',
    ]

    for selector in add_selectors:
        try:
            btn = await page.wait_for_selector(selector, timeout=5000, state="visible")
            if btn and await btn.get_attribute("aria-disabled") != "true":
                await btn.click(timeout=10000)
                logger.info(f"Clicked add-post button with selector: {selector}")
                await page.wait_for_timeout(1000)
                return True
        except Exception:
            continue

    return False


async def _run_playwright_post(
    thread_parts: list[str], media_path: str | None, session_file: str
) -> bool:
    """Runs one Playwright posting attempt. The caller owns timeout/locking."""
    from playwright.async_api import async_playwright

    browser = None
    async with async_playwright() as p:
        try:
            browser = await p.chromium.launch(
                headless=True,
                timeout=30000,
                args=[
                    "--no-sandbox",
                    "--disable-setuid-sandbox",
                    "--disable-dev-shm-usage",
                    "--disable-blink-features=AutomationControlled",
                ],
            )

            context = await browser.new_context(
                storage_state=session_file,
                viewport={"width": 1280, "height": 900},
                user_agent=(
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/124.0.0.0 Safari/537.36"
                ),
            )

            page = await context.new_page()

            logger.info("Opening X compose page...")
            try:
                await page.goto(
                    "https://x.com/compose/post",
                    wait_until="domcontentloaded",
                    timeout=45000,
                )
                try:
                    await page.wait_for_load_state("networkidle", timeout=10000)
                except Exception:
                    logger.info("X did not reach networkidle quickly; continuing after DOM load.")
            except Exception as e:
                logger.warning(f"Page load timeout/error (continuing anyway): {e}")

            await page.wait_for_timeout(3000)

            current_url = page.url
            if "login" in current_url or "i/flow/login" in current_url:
                logger.error(
                    "X session has expired. Re-run capture_x_session.py locally "
                    "and update X_SESSION_COOKIES in Railway."
                )
                return False

            logger.info("X session valid; composing tweet...")

            for popup_selector in [
                '[data-testid="app-dismiss"]',
                'div[role="button"]:has-text("Got it")',
                'div[role="button"]:has-text("Dismiss")',
                'button:has-text("Got it")',
                'button:has-text("Dismiss")',
            ]:
                try:
                    btn = await page.query_selector(popup_selector)
                    if btn:
                        await btn.click(timeout=3000)
                        await page.wait_for_timeout(500)
                except Exception:
                    pass

            compose_box = await _find_compose_box(page, 0)
            if not compose_box:
                logger.error(f"Could not find the tweet compose box on X. Current URL: {page.url}")
                await page.screenshot(path="x_error_debug.png", full_page=True)
                return False

            await compose_box.click(timeout=10000)
            await page.wait_for_timeout(500)

            logger.info("Typing X post content...")
            await page.keyboard.type(thread_parts[0], delay=25)
            await page.wait_for_timeout(1000)

            if media_path and os.path.exists(media_path):
                logger.info(f"Attaching media: {os.path.basename(media_path)}")
                try:
                    media_input = await page.query_selector('input[data-testid="fileInput"]')
                    if media_input:
                        await media_input.set_input_files(media_path, timeout=30000)
                        try:
                            await page.wait_for_selector(
                                '[data-testid="attachments"]', timeout=30000
                            )
                        except Exception:
                            logger.info("Media preview selector not found; waiting briefly.")
                            await page.wait_for_timeout(5000)
                        logger.info("Media upload step completed.")
                    else:
                        logger.warning("Media upload input not found; posting text only.")
                except Exception as e:
                    logger.warning(f"Media upload failed ({e}); posting text only.")

            for index, part in enumerate(thread_parts[1:], start=1):
                logger.info(f"Adding thread post {index + 1}/{len(thread_parts)}...")
                if not await _click_add_post(page):
                    logger.error("Could not find X add-post button for thread creation.")
                    await page.screenshot(path="x_error_no_add_post_button.png", full_page=True)
                    return False

                next_box = await _find_compose_box(page, index)
                if not next_box:
                    logger.error(f"Could not find compose box for thread post {index + 1}.")
                    await page.screenshot(path="x_error_thread_compose_box.png", full_page=True)
                    return False

                await next_box.click(timeout=10000)
                await page.wait_for_timeout(300)
                await page.keyboard.type(part, delay=25)
                await page.wait_for_timeout(700)

            post_button_selectors = [
                'button:has-text("Post all")',
                'div[role="button"]:has-text("Post all")',
                '[data-testid="tweetButtonInline"]',
                '[data-testid="tweetButton"]',
                'button[data-testid="tweetButtonInline"]',
                'button:has-text("Post")',
                'div[role="button"]:has-text("Post")',
            ]

            post_button = None
            for selector in post_button_selectors:
                try:
                    btn = await page.wait_for_selector(selector, timeout=5000, state="visible")
                    if btn and await btn.get_attribute("aria-disabled") != "true":
                        post_button = btn
                        logger.info(f"Post button found with selector: {selector}")
                        break
                except Exception:
                    continue

            if not post_button:
                logger.error(f"Could not find an enabled Post button. Current URL: {page.url}")
                await page.screenshot(path="x_error_no_post_button.png", full_page=True)
                return False

            await post_button.click(timeout=15000)
            logger.info("Post button clicked; waiting for X to accept it...")

            try:
                await page.wait_for_selector('[data-testid="toast"]', timeout=15000)
                logger.info("X displayed a post confirmation toast.")
                return True
            except Exception:
                pass

            await page.wait_for_timeout(5000)
            compose_after = await page.query_selector(
                '[data-testid="tweetTextarea_0"], div[role="textbox"]'
            )
            if not compose_after:
                logger.info("Tweet likely posted; compose box disappeared.")
                return True

            text_after = await compose_after.text_content()
            if not text_after or text_after.strip() == "":
                logger.info("Tweet posted successfully; compose box cleared.")
                return True

            logger.warning("Compose box still has text after clicking Post; tweet may not have posted.")
            await page.screenshot(path="x_error_post_not_sent.png", full_page=True)
            return False
        finally:
            if browser:
                try:
                    await browser.close()
                except Exception:
                    pass


async def post_to_x(text: str, media_path: str | None = None, post_id: str | None = None) -> bool:
    """
    Posts a tweet to X using Playwright.

    Args:
        text: The X post text. Long text is posted as a thread.
        media_path: Optional local file path to an image or video to attach
        post_id: Optional DB post ID to update status in Supabase

    Returns:
        True if posted successfully, False otherwise
    """
    global _daily_post_count, _last_post_time

    if not text or not text.strip():
        logger.warning("Skipping X post - text is empty.")
        return False

    thread_parts = _split_thread_text(text)
    if len(thread_parts) > 1:
        logger.info(f"X text split into {len(thread_parts)} thread posts.")

    ok, reason = _check_rate_limits()
    if not ok:
        logger.info(f"X post skipped: {reason}")
        return False

    session_file = _load_session_to_tempfile()
    if not session_file:
        return False

    success = False
    logger.info("Waiting for X browser lock...")
    async with _browser_lock:
        logger.info("Browser lock acquired - starting X post process...")
        try:
            timeout_seconds = config.X_POST_TIMEOUT_SECONDS + max(0, len(thread_parts) - 1) * 30
            success = await asyncio.wait_for(
                _run_playwright_post(thread_parts, media_path, session_file),
                timeout=timeout_seconds,
            )
        except asyncio.TimeoutError:
            logger.error(
                f"X posting timed out after {timeout_seconds}s; "
                "releasing browser lock so later posts can continue."
            )
            success = False
        except Exception as e:
            logger.exception(f"Playwright error while posting to X: {e}")
            success = False
        finally:
            try:
                if session_file and os.path.exists(session_file):
                    os.remove(session_file)
            except Exception:
                pass

    if success:
        _daily_post_count += 1
        _last_post_time = time.time()
        logger.info(f"X posts today: {_daily_post_count}/{config.MAX_POSTS_PER_DAY}")

        if post_id:
            from database import db

            db.update_post_status(post_id, "posted")
    else:
        if post_id:
            from database import db

            db.update_post_status(post_id, "failed", error_message="Playwright posting failed")

    return success


if __name__ == "__main__":
    import sys

    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

    test_text = "TEST: Ghana News Bot X integration is live. Ignore this tweet."
    test_media = sys.argv[1] if len(sys.argv) > 1 else None

    print(f"\nTest tweet: {test_text}")
    print(f"Media: {test_media or 'None'}\n")

    result = asyncio.run(post_to_x(test_text, media_path=test_media))
    print(f"\n{'SUCCESS' if result else 'FAILED'}")
