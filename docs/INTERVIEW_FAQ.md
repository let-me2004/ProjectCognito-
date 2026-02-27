# ProjectCognito — Interview & Viva FAQ Guide

> Use this document to confidently answer any question about the project.

---

## Q1: What is ProjectCognito?

**Answer:** ProjectCognito (CognitoTrader) is a multi-agent algorithmic trading platform I built from scratch in Python for the Indian stock market (NSE). It uses a hybrid of quantitative analysis, machine learning, and LLM-powered sentiment analysis to generate and execute trades. The system connects to the Fyers brokerage API for live market data via WebSocket feeds, runs 3 independent trading agents simultaneously, and provides a real-time web dashboard for monitoring at `localhost:5050`.

---

## Q2: What is the architecture? How is it designed?

**Answer:** The system follows a **layered, modular architecture**:

1. **Data Layer** — `fyers_client.py` handles all communication with the Fyers API (REST for historical data, WebSocket for real-time ticks)
2. **Strategy Layer** — 6 different strategy modules generate trade signals independently
3. **Decision Layer** — Technical analyzers, ML predictor, and LLM sentiment engine provide multi-filter confluence
4. **Execution Layer** — Risk manager validates position sizing, paper trader simulates execution with realistic brokerage fees
5. **Presentation Layer** — Flask web dashboard displays live positions, prices, and trade history

The agents run as independent Python processes. Each agent has its own position file (`paper_positions_*.json`), and the dashboard reads from all of them to show a unified view.

---

## Q3: What trading strategies did you implement?

**Answer:** I implemented **6 strategies** across options and equity markets:

| # | Strategy | Type | Frequency |
|---|----------|------|-----------|
| 1 | **Opening Range Breakout (ORB)** | Options (Debit Spreads) | 1-2 trades/day |
| 2 | **EMA Crossover + RSI Scalper** | Options | 10-20 trades/day |
| 3 | **SuperTrend + VWAP** | Options | 3-8 trades/day |
| 4 | **Combined ORB + EMA** | Options (Two-phase) | 5-15 trades/day |
| 5 | **Consolidation Hunter (BB Squeeze)** | Equity | 1-3 trades/day |
| 6 | **Weighted Confluence Breakout** | Options | Very selective |

My **primary live strategy** is ORB with Debit Spreads — it detects the first 15-minute range breakout and enters defined-risk spreads on NIFTY and BANKNIFTY.

---

## Q4: How does the ORB (Opening Range Breakout) strategy work?

**Answer:** 
1. **9:15-9:30 AM** — The system captures the high and low of the first 15 minutes (3 × 5-min candles). This is the "Opening Range."
2. **Validation** — The range must be between 20 points and 1% of price (neither too tight nor too wide).
3. **Breakout Detection** — Via WebSocket ticks, when price closes above the ORB high → LONG signal; below ORB low → SHORT signal.
4. **Entry** — Instead of buying naked options, I enter a **Debit Spread** (buy ATM option + sell OTM option 50 points away). This gives me defined risk and requires only ₹30k-40k margin.
5. **Exit** — Stop-loss at opposite ORB boundary + 5pt buffer; take-profit at 1.15× max spread profit. Auto square-off at 3:00 PM.
6. **Risk Control** — Max 1 trade per index per day, 10% risk per trade.

---

## Q5: Why did you choose Debit Spreads over naked options?

**Answer:** Three reasons:
1. **Defined Risk** — Max loss is limited to the net debit paid (premium difference), no unlimited downside
2. **Lower Margin** — A debit spread needs ₹30k-40k vs ₹1.5L+ for a naked option
3. **Theta Neutralization** — Both legs decay together, partially canceling time decay impact

The trade-off is capped profit, but for intraday scalping with defined exits, this is optimal.

---

## Q6: How does the ML pipeline work?

**Answer:** It's a full end-to-end pipeline:

1. **Data Harvesting** (`data_harvester.py`) — Downloads 5 years of 5-minute NIFTY candles (96,000+ data points) from Fyers API in chunks
2. **Feature Engineering** (`feature_engineering.py`) — Creates 21 features from raw OHLCV:
   - Momentum: RSI(14), MACD(12,26,9)
   - Trend: EMA(10), EMA(21), EMA(50), EMA(200)
   - Volatility: Bollinger Bands(20), ATR(14)
   - Custom: 1-hour return, 1-day return
3. **Label Creation** — Binary target: will price be higher in 30 minutes? (6 candles ahead)
4. **Training** (`model_training.py`) — Gradient Boosting Classifier with **time-series-aware split** (no shuffling — train on past 80%, test on future 20%)
5. **Optimization** (`model_optimizer.py`) — RandomizedSearchCV for hyperparameter tuning
6. **Inference** (`ml_predictor.py`) — Loads `.joblib` model, aligns feature columns, returns prediction

The model achieved **51% accuracy** on 19,000+ unseen test samples — which in financial markets is statistically meaningful when combined with proper risk management.

---

## Q7: How does the LLM integration work?

**Answer:** I use the **Groq API** with Meta's **Llama 4 Scout 17B** model for real-time sentiment analysis.

- **Persona:** The LLM acts as "Cognito" — a senior quantitative sentiment analyst
- **Input:** Technical snapshot + recent news headlines (fetched via YFinance)
- **Output:** Structured JSON: `{"outlook": "Bullish/Bearish/Neutral", "confidence": 0.0-1.0}`
- **Temperature:** 0.1 (nearly deterministic for consistency)
- **Response Format:** Forced JSON output to avoid parsing errors

The **Sentiment Engine** weighs individual stock sentiments by their NIFTY 50 index weight, then aggregates for a final market sentiment score. This is used as one of 5 filters in the Weighted Confluence strategy.

---

## Q8: What was the hardest bug you fixed?

**Answer:** The **Spread P&L calculation during EOD square-off** was the trickiest. 

When `close_all_positions()` ran at 3 PM, it was only using the buy leg's price to calculate exit P&L, ignoring the sell leg entirely. For a spread with a ₹20 debit, the system was reporting massive fictional losses because it treated the buy leg as a naked position.

The fix required modifying the `_close_position()` method to calculate the net premium of the spread (buy_exit_price - sell_exit_price) and compare that against the original net debit, not just one leg.

Another significant challenge was **Fyers API symbol discovery** — NSE option symbols follow a complex format (`NSE:NIFTY2630225350PE`) that changes with weekly/monthly expiry dates. I wrote 18 iterative test scripts to reverse-engineer the exact format and then built `find_option_by_offset()` using the Fyers symbol master CSV.

---

## Q9: What testing did you do?

**Answer:**
1. **Backtesting** — 4 different backtesting frameworks covering 60+ days of historical data across all strategies
2. **Paper Trading** — All 3 agents run in paper mode with realistic brokerage (₹40/trade)
3. **Unit Tests** — Individual test scripts for WebSocket connectivity, API calls, symbol lookup, margin API, notifications, and order placement
4. **Live Market Validation** — 41+ trades executed with real market data on paper accounts
5. **Latency Testing** — Measured API call latency to ensure sub-second execution (conversation with Fyers API team)

---

## Q10: How does the web dashboard work?

**Answer:** It's a **Flask web server** (port 5050) with a single-page application:

- **Backend:** Flask serves HTML with embedded CSS/JS, plus REST API endpoints
- **Live Prices:** Background thread connects to Fyers WebSocket, stores ticks in memory dict, frontend polls every 2 seconds
- **Position Sync:** Reads all 3 agent JSON files to show unified view
- **Manual Trading:** Buy/Sell forms submit to API endpoints that write to position files (agents hot-reload)
- **Trade History:** Reads `trade_log.csv` and displays in a table

---

## Q11: How would you deploy this to the cloud?

**Answer:** I would use **AWS EC2** (t3.small, ~$15/month):

1. **EC2 Instance** — Run all agents + dashboard 24/7 with auto-recovery
2. **PostgreSQL (RDS)** — Replace JSON files with proper database for ACID compliance
3. **CloudWatch** — Monitor agent health, set alarms for crashes
4. **Docker** — Containerize for reproducible deployments
5. **systemd** — Auto-restart crashed processes
6. **Telegram/Discord Bot** — Push trade alerts to phone
7. **S3** — Daily backups of trade logs and models

**Key benefits:** No system crash risk, no internet outage risk, 99.9% uptime SLA, accessible from anywhere.

---

## Q12: What would you improve next?

**Answer:**
1. **Live Trading Toggle** — Switch from paper to live with margin verification
2. **Database Migration** — PostgreSQL for position persistence (JSON files are fragile)
3. **Advanced ML** — LSTM/Transformer models for time-series prediction
4. **Options Greeks** — Real-time delta/gamma/theta for spread management
5. **Performance Dashboard** — Sharpe ratio, max drawdown, equity curve charts
6. **Multi-Broker** — Abstract broker layer for Zerodha, Angel One support
7. **Circuit Breaker** — Auto-disable agents after 3 consecutive losses

---

## Q13: What technical indicators do you use?

**Answer:**
| Indicator | Parameters | Used In |
|-----------|-----------|---------|
| EMA (Exponential Moving Average) | 5, 9, 13, 21, 50, 200 | All strategies |
| RSI (Relative Strength Index) | 7, 14 | HFT Scalper, ML |
| MACD | 12, 26, 9 | ML Features |
| Bollinger Bands | 20-period | Consolidation Hunter, ML |
| ATR (Average True Range) | 14-period | Risk management, SuperTrend |
| SuperTrend | Period=10, Mult=2.0 | SuperTrend strategy |
| VWAP | Intraday | SuperTrend strategy |
| ADX | 14-period | SuperTrend, trend filter |

---

## Q14: What APIs and external services do you use?

**Answer:**
| Service | Purpose | Module |
|---------|---------|--------|
| **Fyers API v3** | Market data, order placement, WebSocket | `fyers_client.py` |
| **Groq API** | LLM inference (Llama 4 Scout) | `llm_handler.py` |
| **YFinance** | Stock news headlines | `news_handler.py` |
| **Fyers Symbol Master** | Dynamic option symbol discovery | `fyers_client.py` |

---

## Q15: How do you handle risk management?

**Answer:** Multi-layered risk management:

1. **Position Sizing** — Risk % of account per trade (configurable, default 10%)
2. **Stop-Loss** — ATR-based or fixed-point stop-losses on every position
3. **Lot Limiting** — Default 1 lot for options (conservative)
4. **Max Positions** — Configurable limit (default 5 for equity)
5. **EOD Square-Off** — All positions auto-closed at 3:00 PM
6. **Defined Risk Spreads** — Debit spreads cap maximum loss
7. **Margin Checks** — Verify available margin before live trades
8. **One-Trade-Per-Day** — ORB strategy allows max 1 breakout trade per index

---

*Prepared: February 27, 2026*
