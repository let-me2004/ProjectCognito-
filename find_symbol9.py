import pandas as pd
import requests

url = "https://public.fyers.in/sym_details/NSE_FO.csv"
df = pd.read_csv(url, header=None)

# Let's find exactly the symbols that are Weekly expiries for BankNifty in early March!
m = df[df[9].str.contains("NSE:BANKNIFTY", na=False) & df[9].str.contains("PE", na=False)]

# Sort by Expiry Epoch
m = m.sort_values(by=8)

print("First 10 BankNifty expiries currently trading:")
for _, row in m.head(10).iterrows():
    print(f"Sym: {row[1]}, Fyers Format: {row[9]}, Expiry: {row[12]}")
