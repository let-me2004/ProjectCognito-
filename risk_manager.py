import math
import logging

logger = logging.getLogger(__name__)

# --- Instrument Configuration ---
# NOTE: These are INDEX lot sizes. Equity risk is calculated differently.
LOT_SIZES = {
    "NIFTY": 65,
    "BANKNIFTY": 30
}
# --------------------------------

def calculate_scalping_trade(account_balance, risk_percentage, stop_loss_points, index_name="NIFTY"):
    """
    Calculates the number of lots for an options scalping trade based on a 
    fixed stop-loss in points on the underlying index.
    """
    if stop_loss_points <= 0:
        return {"is_trade_valid": False, "reason": "Stop loss points must be positive."}

    if index_name not in LOT_SIZES:
        return {"is_trade_valid": False, "reason": f"No lot size configured for index: {index_name}"}

    lot_size = LOT_SIZES[index_name]
    
    # Calculate risk parameters
    max_risk_per_trade = account_balance * (risk_percentage / 100)
    risk_per_lot = stop_loss_points * lot_size
    
    if risk_per_lot <= 0:
        return {"is_trade_valid": False, "reason": "Calculated risk per lot is zero or negative."}

    # Calculate ideal number of lots
    try:
        max_lots = math.floor(max_risk_per_trade / risk_per_lot)
    except Exception as e:
        logger.error(f"Error during lot calculation: {e}")
        return {"is_trade_valid": False, "reason": "Error during lot calculation."}

    # Check if we can afford even 1 lot
    if max_lots < 1:
        return {
            "is_trade_valid": False,
            "reason": f"Risk is too high. Stop-loss of {stop_loss_points:.2f} points (₹{risk_per_lot:.2f}/lot) exceeds max risk of ₹{max_risk_per_trade:.2f} even for 1 lot."
        }

    # For scalping, we often just take 1 lot if it's within budget
    lots_to_trade = 1 # Default to 1 lot for this strategy
    
    if lots_to_trade > max_lots:
         return {
            "is_trade_valid": False,
            "reason": f"Calculated lots ({lots_to_trade}) exceeds max allowed lots ({max_lots}) for risk parameters."
        }

    return {
        "is_trade_valid": True,
        "lots": lots_to_trade,
        "quantity": lots_to_trade * lot_size,
        "max_risk_allowed": max_risk_per_trade,
        "risk_per_lot": risk_per_lot
    }

def calculate_equity_trade(account_balance, risk_percentage, entry_price, stop_loss_price):
    """
    Calculates the position size (number of shares) for an equity trade.
    THIS IS THE PATCH: Now correctly handles short positions.
    """
    
    # --- THIS IS THE FIX ---
    # Use absolute difference to handle both long and short trades
    risk_per_share = abs(entry_price - stop_loss_price)
    # -----------------------

    if risk_per_share <= 0:
        return {"is_trade_valid": False, "reason": "Risk per share is zero. Check entry/stop prices."}
        
    if entry_price > stop_loss_price: # Long trade
        pass # Standard logic
    elif entry_price < stop_loss_price: # Short trade
        pass # Logic is now handled by abs()
    else:
        return {"is_trade_valid": False, "reason": "Entry and Stop-loss are the same price."}

    max_risk_per_trade = account_balance * (risk_percentage / 100)
    
    # Check if the trade is even possible
    if risk_per_share > max_risk_per_trade:
        return {
            "is_trade_valid": False,
            "reason": f"Risk per share (₹{risk_per_share:.2f}) is greater than max allowed risk (₹{max_risk_per_trade:.2f})."
        }

    # Calculate position size
    try:
        position_size = math.floor(max_risk_per_trade / risk_per_share)
    except Exception as e:
        logger.error(f"Error during position size calculation: {e}")
        return {"is_trade_valid": False, "reason": "Error during calculation."}

    # Check if we can buy at least 1 share
    if position_size < 1:
        return {"is_trade_valid": False, "reason": "Calculated position size is less than 1 share."}
        
    # Check if we have enough capital to make the purchase
    total_cost = entry_price * position_size
    if total_cost > account_balance:
        # We can't afford the ideal size, so we down-size to what we can afford
        position_size = math.floor(account_balance / entry_price)
        if position_size < 1:
            return {"is_trade_valid": False, "reason": "Not enough capital for 1 share."}

    return {
        "is_trade_valid": True,
        "position_size": position_size,
        "risk_per_share": risk_per_share,
        "total_risk": risk_per_share * position_size,
        "total_cost": entry_price * position_size
    }

