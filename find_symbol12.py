import pandas as pd
url = "https://public.fyers.in/sym_details/NSE_FO.csv"
df = pd.read_csv(url, header=None)

m = df[df[9].str.startswith("NSE:BANKNIFTY", na=False) & df[9].str.endswith("PE", na=False)]

# Print unique first 16 characters
print(m[9].str[:18].unique())
