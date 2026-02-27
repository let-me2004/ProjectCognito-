import fyers_client
import sys

print("Initializing Fyers...")
fyers = fyers_client.get_fyers_model()

funds = fyers.funds()
print("Funds response:")
print(funds)
