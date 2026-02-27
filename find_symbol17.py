import pandas as pd
import datetime

url = "https://public.fyers.in/sym_details/NSE_FO.csv"
df = pd.read_csv(url, header=None)

print("NIFTY Next Expiries:")
m = df[df[9].str.startswith("NSE:NIFTY", na=False) & df[9].str.endswith("PE", na=False)]
m = m.sort_values(by=8)
seen = set()
for _, row in m.apply(lambda r: [r[9], r[8]], axis=1).head(100).items():
    epoch = row[1]
    dt = datetime.datetime.fromtimestamp(epoch)
    if dt.date() not in seen:
        print(f"Date: {dt.date()} ({dt.strftime('%A')}) | Symbol: {row[0]}")
        seen.add(dt.date())

print("\nBANKNIFTY Next Expiries:")
m = df[df[9].str.startswith("NSE:BANKNIFTY", na=False) & df[9].str.endswith("PE", na=False)]
m = m.sort_values(by=8)
seen = set()
for _, row in m.apply(lambda r: [r[9], r[8]], axis=1).head(100).items():
    epoch = row[1]
    dt = datetime.datetime.fromtimestamp(epoch)
    if dt.date() not in seen:
        print(f"Date: {dt.date()} ({dt.strftime('%A')}) | Symbol: {row[0]}")
        seen.add(dt.date())

