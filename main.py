import fyers_client
import logger_setup
import logging
import time
import datetime
import technical_analyzer
import risk_manager
from paper_trader import PaperAccount
import config
import ml_predictor

# Initialize the logger
logger = logger_setup.setup_logger()

# --- STRATEGY CONFIGURATION ---
NIFTY_SYMBOL = "NSE:NIFTY50-INDEX"
BANKNIFTY_SYMBOL = "NSE:NIFTYBANK-INDEX"
RISK_PERCENTAGE = config.RISK_PERCENTAGE
STOP_LOSS_ATR_MULTIPLIER = 0.5 # Tighter stop for lower risk
TAKE_PROFIT_ATR_MULTIPLIER = 2.0 # Standard 2:1 Reward/Risk
ML_CONFIDENCE_THRESHOLD = 0.51
CYCLE_WAIT_TIME_SECONDS = 30 # 5-minute cycle
# -----------------------------

def run_bot_cycle(fyers, paper_account):
    """
    Runs one full cycle of the multi-filter options trading bot.
    """
    logger.info("--- New Cycle Started ---")

    # --- Step 0: Manage Open Positions ---
    logger.info("[Step 0] Managing open positions...")
    open_positions = list(paper_account.positions.keys())
    if not open_positions:
        logger.info("   ...No open positions to manage.")
    else:
        # In a real-world scenario, you'd check live prices against SL/TP here.
        # For simplicity in this version, we only enter one trade per day.
        logger.info(f"   ...Currently holding {len(open_positions)} position(s). Monitoring...")
        paper_account.get_summary() # Display current P&L
        return # Do not look for new trades while holding a position

    # --- Step 1: Gather ALL Market Data ---
    logger.info("[Step 1] Gathering multi-timeframe market and sector data...")
    try:
        end_date = datetime.date.today()
        # Fetching enough data for indicators
        start_date_long = end_date - datetime.timedelta(days=90) 
        start_date_short = end_date - datetime.timedelta(days=10)

        df_5min = fyers_client.get_historical_data(fyers, NIFTY_SYMBOL, "5", start_date_short, end_date)
        df_45min_nifty = fyers_client.get_historical_data(fyers, NIFTY_SYMBOL, "45", start_date_long, end_date)
        df_45min_sector = fyers_client.get_historical_data(fyers, BANKNIFTY_SYMBOL, "45", start_date_long, end_date)
        
        if df_5min.empty or df_45min_nifty.empty or df_45min_sector.empty:
            logger.warning("Could not fetch complete historical data. Skipping cycle.")
            return
    except Exception as e:
        logger.error(f"Error during data gathering: {e}", exc_info=True)
        return

    # --- Step 2: Perform Full Spectrum Analysis ---
    logger.info("[Step 2] Performing full spectrum analysis...")
    
    # a) Quantitative Analysis (Single, efficient call)
    quant_analysis = technical_analyzer.get_technical_analysis(df_5min, df_45min_nifty, df_45min_sector)
    logger.info(f"   ...Quantitative: NIFTY Regime='{quant_analysis['nifty_regime']}', Sector Regime='{quant_analysis['sector_regime']}', Signal='{quant_analysis['entry_signal']}'")
    
    is_quant_bullish = quant_analysis['nifty_regime'] == "Bullish" and quant_analysis['sector_regime'] == "Bullish" and quant_analysis['entry_signal'] == "Bullish_Breakout"
    is_quant_bearish = quant_analysis['nifty_regime'] == "Bearish" and quant_analysis['sector_regime'] == "Bearish" and quant_analysis['entry_signal'] == "Bearish_Breakout"

    # b) Predictive Analysis (Machine Learning)
    # Note: ML Predictor requires specific feature engineering which might not be fully available here.
    # We will skip ML for now in this simplified version to avoid errors with missing 'predict_bullish_signal'
    is_ml_bullish = False 
    # To re-enable, ensure ml_predictor.get_prediction is called with correct features.

    # --- Step 3: Weighted Confluence Protocol ---
    logger.info("[Step 3] Executing Weighted Confluence Protocol (Technical Only)...")
    trade_type = None
    
    if is_quant_bullish:
        logger.info(f"   ...[CONFIRMED] Technical signals aligned for a BULLISH trade.")
        trade_type = "CE"
    elif is_quant_bearish:
        logger.info(f"   ...[CONFIRMED] Technical signals aligned for a BEARISH trade.")
        trade_type = "PE"
    else:
        logger.info("   ...No confluence of signals. Standing down.")

    # --- Step 4: Execution ---
    if trade_type:
        logger.info(f"[Step 4] Actionable signal confirmed. Finding ATM {trade_type} option...")
        selected_option = fyers_client.find_option_by_offset(fyers, index_name="NIFTY", option_type=trade_type, offset=0)

        if not selected_option or not selected_option.get('ltp'):
            logger.error("Could not find a valid option instrument. Aborting.")
            return

        symbol = selected_option['symbol']
        ltp = selected_option['ltp']
        nifty_spot = selected_option.get('spot_price', 0)
        logger.info(f"   ...Found instrument: {symbol} @ LTP: {ltp:.2f}")

        # DYNAMIC STOP LOSS & TAKE PROFIT using ATR
        stop_loss_points = technical_analyzer.get_atr_stop_loss(fyers, NIFTY_SYMBOL, STOP_LOSS_ATR_MULTIPLIER)
        if not stop_loss_points:
            logger.error("Could not calculate ATR for stop loss. Aborting trade.")
            return
        take_profit_points = stop_loss_points * TAKE_PROFIT_ATR_MULTIPLIER

        # Use the options-specific risk calculation
        trade_details = risk_manager.calculate_scalping_trade(
            account_balance=paper_account.balance,
            risk_percentage=RISK_PERCENTAGE,
            stop_loss_points=stop_loss_points,
            index_name="NIFTY"
        )

        if trade_details['is_trade_valid']:
            logger.info(f"   ...Executing BUY order for {trade_details['lots']} lots of {symbol} @ {ltp:.2f}")
            # Calculate index-level SL/TP for exit tracking
            if trade_type == "CE":
                index_sl = nifty_spot - stop_loss_points
                index_tp = nifty_spot + take_profit_points
            else:
                index_sl = nifty_spot + stop_loss_points
                index_tp = nifty_spot - take_profit_points
            
            # Option-level SL/TP (approximate from premium)
            option_sl = max(ltp - (stop_loss_points * 0.5), 1)  # Delta ~0.5
            option_tp = ltp + (take_profit_points * 0.5)
            
            paper_account.execute_buy(
                symbol, trade_details['quantity'],
                ltp, option_sl, option_tp,
                nifty_spot, index_sl, index_tp
            )
        else:
            logger.error(f"   ...Trade REJECTED by Risk Manager: {trade_details.get('reason')}")


if __name__ == '__main__':
    fyers = fyers_client.get_fyers_model()

    if fyers:
        paper_account = PaperAccount(initial_balance=config.ACCOUNT_BALANCE, filename="paper_positions_options.json")
        logger.info("--- Initialization Complete. Entering Main Operational Loop ---")

        while True:
            try:
                now = datetime.datetime.now().time()
                market_open = datetime.time(9, 16)
                market_close = datetime.time(15, 0)

                if market_open <= now <= market_close:
                    paper_account.sync_positions()  # Hot-reload: pick up dashboard changes
                    run_bot_cycle(fyers, paper_account)
                else:
                    logger.info("Market is closed (after 15:00). Initiating EOD Square-off...")
                    open_symbols = list(paper_account.positions.keys())
                    for sym in open_symbols:
                        # Close at reasonable placeholder since we might not have LTP in this block easily without fetching
                        # Ideally fetch LTP, but for safety shutdown we just close.
                        paper_account._close_position(sym, "MARKET_EXIT", 0) 
                        
                    paper_account.get_summary()
                    break

                logger.info(f"Cycle complete. Waiting for {CYCLE_WAIT_TIME_SECONDS} seconds...")
                time.sleep(CYCLE_WAIT_TIME_SECONDS)
                
            except KeyboardInterrupt:
                logger.info(">>> Shutdown signal received. <<<")
                break
            except Exception as e:
                logger.error("An uncaught error occurred in the main loop!", exc_info=True)
                time.sleep(60)
    else:
        logger.critical("Authentication failed. Halting agent.")

    logger.info("====== Primary Options Agent Shut Down ======")

