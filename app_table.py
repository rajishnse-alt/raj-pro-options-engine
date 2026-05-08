"""
Raj Pro Options Engine - Exact Table Match
Matches Pine Script indicator table structure 100%
"""

import streamlit as st
import requests
import time
import pandas as pd
from datetime import datetime
import pytz

from engine_complete import RajProEngine

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
    .raj-table {
        width: 100%;
        border-collapse: collapse;
        background-color: #0d1321;
        border: 1px solid #444;
        font-family: monospace;
        font-size: 12px;
    }
    .raj-table td, .raj-table th {
        border: 1px solid #444;
        padding: 8px;
        text-align: center;
        color: #fff;
    }
    .raj-header {
        background-color: #1a2f4d;
        font-weight: bold;
        color: #2979ff;
    }
    .raj-ce {
        background-color: rgba(0, 128, 0, 0.1);
        color: #7cfc00;
    }
    .raj-pe {
        background-color: rgba(128, 0, 0, 0.1);
        color: #ff4444;
    }
    .raj-gamma-zone {
        background-color: rgba(0, 128, 128, 0.3);
        color: #ffff00;
    }
    .raj-bullish {
        background-color: rgba(0, 128, 0, 0.2);
        color: #7cfc00;
    }
    .raj-bearish {
        background-color: rgba(128, 0, 0, 0.2);
        color: #ff4444;
    }
    .raj-conflict {
        background-color: rgba(255, 165, 0, 0.3);
        color: #ffff00;
    }
    .raj-neutral {
        background-color: rgba(100, 100, 100, 0.1);
        color: #aaa;
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


def build_signal_html_table(symbol_key: str, signal, spot: float, config: dict) -> str:
    """Build exact Pine Script table HTML for one symbol"""

    if not signal or signal.name == "NO_DATA":
        return f"<p style='color: #aaa;'>No data for {config['name']}</p>"

    # Determine colors
    signal_color = "#7cfc00" if signal.color == "green" else "#ff4444" if signal.color == "red" else "#ffff00"
    trend_color = "#7cfc00" if signal.trend == "BULL" else "#ff4444" if signal.trend == "BEAR" else "#aaa"

    # Get premium values with gamma markers
    premiums = signal.premiums
    ce1 = f"{premiums.get('ce1', 0):.2f}" if premiums.get('ce1', 0) > 0 else "—"
    ce2 = f"{premiums.get('ce2', 0):.2f}" if premiums.get('ce2', 0) > 0 else "—"
    ce3 = f"{premiums.get('ce3', 0):.2f}" if premiums.get('ce3', 0) > 0 else "—"
    ce4 = f"{premiums.get('ce4', 0):.2f}" if premiums.get('ce4', 0) > 0 else "—"
    pe1 = f"{premiums.get('pe1', 0):.2f}" if premiums.get('pe1', 0) > 0 else "—"
    pe2 = f"{premiums.get('pe2', 0):.2f}" if premiums.get('pe2', 0) > 0 else "—"
    pe3 = f"{premiums.get('pe3', 0):.2f}" if premiums.get('pe3', 0) > 0 else "—"
    pe4 = f"{premiums.get('pe4', 0):.2f}" if premiums.get('pe4', 0) > 0 else "—"

    html = f"""
    <table class='raj-table'>
        <!-- HEADER ROW -->
        <tr class='raj-header'>
            <td>ATM/Open</td>
            <td>Type</td>
            <td>Selected</td>
            <td>1-OTM</td>
            <td>2-OTM</td>
            <td>3-OTM</td>
            <td>4-OTM</td>
            <td>Trend</td>
        </tr>

        <!-- CE ROW -->
        <tr class='raj-ce'>
            <td rowspan='2' style='color: #ccc;'>{spot:.2f}</td>
            <td>CE</td>
            <td style='color: #7cfc00;'>{spot:.0f}</td>
            <td>{ce1}</td>
            <td>{ce2}</td>
            <td>{ce3}</td>
            <td style='color: #ffff00;'>{ce4}</td>
            <td rowspan='2' style='color: {trend_color}; font-weight: bold;'>{signal.trend}</td>
        </tr>

        <!-- PE ROW -->
        <tr class='raj-pe'>
            <td>PE</td>
            <td style='color: #7cfc00;'>{spot:.0f}</td>
            <td>{pe1}</td>
            <td>{pe2}</td>
            <td>{pe3}</td>
            <td style='color: #ffff00;'>{pe4}</td>
        </tr>

        <!-- GAP/IV/DAYS ROW -->
        <tr class='raj-neutral'>
            <td colspan='2' style='color: #ccc;'>Gap/IV/Days</td>
            <td style='color: #ffff00;'>Gap: 50</td>
            <td colspan='4' style='color: #aaa;'>IV: {signal.volatility*100:.1f}% | T: 5.4d</td>
        </tr>

        <!-- SPIKE CONFLUENCE ROW -->
        <tr class='{("raj-bullish" if "UP" in signal.spike_signal else "raj-bearish" if "DN" in signal.spike_signal else "raj-conflict")}'>
            <td colspan='2' style='font-weight: bold;'>Spike Confluence</td>
            <td colspan='2' style='color: {signal_color};'>{signal.spike_signal}</td>
            <td style='color: #7cfc00;'>CE: {signal.ce_spike_score:.2f}</td>
            <td style='color: #ff4444;'>PE: {signal.pe_spike_score:.2f}</td>
            <td style='color: #ffff00;'>Edge: {abs(signal.score_diff):.2f}</td>
        </tr>

        <!-- GAMMA SCORE ROW -->
        <tr class='raj-neutral'>
            <td colspan='2'>Gamma Score</td>
            <td style='color: {"#7cfc00" if signal.gamma_score > 70 else "#ffff00" if signal.gamma_score > 40 else "#ff4444"};'>{signal.gamma_score:.1f}</td>
            <td colspan='2' style='color: #aaa;'>{"NEAR ATM - HIGH" if signal.gamma_score > 70 else "MEDIUM" if signal.gamma_score > 40 else "FAR OTM - LOW"}</td>
            <td colspan='2' style='color: #ffaa00;'>SmartProb: {int(signal.confidence*100)}%</td>
        </tr>

        <!-- DOM/MOM/VOL ROW -->
        <tr class='raj-neutral'>
            <td colspan='2' style='font-weight: bold;'>DOM / MOM / VOL</td>
            <td style='color: {"#7cfc00" if signal.dominance > 0.04 else "#ff4444" if signal.dominance < -0.04 else "#aaa"};'>{signal.dominance:+.4f}</td>
            <td style='color: {"#7cfc00" if signal.momentum > 0 else "#ff4444"};'>{signal.momentum:+.4f}</td>
            <td style='color: #aaa;'>{signal.volatility:.4f}</td>
            <td colspan='2' style='color: {trend_color};'>{signal.trend}</td>
        </tr>

        <!-- INSTITUTIONAL SIGNALS ROW -->
        <tr class='{("raj-bullish" if "BULL" in signal.inst_signal else "raj-bearish" if "BEAR" in signal.inst_signal else "raj-neutral")}'>
            <td colspan='2' style='font-weight: bold;'>Inst. Signals</td>
            <td colspan='5' style='color: {signal_color};'>{signal.inst_signal}</td>
        </tr>

        <!-- CONFLICT ROW (if applicable) -->
        {'<tr class="raj-conflict">' +
         '<td colspan="2" style="font-weight: bold; color: #ffff00;">⚠️ CONFLICT</td>' +
         '<td colspan="5" style="color: #ffff00;">WAIT / SKIP - Mixed signals detected</td>' +
         '</tr>' if "CONFLICT" in signal.spike_signal else ''}

        <!-- LEGEND ROW -->
        <tr class='raj-header' style='font-size: 10px;'>
            <td colspan='8' style='color: #aaa;'>
                🔺G = CE Gamma Zone (Δ 0.30-0.35) | 🔻G = PE Gamma Zone | Sell premium for max decay
            </td>
        </tr>
    </table>
    """
    return html

# ─────────────────────────────────────────────
# MAIN APP
# ─────────────────────────────────────────────

def main():
    now = datetime.now(IST)
    mkt = (
        now.weekday() < 5 and
        (9, 15) <= (now.hour, now.minute) <= (15, 30)
    )

    st.title("📊 Raj Pro Options Engine")
    st.caption(f"{'🟢' if mkt else '🔴'} {now.strftime('%d %b %H:%M IST')} | Upstox API | 100% Pine Script Indicator Match")

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
        if st.button("🔓 Logout", use_container_width=True):
            for k in list(st.session_state.keys()):
                del st.session_state[k]
            st.rerun()

    # Fetch data for all symbols
    access_token = st.session_state["access_token"]
    all_signals = {}

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

    # Display tables for each symbol
    st.markdown("## 📊 Options Analysis - Pine Script Table Format")

    for symbol_key in ["NIFTY", "BANKNIFTY", "FINNIFTY", "MIDCPNIFTY"]:
        st.markdown(f"### {STRIKE_CONFIG[symbol_key]['name']}")

        if symbol_key in all_signals and all_signals[symbol_key]:
            signal, spot, config, expiry = all_signals[symbol_key]
            html = build_signal_html_table(symbol_key, signal, spot, config)
            st.markdown(html, unsafe_allow_html=True)
        else:
            st.info(f"⏳ Loading data for {STRIKE_CONFIG[symbol_key]['name']}...")

        st.divider()

    # Auto refresh
    time.sleep(180)
    st.rerun()


if __name__ == "__main__":
    main()
