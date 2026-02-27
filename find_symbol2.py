import pandas as pd
import requests

url = "https://public.fyers.in/sym_details/NSE_FO.csv"
print(f"Downloading {url}...")
df = pd.read_csv(url, header=None)

# 12 is ExpiryDesc like 'BANKNIFTY 26 Feb 26'
# wait, symbol name is in column 1.
# Usually 'BANKNIFTY26FEB'
matching = df[df[1].str.contains(r"^NSE:BANKNIFTY26FEB", regex=True) & df[1].str.contains("PE")]
print(f"Found {len(matching)} BankNifty PEs for 26th Feb.")

print(matching[1].values)

