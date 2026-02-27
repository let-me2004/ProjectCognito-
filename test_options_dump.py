import json
import fyers_client

fyers = fyers_client.get_fyers_model()

syms = [
    "NSE:NIFTY26FEB25400PE", 
    "NSE:BANKNIFTY26FEB61100PE",
    "NSE:BANKNIFTY2622661100PE", 
    "NSE:BANKNIFTY2622561100PE", 
    "NSE:BANKNIFTY26FEB2661100PE"
]
out = {}
for s in syms:
    quote = fyers.quotes({"symbols": s})
    out[s] = quote

with open("quote_results.json", "w") as f:
    json.dump(out, f, indent=4)
