# test_connection_stability.py

import fyers_client
import logger_setup
import logging
import time
import config

# Initialize our standard logger
logger = logger_setup.setup_logger()

# --- Configuration ---
SYMBOL_TO_TEST = "NSE:SBIN-EQ"
# -------------------

def on_tick_handler(tick_data):
    """A minimal handler to confirm data is flowing."""
    logger.info(f"DATA RECEIVED: {tick_data}")

if __name__ == '__main__':
    logger.info("====== Connection Stability Test Initializing ======")
    
    # --- We will use the DEDICATED HFT keys for this test ---
    fyers_model = fyers_client.get_fyers_model(
        client_id=config.HFT_FYERS_APP_ID,
        secret_key=config.HFT_FYERS_SECRET_KEY
    )
    
    if fyers_model:
        # We are only subscribing to ONE symbol to minimize variables
        target_symbol = [SYMBOL_TO_TEST]
        
        logger.info(f"Attempting to establish a persistent connection for {target_symbol}...")
        
        try:
            # This is a blocking call. If it works, it will run forever.
            fyers_client.start_level2_websocket(
                access_token=fyers_model.token,
                symbols=target_symbol,
                on_tick=on_tick_handler
            )
        except KeyboardInterrupt:
            logger.info(">>> Shutdown signal received. <<<")
        except Exception as e:
            logger.error(f"A critical error occurred: {e}", exc_info=True)

    else:
        logger.critical("Could not authenticate with Fyers. Halting test.")

    logger.info("====== Connection Stability Test Complete ======")