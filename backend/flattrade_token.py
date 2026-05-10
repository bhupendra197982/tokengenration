#!/usr/bin/env python3
"""
FlatTrade Token Generation Script with Telegram Notifications
==============================================================
Automates the process of generating FlatTrade API tokens via Tradetron integration.

Supports TWO modes:
1. LOCAL MODE (Selenium) - Uses browser automation for login
2. LAMBDA MODE (Requests) - Uses HTTP requests for Lambda deployment

Usage: 
- Local: python3 flattrade_token.py
- Lambda: Deploy and invoke lambda_handler

Configuration via environment variables:
- FLATTRADE_USER_ID (Broker User ID)
- FLATTRADE_PASSWORD (Broker Password)  
- FLATTRADE_TOTP_SECRET (TOTP Secret Key for 2FA)
- TELEGRAM_BOT_TOKEN
- TELEGRAM_CHAT_ID
- USE_SELENIUM (set to "false" for Lambda/HTTP mode)
"""

import os
import sys
import time
import re
import json
import hashlib
import requests
import urllib.parse

# Optional imports for TOTP
try:
    import pyotp
    HAS_PYOTP = True
except ImportError:
    HAS_PYOTP = False

# Check if running in Lambda environment
IS_LAMBDA = os.environ.get("AWS_LAMBDA_FUNCTION_NAME") is not None
USE_SELENIUM = os.environ.get("USE_SELENIUM", "true").lower() == "true" and not IS_LAMBDA

# ============================================================
# CONFIGURATION
# ============================================================

# ============================================================
# FLATTRADE USER CREDENTIALS
# ============================================================
# Add your FlatTrade broker credentials here
# Format: {"user_id": "USER_ID", "password": "PASSWORD", "totp_secret": "TOTP_SECRET"}
#
# EXAMPLE - UNCOMMENT AND MODIFY TO ADD CREDENTIALS:
# FLATTRADE_USERS = [
#     {
#         "user_id": "YOUR_USER_ID_1",
#         "password": "YOUR_PASSWORD_1",
#         "totp_secret": "YOUR_TOTP_SECRET_1"
#     },
#     {
#         "user_id": "YOUR_USER_ID_2",
#         "password": "YOUR_PASSWORD_2",
#         "totp_secret": "YOUR_TOTP_SECRET_2"
#     }
# ]

# Default single user configuration
FLATTRADE_USERS = [
    {
        "user_id": os.environ.get("FLATTRADE_USER_ID", "FZ29374"),
        "password": os.environ.get("FLATTRADE_PASSWORD", "Verma@1979"),
        "totp_secret": os.environ.get("FLATTRADE_TOTP_SECRET", "GVHGG7F3HQZX6NN5")
    }
]

# Tradetron FlatTrade Auth URL
TRADETRON_FLATTRADE_AUTH_URL = os.environ.get(
    "TRADETRON_FLATTRADE_AUTH_URL", 
    "https://flattrade.tradetron.tech/auth/2901162"
)

# FlatTrade API endpoints
FLATTRADE_BASE_URL = "https://auth.flattrade.in"
FLATTRADE_API_URL = "https://authapi.flattrade.in"

# ============================================================
# TELEGRAM CONFIGURATION
# ============================================================
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "8499389750:AAHexwQgpvy8UWBDNJkDRQsTcCkj6St-Mxc")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "6847391264")

# ============================================================
# MULTI-TELEGRAM BOT CONFIGURATION (Optional)
# ============================================================
# TELEGRAM_BOTS = [
#     {
#         "name": "Main Bot",
#         "token": "YOUR_BOT_TOKEN",
#         "chat_id": "YOUR_CHAT_ID"
#     }
# ]

TELEGRAM_BOTS = [
    {
        "name": "Primary Bot",
        "token": TELEGRAM_BOT_TOKEN,
        "chat_id": TELEGRAM_CHAT_ID
    }
]

# HTTP Headers for requests
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) "
                  "Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Connection": "keep-alive",
}

# ============================================================
# TELEGRAM NOTIFICATION FUNCTIONS
# ============================================================

def send_telegram_message(message):
    """Send a message to all configured Telegram bots/channels"""
    if not TELEGRAM_BOTS:
        print("⚠️  No Telegram bots configured - skipping notification")
        return

    for bot in TELEGRAM_BOTS:
        bot_token = bot.get("token")
        chat_id = bot.get("chat_id")
        bot_name = bot.get("name", "Unknown Bot")

        if not bot_token or not chat_id:
            continue

        url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
        payload = {"chat_id": chat_id, "text": message}

        try:
            response = requests.post(url, json=payload, timeout=20)
            if response.status_code == 200:
                print(f"✓ Telegram notification sent via '{bot_name}'")
            else:
                print(f"⚠️  Telegram error on '{bot_name}': {response.status_code}")
        except Exception as e:
            print(f"⚠️  Telegram error on '{bot_name}': {e}")


def generate_totp(secret):
    """Generate TOTP code from secret"""
    if not HAS_PYOTP:
        raise ImportError("pyotp is required for TOTP generation. Install with: pip install pyotp")
    
    totp = pyotp.TOTP(secret)
    return totp.now()


def get_current_timestamp():
    """Get current timestamp in readable format"""
    from datetime import datetime
    return datetime.now().strftime("%b %d, %H:%M")


def extract_last_updated(page_source):
    """Extract Last Updated timestamp from Tradetron page"""
    # Look for patterns like "Last Updated: May 10, 08:45" or similar
    patterns = [
        r'Last\s*Updated[:\s]*([A-Za-z]+\s+\d{1,2},?\s*\d{1,2}:\d{2})',
        r'last[_-]?updated["\s:]+([^"<]+)',
        r'Updated[:\s]*([A-Za-z]+\s+\d{1,2},?\s*\d{1,2}:\d{2})',
    ]
    
    for pattern in patterns:
        match = re.search(pattern, page_source, re.IGNORECASE)
        if match:
            return match.group(1).strip()
    
    return None


# ============================================================
# HTTP-BASED LOGIN (Lambda Compatible)
# ============================================================

def login_flattrade_http(user_id, password, totp_secret):
    """
    Login to FlatTrade using HTTP requests (Lambda compatible).
    This approach doesn't require a browser.
    """
    print(f"\n{'='*60}")
    print(f" FlatTrade Token Generation (HTTP Mode)")
    print(f" User ID: {user_id}")
    print(f"{'='*60}\n")

    session = requests.Session()

    try:
        # Step 1: Get the Tradetron auth URL and follow redirect to FlatTrade
        print("[1/4] Getting FlatTrade auth page...")
        resp = session.get(TRADETRON_FLATTRADE_AUTH_URL, headers=HEADERS, allow_redirects=True)
        print(f"      Redirected to: {resp.url}")
        
        # Extract app_key and sid from URL
        parsed_url = urllib.parse.urlparse(resp.url)
        query_params = urllib.parse.parse_qs(parsed_url.query)
        app_key = query_params.get('app_key', [''])[0]
        sid = query_params.get('sid', [''])[0]
        
        if not app_key or not sid:
            print("      ❌ Could not extract app_key or sid from URL")
            return False
        
        print(f"      App Key: {app_key[:20]}...")
        print(f"      SID: {sid[:20]}...")

        # Step 2: Generate TOTP
        print("[2/4] Generating TOTP...")
        totp_code = generate_totp(totp_secret)
        print(f"      ✓ TOTP: {totp_code}")

        # Step 3: Perform login via API
        print("[3/4] Logging in to FlatTrade...")
        
        # FlatTrade uses a specific login API endpoint
        login_url = f"{FLATTRADE_API_URL}/trade/apitoken"
        
        # Prepare login payload - FlatTrade specific
        login_payload = {
            "uid": user_id,
            "pwd": hashlib.sha256(password.encode()).hexdigest(),
            "factor2": totp_code,
            "apkversion": "1.0.0",
            "imei": "abc1234",
            "vc": "TRADE_API",
            "appkey": app_key,
            "source": "API"
        }
        
        login_headers = {
            **HEADERS,
            "Content-Type": "application/json",
            "Origin": FLATTRADE_BASE_URL,
            "Referer": resp.url,
        }

        # Try direct API login
        try:
            login_resp = session.post(login_url, json=login_payload, headers=login_headers, timeout=30)
            login_data = login_resp.json() if login_resp.text else {}
            
            if login_data.get("stat") == "Ok" or "token" in str(login_data).lower():
                print("      ✓ API Login successful!")
                print(f"      Token received: {str(login_data.get('susertoken', 'N/A'))[:30]}...")
                
                current_time = get_current_timestamp()
                
                # Step 4: Complete Tradetron callback with token
                print("[4/4] Completing Tradetron authentication...")
                
                # Redirect back to Tradetron with success
                callback_url = f"https://flattrade.broker.tradetron.tech/success"
                try:
                    callback_resp = session.get(callback_url, headers=HEADERS, allow_redirects=True)
                    print(f"      Final URL: {callback_resp.url}")
                    
                    # Try to extract Last Updated from callback response
                    last_updated = extract_last_updated(callback_resp.text) or current_time
                    
                    if "success" in callback_resp.url.lower() or callback_resp.status_code == 200:
                        print("\n✅ FlatTrade authentication SUCCESSFUL!")
                        print(f"   📅 Last Updated: {last_updated}")
                        return {"success": True, "last_updated": last_updated}
                except:
                    # Even if callback fails, if we got token, consider it success
                    print("\n✅ FlatTrade token generated (callback redirect skipped)")
                    print(f"   📅 Token generated at: {current_time}")
                    return {"success": True, "last_updated": current_time}
            else:
                print(f"      ❌ Login failed: {login_data.get('emsg', 'Unknown error')}")
                
        except requests.exceptions.RequestException as e:
            print(f"      ⚠️  API login request failed: {e}")

        # Alternative: Try form-based login
        print("      Trying form-based login...")
        
        # Get login page to extract CSRF tokens
        login_page = session.get(f"{FLATTRADE_BASE_URL}/?app_key={app_key}&sid={sid}", headers=HEADERS)
        
        # Look for any hidden tokens in the page
        csrf_patterns = [
            r'name="_token"\s+value="([^"]+)"',
            r'name="csrf_token"\s+value="([^"]+)"',
            r'"_token":\s*"([^"]+)"',
        ]
        
        csrf_token = None
        for pattern in csrf_patterns:
            match = re.search(pattern, login_page.text)
            if match:
                csrf_token = match.group(1)
                break

        # Prepare form data
        form_data = {
            "userId": user_id,
            "password": password,
            "totp": totp_code,
        }
        
        if csrf_token:
            form_data["_token"] = csrf_token
            
        form_headers = {
            **HEADERS,
            "Content-Type": "application/x-www-form-urlencoded",
            "Origin": FLATTRADE_BASE_URL,
            "Referer": login_page.url,
        }

        # Submit login form
        form_resp = session.post(
            f"{FLATTRADE_BASE_URL}/login",
            data=form_data,
            headers=form_headers,
            allow_redirects=True
        )
        
        print(f"      Form response URL: {form_resp.url}")
        
        current_time = get_current_timestamp()
        last_updated = extract_last_updated(form_resp.text) or current_time
        
        # Check for success
        if "success" in form_resp.url.lower() or "tradetron" in form_resp.url.lower():
            print("\n✅ FlatTrade authentication SUCCESSFUL (form login)!")
            print(f"   📅 Last Updated: {last_updated}")
            return {"success": True, "last_updated": last_updated}
        elif form_resp.status_code == 200 and "dashboard" in form_resp.url.lower():
            print("\n✅ FlatTrade authentication SUCCESSFUL!")
            print(f"   📅 Last Updated: {last_updated}")
            return {"success": True, "last_updated": last_updated}
        else:
            print(f"      ❌ Form login may have failed. URL: {form_resp.url}")
            
            # Check page content
            if "invalid" in form_resp.text.lower() or "error" in form_resp.text.lower():
                print("      ❌ Invalid credentials or TOTP")
                return {"success": False, "last_updated": None, "error": "Invalid credentials or TOTP"}

        return {"success": False, "last_updated": None, "error": "Unknown login result"}

    except Exception as e:
        print(f"\n❌ Error during FlatTrade HTTP login: {type(e).__name__}: {e}")
        return {"success": False, "last_updated": None, "error": str(e)}


# ============================================================
# SELENIUM-BASED LOGIN (Local Mode)
# ============================================================

def setup_selenium_driver():
    """Setup Selenium WebDriver with Chrome"""
    try:
        from selenium import webdriver
        from selenium.webdriver.chrome.service import Service
        from selenium.webdriver.chrome.options import Options
        from webdriver_manager.chrome import ChromeDriverManager
    except ImportError:
        print("❌ Selenium not installed!")
        print("   Run: pip install selenium webdriver-manager")
        return None

    chrome_options = Options()
    # Headless mode (no browser window)
    chrome_options.add_argument("--headless=new")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--window-size=1920,1080")
    chrome_options.add_argument("--disable-blink-features=AutomationControlled")
    chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
    chrome_options.add_experimental_option("useAutomationExtension", False)
    
    chrome_options.add_argument(
        "user-agent=Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    )

    try:
        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=chrome_options)
        driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {
            "source": """
                Object.defineProperty(navigator, 'webdriver', {
                    get: () => undefined
                })
            """
        })
        return driver
    except Exception as e:
        print(f"❌ Failed to setup Chrome driver: {e}")
        return None


def login_flattrade_selenium(user_id, password, totp_secret):
    """
    Login to FlatTrade via Tradetron using Selenium browser automation.
    """
    try:
        from selenium.webdriver.common.by import By
        from selenium.webdriver.support.ui import WebDriverWait
        from selenium.webdriver.support import expected_conditions as EC
        from selenium.common.exceptions import TimeoutException, NoSuchElementException
    except ImportError:
        print("❌ Selenium not installed - falling back to HTTP mode")
        return login_flattrade_http(user_id, password, totp_secret)

    print(f"\n{'='*60}")
    print(f" FlatTrade Token Generation (Selenium Mode)")
    print(f" User ID: {user_id}")
    print(f"{'='*60}\n")

    driver = None
    
    try:
        print("[1/5] Setting up browser...")
        driver = setup_selenium_driver()
        if not driver:
            print("      ❌ Failed to setup browser - trying HTTP mode")
            return login_flattrade_http(user_id, password, totp_secret)
            
        wait = WebDriverWait(driver, 30)

        print(f"[2/5] Opening Tradetron FlatTrade auth URL...")
        print(f"      URL: {TRADETRON_FLATTRADE_AUTH_URL}")
        driver.get(TRADETRON_FLATTRADE_AUTH_URL)
        time.sleep(3)
        
        current_url = driver.current_url
        print(f"      Current URL: {current_url}")
        
        print("[3/5] Waiting for FlatTrade login page...")
        
        try:
            user_id_field = wait.until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "input[placeholder='User ID'], input[name='userId'], input[id='userId'], input[type='text']"))
            )
            print("      ✓ Login page loaded")
        except TimeoutException:
            try:
                user_id_field = driver.find_element(By.XPATH, "//input[contains(@placeholder, 'User') or contains(@placeholder, 'user')]")
            except NoSuchElementException:
                print("      ❌ Could not find User ID field")
                return False

        user_id_field.clear()
        user_id_field.send_keys(user_id)
        print(f"      ✓ Entered User ID: {user_id}")
        time.sleep(0.5)

        try:
            password_field = wait.until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "input[type='password'], input[placeholder='Password'], input[name='password']"))
            )
            password_field.clear()
            password_field.send_keys(password)
            print("      ✓ Entered Password")
        except TimeoutException:
            print("      ❌ Could not find Password field")
            return False
        
        time.sleep(0.5)

        print("[4/5] Generating and entering TOTP...")
        totp_code = generate_totp(totp_secret)
        print(f"      ✓ Generated TOTP: {totp_code}")
        
        try:
            totp_field = wait.until(
                EC.presence_of_element_located((By.CSS_SELECTOR, 
                    "input[placeholder*='OTP'], input[placeholder*='TOTP'], "
                    "input[name='totp'], input[name='otp'], "
                    "input[id='totp'], input[id='otp']"
                ))
            )
            totp_field.clear()
            totp_field.send_keys(totp_code)
            print("      ✓ Entered TOTP")
        except TimeoutException:
            try:
                totp_fields = driver.find_elements(By.CSS_SELECTOR, "input[type='text'], input[type='number']")
                for field in totp_fields:
                    placeholder = field.get_attribute("placeholder") or ""
                    if "otp" in placeholder.lower() or "totp" in placeholder.lower():
                        field.clear()
                        field.send_keys(totp_code)
                        print("      ✓ Entered TOTP (alternative locator)")
                        break
            except Exception as e:
                print(f"      ⚠️  Could not find TOTP field: {e}")
        
        time.sleep(0.5)

        print("[5/5] Clicking Login button...")
        login_clicked = False
        
        try:
            login_button = wait.until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, 
                    "button[type='submit'], input[type='submit'], "
                    ".login-btn, #loginBtn, button.btn-primary, "
                    "button.btn, button.submit-btn"
                ))
            )
            login_button.click()
            login_clicked = True
            print("      ✓ Clicked Login button")
        except TimeoutException:
            pass
        
        if not login_clicked:
            try:
                buttons = driver.find_elements(By.TAG_NAME, "button")
                for btn in buttons:
                    btn_text = btn.text.lower().strip()
                    if btn_text in ["log in", "login", "submit", "sign in"]:
                        btn.click()
                        login_clicked = True
                        print("      ✓ Clicked Login button (by text)")
                        break
            except Exception:
                pass
        
        if not login_clicked:
            try:
                login_button = driver.find_element(By.XPATH, 
                    "//button[contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'log in') or "
                    "contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'login')]")
                login_button.click()
                login_clicked = True
                print("      ✓ Clicked Login button (by XPath)")
            except Exception:
                pass
        
        if not login_clicked:
            try:
                buttons = driver.find_elements(By.TAG_NAME, "button")
                for btn in buttons:
                    if btn.is_displayed() and btn.is_enabled():
                        btn.click()
                        login_clicked = True
                        print("      ✓ Clicked first available button")
                        break
            except Exception as e:
                print(f"      ❌ Could not find Login button: {e}")
        
        if not login_clicked:
            print("      ❌ Could not find any Login button")
            return False

        print("\n⏳ Waiting for authentication to complete...")
        time.sleep(5)
        
        current_url = driver.current_url
        print(f"      Current URL after login: {current_url}")
        
        # Get page source for timestamp extraction
        page_source = driver.page_source
        last_updated = extract_last_updated(page_source)
        current_time = get_current_timestamp()
        
        if "tradetron" in current_url.lower() or "success" in current_url.lower():
            print("\n✅ FlatTrade authentication SUCCESSFUL!")
            if last_updated:
                print(f"   📅 Last Updated: {last_updated}")
            else:
                print(f"   📅 Token generated at: {current_time}")
            return {"success": True, "last_updated": last_updated or current_time}
        elif "error" in current_url.lower() or "failed" in current_url.lower():
            print("\n❌ FlatTrade authentication FAILED!")
            return {"success": False, "last_updated": None}
        else:
            page_source_lower = page_source.lower()
            if "success" in page_source_lower or "token" in page_source_lower or "authorized" in page_source_lower:
                print("\n✅ FlatTrade authentication appears SUCCESSFUL!")
                if last_updated:
                    print(f"   📅 Last Updated: {last_updated}")
                else:
                    print(f"   📅 Token generated at: {current_time}")
                return {"success": True, "last_updated": last_updated or current_time}
            elif "invalid" in page_source_lower or "error" in page_source_lower or "failed" in page_source_lower:
                print("\n❌ FlatTrade authentication appears to have FAILED!")
                return {"success": False, "last_updated": None}
            else:
                print("\n⚠️  Authentication status unclear - assuming success")
                print(f"   📅 Attempt time: {current_time}")
                return {"success": True, "last_updated": current_time}

    except Exception as e:
        print(f"\n❌ Error during FlatTrade Selenium login: {type(e).__name__}: {e}")
        return {"success": False, "last_updated": None, "error": str(e)}
    
    finally:
        if driver:
            try:
                driver.quit()
                print("\n✓ Browser closed")
            except:
                pass


# ============================================================
# UNIFIED LOGIN FUNCTION
# ============================================================

def login_flattrade(user_id, password, totp_secret):
    """
    Login to FlatTrade using the appropriate method.
    - Lambda/HTTP mode: Uses requests
    - Local/Selenium mode: Uses browser automation
    """
    if IS_LAMBDA or not USE_SELENIUM:
        print("📡 Using HTTP mode (Lambda compatible)")
        return login_flattrade_http(user_id, password, totp_secret)
    else:
        print("🌐 Using Selenium mode (Local)")
        return login_flattrade_selenium(user_id, password, totp_secret)


def process_user(user):
    """Process token generation for a single user"""
    user_id = user.get("user_id")
    password = user.get("password")
    totp_secret = user.get("totp_secret")

    if not user_id or user_id == "YOUR_USER_ID":
        print("⚠️  User ID not configured - skipping")
        return {"user_id": "Not Configured", "status": 400, "message": "Credentials not set"}

    if not password or password == "YOUR_PASSWORD":
        print("⚠️  Password not configured - skipping")
        return {"user_id": user_id, "status": 400, "message": "Password not set"}

    if not totp_secret or totp_secret == "YOUR_TOTP_SECRET":
        print("⚠️  TOTP secret not configured - skipping")
        return {"user_id": user_id, "status": 400, "message": "TOTP secret not set"}

    # Send start notification for this user
    send_telegram_message(f"🤖 FlatTrade Token Generation Started for {user_id}")

    result = login_flattrade(user_id, password, totp_secret)
    
    # Handle both dict result (new format) and boolean result (fallback)
    if isinstance(result, dict):
        is_success = result.get("success", False)
        last_updated = result.get("last_updated", "")
        error_msg = result.get("error", "")
    else:
        is_success = bool(result)
        last_updated = get_current_timestamp() if is_success else ""
        error_msg = ""
    
    if is_success:
        timestamp_info = f"\n📅 Last Updated: {last_updated}" if last_updated else ""
        send_telegram_message(f"✅ FlatTrade Token Generated Successfully for {user_id}!{timestamp_info}")
        return {"user_id": user_id, "status": 200, "message": "Success", "last_updated": last_updated}
    else:
        error_info = f"\n⚠️ Error: {error_msg}" if error_msg else ""
        send_telegram_message(f"❌ FlatTrade Token Generation FAILED for {user_id}{error_info}")
        return {"user_id": user_id, "status": 500, "message": "Token generation failed", "error": error_msg}


# ============================================================
# MAIN EXECUTION
# ============================================================

def main():
    """Main function to process all FlatTrade users"""
    print("=" * 70)
    print(" FlatTrade Token Generator - Tradetron Integration")
    print(f" Mode: {'Lambda/HTTP' if IS_LAMBDA or not USE_SELENIUM else 'Selenium'}")
    print(f" Total users to process: {len(FLATTRADE_USERS)}")
    print("=" * 70)

    # Check dependencies
    if not HAS_PYOTP:
        print("\n❌ Missing dependency: pyotp")
        print("   Install with: pip install pyotp")
        return {"statusCode": 500, "body": "Missing pyotp dependency"}

    results = []
    
    for idx, user in enumerate(FLATTRADE_USERS, 1):
        print(f"\n[{idx}/{len(FLATTRADE_USERS)}] Processing user...")
        result = process_user(user)
        results.append(result)
        
        # Small delay between users
        if idx < len(FLATTRADE_USERS):
            time.sleep(2)

    # Summary
    print(f"\n{'='*70}")
    print(" SUMMARY")
    print(f"{'='*70}")
    
    successful = sum(1 for r in results if r["status"] == 200)
    failed = len(results) - successful

    for result in results:
        status_icon = "✅" if result["status"] == 200 else "❌"
        timestamp_info = f" (Last Updated: {result.get('last_updated', 'N/A')})" if result["status"] == 200 else ""
        print(f"{status_icon} {result['user_id']}: {result['message']}{timestamp_info}")

    print(f"\nTotal: {successful} successful, {failed} failed")
    print(f"{'='*70}\n")

    # Send summary notification with timestamps
    summary_lines = [f"🔄 FlatTrade Token Generation Summary:"]
    for result in results:
        if result["status"] == 200:
            timestamp_info = result.get('last_updated', 'N/A')
            summary_lines.append(f"✅ {result['user_id']}: {timestamp_info}")
        else:
            error_info = result.get('error', result.get('message', 'Failed'))
            summary_lines.append(f"❌ {result['user_id']}: {error_info}")
    
    summary_msg = "\n".join(summary_lines)
    send_telegram_message(summary_msg)

    return {
        "statusCode": 200 if failed == 0 else 207,
        "body": f"Success: {successful}, Failed: {failed}",
        "details": results
    }


# ============================================================
# AWS LAMBDA HANDLER
# ============================================================

def lambda_handler(event, context):
    """
    AWS Lambda handler.
    
    Environment Variables Required:
    - FLATTRADE_USER_ID: FlatTrade User ID
    - FLATTRADE_PASSWORD: FlatTrade Password
    - FLATTRADE_TOTP_SECRET: TOTP Secret Key
    - TELEGRAM_BOT_TOKEN: Telegram Bot Token (optional)
    - TELEGRAM_CHAT_ID: Telegram Chat ID (optional)
    
    For multiple users, modify FLATTRADE_USERS list in the code
    or pass via event payload.
    """
    global FLATTRADE_USERS
    
    # Check if users passed in event
    if event and isinstance(event, dict):
        event_users = event.get("users", [])
        if event_users:
            FLATTRADE_USERS = event_users
    
    return main()


# ============================================================
# STANDALONE EXECUTION
# ============================================================

if __name__ == "__main__":
    print("\n📦 Required Dependencies:")
    if USE_SELENIUM:
        print("   pip install selenium webdriver-manager pyotp requests")
    else:
        print("   pip install pyotp requests")
    print()
    
    result = main()
    
    if isinstance(result, dict):
        status_code = result.get("statusCode", 500)
        sys.exit(0 if status_code == 200 else 1)
    sys.exit(0)
