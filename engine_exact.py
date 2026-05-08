"""
Raj Pro Options Engine - EXACT Pine Script Implementation
Direct line-by-line conversion of Pine Script v6 indicator
"""

import math
import numpy as np
from datetime import datetime, date
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass
from collections import deque


@dataclass
class Signal:
    """Complete signal output"""
    name: str
    confidence: float
    dominance: float
    momentum: float
    volatility: float
    call_erosion: float
    put_erosion: float
    trend: str
    color: str
    inst_signal: str
    spike_signal: str
    gamma_score: float
    ce_spike_score: float
    pe_spike_score: float
    score_diff: float
    bull_bars: int
    bear_bars: int
    reversal_count: int
    dom_rising_count: int
    dom_falling_count: int
    ce_erosions: Dict[int, float]
    pe_erosions: Dict[int, float]
    premiums: Dict[str, float]
    median: float  # NEW: median value


class RajProEngine:
    """
    Exact Pine Script v6 conversion
    Implements MEDIAN + DAY OPEN TRACKING + EROSION exactly
    """

    INSTRUMENTS = {
        "NIFTY": {"gap": 50, "atm": 24000, "name": "NIFTY 50"},
        "BANKNIFTY": {"gap": 100, "atm": 55000, "name": "BANKNIFTY"},
        "FINNIFTY": {"gap": 50, "atm": 24000, "name": "FINNIFTY"},
        "MIDCPNIFTY": {"gap": 25, "atm": 12000, "name": "MIDCPNIFTY"},
    }

    def __init__(self, config: Optional[Dict] = None):
        """Initialize engine"""
        self.config = config or {
            "dominance_threshold": 0.04,
            "trend_ema_length": 5,
            "trend_confirm_bars": 3,
            "strong_move_coefficient": 1.2,
            "spike_edge_min": 0.01,
        }

        # ========== EXACT Pine Script variables ==========

        # Day open premiums (Pine Script: var float ce1O = na, etc.)
        self.ce1O = None
        self.ce2O = None
        self.ce3O = None
        self.ce4O = None
        self.pe1O = None
        self.pe2O = None
        self.pe3O = None
        self.pe4O = None

        self.current_date = None

        # History tracking
        self.dominance_history = deque(maxlen=50)
        self.ce_erosion_history = deque(maxlen=50)
        self.pe_erosion_history = deque(maxlen=50)
        self.momentum_history = deque(maxlen=50)
        self.vol_history = deque(maxlen=50)

        # Trend tracking
        self.bull_bars = 0
        self.bear_bars = 0
        self.reversal_count = 0
        self.prev_trend_sign = 0.0
        self.dom_rising_count = 0
        self.dom_falling_count = 0

    def process(
        self,
        chain_data: List[Dict],
        underlying_price: float,
        strike_gap: int,
        symbol: str = "NIFTY",
        expiry_date: Optional[str] = None,
    ) -> Signal:
        """
        EXACT Pine Script pipeline
        """

        # ========== CRITICAL: Dump actual data structure ==========
        print(f"\n{'='*80}")
        print(f"[CRITICAL] Actual Upstox data structure for {symbol}")
        print(f"{'='*80}")
        print(f"Total rows: {len(chain_data)}")
        if chain_data:
            print(f"\nFirst row keys: {list(chain_data[0].keys())}")
            print(f"\nFirst row (first 1000 chars):")
            import json
            print(json.dumps(chain_data[0], indent=2, default=str)[:1000])
        print(f"{'='*80}\n")

        # ========== STEP 1: Check day change (Pine Script: nDay = ta.change(time("D")) != 0) ==========
        today = date.today()
        nDay = self.current_date != today

        if nDay:
            # Reset all day-open variables when day changes
            self.ce1O = None
            self.ce2O = None
            self.ce3O = None
            self.ce4O = None
            self.pe1O = None
            self.pe2O = None
            self.pe3O = None
            self.pe4O = None
            self.current_date = today

        # ========== STEP 2: Extract specific OTM premiums ==========
        atm_strike = int(strike_gap * round(underlying_price / strike_gap))

        ce_strikes = [atm_strike + i * strike_gap for i in range(1, 5)]  # ce1S, ce2S, ce3S, ce4S
        pe_strikes = [atm_strike - i * strike_gap for i in range(1, 5)]  # pe1S, pe2S, pe3S, pe4S

        print(f"\n[DEBUG] {symbol} - Spot: {underlying_price}, ATM: {atm_strike}, Gap: {strike_gap}")
        print(f"[DEBUG] CE strikes needed: {ce_strikes}")
        print(f"[DEBUG] PE strikes needed: {pe_strikes}")

        # Build chain dict (matches working app approach)
        chain_dict = {}
        for row in chain_data:
            try:
                strike = int(float(row.get("strike_price", 0)))
                if strike > 0:
                    chain_dict[strike] = row
            except (ValueError, TypeError):
                continue

        print(f"[DEBUG] Total strikes in chain: {len(chain_dict)}")

        # Extract premiums using proven method from working app
        ce1N = self._get_premium(chain_dict, ce_strikes[0], "call")
        ce2N = self._get_premium(chain_dict, ce_strikes[1], "call")
        ce3N = self._get_premium(chain_dict, ce_strikes[2], "call")
        ce4N = self._get_premium(chain_dict, ce_strikes[3], "call")
        pe1N = self._get_premium(chain_dict, pe_strikes[0], "put")
        pe2N = self._get_premium(chain_dict, pe_strikes[1], "put")
        pe3N = self._get_premium(chain_dict, pe_strikes[2], "put")
        pe4N = self._get_premium(chain_dict, pe_strikes[3], "put")

        print(f"[DEBUG] CE Premiums: {ce1N:.2f}, {ce2N:.2f}, {ce3N:.2f}, {ce4N:.2f}")
        print(f"[DEBUG] PE Premiums: {pe1N:.2f}, {pe2N:.2f}, {pe3N:.2f}, {pe4N:.2f}")

        # ========== STEP 3: Calculate MEDIAN (Pine Script exact) ==========
        # float med = vc > 0 ? sp / vc : na
        vc = 0
        sp = 0.0

        # Count non-zero premiums and sum them
        for prem in [ce1N, ce2N, ce3N, ce4N, pe1N, pe2N, pe3N, pe4N]:
            if prem > 0:
                vc += 1
                sp += prem

        median = sp / vc if vc > 0 else 0.0
        print(f"[DEBUG] Median calculation: sum={sp:.2f}, count={vc}, median={median:.4f}")

        # ========== STEP 4: STORE DAY OPEN PREMIUMS (Pine Script exact) ==========
        # Pine Script: ce1O := nDay ? ce1N : na(ce1O) ? ce1N : ce1O
        # Means: if new day, reset to ce1N. Else if was NA, set to ce1N. Else keep it.

        self.ce1O = ce1N if nDay or self.ce1O is None else self.ce1O
        self.ce2O = ce2N if nDay or self.ce2O is None else self.ce2O
        self.ce3O = ce3N if nDay or self.ce3O is None else self.ce3O
        self.ce4O = ce4N if nDay or self.ce4O is None else self.ce4O
        self.pe1O = pe1N if nDay or self.pe1O is None else self.pe1O
        self.pe2O = pe2N if nDay or self.pe2O is None else self.pe2O
        self.pe3O = pe3N if nDay or self.pe3O is None else self.pe3O
        self.pe4O = pe4N if nDay or self.pe4O is None else self.pe4O

        # ========== STEP 5: CALCULATE EROSION (Pine Script exact) ==========
        # ce1E = ce1O != 0 ? (ce1O - ce1N) / ce1O : 0.0

        ce1E = (self.ce1O - ce1N) / self.ce1O if (self.ce1O and self.ce1O != 0 and ce1N) else 0.0
        ce2E = (self.ce2O - ce2N) / self.ce2O if (self.ce2O and self.ce2O != 0 and ce2N) else 0.0
        ce3E = (self.ce3O - ce3N) / self.ce3O if (self.ce3O and self.ce3O != 0 and ce3N) else 0.0
        ce4E = (self.ce4O - ce4N) / self.ce4O if (self.ce4O and self.ce4O != 0 and ce4N) else 0.0
        pe1E = (self.pe1O - pe1N) / self.pe1O if (self.pe1O and self.pe1O != 0 and pe1N) else 0.0
        pe2E = (self.pe2O - pe2N) / self.pe2O if (self.pe2O and self.pe2O != 0 and pe2N) else 0.0
        pe3E = (self.pe3O - pe3N) / self.pe3O if (self.pe3O and self.pe3O != 0 and pe3N) else 0.0
        pe4E = (self.pe4O - pe4N) / self.pe4O if (self.pe4O and self.pe4O != 0 and pe4N) else 0.0

        # ========== STEP 6: Calculate cE and pE (average of 4 erosions) ==========
        # cE  = (ce1E + ce2E + ce3E + ce4E) / 4
        # pE  = (pe1E + pe2E + pe3E + pe4E) / 4

        cE = (ce1E + ce2E + ce3E + ce4E) / 4
        pE = (pe1E + pe2E + pe3E + pe4E) / 4

        # ========== STEP 7: Calculate DOMINANCE (the key!) ==========
        # dom = pE - cE

        dominance = pE - cE

        self.dominance_history.append(dominance)
        self.ce_erosion_history.append(cE)
        self.pe_erosion_history.append(pE)

        # ========== STEP 8: EMA-based momentum ==========
        call_ema = self._ema(list(self.ce_erosion_history), period=self.config["trend_ema_length"])
        put_ema = self._ema(list(self.pe_erosion_history), period=self.config["trend_ema_length"])
        momentum = put_ema - call_ema
        self.momentum_history.append(momentum)

        # ========== STEP 9: Volatility ==========
        volatility = self._stdev(list(self.dominance_history), period=20)
        if volatility <= 0:
            volatility = self.config["dominance_threshold"]
        self.vol_history.append(volatility)

        # ========== STEP 10: Trend detection ==========
        if momentum > 0:
            self.bull_bars += 1
            self.bear_bars = 0
        elif momentum < 0:
            self.bear_bars += 1
            self.bull_bars = 0
        else:
            self.bull_bars = 0
            self.bear_bars = 0

        # ========== STEP 11: Dominance confluence ==========
        prev_dom = self.dominance_history[-2] if len(self.dominance_history) > 1 else dominance
        self.dom_rising_count = self.dom_rising_count + 1 if dominance > prev_dom else 0
        self.dom_falling_count = self.dom_falling_count + 1 if dominance < prev_dom else 0

        # ========== STEP 12: Determine trend ==========
        confirmed_trend = "neutral"
        dom_conf_up = self.dom_rising_count >= self.config.get("dom_confluence_bars", 2)
        dom_conf_down = self.dom_falling_count >= self.config.get("dom_confluence_bars", 2)

        if self.bull_bars >= self.config["trend_confirm_bars"] and dom_conf_up:
            confirmed_trend = "bull"
        elif self.bear_bars >= self.config["trend_confirm_bars"] and dom_conf_down:
            confirmed_trend = "bear"

        # ========== STEP 13: Strong move ==========
        strong_move = abs(momentum) > volatility * self.config["strong_move_coefficient"]

        # ========== STEP 14: Gamma score ==========
        dist_from_atm = abs(underlying_price - float(atm_strike))
        gamma_score = 100.0 / (1.0 + (dist_from_atm / max(strike_gap, 1.0)))

        # ========== STEP 15: Spike scores ==========
        buf = strike_gap * 0.25
        ce_bias = 1.2 if underlying_price > (atm_strike + buf) else 0.8 if underlying_price < (atm_strike - buf) else 1.0
        pe_bias = 1.2 if underlying_price < (atm_strike - buf) else 0.8 if underlying_price > (atm_strike + buf) else 1.0

        ce_spike_score = gamma_score * (1.0 + abs(cE) * 10.0) * ce_bias
        pe_spike_score = gamma_score * (1.0 + abs(pE) * 10.0) * pe_bias
        score_diff = ce_spike_score - pe_spike_score

        spikes_bull = score_diff < -self.config["spike_edge_min"]
        spikes_bear = score_diff > self.config["spike_edge_min"]

        # ========== STEP 16: Build signals ==========
        rss_bull = confirmed_trend == "bull"
        rss_bear = confirmed_trend == "bear"
        otm_bull = momentum > 0
        otm_bear = momentum < 0

        spike_signal = self._build_spike_signal(
            rss_bull, rss_bear, otm_bull, otm_bear, spikes_bull, spikes_bear, strong_move
        )

        signal_name = "UP_CONFIRMED" if (rss_bull and otm_bull and strong_move) else \
                     "DN_CONFIRMED" if (rss_bear and otm_bear and strong_move) else \
                     "UP_BUILDING" if rss_bull else \
                     "DN_BUILDING" if rss_bear else \
                     "NEUTRAL/WAIT"

        confidence = 0.9 if "CONFIRMED" in signal_name else 0.7 if "BUILDING" in signal_name else 0.3
        color = "green" if "UP" in signal_name else "red" if "DN" in signal_name else "gray"

        return Signal(
            name=signal_name,
            confidence=confidence,
            dominance=dominance,
            momentum=momentum,
            volatility=volatility,
            call_erosion=cE,
            put_erosion=pE,
            trend=confirmed_trend.upper() if confirmed_trend != "neutral" else "NEUTRAL",
            color=color,
            inst_signal="NEUTRAL",
            spike_signal=spike_signal,
            gamma_score=gamma_score,
            ce_spike_score=ce_spike_score,
            pe_spike_score=pe_spike_score,
            score_diff=score_diff,
            bull_bars=self.bull_bars,
            bear_bars=self.bear_bars,
            reversal_count=self.reversal_count,
            dom_rising_count=self.dom_rising_count,
            dom_falling_count=self.dom_falling_count,
            ce_erosions={ce_strikes[i]: [ce1E, ce2E, ce3E, ce4E][i] for i in range(4)},
            pe_erosions={pe_strikes[i]: [pe1E, pe2E, pe3E, pe4E][i] for i in range(4)},
            premiums={
                'ce1': ce1N or 0, 'ce2': ce2N or 0, 'ce3': ce3N or 0, 'ce4': ce4N or 0,
                'pe1': pe1N or 0, 'pe2': pe2N or 0, 'pe3': pe3N or 0, 'pe4': pe4N or 0,
            },
            median=median / 1000.0  # Pine Script plots med / 1000
        )

    def _get_premium(self, chain_dict: Dict, strike: int, opt_type: str) -> float:
        """Extract premium from chain - LTP with close_price/bid-ask fallbacks"""
        if strike not in chain_dict:
            return 0.0

        row = chain_dict[strike]

        # Get call_options or put_options
        if opt_type == "call":
            opt_data = row.get("call_options") or {}
        else:
            opt_data = row.get("put_options") or {}

        market_data = opt_data.get("market_data") or {}

        # Try LTP first
        ltp = float(market_data.get("ltp") or 0)
        source = "ltp"

        # If LTP is 0, use close_price as fallback (Upstox sometimes has 0 LTP for illiquid strikes)
        if ltp <= 0:
            ltp = float(market_data.get("close_price") or 0)
            source = "close_price"

        # If still 0, try bid/ask average
        if ltp <= 0:
            bid = float(market_data.get("bid_price") or 0)
            ask = float(market_data.get("ask_price") or 0)
            if bid > 0 and ask > 0:
                ltp = (bid + ask) / 2
                source = "bid/ask_avg"

        print(f"[DEBUG] Strike {strike} ({opt_type}): LTP = {ltp} (from {source})")
        return ltp  # ✓ Returns real value with fallbacks

    def _build_spike_signal(self, rss_bull, rss_bear, otm_bull, otm_bear, spikes_bull, spikes_bear, strong_move) -> str:
        """Build spike signal"""
        if rss_bull and otm_bull:
            return "UP RSS+OTM" + (" STR" if strong_move else "")
        elif rss_bear and otm_bear:
            return "DN RSS+OTM" + (" STR" if strong_move else "")
        else:
            return "NEUTRAL/WAIT"

    @staticmethod
    def _ema(values: List[float], period: int = 5) -> float:
        """Calculate EMA"""
        if not values or len(values) == 0:
            return 0.0
        if len(values) == 1:
            return float(values[0])

        ema = float(values[0])
        multiplier = 2.0 / (period + 1)

        for i in range(1, len(values)):
            ema = float(values[i]) * multiplier + ema * (1 - multiplier)

        return ema

    @staticmethod
    def _stdev(values: List[float], period: int = 20) -> float:
        """Calculate standard deviation"""
        if len(values) < 2:
            return 0.0
        return float(np.std(values[-period:], ddof=1))
