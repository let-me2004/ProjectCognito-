import pandas as pd

url = "https://public.fyers.in/sym_details/NSE_FO.csv"
df = pd.read_csv(url, header=None)

m = df[df[9].str.contains("NSE:NIFTY26", na=False) & df[9].str.contains("PE", na=False)]
row = m.iloc[0]

for i in range(len(row)):
    print(f"Col {i}: {row[i]}")
