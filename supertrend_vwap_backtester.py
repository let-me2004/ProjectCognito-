# supertrend_vwap_backtester.py - Backtester for SuperTrend + VWAP Strategy
# =========================================================================

import pandas as pd
import numpy as np
import logging
from supertrend_vwap_strategy import get_signals_for_day, STOP_LOSS_POINTS, TAKE_PROFIT_POINTS, TRAILING_SL_POINTS

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

DATA_FILE = "nifty_5min_raw_data_5_years.csv"
INITIAL_CAPITAL = 200000.0
LOT_SIZE = 75
LOTS_PER_TRADE = 4
OUTPUT_CSV = "supertrend_vwap_results.csv"
DAILY_LOSS_LIMIT = -5000  # Stop trading if daily loss exceeds this

EOD_HOUR_UTC = 9
EOD_MIN_UTC = 30


def simulate_trade(signal, candles_after_entry):
    """Simulate with trailing stop loss."""
    entry = signal['entry_price']
    sl = signal['stop_loss']
    tp = signal['take_profit']
    is_long = signal['signal'] == 'BUY_CE'
    best_price = entry  # Track best price for trailing SL

    for i in range(len(candles_after_entry)):
        c = candles_after_entry.iloc[i]
        t = candles_after_entry.index[i]

        # EOD exit
        if t.hour >= EOD_HOUR_UTC and t.minute >= EOD_MIN_UTC:
            pnl = (c['close'] - entry) if is_long else (entry - c['close'])
            return {'exit_price': c['close'], 'exit_reason': 'EOD', 'exit_time': t, 'pnl': pnl}

        if is_long:
            # Update trailing stop
            if c['high'] > best_price:
                best_price = c['high']
                new_trail_sl = best_price - TRAILING_SL_POINTS
                if new_trail_sl > sl:
                    sl = new_trail_sl

            if c['low'] <= sl:
                pnl = sl - entry
                reason = 'TRAIL_SL' if sl > signal['stop_loss'] else 'SL'
                return {'exit_price': sl, 'exit_reason': reason, 'exit_time': t, 'pnl': pnl}
            if c['high'] >= tp:
                return {'exit_price': tp, 'exit_reason': 'TP', 'exit_time': t, 'pnl': tp - entry}
        else:
            if c['low'] < best_price:
                best_price = c['low']
                new_trail_sl = best_price + TRAILING_SL_POINTS
                if new_trail_sl < sl:
                    sl = new_trail_sl

            if c['high'] >= sl:
                pnl = entry - sl
                reason = 'TRAIL_SL' if sl < signal['stop_loss'] else 'SL'
                return {'exit_price': sl, 'exit_reason': reason, 'exit_time': t, 'pnl': pnl}
            if c['low'] <= tp:
                return {'exit_price': tp, 'exit_reason': 'TP', 'exit_time': t, 'pnl': entry - tp}

    last = candles_after_entry.iloc[-1]
    pnl = (last['close'] - entry) if is_long else (entry - last['close'])
    return {'exit_price': last['close'], 'exit_reason': 'DAY_END', 'exit_time': candles_after_entry.index[-1], 'pnl': pnl}


def run_backtest():
    logger.info(f"Loading data from {DATA_FILE}...")
    df = pd.read_csv(DATA_FILE, parse_dates=['timestamp'], index_col='timestamp')
    logger.info(f"Loaded {len(df)} candles ({df.index[0]} to {df.index[-1]})")

    df['date'] = df.index.date
    trading_days = df.groupby('date')

    trades = []
    capital = INITIAL_CAPITAL
    peak = INITIAL_CAPITAL
    max_dd = 0
    qty = LOT_SIZE * LOTS_PER_TRADE
    daily_trade_counts = []

    for day_date, day_df in trading_days:
        signals = get_signals_for_day(day_df)
        day_trades = 0
        day_pnl = 0.0

        for sig in signals:
            # Daily loss limit check
            if day_pnl <= DAILY_LOSS_LIMIT:
                break

            entry_time = sig['entry_time']
            after = day_df[day_df.index > entry_time]
            if after.empty:
                continue

            result = simulate_trade(sig, after)
            pnl_rs = result['pnl'] * qty
            capital += pnl_rs
            day_pnl += pnl_rs

            if capital > peak:
                peak = capital
            dd = peak - capital
            if dd > max_dd:
                max_dd = dd

            trades.append({
                'date': day_date,
                'signal': sig['signal'],
                'entry_time': sig['entry_time'],
                'entry_price': sig['entry_price'],
                'adx': sig['adx'],
                'vwap': sig['vwap'],
                'sl': sig['stop_loss'],
                'tp': sig['take_profit'],
                'exit_time': result['exit_time'],
                'exit_price': result['exit_price'],
                'exit_reason': result['exit_reason'],
                'pnl_points': round(result['pnl'], 2),
                'pnl_rupees': round(pnl_rs, 2),
                'capital': round(capital, 2)
            })
            day_trades += 1

        if day_trades > 0:
            daily_trade_counts.append(day_trades)

    # --- Print Results ---
    logger.info("=" * 70)
    logger.info("  SUPERTREND + VWAP + ADX BACKTEST — NIFTY 5-min (4 Lots)")
    logger.info("=" * 70)

    if not trades:
        logger.info("No trades executed.")
        return

    tdf = pd.DataFrame(trades)
    total = len(tdf)
    wins = tdf[tdf['pnl_points'] > 0]
    losses = tdf[tdf['pnl_points'] <= 0]
    wr = len(wins) / total * 100
    pnl_total = tdf['pnl_rupees'].sum()
    gp = wins['pnl_rupees'].sum() if not wins.empty else 0
    gl = abs(losses['pnl_rupees'].sum()) if not losses.empty else 1
    pf = gp / gl

    logger.info(f"  Period:            {tdf['date'].iloc[0]} to {tdf['date'].iloc[-1]}")
    logger.info(f"  Initial Capital:   Rs {INITIAL_CAPITAL:>12,.2f}")
    logger.info(f"  Final Capital:     Rs {capital:>12,.2f}")
    logger.info(f"  Total P&L:         Rs {pnl_total:>12,.2f}")
    logger.info(f"  Return:            {((capital - INITIAL_CAPITAL) / INITIAL_CAPITAL * 100):>11.2f}%")
    logger.info(f"  Max Drawdown:      Rs {max_dd:>12,.2f}")
    logger.info("-" * 70)
    logger.info(f"  Total Trades:      {total}")
    logger.info(f"  Profitable:        {len(wins)}")
    logger.info(f"  Losing:            {len(losses)}")
    logger.info(f"  Win Rate:          {wr:.2f}%")
    logger.info(f"  Profit Factor:     {pf:.2f}")
    logger.info("-" * 70)
    if not wins.empty:
        logger.info(f"  Avg Win:           Rs {wins['pnl_rupees'].mean():>10,.2f}")
    if not losses.empty:
        logger.info(f"  Avg Loss:          Rs {losses['pnl_rupees'].mean():>10,.2f}")
    logger.info("-" * 70)
    if daily_trade_counts:
        logger.info(f"  Avg Trades/Day:    {np.mean(daily_trade_counts):.1f}")
        logger.info(f"  Max Trades/Day:    {max(daily_trade_counts)}")
        logger.info(f"  Min Trades/Day:    {min(daily_trade_counts)}")
    logger.info("-" * 70)
    logger.info("  Exit Reasons:")
    for reason, count in tdf['exit_reason'].value_counts().items():
        logger.info(f"    {reason}: {count}")
    
    # Daily P&L stats
    dp = tdf.groupby('date')['pnl_rupees'].sum()
    logger.info("-" * 70)
    logger.info(f"  Profitable Days:   {(dp > 0).sum()} / {len(dp)} ({(dp > 0).sum() / len(dp) * 100:.1f}%)")
    logger.info(f"  Avg P&L/Day:       Rs {dp.mean():>10,.2f}")

    logger.info("-" * 70)
    logger.info("  YEARLY P&L:")
    tdf['year'] = pd.to_datetime(tdf['date']).dt.year
    for year, pnl in tdf.groupby('year')['pnl_rupees'].sum().items():
        marker = "+" if pnl > 0 else ""
        logger.info(f"    {year}:  Rs {marker}{pnl:>10,.2f}")
    logger.info("=" * 70)

    tdf.to_csv(OUTPUT_CSV, index=False)
    logger.info(f"  Trade log saved: {OUTPUT_CSV}")


if __name__ == "__main__":
    run_backtest()
