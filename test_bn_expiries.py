import pandas as pd
import datetime

url = "https://public.fyers.in/sym_details/NSE_FO.csv"
df = pd.read_csv(url, header=None)

print("Checking BANKNIFTY expiries:")
mask = (df[13] == "BANKNIFTY") & (df[15] == 61200.0) & (df[16] == "CE")
m = df[mask].sort_values(by=8)

for _, row in m.head(5).iterrows():
    sym = row[9]
    epoch = row[8]
    dt = datetime.datetime.fromtimestamp(epoch)
    print(f"Symbol: {sym} -> Expiry: {dt.strftime('%Y-%m-%d %A')} (Epoch: {epoch})")

