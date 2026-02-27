import pandas as pd
url = "https://public.fyers.in/sym_details/NSE_FO.csv"
df = pd.read_csv(url, header=None)

m = df[df[9].str.startswith("NSE:BANKNIFTY", na=False) & df[9].str.endswith("PE", na=False)]
m = m[~m[9].str.contains("MAR|APR|MAY|JUN|JUL|AUG|SEP|OCT|NOV|DEC", regex=True)]

print(f"Found {len(m)} weekly BankNifty options.")
print(m[9].head())
