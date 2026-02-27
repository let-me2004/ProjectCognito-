# ProjectCognito — Changelog & Development History

> Chronological record of all major changes, features, and bug fixes.

---

## Phase 1: Foundation (Initial Commit)

### Core Infrastructure
- [x] Project structure setup with virtual environment
- [x] `config.py` — Environment variable loader for API keys
- [x] `logger_setup.py` — Centralized logging with console output
- [x] `fyers_client.py` — Fyers API authentication (OAuth2 + token caching)
- [x] `fyers_client.py` — Historical data fetcher (any timeframe)
- [x] `fyers_client.py` — Option symbol finder using symbol master CSV
- [x] `requirements.txt` — All Python dependencies

### Options Agent (v1)
- [x] `main.py` — Multi-filter options trading bot
- [x] `technical_analyzer.py` — EMA, ATR, breakout analysis on 5-min and 45-min data
- [x] `risk_manager.py` — Position sizing for options (lot-based)
- [x] `paper_trader.py` — Paper trading engine with position persistence
- [x] `ml_predictor.py` — ML model inference wrapper

### ML Pipeline (v1)
- [x] `data_harvester.py` — 5-year NIFTY data downloader (chunked)
- [x] `feature_engineering.py` — 21 features from raw OHLCV
- [x] `model_training.py` — Gradient Boosting Classifier
- [x] `model_optimizer.py` — Hyperparameter optimization (RandomizedSearchCV)
- [x] Trained model saved as `trading_model.joblib`

### LLM & Sentiment
- [x] `llm_handler.py` — Initially Google Gemini, later migrated to Groq (Llama 4 Scout)
- [x] `news_handler.py` — Initially web scraping, later migrated to YFinance
- [x] `sentiment_engine.py` — Weighted NIFTY 50 sentiment scoring

### Equity Agent
- [x] `equity_main.py` — NIFTY 200 momentum scanner agent
- [x] `equity_scanner.py` — Volume surge detection with daily cache
- [x] `sector_mapper.py` — Stock-to-sector-index mapping
- [x] `nifty200_symbols.py` — NIFTY 200 symbol list
- [x] `consolidation_hunter_strategy.py` — BB Squeeze breakout strategy

---

## Phase 2: HFT Agent & Multi-Strategy Development

### HFT Agent
- [x] `hft_scalper_strategy.py` — Multi-signal scalper (EMA Cross + RSI Reversal + EMA Bounce)
- [x] `hft_equity_main.py` — HFT agent main loop
- [x] `liquidity_scanner.py` — Liquid stock scanner for HFT
- [x] `orderflow_analyzer.py` — Level 2 order book imbalance detector
- [x] `hft_scalper_backtester.py` — Backtesting framework for HFT strategy

### Strategy Library Expansion
- [x] `supertrend_vwap_strategy.py` — SuperTrend + VWAP with ADX filter
- [x] `supertrend_vwap_backtester.py` — Backtesting for SuperTrend
- [x] `combined_strategy.py` — Two-phase ORB + EMA Crossover
- [x] `combined_backtester.py` — Combined strategy backtester
- [x] `orb_strategy.py` — Initial ORB implementation
- [x] `backtester.py` — Generic equity backtester (Consolidation Hunter)

---

## Phase 3: ORB Scalper Agent & Web Dashboard

### ORB Scalper (Primary Live Agent)
- [x] `orb_scalper_strategy.py` — ORB with debit spread entry logic
- [x] `options_scalper_main.py` — Queue-based WebSocket architecture
- [x] Debit spread execution (buy ATM + sell OTM)
- [x] Dynamic option symbol discovery via Fyers symbol master
- [x] Per-index daily breakout tracking (NIFTY + BANKNIFTY)
- [x] Auto EOD square-off at 3:00 PM

### Web Dashboard
- [x] `web_dashboard.py` — Full Flask application (1,476 lines)
- [x] Live position monitoring for all 3 agents
- [x] WebSocket live price streaming
- [x] Manual Buy/Sell trade execution
- [x] Trade history table
- [x] Option chain viewer
- [x] REST API for all operations

---

## Phase 4: Bug Fixes & Refinements

### Critical Bug Fixes
- [x] **Short position risk:** `risk_manager.py` — Used `abs()` for risk-per-share
- [x] **Spread P&L on EOD:** `paper_trader.py` — Fixed net premium calculation for spread exits
- [x] **Logger initialization order:** `backtester.py` — Logger MUST init before imports
- [x] **Missing pandas import:** `paper_trader.py` — Added `import pandas as pd`
- [x] **Duplicate log handlers:** `logger_setup.py` — Clear existing handlers first

### API & Integration Fixes
- [x] **Symbol format discovery:** 18 iterative test scripts for Fyers option symbols
- [x] **WebSocket reconnection:** Error handlers and stability improvements
- [x] **Rate limiting:** Added `time.sleep()` delays for bulk API calls
- [x] **Margin API deprecated:** Built approximate SPAN margin calculator
- [x] **Token persistence:** Auto-cache access tokens across sessions

### Architecture Improvements
- [x] **LLM migration:** Google Gemini → Groq API (Llama 4 Scout) for speed
- [x] **News migration:** Custom scraping → YFinance for reliability
- [x] **Polling → Queue:** Options scalper moved to queue-based WebSocket architecture
- [x] **Position hot-reload:** Dashboard ↔ agent sync via file modification detection
- [x] **Volume caching:** Daily cache for 200-stock volume averages
- [x] **Demo mode:** Toggle in `technical_analyzer.py` for signal flexibility

---

## Phase 5: Testing & Validation

### Latency & Notification Testing
- [x] Fyers API execution latency measurement
- [x] Live trade notification system testing
- [x] Margin rejection handling verification

### Historical Options Data
- [x] `historical_options_harvester.py` — 60-day options data downloader
- [x] Parquet format storage for efficient backtesting
- [x] Updated backtester to use actual options data vs Black-Scholes simulation

### Live Paper Trading
- [x] 41+ trades executed across Feb 20-27, 2026
- [x] Both NIFTY and BANKNIFTY debit spreads
- [x] Equity trades (SIEMENS)
- [x] EOD auto square-off validation

---

*Last updated: February 27, 2026*
