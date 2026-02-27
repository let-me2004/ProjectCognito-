# orb_strategy.py - Opening Range Breakout Strategy for NIFTY Options
# =====================================================================
# The first 15 minutes (3 x 5-min candles) after market open define the
# Opening Range. A breakout above/below this range triggers a trade.

import logging

logger = logging.getLogger(__name__)

# --- Strategy Parameters ---
ORB_CANDLES = 3          # Number of 5-min candles for the opening range (15 mins)
RISK_REWARD_RATIO = 1.5  # Take Profit = 1.5x Risk
MAX_RANGE_PCT = 1.0      # Skip if range > 1% of price (too volatile/choppy)
MIN_RANGE_POINTS = 20    # Skip if range < 20 points (too narrow, likely fake breakout)


def get_orb_signal(day_candles):
    """
    Analyzes a single day's 5-min candles and returns the ORB signal.
    
    Args:
        day_candles: DataFrame of 5-min candles for ONE trading day.
                     Must have columns: open, high, low, close.
                     Index must be DateTimeIndex (UTC).
    
    Returns:
        dict with signal info, or None if no valid signal.
    """
    if len(day_candles) < ORB_CANDLES + 1:
        return None  # Not enough candles to form range + check breakout

    # --- Step 1: Define the Opening Range ---
    orb_candles = day_candles.iloc[:ORB_CANDLES]
    orb_high = orb_candles['high'].max()
    orb_low = orb_candles['low'].min()
    orb_range = orb_high - orb_low

    # --- Step 2: Apply Filters ---
    mid_price = (orb_high + orb_low) / 2
    range_pct = (orb_range / mid_price) * 100

    if range_pct > MAX_RANGE_PCT:
        return None  # Day is too choppy

    if orb_range < MIN_RANGE_POINTS:
        return None  # Range too narrow, likely fake breakout

    # --- Step 3: Scan for Breakout (candle by candle after ORB) ---
    breakout_candles = day_candles.iloc[ORB_CANDLES:]

    for idx in range(len(breakout_candles)):
        candle = breakout_candles.iloc[idx]
        candle_time = breakout_candles.index[idx]

        # Bullish Breakout: Close above ORB High
        if candle['close'] > orb_high:
            entry_price = candle['close']
            stop_loss = orb_low
            risk = entry_price - stop_loss
            take_profit = entry_price + (risk * RISK_REWARD_RATIO)

            return {
                'signal': 'BUY_CE',
                'entry_price': entry_price,
                'stop_loss': stop_loss,
                'take_profit': take_profit,
                'orb_high': orb_high,
                'orb_low': orb_low,
                'orb_range': orb_range,
                'entry_time': candle_time,
                'risk_points': risk
            }

        # Bearish Breakout: Close below ORB Low
        elif candle['close'] < orb_low:
            entry_price = candle['close']
            stop_loss = orb_high
            risk = stop_loss - entry_price
            take_profit = entry_price - (risk * RISK_REWARD_RATIO)

            return {
                'signal': 'BUY_PE',
                'entry_price': entry_price,
                'stop_loss': stop_loss,
                'take_profit': take_profit,
                'orb_high': orb_high,
                'orb_low': orb_low,
                'orb_range': orb_range,
                'entry_time': candle_time,
                'risk_points': risk
            }

    return None  # No breakout today
