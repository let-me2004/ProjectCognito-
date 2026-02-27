import pandas as pd
url = "https://public.fyers.in/sym_details/NSE_FO.csv"
df = pd.read_csv(url, header=None)

# Find NIFTY weeklies
n_m = df[df[9].str.startswith("NSE:NIFTY", na=False) & df[9].str.endswith("PE", na=False)]
print("NIFTY Unique 15-char Prefixes:")
print(n_m[9].str[:15].unique())

