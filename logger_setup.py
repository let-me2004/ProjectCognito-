import logging
import sys

def setup_logger():
    """
    Sets up a simple, robust logger that prints INFO and above to the console.
    """
    # Get the root logger
    logger = logging.getLogger()
    
    # Prevent duplicate handlers if this is called multiple times
    if logger.hasHandlers():
        for handler in logger.handlers[:]:
            logger.removeHandler(handler)

    logger.setLevel(logging.INFO) # Set the minimum level for the logger

    # --- Console Handler ---
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO) # Minimum level for console
    
    # --- Formatter ---
    formatter = logging.Formatter(
        '%(asctime)s - %(levelname)s - [%(name)s] - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    console_handler.setFormatter(formatter)
    
    # Add the handler to the logger
    logger.addHandler(console_handler)
    
    return logger
