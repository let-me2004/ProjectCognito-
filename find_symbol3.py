import pandas as pd
import requests

url = "https://public.fyers.in/sym_details/NSE_FO.csv"
print(f"Downloading {url}...")
df = pd.read_csv(url, header=None)

# Let's find all recent BankNifty PE symbols
matching = df[df[1].str.contains(r"^NSE:BANKNIFTY", regex=True) & df[1].str.contains("PE")]
# Sort by expiry date (Epoch is column 8)
matching = matching.sort_values(by=8)

# Print the first 20 unique prefixes (first 14 chars like 'NSE:BANKNIFTY26')
prefixes = matching[1].apply(lambda x: pd.Series([x, x[:18]])).values
seen = set()
for prefix in prefixes:
    if prefix[1] not in seen:
        print(f"Sample symbol: {prefix[0]}")
        seen.add(prefix[1])
        if len(seen) > 10:
            break
