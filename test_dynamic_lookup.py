import logging
import sys

logging.basicConfig(level=logging.DEBUG, stream=sys.stdout, format='%(levelname)s: %(message)s')

import fyers_client

print("Initializing Fyers...")
fyers = fyers_client.get_fyers_model()

print("\nTesting NIFTY CE offset 0:")
opt = fyers_client.find_option_by_offset(fyers, "NIFTY", "CE", 0)
print(opt)
