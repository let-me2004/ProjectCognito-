import pandas as pd
import requests

url = "https://public.fyers.in/sym_details/NSE_FO.csv"
df = pd.read_csv(url, header=None)

# Find weekly option formats: e.g. NSE:BANKNIFTY263 (Year 26, Month 3 = March)
m = df[df[9].str.contains("NSE:BANKNIFTY263", na=False) & df[9].str.contains("PE", na=False)]
m = m.sort_values(by=8)

for _, row in m.head(5).iterrows():
    print(f"Weekly Fyers Format: {row[9]}, Expiry: {row[12]}")
