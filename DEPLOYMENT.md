# Deployment Guide - Raj Pro Options Engine

## Quick Deployment to Streamlit Cloud

### Step 1: Verify Local Files

Ensure you have these files in your repo directory:
```
app_clean.py           ← Main Streamlit app
engine_clean.py        ← Options analysis engine
requirements.txt       ← Python dependencies
.streamlit/config.toml ← Streamlit configuration
README.md              ← Documentation
.gitignore             ← Git ignore rules
```

### Step 2: Prepare GitHub Repository

1. Open terminal in `/home/rajish/Documents/Trading/opt_analysis/`
2. Initialize git (if not already done):
   ```bash
   git init
   git add .
   git commit -m "Initial commit: Raj Pro Options Engine"
   ```

3. Add remote and push:
   ```bash
   git remote add origin https://github.com/rajishnse-alt/raj-pro-options-engine.git
   git branch -M main
   git push -u origin main
   ```

### Step 3: Create Streamlit Cloud App

1. Go to https://streamlit.io/cloud
2. Click "New app"
3. Select:
   - GitHub repo: `rajishnse-alt/raj-pro-options-engine`
   - Branch: `main`
   - Main file path: `app_clean.py`
4. Click "Deploy"

### Step 4: Configure Secrets

While app is deploying, set up secrets:

1. Go to app settings (gear icon)
2. Click "Secrets" in the menu
3. Add your Upstox credentials:

```toml
[upstox]
api_key = "YOUR_API_KEY_HERE"
api_secret = "YOUR_API_SECRET_HERE"
redirect_uri = "https://YOUR-APP-NAME.streamlit.app"
```

⚠️ **Important**: Replace:
- `YOUR_API_KEY_HERE` with your API key from developer.upstox.com
- `YOUR_API_SECRET_HERE` with your API secret key
- `YOUR-APP-NAME` with your actual Streamlit app name (shown in URL)

### Step 5: Test the App

1. App will reload after secrets are added
2. Click "CONNECT WITH UPSTOX" button
3. You'll be redirected to Upstox login
4. After authentication, you'll see:
   - 🟢 or 🔴 market status indicator
   - Current IST time
   - Three index analysis sections (NIFTY, BANKNIFTY, FINNIFTY)
   - Signal metrics and options chain data

## Troubleshooting

### "Upstox credentials not configured"
- Check that secrets are added in Streamlit Cloud app settings
- Verify spelling: `[upstox]`, `api_key`, `api_secret`, `redirect_uri`
- Restart app after adding secrets (Settings → Rerun)

### "Login failed: ..."
- Verify redirect_uri in app secrets matches your actual Streamlit app URL
- Go to developer.upstox.com and confirm API credentials are valid
- Check that the app is deployed on Streamlit Cloud (not localhost)

### "Could not determine spot price"
- This happens during market hours when data is being fetched
- Upstox API may be slow during peak hours
- App auto-refreshes every 180 seconds
- Check Upstox API status at https://api.upstox.com/health

### "Empty expiry list" / "Failed to fetch chain"
- Market may be closed (9:15 AM - 3:30 PM IST, weekdays only)
- Check market open/closed status (🟢🔴 indicator)
- Upstox API may be temporarily unavailable
- Refresh page and try again

### Token expired
- Happens after 24 hours of login
- Just click "CONNECT WITH UPSTOX" again to re-login
- Your token is automatically refreshed on new login

## Local Development

To run locally for testing:

```bash
cd /home/rajish/Documents/Trading/opt_analysis
pip install -r requirements.txt
streamlit run app_clean.py
```

Then create `.streamlit/secrets.toml` (local only, not committed to git):
```toml
[upstox]
api_key = "YOUR_KEY"
api_secret = "YOUR_SECRET"
redirect_uri = "http://localhost:8501"
```

Access at: http://localhost:8501

## Updating the App

1. Make changes to `app_clean.py` or `engine_clean.py`
2. Test locally
3. Push to GitHub:
   ```bash
   git add .
   git commit -m "Update: your changes here"
   git push
   ```
4. Streamlit Cloud automatically redeploys within seconds

## Performance Notes

- **Cache Duration**: 180 seconds (options chain data)
- **Auto-refresh**: Every 180 seconds (configurable in code)
- **Token Expiry**: 24 hours (automatic re-login required)
- **API Rate Limit**: Check Upstox docs for rate limits per endpoint

## Security

- Never commit `.streamlit/secrets.toml` to GitHub (it's in .gitignore)
- Use Streamlit Cloud secrets dashboard for production
- API credentials are transmitted securely via HTTPS only
- OAuth tokens are stored in Streamlit session state (not persisted)
