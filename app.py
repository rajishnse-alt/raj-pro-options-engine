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
from gamma_analysis import GammaAnalyzer
from complete_table import RajProTable

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

        # ===== EXPIRY SELECTOR =====
        st.markdown("### 📅 Expiry Selection")

        # Fetch expiry dates for first symbol (NIFTY)
        expiry_dates = None
        try:
            from datetime import datetime as dt
            exp_dates, exp_err = fetch_expiry_dates(access_token, "NIFTY")
            if exp_dates:
                expiry_dates = exp_dates
                if "selected_expiry" not in st.session_state:
                    st.session_state.selected_expiry = exp_dates[0]

                selected_expiry = st.selectbox(
                    "Select Expiry Date",
                    options=expiry_dates,
                    index=expiry_dates.index(st.session_state.selected_expiry) if st.session_state.selected_expiry in expiry_dates else 0
                )
                st.session_state.selected_expiry = selected_expiry
                st.caption(f"Selected: **{selected_expiry}**")
        except:
            st.warning("Could not fetch expiry dates")

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

    # Use selected expiry from sidebar, or fetch if not set
    selected_expiry = st.session_state.get("selected_expiry", None)

    # If no expiry selected yet, fetch it
    if not selected_expiry:
        expiry_dates, exp_err = fetch_expiry_dates(access_token, "NIFTY")
        if expiry_dates:
            selected_expiry = expiry_dates[0]
            st.session_state.selected_expiry = selected_expiry
            print(f"[DEBUG] Auto-selected expiry: {selected_expiry}")
        else:
            st.warning("⚠️ Could not fetch expiry dates. Check your API credentials.")
            st.stop()

    for symbol_key in ["NIFTY", "BANKNIFTY", "FINNIFTY", "MIDCPNIFTY"]:
        config = STRIKE_CONFIG[symbol_key]
        selected = selected_expiry

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

            # Get opening price from first row's underlying_open (if available)
            if data:
                try:
                    opening_price = float(data[0].get("underlying_open_price") or 0)
                    if opening_price <= 0:
                        opening_price = spot  # Fallback to current spot if not available
                except:
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
            import json
            print(f"[DATA-DUMP] First row JSON (truncated):")
            print(json.dumps(data[0], indent=2, default=str)[:800])
        print(f"{'='*80}\n")
        # ===== END DEBUG =====

        # Process through complete engine
        try:
            engine = st.session_state.engines[symbol_key]
            signal = engine.process(
                chain_data=data,
                underlying_price=spot,
                opening_price=opening_price,  # NEW: pass opening price
                strike_gap=config["gap"],
                symbol=symbol_key,
                expiry_date=selected,
            )
            all_signals[symbol_key] = (signal, spot, config, selected)
            print(f"[DEBUG] {symbol_key} processed successfully: Dom={signal.dominance:.4f}, Mom={signal.momentum:.4f}")
        except Exception as e:
            print(f"[ERROR] Engine failed for {symbol_key}: {str(e)}")
            import traceback
            traceback.print_exc()
            all_signals[symbol_key] = None

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

    # ─────────────────────────────────────────────
    # COMPLETE RAJ PRO TABLE (Matching Pine Script)
    # ─────────────────────────────────────────────
    st.subheader("📋 Detailed Analysis - Complete Table")

    tabs = st.tabs(["NIFTY", "BANKNIFTY", "FINNIFTY", "MIDCPNIFTY"])

    for idx, symbol_key in enumerate(["NIFTY", "BANKNIFTY", "FINNIFTY", "MIDCPNIFTY"]):
        with tabs[idx]:
            if symbol_key in all_signals and all_signals[symbol_key]:
                signal, spot, config, expiry = all_signals[symbol_key]
                atm = int(config["gap"] * round(spot / config["gap"]))

                try:
                    # Create and display complete table
                    table = RajProTable(
                        signal=signal,
                        spot=spot,
                        config=config,
                        expiry_date=expiry,
                        atm_strike=atm,
                        strike_gap=config["gap"],
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
                signal, spot, config, expiry = all_signals[symbol_key]

                try:
                    # Initialize gamma analyzer
                    gamma = GammaAnalyzer(expiry)

                    # Get CE and PE premiums
                    ce1_prem = signal.premiums.get("ce1", 0)
                    pe1_prem = signal.premiums.get("pe1", 0)

                    # Calculate all deltas
                    atm = int(config["gap"] * round(spot / config["gap"]))
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
                        st.dataframe(delta_df, hide_index=True, use_container_width=True)

                        st.caption(f"IV: {deltas['sigma']*100:.1f}% | T: {deltas['days_left']:.1f}d | 🔺G/🔻G = Max Gamma Zone (Δ 0.30-0.35)")

                except Exception as e:
                    st.warning(f"Could not calculate gamma: {e}")
            else:
                st.info(f"⏳ No data for {config['name']}")

    # ─────────────────────────────────────────────
    # DEBUG LOGS DISPLAY
    # ─────────────────────────────────────────────
    st.markdown("---")
    st.subheader("🔍 Debug Logs & Data Structure")

    with st.expander("📊 View Captured Logs", expanded=False):
        # Read the current session log file
        try:
            if SESSION_LOG_FILE.exists():
                with open(SESSION_LOG_FILE, 'r') as f:
                    log_content = f.read()

                # Split by sections
                critical_idx = log_content.find('[CRITICAL]')
                data_dump_idx = log_content.find('[DATA-DUMP]')

                # Show CRITICAL section (Upstox data structure)
                if critical_idx != -1:
                    st.markdown("#### 🔍 [CRITICAL] Upstox API Response Structure")
                    critical_end = log_content.find('\n================', critical_idx)
                    if critical_end == -1:
                        critical_end = len(log_content)
                    critical_section = log_content[critical_idx:critical_end]
                    st.code(critical_section, language="text")

                # Show DATA-DUMP section
                if data_dump_idx != -1:
                    st.markdown("#### 📤 [DATA-DUMP] Received Data")
                    data_end = log_content.find('\n================', data_dump_idx)
                    if data_end == -1:
                        data_end = len(log_content)
                    data_section = log_content[data_dump_idx:data_end]
                    st.code(data_section[:2000], language="text")

                # Show all DEBUG lines
                debug_lines = [line for line in log_content.split('\n') if '[DEBUG]' in line]
                if debug_lines:
                    st.markdown("#### 🐛 [DEBUG] Extraction Details")
                    st.code('\n'.join(debug_lines[:50]), language="text")

                st.success(f"✅ Log file: {SESSION_LOG_FILE}")
            else:
                st.warning("⏳ Logs not yet captured. Please refresh or wait for data load.")
        except Exception as e:
            st.error(f"Could not read logs: {e}")

    # Auto refresh
    time.sleep(180)
    st.rerun()


if __name__ == "__main__":
    main()
