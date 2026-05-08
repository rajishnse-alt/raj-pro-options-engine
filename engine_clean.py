"""
Raj Pro Options Engine - CLEAN REWRITE
Exact implementation of Pine Script logic with proper daily opening price tracking
"""

import math
from datetime import datetime, date
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass
from collections import deque
import numpy as np


@dataclass
class Signal:
    """Signal output"""
    name: str
    confidence: float
    dominance: float
    momentum: float
    volatility: float
    call_erosion: float
    put_erosion: float
    trend: str
    color: str


class RajProEngine:
    """
    Raj Pro Options Engine - Exact Pine Script conversion
    Properly tracks daily opening prices for erosion calculation
    """

    def __init__(self):
        # Daily opening price tracking (CRITICAL!)
        self.daily_opens: Dict[int, Tuple[float, float]] = {}  # {strike: (ce_open, pe_open)}
        self.current_date: Optional[date] = None

        # History tracking
        self.dominance_history = deque(maxlen=50)
        self.ce_erosion_history = deque(maxlen=50)
        self.pe_erosion_history = deque(maxlen=50)
        self.momentum_history = deque(maxlen=50)

        # Trend tracking
        self.bull_bars = 0
        self.bear_bars = 0
        self.prev_momentum_sign = 0.0

    def process(
        self,
        chain_data: List[Dict],
        underlying_price: float,
        strike_gap: float,
        symbol: str = "NIFTY",
        threshold: float = 0.04,
    ) -> Signal:
        """
        Process options chain and generate signal

        Args:
            chain_data: Upstox options chain data
            underlying_price: Current spot price
            strike_gap: Strike spacing (50 for NIFTY, 100 for BANKNIFTY, etc.)
            symbol: Underlying symbol
            threshold: Dominance threshold for signal (default 0.04)

        Returns:
            Signal object with all metrics
        """

        # Step 1: CHECK IF DAY CHANGED (like Pine Script nDay)
        today = date.today()
        day_changed = self.current_date != today

        if day_changed:
            self.daily_opens = {}  # Reset daily opens
            self.current_date = today

        # Step 2: EXTRACT PREMIUMS FROM CHAIN DATA
        premiums = self._extract_premiums(chain_data)

        if not premiums:
            return Signal(
                name="NO_DATA",
                confidence=0.0,
                dominance=0.0,
                momentum=0.0,
                volatility=0.0,
                call_erosion=0.0,
                put_erosion=0.0,
                trend="NEUTRAL",
                color="gray",
            )

        # Step 3: STORE OPENING PRICES ON FIRST OBSERVATION OF DAY
        for strike, (ce_price, ce_oi, pe_price, pe_oi) in premiums.items():
            if strike not in self.daily_opens:
                # First time seeing this strike today = opening price!
                self.daily_opens[strike] = (ce_price, pe_price)

        # Step 4: CALCULATE EROSION FROM DAY'S OPENING PRICES
        # erosion = (opening_price - current_price) / opening_price
        call_erosion = self._calculate_call_erosion(premiums)
        put_erosion = self._calculate_put_erosion(premiums)

        # Step 5: CALCULATE DOMINANCE
        # dominance = put_erosion - call_erosion
        dominance = put_erosion - call_erosion
        self.dominance_history.append(dominance)
        self.ce_erosion_history.append(call_erosion)
        self.pe_erosion_history.append(put_erosion)

        # Step 6: CALCULATE MOMENTUM (EMA-based)
        # momentum = EMA(put_erosion) - EMA(call_erosion)
        call_ema = self._ema(self.ce_erosion_history, period=5)
        put_ema = self._ema(self.pe_erosion_history, period=5)
        momentum = put_ema - call_ema
        self.momentum_history.append(momentum)

        # Step 7: CALCULATE VOLATILITY
        volatility = self._stdev(self.dominance_history, period=20)
        if volatility <= 0:
            volatility = threshold

        # Step 8: DETECT TREND
        # Count consecutive bullish/bearish bars
        if momentum > 0:
            self.bull_bars += 1
            self.bear_bars = 0
        elif momentum < 0:
            self.bear_bars += 1
            self.bull_bars = 0
        else:
            self.bull_bars = 0
            self.bear_bars = 0

        # Step 9: GENERATE SIGNAL
        signal_name, confidence, trend_type, color = self._build_signal(
            dominance, momentum, volatility, threshold
        )

        return Signal(
            name=signal_name,
            confidence=confidence,
            dominance=dominance,
            momentum=momentum,
            volatility=volatility,
            call_erosion=call_erosion,
            put_erosion=put_erosion,
            trend=trend_type,
            color=color,
        )

    def _extract_premiums(self, chain_data: List[Dict]) -> Dict[int, Tuple[float, float, float, float]]:
        """Extract CE/PE premiums from Upstox format"""
        premiums = {}
        for row in chain_data:
            try:
                strike = int(float(row.get("strike_price", 0)))
                if strike <= 0:
                    continue

                call_md = (row.get("call_options") or {}).get("market_data") or {}
                put_md = (row.get("put_options") or {}).get("market_data") or {}

                ce_price = float(call_md.get("ltp") or 0)
                ce_oi = float(call_md.get("oi") or 0)
                pe_price = float(put_md.get("ltp") or 0)
                pe_oi = float(put_md.get("oi") or 0)

                if ce_price > 0 and pe_price > 0:
                    premiums[strike] = (ce_price, ce_oi, pe_price, pe_oi)
            except (ValueError, TypeError):
                continue

        return premiums

    def _calculate_call_erosion(self, premiums: Dict) -> float:
        """Calculate average CE erosion from daily opening"""
        total = 0.0
        count = 0

        for strike, (ce_price, _, _, _) in premiums.items():
            if strike in self.daily_opens:
                ce_open = self.daily_opens[strike][0]
                if ce_open > 0:
                    erosion = (ce_open - ce_price) / ce_open
                    total += erosion
                    count += 1

        return total / count if count > 0 else 0.0

    def _calculate_put_erosion(self, premiums: Dict) -> float:
        """Calculate average PE erosion from daily opening"""
        total = 0.0
        count = 0

        for strike, (_, _, pe_price, _) in premiums.items():
            if strike in self.daily_opens:
                pe_open = self.daily_opens[strike][1]
                if pe_open > 0:
                    erosion = (pe_open - pe_price) / pe_open
                    total += erosion
                    count += 1

        return total / count if count > 0 else 0.0

    def _build_signal(
        self, dominance: float, momentum: float, volatility: float, threshold: float
    ) -> Tuple[str, float, str, str]:
        """Generate signal name, confidence, trend, and color"""

        # Determine trend
        is_bull = self.bull_bars >= 3
        is_bear = self.bear_bars >= 3

        # Determine signal strength
        dom_strong = abs(dominance) > threshold
        mom_strong = abs(momentum) > volatility * 1.2

        # Generate signal
        if is_bull and dominance > 0:
            if dom_strong and mom_strong:
                return ("UP_CONFIRMED", 0.9, "BULL", "green")
            elif dom_strong:
                return ("UP_BUILDING", 0.7, "BULL", "green")
            else:
                return ("UP_PENDING", 0.5, "BULL", "green")

        elif is_bear and dominance < 0:
            if dom_strong and mom_strong:
                return ("DN_CONFIRMED", 0.9, "BEAR", "red")
            elif dom_strong:
                return ("DN_BUILDING", 0.7, "BEAR", "red")
            else:
                return ("DN_PENDING", 0.5, "BEAR", "red")

        else:
            return ("NEUTRAL/WAIT", 0.3, "NEUTRAL", "gray")

    @staticmethod
    def _ema(values: deque, period: int = 5) -> float:
        """Calculate EMA"""
        if len(values) == 0:
            return 0.0
        if len(values) == 1:
            return values[0]

        values_list = list(values)
        ema = values_list[0]
        multiplier = 2.0 / (period + 1)

        for i in range(1, len(values_list)):
            ema = values_list[i] * multiplier + ema * (1 - multiplier)

        return ema

    @staticmethod
    def _stdev(values: deque, period: int = 20) -> float:
        """Calculate standard deviation"""
        if len(values) < 2:
            return 0.0
        return float(np.std(list(values)[-period:], ddof=1))
