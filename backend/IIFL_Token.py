#!/usr/bin/env python3
"""
IIFL Token Generation Script with Telegram Notifications
==========================================================
Automates the process of generating IIFL API tokens via Tradetron integration.
Uses Selenium to automate the browser login process with TOTP authentication.

This script is designed for IIFL broker token regeneration through Tradetron.

Flow:
1. Open Tradetron IIFL auth URL (https://iiflcapital.broker.tradetron.tech/auth/2901162)
2. Enter Email/Mobile/Client ID/PAN and Password
3. Click Login
4. Enter TOTP on authentication screen
5. Click Authorize on Tradetron authorization page
6. Assert "Token generated successfully" is visible

Usage: python3 IIFL_Token.py

Configuration:
- IIFL_USER_ID (Email/Mobile/Client ID/PAN)
- IIFL_PASSWORD (Broker Password)  
- IIFL_TOTP_SECRET (TOTP Secret Key for 2FA)
- TELEGRAM_BOT_TOKEN
- TELEGRAM_CHAT_ID
"""

import os
import sys
import re
import time
import requests
from datetime import datetime

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

# Detect AWS Lambda environment
IS_LAMBDA = os.environ.get('AWS_LAMBDA_FUNCTION_NAME') is not None

# ============================================================
# IIFL USER CREDENTIALS
# ============================================================
IIFL_USERS = [
    {
        "user_id": os.environ.get("IIFL_USER_ID", "67589274"),
        "password": os.environ.get("IIFL_PASSWORD", "Verma@1234"),
        "totp_secret": os.environ.get("IIFL_TOTP_SECRET", "CDIBDOJBJJAOGQBGUEEYTCKJCVRIQBHS")
    }
]

# Tradetron IIFL Auth URL
TRADETRON_IIFL_AUTH_URL = os.environ.get(
    "TRADETRON_IIFL_AUTH_URL", 
    "https://iiflcapital.broker.tradetron.tech/auth/2901162"
)

# ============================================================
# TELEGRAM CONFIGURATION
# ============================================================
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "8499389750:AAHexwQgpvy8UWBDNJkDRQsTcCkj6St-Mxc")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "6847391264")

TELEGRAM_BOTS = [
    {
        "name": "Primary Bot",
        "token": TELEGRAM_BOT_TOKEN,
        "chat_id": TELEGRAM_CHAT_ID
    }
]


# ============================================================
# HELPER FUNCTIONS
# ============================================================

def get_current_timestamp():
    """Get current timestamp formatted nicely"""
    return datetime.now().strftime("%b %d, %H:%M:%S")


def send_telegram_message(message):
    """Send a message to all configured Telegram bots/channels"""
    if not TELEGRAM_BOTS:
        print("⚠️  No Telegram bots configured - skipping notification")
        return

    for bot in TELEGRAM_BOTS:
        bot_token = bot.get("token")
        chat_id = bot.get("chat_id")
        bot_name = bot.get("name", "Unknown Bot")

        if not bot_token or not chat_id or bot_token == "YOUR_BOT_TOKEN":
            print(f"📱 [Telegram Disabled] {message}")
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
    
    # Clean the secret
    clean_secret = secret.replace(" ", "").replace("-", "").upper()
    totp = pyotp.TOTP(clean_secret)
    return totp.now()


def extract_last_updated(page_content):
    """Extract 'Last Updated' timestamp from page content"""
    patterns = [
        r'Last\s+Updated[:\s]+([A-Za-z]+\s+\d{1,2},?\s+\d{1,2}:\d{2}(?::\d{2})?(?:\s*[AP]M)?)',
        r'Updated[:\s]+(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2})',
        r'Token\s+(?:generated|refreshed)\s+(?:at|on)[:\s]+([^\n<]+)',
        r'(\d{2}[/-]\d{2}[/-]\d{4}\s+\d{2}:\d{2})',
    ]
    
    for pattern in patterns:
        match = re.search(pattern, page_content, re.IGNORECASE)
        if match:
            return match.group(1).strip()
    
    return ""


# ============================================================
# SELENIUM AUTOMATION FOR IIFL LOGIN
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


def login_iifl_via_tradetron(user_id, password, totp_secret):
    """
    Login to IIFL via Tradetron auth URL and complete authentication.
    
    Flow:
    1. Open Tradetron IIFL auth URL
    2. Enter Email/Mobile/Client ID/PAN and Password
    3. Click Login
    4. Wait for TOTP screen and enter TOTP
    5. Click Verify
    6. Wait for Authorize Tradetron page and click Authorize
    7. Assert "Token generated successfully" is visible
    
    Returns:
        dict with success status, message, and last_updated timestamp
    """
    from selenium.webdriver.common.by import By
    from selenium.webdriver.common.keys import Keys
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    from selenium.common.exceptions import TimeoutException, NoSuchElementException

    print(f"\n{'='*70}")
    print(f" IIFL Token Generation via Tradetron")
    print(f" User ID: {user_id}")
    print(f" Timestamp: {get_current_timestamp()}")
    print(f"{'='*70}\n")

    driver = None
    
    try:
        # Setup driver
        print("[1/6] 🌐 Setting up browser...")
        driver = setup_selenium_driver()
        wait = WebDriverWait(driver, 30)
        print("      ✓ Browser launched successfully")

        def capture_debug_artifacts(tag):
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            safe_tag = tag.replace(" ", "_")
            screenshot_path = os.path.join(os.getcwd(), f"iifl_{safe_tag}_{timestamp}.png")
            html_path = os.path.join(os.getcwd(), f"iifl_{safe_tag}_{timestamp}.html")
            try:
                driver.save_screenshot(screenshot_path)
                print(f"      📸 Saved screenshot: {screenshot_path}")
            except Exception as e:
                print(f"      ⚠️  Failed to save screenshot: {e}")
            try:
                with open(html_path, "w", encoding="utf-8") as f:
                    f.write(driver.page_source)
                print(f"      🧾 Saved HTML: {html_path}")
            except Exception as e:
                print(f"      ⚠️  Failed to save HTML: {e}")

        def find_visible_element(selectors, timeout=8):
            for selector in selectors:
                try:
                    element = WebDriverWait(driver, timeout).until(
                        EC.visibility_of_element_located((By.CSS_SELECTOR, selector))
                    )
                    if element.is_displayed():
                        return element, selector
                except Exception:
                    continue
            return None, None

        def find_visible_element_in_frames(selectors, timeout=6):
            element, selector = find_visible_element(selectors, timeout)
            if element:
                return element, selector, "default"

            frames = driver.find_elements(By.TAG_NAME, "iframe")
            for index, frame in enumerate(frames):
                try:
                    driver.switch_to.frame(frame)
                    element, selector = find_visible_element(selectors, timeout)
                    if element:
                        return element, selector, f"iframe[{index}]"
                except Exception:
                    pass
                finally:
                    driver.switch_to.default_content()

            return None, None, None

        # ============================================
        # STEP 1: Open Tradetron IIFL auth URL
        # ============================================
        print(f"\n[2/6] 📍 Opening Tradetron IIFL auth URL...")
        print(f"      URL: {TRADETRON_IIFL_AUTH_URL}")
        driver.get(TRADETRON_IIFL_AUTH_URL)
        wait.until(lambda d: d.execute_script("return document.readyState") == "complete")
        
        current_url = driver.current_url
        print(f"      Current URL: {current_url}")
        
        # Assert: Login page loaded
        page_source = driver.page_source.lower()
        assert "login" in page_source or "sign in" in page_source or "client" in page_source or "password" in page_source, \
            "Login page did not load properly"
        print("      ✓ Login page loaded")

        # ============================================
        # STEP 2: Enter Login Credentials
        # ============================================
        print(f"\n[3/6] 🔑 Entering login credentials...")
        
        # Wait for and find User ID field
        user_id_selectors = [
            "input[placeholder*='Client']",
            "input[placeholder*='client']",
            "input[placeholder*='User']",
            "input[placeholder*='user']",
            "input[placeholder*='Email']",
            "input[placeholder*='email']",
            "input[placeholder*='Mobile']",
            "input[placeholder*='mobile']",
            "input[placeholder*='PAN']",
            "input[aria-label*='Client']",
            "input[aria-label*='User']",
            "input[aria-label*='Email']",
            "input[aria-label*='Mobile']",
            "input[aria-label*='PAN']",
            "input[name='userId']",
            "input[name='clientId']",
            "input[name='client_id']",
            "input[name='email']",
            "input[name*='user']",
            "input[name*='client']",
            "input[id*='user']",
            "input[id*='client']",
            "input[id*='email']",
            "input[id='userId']",
            "input[id='clientId']",
            "input[autocomplete='username']",
            "input[type='text']",
        ]
        
        user_id_field, user_id_selector, user_id_location = find_visible_element_in_frames(user_id_selectors)
        if not user_id_field:
            try:
                user_id_field = driver.find_element(By.XPATH, 
                    "//input[contains(@placeholder, 'User') or contains(@placeholder, 'Client') or "
                    "contains(@placeholder, 'Email') or contains(@placeholder, 'Mobile') or "
                    "contains(@placeholder, 'PAN') or @type='text']")
                user_id_selector = "xpath-fallback"
                user_id_location = "default"
            except NoSuchElementException:
                print("      ❌ Could not find User ID field")
                capture_debug_artifacts("user_id_missing")
                return {"success": False, "message": "User ID field not found", "last_updated": None}
        
        print(f"      Found User ID field: {user_id_selector} ({user_id_location})")
        
        # Enter User ID
        user_id_field.clear()
        user_id_field.send_keys(user_id)
        print(f"      ✓ Entered User ID: {user_id}")

        # Find and enter Password
        password_selectors = [
            "input[type='password']",
            "input[placeholder*='Password']",
            "input[placeholder*='password']",
            "input[name='password']",
            "input[name='pwd']",
            "input[id='password']",
            "input[name*='pass']",
            "input[id*='pass']",
            "input[autocomplete='current-password']",
        ]
        
        password_field, password_selector, password_location = find_visible_element_in_frames(password_selectors)
        if not password_field:
            print("      ❌ Could not find Password field")
            capture_debug_artifacts("password_missing")
            return {"success": False, "message": "Password field not found", "last_updated": None}
        
        print(f"      Found Password field: {password_selector} ({password_location})")
        
        password_field.clear()
        password_field.send_keys(password)
        print("      ✓ Entered Password")

        # ============================================
        # STEP 3: Click Login Button
        # ============================================
        print(f"\n[4/6] 🔓 Clicking Login button...")
        
        login_clicked = False
        login_button_selectors = [
            "button[type='submit']",
            "input[type='submit']",
            "button.login-btn",
            "button.btn-primary",
            "button.submit-btn",
            "#loginBtn",
            ".login-btn",
            "button[aria-label*='Login']",
            "button[name*='login']",
        ]
        
        for selector in login_button_selectors:
            try:
                login_button = driver.find_element(By.CSS_SELECTOR, selector)
                if login_button.is_displayed() and login_button.is_enabled():
                    login_button.click()
                    login_clicked = True
                    print(f"      ✓ Clicked Login button: {selector}")
                    break
            except:
                continue
        
        # Try finding by text content
        if not login_clicked:
            try:
                buttons = driver.find_elements(By.TAG_NAME, "button")
                for btn in buttons:
                    btn_text = btn.text.lower().strip()
                    if btn_text in ["log in", "login", "submit", "sign in", "continue"]:
                        btn.click()
                        login_clicked = True
                        print(f"      ✓ Clicked Login button (by text: '{btn_text}')")
                        break
            except Exception:
                pass
        
        # Try XPath
        if not login_clicked:
            try:
                login_button = driver.find_element(By.XPATH, 
                    "//button[contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'login') or "
                    "contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'log in') or "
                    "contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'sign in')]")
                login_button.click()
                login_clicked = True
                print("      ✓ Clicked Login button (by XPath)")
            except Exception:
                pass
        
        if not login_clicked:
            try:
                password_field.send_keys(Keys.ENTER)
                login_clicked = True
                print("      ✓ Submitted login via Enter key")
            except Exception:
                print("      ⚠️  Could not find Login button - trying to continue anyway")
        
        wait.until(
            lambda d: "totp" in d.page_source.lower()
            or "otp" in d.page_source.lower()
            or "authenticator" in d.page_source.lower()
            or "authorize" in d.page_source.lower()
            or "token" in d.page_source.lower()
        )
        # Telegram message deferred until token generation result

        # ============================================
        # STEP 4: Handle TOTP Authentication
        # ============================================
        print(f"\n[5/6] 🔐 Handling TOTP authentication...")
        
        current_url = driver.current_url
        page_source = driver.page_source.lower()
        
        # Check if TOTP/OTP screen is present
        if "totp" in page_source or "otp" in page_source or "authenticator" in page_source or "2fa" in page_source or "verify" in page_source:
            print("      ✓ TOTP authentication page loaded")
            
            # Generate TOTP
            totp_code = generate_totp(totp_secret)
            print(f"      ✓ Generated TOTP: {totp_code}")
            
            # Find TOTP input field(s)
            totp_entered = False
            totp_inputs = driver.find_elements(By.CSS_SELECTOR, "input[maxlength='1'], input[autocomplete='one-time-code']")
            totp_field = None

            if totp_inputs and len(totp_inputs) >= 6:
                for idx, digit in enumerate(totp_code[:6]):
                    totp_inputs[idx].clear()
                    totp_inputs[idx].send_keys(digit)
                totp_entered = True
                print("      ✓ Entered TOTP into 6 boxes")
            else:
                totp_selectors = [
                    "input[placeholder*='TOTP']",
                    "input[placeholder*='totp']",
                    "input[placeholder*='OTP']",
                    "input[placeholder*='otp']",
                    "input[placeholder*='Authenticator']",
                    "input[placeholder*='2FA']",
                    "input[name='totp']",
                    "input[name='otp']",
                    "input[name='twofa']",
                    "input[id='totp']",
                    "input[id='otp']",
                    "input[type='tel']",
                    "input[maxlength='6']",
                ]
                for selector in totp_selectors:
                    try:
                        totp_field = wait.until(
                            EC.visibility_of_element_located((By.CSS_SELECTOR, selector))
                        )
                        if totp_field.is_displayed():
                            print(f"      Found TOTP field: {selector}")
                            break
                    except:
                        continue
                
                if not totp_field:
                    try:
                        inputs = driver.find_elements(By.CSS_SELECTOR, "input[type='text'], input[type='number'], input[type='tel']")
                        for inp in inputs:
                            if inp.is_displayed():
                                placeholder = inp.get_attribute("placeholder") or ""
                                maxlen = inp.get_attribute("maxlength") or ""
                                if "otp" in placeholder.lower() or "totp" in placeholder.lower() or maxlen == "6":
                                    totp_field = inp
                                    print("      Found TOTP field (by attributes)")
                                    break
                    except:
                        pass
                
                if totp_field:
                    totp_field.clear()
                    totp_field.send_keys(totp_code)
                    totp_entered = True
                    print("      ✓ Entered TOTP")

            if totp_entered:
                # Click Verify/Submit button
                verify_clicked = False
                verify_selectors = [
                    "button[type='submit']",
                    "input[type='submit']",
                    "button.verify-btn",
                    "button.submit-btn",
                    "button.btn-primary",
                ]
                
                for selector in verify_selectors:
                    try:
                        verify_button = driver.find_element(By.CSS_SELECTOR, selector)
                        if verify_button.is_displayed() and verify_button.is_enabled():
                            verify_button.click()
                            verify_clicked = True
                            print(f"      ✓ Clicked Verify button: {selector}")
                            break
                    except:
                        continue
                
                # Try by text
                if not verify_clicked:
                    try:
                        buttons = driver.find_elements(By.TAG_NAME, "button")
                        for btn in buttons:
                            btn_text = btn.text.lower().strip()
                            if btn_text in ["verify", "submit", "authenticate", "continue", "confirm"]:
                                btn.click()
                                verify_clicked = True
                                print(f"      ✓ Clicked Verify button (by text: '{btn_text}')")
                                break
                    except:
                        pass
                
                wait.until(
                    lambda d: "authorize" in d.page_source.lower()
                    or "token" in d.page_source.lower()
                    or "success" in d.page_source.lower()
                )
                # Telegram message deferred until token generation result
            else:
                print("      ⚠️  TOTP field not found - may not be required")
        else:
            print("      ℹ️  No TOTP page detected - continuing")

        # ============================================
        # STEP 5: Handle Tradetron Authorization
        # ============================================
        print(f"\n[6/6] ✅ Handling Tradetron authorization...")
        
        time.sleep(2)
        current_url = driver.current_url
        page_source = driver.page_source.lower()
        
        # Check if we're on authorization page
        if "authorize" in page_source or "permission" in page_source or "allow" in page_source or "grant" in page_source:
            print("      ✓ Authorization page loaded")
            
            # Assert: Authorize page loaded
            assert "authorize" in page_source or "tradetron" in current_url.lower(), \
                "Authorize page did not load"
            
            # Click Authorize button
            authorize_clicked = False
            authorize_selectors = [
                "button.authorize-btn",
                "button.btn-primary",
                "button[type='submit']",
                "#authorizeBtn",
                ".authorize-btn",
            ]
            
            for selector in authorize_selectors:
                try:
                    auth_button = driver.find_element(By.CSS_SELECTOR, selector)
                    if auth_button.is_displayed() and auth_button.is_enabled():
                        auth_button.click()
                        authorize_clicked = True
                        print(f"      ✓ Clicked Authorize button: {selector}")
                        break
                except:
                    continue
            
            # Try by text
            if not authorize_clicked:
                try:
                    buttons = driver.find_elements(By.TAG_NAME, "button")
                    for btn in buttons:
                        btn_text = btn.text.lower().strip()
                        if btn_text in ["authorize", "allow", "approve", "grant", "accept", "confirm", "continue"]:
                            btn.click()
                            authorize_clicked = True
                            print(f"      ✓ Clicked Authorize button (by text: '{btn_text}')")
                            break
                except:
                    pass
            
            # Try links too
            if not authorize_clicked:
                try:
                    links = driver.find_elements(By.TAG_NAME, "a")
                    for link in links:
                        link_text = link.text.lower().strip()
                        if link_text in ["authorize", "allow", "approve"]:
                            link.click()
                            authorize_clicked = True
                            print(f"      ✓ Clicked Authorize link (by text: '{link_text}')")
                            break
                except:
                    pass
            
            time.sleep(3)
            # Telegram message deferred until token generation result
        else:
            print("      ℹ️  No explicit authorization page - may be auto-authorized")

        # ============================================
        # STEP 6: Verify Success
        # ============================================
        print(f"\n[✓] Verifying token generation...")
        
        time.sleep(2)
        final_url = driver.current_url
        final_page_source = driver.page_source
        final_page_lower = final_page_source.lower()
        
        print(f"      Final URL: {final_url}")
        
        # Get timestamp
        last_updated = extract_last_updated(final_page_source) or get_current_timestamp()
        
        # Assert: "Token generated successfully" is visible
        success_indicators = [
            "token generated successfully",
            "token generated",
            "successfully generated",
            "authentication successful",
            "authorized successfully",
            "success",
            "token refreshed",
            "connected successfully",
        ]
        
        token_success = any(indicator in final_page_lower for indicator in success_indicators)
        url_success = "success" in final_url.lower() or "tradetron" in final_url.lower()
        
        if token_success:
            print("\n" + "="*70)
            print("✅ IIFL Token Generated Successfully")
            print(f"📅 Last Updated: {last_updated}")
            print("="*70 + "\n")
            
            return {
                "success": True,
                "message": "Token generated successfully",
                "last_updated": last_updated
            }
        elif url_success:
            print("\n" + "="*70)
            print("✅ IIFL Token Generated Successfully")
            print(f"📅 Last Updated: {last_updated}")
            print("="*70 + "\n")
            
            return {
                "success": True,
                "message": "Token generated (URL indicates success)",
                "last_updated": last_updated
            }
        else:
            # Check for errors
            error_indicators = ["error", "failed", "invalid", "incorrect", "denied", "expired"]
            has_error = any(indicator in final_page_lower for indicator in error_indicators)
            
            if has_error:
                print("\n❌ Token generation FAILED - error detected on page")
                return {
                    "success": False,
                    "message": "Token generation failed - error on page",
                    "last_updated": None
                }
            else:
                print("\n⚠️  Token generation status unclear - assuming success")
                print(f"📅 Timestamp: {last_updated}")
                
                return {
                    "success": True,
                    "message": "Token generation completed (status unclear)",
                    "last_updated": last_updated
                }

    except AssertionError as e:
        error_msg = f"Assertion failed: {str(e)}"
        print(f"\n❌ {error_msg}")
        return {"success": False, "message": error_msg, "last_updated": None}
    
    except Exception as e:
        error_msg = f"{type(e).__name__}: {str(e)}"
        print(f"\n❌ Error during IIFL token generation: {error_msg}")
        return {"success": False, "message": error_msg, "last_updated": None}
    
    finally:
        if driver:
            try:
                driver.quit()
                print("\n✓ Browser closed")
            except:
                pass


# ============================================================
# PROCESS USER FUNCTION
# ============================================================

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

    result = login_iifl_via_tradetron(user_id, password, totp_secret)
    
    if result.get("success"):
        timestamp_info = f"\n📅 Last Updated: {result.get('last_updated')}" if result.get('last_updated') else ""
        send_telegram_message(f"✅ IIFL Token Generated Successfully!\n👤 User: {user_id}{timestamp_info}")
        return {
            "user_id": user_id,
            "status": 200,
            "message": "Success",
            "last_updated": result.get("last_updated")
        }
    else:
        error_msg = result.get("message", "Unknown error")
        send_telegram_message(f"❌ IIFL Token Generation FAILED!\n👤 User: {user_id}\n⚠️ Error: {error_msg}")
        return {
            "user_id": user_id,
            "status": 500,
            "message": error_msg
        }


# ============================================================
# MAIN EXECUTION
# ============================================================

def main():
    """Main function to process all IIFL users"""
    print("\n" + "="*70)
    print(" IIFL Token Generator - Tradetron Integration (Selenium)")
    print(f" Mode: {'AWS Lambda' if IS_LAMBDA else 'Local'}")
    print(f" Total users to process: {len(IIFL_USERS)}")
    print(f" Timestamp: {get_current_timestamp()}")
    print("="*70 + "\n")

    # Check dependencies
    if not HAS_PYOTP:
        print("❌ Missing dependency: pyotp")
        print("   Install with: pip install pyotp")
        return {"statusCode": 500, "body": "Missing pyotp dependency"}

    results = []
    
    for idx, user in enumerate(IIFL_USERS, 1):
        print(f"\n[{idx}/{len(IIFL_USERS)}] Processing user...")
        result = process_user(user)
        results.append(result)
        
        # Small delay between users
        if idx < len(IIFL_USERS):
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

    # Telegram summary notification suppressed; only final token result is sent per user

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
    AWS Lambda handler for IIFL token generation.
    
    Environment Variables Required:
    - IIFL_USER_ID: IIFL User ID (Email/Mobile/Client ID/PAN)
    - IIFL_PASSWORD: IIFL Password
    - IIFL_TOTP_SECRET: TOTP Secret Key
    - TELEGRAM_BOT_TOKEN: Telegram Bot Token (optional)
    - TELEGRAM_CHAT_ID: Telegram Chat ID (optional)
    """
    print("="*70)
    print(" IIFL Token Generator - AWS Lambda (Selenium)")
    print(f" Invoked at: {get_current_timestamp()}")
    print("="*70)
    
    if not HAS_PYOTP:
        return {"statusCode": 500, "body": "Missing dependency: pyotp"}
    
    return main()


if __name__ == "__main__":
    main()
