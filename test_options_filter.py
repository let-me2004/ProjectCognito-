import json
import fyers_client
import sys

fyers = fyers_client.get_fyers_model()

syms = [
    "NSE:NIFTY26FEB25400PE", "NSE:NIFTY26FEB25350PE", "NSE:BANKNIFTY26FEB61100PE",
    "NSE:BANKNIFTY2622661100PE", "NSE:BANKNIFTY2622561100PE", "NSE:BANKNIFTY26FEB2661100PE"
]
for s in syms:
    quote = fyers.quotes({"symbols": s})
    if quote.get('s') == 'ok' and quote.get('d') and quote['d'][0].get('v', {}).get('lp', 0) > 0:
        print(f"VALID: {s}")
    else:
        print(f"INVALID: {s}")
