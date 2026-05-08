# Automated Log Capture & GitHub Integration

This system automatically captures debug output from the Streamlit app and saves it to GitHub for easy analysis.

## How It Works

### 1. **Automatic Log Capture** (`app.py`)
When the Streamlit app runs, all `print()` output is automatically captured to:
```
logs/upstox_data_dump_YYYYMMDD_HHMMSS.log
```

This includes:
- `[CRITICAL]` - Upstox API response structure (first row JSON)
- `[DATA-DUMP]` - Received data from Upstox
- `[DEBUG]` - Premium extraction details
- All other console output

### 2. **View Logs Locally**
```bash
# See all captured logs
python log_viewer.py

# View latest log with [CRITICAL] and [DATA-DUMP] sections
python log_viewer.py latest
```

### 3. **Auto-Commit to GitHub** (via GitHub Actions)
The `.github/workflows/capture-logs.yml` workflow:
- Runs periodically during trading hours
- Auto-commits any new log files
- Pushes to GitHub automatically

**View at:** `https://github.com/rajishnse-alt/raj-pro-options-engine/tree/main/logs`

## Setup Instructions

### Step 1: Enable GitHub Actions
1. Go to **Settings** → **Actions** → **General**
2. Ensure "Actions permissions" allows workflows

### Step 2: Configure Git (if running locally)
```bash
cd /home/rajish/Documents/Trading/opt_analysis
git config user.name "Raj Options Engine"
git config user.email "rajish.g.nair@gmail.com"
```

### Step 3: Manual Log Push (Optional)
If you want to immediately push logs without waiting for the scheduled workflow:
```bash
cd /home/rajish/Documents/Trading/opt_analysis
git add logs/
git commit -m "Manual log push: $(date)"
git push origin main
```

## What You'll See

### In the Logs File
```
================================================================================
[CRITICAL] Actual Upstox data structure for NIFTY
================================================================================
Total rows: 47

First row keys: ['strike_price', 'call_options', 'put_options', 'underlying_spot_price', ...]

First row (first 1000 chars):
{
  "strike_price": "23700",
  "call_options": {
    "market_data": {
      "ltp": 125.5,
      ...
    }
  },
  ...
}
================================================================================
```

### In the Sidebar
You'll see:
- ✓ Current log file location
- 📝 Instructions to view logs
- Link to GitHub logs folder

## Troubleshooting

### Logs Not Appearing?
1. Check that `logs/` directory exists:
   ```bash
   ls -la logs/
   ```
2. Manually trigger workflow in GitHub → Actions tab
3. Run `python log_viewer.py` to see captured logs

### GitHub Actions Not Pushing?
1. Go to **Settings** → **Secrets and variables** → **Actions**
2. Check that repository has write access (it should by default)
3. View workflow runs: **Actions** → **Capture and Commit Debug Logs**

### Can't View Latest Log?
```bash
# Manually check recent files
ls -ltr logs/ | tail -5

# View specific file
cat logs/upstox_data_dump_YYYYMMDD_HHMMSS.log
```

## Next Steps

1. **Deploy to Streamlit Cloud**
   ```bash
   git add -A
   git commit -m "Add automated logging system"
   git push origin main
   ```

2. **Refresh your Streamlit app** - it will auto-capture logs

3. **Check logs in GitHub** (or run `python log_viewer.py latest`)

4. **Share the `[CRITICAL]` section** - this shows the actual Upstox data structure needed to fix premium extraction

---

**Once you share the [CRITICAL] output, I can immediately fix the premium extraction issue.**
