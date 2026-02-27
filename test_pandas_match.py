import pandas as pd

url = "https://public.fyers.in/sym_details/NSE_FO.csv"
df = pd.read_csv(url, header=None)

target_strike = 25500
option_type = "CE"
base_symbol = "NIFTY"

# Print df info for those columns
print(f"Type of Col 13: {df[13].dtype}")
print(f"Type of Col 14: {df[14].dtype}")

mask1 = df[13] == base_symbol
mask2 = df[14] == float(target_strike)
mask3 = df[9].str.endswith(option_type, na=False)

print(f"Mask 1 (base) sum: {mask1.sum()}")
print(f"Mask 2 (strike) sum: {mask2.sum()}")
print(f"Mask 3 (type) sum: {mask3.sum()}")

mask = mask1 & mask2 & mask3
print(f"Combined mask sum: {mask.sum()}")
