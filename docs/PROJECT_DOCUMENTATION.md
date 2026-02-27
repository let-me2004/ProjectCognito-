# ProjectCognito — Complete Technical Documentation

> **Author:** Anuka | **Last Updated:** February 27, 2026  
> **Status:** Active Development | **Language:** Python 3.x

---

## 1. Executive Summary

**ProjectCognito (CognitoTrader)** is a multi-agent algorithmic trading platform built from scratch in Python for the Indian stock market (NSE). It combines quantitative analysis, machine learning, and LLM-powered sentiment analysis to generate and execute trading signals in real-time.

The system connects to the **Fyers brokerage API** for live market data via WebSocket feeds, runs multiple independent trading agents simultaneously, and provides a **real-time web dashboard** for monitoring. All trading is done through a sophisticated **paper trading engine** that simulates real market conditions including brokerage fees, slippage, and position persistence.

### Key Achievements
- Built **3 independent trading agents** (Options, Equity, ORB Scalper)
- Developed **6 distinct trading strategies** with full backtesting
- Trained a **Gradient Boosting ML model** on 5 years of NIFTY data (96,000+ data points)
- Integrated **Groq LLM (Llama 4 Scout)** for real-time sentiment analysis
- Built a **full-stack web dashboard** with WebSocket live price streaming
- Executed **41+ simulated trades** with real market data
- Implemented **debit spread** options trading for defined-risk positions

---

## 2. System Architecture

### 2.1 High-Level Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    FYERS BROKERAGE API                   │
│         (REST API + WebSocket Level 2 Data Feed)        │
└──────────┬──────────────────────────────┬───────────────┘
           │                              │
    ┌──────▼──────┐              ┌────────▼────────┐
    │ fyers_client │              │  WebSocket Feed  │
    │   (REST)     │              │  (Real-time LTP) │
    └──────┬──────┘              └────────┬────────┘
           │                              │
    ┌──────▼──────────────────────────────▼───────────┐
    │              TRADING AGENTS (3 Agents)           │
    │  ┌─────────────┐ ┌──────────────┐ ┌───────────┐ │
    │  │Options Agent │ │ Equity Agent │ │ORB Scalper│ │
    │  │  (main.py)   │ │(equity_main) │ │(options_  │ │
    │  │              │ │              │ │ scalper)  │ │
    │  └──────┬──────┘ └──────┬───────┘ └─────┬─────┘ │
    └─────────┼───────────────┼───────────────┼───────┘
              │               │               │
    ┌─────────▼───────────────▼───────────────▼───────┐
    │              DECISION LAYER                      │
    │  ┌──────────┐ ┌──────────┐ ┌──────────────────┐ │
    │  │Technical  │ │   ML     │ │ LLM Sentiment    │ │
    │  │Analyzer   │ │Predictor │ │ Engine (Groq)    │ │
    │  └──────────┘ └──────────┘ └──────────────────┘ │
    └─────────────────────┬───────────────────────────┘
                          │
    ┌─────────────────────▼───────────────────────────┐
    │              EXECUTION LAYER                     │
    │  ┌──────────┐ ┌──────────┐ ┌──────────────────┐ │
    │  │  Risk     │ │  Paper   │ │   Trade Logger   │ │
    │  │ Manager   │ │ Trader   │ │  (trade_log.csv) │ │
    │  └──────────┘ └──────────┘ └──────────────────┘ │
    └─────────────────────┬───────────────────────────┘
                          │
    ┌─────────────────────▼───────────────────────────┐
    │           WEB DASHBOARD (Flask + WebSocket)      │
    │           http://localhost:5050                   │
    └─────────────────────────────────────────────────┘
```

### 2.2 File Structure Overview

| File | Purpose | Lines |
|------|---------|-------|
| `main.py` | Options Agent — multi-filter confluence bot | 184 |
| `options_scalper_main.py` | ORB Scalper Agent — queue-based tick architecture | 359 |
| `equity_main.py` | Equity Agent — NIFTY 200 surge scanner | 209 |
| `fyers_client.py` | Fyers API wrapper (REST + WebSocket) | 403 |
| `paper_trader.py` | Paper trading engine with spread support | 501 |
| `web_dashboard.py` | Flask dashboard with live WebSocket prices | 1476 |
| `orb_scalper_strategy.py` | Opening Range Breakout strategy | 215 |
| `hft_scalper_strategy.py` | HFT EMA/RSI multi-signal scalper | 136 |
| `supertrend_vwap_strategy.py` | SuperTrend + VWAP strategy | 213 |
| `combined_strategy.py` | Combined ORB + EMA strategy | 189 |
| `consolidation_hunter_strategy.py` | Bollinger Band squeeze breakout | 92 |
| `technical_analyzer.py` | EMA, ATR, breakout detection | 183 |
| `risk_manager.py` | Position sizing for options & equity | 122 |
| `ml_predictor.py` | ML model inference wrapper | 40 |
| `model_training.py` | Gradient Boosting model trainer | 82 |
| `feature_engineering.py` | 21-feature pipeline from raw OHLCV | 84 |
| `llm_handler.py` | Groq/Llama LLM integration | 109 |
| `sentiment_engine.py` | Weighted NIFTY 50 sentiment scorer | 53 |
| `news_handler.py` | YFinance news fetcher | 59 |
| `equity_scanner.py` | NIFTY 200 volume surge scanner | 149 |
| `sector_mapper.py` | Stock-to-sector mapping | 88 |
| `orderflow_analyzer.py` | Level 2 order book imbalance | 117 |
| `config.py` | Environment variable loader | 21 |
| `logger_setup.py` | Centralized logging configuration | 33 |

---

## 3. Trading Strategies — Deep Dive

### 3.1 Opening Range Breakout (ORB) — Primary Live Strategy

**File:** `orb_scalper_strategy.py` | **Used by:** `options_scalper_main.py`

**Concept:** The first 15 minutes of market open (9:15–9:30) establish the day's "opening range." A breakout above/below this range signals strong directional momentum.

**How It Works:**
1. At 9:30 AM, fetch 5-min candles from 9:15–9:30 (3 candles)
2. Compute `orb_high` (highest high) and `orb_low` (lowest low)
3. Validate range: must be between 20 points and 1% of price
4. Monitor live ticks — when price closes above `orb_high` → **LONG**; below `orb_low` → **SHORT**
5. Enter a **Debit Spread** (buy ATM option + sell OTM option) for defined risk
6. Stop-loss: opposite ORB boundary + 5pt buffer
7. Take-profit: 1.15× the spread width (max theoretical profit)

**Risk Parameters:**
- Stop-loss: ORB range + 5pt buffer (~30-80 points)
- Risk per trade: 10% of account (configurable)
- Max 1 trade per index per day (NIFTY + BANKNIFTY)
- Auto square-off at 3:00 PM (EOD)

**Why Debit Spreads?**
- Defined risk (max loss = net debit paid)
- Lower margin requirement (₹30k-40k vs ₹1.5L for naked options)
- Theta decay on both legs partially cancels out

### 3.2 EMA Crossover Scalper (HFT Strategy)

**File:** `hft_scalper_strategy.py` | **Backtested via:** `hft_scalper_backtester.py`

**Concept:** High-frequency scalping using fast EMA crossovers confirmed by RSI momentum.

**Three Signal Types:**
1. **EMA Crossover:** EMA(5) crosses EMA(13) with RSI confirmation
2. **RSI Reversal:** RSI crosses back from overbought/oversold extremes
3. **EMA Bounce:** Price pulls back to fast EMA and bounces in trend direction

**Parameters:** EMA Fast=5, EMA Slow=13, RSI Period=7, SL=12pts, TP=18pts (1.5:1 R:R)

### 3.3 SuperTrend + VWAP Strategy

**File:** `supertrend_vwap_strategy.py` | **Backtested via:** `supertrend_vwap_backtester.py`

**Concept:** SuperTrend direction flip as primary entry, VWAP as confluence, ADX as trend strength filter.

**Key Innovation:** Uses candle range as volume proxy for VWAP calculation (since index options data often has zero volume).

**Parameters:** SuperTrend Period=10, Multiplier=2.0, ADX Threshold=18, SL=15pts, TP=20pts

### 3.4 Combined ORB + EMA Strategy

**File:** `combined_strategy.py` | **Backtested via:** `combined_backtester.py`

**Two-Phase Approach:**
- **Phase 1 (9:15–9:45):** Opening Range Breakout — 1 high-conviction trade
- **Phase 2 (9:45–15:00):** EMA 5/13 Crossover Scalper — multiple smaller trades

### 3.5 Consolidation Hunter (Bollinger Squeeze)

**File:** `consolidation_hunter_strategy.py` | **Used by:** `backtester.py`

**Three-Way Confluence:**
1. Bollinger Band Width < 1.5% (squeeze detected)
2. Price above/below 200-EMA (trend filter)
3. Volume > 20-period MA (conviction filter)

**R:R Ratio:** 3:1 | **Stop-loss:** Middle Bollinger Band

### 3.6 Weighted Confluence Breakout (Options Agent)

**File:** `main.py` | **The most selective strategy**

**Five independent filters must ALL agree:**
1. NIFTY 45-min regime (EMA 50)
2. BANKNIFTY 45-min regime (sector confirmation)
3. 5-min price breakout trigger
4. Weighted sentiment score from top NIFTY 50 stocks via Groq LLM
5. ML model prediction (Gradient Boosting, 51% accuracy on 19k test samples)

---

## 4. Core Components — Technical Details

### 4.1 Fyers API Client (`fyers_client.py`)

**Authentication Flow:**
1. Load `FYERS_APP_ID` and `FYERS_SECRET_KEY` from `.env`
2. Check for cached token in `access_token.txt`
3. If expired → open browser for OAuth2 login → save new token
4. Return authenticated `FyersModel` instance

**Key Functions:**
- `get_historical_data()` — Fetches OHLCV candles (any timeframe: 1min to daily)
- `find_option_by_offset()` — Dynamically finds option symbols using Fyers symbol master CSV
- `get_quotes()` — Batch quote fetching for multiple symbols
- `place_multileg_order()` — Multi-leg basket order for spreads (segment 14, IOC validity)
- `place_market_order()` — Single-leg market order for exits
- `start_level2_websocket()` — Non-blocking WebSocket for real-time tick data
- `get_available_margin()` — Checks account balance before live trades
- `calculate_spread_margin()` — Approximate SPAN margin for debit spreads (₹30k-40k)

### 4.2 Paper Trading Engine (`paper_trader.py`)

The paper trader is the simulation backbone supporting all three agents.

**Key Features:**
- **Dual-Price Architecture:** Stores both SIM prices (option prices for P&L) and INDEX prices (underlying prices for exit triggers)
- **Spread Support:** `execute_spread()` handles debit spreads with buy/sell legs, net debit, and max profit calculation
- **Position Persistence:** Saves/loads positions to JSON files (`paper_positions_*.json`)
- **Hot-Reload Sync:** `sync_positions()` detects external file changes (e.g., from web dashboard) and merges
- **Trade Logging:** Every closed trade is appended to `trade_log.csv` with full details
- **EOD Auto Square-Off:** `close_all_positions()` closes everything at 3:00 PM
- **Brokerage Simulation:** ₹40 flat fee per trade (₹20 entry + ₹20 exit)

### 4.3 Risk Manager (`risk_manager.py`)

**Two calculation modes:**

1. **Options Scalping:** `calculate_scalping_trade()`
   - Input: account balance, risk %, stop-loss points, index name
   - Calculates max lots based on risk budget (NIFTY=65/lot, BANKNIFTY=30/lot)
   - Defaults to 1 lot for conservative sizing

2. **Equity Trading:** `calculate_equity_trade()`
   - Input: account balance, risk %, entry price, stop-loss price
   - Uses `abs()` for risk-per-share to handle both long and short positions (bug fix)
   - Checks capital sufficiency and downsizes if needed

### 4.4 Web Dashboard (`web_dashboard.py`)

**Tech:** Flask web server on port 5050 with embedded HTML/CSS/JS (1,476 lines)

**Features:**
- Real-time position monitoring for all 3 agents
- Live WebSocket price streaming (refreshes every 2 seconds)
- Manual trade execution (Buy/Sell buttons with custom parameters)
- Trade history table from `trade_log.csv`
- Option chain viewer with live spot prices
- Position management (close individual positions)

**API Endpoints:**
| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/api/positions` | GET | All open positions across agents |
| `/api/trades` | GET | Trade history |
| `/api/live-prices` | GET | WebSocket tick store |
| `/api/symbols` | GET | Generate option chain symbols |
| `/api/quote` | GET | Single option quote |
| `/api/buy` | POST | Execute manual buy |
| `/api/sell` | POST | Execute manual sell |
| `/api/clear` | POST | Clear all positions |

### 4.5 ML Pipeline

**Data Harvesting:** `data_harvester.py` downloads 5 years of 5-min NIFTY candles in chunks.

**Feature Engineering:** `feature_engineering.py` creates 21 features:
- **Momentum:** RSI(14), MACD(12,26,9)
- **Trend:** EMA(10), EMA(21), EMA(50), EMA(200)
- **Volatility:** Bollinger Bands(20), ATR(14)
- **Custom:** 1-hour return, 1-day return
- **Target:** Binary — is price higher in 30 minutes? (6 candles ahead)

**Training:** `model_training.py` uses `GradientBoostingClassifier` with time-series-aware split (no shuffling — train on past, test on future).

**Optimization:** `model_optimizer.py` uses `RandomizedSearchCV` for hyperparameter tuning.

**Inference:** `ml_predictor.py` loads the saved `.joblib` model, aligns feature columns, and returns predictions.

### 4.6 LLM & Sentiment Pipeline

**LLM Handler:** `llm_handler.py` — Uses Groq API with `meta-llama/llama-4-scout-17b-16e-instruct`
- Persona: "Cognito" — a senior quantitative sentiment analyst
- Output: JSON with `outlook` (Bullish/Bearish/Neutral) and `confidence` (0.0-1.0)
- Temperature: 0.1 (deterministic), forced JSON output format

**News Handler:** `news_handler.py` — Fetches headlines via `yfinance` for NSE stocks

**Sentiment Engine:** `sentiment_engine.py` — Weighted NIFTY 50 sentiment:
- Analyzes top constituents by index weight
- Multiplies LLM sentiment score by stock's NIFTY weight
- Returns net weighted sentiment score for trading decisions

---

## 5. Bugs Fixed & Changes Made

### 5.1 Critical Bug Fixes

| Bug | File | Fix |
|-----|------|-----|
| **Short position risk calculation** | `risk_manager.py` | Used `abs(entry_price - stop_loss_price)` to handle both long and short trades |
| **Spread P&L calculation on EOD** | `paper_trader.py` | Fixed `close_all_positions()` to use net premium of both buy/sell legs for spread exit P&L |
| **HMAC signature validation** | Binance integration | Corrected C++ HMAC-SHA256 to match Binance's expected format (conversation history) |
| **Logger initialization order** | `backtester.py` | Logger must be initialized FIRST before any imports to prevent pandas_ta from hijacking the root logger |
| **Pandas import missing** | `paper_trader.py` | Added `import pandas as pd` — documented as "THIS IS THE FIX" |
| **Duplicate handler prevention** | `logger_setup.py` | Remove existing handlers before adding new ones to prevent duplicate log lines |

### 5.2 Key Iterative Changes

1. **LLM Migration:** Moved from Google Gemini API → Groq API with Llama 4 Scout for faster inference
2. **News Source Migration:** Moved from custom web scraping → YFinance for reliable headlines
3. **Architecture Upgrade:** Options scalper moved from polling-based → queue-based WebSocket architecture for lower latency
4. **Symbol Discovery:** Built dynamic option symbol finder using Fyers symbol master CSV (handles weekly/monthly expiry format changes)
5. **Spread Trading:** Upgraded from naked option buying → debit spreads for defined risk and lower margin
6. **Volume Cache:** Added daily volume cache (`volume_cache.json`) to avoid 200 API calls per scan cycle
7. **Position Hot-Reload:** Added `sync_positions()` for dashboard ↔ agent synchronization
8. **Margin Estimation:** Since Fyers v3 deprecated margin API, built approximate SPAN margin calculator
9. **Demo Mode Toggle:** Added demo/strict mode in `technical_analyzer.py` for signal generation flexibility

### 5.3 Fyers API Challenges Solved

- **Symbol Format Discovery:** NSE option symbols follow complex patterns (e.g., `NSE:NIFTY2630225350PE`). Built 18 test scripts (`find_symbol*.py`) to reverse-engineer the correct format.
- **WebSocket Stability:** Implemented reconnection logic and error handlers for production WebSocket feeds
- **Rate Limiting:** Added `time.sleep()` delays between bulk API calls and chunked quote fetching (70 symbols per request)
- **Token Management:** Auto-caches access tokens and reuses across sessions

---

## 6. Trading Results Summary

Based on `trade_log.csv` (41 closed trades from Feb 20-27, 2026):

| Metric | Value |
|--------|-------|
| Total Trades | 41 |
| Trade Types | Naked options, Debit spreads, Equity |
| Indices Traded | NIFTY, BANKNIFTY |
| Equities Traded | SIEMENS |
| Spread Width | 50 points (NIFTY), 100 points (BANKNIFTY) |
| Typical Spread Debit | ₹17-25 (NIFTY), ₹39-52 (BANKNIFTY) |

---

## 7. Backtesting Results

Three backtesting frameworks were built and run:

| Backtester | Strategy | Data File |
|------------|----------|-----------|
| `orb_backtester.py` | ORB Breakout | `orb_backtest_results.csv` (207 KB) |
| `hft_scalper_backtester.py` | HFT EMA/RSI | `hft_scalper_results.csv` (3.4 MB) |
| `supertrend_vwap_backtester.py` | SuperTrend+VWAP | `supertrend_vwap_results.csv` (1 MB) |
| `combined_backtester.py` | ORB + EMA | `combined_backtest_results.csv` (1.1 MB) |
| `backtester.py` | Consolidation Hunter | Equity (RELIANCE) |

---

## 8. Future Scope & Cloud Deployment

### 8.1 Cloud Deployment Plan

**Problem:** Running on a local machine means system crashes, internet outages, and power failures can interrupt trading during market hours.

**Solution: Deploy to Cloud Infrastructure**

#### Option A: AWS (Recommended)
```
┌─────────────────────────────────────────┐
│              AWS Architecture            │
│                                         │
│  ┌─────────┐    ┌──────────────────┐   │
│  │ EC2      │    │ RDS (PostgreSQL) │   │
│  │ t3.small │    │ Trade history    │   │
│  │ Trading  │───▶│ Position data    │   │
│  │ Agents   │    │ Performance logs │   │
│  └────┬─────┘    └──────────────────┘   │
│       │                                  │
│  ┌────▼─────┐    ┌──────────────────┐   │
│  │CloudWatch│    │ SNS / Telegram    │   │
│  │ Logs +   │    │ Trade alerts      │   │
│  │ Alarms   │    │ Error notifications│  │
│  └──────────┘    └──────────────────┘   │
└─────────────────────────────────────────┘
```

**Steps:**
1. **EC2 Instance (t3.small ~$15/month):** Run all 3 agents + dashboard 24/7
2. **RDS PostgreSQL:** Replace JSON files with proper database for position/trade storage
3. **CloudWatch:** Monitor agent health, set alarms for crashes, auto-restart
4. **Auto-Recovery:** EC2 auto-recovery on hardware failure
5. **Elastic IP:** Fixed IP for dashboard access from anywhere
6. **S3 Backup:** Daily backup of trade logs and model files

#### Option B: Google Cloud Platform
- **Compute Engine (e2-small ~$12/month)** for agents
- **Cloud SQL** for trade database
- **Cloud Monitoring** for alerts

#### Option C: Azure
- **Azure VM (B1s ~$10/month)** for agents
- **Azure SQL** for trade database
- **Application Insights** for monitoring

### 8.2 Making the System More Robust

| Enhancement | Description | Priority |
|-------------|-------------|----------|
| **Database Migration** | Replace JSON files with PostgreSQL/SQLite for ACID compliance | HIGH |
| **Process Supervisor** | Use `systemd` (Linux) or PM2 to auto-restart crashed agents | HIGH |
| **Health Check API** | Add `/health` endpoint to dashboard for uptime monitoring | HIGH |
| **Telegram/Discord Alerts** | Push trade notifications to phone (already tested in conv history) | MEDIUM |
| **Docker Containerization** | Package everything in Docker for reproducible deployments | MEDIUM |
| **Redis Cache** | Replace JSON volume cache with Redis for atomic reads/writes | MEDIUM |
| **API Rate Limiter** | Add proper rate limiting middleware for Fyers API calls | MEDIUM |
| **Circuit Breaker** | Auto-disable agents if >3 consecutive losses in a day | LOW |
| **Multi-Region Failover** | Run backup instance in different region with shared DB | LOW |
| **WebSocket Reconnection** | Auto-reconnect with exponential backoff on disconnect | LOW (partially done) |

### 8.3 Feature Roadmap

1. **Live Trading Mode:** Toggle from paper → live with margin checks and order confirmation
2. **Advanced ML Models:** LSTM/Transformer for time-series prediction
3. **Options Greeks:** Real-time delta/gamma/theta tracking for spread positions
4. **Portfolio-Level Risk:** Cross-agent risk management (total exposure limits)
5. **Performance Analytics:** Sharpe ratio, max drawdown, win rate charts on dashboard
6. **Multi-Broker Support:** Abstract broker layer to support Zerodha, Angel One, etc.
7. **Backtesting UI:** Run backtests from the dashboard with parameter tuning
8. **Alert System:** Configurable alerts for specific market conditions

---

## 9. Tech Stack Summary

| Category | Technology |
|----------|-----------|
| **Language** | Python 3.x |
| **Broker API** | Fyers API v3 (REST + WebSocket) |
| **Web Framework** | Flask |
| **ML Framework** | Scikit-learn, LightGBM |
| **LLM** | Groq API (Llama 4 Scout 17B) |
| **Technical Analysis** | Pandas-TA, custom indicators |
| **Data** | Pandas, NumPy |
| **News** | YFinance |
| **Model Persistence** | Joblib |
| **Configuration** | python-dotenv |
| **Version Control** | Git + GitHub |

---

## 10. How to Run

```bash
# 1. Setup
python -m venv venv
.\venv\Scripts\activate
pip install -r requirements.txt

# 2. Configure .env file with API keys
# FYERS_APP_ID, FYERS_SECRET_KEY, GROQ_API_KEY, etc.

# 3. Run the web dashboard (always keep running)
python web_dashboard.py

# 4. Run any trading agent
python options_scalper_main.py   # ORB Scalper (primary)
python main.py                   # Options Agent
python equity_main.py            # Equity Agent

# 5. Run backtests
python orb_backtester.py
python hft_scalper_backtester.py
python combined_backtester.py

# 6. Train ML model
python data_harvester.py         # Download raw data
python feature_engineering.py    # Engineer features
python model_training.py         # Train model
python model_optimizer.py        # Optimize hyperparameters
```

---

## 11. Glossary

| Term | Definition |
|------|-----------|
| **ORB** | Opening Range Breakout — first 15 min high/low |
| **Debit Spread** | Buy ATM + Sell OTM option for defined risk |
| **ATM** | At The Money — option strike closest to spot price |
| **OTM** | Out of The Money — option strike away from spot |
| **LTP** | Last Traded Price |
| **EMA** | Exponential Moving Average |
| **RSI** | Relative Strength Index (momentum oscillator) |
| **ADX** | Average Directional Index (trend strength) |
| **VWAP** | Volume Weighted Average Price |
| **SuperTrend** | Trend-following indicator using ATR bands |
| **SPAN Margin** | NSE margin system for options positions |
| **EOD** | End of Day — 3:00 PM auto square-off |
| **Paper Trading** | Simulated trading without real money |
| **Lot Size** | Minimum tradeable quantity (NIFTY=65, BANKNIFTY=30) |

---

*This document is auto-generated from the ProjectCognito codebase. For the latest code, refer to the source files directly.*
