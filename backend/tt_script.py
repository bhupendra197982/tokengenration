#!/usr/bin/env python3
"""
Tradetron Broker Token Regenerator
===================================
Automates the process of regenerating broker tokens on Tradetron
without needing to use the UI.

Usage: python3 tradetron_token_regenerator.py

Configuration: Set your credentials below or use environment variables: 
TRADETRON_EMAIL 
TRADETRON_PASSWORD 
TRADETRON_BROKER_ID (917)
"""

import getpass
import os
import sys
import re
import time
import urllib.parse
import requests

# ============================================================
# CONFIGURATION - Set your credentials here or via env vars
# ============================================================
# Broker id you would get from the Network tab that it calls, 
# you would get it on this link 
# user/broker-and-exchanges/regenerate-token/{BROKER_ID}

EMAIL = os.environ.get("TRADETRON_EMAIL", "trailblazerbhupendra@gmail.com")
PASSWORD = os.environ.get("TRADETRON_PASSWORD", "Verma@1234")
BROKER_ID = os.environ.get("TRADETRON_BROKER_ID", "387")
# ============================================================

import hashlib
import json
import base64

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

def solve_altcha_challenge(session: requests.Session) -> str: 
    """
    Fetch and solve the Altcha proof-of-work challenge. 
    Altcha works by requiring the client to find a number `n` such that 
    SHA-256(salt + n) == challenge. The server provides maxnumber as upper bound. 
    Returns a base64-encoded JSON payload to include in the login form. 
    """ 
    print(" Fetching Altcha challenge...") 
    
    resp = session.get(ALTCHA_CHALLENGE_URL, headers={ 
        **HEADERS, 
        "Accept": "application/json", 
        "Referer": LOGIN_PAGE_URL, 
    }) 
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

    # Build the Altcha payload (base64-encoded JSON) 
    payload = { 
        "algorithm": algorithm, 
        "challenge": challenge, 
        "number": solution, 
        "salt": salt, 
        "signature": signature, 
    } 
    return base64.b64encode(json.dumps(payload).encode()).decode()

def get_xsrf_token_decoded(session: requests.Session) -> str: 
    """Extract and URL-decode the XSRF-TOKEN from session cookies.""" 
    token = session.cookies.get("XSRF-TOKEN", domain="tradetron.tech") 
    if not token: 
        # Try without domain filter 
        token = session.cookies.get("XSRF-TOKEN") 
    
    if not token: 
        raise RuntimeError("XSRF-TOKEN not found in cookies") 
    
    return urllib.parse.unquote(token)

def extract_csrf_from_html(html: str) -> str: 
    """Extract the _token (CSRF) from the login page HTML form.""" 
    # Laravel embeds a hidden _token field in forms 
    # Try various patterns 
    patterns = [ 
        r'name="_token"\s+value="([^"]+)"', 
        r'value="([^"]+)"\s+name="_token"', 
        r'name="csrf-token"\s+content="([^"]+)"', 
        r'<meta\s+name="csrf-token"\s+content="([^"]+)"', 
        r'<meta\s+content="([^"]+)"\s+name="csrf-token"', 
        r'"_token"\s*:\s*"([^"]+)"', 
        r"'_token'\s*:\s*'([^']+)'", 
        r'csrf[_-]?token["\s:=]+([a-zA-Z0-9]{20,})', 
    ] 
    
    for pattern in patterns: 
        match = re.search(pattern, html, re.IGNORECASE) 
        if match: 
            return match.group(1)

    # Debug: save the page so user can inspect 
    debug_file = "tmp_rovodev_login_page_debug.html" 
    with open(debug_file, "w", encoding="utf-8") as f: 
        f.write(html) 
    
    raise RuntimeError( 
        f"Could not extract CSRF token from login page. " 
        f"Page HTML saved to '{debug_file}' for inspection." 
    )

def login(session: requests.Session) -> bool: 
    """Login to Tradetron and establish an authenticated session.""" 
    print("[1/3] Loading login page...") 
    resp = session.get(LOGIN_PAGE_URL, headers=HEADERS) 
    resp.raise_for_status()

    # Try to extract CSRF token from the HTML form 
    csrf_token = None 
    try: 
        csrf_token = extract_csrf_from_html(resp.text) 
        print(f" CSRF token from HTML: {csrf_token[:20]}...") 
    except RuntimeError: 
        print(" No CSRF token in HTML, will use XSRF cookie instead.")

    # Get the XSRF token from cookies 
    xsrf_token = get_xsrf_token_decoded(session) 
    print(f" XSRF cookie token obtained: {xsrf_token[:20]}...")

    # If no form CSRF token, use the XSRF cookie value 
    if not csrf_token: 
        csrf_token = xsrf_token

    # Solve the Altcha proof-of-work challenge 
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

    # After successful login, we should be redirected to dashboard or home 
    # If we land back on the login page, login failed 
    if resp.url.rstrip("/").endswith("/login"): 
        if "These credentials do not match" in resp.text: 
            print(" ✗ Login FAILED: Invalid email or password.") 
            return False 
        
        if "Too Many Attempts" in resp.text: 
            print(" ✗ Login FAILED: Too many attempts. Please wait and try again.") 
            return False 
        
        print(" ✗ Login FAILED: Still on login page after POST.") 
        
        # Save response for debugging 
        debug_file = "tmp_rovodev_login_response_debug.html" 
        with open(debug_file, "w", encoding="utf-8") as f: 
            f.write(resp.text) 
        print(f" Debug: response saved to '{debug_file}'") 
        
        # Try to find error messages for helpful output 
        error_patterns = [ 
            r'class="[^"]*(?:alert|error|invalid|danger)[^"]*"[^>]*>\s*<[^>]+>\s*([^<]+)', 
            r'class="[^"]*(?:alert|error|invalid|danger)[^"]*"[^>]*>([^<]+)', 
            r'<li>([^<]*credentials[^<]*)</li>', 
            r'<li>([^<]*password[^<]*)</li>', 
            r'<li>([^<]*email[^<]*)</li>', 
            r'<span[^>]*>([^<]*(?:error|invalid|incorrect|wrong|fail)[^<]*)</span>', 
        ] 
        
        for pat in error_patterns: 
            m = re.search(pat, resp.text, re.IGNORECASE) 
            if m and m.group(1).strip(): 
                print(f" Error detail: {m.group(1).strip()}") 
                break 
        
        return False

    # Verify we have a valid session 
    print(" ✓ Login successful!") 
    return True

def regenerate_token(session: requests.Session) -> bool: 
    """Call the regenerate-token endpoint.""" 
    print(f"[3/3] Regenerating token for broker ID {BROKER_ID}...")

    # Refresh XSRF token (may have changed after login) 
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

    # The endpoint returns 302 -> redirects to /user/broker-and-exchanges 
    # A successful regeneration typically redirects back to the broker page 
    if resp.status_code == 200 and "broker-and-exchanges" in resp.url: 
        print(" ✓ Token regenerated successfully!") 
        print(f" Final URL: {resp.url}") 
        return True

    if resp.status_code == 200: 
        print(f" ✓ Request completed (status: {resp.status_code})") 
        print(f" Final URL: {resp.url}") 
        
        # Check for success indicators in the page 
        if "Token regenerated" in resp.text or "success" in resp.text.lower(): 
            print(" ✓ Token regeneration confirmed!") 
            return True

    print(f" ✗ Unexpected response: {resp.status_code}") 
    print(f" URL: {resp.url}") 
    return False

def main(): 
    global EMAIL, PASSWORD

    # Validate config — prompt interactively if not set 
    if EMAIL == "YOUR_EMAIL_HERE": 
        EMAIL = input("Enter your Tradetron email: ").strip() 
    if PASSWORD == "YOUR_PASSWORD_HERE": 
        PASSWORD = getpass.getpass("Enter your Tradetron password: ")

    if not EMAIL or not PASSWORD: 
        print("ERROR: Email and password are required.") 
        sys.exit(1)

    print("=" * 60) 
    print(" Tradetron Broker Token Regenerator") 
    print(f" Broker ID: {BROKER_ID}") 
    print(f" Email: {EMAIL}") 
    print("=" * 60) 
    print()

    session = requests.Session() 
    
    # Don't auto-redirect on the regenerate call so we can inspect it 
    # But DO auto-redirect for login
    try: 
        if not login(session): 
            print("\nAborting due to login failure.") 
            sys.exit(1)

        # Small delay to be safe 
        time.sleep(1)

        if regenerate_token(session): 
            print("\n✓ Done! Token regeneration completed successfully.") 
            sys.exit(0) 
        else: 
            print("\n✗ Token regeneration may have failed. Check Tradetron UI.") 
            sys.exit(1)

    except requests.exceptions.ConnectionError as e: 
        print(f"\n✗ Connection error: {e}") 
        sys.exit(1) 
    except requests.exceptions.Timeout as e: 
        print(f"\n✗ Request timed out: {e}") 
        sys.exit(1) 
    except RuntimeError as e: 
        print(f"\n✗ Error: {e}") 
        sys.exit(1) 
    except Exception as e: 
        print(f"\n✗ Unexpected error: {type(e).__name__}: {e}") 
        sys.exit(1)

if __name__ == "__main__": 
    main()