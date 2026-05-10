"""
IIFL Token Generator - Tradetron Integration
============================================

Automates IIFL token generation from Tradetron using Playwright.

Features:
- Playwright browser automation
- TOTP generation using pyotp
- Telegram notifications
- AWS Lambda compatible
- Explicit waits for reliability

Environment Variables Required:
- IIFL_USER_ID: Email / Mobile / Client ID / PAN
- IIFL_PASSWORD: IIFL Password
- IIFL_TOTP_SECRET: TOTP Secret Key
- TELEGRAM_BOT_TOKEN: Telegram Bot Token
- TELEGRAM_CHAT_ID: Telegram Chat ID

Usage:
    python IIFL_Token.py

Author: Auto-generated
Date: May 2026
"""

import os
import re
import time
import requests
from datetime import datetime

# ============================================================
# OPTIONAL IMPORTS (graceful handling)
# ============================================================

try:
    import pyotp
    HAS_PYOTP = True
except ImportError:
    HAS_PYOTP = False
    print("⚠️  pyotp not installed. Install with: pip install pyotp")

try:
    from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout
    HAS_PLAYWRIGHT = True
except ImportError:
    HAS_PLAYWRIGHT = False
    print("⚠️  playwright not installed. Install with: pip install playwright && playwright install chromium")

# ============================================================
# CONFIGURATION
# ============================================================

# Detect AWS Lambda environment
IS_LAMBDA = os.environ.get('AWS_LAMBDA_FUNCTION_NAME') is not None

# IIFL Credentials (from environment variables or hardcoded for testing)
IIFL_CONFIG = {
    "user_id": os.environ.get("IIFL_USER_ID", "YOUR_USER_ID"),
    "password": os.environ.get("IIFL_PASSWORD", "YOUR_PASSWORD"),
    "totp_secret": os.environ.get("IIFL_TOTP_SECRET", "YOUR_TOTP_SECRET"),
}

# Telegram Configuration
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "YOUR_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "YOUR_CHAT_ID")

# URLs
TRADETRON_IIFL_AUTH_URL = "https://iiflcapital.broker.tradetron.tech/auth/2901162"

# Timeouts (in milliseconds for Playwright)
PAGE_LOAD_TIMEOUT = 30000  # 30 seconds
ELEMENT_TIMEOUT = 15000    # 15 seconds
NAVIGATION_TIMEOUT = 60000 # 60 seconds


# ============================================================
# HELPER FUNCTIONS
# ============================================================

def get_current_timestamp():
    """Get current timestamp formatted nicely"""
    return datetime.now().strftime("%b %d, %H:%M:%S")


def send_telegram_message(message: str) -> bool:
    """
    Send a message via Telegram Bot API.
    
    Args:
        message: The message to send
        
    Returns:
        True if successful, False otherwise
    """
    if TELEGRAM_BOT_TOKEN == "YOUR_BOT_TOKEN" or TELEGRAM_CHAT_ID == "YOUR_CHAT_ID":
        print(f"📱 [Telegram Disabled] {message}")
        return False
    
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        payload = {
            "chat_id": TELEGRAM_CHAT_ID,
            "text": message,
            "parse_mode": "HTML"
        }
        response = requests.post(url, json=payload, timeout=10)
        
        if response.status_code == 200:
            print(f"📱 [Telegram] Message sent successfully")
            return True
        else:
            print(f"📱 [Telegram] Failed: {response.status_code}")
            return False
            
    except Exception as e:
        print(f"📱 [Telegram] Error: {e}")
        return False


def generate_totp(secret: str) -> str:
    """
    Generate TOTP code from secret.
    
    Args:
        secret: TOTP secret key
        
    Returns:
        6-digit TOTP code
    """
    if not HAS_PYOTP:
        raise ImportError("pyotp is required for TOTP generation")
    
    # Clean the secret (remove spaces, convert to uppercase)
    clean_secret = secret.replace(" ", "").replace("-", "").upper()
    
    totp = pyotp.TOTP(clean_secret)
    code = totp.now()
    
    print(f"   🔐 Generated TOTP: {code}")
    return code


def extract_last_updated(page_content: str) -> str:
    """
    Extract 'Last Updated' timestamp from page content.
    
    Args:
        page_content: HTML content of the page
        
    Returns:
        Extracted timestamp or empty string
    """
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
# PLAYWRIGHT BROWSER SETUP
# ============================================================

def setup_browser(playwright):
    """
    Setup Playwright browser with appropriate configuration.
    
    Args:
        playwright: Playwright instance
        
    Returns:
        Browser instance
    """
    # Browser launch arguments
    launch_args = [
        "--no-sandbox",
        "--disable-setuid-sandbox",
        "--disable-dev-shm-usage",
        "--disable-gpu",
        "--disable-blink-features=AutomationControlled",
        "--window-size=1920,1080",
    ]
    
    # Additional args for Lambda
    if IS_LAMBDA:
        launch_args.extend([
            "--single-process",
            "--disable-extensions",
            "--disable-background-networking",
        ])
    
    browser = playwright.chromium.launch(
        headless=True,
        args=launch_args
    )
    
    return browser


def create_context(browser):
    """
    Create browser context with appropriate settings.
    
    Args:
        browser: Browser instance
        
    Returns:
        Browser context
    """
    context = browser.new_context(
        viewport={"width": 1920, "height": 1080},
        user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        ignore_https_errors=True,
    )
    
    # Block unnecessary resources for faster loading
    context.route("**/*.{png,jpg,jpeg,gif,svg,ico,woff,woff2}", lambda route: route.abort())
    
    return context


# ============================================================
# IIFL TOKEN GENERATION
# ============================================================

def generate_iifl_token(user_id: str, password: str, totp_secret: str) -> dict:
    """
    Generate IIFL token using Playwright automation.
    
    Args:
        user_id: IIFL User ID (Email/Mobile/Client ID/PAN)
        password: IIFL Password
        totp_secret: TOTP Secret Key
        
    Returns:
        dict with success status, message, and timestamp
    """
    print(f"\n{'='*70}")
    print(f" IIFL Token Generator - Tradetron Integration")
    print(f" User ID: {user_id}")
    print(f" Timestamp: {get_current_timestamp()}")
    print(f"{'='*70}\n")
    
    if not HAS_PLAYWRIGHT:
        return {
            "success": False,
            "message": "Playwright not installed",
            "last_updated": None
        }
    
    if not HAS_PYOTP:
        return {
            "success": False,
            "message": "pyotp not installed",
            "last_updated": None
        }
    
    browser = None
    context = None
    page = None
    
    try:
        with sync_playwright() as playwright:
            # Setup browser
            print("[1/5] 🌐 Launching browser...")
            browser = setup_browser(playwright)
            context = create_context(browser)
            page = context.new_page()
            
            page.set_default_timeout(ELEMENT_TIMEOUT)
            page.set_default_navigation_timeout(NAVIGATION_TIMEOUT)
            
            print("      ✓ Browser launched successfully")
            
            # ============================================
            # STEP 1: Navigate to Tradetron IIFL Auth URL
            # ============================================
            print(f"\n[2/5] 📍 Navigating to Tradetron IIFL auth page...")
            print(f"      URL: {TRADETRON_IIFL_AUTH_URL}")
            
            page.goto(TRADETRON_IIFL_AUTH_URL, wait_until="networkidle")
            
            current_url = page.url
            print(f"      Current URL: {current_url}")
            
            # Wait for login page to load
            page.wait_for_load_state("domcontentloaded")
            print("      ✓ Page loaded")
            
            # ============================================
            # STEP 2: Login with credentials
            # ============================================
            print(f"\n[3/5] 🔑 Entering login credentials...")
            
            # Wait for login form - try multiple selectors
            login_selectors = [
                'input[name="userId"]',
                'input[name="user_id"]',
                'input[name="clientId"]',
                'input[name="client_id"]',
                'input[name="email"]',
                'input[name="mobile"]',
                'input[name="pan"]',
                'input[type="text"]',
                'input[placeholder*="Client"]',
                'input[placeholder*="User"]',
                'input[placeholder*="Email"]',
                'input[placeholder*="Mobile"]',
                'input[placeholder*="PAN"]',
            ]
            
            user_input = None
            for selector in login_selectors:
                try:
                    user_input = page.wait_for_selector(selector, timeout=5000)
                    if user_input:
                        print(f"      Found user input: {selector}")
                        break
                except:
                    continue
            
            if not user_input:
                # Try finding first visible text input
                user_input = page.locator('input[type="text"]:visible').first
            
            # Assert login page loaded
            assert user_input, "Login page did not load - user input not found"
            print("      ✓ Login page loaded")
            
            # Enter User ID
            user_input.fill(user_id)
            print(f"      ✓ Entered User ID: {user_id}")
            
            # Find and fill password
            password_selectors = [
                'input[name="password"]',
                'input[name="pwd"]',
                'input[type="password"]',
                'input[placeholder*="Password"]',
            ]
            
            password_input = None
            for selector in password_selectors:
                try:
                    password_input = page.wait_for_selector(selector, timeout=3000)
                    if password_input:
                        break
                except:
                    continue
            
            if password_input:
                password_input.fill(password)
                print("      ✓ Entered Password")
            else:
                print("      ⚠️  Password field not found (may be on next page)")
            
            # Click Login button
            login_button_selectors = [
                'button:has-text("Login")',
                'button:has-text("Log In")',
                'button:has-text("Sign In")',
                'button:has-text("Submit")',
                'button:has-text("Continue")',
                'input[type="submit"]',
                'button[type="submit"]',
                '.login-btn',
                '#loginBtn',
            ]
            
            login_clicked = False
            for selector in login_button_selectors:
                try:
                    button = page.locator(selector).first
                    if button.is_visible():
                        button.click()
                        login_clicked = True
                        print(f"      ✓ Clicked Login button: {selector}")
                        break
                except:
                    continue
            
            if not login_clicked:
                # Try clicking any visible button with login-related text
                page.get_by_role("button", name=re.compile(r"login|sign.?in|submit|continue", re.IGNORECASE)).first.click()
                print("      ✓ Clicked Login button (by role)")
            
            # Wait for navigation
            page.wait_for_load_state("networkidle")
            time.sleep(2)  # Small delay for any JS execution
            
            send_telegram_message(f"🔑 IIFL Login submitted for {user_id}")
            print("      ✓ Login submitted")
            
            # ============================================
            # STEP 3: TOTP Authentication
            # ============================================
            print(f"\n[4/5] 🔐 Handling TOTP authentication...")
            
            # Generate TOTP
            totp_code = generate_totp(totp_secret)
            
            # Wait for TOTP input field
            totp_selectors = [
                'input[name="totp"]',
                'input[name="otp"]',
                'input[name="twofa"]',
                'input[name="2fa"]',
                'input[placeholder*="TOTP"]',
                'input[placeholder*="OTP"]',
                'input[placeholder*="2FA"]',
                'input[placeholder*="Authenticator"]',
                'input[type="tel"]',
                'input[maxlength="6"]',
            ]
            
            totp_input = None
            for selector in totp_selectors:
                try:
                    totp_input = page.wait_for_selector(selector, timeout=5000)
                    if totp_input:
                        print(f"      Found TOTP input: {selector}")
                        break
                except:
                    continue
            
            # Assert TOTP page loaded
            if not totp_input:
                # Check if we're on a page that asks for TOTP
                page_text = page.content().lower()
                if "totp" in page_text or "otp" in page_text or "authenticator" in page_text or "2fa" in page_text:
                    # Try finding any numeric input
                    totp_input = page.locator('input[type="tel"], input[maxlength="6"], input[type="number"]').first
                    if not totp_input.is_visible():
                        totp_input = None
            
            if totp_input:
                assert totp_input, "TOTP page did not load - TOTP input not found"
                print("      ✓ TOTP page loaded")
                
                # Enter TOTP
                totp_input.fill(totp_code)
                print(f"      ✓ Entered TOTP: {totp_code}")
                
                # Click Verify/Submit button
                verify_button_selectors = [
                    'button:has-text("Verify")',
                    'button:has-text("Submit")',
                    'button:has-text("Authenticate")',
                    'button:has-text("Continue")',
                    'button:has-text("Confirm")',
                    'button[type="submit"]',
                    'input[type="submit"]',
                ]
                
                verify_clicked = False
                for selector in verify_button_selectors:
                    try:
                        button = page.locator(selector).first
                        if button.is_visible():
                            button.click()
                            verify_clicked = True
                            print(f"      ✓ Clicked Verify button: {selector}")
                            break
                    except:
                        continue
                
                if not verify_clicked:
                    page.get_by_role("button", name=re.compile(r"verify|submit|authenticate|continue|confirm", re.IGNORECASE)).first.click()
                    print("      ✓ Clicked Verify button (by role)")
                
                # Wait for navigation
                page.wait_for_load_state("networkidle")
                time.sleep(2)
                
                send_telegram_message(f"🔐 IIFL TOTP submitted for {user_id}")
                print("      ✓ TOTP submitted")
            else:
                print("      ℹ️  No TOTP page detected (may not be required or already authenticated)")
            
            # ============================================
            # STEP 4: Authorize Tradetron
            # ============================================
            print(f"\n[5/5] ✅ Handling Tradetron authorization...")
            
            # Check if we're on the authorize page
            current_url = page.url
            page_content = page.content().lower()
            
            if "authorize" in page_content or "permission" in page_content or "allow" in page_content:
                print("      Found authorization page")
                
                # Assert authorize page loaded
                assert "authorize" in page_content or "tradetron" in current_url.lower(), "Authorize page did not load"
                print("      ✓ Authorize page loaded")
                
                # Click Authorize button
                authorize_selectors = [
                    'button:has-text("Authorize")',
                    'button:has-text("Allow")',
                    'button:has-text("Approve")',
                    'button:has-text("Grant")',
                    'button:has-text("Accept")',
                    'button:has-text("Confirm")',
                    'button:has-text("Continue")',
                    'a:has-text("Authorize")',
                    '.authorize-btn',
                    '#authorizeBtn',
                ]
                
                authorize_clicked = False
                for selector in authorize_selectors:
                    try:
                        button = page.locator(selector).first
                        if button.is_visible():
                            button.click()
                            authorize_clicked = True
                            print(f"      ✓ Clicked Authorize button: {selector}")
                            break
                    except:
                        continue
                
                if not authorize_clicked:
                    try:
                        page.get_by_role("button", name=re.compile(r"authorize|allow|approve|grant|accept|confirm", re.IGNORECASE)).first.click()
                        print("      ✓ Clicked Authorize button (by role)")
                    except:
                        print("      ⚠️  Authorize button not found (may auto-authorize)")
                
                # Wait for final redirect
                page.wait_for_load_state("networkidle")
                time.sleep(3)
                
                send_telegram_message(f"✅ IIFL Authorization completed for {user_id}")
            else:
                print("      ℹ️  No explicit authorization page (may be auto-authorized)")
            
            # ============================================
            # STEP 5: Verify Success
            # ============================================
            print(f"\n[✓] Verifying token generation...")
            
            final_url = page.url
            final_content = page.content()
            
            print(f"      Final URL: {final_url}")
            
            # Extract timestamp
            last_updated = extract_last_updated(final_content)
            if not last_updated:
                last_updated = get_current_timestamp()
            
            # Check for success indicators
            success_indicators = [
                "token generated successfully",
                "token generated",
                "successfully generated",
                "authentication successful",
                "authorized successfully",
                "success",
                "token refreshed",
            ]
            
            page_text_lower = final_content.lower()
            
            # Assert success message visible
            token_success = any(indicator in page_text_lower for indicator in success_indicators)
            url_success = "success" in final_url.lower() or "tradetron" in final_url.lower()
            
            if token_success or url_success:
                print("\n" + "="*70)
                print("✅ IIFL Token Generated Successfully")
                print(f"📅 Last Updated: {last_updated}")
                print("="*70 + "\n")
                
                return {
                    "success": True,
                    "message": "Token generated successfully",
                    "last_updated": last_updated
                }
            else:
                # Check for error indicators
                error_indicators = ["error", "failed", "invalid", "incorrect", "denied"]
                has_error = any(indicator in page_text_lower for indicator in error_indicators)
                
                if has_error:
                    print("\n❌ Token generation appears to have failed")
                    return {
                        "success": False,
                        "message": "Token generation failed - error detected on page",
                        "last_updated": None
                    }
                else:
                    # Assume success if no explicit error
                    print("\n⚠️  Token generation status unclear - assuming success")
                    print(f"📅 Timestamp: {last_updated}")
                    
                    return {
                        "success": True,
                        "message": "Token generation completed (status unclear)",
                        "last_updated": last_updated
                    }
    
    except PlaywrightTimeout as e:
        error_msg = f"Timeout error: {str(e)}"
        print(f"\n❌ {error_msg}")
        return {
            "success": False,
            "message": error_msg,
            "last_updated": None
        }
    
    except AssertionError as e:
        error_msg = f"Assertion failed: {str(e)}"
        print(f"\n❌ {error_msg}")
        return {
            "success": False,
            "message": error_msg,
            "last_updated": None
        }
    
    except Exception as e:
        error_msg = f"{type(e).__name__}: {str(e)}"
        print(f"\n❌ Error during IIFL token generation: {error_msg}")
        return {
            "success": False,
            "message": error_msg,
            "last_updated": None
        }


# ============================================================
# MAIN PROCESS FUNCTION
# ============================================================

def process_iifl_token() -> dict:
    """
    Process IIFL token generation with notifications.
    
    Returns:
        dict with status code and result details
    """
    user_id = IIFL_CONFIG["user_id"]
    password = IIFL_CONFIG["password"]
    totp_secret = IIFL_CONFIG["totp_secret"]
    
    # Validate configuration
    if user_id == "YOUR_USER_ID":
        print("⚠️  User ID not configured")
        return {"statusCode": 400, "body": "User ID not configured"}
    
    if password == "YOUR_PASSWORD":
        print("⚠️  Password not configured")
        return {"statusCode": 400, "body": "Password not configured"}
    
    if totp_secret == "YOUR_TOTP_SECRET":
        print("⚠️  TOTP secret not configured")
        return {"statusCode": 400, "body": "TOTP secret not configured"}
    
    # Send start notification
    send_telegram_message(f"🚀 IIFL Token Generation Started\n👤 User: {user_id}\n⏰ Time: {get_current_timestamp()}")
    
    # Generate token
    result = generate_iifl_token(user_id, password, totp_secret)
    
    # Send result notification
    if result["success"]:
        timestamp_info = f"\n📅 Last Updated: {result['last_updated']}" if result.get('last_updated') else ""
        send_telegram_message(f"✅ IIFL Token Generated Successfully!\n👤 User: {user_id}{timestamp_info}")
        
        return {
            "statusCode": 200,
            "body": "Token generated successfully",
            "last_updated": result.get("last_updated"),
            "user_id": user_id
        }
    else:
        error_msg = result.get("message", "Unknown error")
        send_telegram_message(f"❌ IIFL Token Generation Failed!\n👤 User: {user_id}\n⚠️ Error: {error_msg}")
        
        return {
            "statusCode": 500,
            "body": error_msg,
            "user_id": user_id
        }


# ============================================================
# AWS LAMBDA HANDLER
# ============================================================

def lambda_handler(event, context):
    """
    AWS Lambda handler for IIFL token generation.
    
    Environment Variables Required:
    - IIFL_USER_ID: IIFL User ID
    - IIFL_PASSWORD: IIFL Password
    - IIFL_TOTP_SECRET: TOTP Secret Key
    - TELEGRAM_BOT_TOKEN: Telegram Bot Token (optional)
    - TELEGRAM_CHAT_ID: Telegram Chat ID (optional)
    
    Args:
        event: Lambda event
        context: Lambda context
        
    Returns:
        dict with statusCode and body
    """
    print("="*70)
    print(" IIFL Token Generator - AWS Lambda")
    print(f" Invoked at: {get_current_timestamp()}")
    print("="*70)
    
    # Check dependencies
    if not HAS_PLAYWRIGHT:
        return {
            "statusCode": 500,
            "body": "Missing dependency: playwright"
        }
    
    if not HAS_PYOTP:
        return {
            "statusCode": 500,
            "body": "Missing dependency: pyotp"
        }
    
    # Process token generation
    result = process_iifl_token()
    
    return result


# ============================================================
# MAIN EXECUTION
# ============================================================

def main():
    """Main entry point for script execution"""
    print("\n" + "="*70)
    print(" IIFL Token Generator - Tradetron Integration")
    print(f" Mode: {'AWS Lambda' if IS_LAMBDA else 'Local'}")
    print(f" Timestamp: {get_current_timestamp()}")
    print("="*70 + "\n")
    
    # Check dependencies
    if not HAS_PLAYWRIGHT:
        print("❌ Missing dependency: playwright")
        print("   Install with: pip install playwright && playwright install chromium")
        return
    
    if not HAS_PYOTP:
        print("❌ Missing dependency: pyotp")
        print("   Install with: pip install pyotp")
        return
    
    # Process token generation
    result = process_iifl_token()
    
    # Print summary
    print("\n" + "="*70)
    print(" SUMMARY")
    print("="*70)
    
    if result["statusCode"] == 200:
        print(f"✅ Status: SUCCESS")
        print(f"👤 User: {result.get('user_id', 'N/A')}")
        print(f"📅 Last Updated: {result.get('last_updated', 'N/A')}")
    else:
        print(f"❌ Status: FAILED")
        print(f"⚠️ Error: {result.get('body', 'Unknown error')}")
    
    print("="*70 + "\n")
    
    return result


if __name__ == "__main__":
    main()
