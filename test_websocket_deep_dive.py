# test_websocket_deep_dive.py

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

def on_tick(message):
    logger.info(f"[ON_MESSAGE]: Tick Received: {message}")

def on_error(message):
    logger.error(f"[ON_ERROR]: WebSocket reported an error: {message}")

def on_close(message):
    logger.warning(f"[ON_CLOSE]: WebSocket connection closed: {message}")

def on_open():
    """
    This function is called when the connection is established.
    We will subscribe to our test symbol here.
    """
    logger.info("[ON_OPEN]: Connection established. Subscribing to symbol...")
    data_type = "SymbolData"
    fyers_socket.subscribe(symbols=[SYMBOL_TO_TEST], data_type=data_type)
    logger.info(f"Subscription request sent for {SYMBOL_TO_TEST}.")


if __name__ == '__main__':
    logger.info("====== WebSocket Deep Dive Diagnostic Initialized ======")
    
    # Get a valid access token first
    # We will use the DEDICATED HFT keys for this test
    fyers_model = fyers_client.get_fyers_model(
        client_id=config.HFT_FYERS_APP_ID,
        secret_key=config.HFT_FYERS_SECRET_KEY
    )
    
    if not fyers_model:
        logger.critical("Could not get access token. Halting.")
    else:
        access_token = fyers_model.token
        client_id = config.HFT_FYERS_APP_ID
        socket_access_token = f"{client_id}:{access_token}"

        # Import the WebSocket class directly
        from fyers_apiv3.FyersWebsocket.data_ws import FyersDataSocket

        # Initialize the WebSocket with our custom handlers
        fyers_socket = FyersDataSocket(
            access_token=socket_access_token,
            log_path=fyers_client.os.path.join(fyers_client.os.getcwd(), "logs"),
            litemode=False, # We want the full order book data
            write_to_file=False, # We will handle logging ourselves
            reconnect=True, # Enable auto-reconnect
            on_connect=on_open,
            on_close=on_close,
            on_error=on_error,
            on_message=on_tick
        )

        # Establish the connection. This runs in the background.
        fyers_socket.connect()

        # Keep the main script alive to listen for messages
        try:
            logger.info("Connection process initiated. Listening for events for 5 minutes... Press Ctrl+C to stop early.")
            time.sleep(300) # Keep the script running for 5 minutes
        except KeyboardInterrupt:
            logger.info("Manual shutdown initiated.")
        finally:
            logger.info("Closing connection...")
            fyers_socket.close_connection()
            logger.info("====== Diagnostic Complete ======")