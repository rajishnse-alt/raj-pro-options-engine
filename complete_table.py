"""
Complete Raj Pro Options Engine Table - Pine Script v6 Conversion
Displays as a proper grid table matching Pine Script exactly
"""

import pandas as pd
import streamlit as st
from datetime import datetime
import math


def norm_cdf(x):
    """Normal CDF - Abramowitz & Stegun approximation (matches Pine Script)"""
    t = 1.0 / (1.0 + 0.2316419 * abs(x))
    d = 0.3989423 * math.exp(-x * x / 2.0)
    p = d * t * (0.3193815 + t * (-0.3565638 + t * (1.7814779 + t * (-1.8212560 + t * 1.3302744))))
    return 1.0 - p if x >= 0.0 else p


class RajProTable:
    """Generate complete Raj Pro table matching Pine Script exactly"""

    def __init__(self, signal, spot, config, expiry_date, atm_strike, strike_gap):
        """Initialize table with all required data"""
        self.signal = signal
        self.spot = spot
        self.config = config
        self.expiry_date = expiry_date
        self.atm = atm_strike
        self.gap = strike_gap

        # Calculate days left
        self.days_left = self._calculate_days_left()
        self.T_yr = max(self.days_left / 365.0, 0.5 / 365.0)

        # Calculate IV from straddle
        self.sigma = self._estimate_iv()

    def _calculate_days_left(self):
        """Calculate days until expiry"""
        try:
            expiry = datetime.strptime(self.expiry_date, "%Y-%m-%d")
            now = datetime.now()
            delta = expiry - now
            return max(delta.total_seconds() / 86400.0, 0.5)
        except:
            return 1.0

    def _estimate_iv(self):
        """Back-calculate IV from 1-OTM straddle"""
        ce1 = self.signal.premiums.get("ce1", 0)
        pe1 = self.signal.premiums.get("pe1", 0)

        if self.spot <= 0 or self.T_yr <= 0:
            return 0.20

        straddle = ce1 + pe1
        sqrt_t = math.sqrt(self.T_yr)
        sqrt_2_pi = 0.7979  # sqrt(2/π)

        sigma = straddle / (self.spot * sqrt_t * sqrt_2_pi) if (self.spot * sqrt_t * sqrt_2_pi) > 0 else 0.20
        return max(0.05, min(sigma, 2.0))

    def _norm_cdf(self, x):
        """Normal CDF - Abramowitz & Stegun approximation"""
        return norm_cdf(x)

    def _call_delta(self, strike):
        """Black-Scholes call delta"""
        if self.spot <= 0 or strike <= 0 or self.sigma <= 0 or self.T_yr <= 0:
            return 0.5

        try:
            d1 = (math.log(self.spot / strike) + 0.5 * self.sigma * self.sigma * self.T_yr) / (
                self.sigma * math.sqrt(self.T_yr)
            )
            return self._norm_cdf(d1)
        except:
            return 0.5

    def _put_delta(self, strike):
        """Put delta = abs(1 - call_delta)"""
        return abs(1.0 - self._call_delta(strike))

    def _gamma_marker(self, delta, opt_type):
        """Return gamma marker if delta in 0.30-0.35 zone"""
        if 0.30 <= delta <= 0.35:
            return " 🔺G" if opt_type == "call" else " 🔻G"
        return ""

    def calculate_all_deltas(self):
        """Calculate deltas for all CE and PE strikes"""
        deltas = {
            "ce": {},
            "pe": {},
            "markers_ce": {},
            "markers_pe": {},
        }

        # CE deltas: ATM + gap, +2*gap, +3*gap, +4*gap
        for i in range(1, 5):
            strike = self.atm + i * self.gap
            delta = self._call_delta(strike)
            marker = self._gamma_marker(delta, "call")
            deltas["ce"][i] = delta
            deltas["markers_ce"][i] = marker

        # PE deltas: ATM - gap, -2*gap, -3*gap, -4*gap
        for i in range(1, 5):
            strike = self.atm - i * self.gap
            delta = self._put_delta(strike)
            marker = self._gamma_marker(delta, "put")
            deltas["pe"][i] = delta
            deltas["markers_pe"][i] = marker

        return deltas

    def format_premium(self, value):
        """Format premium value with gamma marker"""
        if value is None or value == 0:
            return "—"
        return f"{value:.2f}"

    def display_streamlit_table(self):
        """Display complete table as a grid matching Pine Script"""
        deltas = self.calculate_all_deltas()

        # Calculate actual strike prices
        ce1_strike = self.atm + self.gap
        ce2_strike = self.atm + 2 * self.gap
        ce3_strike = self.atm + 3 * self.gap
        ce4_strike = self.atm + 4 * self.gap
        pe1_strike = self.atm - self.gap
        pe2_strike = self.atm - 2 * self.gap
        pe3_strike = self.atm - 3 * self.gap
        pe4_strike = self.atm - 4 * self.gap

        # Determine gamma status
        if self.signal.gamma_score > 70:
            gamma_status = "NEAR ATM - HIGH"
        elif self.signal.gamma_score > 40:
            gamma_status = "MEDIUM"
        else:
            gamma_status = "FAR OTM - LOW"

        # Build table rows
        table_data = {
            "ATM/Open": [
                f"₹{self.spot:.0f}",
                f"Gap: {self.gap}",
                f"Δ (IV={self.sigma*100:.1f}%)",
                "",
                f"Score",
                f"DOM/MOM/VOL",
                "",
                f"🔻G Zone",
                f"Legend"
            ],
            "Type": [
                "CE",
                "PE",
                "CE Δ",
                "Spike Confluence",
                f"{self.signal.gamma_score:.1f}",
                f"{self.signal.dominance:+.4f}",
                "",
                "PE Δ",
                "🔺G=CE 🔻G=PE"
            ],
            "Selected": [
                f"{self.atm}",
                f"{self.atm}",
                "PE Δ",
                self.signal.spike_signal,
                gamma_status,
                f"{self.signal.momentum:+.4f}",
                "",
                "0.30-0.35",
                "Sell premium decay"
            ],
            f"1-OTM | CE {ce1_strike} | PE {pe1_strike}": [
                f"{self.signal.premiums.get('ce1', 0):.2f}",
                f"{self.signal.premiums.get('pe1', 0):.2f}",
                f"Δ{deltas['ce'].get(1, 0):.2f}{deltas['markers_ce'].get(1, '')}",
                f"CE: {self.signal.ce_spike_score:.1f}",
                f"SmartProb: 75%",
                f"{self.signal.volatility:.4f}",
                "",
                f"Δ{deltas['pe'].get(1, 0):.2f}{deltas['markers_pe'].get(1, '')}",
                ""
            ],
            f"2-OTM | CE {ce2_strike} | PE {pe2_strike}": [
                f"{self.signal.premiums.get('ce2', 0):.2f}",
                f"{self.signal.premiums.get('pe2', 0):.2f}",
                f"Δ{deltas['ce'].get(2, 0):.2f}{deltas['markers_ce'].get(2, '')}",
                f"PE: {self.signal.pe_spike_score:.1f}",
                "",
                f"{self.signal.trend}",
                "",
                f"Δ{deltas['pe'].get(2, 0):.2f}{deltas['markers_pe'].get(2, '')}",
                ""
            ],
            f"3-OTM | CE {ce3_strike} | PE {pe3_strike}": [
                f"{self.signal.premiums.get('ce3', 0):.2f}",
                f"{self.signal.premiums.get('pe3', 0):.2f}",
                f"Δ{deltas['ce'].get(3, 0):.2f}{deltas['markers_ce'].get(3, '')}",
                f"Edge: {abs(self.signal.score_diff):.2f}",
                "",
                "",
                "",
                f"Δ{deltas['pe'].get(3, 0):.2f}{deltas['markers_pe'].get(3, '')}",
                ""
            ],
            f"4-OTM | CE {ce4_strike} | PE {pe4_strike}": [
                f"{self.signal.premiums.get('ce4', 0):.2f}",
                f"{self.signal.premiums.get('pe4', 0):.2f}",
                f"Δ{deltas['ce'].get(4, 0):.2f}{deltas['markers_ce'].get(4, '')}",
                "",
                "",
                "",
                "",
                f"Δ{deltas['pe'].get(4, 0):.2f}{deltas['markers_pe'].get(4, '')}",
                ""
            ],
            "Trend": [
                self.signal.trend,
                self.signal.trend,
                f"T={self.days_left:.1f}d",
                "",
                "",
                "",
                "⚠️ CONFLICT" if "CONFLICT" in self.signal.spike_signal else "",
                "",
                ""
            ]
        }

        # Create DataFrame
        df = pd.DataFrame(table_data)

        # Display with Streamlit
        st.markdown("### 📊 Complete Options Analysis Table")
        st.dataframe(df, width='stretch', hide_index=True)
