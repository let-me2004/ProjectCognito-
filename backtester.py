import logger_setup
# --- Logger MUST be initialized FIRST ---
# This prevents other modules (like pandas_ta) from
# initializing the default logger before we do.
logger = logger_setup.setup_logger()

import fyers_client
import logging
import datetime
import pandas as pd
from paper_trader import PaperAccount
import consolidation_hunter_strategy as strategy
import config
import risk_manager

# --- Backtest Configuration ---
SYMBOL = "NSE:RELIANCE-EQ" # <--- PIVOT TO EQUITY
TIMEFRAME = "5" # 5-minute candles
DAYS_TO_TEST = 60 # Test on the last 60 days
RISK_PERCENTAGE = 5.0 # 5% of account per trade
# ---------------------------------------------------------

def run_backtest():
    logger.info(f"--- Starting Backtest for '{strategy.__name__}' ---")
    logger.info(f"Symbol: {SYMBOL} | Timeframe: {TIMEFRAME}min | Test Period: {DAYS_TO_TEST} days | Risk: {RISK_PERCENTAGE}%")
    
    fyers = fyers_client.get_fyers_model()
    if not fyers:
        logger.critical("Fyers authentication failed. Cannot download data.")
        return

    # 1. Initialize Account
    paper_account = PaperAccount(initial_balance=config.ACCOUNT_BALANCE)
    
    # 2. Download Historical Data
    end_date = datetime.date.today()
    start_date = end_date - datetime.timedelta(days=DAYS_TO_TEST + 30) # Get extra days for warmup
    
    logger.info(f"Downloading historical data from {start_date} to {end_date}...")
    full_df = fyers_client.get_historical_data(fyers, SYMBOL, TIMEFRAME, start_date, end_date)
    
    if full_df.empty:
        logger.error("Failed to download data. Aborting backtest.")
        return
        
    logger.info(f"Data downloaded. Total candles: {len(full_df)}")
    
    # 3. The "Time Machine" Loop
    warmup_period = 50 # Let indicators stabilize
    
    logger.info(f"Starting simulation loop (this may take a moment)...")
    for i in range(warmup_period, len(full_df)):
        current_df_slice = full_df.iloc[0:i].copy() 
        current_candle = current_df_slice.iloc[-1]
        current_high = current_candle['high']
        current_low = current_candle['low']
        
        # A. Check for exits
        open_positions = list(paper_account.positions.keys())
        for symbol in open_positions:
            # Use the equity exit logic
            paper_account.check_positions_for_exit(symbol, current_high, current_low)

        # B. Check for entries (only if flat)
        if not paper_account.positions:
            signal = strategy.check_for_signal(current_df_slice)
            
            if signal:
                logger.info(f"--- SIGNAL FOUND at {current_candle.name} ---")
                logger.info(f"   Type: {signal['signal']} | Reason: {signal['reason']}")
                
                # C. Calculate Risk using the EQUITY risk manager
                trade_details = risk_manager.calculate_equity_trade(
                    account_balance=paper_account.balance,
                    risk_percentage=RISK_PERCENTAGE,
                    entry_price=signal['entry_price'],
                    stop_loss_price=signal['stop_loss']
                )
                
                if trade_details['is_trade_valid']:
                    logger.info(f"   Risk Manager Approved: {trade_details['position_size']} Shares")
                    
                    # D. Execute Equity Trade
                    # We pass prices twice, as P&L and Triggers are the same for equities
                    if signal['signal'] == "BUY":
                        paper_account.execute_buy(
                            symbol=f"{SYMBOL}_LONG",
                            quantity=trade_details['position_size'],
                            sim_entry_price=signal['entry_price'],
                            sim_stop_loss_price=signal['stop_loss'],
                            sim_take_profit_price=signal['take_profit'],
                            index_entry_price=signal['entry_price'], # Triggers are same as P&L
                            index_stop_loss_price=signal['stop_loss'],
                            index_take_profit_price=signal['take_profit']
                        )
                    elif signal['signal'] == "SELL":
                         paper_account.execute_sell(
                            symbol=f"{SYMBOL}_SHORT",
                            quantity=trade_details['position_size'],
                            sim_entry_price=signal['entry_price'],
                            sim_stop_loss_price=signal['stop_loss'], # For a short, SL is high
                            sim_take_profit_price=signal['take_profit'], # TP is low
                            index_entry_price=signal['entry_price'],
                            index_stop_loss_price=signal['stop_loss'],
                            index_take_profit_price=signal['take_profit']
                        )
                else:
                    logger.warning(f"   Risk Manager REJECTED: {trade_details['reason']}")

    # 4. Final Summary
    logger.info("--- Backtest Complete ---")
    paper_account.get_summary()

if __name__ == "__main__":
    run_backtest()


