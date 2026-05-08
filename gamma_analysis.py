"""
Gamma Analysis & Delta Calculator
Converts Pine Script gamma/delta table to Python
"""

import math
from datetime import datetime
from typing import Dict, Tuple


def norm_cdf(x):
    """Normal CDF - Abramowitz & Stegun approximation (matches Pine Script)"""
    t = 1.0 / (1.0 + 0.2316419 * abs(x))
    d = 0.3989423 * math.exp(-x * x / 2.0)
    p = d * t * (0.3193815 + t * (-0.3565638 + t * (1.7814779 + t * (-1.8212560 + t * 1.3302744))))
    return 1.0 - p if x >= 0.0 else p


class GammaAnalyzer:
    """Calculate delta, gamma, and gamma scores for options"""

    def __init__(self, expiry_date: str):
        """Initialize with expiry date"""
        self.expiry_date = expiry_date
        self.days_left = self._calculate_days_left(expiry_date)
        self.T_yr = max(self.days_left / 365.0, 0.5 / 365.0)

    def _calculate_days_left(self, expiry_date: str) -> float:
        """Calculate days until expiry"""
        try:
            expiry = datetime.strptime(expiry_date, "%Y-%m-%d")
            now = datetime.now()
            delta = expiry - now
            return max(delta.total_seconds() / 86400.0, 0.5)
        except:
            return 1.0

    def estimate_implied_vol(self, ce_premium: float, pe_premium: float, spot: float) -> float:
        """
        Back-calculate IV from 1-OTM straddle approximation
        sigma ≈ (ce1N + pe1N) / (spotRef × sqrt(T) × 0.7979)
        where 0.7979 = sqrt(2/π)
        """
        if spot <= 0 or self.T_yr <= 0:
            return 0.20

        straddle = ce_premium + pe_premium
        sqrt_t = math.sqrt(self.T_yr)
        sqrt_2_pi = 0.7979

        sigma = straddle / (spot * sqrt_t * sqrt_2_pi) if (spot * sqrt_t * sqrt_2_pi) > 0 else 0.20

        # Clamp between 0.05 and 2.0
        return max(0.05, min(sigma, 2.0))

    def call_delta(self, spot: float, strike: float, sigma: float, r: float = 0.0) -> float:
        """
        Black-Scholes call delta
        delta = N(d1) where d1 = (ln(S/K) + (r + σ²/2)T) / (σ√T)
        """
        if spot <= 0 or strike <= 0 or sigma <= 0 or self.T_yr <= 0:
            return 0.5

        try:
            d1 = (math.log(spot / strike) + (r + (sigma ** 2) / 2) * self.T_yr) / (sigma * math.sqrt(self.T_yr))
            delta = norm_cdf(d1)
            return delta
        except:
            return 0.5

    def put_delta(self, spot: float, strike: float, sigma: float, r: float = 0.0) -> float:
        """Put delta = Call delta - 1 (or use abs(call_delta - 1))"""
        call_d = self.call_delta(spot, strike, sigma, r)
        return abs(1.0 - call_d)

    def is_gamma_zone(self, delta: float) -> bool:
        """Check if delta is in gamma peak zone (0.30-0.35)"""
        return 0.30 <= delta <= 0.35

    def gamma_marker(self, delta: float, opt_type: str) -> str:
        """Return gamma marker emoji if in zone"""
        if self.is_gamma_zone(delta):
            return " 🔺G" if opt_type == "call" else " 🔻G"
        return ""

    def calculate_deltas(
        self,
        spot: float,
        atm_strike: int,
        strike_gap: int,
        ce_premium: float,
        pe_premium: float,
    ) -> Dict:
        """Calculate all deltas for CE and PE strikes (1-4 OTM)"""

        sigma = self.estimate_implied_vol(ce_premium, pe_premium, spot)

        result = {
            "sigma": sigma,
            "days_left": self.days_left,
            "T_yr": self.T_yr,
            "ce_deltas": {},
            "pe_deltas": {},
            "ce_markers": {},
            "pe_markers": {},
        }

        # CE strikes: ATM + gap, ATM + 2*gap, etc.
        for i in range(1, 5):
            ce_strike = atm_strike + i * strike_gap
            delta = self.call_delta(spot, ce_strike, sigma)
            marker = self.gamma_marker(delta, "call")

            result["ce_deltas"][i] = delta
            result["ce_markers"][i] = marker

        # PE strikes: ATM - gap, ATM - 2*gap, etc.
        for i in range(1, 5):
            pe_strike = atm_strike - i * strike_gap
            delta = self.put_delta(spot, pe_strike, sigma)
            marker = self.gamma_marker(delta, "put")

            result["pe_deltas"][i] = delta
            result["pe_markers"][i] = marker

        return result

    def gamma_score(self, ce_deltas: Dict, pe_deltas: Dict, dominance: float) -> float:
        """
        Calculate gamma score based on proximity to gamma zone (0.30-0.35)
        and dominance bias
        """
        # Count how many strikes are in gamma zone
        gamma_count = sum(1 for d in list(ce_deltas.values()) + list(pe_deltas.values())
                         if 0.30 <= d <= 0.35)

        # Base score: 0-100 based on gamma proximity
        base_score = min(gamma_count * 20, 100)

        # Adjust for dominance
        if dominance > 0.5:  # Put erosion higher = bullish
            base_score += 10
        elif dominance < -0.5:  # Call erosion higher = bearish
            base_score -= 10

        return max(0, min(base_score, 100))

    def format_delta_display(self, delta: float, marker: str) -> str:
        """Format delta for display"""
        if delta is None or math.isnan(delta):
            return "N/A"
        return f"Δ{delta:.2f}{marker}"
