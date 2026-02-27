import pandas as pd
url = "https://public.fyers.in/sym_details/NSE_FO.csv"
df = pd.read_csv(url, header=None)

m = df[df[9].str.startswith("NSE:NIFTY26", na=False)]
row = m.iloc[0]
for i in range(len(row)):
    print(f"Col {i}: {row[i]}")

# Let's also print 1 for BANKNIFTY
mb = df[df[9].str.startswith("NSE:BANKNIFTY26", na=False)]
rowb = mb.iloc[0]
print("--- BANKNIFTY ---")
for i in range(len(rowb)):
    print(f"Col {i}: {rowb[i]}")
