import fyers_client
import config

print("Authenticating with Fyers...")
fyers = fyers_client.get_fyers_model()

if fyers:
    print("Authentication successful! Firing live test spread order...")
    # Using real symbols from today's session
    buy_sym = "NSE:NIFTY26FEB25400PE"
    sell_sym = "NSE:NIFTY26FEB25350PE"
    qty = 65 # Updated NIFTY size
    
    # Send a regular single-leg market order for 1 lot (Buying a PE)
    # This will immediately trigger the broker's margin block check.
    response = fyers_client.place_market_order(
        fyers_instance=fyers, 
        symbol=buy_sym, 
        qty=qty, 
        side=1  # 1 = Buy
    )
    
    print("\n--- BROKER RESPONSE ---")
    print(response)
else:
    print("Failed to authenticate.")
