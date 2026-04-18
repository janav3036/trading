import pandas as pd
import numpy as np
from shared.config import CAPITAL_PER_TRADE, BROKERAGE_PER_ORDER, STT_RATE, EXCHANGE_RATE, SEBI_RATE, STAMP_RATE, GST_RATE
from shared.data import fetch_all
from orb.strategy import run_strategy
from orb.config import TIME_EXIT_HOUR
from pathlib import Path

OUTPUT_DIR = Path(__file__).parent / "outputs"
OUTPUT_DIR.mkdir(exist_ok=True)

def calculate_costs(entry_price:float, exit_price:float, shares:float, signal:str) -> float:
    buy_value = entry_price*shares if signal=="BUY" else exit_price*shares
    sell_value = exit_price*shares if signal=="BUY" else entry_price*shares

    total_turnover = buy_value+sell_value

    brokerage = BROKERAGE_PER_ORDER*2
    stt = sell_value*STT_RATE
    exchange = total_turnover*EXCHANGE_RATE
    sebi = total_turnover*SEBI_RATE
    stamp = STAMP_RATE*buy_value
    gst = GST_RATE*(brokerage+exchange+sebi)

    return brokerage+stt+exchange+sebi+stamp+gst

def simulate_trade(signal_row:pd.Series, day_data:pd.DataFrame, time_exit_hour: int = TIME_EXIT_HOUR) -> dict:
    signal = signal_row['signal']
    entry = signal_row['entry']
    stop = signal_row['stop_loss']
    target = signal_row['target']

    shares = CAPITAL_PER_TRADE/entry

    post_orb = day_data.sort_index().iloc[1:]
    exit_price = None
    exit_reason = None

    for ts, candle in post_orb.iterrows():
        high = candle['High']
        low = candle['Low']

        if signal=='BUY':
            target_hit = high>=target
            stop_hit = low<=stop
        else:
            target_hit = low<=target
            stop_hit = high>=stop
        
        if stop_hit:
            exit_price=stop
            exit_reason="STOP"
            break
        if target_hit:
            exit_price=target
            exit_reason="TARGET"
            break

        if ts.hour>=time_exit_hour:
            exit_price = candle["Close"]
            exit_reason = "TIME"
            break
    
    if exit_price is None:
        exit_price = post_orb.iloc[-1]["Close"]
        exit_reason="EOD"

    if signal=="BUY":
        g_pnl = (exit_price-entry)*shares
    else:
        g_pnl = (entry-exit_price)*shares

    costs = calculate_costs(entry, exit_price, shares, signal)
    n_pnl = g_pnl - costs

    return {
        "exit_price": round(exit_price,2),
        "exit_reason": exit_reason,
        "shares": round(shares, 4),
        "gross_pnl": round(g_pnl,2),
        "costs": round(costs,2),
        "net_pnl": round(n_pnl,2),
        "win": n_pnl>0
    }

def run_backtest(signals: pd.DataFrame, data: dict,
                 time_exit_hour: int = TIME_EXIT_HOUR) -> pd.DataFrame:
    results = []
 
    for _, row in signals.iterrows():
        if row["signal"] == "NONE":
            continue
 
        ticker   = row["ticker"]
        date     = row["date"]
        df       = data[ticker].copy()
        df["date"] = df.index.date
        day_data = df[df["date"] == date]
 
        if len(day_data) < 2:
            continue
 
        trade = simulate_trade(row, day_data, time_exit_hour=time_exit_hour)
        results.append({
            "date"       : date,
            "ticker"     : ticker,
            "signal"     : row["signal"],
            "entry"      : row["entry"],
            "stop_loss"  : row["stop_loss"],
            "target"     : row["target"],
            "range_size" : row["range_size"],
            **trade
        })
 
    return pd.DataFrame(results).sort_values(["date", "ticker"]).reset_index(drop=True)
 
 
def performance_report(trades: pd.DataFrame, label: str = "") -> None:
    if trades.empty:
        print("No trades to analyse.")
        return
 
    total    = len(trades)
    winners  = trades[trades["win"] == True]
    losers   = trades[trades["win"] == False]
    win_rate = len(winners) / total * 100
 
    total_gross = trades["gross_pnl"].sum()
    total_costs = trades["costs"].sum()
    total_net   = trades["net_pnl"].sum()
    avg_win     = winners["net_pnl"].mean() if len(winners) else 0
    avg_loss    = losers["net_pnl"].mean()  if len(losers)  else 0
 
    pf_denom     = abs(losers["net_pnl"].sum())
    profit_factor = (winners["net_pnl"].sum() / pf_denom
                     if pf_denom > 0 else float("inf"))
    expectancy   = trades["net_pnl"].mean()
 
    equity       = trades.sort_values("date")["net_pnl"].cumsum()
    max_drawdown = (equity - equity.cummax()).min()
 
    daily_pnl    = trades.groupby("date")["net_pnl"].sum()
    sharpe       = ((daily_pnl.mean() / daily_pnl.std()) * np.sqrt(252)
                    if daily_pnl.std() > 0 else float("nan"))
 
    exit_counts  = trades["exit_reason"].value_counts()
 
    header = f"  TIME EXIT: {label}" if label else "  BACKTEST PERFORMANCE REPORT"
    print("=" * 55)
    print(header)
    print("=" * 55)
    print(f"  Total trades          : {total}")
    print(f"  Winners               : {len(winners)}  ({win_rate:.1f}%)")
    print(f"  Losers                : {len(losers)}")
    print()
    print(f"  Gross P&L             : ₹{total_gross:>10.2f}")
    print(f"  Total costs           : ₹{total_costs:>10.2f}")
    print(f"  Net P&L               : ₹{total_net:>10.2f}")
    print()
    print(f"  Avg winning trade     : ₹{avg_win:>10.2f}")
    print(f"  Avg losing trade      : ₹{avg_loss:>10.2f}")
    print(f"  Profit factor         : {profit_factor:>10.2f}")
    print(f"  Expectancy/trade      : ₹{expectancy:>10.2f}")
    print()
    print(f"  Max drawdown          : ₹{max_drawdown:>10.2f}")
    print(f"  Sharpe ratio (ann.)   : {sharpe:>10.2f}")
    print()
    print("  Exit reasons:")
    for reason, count in exit_counts.items():
        print(f"    {reason:<10} : {count}")
    print("=" * 55)
    print()
 
 
if __name__ == "__main__":
    print("Fetching data...")
    data = fetch_all(interval="1h")
 
    print("Running strategy...")
    signals = run_strategy(data)
 
    print("Running backtest with time exit sweep...\n")
 
    cutoffs = {
        "12:15 IST (3 post-ORB candles)": 12,
        "13:15 IST (4 post-ORB candles)": 13,
        "14:15 IST (5 post-ORB candles)": 14,
    }
 
    best_trades = None
    best_label  = None
    best_net    = -float("inf")
 
    for label, hour in cutoffs.items():
        trades = run_backtest(signals, data, time_exit_hour=hour)
        performance_report(trades, label=label)
 
        net = trades["net_pnl"].sum()
        if net > best_net:
            best_net    = net
            best_trades = trades
            best_label  = label
    # ─────────────────────────────────────────────────────────────────────────
 
    print(f"\n  Best cutoff: {best_label}  (Net P&L: ₹{best_net:.2f})")
    best_trades.to_csv(OUTPUT_DIR/"backtest_trades.csv", index=False)
    print("  Full trade log saved to backtest_trades.csv")
 
