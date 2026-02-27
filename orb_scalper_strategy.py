# orb_scalper_strategy.py - ORB Debit Spread Strategy for NIFTY/BANKNIFTY Options
# ==================================================================================
# Uses the Opening Range (first 15 mins) to detect breakouts, then enters
# debit spreads (buy ATM + sell 1-strike OTM) for defined-risk trades.

import logging
import datetime
import fyers_client

logger = logging.getLogger(__name__)

# --- Strategy Parameters ---
ORB_CANDLES = 3              # 3 × 5-min candles = 15 min opening range (9:15 - 9:30)
MAX_RANGE_PCT = 1.0          # Skip if ORB range > 1% of price (too choppy)
MIN_RANGE_POINTS_NIFTY = 30  # NIFTY: skip if range < 30 points
MIN_RANGE_POINTS_BANK = 80   # BANKNIFTY: skip if range < 80 points
SPREAD_WIDTH_NIFTY = 50      # 1 strike = 50 points for NIFTY
SPREAD_WIDTH_BANK = 100      # 1 strike = 100 points for BANKNIFTY
PROFIT_TARGET_PCT = 15.0     # Take profit at 15% of net debit
TRADING_START = datetime.time(9, 15)   # test mode
TRADING_END = datetime.time(23, 59)    # test mode

# Cache: computed once per day
_orb_cache = {}  # key=index_name, value={"date": date, "high": x, "low": y, "valid": bool}


def _get_orb_range(fyers_instance, index_name, fyers_symbol):
    """
    Compute today's Opening Range from 5-min candles.
    Returns dict with orb_high, orb_low, orb_range, or None if invalid.
    Caches result per index per day.
    """
    today = datetime.date.today()
    
    # Return cached value if already computed today
    if index_name in _orb_cache and _orb_cache[index_name]["date"] == today:
        cached = _orb_cache[index_name]
        if not cached["valid"]:
            return None
        return cached
    
    # Need at least 9:30 to have 3 complete 5-min candles
    now = datetime.datetime.now().time()
    if now < TRADING_START:
        logger.info(f"[ORB] {index_name}: Too early ({now}), ORB not formed yet")
        return None
    
    # Fetch today's 5-min candles
    try:
        df = fyers_client.get_historical_data(
            fyers_instance, fyers_symbol, "5",
            today, today
        )
        
        if df is None or df.empty:
            logger.warning(f"[ORB] {index_name}: No 5-min data available for today")
            return None
        
        if len(df) < ORB_CANDLES:
            logger.warning(f"[ORB] {index_name}: Only {len(df)} candles, need {ORB_CANDLES}")
            return None
        
        # First 3 candles = Opening Range (9:15, 9:20, 9:25)
        orb_candles = df.iloc[:ORB_CANDLES]
        orb_high = float(orb_candles['high'].max())
        orb_low = float(orb_candles['low'].min())
        orb_range = orb_high - orb_low
        
        # --- Filters ---
        min_range = MIN_RANGE_POINTS_NIFTY if index_name == "NIFTY" else MIN_RANGE_POINTS_BANK
        mid_price = (orb_high + orb_low) / 2
        range_pct = (orb_range / mid_price) * 100
        
        if orb_range < min_range:
            logger.info(f"[ORB] {index_name}: Range too narrow ({orb_range:.0f} pts < {min_range}). Skipping.")
            _orb_cache[index_name] = {"date": today, "valid": False}
            return None
        
        if range_pct > MAX_RANGE_PCT:
            logger.info(f"[ORB] {index_name}: Range too wide ({range_pct:.2f}% > {MAX_RANGE_PCT}%). Skipping.")
            _orb_cache[index_name] = {"date": today, "valid": False}
            return None
        
        result = {
            "date": today,
            "valid": True,
            "orb_high": orb_high,
            "orb_low": orb_low,
            "orb_range": orb_range
        }
        _orb_cache[index_name] = result
        logger.info(f"[ORB] {index_name}: ORB Range = {orb_low:.2f} - {orb_high:.2f} ({orb_range:.0f} pts)")
        return result
        
    except Exception as e:
        logger.error(f"[ORB] Error computing ORB for {index_name}: {e}", exc_info=True)
        return None


def get_orb_trade_signal(fyers_instance, index_name, fyers_symbol, current_ltp):
    """
    Check if a breakout has occurred and return a trade signal with spread legs.
    
    Args:
        fyers_instance: authenticated Fyers model
        index_name: "NIFTY" or "BANKNIFTY"
        fyers_symbol: "NSE:NIFTY50-INDEX" or "NSE:NIFTYBANK-INDEX"
        current_ltp: current index price from tick
        
    Returns:
        dict with trade signal and spread details, or None
    """
    # --- Time Window Check ---
    now = datetime.datetime.now().time()
    if now < TRADING_START:
        return None  # ORB not formed yet
    if now > TRADING_END:
        return None  # Past trading window
    
    # --- Get ORB Range ---
    orb = _get_orb_range(fyers_instance, index_name, fyers_symbol)
    if orb is None:
        return None
    
    # --- Check for Breakout ---
    signal = None
    
    if current_ltp > orb["orb_high"]:
        # Bullish breakout → Buy CE spread
        signal = {
            "direction": "BULLISH",
            "trade_type": "CE",
            "breakout_price": current_ltp,
            "orb_high": orb["orb_high"],
            "orb_low": orb["orb_low"],
            # SL: if price falls back below ORB low, breakout failed
            "index_stop_loss": orb["orb_low"],
            "index_sl_points": current_ltp - orb["orb_low"],
        }
        logger.info(f"[ORB] 🟢 BULLISH BREAKOUT on {index_name}! LTP {current_ltp:.2f} > ORB High {orb['orb_high']:.2f}")
        
    elif current_ltp < orb["orb_low"]:
        # Bearish breakout → Buy PE spread
        signal = {
            "direction": "BEARISH",
            "trade_type": "PE",
            "breakout_price": current_ltp,
            "orb_high": orb["orb_high"],
            "orb_low": orb["orb_low"],
            # SL: if price rises back above ORB high, breakout failed
            "index_stop_loss": orb["orb_high"],
            "index_sl_points": orb["orb_high"] - current_ltp,
        }
        logger.info(f"[ORB] 🔴 BEARISH BREAKOUT on {index_name}! LTP {current_ltp:.2f} < ORB Low {orb['orb_low']:.2f}")
    
    if signal is None:
        return None  # No breakout yet
    
    # --- Find Spread Legs ---
    spread_width = SPREAD_WIDTH_NIFTY if index_name == "NIFTY" else SPREAD_WIDTH_BANK
    option_type = signal["trade_type"]
    
    # Buy leg: ATM option
    buy_leg = fyers_client.find_option_by_offset(fyers_instance, index_name, option_type, 0)
    if not buy_leg or buy_leg['ltp'] <= 0:
        logger.warning(f"[ORB] Could not find ATM {option_type} for {index_name}")
        return None
    
    # Sell leg: 1-strike OTM
    sell_leg = fyers_client.find_option_by_offset(fyers_instance, index_name, option_type, 
                                                   1 if option_type == "PE" else 1)
    if not sell_leg or sell_leg['ltp'] <= 0:
        logger.warning(f"[ORB] Could not find OTM {option_type} for {index_name}")
        return None
    
    # Calculate spread economics
    net_debit = buy_leg['ltp'] - sell_leg['ltp']
    if net_debit <= 0:
        logger.warning(f"[ORB] Invalid spread: debit is {net_debit:.2f} (buy={buy_leg['ltp']}, sell={sell_leg['ltp']})")
        return None
    
    max_profit = spread_width - net_debit
    profit_target = net_debit * (PROFIT_TARGET_PCT / 100)
    
    signal.update({
        "buy_symbol": buy_leg['symbol'],
        "buy_ltp": buy_leg['ltp'],
        "sell_symbol": sell_leg['symbol'],
        "sell_ltp": sell_leg['ltp'],
        "net_debit": net_debit,
        "max_profit": max_profit,
        "profit_target": profit_target,
        "spread_width": spread_width,
        "spot_price": buy_leg.get('spot_price', current_ltp),
    })
    
    logger.info(f"[ORB] Spread: BUY {buy_leg['symbol']}@{buy_leg['ltp']:.2f} + SELL {sell_leg['symbol']}@{sell_leg['ltp']:.2f}")
    logger.info(f"[ORB] Net Debit: ₹{net_debit:.2f} | Max Profit: ₹{max_profit:.2f} | Target: ₹{profit_target:.2f}")
    
    return signal


def has_breakout_today(index_name):
    """Check if we already detected a breakout for this index today (avoid re-entry)."""
    today = datetime.date.today()
    if index_name in _orb_cache and _orb_cache[index_name].get("date") == today:
        return _orb_cache[index_name].get("breakout_taken", False)
    return False


def mark_breakout_taken(index_name):
    """Mark that we've already taken a trade on today's breakout for this index."""
    if index_name in _orb_cache:
        _orb_cache[index_name]["breakout_taken"] = True
