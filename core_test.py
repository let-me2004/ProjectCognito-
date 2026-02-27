# core_test.py

import time
import logging
from fyers_websockets.FyersSocket import FyersSocket
import config # We need this to get the keys

# --- Basic Logger Setup ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# --- Manual Configuration ---
# NOTE: You must have a fresh, valid access token for this test.
# Run 'python fyers_client.py' once to generate a new 'access_token_hft.txt' if needed.
# --------------------------

ACCESS_TOKEN = ""
CLIENT_ID = config.HFT_FYERS_APP_ID
SYMBOLS = ["NSE:SBIN-EQ"]

# --- Handler Functions ---
def on_message(message):
    logging.info(f"MESSAGE RECEIVED: {message}")

def on_error(message):
    logging.error(f"ERROR: {message}")

def on_close(message):
    logging.warning(f"CONNECTION CLOSED: {message}")

def on_open():
    logging.info("Connection opened. Subscribing to symbols...")
    fyers_socket.subscribe(symbol=SYMBOLS, data_type="SymbolUpdate")

# --- Main Test ---
if __name__ == "__main__":
    logging.info("--- Core WebSocket Test Initialized ---")
    
    # Read the dedicated HFT access token
    try:
        with open("access_token_hft.txt", 'r') as f:
            ACCESS_TOKEN = f.read().strip()
        if not ACCESS_TOKEN:
            raise FileNotFoundError
    except FileNotFoundError:
        logging.critical("FATAL: 'access_token_hft.txt' not found or is empty. Please run fyers_client.py to generate it first.")
        exit()

    # The token for this library needs to be in the format "APP_ID:ACCESS_TOKEN"
    token = f"{CLIENT_ID}:{ACCESS_TOKEN}"

    # Initialize the socket
    fyers_socket = FyersSocket(access_token=token, log_path="")

    # Assign handlers
    fyers_socket.on_message = on_message
    fyers_socket.on_error = on_error
    fyers_socket.on_close = on_close
    fyers_socket.on_open = on_open

    # This is a blocking call that runs the connection
    try:
        logging.info("Connecting to WebSocket...")
        fyers_socket.keep_running()
    except KeyboardInterrupt:
        logging.info("Manual shutdown.")
    except Exception as e:
        logging.error(f"An unexpected error occurred: {e}", exc_info=True)

    logging.info("--- Core WebSocket Test Complete ---")