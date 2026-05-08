# Raj Pro Options Engine - Streamlit App

A professional real-time options trading signal generator with Upstox broker integration. Analyzes options chain data using dominance metrics and generates trading signals based on put/call erosion patterns.

## Features

- **Real-time Options Analysis**: Live NSE options chain data from Upstox API
- **Multi-Index Support**: NIFTY 50, BANKNIFTY, FINNIFTY analysis
- **Signal Generation**: UP_CONFIRMED, DN_CONFIRMED, UP_PENDING, DN_PENDING signals with confidence metrics
- **Dominance Metrics**: 
  - Put/Call erosion calculation from daily opening prices
  - Dominance = Put Erosion - Call Erosion
  - Momentum (EMA-based trend confirmation)
  - Volatility (20-period standard deviation)
- **Professional UI**: Dark theme with clean metric displays
- **OAuth 2.0 Authentication**: Secure Upstox broker integration
- **Auto-refresh**: 180-second automatic data refresh

## Setup Instructions

### Local Development

1. Clone the repository:
   ```bash
   git clone https://github.com/rajishnse-alt/raj-pro-options-engine.git
   cd raj-pro-options-engine
   ```

2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

3. Create Upstox API credentials:
   - Go to https://developer.upstox.com
   - Create a new app
   - Note your API Key and Secret Key

4. Run locally with secrets:
   ```bash
   streamlit run app_clean.py --logger.level=error
   ```

### Deploy to Streamlit Cloud

1. Push code to GitHub:
   ```bash
   git add .
   git commit -m "Deploy Raj Pro Options Engine"
   git push origin main
   ```

2. Go to https://streamlit.io/cloud
3. Click "New app" → Select repository → `app_clean.py`
4. In app settings, add secrets:
   ```
   [upstox]
   api_key = "your_api_key_from_developer.upstox.com"
   api_secret = "your_secret_key"
   redirect_uri = "https://your-app-name.streamlit.app"
   ```
5. Deploy!

## File Structure

- **app_clean.py** - Main Streamlit application with Upstox OAuth
- **engine_clean.py** - Options analysis engine (signal generation logic)
- **requirements.txt** - Python dependencies
- **.streamlit/config.toml** - Streamlit theme and configuration

## How It Works

### Signal Generation Pipeline

1. **Daily Opening Price Tracking**
   - On first observation of each strike per day, store premium price as opening price
   - Reset on market day change (daily 9:15 AM IST)

2. **Erosion Calculation**
   - CE Erosion = (CE Opening Price - Current CE Price) / CE Opening Price
   - PE Erosion = (PE Opening Price - Current PE Price) / PE Opening Price
   - Higher erosion = premium decay = potential directional move

3. **Dominance Analysis**
   - Dominance = PE Erosion - Call Erosion
   - Positive dominance = bullish (puts eroding more)
   - Negative dominance = bearish (calls eroding more)

4. **Momentum Confirmation**
   - Momentum = EMA(PE Erosion) - EMA(CE Erosion)
   - Uses 5-period EMA for trend strength
   - Validates dominance direction

5. **Trend Detection**
   - Count consecutive bars with positive/negative momentum
   - 3+ bullish bars = potential uptrend
   - 3+ bearish bars = potential downtrend

6. **Signal Strength**
   - **UP_CONFIRMED**: 3+ bull bars + dominance > 0.04 + strong momentum → 90% confidence
   - **UP_BUILDING**: 3+ bull bars + dominance > 0.04 → 70% confidence
   - **UP_PENDING**: 3+ bull bars → 50% confidence
   - Similar for bearish (DN_CONFIRMED, DN_BUILDING, DN_PENDING)
   - **NEUTRAL/WAIT**: No confirmed trend → 30% confidence

## Market Hours

- **IST Trading Hours**: 9:15 AM - 3:30 PM (Weekdays)
- **Green Indicator (🟢)**: Market is open
- **Red Indicator (🔴)**: Market is closed

## API Integration

- **Broker**: Upstox
- **Authentication**: OAuth 2.0
- **Endpoints**:
  - `/v2/login/authorization/dialog` - OAuth authorization
  - `/v2/login/authorization/token` - Token exchange
  - `/v2/option/contract` - Expiry dates
  - `/v2/option/chain` or `/v3/option/chain` - Options chain data

## Configuration

### Strike Spacing by Index
- NIFTY: 50-point gap
- BANKNIFTY: 100-point gap
- FINNIFTY: 50-point gap

### Default Parameters
- Dominance Threshold: 0.04
- EMA Period: 5
- Volatility Calculation: 20-period standard deviation
- Cache Duration: 180 seconds

## Support

For issues or questions, please create an issue on GitHub.

## License

Proprietary - Personal trading use only
