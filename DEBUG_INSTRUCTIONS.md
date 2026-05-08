# Debugging Guide - Premium Extraction Issues

## Problem
The Streamlit app is showing all `+0.0000` values for dominance, momentum, and volatility instead of the expected values like `-2.50` and `0.11` shown in the Pine Script indicator.

## Root Cause Analysis
The premium values (LTP - Last Traded Price) are not being extracted from the Upstox API response. This could be because:
1. The Upstox data structure differs from what the code expects
2. The field names for strike prices, options data, or LTP values are different
3. The specific OTM strikes requested don't exist in the chain data

## Solutions

### Option 1: Check Streamlit Cloud Logs (Easiest)

1. Go to https://share.streamlit.io
2. Find your deployed app "raj-pro-options-engine"
3. Click on the app → Settings → Manage App
4. Look for a "Logs" or "Terminal" section
5. The app output will show `[DEBUG]` lines with detailed information about:
   - What strikes it's looking for
   - What strikes exist in the data
   - What premium values were extracted
   - Why extraction failed (if it did)

### Option 2: Run Debug Script Locally (More Detailed)

```bash
cd /home/rajish/Documents/Trading/opt_analysis
python debug_upstox.py
```

The script will:
1. Ask for your Upstox API credentials
2. Fetch the option chain data
3. Show you the EXACT JSON structure returned by Upstox
4. Show which strikes exist in the data
5. Show whether the strikes you're looking for are available

### Option 3: Check Engine Code

I've added comprehensive debug logging to `engine_exact.py`:
- Line 129-168: Shows what strikes it's looking for and finds
- Line 350-400: Shows how it extracts LTP values from the nested data structure

## Debug Output Explained

When the app runs, you'll see output like:

```
[DEBUG] NIFTY - Underlying: 23842.5, ATM Strike: 23850, Gap: 50
[DEBUG] Looking for CE strikes: [23900, 23950, 24000, 24050]
[DEBUG] Looking for PE strikes: [23800, 23750, 23700, 23650]
[DEBUG] Total chain rows received: 234
[DEBUG] Available strikes in chain: [23800, 23850, 23900, 23950, ...]
[DEBUG] Extracted premiums - CE: 125.5, 85.25, 45.10, None | PE: 132.0, 95.50, 58.75, None
```

This tells you:
- ✓ ATM strike was calculated correctly (23850)
- ✓ OTM strikes were found in the chain
- ✓ Premiums were extracted successfully
- ✗ Or shows which strikes/premiums are missing

## Next Steps

1. **If using Option 1 (Cloud Logs)**: Share the `[DEBUG]` output with me
2. **If using Option 2 (Local Script)**: Run it and share the JSON structure output
3. **Once we see the actual data structure**, I'll update the code to handle it correctly

## What the Code is Looking For

### Data Structure Expected

```
chain_data = [
  {
    "strike_price": 23900,
    "call_options": {
      "market_data": {
        "ltp": 125.5  ← This is what we extract
      }
    },
    "put_options": {
      "market_data": {
        "ltp": 132.0  ← This is what we extract
      }
    },
    ...other fields...
  },
  ...more strikes...
]
```

The code now also tries alternate field names:
- `strikePrice`, `strike`, `Strike` (in addition to `strike_price`)
- `callOptions`, `ce`, `CE` (in addition to `call_options`)
- `putOptions`, `pe`, `PE` (in addition to `put_options`)
- `lastPrice`, `price`, `close` (in addition to `ltp` in various cases)
- Case variations: `LTP`, `Ltp`

## Important Notes

1. The Pine Script indicator shows dominance values around **-2.50** to **+2.50**
2. Median values should be around **0.11** to **5.00**
3. These are calculated from 8 premium values (4 call OTM + 4 put OTM)
4. If all values are 0, then premiums aren't being extracted at all

## Immediate Action

If the app is already deployed, please:
1. Run it once and check Streamlit Cloud logs
2. Or run the `debug_upstox.py` script locally
3. Share the debug output so I can identify the exact data structure
