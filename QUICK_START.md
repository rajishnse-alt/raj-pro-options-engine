# Quick Fix Guide - Premium Extraction Issue

## The Problem
✗ App shows: Dominance: `+0.0000`, Momentum: `+0.0000`, Volatility: `0.0000`
✓ Pine Script shows: Dominance: `-2.50`, Momentum: `0.15`, Volatility: `0.45`

## The Fix (What I Did)
Added intelligent premium extraction to handle different Upstox data formats.

## What You Need to Do

### Option 1: Check Cloud Logs (2 minutes)
```
1. Go to https://share.streamlit.io
2. Click your app name
3. Click "Manage App"
4. Click "View Logs"
5. Scroll and find [DEBUG] messages
6. Look for: "Extracted premiums - CE: ..."
7. If you see numbers > 0, it's WORKING ✓
8. If you see "None", send me the debug output ✗
```

### Option 2: Run Local Debug (5 minutes)
```bash
cd /home/rajish/Documents/Trading/opt_analysis
python debug_upstox.py

# You'll be asked for:
# - API Key
# - API Secret
# - Redirect URI
# - Auth Code (from browser)

# It will show you the exact JSON structure from Upstox
```

## What to Look For

### Good Output (Means it's working)
```
[DEBUG] Extracted premiums - CE: 125.5, 85.25, 45.10, 28.75 | PE: 132.0, 95.50, 58.75, 35.25
[DEBUG] Available strikes in chain: [23700, 23750, 23800, ...]
```
→ **Action**: App should now show correct dominance/momentum values

### Bad Output (Premium extraction failing)
```
[DEBUG] Extracted premiums - CE: None, None, None, None | PE: None, None, None, None
[DEBUG] Strike 23900 (call) - NO LTP FOUND
```
→ **Action**: Run `debug_upstox.py` and share the JSON output with me

## Deploy the Fix

If using GitHub + Streamlit Cloud:
```bash
cd /home/rajish/Documents/Trading
git add -A
git commit -m "Add debug logging for premium extraction"
git push
# Streamlit Cloud auto-deploys within 1-2 minutes
```

## Expected Timeline

- **Now**: Deploy changes
- **1-2 min**: Streamlit Cloud rebuilds app
- **2-3 min**: Check logs or run debug script
- **If working ✓**: Done!
- **If not working ✗**: Share debug output → I fix code → Repeat

## Files Changed/Created

**Modified:**
- `engine_exact.py` - Added premium extraction logic
- `app.py` - Added debug toggle (minor)

**Created:**
- `debug_upstox.py` - Standalone debug tool
- `DEBUG_INSTRUCTIONS.md` - Full guide
- `CHANGES_MADE.md` - Detailed changelog
- `QUICK_START.md` - This file

## Support

If you see `[DEBUG]` output mentioning "NOT FOUND" or "NO LTP FOUND":
1. Run `python debug_upstox.py`
2. Copy the entire output
3. Send to me

I'll update the code to handle your specific Upstox response format.

---

**TL;DR**: Deploy → Check logs for `[DEBUG] Extracted premiums` → If numbers show up, problem solved! If not, run `debug_upstox.py` and share output.
