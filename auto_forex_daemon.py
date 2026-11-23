"""Standalone Headless Daemon for 24/5 Automated Forex Trading (Per User).
Runs in the background, continuously scanning live Forex markets for a specific user profile,
managing their positions, enforcing personal risk rules, and executing trades.
"""

import sys
import time
import signal
import argparse
from auto_trader import get_user_trader
from forex_parser import parse_forex_strategy
from user_manager import get_user_profile

def main():
    parser = argparse.ArgumentParser(description="AlphaForex Headless Daemon")
    parser.add_argument("--user", type=str, default="default_trader", help="User profile ID")
    parser.add_argument("--strategy", type=str, default=None, help="Plain English trading strategy prompt")
    parser.add_argument("--interval", type=int, default=10, help="Polling interval in seconds")
    args = parser.parse_args()

    user_id = args.user
    profile = get_user_profile(user_id)
    trader = get_user_trader(user_id)
    trader.polling_interval_sec = args.interval

    if args.strategy:
        spec = parse_forex_strategy(args.strategy)
        trader.set_strategy(spec)

    print("=======================================================")
    print(f"🤖 ALPHA FOREX DAEMON: USER [{profile['display_name']} ({user_id})]")
    print("=======================================================")
    print(f"Account Balance: ${trader.balance:,.2f}")
    print(f"Max Lot Limit:   {profile.get('risk_limits', {}).get('max_lot_size', 0.5)} lots")
    print(f"Active Strategy: {trader.strategy.name if trader.strategy else 'Default'}")
    print(f"Scan Interval:   {args.interval}s")
    print("Press Ctrl+C to stop.\n")

    def sig_handler(sig, frame):
        print(f"\nStopping autonomous trader safely for user {user_id}...")
        trader.stop()
        sys.exit(0)

    signal.signal(signal.SIGINT, sig_handler)
    trader.start()

    while True:
        try:
            summary = trader.get_summary()
            pos = summary["open_position"]
            pos_str = "FLAT (No Position)"
            if pos:
                pips = pos.get("floating_pips", 0.0)
                pnl = pos.get("floating_pnl", 0.0)
                sign = "+" if pnl >= 0 else ""
                pos_str = f"{pos['direction']} {pos['lot_size']}L {pos['pair']} @ {pos['entry_price']} | Floating: {pips:+.1f} pips ({sign}${pnl:.2f})"

            print(f"[{time.strftime('%H:%M:%S')}] [{user_id}] Balance: ${summary['balance']:,.2f} | Equity: ${summary['equity']:,.2f} | Pos: {pos_str}")
            time.sleep(args.interval)
        except KeyboardInterrupt:
            break

    trader.stop()
    print("Daemon stopped.")

if __name__ == "__main__":
    main()
