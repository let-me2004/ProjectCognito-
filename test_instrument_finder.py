# test_instrument_finder.py

import fyers_client
import logger_setup
import logging

# Initialize the logger
logger = logger_setup.setup_logger()

def validate_instrument_finder():
    """
    Performs a live test of the option instrument finding logic to diagnose
    potential issues with symbol construction or data availability.
    """
    logger.info("--- Instrument Finder Diagnostic Initialized ---")
    
    # Authenticate with Fyers
    fyers_model = fyers_client.get_fyers_model()
    if not fyers_model:
        logger.critical("Authentication failed. Halting diagnostic.")
        return

    logger.info("Authentication successful. Proceeding with live test...")

    # --- Test Case 1: Find the At-the-Money CALL Option ---
    logger.info("\n--- Attempting to find ATM CALL (CE) option ---")
    atm_call_option = fyers_client.find_nifty_option_by_offset(fyers_model, option_type="CE", offset=0)
    
    if atm_call_option:
        logger.info(">>> SUCCESS: Found a valid, tradeable CALL option.")
        logger.info(f"    Symbol: {atm_call_option['symbol']}")
        logger.info(f"    LTP: {atm_call_option['ltp']}")
        logger.info(f"    Bid: {atm_call_option['bid']}")
        logger.info(f"    Ask: {atm_call_option['ask']}")
    else:
        logger.error(">>> FAILURE: Could not find a valid, tradeable CALL option.")


    # --- Test Case 2: Find the At-the-Money PUT Option ---
    logger.info("\n--- Attempting to find ATM PUT (PE) option ---")
    atm_put_option = fyers_client.find_nifty_option_by_offset(fyers_model, option_type="PE", offset=0)

    if atm_put_option:
        logger.info(">>> SUCCESS: Found a valid, tradeable PUT option.")
        logger.info(f"    Symbol: {atm_put_option['symbol']}")
        logger.info(f"    LTP: {atm_put_option['ltp']}")
        logger.info(f"    Bid: {atm_put_option['bid']}")
        logger.info(f"    Ask: {atm_put_option['ask']}")
    else:
        logger.error(">>> FAILURE: Could not find a valid, tradeable PUT option.")

    logger.info("\n--- Diagnostic Complete ---")


if __name__ == '__main__':
    validate_instrument_finder()
