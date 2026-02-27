# symbol_recon.py

import fyers_client
import logger_setup
import logging

# Initialize the logger
logger = logger_setup.setup_logger()

def find_valid_option_symbols():
    """
    Performs a live search using the Fyers API to discover the correct
    naming convention for NIFTY weekly options.
    """
    logger.info("--- Symbol Reconnaissance Mission Initialized ---")
    
    # Authenticate with Fyers
    fyers_model = fyers_client.get_fyers_model()
    if not fyers_model:
        logger.critical("Authentication failed. Halting mission.")
        return

    logger.info("Authentication successful. Searching for valid symbols...")

    try:
        # --- NEW: FULL SYSTEM INTERROGATION ---
        logger.info("--- Performing full inspection of FyersModel object ---")
        # Print ALL available functions to find the correct one
        all_functions = [func for func in dir(fyers_model) if not func.startswith('_')]
        logger.info("All available functions in FyersModel:")
        for func_name in all_functions:
            logger.info(f"  - {func_name}")
        logger.info("----------------------------------------------------")
        logger.info("Please review the list above to identify the correct function for searching symbols.")
        # --------------------------------------------------

    except Exception as e:
        logger.error(f"An error occurred during symbol reconnaissance: {e}", exc_info=True)

    logger.info("\n--- Reconnaissance Complete ---")


if __name__ == '__main__':
    find_valid_option_symbols()
