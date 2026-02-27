import logging
import csv
import datetime
import json
import os
import pandas as pd # <--- THIS IS THE FIX

logger = logging.getLogger(__name__)

class PaperAccount:
    """
    A paper trading account that simulates trades and tracks P&L.
    V1.2: Upgraded for backtesting.
    - Stores 6 price points for simulated option trades.
    - Checks exits based on INDEX prices, not option prices.
    """
    def __init__(self, initial_balance=100000.0, filename="paper_positions.json"):
        self.initial_balance = initial_balance
        self.balance = initial_balance
        self.positions = {} # Stores active trades
        self.trade_log = [] # Stores history of closed trades
        self.filename = filename
        self.log_filename = "trade_log.csv"
        self._last_file_mtime = 0  # Track file modification time for hot-reload
        self._setup_log_file()
        self._load_positions() # Restore state
        logger.info(f"Paper Account initialized with balance: ₹{self.balance:,.2f}")
        logger.info(f"Trade log will be saved to: {self.log_filename}")
        logger.info(f"Positions will be saved to: {self.filename}")

    def _setup_log_file(self):
        """Create trade log with headers only if it doesn't exist."""
        if os.path.exists(self.log_filename) and os.path.getsize(self.log_filename) > 0:
            return  # File already has data, don't overwrite
        try:
            with open(self.log_filename, mode='w', newline='') as f:
                writer = csv.writer(f)
                writer.writerow([
                    "trade_id", "symbol", "status", "direction", "qty", 
                    "entry_price", "exit_price", "entry_time", "exit_time",
                    "stop_loss", "take_profit", "pnl"
                ])
        except IOError as e:
            logger.error(f"Could not initialize log file: {e}")

    def _log_trade(self, trade_data):
        try:
            with open(self.log_filename, mode='a', newline='') as f:
                writer = csv.writer(f)
                writer.writerow([
                    trade_data.get("id"), trade_data.get("symbol"), trade_data.get("status"),
                    trade_data.get("direction"), trade_data.get("qty"), trade_data.get("entry_price"),
                    trade_data.get("exit_price"), trade_data.get("entry_time"),
                    trade_data.get("exit_time"), trade_data.get("stop_loss"),
                    trade_data.get("take_profit"), trade_data.get("pnl")
                ])
        except IOError as e:
            logger.error(f"Failed to write to trade log: {e}")

    def _save_positions(self):
        """Saves active positions to a JSON file for persistence."""
        try:
            # excessive serialization for datetime objects
            serializable_positions = {}
            for sym, pos in self.positions.items():
                pos_copy = pos.copy()
                pos_copy['entry_time'] = pos['entry_time'].isoformat()
                serializable_positions[sym] = pos_copy
                
            with open(self.filename, "w") as f:
                json.dump(serializable_positions, f, indent=4)
            
            # Update mtime so we don't re-read our own writes
            self._last_file_mtime = os.path.getmtime(self.filename)
        except Exception as e:
            logger.error(f"Failed to save positions: {e}")

    def _load_positions(self):
        """Loads active positions from JSON file on startup."""
        try:
            with open(self.filename, "r") as f:
                data = json.load(f)
                for sym, pos in data.items():
                    pos['entry_time'] = datetime.datetime.fromisoformat(pos['entry_time'])
                    self.positions[sym] = pos
            if self.positions:
                logger.info(f"Restored {len(self.positions)} active positions from disk.")
            # Track initial file mtime
            self._last_file_mtime = os.path.getmtime(self.filename)
        except FileNotFoundError:
            pass # No existing positions
        except Exception as e:
            logger.error(f"Failed to load positions: {e}")

    def sync_positions(self):
        """
        Hot-reload: checks if the positions JSON file was modified externally
        (e.g. by the web dashboard) and merges any new positions into memory.
        Call this periodically in the main trading loop.
        """
        try:
            if not os.path.exists(self.filename):
                return
            
            current_mtime = os.path.getmtime(self.filename)
            if current_mtime <= self._last_file_mtime:
                return  # No external changes
            
            # File was modified externally — read it
            with open(self.filename, "r") as f:
                disk_data = json.load(f)
            
            # Find NEW positions (on disk but not in memory)
            new_count = 0
            for sym, pos in disk_data.items():
                if sym not in self.positions:
                    pos['entry_time'] = datetime.datetime.fromisoformat(pos['entry_time'])
                    self.positions[sym] = pos
                    new_count += 1
                    logger.info(f"📡 HOT-RELOAD: Picked up new position {sym} (added via dashboard)")
            
            # Find REMOVED positions (in memory but not on disk — closed via dashboard)
            removed = [sym for sym in self.positions if sym not in disk_data]
            for sym in removed:
                del self.positions[sym]
                logger.info(f"📡 HOT-RELOAD: Position {sym} was removed externally (closed via dashboard)")
            
            self._last_file_mtime = current_mtime
            
            if new_count > 0 or removed:
                logger.info(f"📡 HOT-RELOAD complete: +{new_count} new, -{len(removed)} removed. Total: {len(self.positions)}")
        
        except Exception as e:
            logger.error(f"Failed to sync positions: {e}")

    def execute_buy(self, symbol, quantity, 
                    sim_entry_price, sim_stop_loss_price, sim_take_profit_price,
                    index_entry_price, index_stop_loss_price, index_take_profit_price):
        """
        Executes a simulated BUY order.
        Stores both SIM (option) prices for P&L and INDEX (trigger) prices for exits.
        """
        if symbol in self.positions:
            logger.warning(f"Already holding a position in {symbol}. New BUY order ignored.")
            return

        # Calculate Available Balance dynamically
        # Simulating margin: We treat 'sim_entry_price' as full cash requirement for simplicity 
        # unless we want to implement specific margin rules. 
        # For now, let's assume 1x margin (Cash & Carry) for simplicity or match the log logic.
        
        used_margin = sum(p['sim_entry_price'] * p['qty'] for p in self.positions.values())
        available_balance = self.balance - used_margin
        
        cost = sim_entry_price * quantity
        
        if cost > available_balance:
            logger.error(f"Cannot execute BUY for {symbol}. Cost (₹{cost:,.2f}) exceeds AVAILABLE balance (₹{available_balance:,.2f}).")
            return
            
        # We don't deduct balance here, we do it on P&L settlement for simplicity
        
        trade_id = int(datetime.datetime.now().timestamp())
        self.positions[symbol] = {
            "id": trade_id,
            "qty": quantity,
            "direction": "LONG",
            "entry_time": datetime.datetime.now(),
            
            # 1. Prices for P&L (Simulated Option)
            "sim_entry_price": sim_entry_price,
            "sim_stop_loss_price": sim_stop_loss_price,
            "sim_take_profit_price": sim_take_profit_price,
            
            # 2. Prices for Exit Logic (Actual Index)
            "index_entry_price": index_entry_price,
            "index_stop_loss_price": index_stop_loss_price,
            "index_take_profit_price": index_take_profit_price,
        }
        logger.info("--- POSITION OPENED ---")
        logger.info(f"   Symbol: {symbol} | Qty: {quantity} | Entry: ₹{sim_entry_price:,.2f}")
        logger.info(f"   SL (Option): ₹{sim_stop_loss_price:,.2f} | TP (Option): ₹{sim_take_profit_price:,.2f}")
        logger.info(f"   SL (Index): {index_stop_loss_price:,.2f} | TP (Index): {index_take_profit_price:,.2f}")
        
        self._save_positions()

    def execute_sell(self, symbol, quantity, 
                     sim_entry_price, sim_stop_loss_price, sim_take_profit_price,
                     index_entry_price, index_stop_loss_price, index_take_profit_price):
        """
        Executes a simulated SELL (SHORT) order.
        """
        if symbol in self.positions:
            logger.warning(f"Already holding a position in {symbol}. New SELL order ignored.")
            return

        cost = sim_entry_price * quantity
        if cost > self.balance:
            logger.error(f"Cannot execute SELL for {symbol}. Cost (₹{cost:,.2f}) exceeds balance (₹{self.balance:,.2f}).")
            return
            
        trade_id = int(datetime.datetime.now().timestamp())
        self.positions[symbol] = {
            "id": trade_id,
            "qty": quantity,
            "direction": "SHORT",
            "entry_time": datetime.datetime.now(),
            
            # 1. Prices for P&L (Simulated Option)
            "sim_entry_price": sim_entry_price,
            "sim_stop_loss_price": sim_stop_loss_price,
            "sim_take_profit_price": sim_take_profit_price,
            
            # 2. Prices for Exit Logic (Actual Index)
            "index_entry_price": index_entry_price,
            "index_stop_loss_price": index_stop_loss_price,
            "index_take_profit_price": index_take_profit_price,
        }
        logger.info("--- POSITION OPENED (SHORT) ---")
        logger.info(f"   Symbol: {symbol} | Qty: {quantity} | Entry: ₹{sim_entry_price:,.2f}")
        logger.info(f"   SL (Option): ₹{sim_stop_loss_price:,.2f} | TP (Option): ₹{sim_take_profit_price:,.2f}")
        logger.info(f"   SL (Index): {index_stop_loss_price:,.2f} | TP (Index): {index_take_profit_price:,.2f}")
        
        self._save_positions()

    def execute_spread(self, buy_symbol, sell_symbol, quantity, 
                       buy_premium, sell_premium, net_debit,
                       max_profit, profit_target,
                       index_entry_price, index_stop_loss_price, spread_width,
                       direction="LONG"):
        """
        Executes a simulated DEBIT SPREAD order.
        Buys ATM option + Sells OTM option as a single position.
        
        Args:
            buy_symbol: Symbol of the option to buy (ATM leg)
            sell_symbol: Symbol of the option to sell (OTM leg)  
            quantity: Number of shares (lot_size × lots)
            buy_premium: Premium paid for buy leg
            sell_premium: Premium received for sell leg
            net_debit: buy_premium - sell_premium (our cost)
            max_profit: spread_width - net_debit (max we can make)
            profit_target: target exit (% of net_debit)
            index_entry_price: Index price at entry
            index_stop_loss_price: Index price where we exit
            spread_width: Distance between strikes in points
            direction: "LONG" for bullish CE spread, "SHORT" for bearish PE spread
        """
        if buy_symbol in self.positions:
            logger.warning(f"Already holding {buy_symbol}. Spread order ignored.")
            return

        # Check balance against net debit cost
        used_margin = sum(p.get('net_debit', p['sim_entry_price']) * p['qty'] for p in self.positions.values())
        available_balance = self.balance - used_margin
        cost = net_debit * quantity
        
        if cost > available_balance:
            logger.error(f"Cannot execute SPREAD. Cost ₹{cost:,.2f} exceeds available ₹{available_balance:,.2f}")
            return

        trade_id = int(datetime.datetime.now().timestamp())
        
        # TP on index: not used for spreads (we exit on premium target)
        # We use net_debit as sim_entry_price for P&L calculation on dashboard
        # sim_stop_loss_price = 0 means full loss of net_debit
        # sim_take_profit_price = net_debit + profit_target
        self.positions[buy_symbol] = {
            "id": trade_id,
            "qty": quantity,
            "direction": f"LONG SPREAD ({direction})", # Makes dashboard say "LONG SPREAD (SHORT)"
            "entry_time": datetime.datetime.now(),
            
            # Premium prices (for dashboard P&L display)
            "sim_entry_price": net_debit,           # What we paid (net debit per unit)
            "sim_stop_loss_price": 0,                # Max loss = full debit
            "sim_take_profit_price": net_debit + profit_target,  # Target exit premium
            
            # Index-based exit triggers
            "index_entry_price": index_entry_price,
            "index_stop_loss_price": index_stop_loss_price,
            "index_take_profit_price": 0,  # Not used for spreads (premium-based TP)
            
            # Spread-specific fields
            "is_spread": True,
            "sell_symbol": sell_symbol,
            "buy_premium": buy_premium,
            "sell_premium": sell_premium,
            "net_debit": net_debit,
            "max_profit": max_profit,
            "profit_target": profit_target,
            "spread_width": spread_width,
        }
        
        logger.info("--- SPREAD POSITION OPENED ---")
        logger.info(f"   BUY:  {buy_symbol} @ ₹{buy_premium:,.2f}")
        logger.info(f"   SELL: {sell_symbol} @ ₹{sell_premium:,.2f}")
        logger.info(f"   Net Debit: ₹{net_debit:,.2f} × {quantity} = ₹{cost:,.2f}")
        logger.info(f"   Max Profit: ₹{max_profit:,.2f}/unit | Target: +₹{profit_target:,.2f}/unit")
        logger.info(f"   Index SL: {index_stop_loss_price:,.2f}")
        
        self._save_positions()

    def _close_position(self, symbol, exit_reason, index_exit_price):
        """
        Internal function to close a position and log the trade.
        """
        if symbol not in self.positions:
            return

        pos = self.positions.pop(symbol)
        exit_time = datetime.datetime.now()
        
        sim_exit_price = 0
        pnl = 0

        # Determine the exit price based on the reason
        if pos.get('is_spread'):
            sim_exit_price = index_exit_price
            logger.info(f"   ---> {exit_reason} TRIGGERED for spread {symbol} at Net Premium {sim_exit_price:,.2f}")
        else:
            if exit_reason == "TAKE-PROFIT":
                # We hit the INDEX take profit, so we exit at the SIM take profit
                sim_exit_price = pos['sim_take_profit_price']
                logger.info(f"   ---> TAKE-PROFIT TRIGGERED for {symbol} at Index level {index_exit_price:,.2f}")
                
            elif exit_reason == "STOP-LOSS":
                # We hit the INDEX stop loss, so we exit at the SIM stop loss
                sim_exit_price = pos['sim_stop_loss_price']
                logger.info(f"   ---> STOP-LOSS TRIGGERED for {symbol} at Index level {index_exit_price:,.2f}")
                
            elif exit_reason == "MARKET_EXIT":
                 # Exiting at current market price (e.g. EOD or manual close)
                 sim_exit_price = index_exit_price # Here index price IS the Sim price
                 logger.info(f"   ---> MARKET EXIT TRIGGERED for {symbol} at {sim_exit_price:,.2f}")

        # Calculate P&L based on simulated option prices
        if pos.get('is_spread'):
            # Debit Spreads: We bought ATM and sold OTM. We paid a Net Debit (Entry).
            # We want the spread value to INCREASE so we can sell it for a Net Credit (Exit).
            # Profit = Exit Premium - Entry Premium
            gross_pnl = (sim_exit_price - pos['sim_entry_price']) * pos['qty']
        elif pos['direction'] == "LONG":
            gross_pnl = (sim_exit_price - pos['sim_entry_price']) * pos['qty']
        else: # SHORT
            gross_pnl = (pos['sim_entry_price'] - sim_exit_price) * pos['qty']
            
        # Brokerage: ₹20 per order * 2 orders (Entry + Exit) = ₹40
        brokerage = 40.0 
        net_pnl = gross_pnl - brokerage
            
        self.balance += net_pnl
        
        # Determine symbol name for logging
        display_symbol = symbol 
        if pos.get('is_spread') and pos.get('sell_symbol'):
             sell_sym_short = pos['sell_symbol'].replace('NSE:', '')
             buy_sym_short = symbol.replace('NSE:', '')
             display_symbol = f"SPREAD: {buy_sym_short} / {sell_sym_short}"
             
        trade_data = {
            "id": pos['id'], "symbol": display_symbol, "status": "CLOSED",
            "direction": pos['direction'], "qty": pos['qty'],
            "entry_price": pos['sim_entry_price'], "exit_price": sim_exit_price,
            "entry_time": pos['entry_time'], "exit_time": exit_time,
            "stop_loss": pos['sim_stop_loss_price'], "take_profit": pos['sim_take_profit_price'],
            "pnl": net_pnl,
            "brokerage": brokerage
        }
        
        self.trade_log.append(trade_data)
        self._log_trade(trade_data)
        
        logger.info("--- POSITION CLOSED ---")
        logger.info(f"   Symbol: {symbol} | Qty: {pos['qty']} | Exit: ₹{sim_exit_price:,.2f}")
        logger.info(f"   P&L: ₹{net_pnl:,.2f} | New Balance: ₹{self.balance:,.2f}")
        
        self._save_positions()


    def check_positions_for_exit(self, symbol, current_high, current_low):
        """
        This is the new backtesting exit logic.
        It checks the INDEX high/low against the stored INDEX SL/TP levels.
        """
        if symbol not in self.positions:
            return
            
        pos = self.positions[symbol]

        if pos['direction'] == "LONG":
            # Check for STOP-LOSS hit
            if current_low <= pos['index_stop_loss_price']:
                self._close_position(symbol, "STOP-LOSS", pos['index_stop_loss_price'])
            # Check for TAKE-PROFIT hit
            elif pos['index_take_profit_price'] > 0 and current_high >= pos['index_take_profit_price']:
                self._close_position(symbol, "TAKE-PROFIT", pos['index_take_profit_price'])
                
        elif pos['direction'] == "SHORT":
            # Check for STOP-LOSS hit
            if current_high >= pos['index_stop_loss_price']:
                self._close_position(symbol, "STOP-LOSS", pos['index_stop_loss_price'])
            # Check for TAKE-PROFIT hit
            elif pos['index_take_profit_price'] > 0 and current_low <= pos['index_take_profit_price']:
                self._close_position(symbol, "TAKE-PROFIT", pos['index_take_profit_price'])

    def close_all_positions(self, reason="END_OF_DAY", current_prices=None):
        """
        Closes all open positions immediately.
        Used for EOD auto-square-off.
        current_prices: dict of {symbol: ltp} for exit prices.
                       If not provided, uses sim_entry_price (P&L = 0 minus brokerage).
        """
        open_symbols = list(self.positions.keys())
        if not open_symbols:
            logger.info("No positions to close.")
            return

        logger.info(f"--- {reason}: Closing {len(open_symbols)} positions ---")
        for symbol in open_symbols:
            pos = self.positions[symbol]
            ltp = 0
            
            if pos.get("is_spread"):
                buy_ltp = current_prices.get(symbol, 0) if current_prices else 0
                sell_sym = pos.get("sell_symbol")
                sell_ltp = current_prices.get(sell_sym, 0) if current_prices else 0
                
                if buy_ltp > 0 and sell_ltp > 0:
                    ltp = buy_ltp - sell_ltp
            else:
                if current_prices and symbol in current_prices:
                    ltp = current_prices[symbol]

            if ltp > 0:
                self._close_position(symbol, "MARKET_EXIT", ltp)
            else:
                # Fallback: close at entry price (net P&L = -brokerage only)
                self._close_position(symbol, "MARKET_EXIT", pos['sim_entry_price'])
                logger.warning(f"   No LTP available for {symbol}, closed at entry price.")
            
    def close_position_at_market(self, symbol, ltp):
        """Closes a specific position at the given market price (LTP)."""
        if symbol in self.positions:
             self._close_position(symbol, "MARKET_EXIT", ltp)


    def get_summary(self):
        logger.info("--- Trading Summary ---")
        logger.info(f"Initial Balance: Rs {self.initial_balance:,.2f}")
        logger.info(f"Final Balance:   Rs {self.balance:,.2f}")
        
        total_pnl = self.balance - self.initial_balance
        logger.info(f"Total P&L (Realized): Rs {total_pnl:,.2f}")
        
        used_margin = sum(p['sim_entry_price'] * p['qty'] for p in self.positions.values())
        available_balance = self.balance - used_margin
        
        logger.info(f"Used Margin:     Rs {used_margin:,.2f}")
        logger.info(f"Available Bal:   Rs {available_balance:,.2f}")
        
        if self.positions:
            logger.info(f"--- Active Positions: {len(self.positions)} ---")
            for sym, pos in self.positions.items():
                pnl_text = f" (Qty: {pos['qty']}) | Entry: {pos['sim_entry_price']:.2f}"
                logger.info(f"   OPEN: {sym}{pnl_text}")
        else:
            logger.info("--- No Active Positions ---")

        if not self.trade_log:
            logger.info("No closed trades yet.")
            return

        try:
            log_df = pd.DataFrame(self.trade_log)
            total_trades = len(log_df)
            wins = log_df[log_df['pnl'] > 0]
            losses = log_df[log_df['pnl'] <= 0]
            
            win_rate = (len(wins) / total_trades) * 100 if total_trades > 0 else 0
            
            total_profit = wins['pnl'].sum()
            total_loss = abs(losses['pnl'].sum())
            
            profit_factor = total_profit / total_loss if total_loss > 0 else "inf"
            avg_win = wins['pnl'].mean() if len(wins) > 0 else 0
            avg_loss = losses['pnl'].mean() if len(losses) > 0 else 0

            logger.info(f"Full trade log saved to {self.log_filename}")
            logger.info(f"Total Closed Trades: {total_trades}")
            logger.info(f"   > Profitable:     {len(wins)}")
            logger.info(f"   > Unprofitable:   {len(losses)}")
            logger.info(f"Win Rate:            {win_rate:.2f}%")
            logger.info(f"Profit Factor:       {profit_factor}")
            logger.info(f"Average Win:         ₹{avg_win:,.2f}")
            logger.info(f"Average Loss:        ₹{avg_loss:,.2f}")
        
        except Exception as e:
            logger.error(f"Error generating summary: {e}")

