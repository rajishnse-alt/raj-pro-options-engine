"""
Raj Pro Options Engine - Complete App
Matches Pine Script indicator 100%
"""

import streamlit as st
import requests
import time
import pandas as pd
from datetime import datetime
import pytz
import sys
from io import StringIO
from pathlib import Path

from engine_exact import RajProEngine

# ─────────────────────────────────────────────
# LOG CAPTURE SETUP - Auto-save debug output
# ─────────────────────────────────────────────
LOG_DIR = Path("logs")
LOG_DIR.mkdir(exist_ok=True)

# Create a log file for this session
session_timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
SESSION_LOG_FILE = LOG_DIR / f"upstox_data_dump_{session_timestamp}.log"

class DualWriter:
    """Write to both console and file"""
    def __init__(self, file_path):
        self.file = open(file_path, 'w')
        self.console = sys.stdout

    def write(self, message):
        self.console.write(message)
        self.file.write(message)
        self.file.flush()

    def flush(self):
        self.console.flush()
        self.file.flush()

    def close(self):
        self.file.close()

# Start capturing output
sys.stdout = DualWriter(SESSION_LOG_FILE)

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
    cache_key = f"oc_{symbol}_{expiry_date}"
    time_key = f"oc_time_{symbol}_{expiry_date}"
    now = time.time()

    if (cache_key in st.session_state and
            time_key in st.session_state and
            now - st.session_state[time_key] < 180):
        return st.session_state[cache_key], None, "cached"

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
                    st.session_state[cache_key] = data
                    st.session_state[time_key] = now
                    return data, None, url
        except:
            pass

    return None, "Failed to fetch chain", UPSTOX_OC_URLS[-1]

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

    # Initialize engines
    if "engines" not in st.session_state:
        st.session_state.engines = {
            "NIFTY": RajProEngine(),
            "BANKNIFTY": RajProEngine(),
            "FINNIFTY": RajProEngine(),
            "MIDCPNIFTY": RajProEngine(),
        }

    # Sidebar
    with st.sidebar:
        st.markdown("### ⚙️ Settings")

        # Debug toggle
        show_debug = st.checkbox("🐛 Show Debug Info", value=False)

        if st.button("🔓 Logout", use_container_width=True):
            for k in list(st.session_state.keys()):
                del st.session_state[k]
            st.rerun()

        if show_debug:
            st.markdown("### 📊 Debug Info")
            st.caption("Data structure and extraction diagnostics")

        # Log status
        st.markdown("---")
        st.markdown("### 📝 Debug Logs")
        st.caption(f"Auto-saving to: `logs/upstox_data_dump_{session_timestamp}.log`")
        st.info("""
        **View logs in GitHub:**
        1. Go to repo logs/ folder
        2. Open latest file
        3. Search for `[CRITICAL]` or `[DATA-DUMP]`

        **Or run locally:**
        ```bash
        python log_viewer.py latest
        ```
        """)

    # Fetch data for all symbols
    access_token = st.session_state["access_token"]
    all_signals = {}
    debug_info = {}

    for symbol_key in ["NIFTY", "BANKNIFTY", "FINNIFTY", "MIDCPNIFTY"]:
        config = STRIKE_CONFIG[symbol_key]

        # Fetch expiry
        expiry_dates, exp_err = fetch_expiry_dates(access_token, symbol_key)
        if exp_err == "token_expired":
            del st.session_state["access_token"]
            st.rerun()

        if exp_err or not expiry_dates:
            all_signals[symbol_key] = None
            continue

        # Store/get selected expiry
        if f"exp_{symbol_key}" not in st.session_state:
            st.session_state[f"exp_{symbol_key}"] = expiry_dates[0]

        selected = st.session_state[f"exp_{symbol_key}"]

        # Fetch chain
        data, chain_err, _ = fetch_chain(access_token, symbol_key, selected)
        if chain_err == "token_expired":
            del st.session_state["access_token"]
            st.rerun()

        if chain_err or not data:
            all_signals[symbol_key] = None
            continue

        # Extract spot price
        spot = None
        for row in data:
            sp = row.get("underlying_spot_price")
            if sp:
                spot = float(sp)
                break

        if not spot:
            all_signals[symbol_key] = None
            continue

        # ===== DEBUG: Print Upstox data structure =====
        print(f"\n{'='*80}")
        print(f"[DATA-DUMP] {symbol_key} - Received {len(data)} rows from Upstox")
        if data:
            print(f"[DATA-DUMP] First row keys: {list(data[0].keys())}")
            import json
            print(f"[DATA-DUMP] First row JSON (truncated):")
            print(json.dumps(data[0], indent=2, default=str)[:800])
        print(f"{'='*80}\n")
        # ===== END DEBUG =====

        # Process through complete engine
        engine = st.session_state.engines[symbol_key]
        signal = engine.process(
            chain_data=data,
            underlying_price=spot,
            strike_gap=config["gap"],
            symbol=symbol_key,
            expiry_date=selected,
        )

        all_signals[symbol_key] = (signal, spot, config, selected)

    # Display professional table (matching Pine Script indicator)
    st.subheader("📊 Raj Pro Options Analysis Table")

    # Build table rows
    table_rows = []
    for symbol_key in ["NIFTY", "BANKNIFTY", "FINNIFTY", "MIDCPNIFTY"]:
        if symbol_key in all_signals and all_signals[symbol_key]:
            signal, spot, config, expiry = all_signals[symbol_key]

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

            table_rows.append({
                "Index": config["name"],
                "Signal": f"{signal_emoji} {signal.name}",
                "Confidence": f"{signal.confidence:.0%}",
                "Dominance": f"{signal.dominance:+.4f}",
                "Momentum": f"{signal.momentum:+.4f}",
                "Volatility": f"{signal.volatility:.4f}",
                "Trend": signal.trend,
                "Spot": f"₹{spot:,.2f}",
                "CE Ero.": f"{signal.call_erosion:+.4f}",
                "PE Ero.": f"{signal.put_erosion:+.4f}",
                "Gamma Score": f"{signal.gamma_score:.1f}",
                "Spike Signal": signal.spike_signal,
                "Inst Signal": signal.inst_signal,
                "Bull Bars": signal.bull_bars,
                "Bear Bars": signal.bear_bars,
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

    # Display table
    df = pd.DataFrame(table_rows)
    st.dataframe(df, use_container_width=True, height=300)

    # Detailed view for each symbol
    st.subheader("📋 Detailed Analysis")

    tabs = st.tabs(["NIFTY", "BANKNIFTY", "FINNIFTY", "MIDCPNIFTY"])

    for idx, symbol_key in enumerate(["NIFTY", "BANKNIFTY", "FINNIFTY", "MIDCPNIFTY"]):
        with tabs[idx]:
            if symbol_key in all_signals and all_signals[symbol_key]:
                signal, spot, config, expiry = all_signals[symbol_key]

                col1, col2, col3, col4 = st.columns(4)
                with col1:
                    st.metric("Signal", f"{'🟢' if signal.color == 'green' else '🔴' if signal.color == 'red' else '🟡'} {signal.name}", f"{signal.confidence:.0%}")
                with col2:
                    st.metric("Dominance", f"{signal.dominance:+.4f}")
                with col3:
                    st.metric("Momentum", f"{signal.momentum:+.4f}")
                with col4:
                    st.metric("Volatility", f"{signal.volatility:.4f}")

                st.markdown(f"""
                **Market Data:**
                - Spot: ₹{spot:,.2f}
                - CE Erosion: {signal.call_erosion:+.4f}
                - PE Erosion: {signal.put_erosion:+.4f}
                - Gamma Score: {signal.gamma_score:.1f}
                - Bull Bars: {signal.bull_bars} | Bear Bars: {signal.bear_bars}

                **Signals:**
                - Spike Signal: {signal.spike_signal}
                - Institutional: {signal.inst_signal}
                - Trend: {signal.trend}

                **Confluence Scores:**
                - CE Spike Score: {signal.ce_spike_score:.2f}
                - PE Spike Score: {signal.pe_spike_score:.2f}
                - Score Diff: {signal.score_diff:+.2f}
                """)
            else:
                st.info(f"⏳ Loading data for {config['name']}...")

    # Auto refresh
    time.sleep(180)
    st.rerun()


if __name__ == "__main__":
    main()
