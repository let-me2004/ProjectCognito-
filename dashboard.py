# dashboard.py - Position Dashboard + Manual Trading CLI
# ======================================================
# Run: python dashboard.py
# Shows all open positions across agents & allows manual buy/sell.

import json
import os
import datetime
import sys

POSITION_FILES = {
    "Options Agent": "paper_positions_options.json",
    "Scalper Agent": "paper_positions_scalper.json",
    "Equity Agent": "paper_positions_equity.json",
}

COLORS = {
    "green": "\033[92m",
    "red": "\033[91m",
    "yellow": "\033[93m",
    "cyan": "\033[96m",
    "bold": "\033[1m",
    "reset": "\033[0m",
}


def c(text, color):
    return f"{COLORS.get(color, '')}{text}{COLORS['reset']}"


def load_positions(filename):
    if not os.path.exists(filename):
        return {}
    try:
        with open(filename, "r") as f:
            return json.load(f)
    except Exception:
        return {}


def save_positions(filename, positions):
    serializable = {}
    for sym, pos in positions.items():
        serializable[sym] = pos
    with open(filename, "w") as f:
        json.dump(serializable, f, indent=4)


def show_positions():
    print(f"\n{c('=' * 70, 'cyan')}")
    print(f"{c('  POSITION DASHBOARD', 'bold')}  |  {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{c('=' * 70, 'cyan')}")

    total_positions = 0
    all_positions = {}

    for agent_name, filename in POSITION_FILES.items():
        positions = load_positions(filename)
        count = len(positions)
        total_positions += count

        if count == 0:
            print(f"\n  {c(agent_name, 'yellow')}: {c('No open positions', 'green')}")
            continue

        print(f"\n  {c(agent_name, 'yellow')} ({filename}):")
        print(f"  {'Symbol':<35} {'Qty':>5} {'Entry':>10} {'SL(Idx)':>10} {'TP(Idx)':>10} {'Since'}")
        print(f"  {'-'*90}")

        for sym, pos in positions.items():
            qty = pos.get('qty', 0)
            entry = pos.get('sim_entry_price', 0)
            idx_sl = pos.get('index_stop_loss_price', 0)
            idx_tp = pos.get('index_take_profit_price', 0)
            entry_time = pos.get('entry_time', 'unknown')
            if isinstance(entry_time, str) and len(entry_time) > 16:
                entry_time = entry_time[:16]

            print(f"  {sym:<35} {qty:>5} {entry:>10.2f} {idx_sl:>10.2f} {idx_tp:>10.2f} {entry_time}")
            all_positions[sym] = (filename, pos)

    print(f"\n  {c(f'Total Open Positions: {total_positions}', 'bold')}")
    print(f"{c('=' * 70, 'cyan')}")
    return all_positions


def manual_sell(all_positions):
    print(f"\n{c('  MANUAL SELL', 'red')}")
    if not all_positions:
        print("  No positions to sell.")
        return

    symbols = list(all_positions.keys())
    for i, sym in enumerate(symbols, 1):
        print(f"    {i}. {sym}")
    print(f"    0. Cancel")

    try:
        choice = input(f"\n  Enter number to sell (0 to cancel): ").strip()
        if choice == "0" or not choice:
            print("  Cancelled.")
            return

        idx = int(choice) - 1
        if idx < 0 or idx >= len(symbols):
            print("  Invalid choice.")
            return

        sym = symbols[idx]
        filename, pos = all_positions[sym]
        exit_price = input(f"  Exit price for {sym} (or 'market' for current): ").strip()

        # Load current file, remove the position, save
        positions = load_positions(filename)
        if sym in positions:
            qty = positions[sym].get('qty', 0)
            entry = positions[sym].get('sim_entry_price', 0)

            if exit_price.lower() == 'market' or exit_price == '':
                exit_p = entry  # Placeholder
                print(f"  {c('NOTE:', 'yellow')} Using entry price as placeholder. Real P&L needs live LTP.")
            else:
                exit_p = float(exit_price)

            pnl = (exit_p - entry) * qty
            del positions[sym]
            save_positions(filename, positions)
            print(f"\n  {c('SOLD', 'red')} {sym}")
            print(f"    Qty: {qty} | Entry: {entry:.2f} | Exit: {exit_p:.2f} | P&L: Rs {pnl:,.2f}")
        else:
            print(f"  Position {sym} not found in file.")

    except (ValueError, IndexError):
        print("  Invalid input.")


def manual_buy():
    print(f"\n{c('  MANUAL BUY', 'green')}")
    print("  Which agent file?")
    files = list(POSITION_FILES.items())
    for i, (name, fname) in enumerate(files, 1):
        print(f"    {i}. {name} ({fname})")
    print(f"    0. Cancel")

    try:
        choice = int(input("  Enter choice: ").strip())
        if choice == 0:
            print("  Cancelled.")
            return
        agent_name, filename = files[choice - 1]
    except (ValueError, IndexError):
        print("  Invalid choice.")
        return

    symbol = input("  Symbol (e.g. NSE:NIFTY26FEB25800CE): ").strip()
    if not symbol:
        print("  Cancelled.")
        return

    try:
        qty = int(input("  Quantity (e.g. 75): ").strip())
        entry_price = float(input("  Entry price: ").strip())
        sl = float(input("  Stop Loss price: ").strip())
        tp = float(input("  Take Profit price: ").strip())
    except ValueError:
        print("  Invalid numbers.")
        return

    positions = load_positions(filename)
    positions[symbol] = {
        "id": int(datetime.datetime.now().timestamp()),
        "qty": qty,
        "direction": "LONG",
        "entry_time": datetime.datetime.now().isoformat(),
        "sim_entry_price": entry_price,
        "sim_stop_loss_price": sl,
        "sim_take_profit_price": tp,
        "index_entry_price": entry_price,
        "index_stop_loss_price": sl,
        "index_take_profit_price": tp,
    }
    save_positions(filename, positions)
    print(f"\n  {c('BOUGHT', 'green')} {symbol} x {qty} @ Rs {entry_price:.2f}")
    print(f"  Saved to {filename}")


def clear_all():
    print(f"\n{c('  CLEAR ALL POSITIONS', 'red')}")
    confirm = input("  Are you sure? Type 'YES' to confirm: ").strip()
    if confirm == "YES":
        for agent_name, filename in POSITION_FILES.items():
            if os.path.exists(filename):
                save_positions(filename, {})
                print(f"  Cleared {filename}")
        print(f"  {c('All positions cleared.', 'green')}")
    else:
        print("  Cancelled.")


def main():
    while True:
        all_pos = show_positions()

        print(f"\n  {c('Actions:', 'bold')}")
        print("    1. Refresh positions")
        print("    2. Manual SELL (close a position)")
        print("    3. Manual BUY (open a position)")
        print("    4. Clear ALL positions")
        print("    5. Exit")

        try:
            choice = input(f"\n  {c('>', 'cyan')} ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\n  Goodbye!")
            break

        if choice == "1":
            continue
        elif choice == "2":
            manual_sell(all_pos)
        elif choice == "3":
            manual_buy()
        elif choice == "4":
            clear_all()
        elif choice == "5":
            print("  Goodbye!")
            break
        else:
            print("  Invalid choice.")


if __name__ == "__main__":
    main()