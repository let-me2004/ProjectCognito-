# combined_backtester.py - Backtester for ORB + EMA Combined Strategy
# ====================================================================

import pandas as pd
import numpy as np
import logging
from combined_strategy import get_all_signals_for_day

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

DATA_FILE = "nifty_5min_raw_data_5_years.csv"
INITIAL_CAPITAL = 200000.0
LOT_SIZE = 75
LOTS_PER_TRADE = 4
OUTPUT_CSV = "combined_backtest_results.csv"
DAILY_LOSS_LIMIT = -5000  # Stop trading after Rs 5000 daily loss

EOD_HOUR_UTC = 9
EOD_MIN_UTC = 30


def simulate_trade(signal, candles_after_entry):
    entry = signal['entry_price']
    sl = signal['stop_loss']
    tp = signal['take_profit']
    is_long = signal['signal'] == 'BUY_CE'

    for i in range(len(candles_after_entry)):
        c = candles_after_entry.iloc[i]
        t = candles_after_entry.index[i]

        if t.hour >= EOD_HOUR_UTC and t.minute >= EOD_MIN_UTC:
            pnl = (c['close'] - entry) if is_long else (entry - c['close'])
            return {'exit_price': c['close'], 'exit_reason': 'EOD', 'exit_time': t, 'pnl': pnl}

        if is_long:
            if c['low'] <= sl:
                return {'exit_price': sl, 'exit_reason': 'SL', 'exit_time': t, 'pnl': sl - entry}
            if c['high'] >= tp:
                return {'exit_price': tp, 'exit_reason': 'TP', 'exit_time': t, 'pnl': tp - entry}
        else:
            if c['high'] >= sl:
                return {'exit_price': sl, 'exit_reason': 'SL', 'exit_time': t, 'pnl': entry - sl}
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
        signals = get_all_signals_for_day(day_df)
        day_trades = 0
        day_pnl = 0.0

        for sig in signals:
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
                'source': sig.get('source', 'UNKNOWN'),
                'signal': sig['signal'],
                'entry_time': sig['entry_time'],
                'entry_price': sig['entry_price'],
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

    # --- Results ---
    logger.info("=" * 70)
    logger.info("  COMBINED ORB + EMA SCALPER — NIFTY 5-min (4 Lots)")
    logger.info("=" * 70)

    if not trades:
        logger.info("No trades.")
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
    dp = tdf.groupby('date')['pnl_rupees'].sum()

    logger.info(f"  Period:            {tdf['date'].iloc[0]} to {tdf['date'].iloc[-1]}")
    logger.info(f"  Initial Capital:   Rs {INITIAL_CAPITAL:>12,.2f}")
    logger.info(f"  Final Capital:     Rs {capital:>12,.2f}")
    logger.info(f"  Total P&L:         Rs {pnl_total:>12,.2f}")
    logger.info(f"  Return:            {((capital - INITIAL_CAPITAL) / INITIAL_CAPITAL * 100):>11.2f}%")
    logger.info(f"  Max Drawdown:      Rs {max_dd:>12,.2f}")
    logger.info("-" * 70)
    logger.info(f"  Total Trades:      {total}")
    logger.info(f"  Win Rate:          {wr:.2f}%")
    logger.info(f"  Profit Factor:     {pf:.2f}")
    logger.info(f"  Avg Trades/Day:    {np.mean(daily_trade_counts):.1f}")
    logger.info(f"  Profitable Days:   {(dp > 0).sum()}/{len(dp)} ({(dp > 0).sum()/len(dp)*100:.1f}%)")
    logger.info(f"  Avg P&L/Day:       Rs {dp.mean():>10,.2f}")
    logger.info("-" * 70)
    logger.info("  By Source:")
    for src in ['ORB', 'EMA_SCALP']:
        s = tdf[tdf['source'] == src]
        if not s.empty:
            sw = s[s['pnl_points'] > 0]
            logger.info(f"    {src}: {len(s)} trades | WR {len(sw)/len(s)*100:.1f}% | PnL Rs {s['pnl_rupees'].sum():,.0f}")
    logger.info("-" * 70)
    logger.info("  YEARLY:")
    tdf['year'] = pd.to_datetime(tdf['date']).dt.year
    for year, pnl in tdf.groupby('year')['pnl_rupees'].sum().items():
        m = "+" if pnl > 0 else ""
        logger.info(f"    {year}: Rs {m}{pnl:>10,.0f}")
    logger.info("=" * 70)

    tdf.to_csv(OUTPUT_CSV, index=False)
    logger.info(f"  Trade log: {OUTPUT_CSV}")


if __name__ == "__main__":
    run_backtest()
