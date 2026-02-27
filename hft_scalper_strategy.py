# hft_scalper_strategy.py - High-Frequency Scalper for NIFTY Options
# ==================================================================
# Generates 10-20+ trades per day using 5-min candles.
# Strategy V2: Multi-signal approach combining EMA Crossover, RSI Reversal,
# and Momentum Breakout for maximum trade frequency.

import pandas as pd
import numpy as np
import logging

logger = logging.getLogger(__name__)

# --- Strategy Parameters ---
EMA_FAST = 5
EMA_SLOW = 13
RSI_PERIOD = 7           # Faster RSI for more signals
RSI_OVERBOUGHT = 75      
RSI_OVERSOLD = 25        
RSI_ENTRY_BULL = 55      # Momentum confirmation for long
RSI_ENTRY_BEAR = 45      # Momentum confirmation for short
STOP_LOSS_POINTS = 12    # Tight SL
TAKE_PROFIT_POINTS = 18  # 1.5x SL
COOLDOWN_BARS = 1        # Minimal cooldown (5 min)


def compute_rsi(series, period=7):
    """Calculate RSI."""
    delta = series.diff()
    gain = delta.where(delta > 0, 0.0)
    loss = -delta.where(delta < 0, 0.0)
    avg_gain = gain.rolling(window=period, min_periods=period).mean()
    avg_loss = loss.rolling(window=period, min_periods=period).mean()
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))


def get_signals_for_day(day_candles):
    """
    Scans a full day's 5-min candles and returns ALL valid trade signals.
    Uses 3 signal types:
      1. EMA Crossover (primary)
      2. RSI Reversal (from extreme zones)
      3. EMA Momentum (price bounces off fast EMA in trend)
    """
    if len(day_candles) < EMA_SLOW + 5:
        return []

    df = day_candles.copy()
    
    # Calculate indicators
    df['ema_fast'] = df['close'].ewm(span=EMA_FAST, adjust=False).mean()
    df['ema_slow'] = df['close'].ewm(span=EMA_SLOW, adjust=False).mean()
    df['rsi'] = compute_rsi(df['close'], RSI_PERIOD)
    df['prev_rsi'] = df['rsi'].shift(1)
    df['prev_ema_fast'] = df['ema_fast'].shift(1)
    df['prev_ema_slow'] = df['ema_slow'].shift(1)
    df['prev_close'] = df['close'].shift(1)
    df['prev_low'] = df['low'].shift(1)
    df['prev_high'] = df['high'].shift(1)
    
    signals = []
    cooldown_until = 0
    start_idx = max(EMA_SLOW, RSI_PERIOD) + 2

    for i in range(start_idx, len(df)):
        if i < cooldown_until:
            continue

        row = df.iloc[i]
        t = df.index[i]

        if pd.isna(row['rsi']) or pd.isna(row['prev_rsi']):
            continue

        signal = None
        
        # === SIGNAL 1: EMA Crossover ===
        bull_cross = (row['prev_ema_fast'] <= row['prev_ema_slow'] and 
                     row['ema_fast'] > row['ema_slow'])
        bear_cross = (row['prev_ema_fast'] >= row['prev_ema_slow'] and 
                     row['ema_fast'] < row['ema_slow'])

        if bull_cross and row['rsi'] > RSI_ENTRY_BULL and row['rsi'] < RSI_OVERBOUGHT:
            signal = 'BUY_CE'
        elif bear_cross and row['rsi'] < RSI_ENTRY_BEAR and row['rsi'] > RSI_OVERSOLD:
            signal = 'BUY_PE'

        # === SIGNAL 2: RSI Reversal from Extremes ===
        if signal is None:
            # RSI crosses UP from oversold zone
            if row['prev_rsi'] < RSI_OVERSOLD and row['rsi'] >= RSI_OVERSOLD:
                if row['ema_fast'] > row['ema_slow']:  # Only with trend
                    signal = 'BUY_CE'
            # RSI crosses DOWN from overbought zone
            elif row['prev_rsi'] > RSI_OVERBOUGHT and row['rsi'] <= RSI_OVERBOUGHT:
                if row['ema_fast'] < row['ema_slow']:  # Only with trend
                    signal = 'BUY_PE'
        
        # === SIGNAL 3: EMA Bounce (Trend Continuation) ===
        if signal is None:
            # In uptrend, price pulls back to fast EMA and bounces
            if row['ema_fast'] > row['ema_slow']:
                if row['prev_low'] <= row['prev_ema_fast'] and row['close'] > row['ema_fast']:
                    if row['rsi'] > 40 and row['rsi'] < RSI_OVERBOUGHT:
                        signal = 'BUY_CE'
            # In downtrend, price rallies to fast EMA and drops
            elif row['ema_fast'] < row['ema_slow']:
                if row['prev_high'] >= row['prev_ema_fast'] and row['close'] < row['ema_fast']:
                    if row['rsi'] < 60 and row['rsi'] > RSI_OVERSOLD:
                        signal = 'BUY_PE'

        # --- Create signal ---
        if signal:
            entry = row['close']
            if signal == 'BUY_CE':
                sl = entry - STOP_LOSS_POINTS
                tp = entry + TAKE_PROFIT_POINTS
            else:
                sl = entry + STOP_LOSS_POINTS
                tp = entry - TAKE_PROFIT_POINTS

            signals.append({
                'signal': signal,
                'entry_price': entry,
                'stop_loss': sl,
                'take_profit': tp,
                'entry_time': t,
                'rsi': round(row['rsi'], 2),
                'ema_fast': round(row['ema_fast'], 2),
                'ema_slow': round(row['ema_slow'], 2),
                'risk_points': STOP_LOSS_POINTS
            })
            cooldown_until = i + COOLDOWN_BARS

    return signals
