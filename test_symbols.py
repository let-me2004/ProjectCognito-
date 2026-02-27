import json
import fyers_client

fyers = fyers_client.get_fyers_model()
with open("paper_positions_scalper.json", "r") as f:
    positions = json.load(f)

for sym, pos in positions.items():
    print(f"Testing buy leg: {sym}")
    try:
        quote = fyers.quotes({"symbols": sym})
        print(f"Result: {quote}")
    except Exception as e:
        print(f"Exception: {e}")
        
    sell_sym = pos.get("sell_symbol")
    if sell_sym:
        print(f"Testing sell leg: {sell_sym}")
        try:
            quote = fyers.quotes({"symbols": sell_sym})
            print(f"Result: {quote}")
        except Exception as e:
            print(f"Exception: {e}")
