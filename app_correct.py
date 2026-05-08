"""
Raj Pro Options Engine - EXACT Pine Script Table Structure
Matches indicator table 100%
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


def render_table_for_symbol(symbol_key: str, signal, spot: float, config: dict):
    """Render exact Pine Script table layout for one symbol"""

    if not signal or signal.name == "NO_DATA":
        st.warning(f"No data for {config['name']}")
        return

    # Create table with proper structure
    col1, col2, col3, col4, col5, col6, col7, col8 = st.columns([1.2, 0.8, 1, 1, 1, 1, 1, 1])

    with col1:
        st.markdown(f"**ATM/Open**\n{spot:.2f}")

    with col2:
        st.markdown("**Type**\nCE\nPE")

    with col3:
        st.markdown(f"**Selected**\n{int(spot)}\n{int(spot)}")

    # Get premiums
    prems = signal.premiums
    ce_vals = [
        f"{prems.get('ce1', 0):.2f}" if prems.get('ce1', 0) > 0 else "—",
        f"{prems.get('ce2', 0):.2f}" if prems.get('ce2', 0) > 0 else "—",
        f"{prems.get('ce3', 0):.2f}" if prems.get('ce3', 0) > 0 else "—",
        f"{prems.get('ce4', 0):.2f}" if prems.get('ce4', 0) > 0 else "—",
    ]
    pe_vals = [
        f"{prems.get('pe1', 0):.2f}" if prems.get('pe1', 0) > 0 else "—",
        f"{prems.get('pe2', 0):.2f}" if prems.get('pe2', 0) > 0 else "—",
        f"{prems.get('pe3', 0):.2f}" if prems.get('pe3', 0) > 0 else "—",
        f"{prems.get('pe4', 0):.2f}" if prems.get('pe4', 0) > 0 else "—",
    ]

    with col4:
        st.markdown(f"**1-OTM**\n{ce_vals[0]}\n{pe_vals[0]}")
    with col5:
        st.markdown(f"**2-OTM**\n{ce_vals[1]}\n{pe_vals[1]}")
    with col6:
        st.markdown(f"**3-OTM**\n{ce_vals[2]}\n{pe_vals[2]}")
    with col7:
        st.markdown(f"**4-OTM**\n{ce_vals[3]}\n{pe_vals[3]}")

    trend_color = "🟢" if signal.trend == "BULL" else "🔴" if signal.trend == "BEAR" else "⚪"
    with col8:
        st.markdown(f"**Trend**\n{trend_color}\n{signal.trend}")

    st.divider()

    # Detailed metrics below table
    col1, col2, col3 = st.columns(3)

    with col1:
        st.metric("Dominance", f"{signal.dominance:+.4f}", delta=f"{signal.dominance*100:.2f}%")
        st.metric("Call Erosion", f"{signal.call_erosion:+.4f}")

    with col2:
        st.metric("Momentum", f"{signal.momentum:+.4f}", delta=f"{signal.momentum*100:.2f}%")
        st.metric("Put Erosion", f"{signal.put_erosion:+.4f}")

    with col3:
        st.metric("Volatility", f"{signal.volatility:.4f}")
        st.metric("Gamma Score", f"{signal.gamma_score:.1f}")

    # Detailed signals
    st.markdown("---")
    col1, col2, col3 = st.columns(3)

    with col1:
        st.markdown(f"""
        **Spike Confluence**
        {signal.spike_signal}
        """)

    with col2:
        st.markdown(f"""
        **Institutional Signal**
        {signal.inst_signal}
        """)

    with col3:
        st.markdown(f"""
        **Signal Quality**
        {signal.name}
        Confidence: {signal.confidence:.0%}
        """)

    # Confluence scores
    st.markdown("---")
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.markdown(f"**CE Spike Score**\n{signal.ce_spike_score:.2f}")

    with col2:
        st.markdown(f"**PE Spike Score**\n{signal.pe_spike_score:.2f}")

    with col3:
        st.markdown(f"**Score Diff**\n{signal.score_diff:+.2f}")

    with col4:
        st.markdown(f"""
        **Bar Counts**
        Bull: {signal.bull_bars}
        Bear: {signal.bear_bars}
        """)

    # Conflict warning
    if "CONFLICT" in signal.spike_signal:
        st.error(f"⚠️ CONFLICT: {signal.spike_signal} - WAIT/SKIP")

    st.markdown("---")

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
    st.caption(f"{'🟢' if mkt else '🔴'} {now.strftime('%d %b %H:%M IST')} | Upstox API | Pine Script Conversion")

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

        expiry_dates, exp_err = fetch_expiry_dates(access_token, symbol_key)
        if exp_err == "token_expired":
            del st.session_state["access_token"]
            st.rerun()

        if exp_err or not expiry_dates:
            all_signals[symbol_key] = None
            continue

        if f"exp_{symbol_key}" not in st.session_state:
            st.session_state[f"exp_{symbol_key}"] = expiry_dates[0]

        selected = st.session_state[f"exp_{symbol_key}"]

        data, chain_err, _ = fetch_chain(access_token, symbol_key, selected)
        if chain_err == "token_expired":
            del st.session_state["access_token"]
            st.rerun()

        if chain_err or not data:
            all_signals[symbol_key] = None
            continue

        spot = None
        for row in data:
            sp = row.get("underlying_spot_price")
            if sp:
                spot = float(sp)
                break

        if not spot:
            all_signals[symbol_key] = None
            continue

        engine = st.session_state.engines[symbol_key]
        signal = engine.process(
            chain_data=data,
            underlying_price=spot,
            strike_gap=config["gap"],
            symbol=symbol_key,
            expiry_date=selected,
        )

        all_signals[symbol_key] = (signal, spot, config, selected)

    # Display tables
    st.markdown("## Options Analysis Tables")

    for symbol_key in ["NIFTY", "BANKNIFTY", "FINNIFTY", "MIDCPNIFTY"]:
        st.markdown(f"### {STRIKE_CONFIG[symbol_key]['name']}")

        if symbol_key in all_signals and all_signals[symbol_key]:
            signal, spot, config, expiry = all_signals[symbol_key]
            render_table_for_symbol(symbol_key, signal, spot, config)
        else:
            st.info(f"⏳ Fetching data for {STRIKE_CONFIG[symbol_key]['name']}...")

    # Auto refresh
    time.sleep(180)
    st.rerun()


if __name__ == "__main__":
    main()
