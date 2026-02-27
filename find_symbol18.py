import pandas as pd
import datetime

url = "https://public.fyers.in/sym_details/NSE_FO.csv"
df = pd.read_csv(url, header=None)

m = df[df[9].str.contains("NSE:NIFTY|NSE:BANKNIFTY", na=False)]
m = m[~m[9].str.contains('MAR|APR|MAY|JUN|JUL|AUG|SEP|OCT|NOV|DEC', regex=True)]
m = m.sort_values(by=8)

for _, row in m.head(50).iterrows():
    sym = row[9]
    epoch = row[8]
    # Fyers epoch might be in seconds.
    try:
        dt = datetime.datetime.fromtimestamp(epoch)
        print(f"Sym: {sym} -> {dt.strftime('%Y-%m-%d %A')} (Epoch: {epoch})")
    except Exception as e:
        pass
