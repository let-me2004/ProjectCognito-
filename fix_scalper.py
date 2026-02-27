import sys

with open('c:/dev/ProjectCognito/options_scalper_main.py', 'r', encoding='utf-8') as f:
    code = f.read()

# Fix 1: The order_response check KeyError bug
old_check = 'if order_response["status"] == "success":'
new_check = 'if order_response.get("s") == "ok" or order_response.get("status") == "success":'
code = code.replace(old_check, new_check)

# Fix 2: Move the throttle block
old_throttle = '''            # --- SLOW LOOP: Scan for new trades and print summaries ---
            current_time = time.time()
            if current_time - last_analysis_time < ANALYSIS_INTERVAL:
                continue
            
            last_analysis_time = current_time
            now = datetime.datetime.now().time()'''

new_throttle = '''            # --- SLOW LOOP: Summary printing and Auto Square-Off ---
            now = datetime.datetime.now().time()
            current_time = time.time()
            if current_time - last_analysis_time >= ANALYSIS_INTERVAL:
                last_analysis_time = current_time'''

code = code.replace(old_throttle, new_throttle)

code = code.replace('            paper_account.sync_positions()', '                paper_account.sync_positions()')
code = code.replace('            logger.info("=" * 50)', '                logger.info("=" * 50)')
code = code.replace('            logger.info(f"[{now.strftime(', '                logger.info(f"[{now.strftime(')

# EOD Block
eod_start = '            # --- EOD Auto-Square-Off ---'
eod_end = '                exit(0)\n'
idx1 = code.find(eod_start)
idx2 = code.find(eod_end, idx1) + len(eod_end)
eod_block = code[idx1:idx2]
new_eod_block = eod_block.replace('\\n            ', '\\n                ')
code = code.replace(eod_block, new_eod_block)

# Fix the 'Max positions reached' spam
max_pos_spam = '''            if len(paper_account.positions) >= MAX_OPEN_POSITIONS:
                logger.info("Max positions reached. Monitoring only.")
                paper_account.get_summary()
                continue'''
new_max_pos = '''            if len(paper_account.positions) >= MAX_OPEN_POSITIONS:
                continue'''
code = code.replace(max_pos_spam, new_max_pos)

# Fix the time logic spam
time_logic = '''            # Only scan during trading window
            if now < orb_scalper_strategy.TRADING_START:
                logger.info(f"Waiting for ORB trading window to open at {orb_scalper_strategy.TRADING_START}")
                continue
            if now > orb_scalper_strategy.TRADING_END:
                logger.info(f"ORB trading window closed at {orb_scalper_strategy.TRADING_END}")
                continue'''
new_time_logic = '''            # Only scan during trading window
            if now < orb_scalper_strategy.TRADING_START:
                continue
            if now > orb_scalper_strategy.TRADING_END:
                continue'''
code = code.replace(time_logic, new_time_logic)

with open('c:/dev/ProjectCognito/options_scalper_main.py', 'w', encoding='utf-8') as f:
    f.write(code)
    
print("Successfully patched options_scalper_main.py!")
