import fyers_client
import pandas as pd
import datetime
import calendar
import time
import os
import yfinance as yf
import logging
from tqdm import tqdm

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# --- Utility Functions ---
def get_historical_thursdays(start_date, end_date):
    """Returns a list of all Thursdays between start_date and end_date."""
    thursdays = []
    current_date = start_date
    while current_date <= end_date:
        if current_date.weekday() == 3: # Thursday
            thursdays.append(current_date)
        current_date += datetime.timedelta(days=1)
    return thursdays

def get_symbols_for_date(index_name, target_date, spot_price):
    """
    Constructs the Fyers option symbol for a given date and spot price.
    Returns (Call Symbol, Put Symbol).
    Note: Prior to recent NSE changes, banknifty also expired on Thursdays.
    For simplicity in historical 5-year data, we assume Thursday expiries.
    """
    rounding = 50 if index_name == "NIFTY" else 100
    atm_strike = int(round(spot_price / rounding) * rounding)
    
    # Logic to find the *next* weekly expiry from the target_date
    days_ahead = 3 - target_date.weekday()
    if days_ahead < 0:
        days_ahead += 7
    expiry_date = target_date + datetime.timedelta(days=days_ahead)
    
    # Fyers Symbol Format: NSE:NIFTY24O1025000CE
    # Format rules: YY (Year), M/Mon (Month), DD (Day), STRIKE, TYPE
    base_sym = "NIFTY" if index_name == "NIFTY" else "BANKNIFTY"
    
    month_map = {10: 'O', 11: 'N', 12: 'D'}
    month_part = str(expiry_date.month) if expiry_date.month < 10 else month_map[expiry_date.month]
    date_str_format1 = f"{expiry_date.strftime('%y')}{month_part}{expiry_date.strftime('%d')}"
    date_str_format2 = expiry_date.strftime('%y%b').upper()
    
    # We will try format 1 first (weekly), then format 2 (monthly) if format 1 fails
    ce_sym_1 = f"NSE:{base_sym}{date_str_format1}{atm_strike}CE"
    pe_sym_1 = f"NSE:{base_sym}{date_str_format1}{atm_strike}PE"
    
    ce_sym_2 = f"NSE:{base_sym}{date_str_format2}{atm_strike}CE"
    pe_sym_2 = f"NSE:{base_sym}{date_str_format2}{atm_strike}PE"
    
    return [(ce_sym_1, pe_sym_1), (ce_sym_2, pe_sym_2)]

def fetch_option_data(fyers, symbol, date):
    """Fetches 5-minute intraday data for a specific option symbol on a specific date."""
    try:
        data = {
            "symbol": symbol,
            "resolution": "5",
            "date_format": "1",
            "range_from": date.strftime("%Y-%m-%d"),
            "range_to": date.strftime("%Y-%m-%d"),
            "cont_flag": "1"
        }
        res = fyers.history(data=data)
        if res.get('s') == 'ok' and res.get('candles'):
            df = pd.DataFrame(res['candles'], columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
            df['timestamp'] = pd.to_datetime(df['timestamp'], unit='s')
            df['timestamp'] = df['timestamp'].dt.tz_localize('UTC').dt.tz_convert('Asia/Kolkata').dt.tz_localize(None)
            return df
        return None
    except Exception as e:
        logger.error(f"Error fetching {symbol}: {e}")
        return None

def harvest_options_history():
    print("--- Starting Historical Options Data Harvest ---")
    fyers = fyers_client.get_fyers_model()
    if not fyers:
        logger.error("Fyers authentication failed. Please check access_token.txt")
        return

    # 1. Fetch Daily Spot prices from yfinance to determine ATM strikes
    print("Fetching historical spot prices from yfinance for the last 60 days...")
    
    # Get dates for the last 60 days
    end_date_str = datetime.date.today().strftime("%Y-%m-%d")
    start_date = datetime.date.today() - datetime.timedelta(days=90) # Buffer for non-trading days
    start_date_str = start_date.strftime("%Y-%m-%d")

    nifty_spot = yf.download("^NSEI", start=start_date_str, end=end_date_str, progress=False)['Open']
    bn_spot = yf.download("^NSEBANK", start=start_date_str, end=end_date_str, progress=False)['Open']
    
    if isinstance(nifty_spot, pd.DataFrame): nifty_spot = nifty_spot.iloc[:, 0]
    if isinstance(bn_spot, pd.DataFrame): bn_spot = bn_spot.iloc[:, 0]

    spot_df = pd.DataFrame({'NIFTY': nifty_spot, 'BANKNIFTY': bn_spot}).dropna()
    
    # Ensure we only take the last 60 trading days exactly
    spot_df = spot_df.tail(60)

    results = []
    
    # Create directory for raw data
    os.makedirs('data/historical_options', exist_ok=True)

    print(f"Total trading days to process: {len(spot_df)}")
    
    # 2. Iterate through each day and fetch the ATM option prices
    for date, row in tqdm(spot_df.iterrows(), total=len(spot_df), desc="Harvesting Data"):
        date_obj = date.date()
        
        day_results = {'Date': date_obj}

        for index_name, spot_price in [('NIFTY', row['NIFTY']), ('BANKNIFTY', row['BANKNIFTY'])]:
            symbol_pairs = get_symbols_for_date(index_name, date_obj, spot_price)
            
            ce_df, pe_df = None, None
            
            # Try weekly format, if no data, try monthly format
            for ce_sym, pe_sym in symbol_pairs:
                ce_df = fetch_option_data(fyers, ce_sym, date_obj)
                pe_df = fetch_option_data(fyers, pe_sym, date_obj)
                
                if ce_df is not None and not ce_df.empty and pe_df is not None and not pe_df.empty:
                    break # Found valid data
                    
                time.sleep(0.5) # Fyers API rate limit compliance
            
            # If we successfully got data for both legs
            if ce_df is not None and not ce_df.empty and pe_df is not None and not pe_df.empty:
                # Extract the 9:15 AM Open (Entry Base) and 3:25 PM Close (Exit Base)
                try:
                    ce_open = ce_df.iloc[0]['open']
                    pe_open = pe_df.iloc[0]['open']
                    
                    ce_close = ce_df.iloc[-1]['close']
                    pe_close = pe_df.iloc[-1]['close']
                    
                    day_results[f'{index_name}_CE_Open'] = ce_open
                    day_results[f'{index_name}_PE_Open'] = pe_open
                    day_results[f'{index_name}_CE_Close'] = ce_close
                    day_results[f'{index_name}_PE_Close'] = pe_close
                    day_results[f'{index_name}_Spot_Open'] = spot_price
                except IndexError:
                    pass # Not enough candles for the day
        
        results.append(day_results)
        
        # Save progress every 100 days to prevent data loss
        if len(results) % 100 == 0:
            temp_df = pd.DataFrame(results)
            temp_df['Date'] = pd.to_datetime(temp_df['Date'])
            temp_df.to_parquet('data/historical_options_progress.parquet', index=False)

    # Final Save
    final_df = pd.DataFrame(results)
    final_df['Date'] = pd.to_datetime(final_df['Date'])
    final_df.to_parquet('data/actual_historical_options_straddle.parquet', index=False)
    print("--- Harvest Complete! Saved to data/actual_historical_options_straddle.parquet ---")

if __name__ == "__main__":
    harvest_options_history()
