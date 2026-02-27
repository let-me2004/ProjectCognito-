import json
import fyers_client

fyers = fyers_client.get_fyers_model()

sym1 = "NSE:BANKNIFTY26FEB61100PE"
sym2 = "NSE:BANKNIFTY26FEB61000PE"

for s in [sym1, sym2]:
    print(f"Testing {s}:")
    quote = fyers.quotes({"symbols": s})
    print(quote)
