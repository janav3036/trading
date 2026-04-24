import pandas as pd

stocks = ['RELIANCE', 'INFY', 'TCS', 'HDFCBANK', 'ICICIBANK']

# Check each stock
for stock in stocks:
    df = pd.read_parquet(f'data/1m/{stock}_spot_1min.parquet')
    print(f"\n{stock}: {len(df):,} rows | {df.index.min()} → {df.index.max()} | cols: {df.columns.tolist()}")

# Check nifty
nifty = pd.read_parquet('data/1m/nifty_spot_1min.parquet')
nifty_market = nifty.between_time('09:15', '15:30')
print(f"\nNIFTY (raw): {len(nifty):,} rows | {nifty.index.min()} → {nifty.index.max()}")
print(f"NIFTY (market hours): {len(nifty_market):,} rows")
print(f"Cols: {nifty.columns.tolist()}")