"""
capture_x_session.py - Extracts your X (Twitter) session from your existing Chrome browser.

No browser window opens. Just make sure you are logged into X in Chrome, then run this.

Steps:
1. Log into x.com in your regular Chrome browser (if not already)
2. Close Chrome completely (important on Windows so the cookie DB isn't locked)
3. python capture_x_session.py
4. Copy the printed X_SESSION_COOKIES value into Railway env vars
"""

import base64
import json
import sys
import time

# Fix Windows console encoding
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")

SESSION_FILE = "x_session.json"

# Domains to grab cookies for
X_DOMAINS = ["x.com", ".x.com", "twitter.com", ".twitter.com"]


def extract_cookies_from_chrome():
    """Reads X/Twitter cookies from Chrome's local cookie store using rookiepy."""
    try:
        import rookiepy
        print("[*] Reading cookies from Chrome via rookiepy...")
        # Get all Chrome cookies for x.com and twitter.com
        all_cookies = []
        for domain in ["x.com", "twitter.com"]:
            try:
                cookies = rookiepy.chrome(domains=[domain])
                all_cookies.extend(cookies)
            except Exception as e:
                print(f"    [warn] Could not get cookies for {domain}: {e}")
        return all_cookies
    except Exception as e:
        print(f"[!] rookiepy failed: {e}")
        return []


def build_playwright_state(raw_cookies):
    """Converts rookiepy cookies (list of dicts) into Playwright storage_state format."""
    seen = set()
    playwright_cookies = []

    for c in raw_cookies:
        # rookiepy returns dicts with keys: name, value, domain, path, expires, secure, httpOnly, sameSite
        name = c.get("name", "")
        value = c.get("value", "")
        domain = c.get("domain", "")

        key = (name, domain)
        if key in seen:
            continue
        seen.add(key)

        if not domain.startswith("."):
            domain = f".{domain}"

        same_site = c.get("sameSite", "None") or "None"
        if same_site.lower() not in ("strict", "lax", "none"):
            same_site = "None"
        else:
            same_site = same_site.capitalize()

        expires = c.get("expires", None)
        if not expires or expires < 0:
            expires = int(time.time()) + 86400 * 365

        playwright_cookies.append({
            "name": name,
            "value": value,
            "domain": domain,
            "path": c.get("path", "/") or "/",
            "expires": int(expires),
            "httpOnly": bool(c.get("httpOnly", False)),
            "secure": bool(c.get("secure", True)),
            "sameSite": same_site,
        })

    return {
        "cookies": playwright_cookies,
        "origins": []
    }


def main():
    print("=" * 60)
    print("  X Session Extractor (reads from your Chrome cookies)")
    print("=" * 60)

    cookies = extract_cookies_from_chrome()

    if not cookies:
        print("\n[!] No cookies found. Make sure:")
        print("    1. You are logged into x.com in Chrome")
        print("    2. Chrome is fully closed before running this script")
        sys.exit(1)

    # Check the critical auth cookie exists
    auth_cookie = next((c for c in cookies if c.get("name") == "auth_token"), None)
    if not auth_cookie:
        print("\n[!] 'auth_token' cookie not found.")
        print("    This means you are not logged into X in Chrome.")
        print("    Please log into x.com in your Chrome browser first, then close Chrome and re-run.")
        sys.exit(1)

    print(f"[OK] Found {len(cookies)} X cookies (auth_token present)")

    state = build_playwright_state(cookies)

    with open(SESSION_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2)

    print(f"[OK] Session saved to {SESSION_FILE}")

    # Base64 encode for Railway
    with open(SESSION_FILE, "rb") as f:
        encoded = base64.b64encode(f.read()).decode("utf-8")

    print("\n" + "=" * 60)
    print("  Add this to your Railway environment variables:")
    print("=" * 60)
    print(f"\nX_SESSION_COOKIES={encoded}\n")
    print("=" * 60)
    print("\n[!] Keep x_session.json safe -- full account access.")
    print("    Already in .gitignore.\n")


if __name__ == "__main__":
    main()
