import yfinance as yf
import pandas as pd
import numpy as np
import scipy.stats as stats
import matplotlib.pyplot as plt
import os

def black_scholes_straddle(S, K, T, r, sigma):
    """
    Calculates the price of an ATM straddle (Call + Put) using Black-Scholes.
    S: Spot Price
    K: Strike Price
    T: Time to Maturity (Years)
    r: Risk-free rate
    sigma: Volatility
    """
    if T <= 0:
        return max(S - K, 0) + max(K - S, 0)
    
    d1 = (np.log(S / K) + (r + 0.5 * sigma ** 2) * T) / (sigma * np.sqrt(T))
    d2 = d1 - sigma * np.sqrt(T)
    
    call_price = S * stats.norm.cdf(d1) - K * np.exp(-r * T) * stats.norm.cdf(d2)
    put_price = K * np.exp(-r * T) * stats.norm.cdf(-d2) - S * stats.norm.cdf(-d1)
    
    return call_price + put_price

def fetch_real_data():
    print("Loading actual historical options data from parquet...")
    df = pd.read_parquet('data/actual_historical_options_straddle.parquet')
    print(f"Initial raw rows loaded: {len(df)}")
    
    # We need the daily returns of the spot to calculate HV still
    if 'NIFTY_Spot_Open' not in df.columns or 'BANKNIFTY_Spot_Open' not in df.columns:
        print("Required spot open columns are missing. Check historical data.")
        return pd.DataFrame()

    df['Nifty_Ret'] = df['NIFTY_Spot_Open'] / df['NIFTY_Spot_Open'].shift(1) - 1
    df['BankNifty_Ret'] = df['BANKNIFTY_Spot_Open'] / df['BANKNIFTY_Spot_Open'].shift(1) - 1
    
    # For a 60-day dataset, a 20-day HV window drops 1/3rd of our data.
    # Reducing HV window to 5 days.
    df['Nifty_HV'] = df['Nifty_Ret'].rolling(window=5).std() * np.sqrt(252)
    df['BankNifty_HV'] = df['BankNifty_Ret'].rolling(window=5).std() * np.sqrt(252)
    
    valid_df = df.dropna()
    print(f"Valid rows remaining after dropping NAs (5-day window offset): {len(valid_df)}")
    return valid_df

def simulate_real_short_straddle(df, prefix):
    print(f"Simulating short straddle with real premium for {prefix}...")
    
    pnl = []
    
    for idx, row in df.iterrows():
        # Short Straddle: Sell CE + PE at Open, Buy back at Close
        # Profit = (Entry Credit) - (Exit Debit)
        entry_premium = row[f'{prefix}_CE_Open'] + row[f'{prefix}_PE_Open']
        exit_premium = row[f'{prefix}_CE_Close'] + row[f'{prefix}_PE_Close']
        
        # PnL normalized to Spot price for percentage return comparison
        trade_pnl_pct = (entry_premium - exit_premium) / row[f'{prefix}_Spot_Open']
        pnl.append(trade_pnl_pct)
        
    df[f'{prefix}_Straddle_Ret'] = pnl
    df[f'{prefix}_Straddle_Equity'] = (1 + df[f'{prefix}_Straddle_Ret']).cumprod()
    
    return df

def main():
    if not os.path.exists('data/actual_historical_options_straddle.parquet'):
        print("Real data not found. Run historical_options_harvester.py first.")
        return
        
    df = fetch_real_data()
    df = simulate_real_short_straddle(df, 'NIFTY')
    df = simulate_real_short_straddle(df, 'BANKNIFTY')
    
    # Calculate correlation
    correlation = df['NIFTY_Straddle_Ret'].corr(df['BANKNIFTY_Straddle_Ret'])
    
    print(f"\n======================================")
    print(f"Overall Pearson Correlation (Real Data): {correlation:.4f}")
    print(f"======================================\n")
    
    if len(df) > 0:
        # Calculate cumulative metrics
        nifty_cum = df['NIFTY_Straddle_Equity'].iloc[-1].item() if isinstance(df['NIFTY_Straddle_Equity'].iloc[-1], (pd.Series, pd.DataFrame)) else df['NIFTY_Straddle_Equity'].iloc[-1]
        bank_cum = df['BANKNIFTY_Straddle_Equity'].iloc[-1].item() if isinstance(df['BANKNIFTY_Straddle_Equity'].iloc[-1], (pd.Series, pd.DataFrame)) else df['BANKNIFTY_Straddle_Equity'].iloc[-1]
        print(f"Nifty Strategy End Equity: {nifty_cum:.2f}")
        print(f"BankNifty Strategy End Equity: {bank_cum:.2f}")
        
        # Calculate rolling 3-day correlation (shorter window since we only have 11 days)
        df['Rolling_Corr'] = df['NIFTY_Straddle_Ret'].rolling(3).corr(df['BANKNIFTY_Straddle_Ret'])
        
        # Simulate Pairs Trading:
        # Rule: If Rolling Correlation drops below 0.6, we assume a pricing dislocation.
        # We Short the straddle of the index with historically higher HV and Long the other.
        pairs_pnl = []
        
        for idx, row in df.iterrows():
            # For Pairs trading, we need enough data for HV and Rolling Corr to exist
            if pd.isna(row.get('Rolling_Corr')) or pd.isna(row.get('Nifty_HV')) or pd.isna(row.get('BankNifty_HV')) or row.get('Rolling_Corr') >= 0.6:
                pairs_pnl.append(0.0) # No trade
            else:
                # Pricing dislocation detected!
                if row['Nifty_HV'] > row['BankNifty_HV']:
                    trade_ret = row['NIFTY_Straddle_Ret'] - row['BANKNIFTY_Straddle_Ret']
                else:
                    trade_ret = row['BANKNIFTY_Straddle_Ret'] - row['NIFTY_Straddle_Ret']
                pairs_pnl.append(trade_ret)
                
        df['Pairs_Ret'] = pairs_pnl
        df['Pairs_Equity'] = (1 + df['Pairs_Ret']).cumprod()
        
        pairs_cum = df['Pairs_Equity'].iloc[-1].item() if isinstance(df['Pairs_Equity'].iloc[-1], (pd.Series, pd.DataFrame)) else df['Pairs_Equity'].iloc[-1]
        print(f"Pairs Trading Strategy End Equity: {pairs_cum:.2f}")
    else:
        print("Dataframe is empty after dropping NAs. Adjust HV window or fetch more data.")
        return

    # Plotting
    os.makedirs('notebooks', exist_ok=True)
    
    plt.figure(figsize=(12, 12))
    
    # Plot 1: Equity Curves
    plt.subplot(3, 1, 1)
    plt.plot(df['Date'], df['NIFTY_Straddle_Equity'], label='Nifty Short Straddle (Real Data)')
    plt.plot(df['Date'], df['BANKNIFTY_Straddle_Equity'], label='BankNifty Short Straddle (Real Data)')
    plt.title('Simulated Intraday Short ATM Straddle Equity Curve (Actual Fyers Data)')
    plt.ylabel('Cumulative Growth')
    plt.legend()
    plt.grid(True)
    
    # Plot 2: Rolling Correlation
    plt.subplot(3, 1, 2)
    plt.plot(df['Date'], df['Rolling_Corr'], color='purple', label='10-Day Rolling Correlation')
    plt.axhline(0.6, color='orange', linestyle='--', label='Pairs Trade Trigger (< 0.6)')
    plt.axhline(df['Rolling_Corr'].mean(), color='red', linestyle='--', label='Mean Correlation')
    plt.title('Rolling 10-Day Correlation between Nifty and BankNifty Straddle Returns')
    plt.ylabel('Correlation Coefficient')
    plt.legend()
    plt.grid(True)
    
    # Plot 3: Pairs Trading Equity Curve
    plt.subplot(3, 1, 3)
    plt.plot(df['Date'], df['Pairs_Equity'], color='green', label='Pairs Trading Equity')
    plt.title('Pairs Trade Equity (Triggered only when Correlation < 0.6)')
    plt.ylabel('Cumulative Growth')
    plt.legend()
    plt.grid(True)
    
    plt.tight_layout()
    plt.savefig('notebooks/volatility_correlation_actual.png')
    print("Plot saved to notebooks/volatility_correlation_actual.png")
    
if __name__ == "__main__":
    main()
