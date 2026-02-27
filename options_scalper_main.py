# options_scalper_main.py - ORB Debit Spread Scalper (Queue Architecture)
# ========================================================================
# Uses Opening Range Breakout to detect momentum, then enters debit spreads
# (buy ATM + sell 1-strike OTM) for defined-risk, small-capital trades.
# Only trades 9:30 AM - 11:15 AM when momentum is strongest.

import fyers_client
import logger_setup
import logging
import orb_scalper_strategy
from paper_trader import PaperAccount
import risk_manager
import config
import time
import datetime
import threading
import queue

logger = logger_setup.setup_logger()

# --- STRATEGY CONFIGURATION ---
SYMBOLS_TO_TRADE = {
    "NIFTY": "NSE:NIFTY50-INDEX",
    "BANKNIFTY": "NSE:NIFTYBANK-INDEX"
}
MAX_OPEN_POSITIONS = 4  # 1 per index max (spread = 1 position)
RISK_PERCENTAGE = 1.0
ANALYSIS_INTERVAL = 30  # Check every 30 seconds (faster for breakout detection)
LIVE_TRADING = False    # Set to True to send real orders to the broker

# --- Global State ---
paper_account = None
fyers_model = None
tick_queue = queue.Queue()

# Track latest index LTPs from ticks
_latest_ltp = {}  # {"NIFTY": 25500.0, "BANKNIFTY": 61000.0}


def on_index_tick(tick_data):
    """Fast callback: just push ticks into the queue for processing."""
    if isinstance(tick_data, list):
        for tick in tick_data:
            tick_queue.put(tick)
    else:
        tick_queue.put(tick_data)


def analysis_and_trading_loop():
    """Main logic loop — processes ticks and runs ORB strategy."""
    global paper_account, fyers_model, _latest_ltp
    last_analysis_time = 0

    # Track which symbols we are currently subscribed to
    global currently_subscribed
    currently_subscribed = set(SYMBOLS_TO_TRADE.values())

    while True:
        try:
            tick = tick_queue.get_nowait()
            
            # --- TICK PROCESSING ---
            tick_index_name = None
            index_symbol = None
            index_ltp = 0
            if isinstance(tick, dict) and 'symbol' in tick and 'ltp' in tick:
                sym = tick['symbol']
                ltp = tick['ltp']
                
                # Update latest LTP from tick
                _latest_ltp[sym] = ltp
                
                # Identify if this tick is from an index
                if "NIFTY50" in sym:
                    tick_index_name = "NIFTY"
                    index_symbol = sym
                    index_ltp = ltp
                elif "NIFTYBANK" in sym:
                    tick_index_name = "BANKNIFTY"
                    index_symbol = sym
                    index_ltp = ltp
            
            # Hot-reload: pick up positions added/removed via web dashboard occasionally
            # (We don't need to do this every millisecond, so we can do it during the throttle,
            # but we need the positions object during the fast loop)
            
            # --- FAST LOOP: Position Management (Exits) ---
            # Evaluate exits EVERY single time a new price tick arrives for millisecond execution
            active_positions = list(paper_account.positions.items())
            for sym, pos in active_positions:
                
                # We only process spreads
                if not pos.get('is_spread'):
                    continue
                    
                buy_sym = sym
                sell_sym = pos['sell_symbol']
                
                # Subscribe to options if we haven't already
                if buy_sym not in currently_subscribed or sell_sym not in currently_subscribed:
                    new_subs = [s for s in [buy_sym, sell_sym] if s not in currently_subscribed]
                    if new_subs:
                        logger.info(f"Dynamically subscribing to new options: {new_subs}")
                        fyers_socket.subscribe(symbols=new_subs)
                        for s in new_subs:
                            currently_subscribed.add(s)
                
                # Map to proper index
                is_nifty_pos = 'NIFTY' in buy_sym and 'BANK' not in buy_sym
                is_banknifty_pos = 'BANKNIFTY' in buy_sym
                
                pos_index_name = "NIFTY" if is_nifty_pos else ("BANKNIFTY" if is_banknifty_pos else None)
                
                # 1. Check Index-Based Stop Loss (if index tick)
                if tick_index_name and pos_index_name == tick_index_name:
                    index_live = _latest_ltp.get(pos_index_name, 0)
                    if index_live > 0:
                        sl_hit = False
                        # Format is "LONG SPREAD (LONG)" or "LONG SPREAD (SHORT)"
                        if "(LONG)" in pos['direction']: # Call Spread
                            if index_live <= pos['index_stop_loss_price']:
                                sl_hit = True
                        else: # Put Spread -> "(SHORT)"
                            if index_live >= pos['index_stop_loss_price']:
                                sl_hit = True
                                
                        if sl_hit:
                            logger.warning(f"   [{pos_index_name}] 🔴 ORB STOP-LOSS HIT at {index_live}")
                            if LIVE_TRADING:
                                logger.warning(f"🚨 LIVE TRADING: Executing Stop-Loss market orders for {pos['qty']} qty")
                                _sl_start = time.time()
                                # Close the long leg (sell to close)
                                fyers_client.place_market_order(fyers_model, buy_sym, pos['qty'], -1)
                                # Close the short leg (buy to close)
                                fyers_client.place_market_order(fyers_model, sell_sym, pos['qty'], 1)
                                _sl_end = time.time()
                                logger.warning(f"  ⏱️ FYERS API SL EXECUTION LATENCY: {(_sl_end - _sl_start) * 1000:.2f} ms")
                            
                            # Close on paper account
                            buy_val = _latest_ltp.get(buy_sym, 0)
                            sell_val = _latest_ltp.get(sell_sym, 0)
                            exit_price = (buy_val - sell_val) if (buy_val > 0 and sell_val > 0) else pos['sim_stop_loss_price']
                            paper_account._close_position(buy_sym, "STOP-LOSS", exit_price)
                            continue
                
                # 2. Check Premium-Based Take Profit (Requires Option Ticks)
                # This executes instantly when the option leg ticks
                buy_ltp = _latest_ltp.get(buy_sym, 0)
                sell_ltp = _latest_ltp.get(sell_sym, 0)
                
                if buy_ltp > 0 and sell_ltp > 0:
                    current_spread_value = buy_ltp - sell_ltp
                    
                    if current_spread_value >= pos['sim_take_profit_price']:
                        logger.info(f"   [{pos_index_name}] 🟢 SPREAD TARGET HIT at Rs {current_spread_value:.2f} (Target: Rs {pos['sim_take_profit_price']:.2f})")
                        if LIVE_TRADING:
                            logger.warning(f"🚨 LIVE TRADING: Executing Take-Profit market orders for {pos['qty']} qty")
                            _tp_start = time.time()
                            # Close the long leg (sell to close)
                            fyers_client.place_market_order(fyers_model, buy_sym, pos['qty'], -1)
                            # Close the short leg (buy to close)
                            fyers_client.place_market_order(fyers_model, sell_sym, pos['qty'], 1)
                            _tp_end = time.time()
                            logger.warning(f"  ⏱️ FYERS API TARGET EXECUTION LATENCY: {(_tp_end - _tp_start) * 1000:.2f} ms")
                            
                        paper_account._close_position(buy_sym, "TAKE-PROFIT", current_spread_value)


            # --- SLOW LOOP: Summary printing and Auto Square-Off ---
            now = datetime.datetime.now().time()
            current_time = time.time()
            if current_time - last_analysis_time >= ANALYSIS_INTERVAL:
                last_analysis_time = current_time
            
            # Hot-reload: pick up positions added/removed via web dashboard
                paper_account.sync_positions()
            
                logger.info("=" * 50)
                logger.info(f"[{now.strftime('%H:%M:%S')}] Active Subscriptions: {len(currently_subscribed)} | Positions: {len(paper_account.positions)}/{MAX_OPEN_POSITIONS}")
            
            # --- EOD Auto-Square-Off ---
            if now >= datetime.time(15, 0):
                logger.warning(f"It is {now.strftime('%H:%M')}. Initiating EOD Auto-Square-Off.")
                symbols_to_quote = set(paper_account.positions.keys())
                for pos in paper_account.positions.values():
                    if pos.get('is_spread') and pos.get('sell_symbol'):
                        symbols_to_quote.add(pos['sell_symbol'])
                
                if symbols_to_quote:
                    try:
                        quotes = fyers_model.quotes(data={"symbols": ",".join(symbols_to_quote)})
                        if quotes.get('s') == 'ok':
                            current_prices = {}
                            for q in quotes['d']:
                                current_prices[q['n']] = q['v'].get('lp', 0)
                            paper_account.close_all_positions(reason="EOD_SQUARE_OFF", current_prices=current_prices)
                    except Exception as e:
                        logger.error(f"Error during EOD Square-Off: {e}")
                
                logger.info("--- EOD Square-Off Complete. Exiting. ---")
                paper_account.get_summary()
                exit(0)
                
            # --- 3. New Trade Scanning (ORB Strategy) ---
            if len(paper_account.positions) >= MAX_OPEN_POSITIONS:
                continue
            
            # Only scan during trading window
            if now < orb_scalper_strategy.TRADING_START:
                continue
            if now > orb_scalper_strategy.TRADING_END:
                continue
                
            # Check for ORB breakout (only if this tick is an index update)
            if tick_index_name and index_symbol and index_ltp > 0:
                signal = orb_scalper_strategy.get_orb_trade_signal(
                    fyers_model, tick_index_name, index_symbol, index_ltp
                )
                
                if signal is None:
                    continue
                
                # --- Execute the spread trade ---
                logger.info(f"   [{tick_index_name}] 🎯 BREAKOUT DETECTED: {signal['direction']}")
                
                # Spread risk check: max loss = net_debit × quantity
                # For spreads, we DON'T use index SL points (that's for naked options)
                lot_size = risk_manager.LOT_SIZES.get(tick_index_name, 65)
                max_risk_per_trade = paper_account.balance * (RISK_PERCENTAGE / 100)
                max_loss_per_lot = signal["net_debit"] * lot_size  # e.g. ₹26 × 75 = ₹1,950
                
                if max_loss_per_lot > max_risk_per_trade:
                    logger.warning(f"   [{tick_index_name}] Spread cost ₹{max_loss_per_lot:,.0f}/lot exceeds risk budget ₹{max_risk_per_trade:,.0f}")
                    continue
                
                lots = 1  # Conservative: 1 lot per spread
                quantity = lots * lot_size
                
                logger.info(f"   [{tick_index_name}] Risk OK: Max loss ₹{max_loss_per_lot:,.0f}/lot (budget: ₹{max_risk_per_trade:,.0f})")
            
                # Execute the spread
                direction = "LONG" if signal["trade_type"] == "CE" else "SHORT"
                
                if LIVE_TRADING:
                    # --- LIVE MARGIN CHECK ---
                    # Calculate approximated margin required for this specific index's spread
                    min_margin_required = fyers_client.calculate_spread_margin(tick_index_name)
                    
                    live_balance = fyers_client.get_available_margin(fyers_model)
                    if live_balance < min_margin_required:
                        logger.warning(f"🚨 LIVE TRADING BLOCKED: Insufficient free margin (₹{live_balance:,.2f}). Need estimated ₹{min_margin_required:,.0f} for a new {tick_index_name} spread.")
                        continue
                        
                    # ---------------- LIVE TRADE EXECUTION ----------------
                    # Calculate limit prices with a 1% markup/markdown to ensure IOC execution against L1 quotes
                    buy_limit = round(signal["buy_ltp"] * 1.01, 2)
                    sell_limit = round(signal["sell_ltp"] * 0.99, 2)
                    
                    logger.warning(f"🚨 LIVE TRADING: Placing Multi-Leg Order for {quantity} qty")
                    
                    _send_time = time.time()
                    order_response = fyers_client.place_multileg_order(
                        fyers_instance=fyers_model,
                        buy_symbol=signal["buy_symbol"],
                        buy_qty=quantity,
                        buy_limit_price=buy_limit,
                        sell_symbol=signal["sell_symbol"],
                        sell_qty=quantity,
                        sell_limit_price=sell_limit
                    )
                    _ack_time = time.time()
                    latency_ms = (_ack_time - _send_time) * 1000
                    logger.warning(f"  ⏱️ FYERS API ENTRY EXECUTION LATENCY: {latency_ms:.2f} ms")
                    
                    if order_response.get("s") == "ok" or order_response.get("status") == "success":
                        logger.info(f"✅ Live spread filled: {order_response['order_id']}")
                        
                        # Also record it in paper account for dashboard tracking
                        paper_account.execute_spread(
                            buy_symbol=signal["buy_symbol"],
                            sell_symbol=signal["sell_symbol"],
                            quantity=quantity,
                            buy_premium=buy_limit,  # use limit price as entry
                            sell_premium=sell_limit, # use limit price as sell entry
                            net_debit=buy_limit - sell_limit,
                            max_profit=signal["spread_width"] - (buy_limit - sell_limit),
                            profit_target=signal["profit_target"],
                            index_entry_price=signal["breakout_price"],
                            index_stop_loss_price=signal["index_stop_loss"],
                            spread_width=signal["spread_width"],
                            direction=direction
                        )
                    else:
                        logger.error(f"❌ Live spread execution failed: {order_response['message']}")
                else:
                    # ---------------- PAPER TRADE EXECUTION ----------------
                    paper_account.execute_spread(
                        buy_symbol=signal["buy_symbol"],
                        sell_symbol=signal["sell_symbol"],
                        quantity=quantity,
                        buy_premium=signal["buy_ltp"],
                        sell_premium=signal["sell_ltp"],
                        net_debit=signal["net_debit"],
                        max_profit=signal["max_profit"],
                        profit_target=signal["profit_target"],
                        index_entry_price=signal["breakout_price"],
                        index_stop_loss_price=signal["index_stop_loss"],
                        spread_width=signal["spread_width"],
                        direction=direction
                    )
            
                # Mark this breakout as taken (1 trade per index per day)
                orb_scalper_strategy.mark_breakout_taken(tick_index_name)
            
            paper_account.get_summary()

        except queue.Empty:
            time.sleep(0.1)
        except Exception as e:
            logger.error(f"Error in analysis loop: {e}", exc_info=True)
            time.sleep(5)


if __name__ == '__main__':
    logger.info("====== ORB Debit Spread Scalper Initializing ======")
    fyers_model = fyers_client.get_fyers_model()
    if fyers_model:
        paper_account = PaperAccount(initial_balance=config.ACCOUNT_BALANCE, filename="paper_positions_scalper.json")
        
        symbols_to_watch = list(SYMBOLS_TO_TRADE.values())
        
        fyers_socket = fyers_client.start_level2_websocket(
            access_token=fyers_model.token,
            on_tick=on_index_tick,
            symbols=symbols_to_watch
        )

        if fyers_socket:
            ws_thread = threading.Thread(target=fyers_socket.keep_running, daemon=True)
            ws_thread.start()
            
            try:
                logger.info("--- Initialization Complete. ORB Scalper is live. ---")
                logger.info(f"--- Trading window: {orb_scalper_strategy.TRADING_START} - {orb_scalper_strategy.TRADING_END} ---")
                logger.info(f"--- Max positions: {MAX_OPEN_POSITIONS} | Profit target: {orb_scalper_strategy.PROFIT_TARGET_PCT}% ---")
                analysis_and_trading_loop()
            except KeyboardInterrupt:
                logger.info(">>> Shutdown signal received. <<<")
            finally:
                if fyers_socket.is_connected():
                    fyers_socket.close_connection()
                logger.info("WebSocket connection closed.")
        else:
            logger.critical("Could not start WebSocket.")
    else:
        logger.critical("Authentication failed.")
    
    logger.info("====== ORB Debit Spread Scalper Shut Down ======")
