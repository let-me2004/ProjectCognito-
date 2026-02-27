import pandas as pd
import re

url = "https://public.fyers.in/sym_details/NSE_FO.csv"
df = pd.read_csv(url, header=None)

m = df[df[9].str.contains("NSE:BANKNIFTY", na=False) & df[9].str.contains("PE", na=False)]

prefixes = m[9].astype(str).str.extract(r'(NSE:BANKNIFTY.*?)(\d{5}PE)')[0].unique()
print("BankNifty Unique Expiry Prefixes in Master:")
for p in prefixes:
    print(p)
