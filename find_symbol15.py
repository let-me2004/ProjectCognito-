import pandas as pd
url = "https://public.fyers.in/sym_details/NSE_FO.csv"
df = pd.read_csv(url, header=None)

m = df[df[9].str.startswith("NSE:NIFTY", na=False) & df[9].str.endswith("PE", na=False)]
m = m[~m[9].str.contains("MAR|APR|MAY|JUN|JUL|AUG|SEP|OCT|NOV|DEC", regex=True)]

# Sort by expiry epoch
m = m.sort_values(by=8)
for _, row in m.head(20).iterrows():
    print(f"Format: {row[9]}, ExpiryDate: {row[12]}")
