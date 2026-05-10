#!/usr/bin/env python3

import os
import re
import time
import urllib.parse
import requests
import hashlib
import json
import base64

EMAIL = os.environ.get("TRADETRON_EMAIL", "bhupandraverma@gmail.com")
PASSWORD = os.environ.get("TRADETRON_PASSWORD", "Verma@1234")
BROKER_ID = os.environ.get("TRADETRON_BROKER_ID", "917")

# ============================================================
# TELEGRAM CONFIGURATION
# ============================================================

TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "8499389750:AAHexwQgpvy8UWBDNJkDRQsTcCkj6St-Mxc")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "6847391264")

def send_telegram_message(message):
    """Send a message to Telegram chat"""
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print("Telegram config missing")
        return

    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"

    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": message
    }

    try:
        response = requests.post(url, json=payload, timeout=20)
        print("Telegram Status:", response.status_code)
    except Exception as e:
        print(f"Telegram Error: {e}")

BASE_URL = "https://tradetron.tech"
ALTCHA_CHALLENGE_URL = f"{BASE_URL}/altcha-challenge"
LOGIN_PAGE_URL = f"{BASE_URL}/login"
LOGIN_POST_URL = f"{BASE_URL}/login"
BROKER_PAGE_URL = f"{BASE_URL}/user/broker-and-exchanges"
REGENERATE_URL = f"{BASE_URL}/user/broker-and-exchanges/regenerate-token/{BROKER_ID}"

HEADERS = {
    "User-Agent": "Mozilla/5.0",
    "Accept": "text/html,application/xhtml+xml",
}

def solve_altcha_challenge(session):
    """Solve Altcha proof-of-work challenge"""
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

    solution = None

    for n in range(maxnumber + 1):
        hash_hex = hashlib.sha256(f"{salt}{n}".encode()).hexdigest()

        if hash_hex == challenge:
            solution = n
            break

    if solution is None:
        raise RuntimeError("Failed to solve Altcha challenge")

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
    token = session.cookies.get("XSRF-TOKEN")

    if not token:
        raise RuntimeError("XSRF token not found")

    return urllib.parse.unquote(token)

def extract_csrf_from_html(html):
    """Extract CSRF token from HTML"""
    patterns = [
        r'name="_token"\s+value="([^"]+)"',
        r'<meta\s+name="csrf-token"\s+content="([^"]+)"',
    ]

    for pattern in patterns:
        match = re.search(pattern, html, re.IGNORECASE)

        if match:
            return match.group(1)

    raise RuntimeError("CSRF token not found")

def login(session):
    """Login to Tradetron and establish authenticated session"""
    resp = session.get(LOGIN_PAGE_URL, headers=HEADERS)
    resp.raise_for_status()

    csrf_token = extract_csrf_from_html(resp.text)

    xsrf_token = get_xsrf_token_decoded(session)

    altcha_payload = solve_altcha_challenge(session)

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

    if resp.url.rstrip("/").endswith("/login"):
        return False

    return True

def regenerate_token(session):
    """Regenerate broker token"""
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

    if resp.status_code == 200:
        return True

    return False

def main():
    """Main function to execute token regeneration"""
    session = requests.Session()
    
    # Send start notification
    send_telegram_message("🤖 AWS Lambda - Tradetron Token Regeneration Started")

    try:
        if not login(session):
            error_msg = "❌ AWS Lambda - Login Failed"
            send_telegram_message(error_msg)
            raise Exception("Login Failed")

        time.sleep(1)

        if regenerate_token(session):
            success_msg = "✅ AWS Lambda - Token Regeneration SUCCESSFUL!"
            send_telegram_message(success_msg)
            return {
                "statusCode": 200,
                "body": "Success"
            }
        else:
            error_msg = "❌ AWS Lambda - Token Regeneration Failed"
            send_telegram_message(error_msg)
            raise Exception("Token Regeneration Failed")

    except requests.exceptions.ConnectionError as e:
        error_msg = f"❌ AWS Lambda - Connection Error: {str(e)}"
        send_telegram_message(error_msg)
        raise Exception(f"Connection Error: {e}")
    
    except requests.exceptions.Timeout as e:
        error_msg = f"❌ AWS Lambda - Request Timeout: {str(e)}"
        send_telegram_message(error_msg)
        raise Exception(f"Timeout Error: {e}")
    
    except Exception as e:
        error_msg = f"❌ AWS Lambda - Error: {str(e)}"
        send_telegram_message(error_msg)
        raise

def lambda_handler(event, context):
    """AWS Lambda handler"""
    try:
        return main()

    except Exception as e:
        return {
            "statusCode": 500,
            "body": str(e)
        }
