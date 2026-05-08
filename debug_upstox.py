"""
Debug script to understand Upstox chain data structure
Run this locally with: python debug_upstox.py
"""

import json
import requests
from datetime import datetime
import pytz



api_key=""
api_secret=""
redirect_uri=""

# Configuration
IST = pytz.timezone("Asia/Kolkata")

UPSTOX_TOKEN_URL = "https://api.upstox.com/v2/login/authorization/token"
UPSTOX_OC_URLS = [
    "https://api.upstox.com/v2/option/chain",
    "https://api.upstox.com/v3/option/chain"
]
UPSTOX_CONTRACT_URL = "https://api.upstox.com/v2/option/contract"

INSTRUMENT_KEY = {
    "NIFTY": "NSE_INDEX|Nifty 50",
    "BANKNIFTY": "NSE_INDEX|Nifty Bank",
}

STRIKE_CONFIG = {
    "NIFTY": {"gap": 50, "atm": 24000, "name": "NIFTY 50"},
    "BANKNIFTY": {"gap": 100, "atm": 55000, "name": "BANKNIFTY"},
}

def upstox_headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}", "Accept": "application/json"}

def exchange_code(api_key=api_key, api_secret=api_secret, redirect_uri=redirect_uri, code: str) -> tuple:
    """Exchange auth code for access token"""
    try:
        r = requests.post(
            UPSTOX_TOKEN_URL,
            data={
                "code": code,
                "client_id": api_key,
                "client_secret": api_secret,
                "redirect_uri": redirect_uri,
                "grant_type": "authorization_code",
            },
            headers={"Accept": "application/json"},
            timeout=15,
        )
        d = r.json()
        return (d["access_token"], None) if "access_token" in d else (None, str(d))
    except Exception as e:
        return None, str(e)

def fetch_expiry_dates(token: str, symbol: str) -> tuple:
    """Get available expiry dates"""
    try:
        r = requests.get(
            UPSTOX_CONTRACT_URL,
            params={"instrument_key": INSTRUMENT_KEY[symbol]},
            headers=upstox_headers(token),
            timeout=15,
        )
        d = r.json()
        if r.status_code == 401:
            return None, "token_expired"
        if d.get("status") == "success" and d.get("data"):
            raw = d["data"]
            dates = [
                str(item.get("expiry") or item.get("expiry_date") or "")
                for item in raw
            ] if raw and isinstance(raw[0], dict) else [str(x) for x in raw]
            dates = sorted(set([x for x in dates if x]))
            return (dates, None) if dates else (None, "Empty expiry list")
        return None, f"Failed: {d}"
    except Exception as e:
        return None, str(e)

def fetch_chain(token: str, symbol: str, expiry_date: str) -> tuple:
    """Fetch option chain data"""
    for url in UPSTOX_OC_URLS:
        try:
            print(f"\n[INFO] Trying URL: {url}")
            r = requests.get(
                url,
                params={
                    "instrument_key": INSTRUMENT_KEY[symbol],
                    "expiry_date": expiry_date,
                },
                headers=upstox_headers(token),
                timeout=15,
            )
            print(f"[INFO] Response status: {r.status_code}")
            d = r.json()
            if r.status_code == 401:
                return None, "token_expired", url
            if d.get("status") == "success":
                data = d.get("data") or []
                if data:
                    return data, None, url
                else:
                    print(f"[ERROR] No data in response")
        except Exception as e:
            print(f"[ERROR] Exception: {e}")
            pass

    return None, "Failed to fetch chain", UPSTOX_OC_URLS[-1]

def debug_chain_structure(token: str, symbol: str = "NIFTY"):
    """Debug the chain data structure"""
    print(f"\n{'='*80}")
    print(f"DEBUG: {symbol} Chain Data Structure")
    print(f"{'='*80}")

    # Get expiry dates
    expiry_dates, exp_err = fetch_expiry_dates(token, symbol)
    if exp_err:
        print(f"[ERROR] Failed to fetch expiry dates: {exp_err}")
        return

    print(f"[INFO] Available expiry dates: {expiry_dates}")
    if not expiry_dates:
        print("[ERROR] No expiry dates available")
        return

    # Fetch chain for first expiry
    selected_expiry = expiry_dates[0]
    print(f"[INFO] Using expiry: {selected_expiry}")

    data, chain_err, url = fetch_chain(token, symbol, selected_expiry)
    if chain_err:
        print(f"[ERROR] Failed to fetch chain: {chain_err}")
        return

    print(f"[SUCCESS] Fetched chain from: {url}")
    print(f"[INFO] Total rows in chain: {len(data)}")

    # Analyze structure
    if not data:
        print("[ERROR] No data in response")
        return

    print(f"\n[DEBUG] First row structure:")
    first_row = data[0]
    print(f"  Keys: {list(first_row.keys())}")

    # Print full first row (limited output)
    print(f"\n[DEBUG] First row (JSON):")
    print(json.dumps(first_row, indent=2, default=str)[:2000])

    # Check for strike_price and options structure
    if "strike_price" in first_row:
        print(f"\n[INFO] strike_price found: {first_row['strike_price']}")

    if "call_options" in first_row:
        print(f"\n[DEBUG] call_options keys: {list(first_row['call_options'].keys())}")
        if "market_data" in first_row['call_options']:
            print(f"[DEBUG]   market_data keys: {list(first_row['call_options']['market_data'].keys())}")
            ltp = first_row['call_options']['market_data'].get('ltp')
            print(f"[DEBUG]   LTP: {ltp}")

    if "put_options" in first_row:
        print(f"\n[DEBUG] put_options keys: {list(first_row['put_options'].keys())}")
        if "market_data" in first_row['put_options']:
            print(f"[DEBUG]   market_data keys: {list(first_row['put_options']['market_data'].keys())}")
            ltp = first_row['put_options']['market_data'].get('ltp')
            print(f"[DEBUG]   LTP: {ltp}")

    # Find ATM strike
    strikes = []
    for row in data:
        try:
            strike = int(float(row.get("strike_price", 0)))
            if strike > 0:
                strikes.append(strike)
        except:
            pass

    strikes = sorted(set(strikes))
    print(f"\n[INFO] Available strikes (first 15): {strikes[:15]}")

    # Get spot price
    spot = None
    for row in data:
        sp = row.get("underlying_spot_price")
        if sp:
            spot = float(sp)
            break

    if spot:
        print(f"[INFO] Underlying spot price: {spot}")

        # Calculate what we're looking for
        gap = STRIKE_CONFIG[symbol]["gap"]
        atm_strike = int(gap * round(spot / gap))
        print(f"[INFO] Calculated ATM strike: {atm_strike} (gap={gap})")

        # Check if ATM and surrounding strikes exist
        for i in range(1, 5):
            ce_strike = atm_strike + i * gap
            pe_strike = atm_strike - i * gap
            ce_exists = ce_strike in strikes
            pe_exists = pe_strike in strikes
            print(f"[INFO]   Strike {ce_strike} (CE): {'✓' if ce_exists else '✗'} | Strike {pe_strike} (PE): {'✓' if pe_exists else '✗'}")

if __name__ == "__main__":
    # Get credentials from environment or user input
    print("Upstox Chain Data Structure Debugger")
    print("=" * 80)
    print("\nTo use this script, you need Upstox API credentials.")
    print("1. Get your API key and secret from developer.upstox.com")
    print("2. Get an auth code by visiting (replace {api_key} and {redirect_uri}):")
    print("   https://api.upstox.com/v2/login/authorization/dialog?response_type=code&client_id={api_key}&redirect_uri={redirect_uri}")
    print("3. Use the code parameter value to exchange for access token\n")

    api_key = input("Enter API Key: ").strip()
    api_secret = input("Enter API Secret: ").strip()
    redirect_uri = input("Enter Redirect URI: ").strip()
    auth_code = input("Enter Auth Code: ").strip()

    print("\n[INFO] Exchanging auth code for access token...")
    token, err = exchange_code(api_key, api_secret, redirect_uri, auth_code)

    if err:
        print(f"[ERROR] Failed to exchange code: {err}")
        exit(1)

    print(f"[SUCCESS] Got access token: {token[:20]}...")

    # Debug NIFTY and BANKNIFTY
    debug_chain_structure(token, "NIFTY")
    debug_chain_structure(token, "BANKNIFTY")

    print(f"\n{'='*80}")
    print("Debug complete. Share this output with the developer.")
    print(f"{'='*80}")
