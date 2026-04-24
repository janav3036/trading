import pandas as pd
import numpy as np
from shared.config import WATCHLIST, CAPITAL_PER_TRADE
from mean_reversion.strategy import get_signal
from mean_reversion.backtester import backtest

def run():
    nifty_df = pd.read_parquet("data/1m/nifty_spot_1min.parquet")
    all_trades=[]
    for stock in WATCHLIST:
        stock_s = stock.split(".")[0]
        stock_df = pd.read_parquet(f"data/1m/{stock_s}_spot_1min.parquet")
        signals_df = get_signal(stock_df, nifty_df)
        trades_df = backtest(signals_df)
        trades_df['ticker'] = stock
        all_trades.append(trades_df)

    results = pd.concat(all_trades)
    results['pnl']= np.where(results['direction'] == "LONG", results['exit'] - results['entry'], results['entry'] - results['exit'] )
    results['quantity'] = (CAPITAL_PER_TRADE / results['entry']).astype(int)
    results['pnl_rs'] = results['pnl'] * results['quantity']
    results['pnl_rs_net'] = results['pnl_rs'] - 40  # ₹40 brokerage per trade


    print(f"Total trades: {len(results)}")
    print(f"Win rate: {(results['reason'] == 'TARGET').mean():.1%}")
    print(f"Target hits: {(results['reason'] == 'TARGET').sum()}")
    print(f"Stop hits: {(results['reason'] == 'STOP').sum()}")
    print(f"Time exits: {(results['reason'] == 'TIME').sum()}")

    print(f"\nCost-adjusted P&L:")
    print(f"Gross P&L: ₹{results['pnl_rs'].sum():,.0f}")
    print(f"Net P&L: ₹{results['pnl_rs_net'].sum():,.0f}")
    print(f"Avg net P&L per trade: ₹{results['pnl_rs_net'].mean():,.0f}")
    print(results.groupby('ticker')['pnl_rs_net'].sum())

    print(results.groupby('ticker')['pnl'].agg(['sum', 'mean', 'count']))
    print(results.groupby(['ticker', 'direction'])['pnl'].agg(['sum', 'count']))
     
if __name__ == "__main__":
    run()