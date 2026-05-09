"""
Raj Pro Options Engine - Complete App
Matches Pine Script indicator 100%
"""

import streamlit as st
import requests
import time
import pandas as pd
from datetime import datetime, timedelta
import pytz
import sys
from io import StringIO
from pathlib import Path

from engine_exact import RajProEngine
from gamma_analysis import GammaAnalyzer
from complete_table import RajProTable

# ─────────────────────────────────────────────
# LOG CAPTURE SETUP - Store logs in session state
# ─────────────────────────────────────────────
class SessionStateLogger:
    """Capture logs to session state for display"""
    def __init__(self):
        self.console = sys.__stdout__  # Original stdout

    def write(self, message):
        self.console.write(message)  # Print to console
        if hasattr(st, 'session_state'):
            if 'debug_logs' not in st.session_state:
                st.session_state.debug_logs = []
            st.session_state.debug_logs.append(message)

    def flush(self):
        self.console.flush()

# Initialize session state logs
if 'debug_logs' not in st.session_state:
    st.session_state.debug_logs = []

# Start capturing output
sys.stdout = SessionStateLogger()

# ─────────────────────────────────────────────
# CONFIG
# ─────────────────────────────────────────────
IST = pytz.timezone("Asia/Kolkata")

STRIKE_CONFIG = {
    "NIFTY": {"gap": 50, "atm": 24000, "name": "NIFTY 50"},
    "BANKNIFTY": {"gap": 100, "atm": 55000, "name": "BANKNIFTY"},
    "FINNIFTY": {"gap": 50, "atm": 24000, "name": "FINNIFTY"},
    "MIDCPNIFTY": {"gap": 25, "atm": 12000, "name": "MIDCPNIFTY"},
}

INSTRUMENT_KEY = {
    "NIFTY": "NSE_INDEX|Nifty 50",
    "BANKNIFTY": "NSE_INDEX|Nifty Bank",
    "FINNIFTY": "NSE_INDEX|Nifty Financial Services",
    "MIDCPNIFTY": "NSE_INDEX|Nifty Midcap 50",
}

UPSTOX_OC_URLS = [
    "https://api.upstox.com/v2/option/chain",
    "https://api.upstox.com/v3/option/chain"
]
UPSTOX_CONTRACT_URL = "https://api.upstox.com/v2/option/contract"
UPSTOX_AUTH_URL = "https://api.upstox.com/v2/login/authorization/dialog"
UPSTOX_TOKEN_URL = "https://api.upstox.com/v2/login/authorization/token"

# ─────────────────────────────────────────────
# PAGE CONFIG
# ─────────────────────────────────────────────
st.set_page_config(
    page_title="Raj Pro Options Engine",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown("""
<style>
    [data-testid="stMetric"] {
        background-color: #0d1321;
        padding: 15px;
        border-radius: 8px;
        border-left: 3px solid #2979ff;
    }
    table {
        font-size: 12px;
    }
</style>
""", unsafe_allow_html=True)

# ─────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────
def secrets_ok() -> bool:
    try:
        _ = st.secrets["upstox"]["api_key"]
        _ = st.secrets["upstox"]["api_secret"]
        _ = st.secrets["upstox"]["redirect_uri"]
        return True
    except:
        return False

def upstox_headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}", "Accept": "application/json"}

def build_auth_url(api_key: str, redirect_uri: str) -> str:
    return f"{UPSTOX_AUTH_URL}?response_type=code&client_id={api_key}&redirect_uri={redirect_uri}"

def exchange_code(api_key: str, api_secret: str, redirect_uri: str, code: str) -> tuple:
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
    """Fetch fresh option chain data on every call (NO caching of LTP)

    User requirement: LTP must always be fresh for accurate premium values.
    Expiry_date persistence is handled separately in session state.
    """
    for url in UPSTOX_OC_URLS:
        try:
            r = requests.get(
                url,
                params={
                    "instrument_key": INSTRUMENT_KEY[symbol],
                    "expiry_date": expiry_date,
                },
                headers=upstox_headers(token),
                timeout=15,
            )
            d = r.json()
            if r.status_code == 401:
                return None, "token_expired", url
            if d.get("status") == "success":
                data = d.get("data") or []
                if data:
                    print(f"[DEBUG] Fetched FRESH option chain data from {url}")
                    return data, None, url
        except Exception as e:
            print(f"[DEBUG] Error fetching from {url}: {str(e)}")
            pass

    return None, "Failed to fetch chain", UPSTOX_OC_URLS[-1]

def fetch_historical_candles(token: str, symbol: str, date_str: str) -> tuple:
    """Fetch 1-minute historical candles for a symbol on a specific date
    Used for debugging to understand candle order

    Args:
        token: API access token
        symbol: NIFTY, BANKNIFTY, etc.
        date_str: Date in YYYY-MM-DD format

    Returns:
        (candles_list, error_message)
    """
    try:
        instrument_key = INSTRUMENT_KEY[symbol]
        url = f"https://api.upstox.com/v2/historical-candle/{instrument_key}/1minute/{date_str}/{date_str}"

        print(f"[DEBUG] Fetching 1-minute candles: {url}")

        r = requests.get(
            url,
            headers=upstox_headers(token),
            timeout=15,
        )

        if r.status_code == 401:
            return None, "token_expired"

        d = r.json()

        if d.get("status") == "success" and d.get("data"):
            candles = d.get("data", {}).get("candles", [])

            if isinstance(candles, list) and len(candles) > 0:
                print(f"[DEBUG] ✓ Got {len(candles)} 1-minute candles for {symbol}")
                return candles, None
            else:
                return None, f"No candles in response"

        return None, f"Failed: {d}"
    except Exception as e:
        print(f"[ERROR] 1-minute candles fetch failed: {e}")
        import traceback
        traceback.print_exc()
        return None, str(e)

def fetch_daily_candle(token: str, symbol: str, date_str: str) -> tuple:
    """Fetch DAILY candle for a specific date to get day's opening price

    Args:
        token: API access token
        symbol: NIFTY, BANKNIFTY, etc.
        date_str: Date in YYYY-MM-DD format

    Returns:
        (candle_data, error_message) where candle = [timestamp, open, high, low, close, vol, oi]
    """
    try:
        # Get instrument key for underlying (not options)
        instrument_key = INSTRUMENT_KEY[symbol]

        # Fetch DAILY candle: /historical-candle/{instrument_key}/day/{to_date}/{from_date}
        url = f"https://api.upstox.com/v2/historical-candle/{instrument_key}/day/{date_str}/{date_str}"

        print(f"[DEBUG] Fetching daily candle: {url}")

        r = requests.get(
            url,
            headers=upstox_headers(token),
            timeout=15,
        )

        if r.status_code == 401:
            return None, "token_expired"

        d = r.json()

        if d.get("status") == "success" and d.get("data"):
            candles = d.get("data", {}).get("candles", [])

            if isinstance(candles, list) and len(candles) > 0:
                daily_candle = candles[0]
                print(f"[DEBUG] ✓ Daily candle for {symbol} on {date_str}: {daily_candle}")
                return daily_candle, None
            else:
                print(f"[ERROR] No daily candle data")
                return None, f"No candles in response"

        return None, f"Failed: {d}"
    except Exception as e:
        print(f"[ERROR] Daily candle fetch failed: {e}")
        import traceback
        traceback.print_exc()
        return None, str(e)

def fetch_last_traded_day_opening(token: str, symbol: str, max_days_back: int = 10) -> tuple:
    """Find the LAST TRADED DAY and fetch its DAILY candle to get opening price

    Args:
        token: API access token
        symbol: NIFTY, BANKNIFTY, etc.
        max_days_back: Maximum days to search back (default 10)

    Returns:
        (opening_price, traded_date_str, error_message)
    """
    today = datetime.now()

    # Search backwards for last traded day
    for days_back in range(1, max_days_back + 1):
        search_date = today - timedelta(days=days_back)
        date_str = search_date.strftime("%Y-%m-%d")

        # Skip weekends (Saturday=5, Sunday=6)
        if search_date.weekday() >= 5:
            print(f"[DEBUG] {date_str} is weekend, skipping")
            continue

        daily_candle, error = fetch_daily_candle(token, symbol, date_str)

        if daily_candle and isinstance(daily_candle, list) and len(daily_candle) >= 2:
            opening_price = float(daily_candle[1])  # Index 1 = OPEN
            timestamp = daily_candle[0]
            print(f"[DEBUG] ✓ Found last traded day: {date_str}, Opening: {opening_price:.2f}")
            return opening_price, date_str, None

        print(f"[DEBUG] No daily candle on {date_str}, searching further back...")

    return None, None, f"No traded day found in last {max_days_back} days"

# ─────────────────────────────────────────────
# MAIN APP
# ─────────────────────────────────────────────

def main():
    now = datetime.now(IST)
    mkt = (
        now.weekday() < 5 and
        (9, 15) <= (now.hour, now.minute) <= (15, 30)
    )

    st.title("📊 Raj Pro Options Engine - COMPLETE")
    st.caption(f"{'🟢' if mkt else '🔴'} {now.strftime('%d %b %H:%M IST')} | Upstox API | 100% Pine Script Match")

    # Check secrets
    if not secrets_ok():
        st.error("⚠️ Upstox credentials not configured")
        st.info("""
        **Setup Instructions:**
        1. Go to developer.upstox.com
        2. Create API credentials
        3. Streamlit Cloud → Settings → Secrets → Add:
        ```
        [upstox]
        api_key = "your_key"
        api_secret = "your_secret"
        redirect_uri = "https://yourapp.streamlit.app"
        ```
        """)
        st.stop()

    api_key = st.secrets["upstox"]["api_key"]
    api_secret = st.secrets["upstox"]["api_secret"]
    redirect_uri = st.secrets["upstox"]["redirect_uri"]

    # OAuth
    qp = st.query_params
    auth_code = qp.get("code")
    if auth_code and "access_token" not in st.session_state:
        with st.spinner("Logging in..."):
            token, err = exchange_code(api_key, api_secret, redirect_uri, auth_code)
        if token:
            st.session_state["access_token"] = token
            st.session_state["token_acquired"] = time.time()
            st.query_params.clear()
            st.rerun()
        else:
            st.error(f"Login failed: {err}")
            st.stop()

    # Token expiry
    if "access_token" in st.session_state:
        if time.time() - st.session_state.get("token_acquired", 0) > 86400:
            del st.session_state["access_token"]
            st.rerun()

    # Login
    if "access_token" not in st.session_state:
        auth_url = build_auth_url(api_key, redirect_uri)
        st.markdown(f"""
        <div style='text-align: center; padding: 3rem;'>
            <a href='{auth_url}' style='display: inline-block; background: #2979ff;
               color: white; padding: 15px 40px; border-radius: 8px; text-decoration: none;
               font-weight: bold; font-size: 16px;'>
                🔑 CONNECT WITH UPSTOX
            </a>
        </div>
        """, unsafe_allow_html=True)
        st.stop()

    # Initialize engines and opening premium storage
    if "engines" not in st.session_state:
        st.session_state.engines = {
            "NIFTY": RajProEngine(),
            "BANKNIFTY": RajProEngine(),
            "FINNIFTY": RajProEngine(),
            "MIDCPNIFTY": RajProEngine(),
        }

    # Initialize opening premium storage (persistent across runs)
    if "opening_premiums" not in st.session_state:
        st.session_state.opening_premiums = {
            "NIFTY": {"ce1O": None, "ce2O": None, "ce3O": None, "ce4O": None,
                      "pe1O": None, "pe2O": None, "pe3O": None, "pe4O": None, "date": None},
            "BANKNIFTY": {"ce1O": None, "ce2O": None, "ce3O": None, "ce4O": None,
                          "pe1O": None, "pe2O": None, "pe3O": None, "pe4O": None, "date": None},
            "FINNIFTY": {"ce1O": None, "ce2O": None, "ce3O": None, "ce4O": None,
                         "pe1O": None, "pe2O": None, "pe3O": None, "pe4O": None, "date": None},
            "MIDCPNIFTY": {"ce1O": None, "ce2O": None, "ce3O": None, "ce4O": None,
                           "pe1O": None, "pe2O": None, "pe3O": None, "pe4O": None, "date": None},
        }

    # Sidebar
    with st.sidebar:
        st.markdown("### ⚙️ Settings")

        # Debug toggle
        show_debug = st.checkbox("🐛 Show Debug Info", value=False)

        if st.button("🔓 Logout", width='stretch'):
            for k in list(st.session_state.keys()):
                del st.session_state[k]
            st.rerun()

        if show_debug:
            st.markdown("### 📊 Debug Info")
            st.caption("Data structure and extraction diagnostics")

        # Log status
        st.markdown("---")
        st.markdown("### 📝 Debug Logs")
        st.info("Debug logs captured in real-time below")

    # Fetch data for all symbols
    access_token = st.session_state["access_token"]
    all_signals = {}
    debug_info = {}

    # Initialize per-instrument expiry storage in session state
    if "instrument_expiries" not in st.session_state:
        st.session_state.instrument_expiries = {}

    for symbol_key in ["NIFTY", "BANKNIFTY", "FINNIFTY", "MIDCPNIFTY"]:
        config = STRIKE_CONFIG[symbol_key]

        # Fetch available expiry dates for this instrument
        try:
            expiry_dates, exp_err = fetch_expiry_dates(access_token, symbol_key)
            if not expiry_dates:
                print(f"[DEBUG] No expiry dates for {symbol_key}")
                all_signals[symbol_key] = None
                continue
        except:
            print(f"[DEBUG] Error fetching expiry dates for {symbol_key}")
            all_signals[symbol_key] = None
            continue

        # Get or set default expiry for this instrument
        if symbol_key not in st.session_state.instrument_expiries:
            st.session_state.instrument_expiries[symbol_key] = expiry_dates[0]

        selected = st.session_state.instrument_expiries[symbol_key]

        # Fetch chain
        data, chain_err, _ = fetch_chain(access_token, symbol_key, selected)
        if chain_err == "token_expired":
            del st.session_state["access_token"]
            st.rerun()

        if chain_err or not data:
            all_signals[symbol_key] = None
            continue

        # Extract spot price and opening prices
        spot = None
        opening_price = None

        try:
            for row in data:
                sp = row.get("underlying_spot_price")
                if sp:
                    spot = float(sp)
                    break

            # Get TODAY'S opening price from 1-minute chart (matching Pine Script logic)
            # When market is CLOSED: Fetch historical candles to get today's opening
            # When market is OPEN: Use first 1-minute candle at market open (09:15)
            opening_price = spot  # Default fallback
            try:
                is_market_open = (
                    now.weekday() < 5 and
                    (9, 15) <= (now.hour, now.minute) <= (15, 30)
                )

                if not is_market_open:
                    # Market CLOSED: Get opening price from FIRST 1-MINUTE CANDLE (09:15 market open)
                    print(f"[DEBUG] Market closed, fetching first 1-minute candle (09:15 market open)...")

                    search_date = datetime.now() - timedelta(days=1)
                    date_str = search_date.strftime("%Y-%m-%d")
                    if search_date.weekday() >= 5:  # If weekend, go back further
                        for days_back in range(1, 10):
                            search_date = datetime.now() - timedelta(days=days_back)
                            if search_date.weekday() < 5:
                                date_str = search_date.strftime("%Y-%m-%d")
                                break

                    # Fetch 1-minute candles for last traded day
                    candles_1min, err_1min = fetch_historical_candles(access_token, symbol_key, date_str)

                    opening_price_1min = None
                    if candles_1min and isinstance(candles_1min, list) and len(candles_1min) > 0:
                        # Candles are in REVERSE chronological order: [0]=latest (15:30), [-1]=first (09:15)
                        first_candle = candles_1min[-1]  # Get the 09:15 (market open) candle
                        if isinstance(first_candle, list) and len(first_candle) >= 2:
                            opening_price_1min = float(first_candle[1])  # Index [1] = OPEN price
                            print(f"[DEBUG] ✓ First 1-min candle (09:15): {first_candle[0]}")
                            print(f"[DEBUG] ✓ Opening from 1-MIN: {opening_price_1min:.2f}")
                        elif isinstance(first_candle, dict) and "open" in first_candle:
                            opening_price_1min = float(first_candle.get("open", 0))
                            print(f"[DEBUG] ✓ Opening from 1-MIN (dict): {opening_price_1min:.2f}")

                    # Fallback: Also fetch daily candle as backup
                    if not opening_price_1min:
                        print(f"[DEBUG] 1-MIN candles not available, trying daily candle...")
                        opening_price_daily, traded_date, candle_err = fetch_last_traded_day_opening(access_token, symbol_key)
                        if opening_price_daily:
                            opening_price_1min = opening_price_daily
                            print(f"[DEBUG] ✓ Opening from DAILY: {opening_price_daily:.2f}")

                    opening_price = opening_price_1min if opening_price_1min else spot

                    if opening_price and opening_price > 0:
                        print(f"[DEBUG] ✓✓ SUCCESS! Opening price (from 1-min): {opening_price:.2f}")
                    else:
                        opening_price = spot
                        print(f"[DEBUG] ⚠️ Using spot: {spot:.2f}")
                else:
                    # Market OPEN: Use underlying_open_price from chain (today's opening at 09:15)
                    if data:
                        opening_price = float(data[0].get("underlying_open_price") or 0)
                        if opening_price <= 0:
                            opening_price = spot
                            print(f"[DEBUG] ⚠️ Opening price not available, using spot: {spot:.2f}")
                        else:
                            print(f"[DEBUG] ✓ TODAY'S opening price (market open): {opening_price:.2f}")

            except Exception as e:
                print(f"[ERROR] Error getting opening price: {str(e)}")
                import traceback
                traceback.print_exc()
                opening_price = spot

            if not spot or spot <= 0:
                print(f"[ERROR] Could not extract spot price for {symbol_key}")
                all_signals[symbol_key] = None
                continue

            if not opening_price or opening_price <= 0:
                opening_price = spot  # Fallback to spot if opening not available
                print(f"[DEBUG] Opening price not available, using spot: {spot:.2f}")

        except Exception as e:
            print(f"[ERROR] Failed to extract prices for {symbol_key}: {e}")
            all_signals[symbol_key] = None
            continue

        # ===== DEBUG: Print Upstox data structure =====
        print(f"\n{'='*80}")
        print(f"[DATA-DUMP] {symbol_key} - Received {len(data)} rows from Upstox")
        print(f"[DATA-DUMP] Spot: {spot:.2f}, Opening: {opening_price:.2f}")
        if data:
            print(f"[DATA-DUMP] First row keys: {list(data[0].keys())}")
            print(f"[DATA-DUMP] underlying_open_price: {data[0].get('underlying_open_price')}")
            print(f"[DATA-DUMP] underlying_spot_price: {data[0].get('underlying_spot_price')}")
            print(f"[DATA-DUMP] underlying_close_price: {data[0].get('underlying_close_price')}")
            import json
            print(f"[DATA-DUMP] First row JSON (truncated):")
            print(json.dumps(data[0], indent=2, default=str)[:800])
        print(f"{'='*80}\n")
        # ===== END DEBUG =====

        # Process through complete engine
        try:
            engine = st.session_state.engines[symbol_key]

            # Pass opening premiums from session state
            opening_prems = st.session_state.opening_premiums.get(symbol_key, {})
            print(f"\n[DEBUG] {symbol_key} - Loading opening premiums from session state:")
            print(f"[DEBUG] ce1O={opening_prems.get('ce1O')}, ce2O={opening_prems.get('ce2O')}, pe1O={opening_prems.get('pe1O')}, pe2O={opening_prems.get('pe2O')}, date={opening_prems.get('date')}")
            print(f"[DEBUG] Today's date: {str(datetime.now().date())}")

            signal = engine.process(
                chain_data=data,
                underlying_price=spot,
                opening_price=opening_price,
                strike_gap=config["gap"],
                symbol=symbol_key,
                expiry_date=selected,
                opening_premiums=opening_prems,  # NEW: pass persistent opening premiums
            )

            # Update opening premiums in session state (for next run)
            st.session_state.opening_premiums[symbol_key] = {
                "ce1O": float(engine.ce1O) if engine.ce1O else None,
                "ce2O": float(engine.ce2O) if engine.ce2O else None,
                "ce3O": float(engine.ce3O) if engine.ce3O else None,
                "ce4O": float(engine.ce4O) if engine.ce4O else None,
                "pe1O": float(engine.pe1O) if engine.pe1O else None,
                "pe2O": float(engine.pe2O) if engine.pe2O else None,
                "pe3O": float(engine.pe3O) if engine.pe3O else None,
                "pe4O": float(engine.pe4O) if engine.pe4O else None,
                "date": str(datetime.now().date()),
            }
            print(f"[DEBUG] {symbol_key} - Updated session state with opening premiums:")
            print(f"[DEBUG] Stored: ce1O={st.session_state.opening_premiums[symbol_key]['ce1O']}, pe1O={st.session_state.opening_premiums[symbol_key]['pe1O']}, date={st.session_state.opening_premiums[symbol_key]['date']}")

            all_signals[symbol_key] = (signal, spot, config, selected, opening_price)
            print(f"[DEBUG] {symbol_key} processed successfully:")
            print(f"[DEBUG]   Dominance: {signal.dominance:+.4f}")
            print(f"[DEBUG]   Momentum: {signal.momentum:+.4f}")
            print(f"[DEBUG]   CE Erosion: {signal.call_erosion:+.4f}")
            print(f"[DEBUG]   PE Erosion: {signal.put_erosion:+.4f}")
            print(f"[DEBUG]   Volatility: {signal.volatility:.4f}")
        except Exception as e:
            print(f"[ERROR] Engine failed for {symbol_key}: {str(e)}")
            import traceback
            traceback.print_exc()
            all_signals[symbol_key] = None

    # Display professional table (matching Pine Script indicator)
    st.subheader("📊 Raj Pro Options Analysis Table")

    # Build table rows with per-instrument expiry selectors
    table_rows = []
    for symbol_key in ["NIFTY", "BANKNIFTY", "FINNIFTY", "MIDCPNIFTY"]:
        # Display expiry selector for this instrument
        try:
            expiry_dates, _ = fetch_expiry_dates(access_token, symbol_key)
            if expiry_dates:
                col1, col2 = st.columns([3, 1])

                with col1:
                    st.markdown(f"#### 📊 {STRIKE_CONFIG[symbol_key]['name']}")
                    st.markdown(f"**📅 Expiry:**")

                with col2:
                    selected = st.selectbox(
                        "Select expiry",
                        options=expiry_dates,
                        index=expiry_dates.index(st.session_state.instrument_expiries.get(symbol_key, expiry_dates[0])) if st.session_state.instrument_expiries.get(symbol_key) in expiry_dates else 0,
                        key=f"expiry_{symbol_key}",
                        label_visibility="collapsed"
                    )
                    if selected != st.session_state.instrument_expiries.get(symbol_key):
                        st.session_state.instrument_expiries[symbol_key] = selected
                        st.rerun()
        except:
            pass

        if symbol_key in all_signals and all_signals[symbol_key]:
            try:
                signal, spot, config, expiry, opening_price = all_signals[symbol_key]

                signal_emoji = "🟢" if signal.color == "green" else "🔴" if signal.color == "red" else "🟡"

                # Build premium display
                ce1 = f"{signal.premiums.get('ce1', 0):.2f}" if signal.premiums.get('ce1', 0) > 0 else "—"
                ce2 = f"{signal.premiums.get('ce2', 0):.2f}" if signal.premiums.get('ce2', 0) > 0 else "—"
                ce3 = f"{signal.premiums.get('ce3', 0):.2f}" if signal.premiums.get('ce3', 0) > 0 else "—"
                ce4 = f"{signal.premiums.get('ce4', 0):.2f}" if signal.premiums.get('ce4', 0) > 0 else "—"
                pe1 = f"{signal.premiums.get('pe1', 0):.2f}" if signal.premiums.get('pe1', 0) > 0 else "—"
                pe2 = f"{signal.premiums.get('pe2', 0):.2f}" if signal.premiums.get('pe2', 0) > 0 else "—"
                pe3 = f"{signal.premiums.get('pe3', 0):.2f}" if signal.premiums.get('pe3', 0) > 0 else "—"
                pe4 = f"{signal.premiums.get('pe4', 0):.2f}" if signal.premiums.get('pe4', 0) > 0 else "—"

                # Calculate strike values for summary display (use current_atm based on live price)
                gap = config["gap"]
                ce1_strike = signal.current_atm + gap
                ce2_strike = signal.current_atm + 2 * gap
                pe1_strike = signal.current_atm - gap
                pe2_strike = signal.current_atm - 2 * gap

                table_rows.append({
                    "Index": config["name"],
                    "Signal": f"{signal_emoji} {signal.name}",
                    "Confidence": f"{signal.confidence:.0%}",
                    "Dominance": f"{signal.dominance:+.4f}",
                    "Momentum": f"{signal.momentum:+.4f}",
                    "Volatility": f"{signal.volatility:.4f}",
                    "Trend": signal.trend,
                    "Spot": f"({signal.current_atm}|{signal.pcr:.2f}) ₹{spot:,.2f}",
                    "CE Ero.": f"{signal.call_erosion:+.4f}",
                    "PE Ero.": f"{signal.put_erosion:+.4f}",
                    "Gamma Score": f"{signal.gamma_score:.1f}",
                    "Spike Signal": signal.spike_signal,
                    "Inst Signal": signal.inst_signal,
                    "Bull Bars": signal.bull_bars,
                    "Bear Bars": signal.bear_bars,
                })
            except Exception as e:
                print(f"[ERROR] Table row build failed for {symbol_key}: {str(e)}")
                print(f"[ERROR] Signal attributes: {dir(signal) if 'signal' in locals() else 'N/A'}")
                table_rows.append({
                    "Index": config["name"] if 'config' in locals() else symbol_key,
                    "Signal": "ERROR",
                    "Confidence": "—",
                    "Dominance": "—",
                    "Momentum": "—",
                    "Volatility": "—",
                    "Trend": "—",
                    "Spot": f"Error: {str(e)}",
                    "CE Ero.": "—",
                    "PE Ero.": "—",
                    "Gamma Score": "—",
                    "Spike Signal": "—",
                    "Inst Signal": "—",
                    "Bull Bars": "—",
                    "Bear Bars": "—",
                })
        else:
            table_rows.append({
                "Index": STRIKE_CONFIG[symbol_key]["name"],
                "Signal": "N/A",
                "Confidence": "—",
                "Dominance": "—",
                "Momentum": "—",
                "Volatility": "—",
                "Trend": "—",
                "Spot": "—",
                "CE Ero.": "—",
                "PE Ero.": "—",
                "Gamma Score": "—",
                "Spike Signal": "—",
                "Inst Signal": "—",
                "Bull Bars": "—",
                "Bear Bars": "—",
            })

    # Display table with PyArrow safe conversion
    df = pd.DataFrame(table_rows)

    # Convert all columns to strings for PyArrow compatibility (handles mixed "—" and numeric values)
    df = df.astype(str)

    st.dataframe(df, width='stretch', height=300)

    # ─────────────────────────────────────────────
    # PUT-CALL RATIO (PCR) TABLE
    # ─────────────────────────────────────────────
    st.subheader("📊 Put-Call Ratio (PCR) Summary")

    pcr_rows = []
    for symbol_key in ["NIFTY", "BANKNIFTY", "FINNIFTY", "MIDCPNIFTY"]:
        if symbol_key in all_signals and all_signals[symbol_key]:
            signal, spot, config, expiry, opening_price = all_signals[symbol_key]
            gap = config["gap"]

            # Calculate strike values based on CURRENT ATM (live spot price)
            atm = signal.current_atm
            ce1 = atm + gap
            ce2 = atm + 2 * gap
            ce3 = atm + 3 * gap
            ce4 = atm + 4 * gap
            pe1 = atm - gap
            pe2 = atm - 2 * gap
            pe3 = atm - 3 * gap
            pe4 = atm - 4 * gap

            # Calculate deltas for gamma zone check (0.30-0.35)
            from engine_exact import norm_cdf
            import math

            def calc_delta(S, K, T, sigma, is_call=True):
                if S <= 0 or K <= 0 or T <= 0 or sigma <= 0:
                    return 0.5
                try:
                    d1 = (math.log(S / K) + 0.5 * sigma * sigma * T) / (sigma * math.sqrt(T))
                    delta = norm_cdf(d1)
                    return delta if is_call else abs(1.0 - delta)
                except:
                    return 0.5

            # Calculate days left and IV for delta calc
            from datetime import datetime
            try:
                expiry = datetime.strptime(expiry, "%Y-%m-%d")
                days_left = max((expiry - datetime.now()).total_seconds() / 86400.0, 0.5)
                T_yr = days_left / 365.0
            except:
                T_yr = 0.01

            # Estimate IV from straddle if available
            sigma = 0.20  # Default
            if signal.premiums.get('ce1', 0) > 0 and signal.premiums.get('pe1', 0) > 0:
                straddle = signal.premiums.get('ce1', 0) + signal.premiums.get('pe1', 0)
                sqrt_t = math.sqrt(T_yr)
                sqrt_2_pi = 0.7979
                if spot > 0:
                    sigma = straddle / (spot * sqrt_t * sqrt_2_pi) if (spot * sqrt_t * sqrt_2_pi) > 0 else 0.20
                    sigma = max(0.05, min(sigma, 2.0))

            def get_gamma_marker(delta, opt_type):
                if 0.30 <= delta <= 0.35:
                    return " 🔺G" if opt_type == "call" else " 🔻G"
                return ""

            # Calculate gamma markers
            ce1_gamma = get_gamma_marker(calc_delta(spot, ce1, T_yr, sigma, True), "call")
            ce2_gamma = get_gamma_marker(calc_delta(spot, ce2, T_yr, sigma, True), "call")
            ce3_gamma = get_gamma_marker(calc_delta(spot, ce3, T_yr, sigma, True), "call")
            ce4_gamma = get_gamma_marker(calc_delta(spot, ce4, T_yr, sigma, True), "call")
            pe1_gamma = get_gamma_marker(calc_delta(spot, pe1, T_yr, sigma, False), "put")
            pe2_gamma = get_gamma_marker(calc_delta(spot, pe2, T_yr, sigma, False), "put")
            pe3_gamma = get_gamma_marker(calc_delta(spot, pe3, T_yr, sigma, False), "put")
            pe4_gamma = get_gamma_marker(calc_delta(spot, pe4, T_yr, sigma, False), "put")

            pcr_rows.append({
                "Index": config["name"],
                "PE4": f"{pe4}|{signal.pcr_pe4:.2f}{pe4_gamma}",
                "PE3": f"{pe3}|{signal.pcr_pe3:.2f}{pe3_gamma}",
                "PE2": f"{pe2}|{signal.pcr_pe2:.2f}{pe2_gamma}",
                "PE1": f"{pe1}|{signal.pcr_pe1:.2f}{pe1_gamma}",
                "ATM": f"{atm}|{signal.pcr:.2f}",
                "CE1": f"{ce1}|{signal.pcr_ce1:.2f}{ce1_gamma}",
                "CE2": f"{ce2}|{signal.pcr_ce2:.2f}{ce2_gamma}",
                "CE3": f"{ce3}|{signal.pcr_ce3:.2f}{ce3_gamma}",
                "CE4": f"{ce4}|{signal.pcr_ce4:.2f}{ce4_gamma}",
                "_pe4_val": signal.pcr_pe4,
                "_pe3_val": signal.pcr_pe3,
                "_pe2_val": signal.pcr_pe2,
                "_pe1_val": signal.pcr_pe1,
                "_ce1_val": signal.pcr_ce1,
                "_ce2_val": signal.pcr_ce2,
                "_ce3_val": signal.pcr_ce3,
                "_ce4_val": signal.pcr_ce4,
            })
        else:
            pcr_rows.append({
                "Index": STRIKE_CONFIG[symbol_key]["name"],
                "PE4": "—",
                "PE3": "—",
                "PE2": "—",
                "PE1": "—",
                "ATM": "—",
                "CE1": "—",
                "CE2": "—",
                "CE3": "—",
                "CE4": "—",
                "_pe4_val": 0,
                "_pe3_val": 0,
                "_pe2_val": 0,
                "_pe1_val": 0,
                "_ce1_val": 0,
                "_ce2_val": 0,
                "_ce3_val": 0,
                "_ce4_val": 0,
            })

    pcr_df = pd.DataFrame(pcr_rows)

    # Remove helper columns
    display_df = pcr_df.drop(columns=['_ce1_val', '_ce2_val', '_ce3_val', '_ce4_val', '_pe1_val', '_pe2_val', '_pe3_val', '_pe4_val']).copy()

    # Style the dataframe - highlight threshold breakout levels
    def style_pcr_row(row):
        styles = [''] * len(row)

        pe_cols = ['PE4', 'PE3', 'PE2', 'PE1']
        ce_cols = ['CE1', 'CE2', 'CE3', 'CE4']

        pe_gt1 = {}  # PE values > 1
        ce_lt1 = {}  # CE values < 1

        # Collect PE > 1 values
        for col in pe_cols:
            if col in row.index:
                val = row[col]
                if '|' in str(val):
                    try:
                        pcr_val = float(str(val).split('|')[1])
                        if pcr_val > 1:
                            pe_gt1[col] = pcr_val
                    except:
                        pass

        # Collect CE < 1 values
        for col in ce_cols:
            if col in row.index:
                val = row[col]
                if '|' in str(val):
                    try:
                        pcr_val = float(str(val).split('|')[1])
                        if pcr_val < 1:
                            ce_lt1[col] = pcr_val
                    except:
                        pass

        # PE side GREEN: Among PCR > 1, highlight the SMALLEST value (closest to 1 threshold)
        if pe_gt1:
            pe_min_col = min(pe_gt1, key=pe_gt1.get)  # Column with minimum PCR > 1
            for i, col in enumerate(row.index):
                if col == pe_min_col:
                    styles[i] = 'background-color: rgba(0, 255, 0, 0.5); color: black; font-weight: bold'

        # CE side RED: Among PCR < 1, highlight the LARGEST value (closest to 1 threshold)
        if ce_lt1:
            ce_max_col = max(ce_lt1, key=ce_lt1.get)  # Column with maximum PCR < 1
            for i, col in enumerate(row.index):
                if col == ce_max_col:
                    styles[i] = 'background-color: rgba(255, 0, 0, 0.5); color: white; font-weight: bold'

        return styles

    styler = display_df.style.apply(style_pcr_row, axis=1)
    st.dataframe(styler, width='stretch', height=200)

    # ─────────────────────────────────────────────
    # COMPLETE RAJ PRO TABLE (Matching Pine Script)
    # ─────────────────────────────────────────────
    st.subheader("📋 Detailed Analysis - Complete Table")

    tabs = st.tabs(["NIFTY", "BANKNIFTY", "FINNIFTY", "MIDCPNIFTY"])

    for idx, symbol_key in enumerate(["NIFTY", "BANKNIFTY", "FINNIFTY", "MIDCPNIFTY"]):
        with tabs[idx]:
            if symbol_key in all_signals and all_signals[symbol_key]:
                signal, spot, config, expiry, opening_price = all_signals[symbol_key]
                # Use opening price for ATM calculation (more accurate for closed market)
                atm = int(config["gap"] * round(opening_price / config["gap"]))

                try:
                    # Create and display complete table
                    table = RajProTable(
                        signal=signal,
                        spot=spot,
                        config=config,
                        expiry_date=expiry,
                        atm_strike=atm,
                        strike_gap=config["gap"],
                        opening_price=opening_price,
                    )
                    table.display_streamlit_table()

                except Exception as e:
                    st.error(f"Error displaying table: {e}")
                    # Fallback to simple metrics
                    col1, col2, col3, col4 = st.columns(4)
                    with col1:
                        st.metric("Signal", f"{'🟢' if signal.color == 'green' else '🔴' if signal.color == 'red' else '🟡'} {signal.name}", f"{signal.confidence:.0%}")
                    with col2:
                        st.metric("Dominance", f"{signal.dominance:+.4f}")
                    with col3:
                        st.metric("Momentum", f"{signal.momentum:+.4f}")
                    with col4:
                        st.metric("Volatility", f"{signal.volatility:.4f}")
            else:
                st.info(f"⏳ Loading data for {config['name']}...")

    # ─────────────────────────────────────────────
    # GAMMA ANALYSIS TABLE (Pine Script Delta/Gamma)
    # ─────────────────────────────────────────────
    st.subheader("📊 Gamma Analysis & Delta Table")

    gamma_cols = st.columns(4)

    for idx, symbol_key in enumerate(["NIFTY", "BANKNIFTY", "FINNIFTY", "MIDCPNIFTY"]):
        with gamma_cols[idx]:
            if symbol_key in all_signals and all_signals[symbol_key]:
                signal, spot, config, expiry, opening_price = all_signals[symbol_key]

                try:
                    # Initialize gamma analyzer
                    gamma = GammaAnalyzer(expiry)

                    # Get CE and PE premiums
                    ce1_prem = signal.premiums.get("ce1", 0)
                    pe1_prem = signal.premiums.get("pe1", 0)

                    # Calculate all deltas (use opening price for ATM when market closed)
                    atm = int(config["gap"] * round(opening_price / config["gap"]))
                    deltas = gamma.calculate_deltas(
                        spot=spot,
                        atm_strike=atm,
                        strike_gap=config["gap"],
                        ce_premium=ce1_prem,
                        pe_premium=pe1_prem,
                    )

                    # Calculate gamma score
                    g_score = gamma.gamma_score(
                        deltas["ce_deltas"],
                        deltas["pe_deltas"],
                        signal.dominance
                    )

                    # Display metrics
                    st.metric("Gamma Score", f"{g_score:.1f}", delta=f"IV: {deltas['sigma']*100:.1f}%")

                    # Display delta table
                    with st.expander(f"🔺 {symbol_key} Delta Analysis", expanded=False):
                        delta_data = {
                            "Strike": ["CE1", "CE2", "CE3", "CE4", "PE1", "PE2", "PE3", "PE4"],
                            "Delta": [
                                f"{deltas['ce_deltas'].get(1, 0):.3f}{deltas['ce_markers'].get(1, '')}",
                                f"{deltas['ce_deltas'].get(2, 0):.3f}{deltas['ce_markers'].get(2, '')}",
                                f"{deltas['ce_deltas'].get(3, 0):.3f}{deltas['ce_markers'].get(3, '')}",
                                f"{deltas['ce_deltas'].get(4, 0):.3f}{deltas['ce_markers'].get(4, '')}",
                                f"{deltas['pe_deltas'].get(1, 0):.3f}{deltas['pe_markers'].get(1, '')}",
                                f"{deltas['pe_deltas'].get(2, 0):.3f}{deltas['pe_markers'].get(2, '')}",
                                f"{deltas['pe_deltas'].get(3, 0):.3f}{deltas['pe_markers'].get(3, '')}",
                                f"{deltas['pe_deltas'].get(4, 0):.3f}{deltas['pe_markers'].get(4, '')}",
                            ],
                        }

                        delta_df = pd.DataFrame(delta_data)
                        st.dataframe(delta_df, hide_index=True, width='stretch')

                        st.caption(f"IV: {deltas['sigma']*100:.1f}% | T: {deltas['days_left']:.1f}d | 🔺G/🔻G = Max Gamma Zone (Δ 0.30-0.35)")

                except Exception as e:
                    st.warning(f"Could not calculate gamma: {e}")
            else:
                st.info(f"⏳ No data for {config['name']}")

    # ─────────────────────────────────────────────
    # DEBUG LOGS DISPLAY (from session state)
    # ─────────────────────────────────────────────
    st.markdown("---")
    st.subheader("🔍 Debug Logs & Data Structure")

    with st.expander("📊 View Captured Logs", expanded=False):
        if 'debug_logs' in st.session_state and st.session_state.debug_logs:
            log_content = ''.join(st.session_state.debug_logs)

            # Split by sections
            critical_idx = log_content.find('[CRITICAL]')
            data_dump_idx = log_content.find('[DATA-DUMP]')
            debug_idx = log_content.find('[DEBUG]')

            # Show DATA-DUMP section (Upstox structure)
            if data_dump_idx != -1:
                st.markdown("#### 📤 [DATA-DUMP] Received Data")
                data_end = log_content.find('\n[', data_dump_idx + 1)
                if data_end == -1:
                    data_end = len(log_content)
                data_section = log_content[data_dump_idx:data_end]
                st.code(data_section[:2000], language="text")

            # Show all DEBUG lines (extraction details)
            if debug_idx != -1:
                st.markdown("#### 🐛 [DEBUG] Extraction & Calculation Details")
                debug_lines = [line for line in log_content.split('\n') if '[DEBUG]' in line]
                if debug_lines:
                    st.code('\n'.join(debug_lines), language="text")

            st.success(f"✅ Total log lines: {len(st.session_state.debug_logs)}")
        else:
            st.warning("⏳ Logs not yet captured. API data being fetched...")

    # Manual refresh button
    st.markdown("---")
    if st.button("🔄 Refresh Data (Manual)", width='stretch'):
        st.rerun()


if __name__ == "__main__":
    main()
