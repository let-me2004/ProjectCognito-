import pandas_ta as ta
import pandas as pd
import logging

logger = logging.getLogger(__name__)

# --- Strategy Parameters ---
SQUEEZE_LENGTH = 20      # Bollinger Band length
SQUEEZE_THRESHOLD = 0.015 # How "tight" the squeeze needs to be (lower is tighter)
TREND_FILTER_LENGTH = 200 # The 200-period EMA for our trend filter
VOLUME_FILTER_LENGTH = 20 # The 20-period MA for our volume filter
REWARD_RISK_RATIO = 3.0   # 3:1 R:R
# -------------------------

def check_for_signal(df):
    """
    Analyzes data to find a trade signal, now with a 200-EMA trend filter
    AND a 20-MA volume filter.
    """
    if df.empty or len(df) < TREND_FILTER_LENGTH:
        return None # Not enough data for indicators

    try:
        # 1. Calculate Indicators
        df.ta.bbands(length=SQUEEZE_LENGTH, append=True)
        df.ta.ema(length=TREND_FILTER_LENGTH, append=True)
        df.ta.sma(close='volume', length=VOLUME_FILTER_LENGTH, append=True) # Volume MA
        
        bbw_col = f'BBW_{SQUEEZE_LENGTH}_2.0'
        bbu_col = f'BBU_{SQUEEZE_LENGTH}_2.0'
        bbl_col = f'BBL_{SQUEEZE_LENGTH}_2.0'
        bbm_col = f'BBM_{SQUEEZE_LENGTH}_2.0'
        ema_col = f'EMA_{TREND_FILTER_LENGTH}'
        vol_ma_col = f'SMA_{VOLUME_FILTER_LENGTH}'
        
        df[bbw_col] = (df[bbu_col] - df[bbl_col]) / df[bbm_col]
        
        # 2. Get the latest and previous candle's data
        latest = df.iloc[-1]
        previous = df.iloc[-2]

        # 3. The "Squeeze" Logic
        is_in_squeeze = previous[bbw_col] < SQUEEZE_THRESHOLD

        # 4. The "Breakout" Logic
        is_bullish_breakout = is_in_squeeze and latest['close'] > previous[bbu_col]
        is_bearish_breakout = is_in_squeeze and latest['close'] < previous[bbl_col]
        
        # 5. The "Trend Filter" Logic
        is_uptrend = latest['close'] > latest[ema_col]
        is_downtrend = latest['close'] < latest[ema_col]
        
        # 6. --- NEW: The "Volume Filter" Logic ---
        has_conviction = latest['volume'] > latest[vol_ma_col]

        # 7. Generate Signal (with 3-WAY CONFLUENCE)
        if is_bullish_breakout and is_uptrend and has_conviction:
            entry_price = latest['close']
            stop_loss_price = latest[bbm_col] # Stop at the middle band
            
            stop_points = entry_price - stop_loss_price
            if stop_points <= 0: return None # Invalid stop
            
            take_profit_price = entry_price + (stop_points * REWARD_RISK_RATIO)
            
            return {
                "signal": "BUY",
                "entry_price": entry_price, "stop_loss": stop_loss_price, "take_profit": take_profit_price,
                "reason": f"Bullish Squeeze Breakout (BBW: {previous[bbw_col]:.4f}) + Uptrend + Vol Conviction"
            }
            
        elif is_bearish_breakout and is_downtrend and has_conviction:
            entry_price = latest['close']
            stop_loss_price = latest[bbm_col] # Stop at the middle band

            stop_points = stop_loss_price - entry_price
            if stop_points <= 0: return None # Invalid stop
            
            take_profit_price = entry_price - (stop_points * REWARD_RISK_RATIO)
            
            return {
                "signal": "SELL",
                "entry_price": entry_price, "stop_loss": stop_loss_price, "take_profit": take_profit_price,
                "reason": f"Bearish Squeeze Breakout (BBW: {previous[bbw_col]:.4f}) + Downtrend + Vol Conviction"
            }

    except Exception as e:
        logger.error(f"Error in strategy logic: {e}", exc_info=True)
        
    return None # No signal

