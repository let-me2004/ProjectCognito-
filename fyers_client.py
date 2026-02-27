# fyers_client.py - FINAL MASTER VERSION

import os
import webbrowser
import datetime
import pandas as pd
from fyers_apiv3.fyersModel import FyersModel, SessionModel
from fyers_apiv3.FyersWebsocket.data_ws import FyersDataSocket
import config
import time
import logging

logger = logging.getLogger(__name__)

# --- Configuration ---
REDIRECT_URI = "http://127.0.0.1"
TOKEN_FILE = "access_token.txt"

# --- Authentication Functions ---
def generate_new_token(client_id, secret_key):
    """Generates a new access token via the manual login flow."""
    try:
        session = SessionModel(
            client_id=client_id, 
            secret_key=secret_key, 
            redirect_uri=REDIRECT_URI, 
            response_type="code", 
            grant_type="authorization_code"
        )
        auth_url = session.generate_authcode()
        logger.info("--- NEW FYERS AUTHENTICATION REQUIRED ---")
        logger.info("1. A login page will now open. Please log in.")
        webbrowser.open(auth_url, new=1)
        auth_code = input("2. Paste the auth_code from the redirected URL here and press Enter: ")
        session.set_token(auth_code)
        response = session.generate_token()
        if response and "access_token" in response:
            access_token = response["access_token"]
            logger.info("Access Token generated successfully.")
            token_file = "access_token_hft.txt" if client_id == config.HFT_FYERS_APP_ID else TOKEN_FILE
            with open(token_file, 'w') as f: f.write(access_token)
            return access_token
        else:
            logger.error(f"Failed to generate Access Token. Response: {response}")
            return None
    except Exception as e:
        logger.error(f"Error during new token generation: {e}", exc_info=True)
        return None

def get_fyers_model(client_id=None, secret_key=None):
    """Initializes and returns an authenticated FyersModel instance."""
    use_hft_keys = client_id is not None and secret_key is not None
    if not use_hft_keys:
        client_id = config.FYERS_APP_ID
        secret_key = config.FYERS_SECRET_KEY

    token_file = "access_token_hft.txt" if use_hft_keys else TOKEN_FILE
    access_token = None

    if os.path.exists(token_file):
        with open(token_file, 'r') as f:
            access_token = f.read().strip()

    if access_token:
        fyers = FyersModel(client_id=client_id, token=access_token, log_path=os.path.join(os.getcwd(), "logs"))
        profile_check = fyers.get_profile()
        if profile_check.get('s') == 'ok':
            logger.info(f"Authentication successful for {client_id} using saved token.")
            return fyers
        else:
            logger.warning(f"Saved token for {client_id} is invalid. Requesting new token.")
            if os.path.exists(token_file): os.remove(token_file)
    
    new_access_token = generate_new_token(client_id, secret_key)
    if new_access_token:
        return FyersModel(client_id=client_id, token=new_access_token, log_path=os.path.join(os.getcwd(), "logs"))
    else:
        return None

# --- Data Functions for Options Agent & ML ---
def get_historical_data(fyers_instance, symbol, timeframe, start_date, end_date):
    """Fetches historical data and returns it as a pandas DataFrame."""
    try:
        data = {
            "symbol": symbol,
            "resolution": str(timeframe),
            "date_format": "1",
            "range_from": start_date.strftime("%Y-%m-%d"),
            "range_to": end_date.strftime("%Y-%m-%d"),
            "cont_flag": "1"
        }
        response = fyers_instance.history(data=data)
        if response.get("s") == 'ok' and response.get('candles'):
            candles = response['candles']
            df = pd.DataFrame(candles, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
            df['timestamp'] = pd.to_datetime(df['timestamp'], unit='s')
            df = df.sort_values(by='timestamp').set_index('timestamp')
            return df
        else:
            logger.error(f"Could not fetch historical data for {symbol}: {response}")
            return pd.DataFrame()
    except Exception as e:
        logger.error(f"Error in get_historical_data for {symbol}: {e}", exc_info=True)
        return pd.DataFrame()

_symbol_master_df = None
_symbol_master_date = None

def _get_fyers_symbol_master():
    global _symbol_master_df, _symbol_master_date
    today = datetime.date.today()
    if _symbol_master_df is not None and _symbol_master_date == today:
        return _symbol_master_df
    
    try:
        logger.info("Downloading Fyers Symbol Master...")
        url = "https://public.fyers.in/sym_details/NSE_FO.csv"
        df = pd.read_csv(url, header=None)
        _symbol_master_df = df
        _symbol_master_date = today
        return df
    except Exception as e:
        logger.error(f"Failed to fetch Fyers Symbol Master: {e}")
        return None

def find_option_by_offset(fyers_instance, index_name, option_type="CE", offset=0):
    """
    Finds an option for a given index (NIFTY or BANKNIFTY) by constructing
    and validating possible symbols using the Fyers symbol master.
    """
    try:
        if index_name.upper() == "NIFTY":
            underlying_symbol = "NSE:NIFTY50-INDEX"
            base_symbol = "NIFTY"
        elif index_name.upper() == "BANKNIFTY":
            underlying_symbol = "NSE:NIFTYBANK-INDEX"
            base_symbol = "BANKNIFTY"
        else:
            underlying_symbol = f"NSE:{index_name.upper()}-INDEX"
            base_symbol = index_name.upper()
        
        quote_data = {"symbols": underlying_symbol}
        quote = fyers_instance.quotes(data=quote_data)
        if quote.get('s') != 'ok' or not quote.get('d'):
            logger.error(f"Could not fetch spot price for {index_name}. Response: {quote}")
            return None
            
        data = quote['d'][0]['v']
        if 'lp' not in data:
             logger.error(f"Spot price 'lp' missing in response for {index_name}: {data}")
             return None
             
        spot_price = data['lp']
        logger.info(f"   ...{index_name} spot price is {spot_price}")

        rounding = 50 if index_name.upper() == "NIFTY" else 100
        strike_step = 50 if index_name.upper() == "NIFTY" else 100

        atm_strike = round(spot_price / rounding) * rounding
        target_strike = atm_strike + (offset * strike_step) if option_type == "CE" else atm_strike - (offset * strike_step)
        logger.info(f"   ...Targeting strike price: {target_strike}")
        
        # --- NEW LOGIC: Use Fyers Symbol Master to find exact symbol ---
        df = _get_fyers_symbol_master()
        if df is not None:
            # Filter for the specific base, exact strike and option type
            # 13: Underlying, 15: Strike Price, 16: Option Type (CE/PE/XX)
            mask = (df[13] == base_symbol) & (df[15] == float(target_strike)) & (df[16] == option_type)
            matching = df[mask]
            
            if not matching.empty:
                # Sort by Expiry Epoch (Column 8)
                matching = matching.sort_values(by=8)
                best_symbol = matching.iloc[0][9]
                
                logger.debug(f"   ...Testing master symbol: {best_symbol}")
                quote = fyers_instance.quotes({"symbols": best_symbol})
                if quote.get('s') == 'ok' and quote.get('d') and quote['d'][0].get('v', {}).get('lp', 0) > 0:
                    logger.info(f"   >>> SUCCESS: Valid symbol found from master: {best_symbol}")
                    option_data = quote['d'][0]['v']
                    return { "symbol": best_symbol, "ltp": option_data.get('lp'), "bid": option_data.get('bid'), "ask": option_data.get('ask'), "spot_price": spot_price}
                else:
                    logger.debug(f"   ...Symbol {best_symbol} from master returned invalid quote.")
            else:
                 logger.debug(f"   ...No matching symbols found in master for {base_symbol} {target_strike} {option_type}")
        
        logger.debug(f">>> FAILURE: Could not find a valid instrument for {index_name} at strike {target_strike}.")
        return None
            
    except Exception as e:
        logger.error(f"An error occurred in find_option_by_offset: {e}", exc_info=True)
        return None

# --- Quote Functions ---

def get_quotes(fyers_instance, symbols):
    """
    Fetch current quotes for a list of symbols.
    Returns list of dicts with 'symbol' and 'ltp' keys.
    """
    try:
        symbols_str = ",".join(symbols) if isinstance(symbols, list) else symbols
        quote_data = {"symbols": symbols_str}
        response = fyers_instance.quotes(data=quote_data)
        if response.get('s') != 'ok' or not response.get('d'):
            logger.error(f"Quote fetch failed: {response}")
            return []
        
        results = []
        for item in response['d']:
            v = item.get('v', {})
            results.append({
                'symbol': v.get('symbol', item.get('n', '')),
                'ltp': v.get('lp', 0)
            })
        return results
    except Exception as e:
        logger.error(f"Error fetching quotes: {e}")
        return []

def place_multileg_order(fyers_instance, buy_symbol, buy_qty, buy_limit_price, 
                         sell_symbol, sell_qty, sell_limit_price):
    """
    Places a multi-leg order (basket) for an option spread to get margin benefits.
    Fyers API requires:
    - segment = 14 (NSE FNO)
    - type = 1 (Limit Order)
    - validity = "IOC"
    - slNo = Sequential number for each leg (1, 2)
    """
    try:
        data = {
            "orderType": "2L",  # 2L = 2-Leg Order
            "validity": "IOC", # Must be IOC for multi-leg
            "offlineOrder": False,
            "productType": "MARGIN",
            "legs": [
                {
                    "symbol": buy_symbol,
                    "qty": int(buy_qty),
                    "type": 1,  # Limit Order
                    "side": 1,  # 1 = Buy
                    "productType": "MARGIN",
                    "limitPrice": float(buy_limit_price),
                    "slNo": 1
                },
                {
                    "symbol": sell_symbol,
                    "qty": int(sell_qty),
                    "type": 1,  # Limit Order
                    "side": -1, # -1 = Sell
                    "productType": "MARGIN",
                    "limitPrice": float(sell_limit_price),
                    "slNo": 2
                }
            ]
        }
        
        logger.info(f"Placing Multi-Leg Spread Order: BUY {buy_symbol} @ {buy_limit_price}, SELL {sell_symbol} @ {sell_limit_price}")
        response = fyers_instance.place_multileg_order(data=data)
        
        if response is None:
             logger.error("Fyers API returned None. Order was instantly rejected or network timeout.")
             return {"status": "error", "message": "Fyers API returned None for multileg order"}
             
        if response.get('s') == 'ok':
            order_id = response.get('id')
            logger.info(f"Multi-Leg Order placed successfully. Order ID: {order_id}")
            return {"status": "success", "order_id": order_id, "response": response}
        else:
            logger.error(f"Failed to place multi-leg order: {response}")
            return {"status": "error", "message": response.get('message', str(response))}
            
    except Exception as e:
        logger.error(f"Exception during multi-leg order placement: {e}", exc_info=True)
        return {"status": "error", "message": str(e)}

def place_market_order(fyers_instance, symbol, qty, side):
    """
    Places a single-leg Market order to close out a position.
    Fyers API requires:
    - segment = 14 (NSE FNO)
    - type = 2 (Market Order)
    - side = 1 (Buy) or -1 (Sell)
    """
    try:
        data = {
            "symbol": symbol,
            "qty": int(qty),
            "type": 2,          # Market Order
            "side": int(side),  # 1 for Buy, -1 for Sell
            "productType": "MARGIN",
            "limitPrice": 0,
            "stopPrice": 0,
            "validity": "DAY",
            "disclosedQty": 0,
            "offlineOrder": False
        }
        
        action = "BUY" if side == 1 else "SELL"
        logger.info(f"Placing Market Order: {action} {qty} qty of {symbol}")
        
        response = fyers_instance.place_order(data=data)
        
        if response.get('s') == 'ok':
            order_id = response.get('id')
            logger.info(f"Market Order {action} placed successfully. Order ID: {order_id}")
            return {"status": "success", "order_id": order_id, "response": response}
        else:
            logger.error(f"Failed to place market order: {response}")
            return {"status": "error", "message": response.get('message', str(response))}
            
    except Exception as e:
        logger.error(f"Exception during market order placement: {e}", exc_info=True)
        return {"status": "error", "message": str(e)}

# --- WebSocket Function (NON-BLOCKING) ---
def start_level2_websocket(access_token, on_tick, symbols):
    """
    Connects to the Fyers WebSocket for Level 2 data.
    THIS IS NON-BLOCKING and requires a valid access token.
    """
    try:
        client_id = config.FYERS_APP_ID # Sockets use the primary app ID
        socket_access_token = f"{client_id}:{access_token}"

        def on_message(message):
            on_tick(message)

        def on_error(message):
            # print(f"[FYERS DEBUG] WebSocket Error: {message}")
            logger.error(f"WebSocket Error: {message}")

        def on_close(message):
            # print(f"[FYERS DEBUG] WebSocket Closed: {message}")
            logger.warning(f"WebSocket Connection Closed: {message}")

        def on_open():
            # print("[FYERS DEBUG] WebSocket Opened. Subscribing...")
            logger.info("WebSocket Connection Opened. Subscribing to symbols...")
            # data_type not specified - rely on default
            fyers_socket.subscribe(symbols=symbols)
            # print(f"[FYERS DEBUG] Subscribed to: {symbols}")
            logger.info(f"Subscribed to: {symbols}")

        fyers_socket = FyersDataSocket(
            access_token=socket_access_token,
            log_path=os.path.join(os.getcwd(), "logs"),
            on_message=on_message,
            on_error=on_error,
            on_close=on_close,
            on_connect=on_open
        )

        fyers_socket.connect()
        
        logger.info("WebSocket connection process initiated...")
        return fyers_socket

    except Exception as e:
        logger.error(f"An error occurred in start_level2_websocket: {e}", exc_info=True)
        return None

def get_available_margin(fyers_instance):
    """
    Fetches the 'Available Balance' from the Fyers Funds API to ensure
    there is sufficient margin before taking a new live trade.
    """
    try:
        response = fyers_instance.funds()
        if response and response.get('s') == 'ok':
            for fund in response.get('fund_limit', []):
                if fund.get('id') == 10 or fund.get('title') == 'Available Balance':
                    return float(fund.get('equityAmount', 0.0))
                    
        logger.error(f"Could not parse live available balance from Fyers: {response}")
        # Fallback to config balance if API string fails
        import config
        return config.ACCOUNT_BALANCE
    except Exception as e:
        logger.error(f"Error fetching live funds: {e}", exc_info=True)
        import config
        return config.ACCOUNT_BALANCE

def calculate_spread_margin(index_name):
    """
    Since the Fyers v3 Margin API endpoint is deprecated for raw HTTP posts, 
    we approximate the NSE span + exposure margin required for a 1-lot Debit Spread.
    
    A perfectly hedged 1-lot debit spread (Buy ATM, Sell OTM) has defined risk
    and benefits from massive margin reduction, typically requiring ₹30k - ₹40k.
    We add a 5% buffer for peak margin fluctuations.
    """
    if index_name == "NIFTY":
        # Standard hedged span + exposure for 1 Nifty lot (75) is roughly ~22,000 to ~32,000.
        # Plus execution buffer and charges:
        return 36500.0  
    elif index_name == "BANKNIFTY":
        # Standard hedged span + exposure for 1 BankNifty lot (15) is roughly ~28,000 to ~38,000.
        # Plus execution buffer and charges:
        return 42500.0
    else:
        return 50000.0