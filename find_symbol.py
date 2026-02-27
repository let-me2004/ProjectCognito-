import pandas as pd
import requests

url = "https://public.fyers.in/sym_details/NSE_FO.csv"
print(f"Downloading {url}...")
# It has no headers by default, columns: 
# FyersToken, SymbolDetails, Instrument, LotSize, TickSize, ISIN, TradingSession, LastUpdateDate, ExpiryDate
df = pd.read_csv(url, header=None)

# Let's inspect rows containing BANKNIFTY and 61000 and PE
matching = df[df[1].str.contains("BANKNIFTY") & df[1].str.contains("61000") & df[1].str.contains("PE")]

print(f"Found {len(matching)} matching symbols.")
for idx, row in matching.iterrows():
    print(row[1], row[8]) # Symbol and Expiry
