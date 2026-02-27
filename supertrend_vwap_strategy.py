# supertrend_vwap_strategy.py - SuperTrend + VWAP Scalper for NIFTY Options
# =========================================================================
# V2: Fixed overly strict filters. Uses SuperTrend as primary signal,
# VWAP as confirmation, and ADX as optional strength filter.

import pandas as pd
import numpy as np
import logging

logger = logging.getLogger(__name__)

# --- Strategy Parameters ---
ST_PERIOD = 10
ST_MULTIPLIER = 2.0
ADX_PERIOD = 14
ADX_THRESHOLD = 18      # Lowered from 20
STOP_LOSS_POINTS = 15
TAKE_PROFIT_POINTS = 20
COOLDOWN_BARS = 2
TRAILING_SL_POINTS = 10


def compute_supertrend(df, period=10, multiplier=2.0):
    """Calculate SuperTrend indicator."""
    hl2 = (df['high'] + df['low']) / 2
    
    tr = pd.DataFrame(index=df.index)
    tr['hl'] = df['high'] - df['low']
    tr['hc'] = abs(df['high'] - df['close'].shift(1))
    tr['lc'] = abs(df['low'] - df['close'].shift(1))
    tr['tr'] = tr[['hl', 'hc', 'lc']].max(axis=1)
    atr = tr['tr'].rolling(window=period, min_periods=1).mean()
    
    basic_upper = hl2 + (multiplier * atr)
    basic_lower = hl2 - (multiplier * atr)
    
    n = len(df)
    final_upper = np.full(n, np.nan)
    final_lower = np.full(n, np.nan)
    supertrend = np.full(n, np.nan)
    direction = np.ones(n)
    
    final_upper[0] = basic_upper.iloc[0]
    final_lower[0] = basic_lower.iloc[0]
    supertrend[0] = basic_upper.iloc[0]
    direction[0] = -1
    
    close_vals = df['close'].values
    bu_vals = basic_upper.values
    bl_vals = basic_lower.values
    
    for i in range(1, n):
        # Upper band
        if bu_vals[i] < final_upper[i-1] or close_vals[i-1] > final_upper[i-1]:
            final_upper[i] = bu_vals[i]
        else:
            final_upper[i] = final_upper[i-1]
        
        # Lower band
        if bl_vals[i] > final_lower[i-1] or close_vals[i-1] < final_lower[i-1]:
            final_lower[i] = bl_vals[i]
        else:
            final_lower[i] = final_lower[i-1]
        
        # Direction & SuperTrend value
        if direction[i-1] == -1:  # Was bearish
            if close_vals[i] > final_upper[i]:
                direction[i] = 1
                supertrend[i] = final_lower[i]
            else:
                direction[i] = -1
                supertrend[i] = final_upper[i]
        else:  # Was bullish
            if close_vals[i] < final_lower[i]:
                direction[i] = -1
                supertrend[i] = final_upper[i]
            else:
                direction[i] = 1
                supertrend[i] = final_lower[i]
    
    return pd.Series(supertrend, index=df.index), pd.Series(direction, index=df.index)


def compute_vwap(df):
    """Calculate VWAP using range as volume proxy (since volume=0 in data)."""
    vol = (df['high'] - df['low']).replace(0, 0.01)
    typical_price = (df['high'] + df['low'] + df['close']) / 3
    cum_tp_vol = (typical_price * vol).cumsum()
    cum_vol = vol.cumsum()
    return cum_tp_vol / cum_vol


def compute_adx(df, period=14):
    """Calculate ADX."""
    high = df['high'].values
    low = df['low'].values
    close = df['close'].values
    n = len(df)
    
    plus_dm = np.zeros(n)
    minus_dm = np.zeros(n)
    tr_arr = np.zeros(n)
    
    for i in range(1, n):
        up = high[i] - high[i-1]
        down = low[i-1] - low[i]
        plus_dm[i] = up if (up > down and up > 0) else 0
        minus_dm[i] = down if (down > up and down > 0) else 0
        tr_arr[i] = max(high[i] - low[i], abs(high[i] - close[i-1]), abs(low[i] - close[i-1]))
    
    # Smoothed averages
    atr = pd.Series(tr_arr).rolling(window=period, min_periods=period).mean()
    sm_plus = pd.Series(plus_dm).rolling(window=period, min_periods=period).mean()
    sm_minus = pd.Series(minus_dm).rolling(window=period, min_periods=period).mean()
    
    plus_di = 100 * sm_plus / atr.replace(0, np.nan)
    minus_di = 100 * sm_minus / atr.replace(0, np.nan)
    
    di_sum = plus_di + minus_di
    dx = 100 * abs(plus_di - minus_di) / di_sum.replace(0, np.nan)
    adx = dx.rolling(window=period, min_periods=period).mean()
    
    return adx.values, plus_di.values, minus_di.values


def get_signals_for_day(day_candles):
    """
    Generate signals: SuperTrend flip is the PRIMARY signal.
    VWAP confirmation is optional (boosts confidence but not required).
    ADX filters out the flattest days.
    """
    if len(day_candles) < 30:
        return []

    df = day_candles.copy()
    
    df['supertrend'], df['st_direction'] = compute_supertrend(df, ST_PERIOD, ST_MULTIPLIER)
    df['vwap'] = compute_vwap(df)
    adx_vals, plus_di, minus_di = compute_adx(df, ADX_PERIOD)
    df['adx'] = adx_vals
    df['prev_st_dir'] = df['st_direction'].shift(1)
    
    signals = []
    cooldown_until = 0
    start_idx = 28  # Warmup

    for i in range(start_idx, len(df)):
        if i < cooldown_until:
            continue

        row = df.iloc[i]
        t = df.index[i]

        if pd.isna(row['adx']) or pd.isna(row['supertrend']):
            continue

        # ADX filter - skip very flat markets but be lenient
        if row['adx'] < ADX_THRESHOLD:
            continue

        signal = None

        # === PRIMARY: SuperTrend Direction Flip ===
        st_flip_up = (row['prev_st_dir'] == -1 and row['st_direction'] == 1)
        st_flip_down = (row['prev_st_dir'] == 1 and row['st_direction'] == -1)

        above_vwap = row['close'] > row['vwap']
        below_vwap = row['close'] < row['vwap']

        # BUY CE: SuperTrend flips bullish
        if st_flip_up:
            signal = 'BUY_CE'
        # BUY PE: SuperTrend flips bearish
        elif st_flip_down:
            signal = 'BUY_PE'

        # === SECONDARY: VWAP Bounce in existing SuperTrend ===
        if signal is None and row['st_direction'] == 1:  # Bullish ST
            prev = df.iloc[i-1]
            if not pd.isna(prev['vwap']) and prev['low'] <= prev['vwap'] * 1.002 and row['close'] > row['vwap']:
                if row['adx'] > 22:
                    signal = 'BUY_CE'
        
        if signal is None and row['st_direction'] == -1:  # Bearish ST
            prev = df.iloc[i-1]
            if not pd.isna(prev['vwap']) and prev['high'] >= prev['vwap'] * 0.998 and row['close'] < row['vwap']:
                if row['adx'] > 22:
                    signal = 'BUY_PE'

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
                'adx': round(row['adx'], 2) if not pd.isna(row['adx']) else 0,
                'vwap': round(row['vwap'], 2) if not pd.isna(row['vwap']) else 0,
                'supertrend': round(row['supertrend'], 2),
                'risk_points': STOP_LOSS_POINTS
            })
            cooldown_until = i + COOLDOWN_BARS

    return signals
