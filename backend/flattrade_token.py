#!/usr/bin/env python3
"""
FlatTrade Token Generation Script with Telegram Notifications
==============================================================
Automates the process of generating FlatTrade API tokens via Tradetron integration.
Uses Selenium to automate the browser login process with TOTP authentication.

This script is designed for FlatTrade broker token regeneration through Tradetron.

Usage: python3 flattrade_token.py

Configuration:
- FLATTRADE_USER_ID (Broker User ID)
- FLATTRADE_PASSWORD (Broker Password)  
- FLATTRADE_TOTP_SECRET (TOTP Secret Key for 2FA)
- TELEGRAM_BOT_TOKEN
- TELEGRAM_CHAT_ID
"""

import os
import sys
import time
import requests

# Optional imports for TOTP
try:
    import pyotp
    HAS_PYOTP = True
except ImportError:
    HAS_PYOTP = False
    print("⚠️  pyotp not installed. Run: pip install pyotp")

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
        "password": os.environ.get("FLATTRADE_PASSWORD", "@Bhupendra25"),
        "totp_secret": os.environ.get("FLATTRADE_TOTP_SECRET", "5SF7Z2QZW6NUUTFHGX7QWGUUFR373NG5")
    }
]

# Tradetron FlatTrade Auth URL (from the screenshot)
# This URL redirects to FlatTrade login page
TRADETRON_FLATTRADE_AUTH_URL = os.environ.get(
    "TRADETRON_FLATTRADE_AUTH_URL", 
    "https://flattrade.tradetron.tech/auth/2901162"
)

# FlatTrade Direct Login URL (from the screenshot)
FLATTRADE_LOGIN_URL = "https://auth.flattrade.in/"

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


# ============================================================
# SELENIUM AUTOMATION FOR FLATTRADE LOGIN
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
        sys.exit(1)

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
    
    # Add user agent
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
        sys.exit(1)


def login_flattrade_via_tradetron(user_id, password, totp_secret):
    """
    Login to FlatTrade via Tradetron auth URL and complete authentication.
    
    Flow:
    1. Open Tradetron FlatTrade auth URL (https://flattrade.tradetron.tech/auth/2901162)
    2. This redirects to FlatTrade login page
    3. Enter User ID, Password, and TOTP
    4. Click Login
    5. Wait for successful authentication and redirect back to Tradetron
    """
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    from selenium.common.exceptions import TimeoutException, NoSuchElementException

    print(f"\n{'='*60}")
    print(f" FlatTrade Token Generation")
    print(f" User ID: {user_id}")
    print(f"{'='*60}\n")

    driver = None
    
    try:
        # Setup driver
        print("[1/5] Setting up browser...")
        driver = setup_selenium_driver()
        wait = WebDriverWait(driver, 30)

        # Step 1: Open Tradetron FlatTrade auth URL
        print(f"[2/5] Opening Tradetron FlatTrade auth URL...")
        print(f"      URL: {TRADETRON_FLATTRADE_AUTH_URL}")
        driver.get(TRADETRON_FLATTRADE_AUTH_URL)
        time.sleep(3)
        
        # Check if redirected to FlatTrade login page
        current_url = driver.current_url
        print(f"      Current URL: {current_url}")
        
        # Step 2: Wait for login page and enter credentials
        print("[3/5] Waiting for FlatTrade login page...")
        
        # Wait for User ID field
        try:
            user_id_field = wait.until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "input[placeholder='User ID'], input[name='userId'], input[id='userId'], input[type='text']"))
            )
            print("      ✓ Login page loaded")
        except TimeoutException:
            # Try alternative selectors
            try:
                user_id_field = driver.find_element(By.XPATH, "//input[contains(@placeholder, 'User') or contains(@placeholder, 'user')]")
            except NoSuchElementException:
                print("      ❌ Could not find User ID field")
                print(f"      Page source preview: {driver.page_source[:500]}")
                return False

        # Clear and enter User ID
        user_id_field.clear()
        user_id_field.send_keys(user_id)
        print(f"      ✓ Entered User ID: {user_id}")
        time.sleep(0.5)

        # Enter Password
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

        # Generate and enter TOTP
        print("[4/5] Generating and entering TOTP...")
        try:
            totp_code = generate_totp(totp_secret)
            print(f"      ✓ Generated TOTP: {totp_code}")
            
            # Find TOTP/OTP field
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
            # Try alternative TOTP field locators
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
                # Continue anyway - maybe TOTP is not required
        
        time.sleep(0.5)

        # Click Login button
        print("[5/5] Clicking Login button...")
        login_clicked = False
        
        # Try multiple approaches to find and click the login button
        try:
            # First try: Look for submit button or common login button classes
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
        
        # Second try: Find button by text content
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
        
        # Third try: Find by XPath
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
            # Last resort: Try clicking any visible button
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

        # Wait for redirect/success
        print("\n⏳ Waiting for authentication to complete...")
        time.sleep(5)
        
        current_url = driver.current_url
        print(f"      Current URL after login: {current_url}")
        
        # Check for success indicators
        if "tradetron" in current_url.lower() or "success" in current_url.lower():
            print("\n✅ FlatTrade authentication SUCCESSFUL!")
            send_telegram_message(f"✅ FlatTrade Token Generated Successfully for {user_id}!")
            return True
        elif "error" in current_url.lower() or "failed" in current_url.lower():
            print("\n❌ FlatTrade authentication FAILED!")
            send_telegram_message(f"❌ FlatTrade Token Generation FAILED for {user_id}")
            return False
        else:
            # Check page content for success/error messages
            page_source = driver.page_source.lower()
            if "success" in page_source or "token" in page_source or "authorized" in page_source:
                print("\n✅ FlatTrade authentication appears SUCCESSFUL!")
                send_telegram_message(f"✅ FlatTrade Token Generated Successfully for {user_id}!")
                return True
            elif "invalid" in page_source or "error" in page_source or "failed" in page_source:
                print("\n❌ FlatTrade authentication appears to have FAILED!")
                send_telegram_message(f"❌ FlatTrade Token Generation FAILED for {user_id}")
                return False
            else:
                print("\n⚠️  Authentication status unclear - please verify manually")
                send_telegram_message(f"⚠️ FlatTrade Token Generation status unclear for {user_id} - verify manually")
                return True  # Assume success

    except Exception as e:
        print(f"\n❌ Error during FlatTrade login: {type(e).__name__}: {e}")
        send_telegram_message(f"❌ FlatTrade Error for {user_id}: {str(e)}")
        return False
    
    finally:
        if driver:
            try:
                driver.quit()
                print("\n✓ Browser closed")
            except:
                pass


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

    result = login_flattrade_via_tradetron(user_id, password, totp_secret)
    
    if result:
        return {"user_id": user_id, "status": 200, "message": "Success"}
    else:
        return {"user_id": user_id, "status": 500, "message": "Token generation failed"}


def main():
    """Main function to process all FlatTrade users"""
    print("=" * 70)
    print(" FlatTrade Token Generator - Tradetron Integration")
    print(f" Total users to process: {len(FLATTRADE_USERS)}")
    print("=" * 70)

    # Check dependencies
    if not HAS_PYOTP:
        print("\n❌ Missing dependency: pyotp")
        print("   Install with: pip install pyotp")
        return {"statusCode": 500, "body": "Missing pyotp dependency"}

    # Send start notification
    send_telegram_message("🤖 FlatTrade Token Generation Started")

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
        print(f"{status_icon} {result['user_id']}: {result['message']}")

    print(f"\nTotal: {successful} successful, {failed} failed")
    print(f"{'='*70}\n")

    # Send summary notification
    summary_msg = f"🔄 FlatTrade Token Generation Summary:\n✅ Success: {successful}\n❌ Failed: {failed}"
    send_telegram_message(summary_msg)

    return {
        "statusCode": 200 if failed == 0 else 207,
        "body": f"Success: {successful}, Failed: {failed}",
        "details": results
    }


def lambda_handler(event, context):
    """AWS Lambda handler"""
    return main()


if __name__ == "__main__":
    # Install dependencies reminder
    print("\n📦 Required Dependencies:")
    print("   pip install selenium webdriver-manager pyotp requests")
    print()
    
    result = main()
    
    if isinstance(result, dict):
        status_code = result.get("statusCode", 500)
        sys.exit(0 if status_code == 200 else 1)
    sys.exit(0)
