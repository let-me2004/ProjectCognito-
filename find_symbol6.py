import pandas as pd
import requests

url = "https://public.fyers.in/sym_details/NSE_FO.csv"
df = pd.read_csv(url, header=None)

m = df[df[1].str.contains("BANKNIFTY", na=False) & df[1].str.contains("PE", na=False)]
m = m.sort_values(by=8)

print("Earliest BankNifty Expiries:")
for _, row in m.head(20).iterrows():
    print(f"Col 1 (Symbol): {row[1]}, Col 8 (Epoch): {row[8]}, Col 9 (ExpiryStr): {row[9]}, Col 12 (Desc): {row[12]}")
