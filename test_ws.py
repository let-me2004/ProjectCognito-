import fyers_client
import time

fyers = fyers_client.get_fyers_model()

def on_tick(msg):
    print(f"WS TICK: {msg}")

symbols = ['NSE:NIFTY50-INDEX', 'NSE:NIFTYBANK-INDEX', 'NSE:BANKNIFTY26FEB61100PE', 'NSE:BANKNIFTY26FEB61000PE']
print(f"Subscribing to: {symbols}")

ws = fyers_client.start_level2_websocket(fyers.token, on_tick, symbols)

import threading
t = threading.Thread(target=ws.keep_running)
t.start()

time.sleep(10)
ws.close_connection()
print("Done.")
