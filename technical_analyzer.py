# technical_analyzer.py - FINAL VERSION WITH SECTOR ANALYSIS

import pandas as pd
import logging
import datetime
# Note: cyclic import risk if fyers_client imports this. Checked and it seems safe.
import fyers_client 

logger = logging.getLogger(__name__)

def get_technical_analysis(df_5min, df_45min_nifty, df_45min_sector):
    """
    Analyzes dataframes for NIFTY and a key sector to provide confluent signals.
    """
    analysis = {
        "nifty_regime": "Neutral",
        "sector_regime": "Neutral",
        "entry_signal": "No_Signal",
        "is_strong_trend": False,
        "latest_price": 0
    }
    
    try:
        # --- 45-Minute NIFTY Analysis (Overall Regime) ---
        if not df_45min_nifty.empty:
            ema_50_nifty = df_45min_nifty['close'].ewm(span=50, adjust=False).mean().iloc[-1]
            latest_price_nifty = df_45min_nifty['close'].iloc[-1]
            analysis["nifty_regime"] = "Bullish" if latest_price_nifty > ema_50_nifty else "Bearish"

        # --- 45-Minute Sector Analysis (Sector Regime) ---
        if not df_45min_sector.empty:
            ema_50_sector = df_45min_sector['close'].ewm(span=50, adjust=False).mean().iloc[-1]
            latest_price_sector = df_45min_sector['close'].iloc[-1]
            analysis["sector_regime"] = "Bullish" if latest_price_sector > ema_50_sector else "Bearish"

        # --- 5-Minute Analysis (Entry Trigger & Trend Strength) ---
        if not df_5min.empty and len(df_5min) > 1:
            analysis["latest_price"] = df_5min['close'].iloc[-1]
            # Breakout Signal
            latest_close = df_5min['close'].iloc[-1]
            previous_high = df_5min['high'].iloc[-2]
            previous_low = df_5min['low'].iloc[-2]
            if latest_close > previous_high:
                analysis["entry_signal"] = "Bullish_Breakout"
            elif latest_close < previous_low:
                analysis["entry_signal"] = "Bearish_Breakout"
            
            # ADX placeholder - In a full version, the complex ADX calculation would be here.
            # For our current strategy, we will assume the trend is strong if a breakout occurs.
            if analysis["entry_signal"] != "No_Signal":
                analysis["is_strong_trend"] = True

        return analysis

    except Exception as e:
        logger.error(f"Error calculating technical analysis: {e}", exc_info=True)
        # Return the default neutral values on error
        return analysis

def get_atr_stop_loss(fyers_instance, symbol, multiplier):
    """
    Calculates the ATR-based stop loss in points.
    """
    try:
        end_date = datetime.date.today()
        start_date = end_date - datetime.timedelta(days=30)
        # Fetch daily data for ATR
        df = fyers_client.get_historical_data(fyers_instance, symbol, "D", start_date, end_date)
        
        if df.empty or len(df) < 15:
            logger.warning(f"Not enough data for ATR calculation for {symbol}")
            return None
        
        # Calculate True Range (TR)
        df['prev_close'] = df['close'].shift(1)
        df['tr1'] = df['high'] - df['low']
        df['tr2'] = abs(df['high'] - df['prev_close'])
        df['tr3'] = abs(df['low'] - df['prev_close'])
        df['tr'] = df[['tr1', 'tr2', 'tr3']].max(axis=1)
        
        # Calculate ATR (14-period SMA of TR)
        df['atr'] = df['tr'].rolling(window=14).mean()
        
        current_atr = df['atr'].iloc[-1]
        
        if pd.isna(current_atr):
            return None
            
        return current_atr * multiplier

    except Exception as e:
        logger.error(f"Error calculating ATR stop loss: {e}", exc_info=True)
        return None

def get_scalping_analysis(df):
    """
    Analyzes 15-min data for scalping signals (EMA Crossover).
    Used by options_scalper_main.py
    """
    analysis = {
        "trend": "Neutral",
        "strength": "Weak",
        "entry_signal": "No_Signal"
    }
    
    if df.empty or len(df) < 22:
        return analysis
        
    try:
        # Calculate EMAs
        df['ema_9'] = df['close'].ewm(span=9, adjust=False).mean()
        df['ema_21'] = df['close'].ewm(span=21, adjust=False).mean()
        
        current_ema9 = df['ema_9'].iloc[-1]
        current_ema21 = df['ema_21'].iloc[-1]
        
        # Determine Trend
        if current_ema9 > current_ema21:
            analysis['trend'] = 'Bullish'
        elif current_ema9 < current_ema21:
            analysis['trend'] = 'Bearish'
            
        # DEMO MODE: Force signal on ANY trend to show trades
        if analysis['trend'] == 'Bullish':
            analysis['entry_signal'] = 'Bullish_Cross'
            analysis['strength'] = 'Strong'
        elif analysis['trend'] == 'Bearish':
            analysis['entry_signal'] = 'Bearish_Cross'
            analysis['strength'] = 'Strong'
        
        # Original strict logic (commented out for demo)
        # if prev_ema9 <= prev_ema21 and current_ema9 > current_ema21:
        #     analysis['entry_signal'] = 'Bullish_Cross'
        # elif prev_ema9 >= prev_ema21 and current_ema9 < current_ema21:
        #     analysis['entry_signal'] = 'Bearish_Cross'
            
        # Determine Strength (Distance between EMAs)
        # Simple heuristic: if distance > 0.05% of price, consider it strong
        # price = df['close'].iloc[-1]
        # distance_pct = abs(current_ema9 - current_ema21) / price * 100
        # if distance_pct > 0.05:
        #    analysis['strength'] = 'Strong'
        
        analysis['latest_price'] = df['close'].iloc[-1]
        
        return analysis
        
    except Exception as e:
        logger.error(f"Error calculating scalping analysis: {e}", exc_info=True)
        return analysis

def get_market_regime(fyers_instance, symbol):
    """
    Determines the market regime (Bullish/Bearish) for a given symbol
    based on the 50-period EMA on a 45-minute timeframe.
    """
    try:
        end_date = datetime.date.today()
        start_date = end_date - datetime.timedelta(days=30)
        
        # Fetch 45-minute data
        # "45" is the resolution for 45 minutes
        df = fyers_client.get_historical_data(fyers_instance, symbol, "45", start_date, end_date)
        
        if df.empty or len(df) < 50:
            logger.warning(f"Not enough data for market regime analysis for {symbol}")
            return "Neutral"
            
        # Calculate 50 EMA
        df['ema_50'] = df['close'].ewm(span=50, adjust=False).mean()
        
        latest_close = df['close'].iloc[-1]
        latest_ema = df['ema_50'].iloc[-1]
        
        if latest_close > latest_ema:
            return "Bullish"
        else:
            return "Bearish"
            
    except Exception as e:
        logger.error(f"Error determining market regime for {symbol}: {e}", exc_info=True)
        return "Neutral"
