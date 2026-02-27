import pandas as pd
url = "https://public.fyers.in/sym_details/NSE_FO.csv"
df = pd.read_csv(url, header=None)

# Let's find any BANKNIFTY symbol
m = df[df[9].str.startswith("NSE:BANKNIFTY", na=False) & df[9].str.endswith("PE", na=False)]
m = m.sort_values(by=8)

for _, row in m.head(30).iterrows():
    print(f"Format: {row[9]}, Expiry: {row[12]}")
