# hft_equity_main.py - FINAL DEFINITIVE VERSION

import fyers_client
import logger_setup
import logging
from orderflow_analyzer import OrderFlowAnalyzer
from paper_trader import PaperAccount
import config
import time

logger = logger_setup.setup_logger()

# --- Global State ---
analyzers = {}
paper_account = None
last_log_time = {}

def on_tick_handler(tick_data):
    """
    The master tick handler. Receives data for ALL subscribed stocks
    and routes it to the correct analyzer.
    """
    global analyzers, paper_account, last_log_time
    try:
        # The new library provides a list of ticks
        for tick in tick_data:
            symbol = tick.get('symbol')
            if symbol in analyzers:
                analyzer = analyzers[symbol]
                analyzer.process_tick(tick) # Pass the individual tick
                
                # --- Heartbeat Logic ---
                current_time = time.time()
                if current_time - last_log_time.get(symbol, 0) > 5:
                    logger.info(f"[{symbol}] Heartbeat: Imbalance = {analyzer.last_imbalance_ratio:.2f}%")
                    last_log_time[symbol] = current_time

                signal = analyzer.get_signal()
                ltp = tick.get('ltp', 0)

                # --- Trade & Exit Logic ---
                position_exists = symbol in paper_account.positions

                if signal != "NEUTRAL" and not position_exists:
                    logger.info(f"[{symbol}] ACTIONABLE SIGNAL: {signal} | Imbalance: {analyzer.last_imbalance_ratio:.2f}%")
                    trade_qty = 1
                    if signal == "BUY":
                        paper_account.execute_buy(symbol, trade_qty, ltp, 0, 0)
                    elif signal == "SELL":
                        logger.warning(f"[{symbol}] Simulating SHORT SELL.")

                elif signal == "NEUTRAL" and position_exists:
                    logger.info(f"[{symbol}] NEUTRAL SIGNAL: Exiting position.")
                    position_data = paper_account.positions[symbol]
                    paper_account.execute_sell(symbol, position_data['qty'], ltp)
                    paper_account.get_summary()
    except Exception as e:
        logger.error(f"An error occurred in on_tick_handler: {e}", exc_info=True)


if __name__ == '__main__':
    logger.info("====== Multi-Target Order Flow Agent Initializing (v2 Library) ======")
    
    fyers_model = fyers_client.get_fyers_model(
        client_id=config.HFT_FYERS_APP_ID,
        secret_key=config.HFT_FYERS_SECRET_KEY
    )
    
    if fyers_model:
        import liquidity_scanner
        top_targets = liquidity_scanner.find_top_liquid_stocks(fyers_model, top_n=5)

        if top_targets:
            logger.info(f"--- Top targets for today: {top_targets} ---")
            
            paper_account = PaperAccount(initial_balance=config.ACCOUNT_BALANCE)
            for symbol in top_targets:
                analyzers[symbol] = OrderFlowAnalyzer(symbol, imbalance_threshold=30.0)
                last_log_time[symbol] = 0

            try:
                # Call the new, superior WebSocket function
                fyers_client.start_level2_websocket(
                    access_token=fyers_model.token,
                    on_tick=on_tick_handler,
                    symbols=top_targets
                )
            except KeyboardInterrupt:
                logger.info(">>> Shutdown signal received. <<<")

        else:
            logger.warning("Liquidity scan found no suitable targets. Shutting down.")
    else:
        logger.critical("Could not authenticate with Fyers. Halting agent.")

    logger.info("====== Multi-Target Order Flow Agent Shut Down ======")