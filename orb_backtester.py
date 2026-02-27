# orb_backtester.py - Backtester for the Opening Range Breakout Strategy
# ======================================================================
# Uses 5 years of NIFTY 5-min data to simulate the ORB strategy.
# Outputs: Win Rate, Total P&L, Avg Win/Loss, Max Drawdown, and a CSV trade log.

import pandas as pd
import numpy as np
import logging
import os
from orb_strategy import get_orb_signal

# --- Setup Logger ---
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# --- Backtest Configuration ---
DATA_FILE = "nifty_5min_raw_data_5_years.csv"
INITIAL_CAPITAL = 200000.0   # ₹2,00,000
LOT_SIZE = 75                # NIFTY lot size
LOTS_PER_TRADE = 1           # Trade 1 lot at a time
OUTPUT_CSV = "orb_backtest_results.csv"

# UTC offset: IST = UTC + 5:30
# Market open  09:15 IST = 03:45 UTC
# EOD exit     15:00 IST = 09:30 UTC
EOD_EXIT_HOUR_UTC = 9
EOD_EXIT_MINUTE_UTC = 30


def load_data():
    """Load and prepare the NIFTY 5-min CSV data."""
    logger.info(f"Loading data from {DATA_FILE}...")
    df = pd.read_csv(DATA_FILE, parse_dates=['timestamp'], index_col='timestamp')
    df.index = pd.to_datetime(df.index)
    logger.info(f"Loaded {len(df)} candles from {df.index[0]} to {df.index[-1]}")
    return df


def simulate_trade_on_candles(signal, day_candles_after_entry):
    """
    Simulate the trade bar-by-bar after entry to determine the exit.
    
    Returns:
        dict with exit details: exit_price, exit_reason, exit_time, pnl_points
    """
    entry_price = signal['entry_price']
    stop_loss = signal['stop_loss']
    take_profit = signal['take_profit']
    is_long = signal['signal'] == 'BUY_CE'

    for idx in range(len(day_candles_after_entry)):
        candle = day_candles_after_entry.iloc[idx]
        candle_time = day_candles_after_entry.index[idx]

        # Check EOD exit (15:00 IST = 09:30 UTC)
        if candle_time.hour >= EOD_EXIT_HOUR_UTC and candle_time.minute >= EOD_EXIT_MINUTE_UTC:
            exit_price = candle['close']
            if is_long:
                pnl = exit_price - entry_price
            else:
                pnl = entry_price - exit_price
            return {
                'exit_price': exit_price,
                'exit_reason': 'EOD_EXIT',
                'exit_time': candle_time,
                'pnl_points': pnl
            }

        if is_long:
            # Check Stop Loss (price went below SL)
            if candle['low'] <= stop_loss:
                pnl = stop_loss - entry_price  # Negative
                return {
                    'exit_price': stop_loss,
                    'exit_reason': 'STOP_LOSS',
                    'exit_time': candle_time,
                    'pnl_points': pnl
                }
            # Check Take Profit (price went above TP)
            if candle['high'] >= take_profit:
                pnl = take_profit - entry_price  # Positive
                return {
                    'exit_price': take_profit,
                    'exit_reason': 'TAKE_PROFIT',
                    'exit_time': candle_time,
                    'pnl_points': pnl
                }
        else:  # Short (BUY_PE)
            # Check Stop Loss (price went above SL)
            if candle['high'] >= stop_loss:
                pnl = entry_price - stop_loss  # Negative
                return {
                    'exit_price': stop_loss,
                    'exit_reason': 'STOP_LOSS',
                    'exit_time': candle_time,
                    'pnl_points': pnl
                }
            # Check Take Profit (price went below TP)
            if candle['low'] <= take_profit:
                pnl = entry_price - take_profit  # Positive
                return {
                    'exit_price': take_profit,
                    'exit_reason': 'TAKE_PROFIT',
                    'exit_time': candle_time,
                    'pnl_points': pnl
                }

    # If we reach here, the day ended without a clear exit (shouldn't happen with EOD)
    last_candle = day_candles_after_entry.iloc[-1]
    exit_price = last_candle['close']
    if is_long:
        pnl = exit_price - entry_price
    else:
        pnl = entry_price - exit_price
    return {
        'exit_price': exit_price,
        'exit_reason': 'DAY_END',
        'exit_time': day_candles_after_entry.index[-1],
        'pnl_points': pnl
    }


def run_backtest():
    """Main backtest loop."""
    df = load_data()
    
    # Group candles by trading day
    df['date'] = df.index.date
    trading_days = df.groupby('date')
    
    # --- Trade Log ---
    trades = []
    capital = INITIAL_CAPITAL
    peak_capital = INITIAL_CAPITAL
    max_drawdown = 0
    qty = LOT_SIZE * LOTS_PER_TRADE

    total_days = len(trading_days)
    logger.info(f"Total trading days found: {total_days}")
    logger.info(f"Starting backtest with ₹{INITIAL_CAPITAL:,.2f} capital, {LOTS_PER_TRADE} lot(s) ({qty} qty)...")
    logger.info("=" * 70)

    for day_date, day_df in trading_days:
        # Get ORB signal for this day
        signal = get_orb_signal(day_df)
        
        if signal is None:
            continue  # No valid signal today

        # Find candles AFTER the entry candle
        entry_time = signal['entry_time']
        candles_after_entry = day_df[day_df.index > entry_time]
        
        if candles_after_entry.empty:
            continue  # No candles after entry (shouldn't happen)

        # Simulate the trade
        result = simulate_trade_on_candles(signal, candles_after_entry)
        
        # Calculate P&L in rupees
        pnl_rupees = result['pnl_points'] * qty
        capital += pnl_rupees

        # Track drawdown
        if capital > peak_capital:
            peak_capital = capital
        drawdown = peak_capital - capital
        if drawdown > max_drawdown:
            max_drawdown = drawdown

        # Log the trade
        trade_record = {
            'date': day_date,
            'signal': signal['signal'],
            'entry_time': signal['entry_time'],
            'entry_price': signal['entry_price'],
            'orb_high': signal['orb_high'],
            'orb_low': signal['orb_low'],
            'orb_range': signal['orb_range'],
            'stop_loss': signal['stop_loss'],
            'take_profit': signal['take_profit'],
            'exit_time': result['exit_time'],
            'exit_price': result['exit_price'],
            'exit_reason': result['exit_reason'],
            'pnl_points': round(result['pnl_points'], 2),
            'pnl_rupees': round(pnl_rupees, 2),
            'capital': round(capital, 2)
        }
        trades.append(trade_record)

    # --- Results Analysis ---
    logger.info("=" * 70)
    logger.info("           BACKTEST RESULTS — ORB Strategy (NIFTY)")
    logger.info("=" * 70)

    if not trades:
        logger.info("No trades were executed.")
        return

    trades_df = pd.DataFrame(trades)
    
    total_trades = len(trades_df)
    wins = trades_df[trades_df['pnl_points'] > 0]
    losses = trades_df[trades_df['pnl_points'] <= 0]
    win_count = len(wins)
    loss_count = len(losses)
    win_rate = (win_count / total_trades) * 100 if total_trades > 0 else 0
    
    total_pnl = trades_df['pnl_rupees'].sum()
    avg_win = wins['pnl_rupees'].mean() if not wins.empty else 0
    avg_loss = losses['pnl_rupees'].mean() if not losses.empty else 0
    
    # Profit Factor
    gross_profit = wins['pnl_rupees'].sum() if not wins.empty else 0
    gross_loss = abs(losses['pnl_rupees'].sum()) if not losses.empty else 1
    profit_factor = gross_profit / gross_loss if gross_loss > 0 else float('inf')
    
    # Exit Reason Breakdown
    exit_reasons = trades_df['exit_reason'].value_counts()
    
    # Signal Breakdown
    signal_counts = trades_df['signal'].value_counts()

    # --- Print Results ---
    logger.info(f"  Test Period:       {trades_df['date'].iloc[0]} to {trades_df['date'].iloc[-1]}")
    logger.info(f"  Total Trading Days: {total_days}")
    logger.info(f"  Days with Trades:  {total_trades}")
    logger.info("-" * 70)
    logger.info(f"  Initial Capital:   ₹{INITIAL_CAPITAL:>12,.2f}")
    logger.info(f"  Final Capital:     ₹{capital:>12,.2f}")
    logger.info(f"  Total P&L:         ₹{total_pnl:>12,.2f}")
    logger.info(f"  Return:            {((capital - INITIAL_CAPITAL) / INITIAL_CAPITAL * 100):>11.2f}%")
    logger.info(f"  Max Drawdown:      ₹{max_drawdown:>12,.2f}")
    logger.info("-" * 70)
    logger.info(f"  Total Trades:      {total_trades}")
    logger.info(f"  Profitable Trades: {win_count}")
    logger.info(f"  Losing Trades:     {loss_count}")
    logger.info(f"  Win Rate:          {win_rate:.2f}%")
    logger.info("-" * 70)
    logger.info(f"  Avg Win:           ₹{avg_win:>12,.2f}")
    logger.info(f"  Avg Loss:          ₹{avg_loss:>12,.2f}")
    logger.info(f"  Profit Factor:     {profit_factor:.2f}")
    logger.info("-" * 70)
    logger.info("  Exit Reasons:")
    for reason, count in exit_reasons.items():
        logger.info(f"    {reason}: {count}")
    logger.info("  Signal Breakdown:")
    for sig, count in signal_counts.items():
        logger.info(f"    {sig}: {count}")
    logger.info("=" * 70)

    # --- Save to CSV ---
    trades_df.to_csv(OUTPUT_CSV, index=False)
    logger.info(f"  Trade log saved to: {OUTPUT_CSV}")
    logger.info("=" * 70)

    # --- Monthly P&L Breakdown ---
    trades_df['month'] = pd.to_datetime(trades_df['date']).dt.to_period('M')
    monthly_pnl = trades_df.groupby('month')['pnl_rupees'].sum()
    
    logger.info("  MONTHLY P&L BREAKDOWN:")
    logger.info("-" * 40)
    for month, pnl in monthly_pnl.items():
        marker = "✓" if pnl > 0 else "✗"
        logger.info(f"    {month}:  ₹{pnl:>10,.2f}  {marker}")
    
    profitable_months = (monthly_pnl > 0).sum()
    total_months = len(monthly_pnl)
    logger.info("-" * 40)
    logger.info(f"  Profitable Months: {profitable_months}/{total_months} ({profitable_months/total_months*100:.1f}%)")
    logger.info("=" * 70)


if __name__ == "__main__":
    run_backtest()
