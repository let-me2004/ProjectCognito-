import pandas as pd
import re

url = "https://public.fyers.in/sym_details/NSE_FO.csv"
df = pd.read_csv(url, header=None)

m = df[df[9].str.contains("NSE:BANKNIFTY", na=False) & df[9].str.contains("PE", na=False)]

# Extract everything up to the strike price digits
# Something like NSE:BANKNIFTY.....61000PE -> extract the prefix before digits
prefixes = m[9].astype(str).str.extract(r'(NSE:BANKNIFTY[A-Z0-9]+?)(\d{4,}PE)')[0].unique()
print("BankNifty Unique Expiry Prefixes in Master:")
for p in prefixes:
    print(p)
