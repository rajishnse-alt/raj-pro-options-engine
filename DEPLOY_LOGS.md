# 🚀 Deploy Logging System - Quick Start

You now have **automatic debug log capture** that pushes to GitHub. Here's how to deploy it:

## Option 1: Automated Deploy (Easiest)

```bash
cd /home/rajish/Documents/Trading/opt_analysis
bash deploy_with_logging.sh "Deploy logging system"
```

That's it. The script will:
- ✅ Configure git
- ✅ Create logs directory
- ✅ Commit all changes
- ✅ Push to GitHub

## Option 2: Manual Deploy

```bash
cd /home/rajish/Documents/Trading/opt_analysis

# Add files
git add -A

# Commit
git commit -m "Add automated logging system"

# Push
git push origin main
```

## What This Deploys

### New Files Created:
- 📄 `log_capture.py` - Core logging utility
- 📄 `log_viewer.py` - View captured logs
- 📊 `.github/workflows/capture-logs.yml` - Auto-commit workflow
- 📋 `LOGGING_SETUP.md` - Full documentation
- 📁 `logs/` - Directory for captured logs

### Modified Files:
- 🔧 `app.py` - Now auto-captures output to file + displays log status in sidebar

## After Deployment

### 1. Refresh Streamlit Cloud App
Visit: `https://raj-pro-options-engine-8.streamlit.app` (or your app URL)

Your app will automatically capture debug output to:
```
logs/upstox_data_dump_YYYYMMDD_HHMMSS.log
```

### 2. View the Logs

**Option A: Locally (Fastest)**
```bash
# View latest with [CRITICAL] highlighted
bash view_latest_logs.sh

# Or use Python viewer
python log_viewer.py latest
```

**Option B: On GitHub**
```
https://github.com/rajishnse-alt/raj-pro-options-engine/tree/main/logs
```
(Logs auto-appear when GitHub Actions workflow runs)

### 3. Share the [CRITICAL] Section

Once you see the logs, copy the `[CRITICAL]` section that shows the Upstox data structure and paste it here. That's all I need to fix the premium extraction.

## What the Logs Contain

```
[CRITICAL] - Actual JSON structure from Upstox API
  - First row keys
  - Nested field structure
  - Data types
  ← THIS IS WHAT WE NEED TO FIX THE ISSUE!

[DATA-DUMP] - What was received from Upstox
[DEBUG] - Premium extraction attempts
```

## Troubleshooting

### Logs directory not created?
```bash
mkdir -p logs
git add logs/
```

### Can't push to GitHub?
```bash
git remote -v  # Check remote is set
git push origin main -u  # Force set upstream
```

### Workflow not auto-committing?
No problem - logs are still being captured locally. Run:
```bash
bash deploy_with_logging.sh "Manual push of captured logs"
```

## Next: Fix the Issue

Once you've deployed and refreshed the app:

1. Run: `bash view_latest_logs.sh`
2. Copy the `[CRITICAL]` output
3. Paste here
4. I'll fix the premium extraction immediately

---

**Ready?** Start with:
```bash
bash deploy_with_logging.sh
```
