"""
convert_cookies.py - Converts Cookie-Editor JSON export to Playwright session format.

Steps:
1. Install Cookie-Editor Chrome extension
2. Go to x.com (logged in)
3. Click Cookie-Editor icon -> Export (copies JSON to clipboard)
4. Paste into x_cookies_raw.json in this folder
5. Run: python convert_cookies.py
"""

import base64
import json
import sys
import time
import os

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")

RAW_FILE = "x_cookies_raw.json"
SESSION_FILE = "x_session.json"


def main():
    print("=" * 60)
    print("  Cookie-Editor -> Playwright Session Converter")
    print("=" * 60)

    if not os.path.exists(RAW_FILE):
        print(f"\n[!] '{RAW_FILE}' not found in this folder.")
        print("    Export cookies from Cookie-Editor and save as x_cookies_raw.json")
        sys.exit(1)

    with open(RAW_FILE, "r", encoding="utf-8") as f:
        raw = json.load(f)

    print(f"[OK] Loaded {len(raw)} cookies from {RAW_FILE}")

    # Validate auth_token is present
    auth = next((c for c in raw if c.get("name") == "auth_token"), None)
    if not auth:
        print("\n[!] 'auth_token' not found in the exported cookies.")
        print("    Make sure you are logged into x.com before exporting.")
        sys.exit(1)

    print(f"[OK] auth_token found - you are logged in as: (cookie present)")

    # Build Playwright storage_state format
    playwright_cookies = []
    for c in raw:
        name = c.get("name", "")
        value = c.get("value", "")
        domain = c.get("domain", ".x.com")

        if not domain.startswith("."):
            domain = f".{domain}"

        # sameSite mapping
        same_site = c.get("sameSite", "no_restriction") or "no_restriction"
        same_site_map = {
            "strict": "Strict",
            "lax": "Lax",
            "no_restriction": "None",
            "none": "None",
            "unspecified": "None",
        }
        same_site = same_site_map.get(same_site.lower(), "None")

        expires = c.get("expirationDate", None) or c.get("expires", None)
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

    state = {"cookies": playwright_cookies, "origins": []}

    with open(SESSION_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2)

    print(f"[OK] Playwright session saved to {SESSION_FILE}")
    print(f"     Total cookies: {len(playwright_cookies)}")

    # Base64 encode for Railway
    with open(SESSION_FILE, "rb") as f:
        encoded = base64.b64encode(f.read()).decode("utf-8")

    print("\n" + "=" * 60)
    print("  Add this to your Railway environment variables:")
    print("=" * 60)
    print(f"\nX_SESSION_COOKIES={encoded}\n")
    print("=" * 60)
    print("\n[!] Done! Paste X_SESSION_COOKIES into Railway and deploy.")
    print("    x_cookies_raw.json and x_session.json are in .gitignore.\n")


if __name__ == "__main__":
    main()
