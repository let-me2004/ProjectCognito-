import pandas as pd

url = "https://public.fyers.in/sym_details/NSE_FO.csv"
df = pd.read_csv(url, header=None)

m = df[df[13] == "NIFTY"]
print("Sample NIFTY Strike Prices in Col 14:")
print(m[14].unique()[:20])

m2 = df[(df[13] == "NIFTY") & (df[9].str.endswith("PE", na=False))]
print("Sample NIFTY PE Strike Prices in Col 14:")
print(m2[14].unique()[:20])
