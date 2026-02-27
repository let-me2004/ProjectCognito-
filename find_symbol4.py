import pandas as pd
import requests

url = "https://public.fyers.in/sym_details/NSE_FO.csv"
print(f"Downloading {url}...")
df = pd.read_csv(url, header=None)

# 12 is ExpiryDesc like 'BANKNIFTY 26 Feb 26'
# Let's find all recent BankNifty PE symbols
matching = df[df[1].str.startswith("BANKNIFTY", na=False) & df[1].str.contains("PE", na=False)]
# Sort by expiry date (Epoch is column 8)
matching = matching.sort_values(by=8)

# Print the first 20 unique prefixes (first 14 chars like 'BANKNIFTY26FEB')
prefixes = matching[1].apply(str).values
seen = set()
for p in prefixes:
    prefix = p[:15]
    if prefix not in seen:
        print(f"Sample symbol: {p}")
        seen.add(prefix)
        if len(seen) > 10:
            break
