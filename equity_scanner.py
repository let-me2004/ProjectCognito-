import logging
import nifty200_symbols
import pandas as pd
import datetime
import json
import os
import time

logger = logging.getLogger(__name__)

# --- SCANNER CONFIGURATION ---
MIN_PRICE_CHANGE_PCT = 1.5
MIN_VOLUME_SURGE_FACTOR = 2.0
MIN_TOTAL_SURGE_SCORE = 5.0
TOP_N_CANDIDATES = 10
VOLUME_CACHE_FILE = "volume_cache.json"
# -----------------------------

def update_volume_cache(fyers):
    """
    Performs the slow, one-time task of fetching 10-day average volume
    for all NIFTY 200 stocks and saves it to a local cache file.
    """
    logger.info("--- Performing one-time update of the average volume cache. This may take a few minutes... ---")
    symbols = nifty200_symbols.NIFTY_200_SYMBOLS
    volume_cache = {}
    
    end_date = datetime.date.today()
    start_date = end_date - datetime.timedelta(days=20) # Fetch more days to be safe

    for i, symbol in enumerate(symbols):
        try:
            data = {
                "symbol": symbol, "resolution": "D", "date_format": "1",
                "range_from": start_date.strftime("%Y-%m-%d"),
                "range_to": end_date.strftime("%Y-%m-%d"), "cont_flag": "1"
            }
            # Add a small delay to avoid hitting API rate limits
            if i > 0 and i % 3 == 0: time.sleep(0.5) 
                
            response = fyers.history(data=data)

            if response.get("s") == 'ok' and response.get('candles'):
                df = pd.DataFrame(response['candles'])
                avg_vol = df[5].tail(10).mean() # Column 5 is volume
                volume_cache[symbol] = avg_vol
                logger.info(f"Cached avg volume for {symbol}: {avg_vol:,.0f} ({i+1}/{len(symbols)})")
            else:
                logger.warning(f"Could not fetch history for {symbol} during cache update.")
        except Exception as e:
            logger.error(f"Error updating volume cache for {symbol}: {e}")

    # Save the populated cache to disk
    with open(VOLUME_CACHE_FILE, 'w') as f:
        json.dump(volume_cache, f)
        
    logger.info(f"--- Volume cache update complete. Saved to {VOLUME_CACHE_FILE} ---")
    return volume_cache

def get_volume_cache(fyers):
    """
    Loads the average volume data from the local cache file. If the file
    doesn't exist or is from a previous day, it triggers a full update.
    """
    today_str = datetime.date.today().strftime("%Y-%m-%d")
    
    if os.path.exists(VOLUME_CACHE_FILE):
        file_mod_date = datetime.date.fromtimestamp(os.path.getmtime(VOLUME_CACHE_FILE)).strftime("%Y-%m-%d")
        if file_mod_date == today_str:
            logger.info("Loading average volume data from today's cache.")
            with open(VOLUME_CACHE_FILE, 'r') as f:
                return json.load(f)

    # If cache is old or doesn't exist, create a new one
    return update_volume_cache(fyers)


def scan_for_surges(fyers, volume_cache):
    """
    Performs a high-speed scan using the pre-loaded volume cache.
    """
    symbols = nifty200_symbols.NIFTY_200_SYMBOLS
    logger.info("Performing high-speed scan using cached volume data...")
    
    try:
        all_quotes = {}
        # The Fyers quotes API can handle all 200 symbols in a few chunks
        for i in range(0, len(symbols), 70):
            chunk = symbols[i:i + 70]
            quote_data = {"symbols": ",".join(chunk)}
            response = fyers.quotes(data=quote_data)
            if response.get('s') == 'ok':
                for item in response.get('d', []):
                    all_quotes[item['n']] = item['v']
            else:
                logger.error(f"Failed to fetch quotes for chunk {i+1}: {response}")
                time.sleep(0.5) # Wait before next API call on error
        
        if not all_quotes:
            logger.error("Failed to fetch any quote data in this cycle.")
            return []

    except Exception as e:
        logger.error(f"An error occurred during bulk quote fetch: {e}", exc_info=True)
        return []

    candidates = []
    for symbol, quote in all_quotes.items():
        avg_volume = volume_cache.get(symbol)
        if not avg_volume or avg_volume == 0:
            continue

        ltp = quote.get('lp', 0)
        prev_close = quote.get('prev_close_price', 0)
        current_volume = quote.get('volume', 0)
        
        if ltp == 0 or prev_close == 0:
            continue

        price_change_pct = ((ltp - prev_close) / prev_close) * 100
        volume_factor = current_volume / avg_volume

        # --- SURGE SCORING LOGIC ---
        price_score = (price_change_pct / MIN_PRICE_CHANGE_PCT) * 5.0 if MIN_PRICE_CHANGE_PCT > 0 else 0
        volume_score = (volume_factor / MIN_VOLUME_SURGE_FACTOR) * 5.0 if MIN_VOLUME_SURGE_FACTOR > 0 else 0
        total_score = price_score + volume_score

        if price_change_pct > MIN_PRICE_CHANGE_PCT and volume_factor > MIN_VOLUME_SURGE_FACTOR and total_score > MIN_TOTAL_SURGE_SCORE:
            candidate_data = {
                'symbol': symbol, 'ltp': ltp, 'price_change_pct': price_change_pct,
                'volume_factor': volume_factor, 'score': total_score
            }
            candidates.append(candidate_data)

    if not candidates:
        logger.info("...Scan complete. No stocks passed the initial surge filter.")
        return []

    # Rank and return the best candidates
    ranked_candidates = sorted(candidates, key=lambda x: x['score'], reverse=True)
    top_candidates = ranked_candidates[:TOP_N_CANDIDATES]
    
    logger.info(f"--- High-speed scan complete. Identified {len(top_candidates)} high-potential surge candidate(s). ---")
    for cand in top_candidates:
        logger.info(f"   --> CANDIDATE: {cand['symbol']} | Score: {cand['score']:.2f} (Price: {cand['price_change_pct']:.2f}%, Vol Factor: {cand['volume_factor']:.2f}x)")

    return top_candidates

