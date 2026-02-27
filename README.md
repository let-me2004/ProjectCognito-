# ProjectCognito — Algorithmic Options & Equity Trading Bot

An automated trading system built in Python that trades **NIFTY** and **BANKNIFTY** index option spreads using the **Fyers API**. The bot detects intraday breakouts via the Opening Range Breakout (ORB) strategy, executes hedged debit spreads for defined-risk trades, and monitors positions with millisecond-precision exit logic — all powered by a real-time WebSocket data feed.

---

## 🚀 Key Features

- **Live Fyers API Integration** — Authenticates via OAuth2, streams real-time tick data over WebSocket, and places multi-leg spread orders directly on NSE.
- **Opening Range Breakout (ORB) Strategy** — Identifies the first 15-minute price range and triggers entries on confirmed breakouts.
- **Hedged Debit Spreads** — Buys ATM options and sells OTM options simultaneously for defined-risk, capital-efficient trades (~₹36k–₹45k margin per spread).
- **Dynamic Symbol Lookup** — Downloads and caches the Fyers Symbol Master CSV daily to resolve correct option symbols, handling exchange lot size changes and holiday-shifted expiries automatically.
- **Live Margin Checks** — Queries your Fyers account balance in real-time before every trade to prevent over-leveraging.
- **Millisecond Latency Tracking** — Measures exact round-trip API execution time for every entry, stop-loss, and take-profit order.
- **Paper Trading Mode** — Full simulation environment with JSON-based position tracking, P&L calculation, and trade logging.
- **Web Dashboard** — Real-time browser UI showing live positions, P&L, and market data with REST API fallback for quotes.
- **EOD Auto Square-Off** — Automatically closes all open positions at 3:00 PM IST to avoid overnight risk.

---

## 📊 Trading Strategies

### ORB Debit Spread Scalper (`options_scalper_main.py`)

The primary strategy. Designed for capital-efficient, defined-risk intraday option trading.

| Parameter | Value |
|---|---|
| Instruments | NIFTY 50, BANKNIFTY |
| Entry Window | 9:15 AM – 11:15 AM IST |
| ORB Period | First 15 minutes (3 × 5-min candles) |
| Trade Type | Debit Spread (Buy ATM + Sell 1-strike OTM) |
| Max Positions | 4 simultaneous spreads |
| Risk Per Trade | 1% of account balance |
| Profit Target | 15% of net debit |
| Stop Loss | Index-based (ORB range invalidation) |
| Margin Required | ~₹36,500 (Nifty) / ~₹42,500 (BankNifty) per spread |

**How it works:**
1. Calculates the Opening Range (High/Low) from the first 15 minutes of trading.
2. Waits for price to break above the ORB High (bullish) or below the ORB Low (bearish).
3. On breakout, constructs a debit spread: buys ATM option + sells 1-strike OTM option.
4. Monitors positions tick-by-tick for stop-loss (index reversal) and take-profit (spread value target).
5. Auto squares-off all remaining positions at 3:00 PM.

### Equity Surge Scanner (`equity_main.py`)

Scans the NIFTY 200 universe for intraday momentum plays based on price change and volume surges.

### HFT Order Flow Scalper (`hft_equity_main.py`)

A high-frequency scalping agent that analyzes Level 2 order book imbalances on liquid stocks.

---

## 🏗️ Architecture

```
ProjectCognito/
├── options_scalper_main.py    # Main ORB spread scalper (primary bot)
├── orb_scalper_strategy.py    # ORB breakout detection & spread construction
├── fyers_client.py            # Fyers API wrapper (auth, orders, WebSocket, margin)
├── paper_trader.py            # Paper trading engine with P&L tracking
├── risk_manager.py            # Position sizing & risk rules
├── web_dashboard.py           # Real-time web UI dashboard
├── config.py                  # API keys & configuration (gitignored)
├── equity_main.py             # Equity momentum scanner
├── hft_equity_main.py         # HFT order book scalper
├── orb_backtester.py          # ORB strategy backtester
├── combined_backtester.py     # Multi-strategy backtester
└── trade_log.csv              # Historical trade records
```

---

## ⚙️ Setup

### Prerequisites
- Python 3.10+
- A [Fyers](https://fyers.in) trading account with API access

### Installation

```bash
git clone https://github.com/let-me2004/AI-Trading-Agent-.git
cd AI-Trading-Agent-
python -m venv venv
.\venv\Scripts\activate      # Windows
pip install -r requirements.txt
```

### Configuration

Create a `config.py` file in the root directory:

```python
FYERS_APP_ID = "your_app_id"
FYERS_SECRET_KEY = "your_secret_key"
FYERS_REDIRECT_URI = "https://trade.fyers.in/api-login/redirect-uri/index.html"
ACCOUNT_BALANCE = 200000.0    # Your trading capital in INR
RISK_PERCENTAGE = 1.0         # Max risk per trade (%)
```

### Running

```bash
# Paper trading (default)
python options_scalper_main.py

# Web dashboard (run in a separate terminal)
python web_dashboard.py
```

To enable live trading, set `LIVE_TRADING = True` in `options_scalper_main.py` (Line 29).

---

## 📈 Live Trading Safeguards

The bot includes multiple layers of protection for live execution:

1. **Margin Gate** — Queries Fyers `funds()` API before every trade. Blocks entry if available balance < required spread margin.
2. **Position Limits** — Hard cap of 4 simultaneous positions to prevent over-exposure.
3. **Risk Budget** — Each trade's max loss (net debit × lot size) must fit within 1% of account balance.
4. **Latency Logging** — Every API call is timed to the millisecond, letting you monitor execution quality.
5. **EOD Square-Off** — All positions auto-close at 3:00 PM to eliminate overnight risk.
6. **NoneType Safety** — Gracefully handles Fyers API returning `None` on rejected orders without crashing.

---

## 📉 Performance

The bot logs all trades to `trade_log.csv` with entry/exit timestamps, P&L, and position details for post-market analysis.

---

## 🛠️ Tech Stack

| Component | Technology |
|---|---|
| Language | Python 3.10+ |
| Broker API | Fyers API v3 |
| Data Feed | WebSocket (real-time ticks) |
| Data Processing | Pandas, NumPy |
| Technical Analysis | Pandas-TA |
| Web Dashboard | Flask / HTML |
| Version Control | Git |

---

## ⚠️ Disclaimer

This project is for **educational and research purposes only**. Trading financial derivatives involves significant risk of loss. The strategies implemented here are not guaranteed to be profitable. Do not deploy with real capital unless you fully understand the risks involved.

---

## 📜 License

MIT License
