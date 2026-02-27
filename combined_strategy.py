# combined_strategy.py - ORB + EMA Crossover Multi-Strategy
# ==========================================================
# Phase 1 (09:15-09:45): Opening Range Breakout — 1 high-conviction trade
# Phase 2 (09:45-15:00): EMA 5/13 Crossover Scalper — multiple trades
# This combines the best of both strategies.

import pandas as pd
import numpy as np
import logging

logger = logging.getLogger(__name__)

# --- ORB Parameters (Phase 1) ---
ORB_CANDLES = 3           # First 15 min (3 x 5-min candles)
ORB_SL_BUFFER = 5         # Extra SL buffer in points
ORB_RR_RATIO = 1.5        # Risk:Reward for ORB
ORB_MAX_RANGE_PCT = 1.0   # Skip if range > 1% of price
ORB_MIN_RANGE = 20        # Min range in points

# --- EMA Scalper Parameters (Phase 2) ---
EMA_FAST = 5
EMA_SLOW = 13
RSI_PERIOD = 7
RSI_OB = 75
RSI_OS = 25
SCALP_SL = 12
SCALP_TP = 18
SCALP_COOLDOWN = 2


def compute_rsi(series, period=7):
    delta = series.diff()
    gain = delta.where(delta > 0, 0.0)
    loss = -delta.where(delta < 0, 0.0)
    avg_gain = gain.rolling(window=period, min_periods=period).mean()
    avg_loss = loss.rolling(window=period, min_periods=period).mean()
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))


def get_orb_signal(day_candles):
    """Phase 1: Get the ORB signal from first 15 min."""
    if len(day_candles) < ORB_CANDLES + 1:
        return None

    orb = day_candles.iloc[:ORB_CANDLES]
    orb_high = orb['high'].max()
    orb_low = orb['low'].min()
    orb_range = orb_high - orb_low
    mid = (orb_high + orb_low) / 2

    if (orb_range / mid) * 100 > ORB_MAX_RANGE_PCT:
        return None
    if orb_range < ORB_MIN_RANGE:
        return None

    # Check candles after ORB for breakout
    post_orb = day_candles.iloc[ORB_CANDLES:]
    for idx in range(len(post_orb)):
        candle = post_orb.iloc[idx]
        t = post_orb.index[idx]

        if candle['close'] > orb_high:
            entry = candle['close']
            sl = orb_low - ORB_SL_BUFFER
            risk = entry - sl
            tp = entry + (risk * ORB_RR_RATIO)
            return {
                'signal': 'BUY_CE', 'entry_price': entry,
                'stop_loss': sl, 'take_profit': tp,
                'entry_time': t, 'risk_points': risk,
                'source': 'ORB', 'orb_high': orb_high, 'orb_low': orb_low
            }
        elif candle['close'] < orb_low:
            entry = candle['close']
            sl = orb_high + ORB_SL_BUFFER
            risk = sl - entry
            tp = entry - (risk * ORB_RR_RATIO)
            return {
                'signal': 'BUY_PE', 'entry_price': entry,
                'stop_loss': sl, 'take_profit': tp,
                'entry_time': t, 'risk_points': risk,
                'source': 'ORB', 'orb_high': orb_high, 'orb_low': orb_low
            }
    return None


def get_ema_signals(day_candles, start_after_idx=0):
    """Phase 2: EMA Crossover + RSI signals after ORB period."""
    if len(day_candles) < EMA_SLOW + 5:
        return []

    df = day_candles.copy()
    df['ema_fast'] = df['close'].ewm(span=EMA_FAST, adjust=False).mean()
    df['ema_slow'] = df['close'].ewm(span=EMA_SLOW, adjust=False).mean()
    df['rsi'] = compute_rsi(df['close'], RSI_PERIOD)
    df['prev_ema_fast'] = df['ema_fast'].shift(1)
    df['prev_ema_slow'] = df['ema_slow'].shift(1)
    df['prev_rsi'] = df['rsi'].shift(1)
    df['prev_close'] = df['close'].shift(1)
    df['prev_low'] = df['low'].shift(1)
    df['prev_high'] = df['high'].shift(1)

    signals = []
    cooldown_until = 0
    start = max(start_after_idx, EMA_SLOW + 2)

    for i in range(start, len(df)):
        if i < cooldown_until:
            continue

        row = df.iloc[i]
        t = df.index[i]
        if pd.isna(row['rsi']) or pd.isna(row['prev_rsi']):
            continue

        signal = None

        # EMA Crossover
        bull_cross = (row['prev_ema_fast'] <= row['prev_ema_slow'] and
                     row['ema_fast'] > row['ema_slow'])
        bear_cross = (row['prev_ema_fast'] >= row['prev_ema_slow'] and
                     row['ema_fast'] < row['ema_slow'])

        if bull_cross and row['rsi'] > 55 and row['rsi'] < RSI_OB:
            signal = 'BUY_CE'
        elif bear_cross and row['rsi'] < 45 and row['rsi'] > RSI_OS:
            signal = 'BUY_PE'

        # RSI Reversal
        if signal is None:
            if row['prev_rsi'] < RSI_OS and row['rsi'] >= RSI_OS:
                if row['ema_fast'] > row['ema_slow']:
                    signal = 'BUY_CE'
            elif row['prev_rsi'] > RSI_OB and row['rsi'] <= RSI_OB:
                if row['ema_fast'] < row['ema_slow']:
                    signal = 'BUY_PE'

        # EMA Bounce
        if signal is None:
            if row['ema_fast'] > row['ema_slow']:
                if row['prev_low'] <= row['prev_ema_fast'] and row['close'] > row['ema_fast']:
                    if 40 < row['rsi'] < RSI_OB:
                        signal = 'BUY_CE'
            elif row['ema_fast'] < row['ema_slow']:
                if row['prev_high'] >= row['prev_ema_fast'] and row['close'] < row['ema_fast']:
                    if RSI_OS < row['rsi'] < 60:
                        signal = 'BUY_PE'

        if signal:
            entry = row['close']
            if signal == 'BUY_CE':
                sl = entry - SCALP_SL
                tp = entry + SCALP_TP
            else:
                sl = entry + SCALP_SL
                tp = entry - SCALP_TP

            signals.append({
                'signal': signal, 'entry_price': entry,
                'stop_loss': sl, 'take_profit': tp,
                'entry_time': t, 'risk_points': SCALP_SL,
                'source': 'EMA_SCALP'
            })
            cooldown_until = i + SCALP_COOLDOWN

    return signals


def get_all_signals_for_day(day_candles):
    """
    Combined signal generator:
    1. Try ORB first (Phase 1)
    2. Then run EMA scalper (Phase 2) after ORB period
    """
    all_signals = []

    # Phase 1: ORB
    orb_signal = get_orb_signal(day_candles)
    if orb_signal:
        all_signals.append(orb_signal)

    # Phase 2: EMA scalper (start after ORB candles)
    ema_start = ORB_CANDLES + 1
    ema_signals = get_ema_signals(day_candles, start_after_idx=ema_start)
    all_signals.extend(ema_signals)

    return all_signals
