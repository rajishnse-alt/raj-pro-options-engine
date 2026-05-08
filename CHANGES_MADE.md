# Changes Made to Fix Premium Extraction Issue

## Problem Summary
The Streamlit app shows all `+0.0000` values for dominance, momentum, and volatility instead of real values from the Pine Script indicator.

## Root Cause
The premium values (LTP - Last Traded Price) are not being extracted from Upstox API response, causing:
- All erosion calculations to be 0 (can't calculate erosion without premiums)
- All derived metrics (dominance, momentum, volatility, etc.) to be 0
- Signals to default to "NEUTRAL/WAIT" with 0.0000 confidence

## Changes Made

### 1. **engine_exact.py** - Enhanced Premium Extraction

#### Added Debug Logging (Lines 129-168)
```python
print(f"[DEBUG] {symbol} - Underlying: {underlying_price}, ATM Strike: {atm_strike}, Gap: {strike_gap}")
print(f"[DEBUG] Looking for CE strikes: {ce_strikes}")
print(f"[DEBUG] Looking for PE strikes: {pe_strikes}")
print(f"[DEBUG] Available strikes in chain: {sorted(available_strikes)[:10]}")
print(f"[DEBUG] Extracted premiums - CE: {ce1N}, {ce2N}, {ce3N}, {ce4N} | PE: {pe1N}, {pe2N}, {pe3N}, {pe4N}")
```

This helps identify:
- What strikes the code is looking for
- What strikes exist in the actual data
- Whether premiums are being extracted
- Where the extraction fails

#### Improved Strike Price Parsing (Lines 144-155)
```python
# Now tries multiple possible field names for strike price
strike_val = (row.get("strike_price") or 
             row.get("strikePrice") or 
             row.get("strike") or 
             row.get("Strike") or 0)
```

#### Completely Rewrote _get_premium() Method (Lines 354-419)
Now handles multiple data structure variations:

**Alternative Field Names:**
- Strike: `strike_price`, `strikePrice`, `strike`, `Strike`
- Call Options: `call_options`, `callOptions`, `ce`, `CE`
- Put Options: `put_options`, `putOptions`, `pe`, `PE`

**Alternative LTP Locations:**
1. `opt_data.market_data.ltp` (expected)
2. `opt_data.ltp` (direct)
3. `opt_data.last_price` (alternative)
4. `opt_data.price` (alternative)
5. `opt_data.close` (alternative)

**Also Tries Case Variations:**
- `ltp`, `LTP`, `Ltp`
- `lastPrice`, `lastprice`

Each attempt prints debug info showing:
- Whether data was found
- Where it was found
- What value was extracted
- Why it failed (if it did)

### 2. **debug_upstox.py** - New Debug Tool

Created a standalone Python script that:
- Takes Upstox API credentials as input
- Fetches actual option chain data
- Displays the exact JSON structure
- Shows what strikes exist
- Shows whether your target strikes exist
- No need to check server logs

**Usage:**
```bash
python debug_upstox.py
```

### 3. **DEBUG_INSTRUCTIONS.md** - User Guide

Comprehensive debugging guide with:
- How to check Streamlit Cloud logs
- How to run the debug script locally
- What the debug output means
- What data structure the code expects
- Troubleshooting steps

### 4. **app.py** - Minor Updates

Added debug toggle to sidebar:
```python
show_debug = st.checkbox("🐛 Show Debug Info", value=False)
```

(Currently just shows label, actual debug output goes to console/logs)

## How to Debug

### Step 1: Get Debug Output
**Option A - Streamlit Cloud Logs:**
1. Go to https://share.streamlit.io
2. Click your app → Settings → Manage App
3. Check the Logs/Terminal section

**Option B - Run Debug Script:**
```bash
cd /home/rajish/Documents/Trading/opt_analysis
python debug_upstox.py
```

### Step 2: Look for Key Information
The debug output will show:
```
[DEBUG] NIFTY - Underlying: 23842.5, ATM Strike: 23850, Gap: 50
[DEBUG] Available strikes in chain: [23700, 23750, 23800, 23850, 23900, ...]
[DEBUG] Extracted premiums - CE: 125.5, 85.25, 45.10, 28.75 | PE: 132.0, 95.50, 58.75, 35.25
```

- ✓ If you see premium values > 0, extraction is working
- ✗ If you see `None` values, look at the `[DEBUG]` messages explaining why

### Step 3: Share Output
If premiums aren't being extracted:
1. Share the debug output
2. Or run `debug_upstox.py` and share the JSON structure
3. I'll update the code to handle the actual Upstox data format

## Expected Results After Fix

Once premiums are correctly extracted, you should see:
- **Dominance**: Values like -2.50 to +2.50 (not 0.0000)
- **Momentum**: Values like -0.15 to +0.15 (not 0.0000)
- **Volatility**: Values like 0.05 to 0.50 (not 0.0000)
- **Signals**: "UP RSS+OTM", "DN RSS+OTM", or "NEUTRAL/WAIT" (not always NEUTRAL)
- **Confidence**: Values like 30-100% (not always 30%)

## Files Modified

1. `engine_exact.py` - Core engine with debug logging
2. `app.py` - Added debug toggle (minor change)

## Files Created

1. `debug_upstox.py` - Standalone debug tool
2. `DEBUG_INSTRUCTIONS.md` - User guide
3. `CHANGES_MADE.md` - This file

## Next Steps

1. **Run the app** and check Streamlit Cloud logs OR run `debug_upstox.py`
2. **Share the [DEBUG] output** or JSON structure from debug script
3. **I'll update the code** to handle the actual Upstox response format
4. **Deploy updated code** and test with live data

## Deployment Notes

If deploying to Streamlit Cloud:
1. Push changes to GitHub repo
2. Streamlit Cloud auto-deploys
3. Check app and look at logs
4. Share debug output for analysis

Current repo: `https://github.com/rajishnse-alt/raj-pro-options-engine.git`
