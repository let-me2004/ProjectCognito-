import fyers_client
import logger_setup
import logging
import time
import datetime
import equity_scanner
from sector_mapper import SectorMapper
import technical_analyzer
import llm_handler
import risk_manager
from paper_trader import PaperAccount
import config
import news_handler

logger = logger_setup.setup_logger()

# --- Configuration ---
RISK_PERCENTAGE = 1.0
STOP_LOSS_ATR_MULTIPLIER = 1.5
MAX_OPEN_POSITIONS = 5
CYCLE_WAIT_TIME_SECONDS = 30 # 5-minute cycle
# --------------------

def run_equity_agent_cycle(fyers, paper_account, sector_mapper, volume_cache):
    logger.info("--- New Equity Agent Cycle Started ---")

    # --- Step 0: Manage Open Positions ---
    logger.info("[Step 0] Managing open positions...")
    
    # EOD Auto-Square-Off Logic
    current_time = datetime.datetime.now().time()
    if current_time >= datetime.time(15, 00):
        logger.warning(f"It is {current_time.strftime('%H:%M')}. Initiating EOD Auto-Square-Off (30 mins before close).")
        
        # 1. Fetch latest prices for all open positions
        open_symbols = list(paper_account.positions.keys())
        if open_symbols:
            try:
                quotes = fyers.quotes(data={"symbols": ",".join(open_symbols)})
                if quotes.get('s') == 'ok':
                    for quote in quotes['d']:
                        symbol = quote['n']
                        ltp = quote['v'].get('lp')
                        if ltp:
                            # Close specific position at market
                            paper_account.close_position_at_market(symbol, ltp)
            except Exception as e:
                logger.error(f"Error during EOD Square-Off: {e}")
                
        # 2. Add final logging and exit
        logger.info("--- EOD Square-Off Complete. Exiting Equity Agent. ---")
        paper_account.get_summary()
        exit(0)

    # Check for exits on open positions
    open_positions = list(paper_account.positions.keys())
    if open_positions:
        try:
            quotes = fyers.quotes(data={"symbols": ",".join(open_positions)})
            if quotes.get('s') == 'ok':
                for quote in quotes['d']:
                    symbol = quote['n']
                    ltp = quote['v'].get('lp')
                    if ltp:
                        paper_account.check_positions_for_exit(symbol, ltp, ltp)
        except Exception as e:
            logger.error(f"Error managing open positions: {e}")
            
    paper_account.get_summary()

    # --- Step 1: High-Speed Quantitative Scanner ---
    logger.info("[Step 1] Running quantitative scanner...")
    # THIS IS THE FIX: We now call the correct function and pass the volume cache.
    surge_stocks = equity_scanner.scan_for_surges(fyers, volume_cache)

    if not surge_stocks:
        # This is now handled inside the scanner, but we keep this log for clarity.
        logger.info("Scanner did not identify any top candidates in this cycle.")
        return

    confirmed_candidates = []

    # --- Step 2: Qualitative Filters ---
    logger.info(f"[Step 2] Applying Sector and Sentiment filters to {len(surge_stocks)} top candidate(s)...")
    for stock in surge_stocks:
        symbol = stock['symbol']
        
        # --- Sector Confluence Filter ---
        sector = sector_mapper.get_sector_for_stock(symbol)
        if not sector:
            logger.warning(f"   ...No sector mapping found for {symbol}. Skipping.")
            continue
            
        sector_symbol = sector_mapper.get_fyers_sector_symbol(sector)
        if not sector_symbol:
             logger.warning(f"   ...No Fyers symbol mapped for sector '{sector}'. Skipping.")
             continue

        logger.info(f"   ...Checking sector trend for {symbol} (Sector: {sector} -> {sector_symbol})")
        sector_regime = technical_analyzer.get_market_regime(fyers, sector_symbol)
        
        if sector_regime != "Bullish":
            logger.info(f"   ---> REJECTED: {symbol} failed sector check. Sector regime is '{sector_regime}'.")
            continue
        
        logger.info(f"   ...Sector check PASSED for {symbol}.")

        # --- AI Sentiment Filter ---
        logger.info(f"   ...Analyzing news for {symbol}...")
        headlines = news_handler.get_latest_headlines(symbol, count=3)
        headlines_str = " | ".join(headlines) if headlines else "No specific news found."
        tech_summary_for_llm = f"Analyzing news for {symbol} which is showing strong price and volume surge."
        
        analysis = llm_handler.get_market_analysis(tech_summary_for_llm, headlines_str)
        
        if analysis and "Bullish" in analysis.get('outlook', 'Neutral'):
            logger.info(f"   ---> CONFIRMED: {symbol} passed qualitative filter with '{analysis.get('outlook')}' outlook.")
            confirmed_candidates.append(stock)
        else:
            outlook = analysis.get('outlook', 'Neutral') if analysis else 'None'
            logger.info(f"   ---> REJECTED: {symbol} failed sentiment check. AI outlook was '{outlook}'.")

    # --- Step 3: Execution ---
    logger.info("[Step 3] Executing trades for confirmed candidates...")
    if not confirmed_candidates:
        logger.info("No candidates passed all filters. Standing down.")
        return

    for candidate in confirmed_candidates:
        if len(paper_account.positions) >= MAX_OPEN_POSITIONS:
            logger.warning("Max open positions reached. Halting further trade execution in this cycle.")
            break
            
        symbol = candidate['symbol']
        ltp = candidate['ltp']

        logger.info(f"   ...Initiating trade for {symbol}.")
        
        # Calculate Stop Loss using ATR
        atr_stop_loss = technical_analyzer.get_atr_stop_loss(fyers, symbol, STOP_LOSS_ATR_MULTIPLIER)
        if not atr_stop_loss:
            logger.error(f"Could not calculate ATR stop loss for {symbol}. Aborting trade.")
            continue

        stop_loss_price = ltp - atr_stop_loss

        # Calculate position size
        trade_details = risk_manager.calculate_equity_trade(
            account_balance=paper_account.balance,
            risk_percentage=RISK_PERCENTAGE,
            entry_price=ltp,
            stop_loss_price=stop_loss_price
        )

        if trade_details['is_trade_valid']:
            logger.info(f"   ...Executing BUY order for {trade_details['position_size']} shares of {symbol} @ {ltp:.2f}")
            # NOTE: Take Profit is not defined in this strategy yet. Setting to 0.
            # The 'stop_loss_price' argument for execute_buy is the price, not points.
            paper_account.execute_buy(
                symbol, 
                trade_details['position_size'], 
                ltp,                # Sim Entry
                stop_loss_price,    # Sim SL
                0,                  # Sim TP
                ltp,                # Index Entry (Same for Equity)
                stop_loss_price,    # Index SL (Same for Equity)
                0                   # Index TP
            )
        else:
            logger.error(f"Trade for {symbol} REJECTED by Risk Manager: {trade_details.get('reason')}")


if __name__ == '__main__':
    fyers = fyers_client.get_fyers_model()
    
    if fyers:
        paper_account = PaperAccount(initial_balance=config.ACCOUNT_BALANCE, filename="paper_positions_equity.json")
        try:
            sector_mapper = SectorMapper()
            # THIS IS THE FIX: Load or create the volume cache at startup.
            volume_cache = equity_scanner.get_volume_cache(fyers)
        except Exception as e:
            print(f"FATAL ERROR during initialization: {e}")
            sector_mapper = None
            volume_cache = None

        if sector_mapper and volume_cache:
            logger.info("--- Initialization Complete. Entering Main Operational Loop ---")
            while True:
                try:
                    # Hot-reload: pick up positions added/removed via web dashboard
                    paper_account.sync_positions()
                    # Pass the volume_cache into the main cycle function
                    run_equity_agent_cycle(fyers, paper_account, sector_mapper, volume_cache)
                    
                    logger.info(f"Cycle complete. Waiting for {CYCLE_WAIT_TIME_SECONDS} seconds...")
                    time.sleep(CYCLE_WAIT_TIME_SECONDS)
                except KeyboardInterrupt:
                    logger.info(">>> Shutdown signal received. Exiting main loop. <<<")
                    break
                except Exception as e:
                    logger.error("An uncaught error occurred in the main loop!", exc_info=True)
                    time.sleep(60) # Wait a minute before retrying
    else:
        logger.critical("Authentication failed. Halting agent.")

    logger.info("====== Equity Surge Agent Shut Down ======")

