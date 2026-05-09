# Bug Fixes Applied - Raj Pro Options Engine

## Summary
Fixed critical issues causing cache depletion errors and application failures:
1. **KeyError: 0** when accessing candles[0]
2. **Streamlit deprecation warnings** with `use_container_width`
3. **PyArrow serialization errors** with mixed "—" and numeric values

---

## Issue #1: KeyError: 0 - Candle Data Structure

### Problem
```python
# Line 457 in app.py (OLD)
first_candle = candles[0]  # ❌ KeyError: 0
```

The Upstox API returns candle data in a nested structure that could be:
- **Dict with "candles" key:** `{"candles": [[...], [...]]}`
- **List directly:** `[[...], [...]]`

But the code assumed it was always a list-indexed structure.

### Root Cause
When Upstox API returns `data = {"candles": [...]}`, trying to access `candles[0]` where `candles` is a dict causes `KeyError: 0` because Python tries to find a dictionary key "0" instead of list index 0.

### Solution
Added proper type checking and nested structure handling in `fetch_historical_candles()`:

```python
# NEW CODE (Lines 225-242)
if d.get("status") == "success" and d.get("data"):
    data = d["data"]

    # Handle nested structure: data might be {"candles": [...]} or just [...]
    if isinstance(data, dict) and "candles" in data:
        candles = data["candles"]
    elif isinstance(data, list):
        candles = data
    else:
        print(f"[ERROR] Unexpected data structure: {type(data)}")
        return None, f"Unexpected data structure: {type(data)}"

    if candles and len(candles) > 0:
        print(f"[DEBUG] Got {len(candles)} candles for {symbol} on {date_str}")
        print(f"[DEBUG] First candle: {candles[0]}")  # ✓ Now safe
        return candles, None
```

Also improved the candle extraction logic (Lines 468-501):

```python
# NEW: Type-safe candle access
if candles and isinstance(candles, list) and len(candles) > 0:
    first_candle = candles[0]
    
    # Handle both list and dict candle formats
    if isinstance(first_candle, list) and len(first_candle) >= 2:
        opening_price = float(first_candle[1])  # [timestamp, open, high, low, close, vol, oi]
    elif isinstance(first_candle, dict):
        opening_price = float(first_candle.get("open", 0))
```

---

## Issue #2: Streamlit Deprecation - use_container_width

### Problem
```python
# OLD (3 occurrences)
st.dataframe(df, use_container_width=True, height=300)  # ⚠️ Deprecated
st.dataframe(delta_df, hide_index=True, use_container_width=True)  # ⚠️ Deprecated
if st.button("🔄 Refresh Data (Manual)", use_container_width=True):  # ⚠️ Deprecated
```

Streamlit deprecated `use_container_width=True` in favor of the newer `width='stretch'` parameter.

### Impact
- Warning messages in logs (cache depletion potential)
- Future incompatibility with newer Streamlit versions

### Solution
```python
# NEW (All occurrences replaced)
st.dataframe(df, width='stretch', height=300)  # ✓ Modern parameter
st.dataframe(delta_df, hide_index=True, width='stretch')  # ✓ Modern parameter
if st.button("🔄 Refresh Data (Manual)", width='stretch'):  # ✓ Modern parameter
```

**Lines Changed:**
- Line 661 (formerly): `st.dataframe(df, use_container_width=True, height=300)`
- Line 760 (formerly): `st.dataframe(delta_df, hide_index=True, use_container_width=True)`
- Line 806 (formerly): `if st.button(..., use_container_width=True):`

---

## Issue #3: PyArrow Serialization - Mixed Type Columns

### Problem
```
PyArrow Error: Could not convert '—' with type str: tried to convert to int64
```

This happens when DataFrame columns contain mixed types (numeric values + "—" em-dash strings):

```python
"Bull Bars": 5,           # integer
"Bull Bars": "—",         # string (em-dash)
```

PyArrow tries to infer a single type for the column and fails when it encounters the "—" string.

### Root Cause
In table building (Lines 654-655), Bull Bars and Bear Bars come directly from signal object and could be integers OR the string "—" in different rows. When creating the DataFrame, PyArrow cannot convert this to a consistent type.

### Solution
Convert all DataFrame columns to strings before display (Lines 676-682):

```python
# NEW: PyArrow-safe conversion
df = pd.DataFrame(table_rows)

# Convert all columns to strings for PyArrow compatibility 
# (handles mixed "—" and numeric values)
df = df.astype(str)

st.dataframe(df, width='stretch', height=300)
```

This ensures all values (numeric strings like "5.4567", "—", "🟢 BULLISH", etc.) are treated consistently as strings, avoiding PyArrow conversion errors.

---

## Files Modified

### 1. `/home/rajish/Documents/Trading/opt_analysis/app.py`
- **fetch_historical_candles()**: Added nested dict/list structure handling
- **Candle access logic**: Added type checking for first_candle extraction (Lines 468-501)
- **DataFrame display**: Added `df.astype(str)` for PyArrow safety (Lines 676-682)
- **Parameter replacement**: All `use_container_width=True` → `width='stretch'` (3 locations)

### 2. `/home/rajish/Documents/Trading/opt_analysis/app_FIXED.py`
- Complete updated version with all fixes applied

---

## Testing & Verification

### To Verify Fix #1 (Candle Structure)
Run with market closed/holiday:
- Check Debug Logs for: `✓ List format - extracted open from index [1]: XXXX.XX`
- Or: `✓ Dict format - extracted open: XXXX.XX`
- Opening price should be from first 1-minute candle, not current spot price

### To Verify Fix #2 (Deprecation)
- Run Streamlit app and check console output
- No more deprecation warnings about `use_container_width`
- Streamlit logs should be clean

### To Verify Fix #3 (PyArrow)
- DataFrame display without errors
- No "Could not convert" exceptions
- All columns display correctly including mixed "—" and numeric values

---

## Before & After Comparison

### Before (Broken)
```
❌ KeyError: 0
❌ Deprecation warnings (cache issues)
❌ PyArrow conversion errors
```

### After (Fixed)
```
✅ Proper candle structure handling
✅ Modern Streamlit parameters
✅ PyArrow-compatible DataFrame
✅ All debug logs display correctly
```

---

## Notes for Production Deployment

1. **Replace app.py** with the fixed version
2. **Test with market closed** to verify candle extraction works
3. **Monitor logs** for any remaining errors
4. **Streamlit Cloud**: No config changes needed, fixes are code-level only
5. **Backward compatibility**: All changes are backward compatible with existing Upstox API

---

**Last Updated:** May 8, 2026
**Status:** ✅ Ready for testing
