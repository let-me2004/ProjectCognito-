import pandas as pd
import requests

url = "https://public.fyers.in/sym_details/NSE_FO.csv"
print(f"Downloading {url}...")
df = pd.read_csv(url, header=None)

# Find any row with BANKNIFTY and PE
matching = df[df[1].str.contains("BANKNIFTY", na=False) & df[1].str.contains("26", na=False) & df[1].str.contains("PE", na=False)]
print(f"Found {len(matching)} matches.")
print(matching.head())
