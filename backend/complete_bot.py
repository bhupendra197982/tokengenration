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

# ============================================================
# MULTI-USER CREDENTIALS
# ============================================================
# Add credentials for multiple users here
# Format: {"email": "user@example.com", "password": "password", "broker_id": "917"}
# 
# EXAMPLE - UNCOMMENT AND MODIFY TO ADD MORE USERS:
# USERS = [
#     {
#         "email": "user1@example.com",
#         "password": "user1_password",
#         "broker_id": "917"
#     },
#     {
#         "email": "user2@example.com",
#         "password": "user2_password",
#         "broker_id": "917"
#     },
#     {
#         "email": "user3@example.com",
#         "password": "user3_password",
#         "broker_id": "917"
#     }
# ]

# Default single user (used if USERS list not configured)
USERS = [
    {
        "email": os.environ.get("TRADETRON_EMAIL", "bhupandraverma@gmail.com"),
        "password": os.environ.get("TRADETRON_PASSWORD", "Verma@1234"),
        "broker_id": os.environ.get("TRADETRON_BROKER_ID", "917")
    }
]

# Backward compatibility - single user environment variables
EMAIL = os.environ.get("TRADETRON_EMAIL", "bhupandraverma@gmail.com")
PASSWORD = os.environ.get("TRADETRON_PASSWORD", "Verma@1234")
BROKER_ID = os.environ.get("TRADETRON_BROKER_ID", "917")

# Telegram configuration
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "8499389750:AAHexwQgpvy8UWBDNJkDRQsTcCkj6St-Mxc")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "6847391264")

# ============================================================
# MULTI-TELEGRAM BOT CONFIGURATION
# ============================================================
# Add multiple telegram bots/channels for notifications
# Format: {"name": "Bot Name", "token": "BOT_TOKEN", "chat_id": "CHAT_ID"}
#
# EXAMPLE - UNCOMMENT AND MODIFY TO ADD MORE TELEGRAM BOTS:
# TELEGRAM_BOTS = [
#     {
#         "name": "Main Bot",
#         "token": "8499389750:AAHexwQgpvy8UWBDNJkDRQsTcCkj6St-Mxc",
#         "chat_id": "6847391264"
#     },
#     {
#         "name": "Backup Bot",
#         "token": "YOUR_BACKUP_BOT_TOKEN",
#         "chat_id": "YOUR_BACKUP_CHAT_ID"
#     },
#     {
#         "name": "Team Channel",
#         "token": "YOUR_TEAM_BOT_TOKEN",
#         "chat_id": "YOUR_TEAM_CHAT_ID"
#     }
# ]

# Default single telegram bot (used if TELEGRAM_BOTS list not configured)
TELEGRAM_BOTS = [
    {
        "name": "Primary Bot",
        "token": TELEGRAM_BOT_TOKEN,
        "chat_id": TELEGRAM_CHAT_ID
    }
]

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
    """Send a message to all configured Telegram bots/channels"""
    if not TELEGRAM_BOTS:
        print("⚠️  No Telegram bots configured - skipping notification")
        return

    sent_count = 0
    failed_count = 0

    for bot in TELEGRAM_BOTS:
        bot_token = bot.get("token")
        chat_id = bot.get("chat_id")
        bot_name = bot.get("name", "Unknown Bot")

        if not bot_token or not chat_id:
            print(f"⚠️  Telegram bot '{bot_name}' config missing - skipping")
            failed_count += 1
            continue

        url = f"https://api.telegram.org/bot{bot_token}/sendMessage"

        payload = {
            "chat_id": chat_id,
            "text": message
        }

        try:
            response = requests.post(url, json=payload, timeout=20)
            if response.status_code == 200:
                print(f"✓ Notification sent via '{bot_name}': {message[:40]}...")
                sent_count += 1
            else:
                print(f"⚠️  Telegram error on '{bot_name}': {response.status_code}")
                failed_count += 1
        except Exception as e:
            print(f"⚠️  Telegram error on '{bot_name}': {e}")
            failed_count += 1

    if sent_count > 0:
        print(f"📤 Sent to {sent_count} bot(s), Failed: {failed_count}\n")

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
    """Main function to execute token regeneration for all users"""
    global EMAIL, PASSWORD, BROKER_ID

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

    print("=" * 70)
    print(" Tradetron Broker Token Regenerator - Multi-User Support")
    print(f" Total users to process: {len(USERS)}")
    print("=" * 70)
    print()

    # Process each user
    results = []
    for idx, user in enumerate(USERS, 1):
        user_email = user.get("email")
        user_password = user.get("password")
        user_broker_id = user.get("broker_id", BROKER_ID)

        print(f"\n{'='*70}")
        print(f" [{idx}/{len(USERS)}] Processing user: {user_email}")
        print(f" Broker ID: {user_broker_id}")
        print(f"{'='*70}\n")

        result = process_user(user_email, user_password, user_broker_id)
        results.append({
            "email": user_email,
            "status": result.get("statusCode"),
            "message": result.get("body")
        })

    # Summary
    print(f"\n{'='*70}")
    print(" SUMMARY")
    print(f"{'='*70}")
    successful = sum(1 for r in results if r["status"] == 200)
    failed = len(results) - successful

    for result in results:
        status_icon = "✅" if result["status"] == 200 else "❌"
        print(f"{status_icon} {result['email']}: {result['message']}")

    print(f"\nTotal: {successful} successful, {failed} failed")
    print(f"{'='*70}\n")

    # Send summary notification
    summary_msg = f"🔄 Token Regeneration Summary:\n✅ Success: {successful}\n❌ Failed: {failed}"
    send_telegram_message(summary_msg)

    # Return overall status
    return {
        "statusCode": 200 if failed == 0 else 207,  # 207 = Multi-status
        "body": f"Success: {successful}, Failed: {failed}",
        "details": results
    }

def process_user(email, password, broker_id):
    """Process token regeneration for a single user"""
    global EMAIL, PASSWORD, BROKER_ID

    # Set global variables for this user
    EMAIL = email
    PASSWORD = password
    BROKER_ID = broker_id

    # Update URLs with the broker ID
    global REGENERATE_URL
    REGENERATE_URL = f"{BASE_URL}/user/broker-and-exchanges/regenerate-token/{BROKER_ID}"

    session = requests.Session()

    # Send start notification for this user
    send_telegram_message(f"🤖 Token Regeneration Started for {email}")

    try:
        if not login(session):
            print(f"\nAborting {email} due to login failure.")
            notify_error(f"Login failed for {email}")
            return {
                "statusCode": 401,
                "body": "Login failed"
            }

        # Small delay to be safe
        time.sleep(1)

        if regenerate_token(session):
            print(f"\n✓ Done! Token regeneration completed successfully for {email}.")
            send_telegram_message(f"✅ Token Regeneration SUCCESSFUL for {email}")
            return {
                "statusCode": 200,
                "body": "Success"
            }
        else:
            print(f"\n✗ Token regeneration may have failed for {email}. Check Tradetron UI.")
            return {
                "statusCode": 500,
                "body": "Token regeneration failed"
            }

    except requests.exceptions.ConnectionError as e:
        print(f"\n✗ Connection error for {email}: {e}")
        notify_error(f"Connection error for {email}: {str(e)}")
        return {
            "statusCode": 500,
            "body": f"Connection error: {str(e)}"
        }

    except requests.exceptions.Timeout as e:
        print(f"\n✗ Request timed out for {email}: {e}")
        notify_error(f"Request timeout for {email}: {str(e)}")
        return {
            "statusCode": 500,
            "body": f"Request timeout: {str(e)}"
        }

    except RuntimeError as e:
        print(f"\n✗ Error for {email}: {e}")
        notify_error(f"Error for {email}: {str(e)}")
        return {
            "statusCode": 500,
            "body": str(e)
        }

    except Exception as e:
        print(f"\n✗ Unexpected error for {email}: {type(e).__name__}: {e}")
        notify_error(f"Error for {email}: {type(e).__name__}: {str(e)}")
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
