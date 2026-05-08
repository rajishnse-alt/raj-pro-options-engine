"""
Raj Pro Options Engine - EXACT Pine Script v6 Implementation
Line-by-line conversion matching Pine Script indicator 100%
"""

import math
import numpy as np
from datetime import datetime, date, timedelta
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass
from collections import deque


@dataclass
class Signal:
    """Complete signal output matching Pine Script exactly"""
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
    median: float


def norm_cdf(x):
    """Normal CDF - Abramowitz & Stegun approximation (matches Pine Script exactly)"""
    t = 1.0 / (1.0 + 0.2316419 * abs(x))
    d = 0.3989423 * math.exp(-x * x / 2.0)
    p = d * t * (0.3193815 + t * (-0.3565638 + t * (1.7814779 + t * (-1.8212560 + t * 1.3302744))))
    return 1.0 - p if x >= 0.0 else p


def call_delta(S, K, T_yr, sigma):
    """Black-Scholes call delta matching Pine Script"""
    if S <= 0 or K <= 0 or T_yr <= 0 or sigma <= 0:
        return 0.5
    try:
        d1 = (math.log(S / K) + 0.5 * sigma * sigma * T_yr) / (sigma * math.sqrt(T_yr))
        return norm_cdf(d1)
    except:
        return 0.5


class RajProEngine:
    """
    Exact Pine Script v6 implementation
    Line-by-line conversion from Pine Script indicator
    """

    # Strike gaps by instrument (from Pine Script)
    STRIKE_GAPS = {
        "NIFTY": 50,
        "BANKNIFTY": 100,
        "FINNIFTY": 50,
        "MIDCPNIFTY": 25,
    }

    # Default ATM strikes (from Pine Script)
    DEFAULT_ATMS = {
        "NIFTY": 24000,
        "BANKNIFTY": 55000,
        "FINNIFTY": 24000,
        "MIDCPNIFTY": 12000,
    }

    def __init__(self):
        """Initialize engine with Pine Script defaults"""
        # ===== PINE SCRIPT INPUTS =====
        self.thr = 0.04  # Dominance threshold
        self.trendEmaLen = 5  # Trend EMA length
        self.trendConfBars = 3  # Bars to confirm trend
        self.revConfBars = 2  # Reversal confirmation bars
        self.strongMoveCoeff = 1.2  # Strong move sensitivity
        self.domConfBars = 2  # Dominance confluence bars
        self.spikeEdgeMin = 0.01  # Minimum spike edge

        # ===== DAY OPEN PREMIUM STORAGE (var in Pine Script) =====
        self.ce1O = None  # Opening premium CE1
        self.ce2O = None
        self.ce3O = None
        self.ce4O = None
        self.pe1O = None  # Opening premium PE1
        self.pe2O = None
        self.pe3O = None
        self.pe4O = None
        self.current_date = None

        # ===== HISTORY TRACKING =====
        self.dominance_history = deque(maxlen=50)
        self.ce_erosion_history = deque(maxlen=50)
        self.pe_erosion_history = deque(maxlen=50)
        self.mD_history = deque(maxlen=50)  # Momentum history
        self.vol_history = deque(maxlen=20)  # Volatility history (stdev uses 20)

        # ===== TREND TRACKING (from Pine Script) =====
        self.bull_bars = 0
        self.bear_bars = 0
        self.reversal_count = 0
        self.prev_trend_sign = 0.0
        self.dom_rising_count = 0
        self.dom_falling_count = 0
        self.confirmed_trend = "neutral"  # Pine Script: var string

    def process(
        self,
        chain_data: List[Dict],
        underlying_price: float,
        opening_price: float,  # NEW: opening price from API
        strike_gap: int,
        symbol: str = "NIFTY",
        expiry_date: Optional[str] = None,
        opening_premiums: Optional[Dict] = None,  # NEW: persistent opening premiums from session state
    ) -> Signal:
        """
        EXACT Pine Script pipeline
        """

        # ===== STEP 1: DAY CHANGE DETECTION =====
        today = date.today()
        nDay = self.current_date != today

        if nDay:
            # Reset all day-open variables (Pine Script: var logic)
            self.ce1O = None
            self.ce2O = None
            self.ce3O = None
            self.ce4O = None
            self.pe1O = None
            self.pe2O = None
            self.pe3O = None
            self.pe4O = None
            self.current_date = today
            print(f"[DEBUG] Day changed - resetting opening premiums")

        # ===== STEP 2: STRIKE GAP & ATM CALCULATION (matching Pine Script) =====
        sGap = strike_gap
        iGap = int(sGap)

        # ATM Strike - Dynamic (matches Pine Script if barstate.isrealtime or barstate.islast)
        # Uses opening price first, then current price
        _base = opening_price if opening_price > 0 else underlying_price
        atm_strike = int(sGap * round(_base / sGap))

        # ATM Open - For opening-based ATM
        atm_O = int(sGap * round(opening_price / sGap)) if opening_price > 0 else atm_strike

        ceS = atm_strike
        peS = atm_strike

        print(f"\n{'='*80}")
        print(f"[DEBUG] {symbol} - ATM: {atm_strike}, ATM_Open: {atm_O}, Gap: {sGap}")
        print(f"[DEBUG] Spot: {underlying_price:.2f}, Opening: {opening_price:.2f}")
        print(f"{'='*80}\n")

        # ===== STEP 3: OTM STRIKES =====
        ce_strikes = [ceS + i * iGap for i in range(1, 5)]  # CE1, CE2, CE3, CE4
        pe_strikes = [peS - i * iGap for i in range(1, 5)]  # PE1, PE2, PE3, PE4

        # ===== STEP 4: EXTRACT PREMIUMS FROM CHAIN =====
        chain_dict = {}
        for row in chain_data:
            try:
                strike = int(float(row.get("strike_price", 0)))
                if strike > 0:
                    chain_dict[strike] = row
            except (ValueError, TypeError):
                continue

        # Get premiums with fallback logic
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

        # ===== STEP 5: CALCULATE MEDIAN (Pine Script exact) =====
        vc = 0
        sp = 0.0
        for prem in [ce1N, ce2N, ce3N, ce4N, pe1N, pe2N, pe3N, pe4N]:
            if prem > 0:
                vc += 1
                sp += prem

        median = sp / vc if vc > 0 else 0.0
        print(f"[DEBUG] Median calculation: sum={sp:.2f}, count={vc}, median={median:.4f}")

        # ===== STEP 6: STORE DAY OPEN PREMIUMS (Pine Script: var logic) =====
        # Use opening premiums from session state if available (persistent across runs)
        if opening_premiums:
            # Load from session state (previous run's stored values)
            self.ce1O = opening_premiums.get("ce1O") or (ce1N if self.ce1O is None else self.ce1O)
            self.ce2O = opening_premiums.get("ce2O") or (ce2N if self.ce2O is None else self.ce2O)
            self.ce3O = opening_premiums.get("ce3O") or (ce3N if self.ce3O is None else self.ce3O)
            self.ce4O = opening_premiums.get("ce4O") or (ce4N if self.ce4O is None else self.ce4O)
            self.pe1O = opening_premiums.get("pe1O") or (pe1N if self.pe1O is None else self.pe1O)
            self.pe2O = opening_premiums.get("pe2O") or (pe2N if self.pe2O is None else self.pe2O)
            self.pe3O = opening_premiums.get("pe3O") or (pe3N if self.pe3O is None else self.pe3O)
            self.pe4O = opening_premiums.get("pe4O") or (pe4N if self.pe4O is None else self.pe4O)
            print(f"[DEBUG] Loaded opening premiums from session state")
        else:
            # New day or first run - initialize from current premiums
            self.ce1O = ce1N if nDay or self.ce1O is None else self.ce1O
            self.ce2O = ce2N if nDay or self.ce2O is None else self.ce2O
            self.ce3O = ce3N if nDay or self.ce3O is None else self.ce3O
            self.ce4O = ce4N if nDay or self.ce4O is None else self.ce4O
            self.pe1O = pe1N if nDay or self.pe1O is None else self.pe1O
            self.pe2O = pe2N if nDay or self.pe2O is None else self.pe2O
            self.pe3O = pe3N if nDay or self.pe3O is None else self.pe3O
            self.pe4O = pe4N if nDay or self.pe4O is None else self.pe4O

        print(f"[DEBUG] Opening premiums: CE={self.ce1O:.2f}, PE={self.pe1O:.2f}")

        # ===== STEP 7: CALCULATE EROSION (Pine Script exact formula) =====
        # erosion = (opening - current) / opening
        ce1E = (self.ce1O - ce1N) / self.ce1O if (self.ce1O and self.ce1O != 0) else 0.0
        ce2E = (self.ce2O - ce2N) / self.ce2O if (self.ce2O and self.ce2O != 0) else 0.0
        ce3E = (self.ce3O - ce3N) / self.ce3O if (self.ce3O and self.ce3O != 0) else 0.0
        ce4E = (self.ce4O - ce4N) / self.ce4O if (self.ce4O and self.ce4O != 0) else 0.0
        pe1E = (self.pe1O - pe1N) / self.pe1O if (self.pe1O and self.pe1O != 0) else 0.0
        pe2E = (self.pe2O - pe2N) / self.pe2O if (self.pe2O and self.pe2O != 0) else 0.0
        pe3E = (self.pe3O - pe3N) / self.pe3O if (self.pe3O and self.pe3O != 0) else 0.0
        pe4E = (self.pe4O - pe4N) / self.pe4O if (self.pe4O and self.pe4O != 0) else 0.0

        print(f"[DEBUG] Erosion calculation:")
        print(f"[DEBUG] CE1: ({self.ce1O:.2f} - {ce1N:.2f}) / {self.ce1O:.2f} = {ce1E:.4f}")
        print(f"[DEBUG] PE1: ({self.pe1O:.2f} - {pe1N:.2f}) / {self.pe1O:.2f} = {pe1E:.4f}")

        # ===== STEP 8: AVERAGE EROSIONS =====
        cE = (ce1E + ce2E + ce3E + ce4E) / 4
        pE = (pe1E + pe2E + pe3E + pe4E) / 4

        # ===== STEP 9: DOMINANCE (the key!) =====
        dom = pE - cE
        self.dominance_history.append(dom)
        self.ce_erosion_history.append(cE)
        self.pe_erosion_history.append(pE)

        print(f"[DEBUG] Erosion: cE={cE:.4f}, pE={pE:.4f}, Dominance={dom:.4f}")

        # ===== STEP 10: MOMENTUM (EMA of erosion) =====
        call_ema = self._ema(list(self.ce_erosion_history), self.trendEmaLen)
        put_ema = self._ema(list(self.pe_erosion_history), self.trendEmaLen)
        mD = put_ema - call_ema
        self.mD_history.append(mD)

        print(f"[DEBUG] EMA: callEMA={call_ema:.4f}, putEMA={put_ema:.4f}, Momentum={mD:.4f}")

        # ===== STEP 11: VOLATILITY (stdev of dominance) =====
        vol = self._stdev(list(self.dominance_history), period=20)
        vol = vol if vol > 0 else self.thr

        # ===== STEP 12: STRONG MOVE =====
        strong_move = abs(mD) > vol * self.strongMoveCoeff

        # ===== STEP 13: REVERSAL COUNTER =====
        cur_sign = 1.0 if mD > 0 else (-1.0 if mD < 0 else 0.0)
        if self.prev_trend_sign != 0 and cur_sign != 0 and cur_sign != self.prev_trend_sign:
            self.reversal_count += 1
        else:
            self.reversal_count = 0
        early_reversal = self.reversal_count >= self.revConfBars

        # ===== STEP 14: DOMINANCE CONFLUENCE =====
        prev_dom = self.dominance_history[-2] if len(self.dominance_history) > 1 else dom
        self.dom_rising_count = self.dom_rising_count + 1 if dom > prev_dom else 0
        self.dom_falling_count = self.dom_falling_count + 1 if dom < prev_dom else 0

        dom_conf_up = self.dom_rising_count >= self.domConfBars
        dom_conf_down = self.dom_falling_count >= self.domConfBars

        # ===== STEP 15: TREND DETECTION (bar-count gated) =====
        if mD > 0:
            self.bull_bars += 1
            self.bear_bars = 0
        elif mD < 0:
            self.bear_bars += 1
            self.bull_bars = 0
        else:
            self.bull_bars = 0
            self.bear_bars = 0

        if self.bull_bars >= self.trendConfBars and dom_conf_up:
            self.confirmed_trend = "bull"
            self.prev_trend_sign = 1.0
        elif self.bear_bars >= self.trendConfBars and dom_conf_down:
            self.confirmed_trend = "bear"
            self.prev_trend_sign = -1.0

        # ===== STEP 16: GAMMA SCORE (from Pine Script) =====
        dist_from_atm = abs(underlying_price - float(atm_strike))
        gamma_score = 100.0 / (1.0 + (dist_from_atm / max(sGap, 1.0)))

        # ===== STEP 17: SPIKE SCORES (from Pine Script) =====
        buf = sGap * 0.25
        ce_bias = 1.2 if underlying_price > (atm_strike + buf) else (0.8 if underlying_price < (atm_strike - buf) else 1.0)
        pe_bias = 1.2 if underlying_price < (atm_strike - buf) else (0.8 if underlying_price > (atm_strike + buf) else 1.0)

        ce_spike_score = gamma_score * (1.0 + abs(cE) * 10.0) * ce_bias
        pe_spike_score = gamma_score * (1.0 + abs(pE) * 10.0) * pe_bias
        score_diff = ce_spike_score - pe_spike_score

        spikes_bull = score_diff < -self.spikeEdgeMin
        spikes_bear = score_diff > self.spikeEdgeMin

        # ===== STEP 18: BUILD SIGNALS =====
        rss_bull = self.confirmed_trend == "bull"
        rss_bear = self.confirmed_trend == "bear"
        otm_bull = mD > 0
        otm_bear = mD < 0

        # Build spike signal (matching Pine Script logic)
        spike_signal = self._build_spike_signal(
            rss_bull, rss_bear, otm_bull, otm_bear, spikes_bull, spikes_bear, strong_move
        )

        # Determine core trend string
        if self.bull_bars >= self.trendConfBars and not dom_conf_up:
            core_trend = "UP PENDING"
        elif self.bear_bars >= self.trendConfBars and not dom_conf_down:
            core_trend = "DN PENDING"
        elif self.confirmed_trend == "bull":
            if strong_move:
                core_trend = "UP STR REV" if early_reversal else "UP STRONG"
            else:
                core_trend = "UP REV" if early_reversal else "UP"
        elif self.confirmed_trend == "bear":
            if strong_move:
                core_trend = "DN STR REV" if early_reversal else "DN STRONG"
            else:
                core_trend = "DN REV" if early_reversal else "DN"
        else:
            core_trend = "NEUTRAL"

        # Signal name
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
            dominance=dom,
            momentum=mD,
            volatility=vol,
            call_erosion=cE,
            put_erosion=pE,
            trend=self.confirmed_trend.upper(),
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
        opt_data = row.get("call_options" if opt_type == "call" else "put_options") or {}
        market_data = opt_data.get("market_data") or {}

        # Tier 1: Try LTP
        ltp = float(market_data.get("ltp") or 0)
        source = "ltp"

        # Tier 2: Fallback to close_price
        if ltp <= 0:
            ltp = float(market_data.get("close_price") or 0)
            source = "close_price"

        # Tier 3: Fallback to bid/ask average
        if ltp <= 0:
            bid = float(market_data.get("bid_price") or 0)
            ask = float(market_data.get("ask_price") or 0)
            if bid > 0 and ask > 0:
                ltp = (bid + ask) / 2
                source = "bid/ask_avg"

        print(f"[DEBUG] Strike {strike} ({opt_type}): LTP = {ltp:.2f} (from {source})")
        return ltp

    def _build_spike_signal(self, rss_bull, rss_bear, otm_bull, otm_bear, spikes_bull, spikes_bear, strong_move) -> str:
        """Build spike signal matching Pine Script"""
        if rss_bull and otm_bull:
            return "UP RSS+OTM" + (" STR" if strong_move else "")
        elif rss_bear and otm_bear:
            return "DN RSS+OTM" + (" STR" if strong_move else "")
        else:
            return "NEUTRAL/WAIT"

    @staticmethod
    def _ema(values: List[float], period: int = 5) -> float:
        """Calculate EMA matching Pine Script"""
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
        """Calculate standard deviation matching Pine Script"""
        if len(values) < 2:
            return 0.0
        return float(np.std(values[-period:], ddof=1))
