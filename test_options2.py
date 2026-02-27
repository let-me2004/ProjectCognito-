import json
import fyers_client

fyers = fyers_client.get_fyers_model()

syms = [
    "NSE:NIFTY26FEB25400PE", "NSE:NIFTY26FEB25350PE", "NSE:BANKNIFTY26FEB61100PE",
    "NSE:BANKNIFTY2622661100PE", "NSE:BANKNIFTY2622561100PE", "NSE:BANKNIFTY26FEB2661100PE"
]
for s in syms:
    quote = fyers.quotes({"symbols": s})
    print(f"{s} -> {quote}")
