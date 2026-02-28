# ProjectCognito — Options Agent: Complete Technical Documentation

> **Last Updated:** 28 February 2026  
> **Version:** 2.0  
> **Primary File:** `options_scalper_main.py`  
> **Status:** Production-Ready (Paper + Live)

---

## Table of Contents

1. [Project Overview](#1-project-overview)
2. [Strategy: Opening Range Breakout (ORB)](#2-strategy-opening-range-breakout-orb)
3. [Trade Instrument: Debit Spreads](#3-trade-instrument-debit-spreads)
4. [System Architecture](#4-system-architecture)
5. [Data Pipeline & WebSocket](#5-data-pipeline--websocket)
6. [Dynamic Symbol Resolution](#6-dynamic-symbol-resolution)
7. [Execution Flow (Step-by-Step)](#7-execution-flow-step-by-step)
8. [Risk Management Layers](#8-risk-management-layers)
9. [Live Trading Safeguards](#9-live-trading-safeguards)
10. [Latency Tracking](#10-latency-tracking)
11. [Paper Trading Engine](#11-paper-trading-engine)
12. [Web Dashboard](#12-web-dashboard)
13. [Configuration Reference](#13-configuration-reference)
14. [File Reference](#14-file-reference)
15. [Known Issues & Fixes](#15-known-issues--fixes)
16. [Changelog](#16-changelog)

---

## 1. Project Overview

ProjectCognito's **Options Agent** is an automated intraday trading bot that trades **NIFTY** and **BANKNIFTY** index options using the **Opening Range Breakout (ORB)** strategy. Instead of buying naked options (which carry unlimited risk from theta decay), the bot constructs **hedged debit spreads** — buying an ATM option and simultaneously selling an OTM option — for defined-risk, capital-efficient trades.

### Why This Approach?

| Problem | Solution |
|---|---|
| Naked options lose value every second (Theta decay) | Debit spreads neutralize Theta — the sold leg decays in your favor |
| Nifty options require ₹1L+ margin for naked selling | Spreads require only ~₹36k–₹45k margin per trade |
| Directional bias is hard to predict | ORB strategy only trades confirmed momentum breakouts |
| Manual trading is slow and emotional | Fully automated with millisecond-precision exits |

### Capital Requirements

| Scenario | Capital Needed |
|---|---|
| 1 Nifty spread | ~₹36,500 |
| 1 BankNifty spread | ~₹42,500 |
| 4 simultaneous spreads (max) | ~₹1,60,000 – ₹1,70,000 |
| Recommended account size | ₹2,00,000 |

---

## 2. Strategy: Opening Range Breakout (ORB)

### What is the Opening Range?

The **Opening Range (OR)** is the price range established by the market during the first 15 minutes of trading (9:15 AM – 9:30 AM IST). This range is defined by the **highest high** and **lowest low** of the first three 5-minute candles.

### How the Breakout Works

```
ORB High: 25,400 ────────────────── ← Bullish breakout level
                  │  Opening Range  │
ORB Low:  25,350 ────────────────── ← Bearish breakout level
```

- **Bullish Breakout:** If price closes above the ORB High → Buy a **Call (CE) Spread**
- **Bearish Breakout:** If price closes below the ORB Low → Buy a **Put (PE) Spread**

### Strategy Parameters

| Parameter | Value | Source File |
|---|---|---|
| ORB Candles | 3 (first 15 minutes) | `orb_scalper_strategy.py` |
| Min Range (Nifty) | 30 points | Filters out choppy, sideways days |
| Min Range (BankNifty) | 80 points | Filters out choppy, sideways days |
| Max Range | 1% of price | Filters out gap-up/gap-down chaos days |
| Trading Window | 9:15 AM – 11:15 AM IST | Momentum is strongest in the morning |
| Profit Target | 15% of net debit | e.g., ₹20 debit → exit at ₹23 spread value |
| Stop Loss | Index-based (ORB invalidation) | If price reverses back through the entire ORB range |

### Filters That Prevent Bad Trades

1. **Range Too Narrow:** If the ORB range is less than 30 pts (Nifty) or 80 pts (BankNifty), the day is likely choppy — no trades taken.
2. **Range Too Wide:** If the ORB range exceeds 1% of the index price, it signals a gap-up/gap-down day where false breakouts are common — no trades taken.
3. **One Trade Per Index Per Day:** Once the bot takes a trade on a breakout, it marks that index as "taken" and won't re-enter on the same day (prevents whipsaws).

---

## 3. Trade Instrument: Debit Spreads

### What is a Debit Spread?

A debit spread combines two options:
- **Buy Leg:** ATM (At-The-Money) option — this is the directional bet
- **Sell Leg:** OTM (Out-of-The-Money) option, 1 strike away — this collects premium to offset the cost

### Example: Bearish Breakout on Nifty at 25,300

| Leg | Action | Symbol | Premium | Qty |
|---|---|---|---|---|
| Buy Leg (ATM) | BUY | NSE:NIFTY2630225300PE | ₹95.00 | 65 |
| Sell Leg (OTM) | SELL | NSE:NIFTY2630225250PE | ₹74.85 | 65 |

**Spread Economics:**
- **Net Debit (Cost):** ₹95.00 − ₹74.85 = **₹20.15 per share**
- **Max Loss:** ₹20.15 × 65 = **₹1,309.75** (if spread goes to zero)
- **Spread Width:** 25300 − 25250 = **50 points**
- **Max Profit:** (50 − 20.15) × 65 = **₹1,940.25** (if spread reaches full width)
- **Profit Target (15%):** ₹20.15 × 0.15 = **₹3.02** → Exit when spread value = ₹23.17

### Why Spreads Instead of Naked Options?

| Metric | Naked Option | Debit Spread |
|---|---|---|
| Margin Required | ₹80,000+ | ~₹36,500 |
| Theta Decay | Working against you every second | Partially neutralized by sold leg |
| Max Loss | Entire premium paid | Net debit only (smaller) |
| Max Profit | Unlimited | Capped at spread width |
| Volatility Impact | Fully exposed to IV crush | Reduced by sold leg |

---

## 4. System Architecture

### High-Level Flow

```
┌─────────────────┐
│  Fyers WebSocket │ ← Real-time ticks (NIFTY, BANKNIFTY, option legs)
└────────┬────────┘
         │ tick_data
         ▼
┌─────────────────┐
│   Tick Queue     │ ← Thread-safe queue.Queue()
└────────┬────────┘
         │ tick = queue.get_nowait()
         ▼
┌─────────────────────────────────────────────────────┐
│              FAST LOOP (every tick)                  │
│                                                     │
│  1. Update _latest_ltp dict                         │
│  2. Check Stop-Loss on every index tick             │
│  3. Check Take-Profit on every option tick          │
│  4. Check for new ORB Breakout signals              │
│  5. Execute spread (Paper or Live)                  │
└────────┬────────────────────────────────────────────┘
         │ every 30 seconds
         ▼
┌─────────────────────────────────────────────────────┐
│              SLOW LOOP (every 30s)                  │
│                                                     │
│  1. Sync positions from JSON file                   │
│  2. Print summary to terminal                       │
│  3. Check EOD Auto Square-Off (3:00 PM)             │
└─────────────────────────────────────────────────────┘
```

### Threading Model

| Thread | Purpose |
|---|---|
| **WebSocket Thread** | Receives live ticks from Fyers and pushes them into `tick_queue` |
| **Main Thread** | Runs `analysis_and_trading_loop()` — drains queue and executes strategy |

The WebSocket callback (`on_index_tick`) does zero processing — it simply pushes raw tick dicts into a `queue.Queue()`. This ensures the WebSocket thread never blocks, even if the strategy takes 300ms+ to execute an order.

---

## 5. Data Pipeline & WebSocket

### Connection Flow

1. Bot authenticates with Fyers OAuth2 using `config.py` credentials
2. Access token is cached in `access_token.txt` (reused until expiry)
3. WebSocket connects to Fyers Level 1 data feed
4. Subscribes to `NSE:NIFTY50-INDEX` and `NSE:NIFTYBANK-INDEX`
5. When a position is opened, dynamically subscribes to the option leg symbols

### Tick Data Format

Each tick arrives as a dictionary:
```python
{
    "symbol": "NSE:NIFTY50-INDEX",
    "ltp": 25300.15,
    "vol_traded_today": 1234567,
    "last_traded_time": 1709117421,
    ...
}
```

### REST API Fallback

The web dashboard uses a REST API fallback (`fyers_model.quotes()`) to fetch live quotes when WebSocket data is unavailable, ensuring the dashboard's LIVE LTP display remains populated.

---

## 6. Dynamic Symbol Resolution

### The Problem

Fyers options symbols follow a very specific format:
```
NSE:NIFTY2630225300PE
     └──┘└───┘└────┘└┘
      │    │     │    └─ Option type (CE/PE)
      │    │     └────── Strike price
      │    └──────────── Expiry date (YYMDD format)
      └───────────────── Underlying name
```

Exchange rules change regularly (lot sizes, expiry days, holidays), making hardcoded symbols unreliable.

### The Solution: Fyers Symbol Master

The bot downloads the official **Fyers Symbol Master CSV** (`NSE_FO.csv`) daily and caches it in memory.

**How it works (`fyers_client.find_option_by_offset()`):**

1. Fetch the live spot price of the index (e.g., NIFTY at 25,300)
2. Round to the nearest strike interval (50 for Nifty, 100 for BankNifty) → ATM strike = 25,300
3. Apply offset (0 = ATM, 1 = 1 strike OTM, etc.) → target strike = 25,250
4. Search the Symbol Master CSV for rows matching:
   - Underlying = "NIFTY"
   - Strike Price = 25,250
   - Option Type = "PE"
5. Sort by expiry date (ascending) → pick the nearest valid expiry
6. Validate the symbol by fetching a live quote — if LTP > 0, it is confirmed as active
7. Return the validated symbol with its live price

### Key CSV Columns Used

| Column Index | Content |
|---|---|
| 9 | Full Fyers symbol (e.g., `NSE:NIFTY2630225300PE`) |
| 13 | Underlying name (e.g., `NIFTY`) |
| 15 | Strike price (e.g., `25300.0`) |
| 16 | Option type (`CE`, `PE`, or `XX`) |
| 8 | Expiry epoch timestamp |

---

## 7. Execution Flow (Step-by-Step)

### Phase 1: Initialization (Before Market Open)

1. Authenticate with Fyers API
2. Load paper account from `paper_positions_scalper.json`
3. Start WebSocket and subscribe to index symbols
4. Launch the analysis loop on the main thread

### Phase 2: ORB Formation (9:15 AM – 9:30 AM)

1. Bot receives live index ticks via WebSocket
2. At 9:30 AM, fetches the first 3 five-minute candles for the day
3. Computes ORB High and ORB Low
4. Validates the range (not too narrow, not too wide)
5. Caches the ORB values for the entire trading day

### Phase 3: Breakout Detection (9:30 AM – 11:15 AM)

1. Every tick, the bot compares the live index price against the ORB range
2. If `LTP > ORB High` → Bullish signal generated
3. If `LTP < ORB Low` → Bearish signal generated
4. On signal, resolves the exact option symbols via Symbol Master lookup
5. Fetches live quotes for both legs to calculate spread economics

### Phase 4: Trade Execution

**Paper Mode (`LIVE_TRADING = False`):**
1. Records spread in `paper_positions_scalper.json`
2. Subscribes WebSocket to both option legs for live monitoring

**Live Mode (`LIVE_TRADING = True`):**
1. Queries Fyers `funds()` API for available balance
2. Calculates required margin (₹36,500 for Nifty, ₹42,500 for BankNifty)
3. Blocks trade if balance < required margin
4. Calculates limit prices (1% buffer for IOC execution)
5. Sends multi-leg order via `fyers.place_multileg_order()`
6. Logs API round-trip latency in milliseconds
7. Records trade in paper account for dashboard tracking

### Phase 5: Position Monitoring (Every Tick)

Two exit mechanisms run on every single incoming tick:

**Stop-Loss (Index-Based):**
- For Call Spreads: if index drops below ORB Low → close position
- For Put Spreads: if index rises above ORB High → close position
- Rationale: the breakout has been completely invalidated

**Take-Profit (Premium-Based):**
- Monitors the live spread value (buy LTP − sell LTP)
- If spread value ≥ entry debit + 15% → close position
- Example: entered at ₹20.15, target = ₹23.17

### Phase 6: EOD Auto Square-Off (3:00 PM)

1. At 3:00 PM, fetches final quotes for all open positions
2. Closes every position at the current market price
3. Logs the P&L summary
4. Gracefully shuts down the bot

---

## 8. Risk Management Layers

The bot implements **6 independent layers** of risk protection:

### Layer 1: ORB Range Filters
Prevents trading on choppy or gap days by requiring the morning range to be within acceptable bounds.

### Layer 2: Risk Budget Per Trade
Each trade's maximum possible loss (net debit × lot size) must be ≤ 1% of account balance.
```
Example: ₹2,00,000 × 1% = ₹2,000 max risk per trade
         ₹20.15 debit × 65 qty = ₹1,309 → PASS ✅
```

### Layer 3: Position Count Limit
Hard cap at 4 simultaneous open positions.

### Layer 4: One Breakout Per Index Per Day
After taking a trade on a NIFTY breakout, the bot will not take another NIFTY trade that day, even if the price breaks out again (prevents whipsaw losses).

### Layer 5: Live Margin Check (Live Mode Only)
Queries the broker's real-time available balance before every trade. Blocks execution if the margin is insufficient.

### Layer 6: EOD Auto Square-Off
All positions are forcibly closed at 3:00 PM IST to prevent overnight exposure.

---

## 9. Live Trading Safeguards

### Margin Check

Before every live trade, the bot pings `fyers.funds()` to get the real Available Balance:

```python
live_balance = fyers_client.get_available_margin(fyers_model)
min_margin_required = fyers_client.calculate_spread_margin(tick_index_name)
# NIFTY: ₹36,500 | BANKNIFTY: ₹42,500

if live_balance < min_margin_required:
    logger.warning("🚨 LIVE TRADING BLOCKED: Insufficient free margin")
    continue  # Skip this trade
```

If the Fyers API fails or returns an unexpected format, the bot falls back to `config.ACCOUNT_BALANCE` to avoid accidentally blocking valid trades.

### Multi-Leg Order Execution

Live orders are sent as IOC (Immediate or Cancel) limit orders with a 1% price buffer:

| Parameter | Value |
|---|---|
| Order Type | `2L` (Two-Leg) |
| Validity | `IOC` |
| Product Type | `MARGIN` |
| Buy Limit | LTP × 1.01 (1% above market) |
| Sell Limit | LTP × 0.99 (1% below market) |

### NoneType Safety

If Fyers' API returns `None` (happens on instant rejections), the bot catches it cleanly instead of crashing:
```python
if response is None:
    return {"status": "error", "message": "Fyers API returned None"}
```

---

## 10. Latency Tracking

Every Fyers API order call is wrapped with `time.time()` precision timing:

```
⏱️ FYERS API ENTRY EXECUTION LATENCY: 333.68 ms
⏱️ FYERS API TARGET EXECUTION LATENCY: 210.50 ms
⏱️ FYERS API SL EXECUTION LATENCY: 180.15 ms
```

This measures the complete round-trip time:
1. Python constructs the order payload
2. HTTPS POST is sent to Fyers servers in Mumbai
3. Fyers processes the multi-leg order
4. Response travels back to your PC

**Observed latency:** ~330–350ms on a standard Indian broadband connection.

---

## 11. Paper Trading Engine

The `PaperAccount` class (`paper_trader.py`) simulates a full trading account:

- **Balance Tracking:** Maintains initial balance, realized P&L, and used margin
- **Position Management:** Stores open spreads with all metadata (entry prices, stops, targets)
- **Persistence:** Saves/loads positions from `paper_positions_scalper.json`
- **Trade Logging:** Appends every closed trade to `trade_log.csv` with timestamps
- **Summary Reports:** Prints win rate, profit factor, average win/loss after every analysis cycle

### Position JSON Structure

```json
{
    "NSE:NIFTY2630225300PE": {
        "is_spread": true,
        "sell_symbol": "NSE:NIFTY2630225250PE",
        "qty": 65,
        "direction": "LONG SPREAD (SHORT)",
        "sim_entry_price": 20.15,
        "sim_stop_loss_price": 0,
        "sim_take_profit_price": 23.17,
        "index_entry_price": 25300.15,
        "index_stop_loss_price": 25400.0,
        "spread_width": 50
    }
}
```

---

## 12. Web Dashboard

`web_dashboard.py` serves a real-time browser UI showing:

- Live positions with current spread value and P&L
- Account balance and margin usage
- Live LTP for all subscribed symbols (with REST API fallback)
- Trade history from `trade_log.csv`

Access it by running `python web_dashboard.py` in a separate terminal.

---

## 13. Configuration Reference

### `config.py` (gitignored — contains API keys)

| Variable | Description | Example |
|---|---|---|
| `FYERS_APP_ID` | Your Fyers API app ID | `"ABCDEF1234-100"` |
| `FYERS_SECRET_KEY` | Your Fyers API secret | `"XXXXXXXXXX"` |
| `FYERS_REDIRECT_URI` | OAuth2 redirect URL | `"https://trade.fyers.in/..."` |
| `ACCOUNT_BALANCE` | Starting paper balance | `200000.0` |
| `RISK_PERCENTAGE` | Max risk per trade (%) | `1.0` |

### `options_scalper_main.py` (Strategy Constants)

| Variable | Value | Description |
|---|---|---|
| `MAX_OPEN_POSITIONS` | `4` | Maximum simultaneous spread positions |
| `RISK_PERCENTAGE` | `1.0` | Max risk per trade as % of balance |
| `ANALYSIS_INTERVAL` | `30` | Seconds between terminal summary prints |
| `LIVE_TRADING` | `False` | Toggle paper/live mode |

### `orb_scalper_strategy.py` (ORB Parameters)

| Variable | Value | Description |
|---|---|---|
| `ORB_CANDLES` | `3` | Number of 5-min candles for ORB |
| `MAX_RANGE_PCT` | `1.0` | Skip if ORB range > 1% of price |
| `MIN_RANGE_POINTS_NIFTY` | `30` | Skip if Nifty range < 30 pts |
| `MIN_RANGE_POINTS_BANK` | `80` | Skip if BankNifty range < 80 pts |
| `SPREAD_WIDTH_NIFTY` | `50` | Nifty strike interval |
| `SPREAD_WIDTH_BANK` | `100` | BankNifty strike interval |
| `PROFIT_TARGET_PCT` | `15.0` | Take profit at 15% of net debit |
| `TRADING_START` | `9:15 AM` | ORB scanning begins |
| `TRADING_END` | `11:15 AM` | No new entries after this time |

---

## 14. File Reference

| File | Purpose |
|---|---|
| `options_scalper_main.py` | Main bot entry point — WebSocket loop, strategy execution, position management |
| `orb_scalper_strategy.py` | ORB breakout detection, spread leg construction, signal generation |
| `fyers_client.py` | Fyers API wrapper — auth, WebSocket, orders, quotes, margin, symbol master |
| `paper_trader.py` | Paper trading engine — positions, P&L, balance, trade log |
| `risk_manager.py` | Lot sizes, position sizing rules |
| `web_dashboard.py` | Real-time browser dashboard with REST fallback |
| `config.py` | API keys and account configuration (gitignored) |
| `logger_setup.py` | Rotating file + console logger setup |
| `paper_positions_scalper.json` | Persistent storage for open paper positions |
| `trade_log.csv` | Historical record of all closed trades |
| `access_token.txt` | Cached Fyers OAuth2 token |

---

## 15. Known Issues & Fixes

### Issue: Fyers Multi-Leg Order Returns `None`
**Cause:** When the account has ₹0 balance, Fyers' backend silently drops the multi-leg request without generating an Order ID.  
**Fix:** Added `if response is None:` check in `place_multileg_order()`. Falls back gracefully.

### Issue: Symbol Master Column Mapping
**Cause:** The Fyers CSV uses undocumented column indices. Initial attempts used wrong columns for strike price and option type.  
**Fix:** Mapped to Column 15 (Strike Price) and Column 16 (Option Type) after exhaustive testing.

### Issue: WebSocket Log Spam
**Cause:** Invalid symbols generated `WARNING` logs every tick, flooding the terminal.  
**Fix:** Downgraded invalid symbol logs from `warning` to `debug` level.

### Issue: Bot Shutting Down at Max Positions
**Cause:** The bot called `exit(0)` when `MAX_OPEN_POSITIONS` was reached.  
**Fix:** Changed to `continue` — bot keeps monitoring existing positions for exits while blocking new entries.

### Issue: Fyers `funds()` API Returning ₹0.00
**Cause:** API sometimes returns an unexpected JSON structure during server lag.  
**Fix:** Added fallback to `config.ACCOUNT_BALANCE` if the live API parse fails.

---

## 16. Changelog

### v2.0 — February 27, 2026
- Added live margin checks before trade execution
- Added millisecond latency tracking for all order types
- Implemented dynamic Fyers Symbol Master CSV lookup
- Fixed bot shutdown bug at max positions
- Added `NoneType` safety for Fyers API rejections
- Added REST API fallback for web dashboard quotes
- Bypassed margin block for latency testing (temporary, reverted)
- Pushed all changes to GitHub

### v1.0 — February 23–25, 2026
- Initial ORB Debit Spread Scalper implementation
- WebSocket real-time tick processing with queue architecture
- Paper trading engine with JSON persistence
- Web dashboard with live P&L display
- Trade logging to CSV
- EOD auto square-off at 3:00 PM
- Multi-index support (NIFTY + BANKNIFTY)
