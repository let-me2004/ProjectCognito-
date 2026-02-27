import json
import fyers_client

fyers = fyers_client.get_fyers_model()

syms = []
for strike in range(60500, 61600, 100):
   syms.append(f"NSE:BANKNIFTY26FEB{strike}PE")

results = []
for s in syms:
    quote = fyers.quotes({"symbols": s})
    if quote.get('s') == 'ok' and quote.get('d') and quote['d'][0].get('v', {}).get('lp', 0) > 0:
        results.append(f"VALID: {s}")
    else:
        results.append(f"INVALID: {s}")
        
for r in results:
   print(r)
