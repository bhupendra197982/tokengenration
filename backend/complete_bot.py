#!/usr/bin/env python3
"""
Complete Tradetron Token Regeneration Script with Telegram Notifications
==========================================================================
Automates token regeneration on Tradetron with integrated telegram alerts.

Works as:
- Standalone script
- AWS Lambda function
- Scheduled GitHub Actions job

Configuration via environment variables:
- TRADETRON_EMAIL
- TRADETRON_PASSWORD
- TRADETRON_BROKER_ID
- TELEGRAM_BOT_TOKEN
- TELEGRAM_CHAT_ID
"""

import os
import re
import time
import urllib.parse
import requests
import hashlib
import json
import base64
import sys
import getpass

# ============================================================
# CONFIGURATION
# ============================================================

# Tradetron credentials
EMAIL = os.environ.get("TRADETRON_EMAIL", "bhupandraverma@gmail.com")
PASSWORD = os.environ.get("TRADETRON_PASSWORD", "Verma@1234")
BROKER_ID = os.environ.get("TRADETRON_BROKER_ID", "917")

# Telegram configuration
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "8499389750:AAHexwQgpvy8UWBDNJkDRQsTcCkj6St-Mxc")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "6847391264")

# ============================================================
# TRADETRON CONFIGURATION
# ============================================================

BASE_URL = "https://tradetron.tech"
ALTCHA_CHALLENGE_URL = f"{BASE_URL}/altcha-challenge"
LOGIN_PAGE_URL = f"{BASE_URL}/login"
LOGIN_POST_URL = f"{BASE_URL}/login"
BROKER_PAGE_URL = f"{BASE_URL}/user/broker-and-exchanges"
REGENERATE_URL = f"{BASE_URL}/user/broker-and-exchanges/regenerate-token/{BROKER_ID}"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) "
                  "Chrome/147.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,"
              "image/avif,image/webp,image/apng,*/*;q=0.8",
    "Accept-Language": "en-GB,en;q=0.8",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
}

# ============================================================
# TELEGRAM NOTIFICATION FUNCTIONS
# ============================================================

def send_telegram_message(message, prefix=""):
    """Send a message to Telegram chat"""
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print("⚠️  Telegram config missing - skipping notification")
        return

    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"

    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": message
    }

    try:
        response = requests.post(url, json=payload, timeout=20)
        if response.status_code == 200:
            print(f"✓ Telegram notification sent: {message[:50]}...")
        else:
            print(f"⚠️  Telegram error: {response.status_code}")
    except Exception as e:
        print(f"⚠️  Telegram error: {e}")

def notify_start():
    """Notify that script has started"""
    send_telegram_message("🤖 Tradetron Token Regeneration Started")

def notify_success():
    """Notify successful token regeneration"""
    send_telegram_message("✅ Token Regeneration SUCCESSFUL!")

def notify_login_failed():
    """Notify login failure"""
    send_telegram_message("❌ Login FAILED - Check credentials")

def notify_regeneration_failed():
    """Notify regeneration failure"""
    send_telegram_message("❌ Token Regeneration FAILED - Check Tradetron UI")

def notify_error(error_msg):
    """Notify generic error"""
    send_telegram_message(f"❌ Error: {error_msg}")

# ============================================================
# TRADETRON TOKEN REGENERATION FUNCTIONS
# ============================================================

def solve_altcha_challenge(session):
    """
    Fetch and solve the Altcha proof-of-work challenge.
    Altcha requires finding a number n where SHA-256(salt + n) == challenge.
    """
    print(" Fetching Altcha challenge...")

    resp = session.get(
        ALTCHA_CHALLENGE_URL,
        headers={
            **HEADERS,
            "Accept": "application/json",
            "Referer": LOGIN_PAGE_URL,
        },
    )

    resp.raise_for_status()
    data = resp.json()

    algorithm = data["algorithm"]
    challenge = data["challenge"]
    maxnumber = data["maxnumber"]
    salt = data["salt"]
    signature = data["signature"]

    if algorithm != "SHA-256":
        raise RuntimeError(f"Unsupported Altcha algorithm: {algorithm}")

    print(f" Solving challenge (max {maxnumber} iterations)...")

    # Brute-force: find n where SHA-256(salt + str(n)) == challenge
    solution = None

    for n in range(maxnumber + 1):
        hash_hex = hashlib.sha256(f"{salt}{n}".encode()).hexdigest()

        if hash_hex == challenge:
            solution = n
            break

    if solution is None:
        raise RuntimeError("Failed to solve Altcha challenge")

    print(f" ✓ Challenge solved! (n={solution})")

    payload = {
        "algorithm": algorithm,
        "challenge": challenge,
        "number": solution,
        "salt": salt,
        "signature": signature,
    }

    return base64.b64encode(json.dumps(payload).encode()).decode()

def get_xsrf_token_decoded(session):
    """Extract and URL-decode the XSRF-TOKEN from session cookies"""
    token = session.cookies.get("XSRF-TOKEN", domain="tradetron.tech")

    if not token:
        token = session.cookies.get("XSRF-TOKEN")

    if not token:
        raise RuntimeError("XSRF-TOKEN not found in cookies")

    return urllib.parse.unquote(token)

def extract_csrf_from_html(html):
    """Extract the CSRF token from the login page HTML form"""
    patterns = [
        r'name="_token"\s+value="([^"]+)"',
        r'value="([^"]+)"\s+name="_token"',
        r'name="csrf-token"\s+content="([^"]+)"',
        r'<meta\s+name="csrf-token"\s+content="([^"]+)"',
        r'<meta\s+content="([^"]+)"\s+name="csrf-token"',
        r'"_token"\s*:\s*"([^"]+)"',
        r"'_token'\s*:\s*'([^']+)'",
    ]

    for pattern in patterns:
        match = re.search(pattern, html, re.IGNORECASE)

        if match:
            return match.group(1)

    raise RuntimeError("Could not extract CSRF token from login page")

def login(session):
    """Login to Tradetron and establish an authenticated session"""
    print("[1/3] Loading login page...")

    resp = session.get(LOGIN_PAGE_URL, headers=HEADERS)
    resp.raise_for_status()

    # Extract CSRF token from HTML
    csrf_token = None
    try:
        csrf_token = extract_csrf_from_html(resp.text)
        print(f" CSRF token from HTML: {csrf_token[:20]}...")
    except RuntimeError:
        print(" No CSRF token in HTML, will use XSRF cookie instead.")

    # Get XSRF token from cookies
    xsrf_token = get_xsrf_token_decoded(session)
    print(f" XSRF cookie token obtained: {xsrf_token[:20]}...")

    # If no form CSRF token, use the XSRF cookie value
    if not csrf_token:
        csrf_token = xsrf_token

    # Solve Altcha challenge
    altcha_payload = solve_altcha_challenge(session)

    print("[2/3] Logging in...")

    login_headers = {
        **HEADERS,
        "Content-Type": "application/x-www-form-urlencoded",
        "Referer": LOGIN_PAGE_URL,
        "Origin": BASE_URL,
        "X-XSRF-TOKEN": xsrf_token,
    }

    login_data = {
        "_token": csrf_token,
        "email": EMAIL,
        "password": PASSWORD,
        "altcha": altcha_payload,
    }

    resp = session.post(
        LOGIN_POST_URL,
        data=login_data,
        headers=login_headers,
        allow_redirects=True,
    )

    print(f" Post-login URL: {resp.url}")
    print(f" Post-login status: {resp.status_code}")

    # Check if login failed
    if resp.url.rstrip("/").endswith("/login"):
        if "These credentials do not match" in resp.text:
            print(" ✗ Login FAILED: Invalid email or password.")
            notify_login_failed()
            return False

        if "Too Many Attempts" in resp.text:
            print(" ✗ Login FAILED: Too many attempts. Please wait and try again.")
            notify_error("Too many login attempts")
            return False

        print(" ✗ Login FAILED: Still on login page after POST.")
        notify_login_failed()
        return False

    print(" ✓ Login successful!")
    return True

def regenerate_token(session):
    """Call the regenerate-token endpoint"""
    print(f"[3/3] Regenerating token for broker ID {BROKER_ID}...")

    # Refresh XSRF token
    xsrf_token = get_xsrf_token_decoded(session)

    regen_headers = {
        **HEADERS,
        "Referer": BROKER_PAGE_URL,
        "X-XSRF-TOKEN": xsrf_token,
    }

    resp = session.get(
        REGENERATE_URL,
        headers=regen_headers,
        allow_redirects=True,
    )

    # Check for successful regeneration
    if resp.status_code == 200 and "broker-and-exchanges" in resp.url:
        print(" ✓ Token regenerated successfully!")
        print(f" Final URL: {resp.url}")
        return True

    if resp.status_code == 200:
        print(f" ✓ Request completed (status: {resp.status_code})")
        print(f" Final URL: {resp.url}")

        if "Token regenerated" in resp.text or "success" in resp.text.lower():
            print(" ✓ Token regeneration confirmed!")
            return True

    print(f" ✗ Unexpected response: {resp.status_code}")
    print(f" URL: {resp.url}")
    notify_regeneration_failed()
    return False

# ============================================================
# MAIN EXECUTION
# ============================================================

def main():
    """Main function to execute token regeneration"""
    global EMAIL, PASSWORD

    # Validate credentials - prompt interactively if not set
    if EMAIL == "YOUR_EMAIL_HERE":
        EMAIL = input("Enter your Tradetron email: ").strip()
    if PASSWORD == "YOUR_PASSWORD_HERE":
        PASSWORD = getpass.getpass("Enter your Tradetron password: ")

    if not EMAIL or not PASSWORD:
        print("ERROR: Email and password are required.")
        return {
            "statusCode": 400,
            "body": "Missing credentials"
        }

    print("=" * 60)
    print(" Tradetron Broker Token Regenerator")
    print(f" Broker ID: {BROKER_ID}")
    print(f" Email: {EMAIL}")
    print("=" * 60)
    print()

    session = requests.Session()

    # Send start notification
    notify_start()

    try:
        if not login(session):
            print("\nAborting due to login failure.")
            return {
                "statusCode": 401,
                "body": "Login failed"
            }

        # Small delay to be safe
        time.sleep(1)

        if regenerate_token(session):
            print("\n✓ Done! Token regeneration completed successfully.")
            notify_success()
            return {
                "statusCode": 200,
                "body": "Success"
            }
        else:
            print("\n✗ Token regeneration may have failed. Check Tradetron UI.")
            return {
                "statusCode": 500,
                "body": "Token regeneration failed"
            }

    except requests.exceptions.ConnectionError as e:
        print(f"\n✗ Connection error: {e}")
        notify_error(f"Connection error: {str(e)}")
        return {
            "statusCode": 500,
            "body": f"Connection error: {str(e)}"
        }

    except requests.exceptions.Timeout as e:
        print(f"\n✗ Request timed out: {e}")
        notify_error(f"Request timeout: {str(e)}")
        return {
            "statusCode": 500,
            "body": f"Request timeout: {str(e)}"
        }

    except RuntimeError as e:
        print(f"\n✗ Error: {e}")
        notify_error(str(e))
        return {
            "statusCode": 500,
            "body": str(e)
        }

    except Exception as e:
        print(f"\n✗ Unexpected error: {type(e).__name__}: {e}")
        notify_error(f"{type(e).__name__}: {str(e)}")
        return {
            "statusCode": 500,
            "body": f"{type(e).__name__}: {str(e)}"
        }

# ============================================================
# ENTRY POINTS
# ============================================================

def lambda_handler(event, context):
    """AWS Lambda handler"""
    return main()

if __name__ == "__main__":
    result = main()
    # Exit with appropriate status code for standalone execution
    if isinstance(result, dict):
        status_code = result.get("statusCode", 500)
        sys.exit(0 if status_code == 200 else 1)
    sys.exit(0)
