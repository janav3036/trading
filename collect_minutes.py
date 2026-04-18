import pandas as pd
import yfinance as yf
from datetime import date, timedelta
from pathlib import Path
from config import WATCHLIST

DATA_DIR = Path("data_1m")
DATA_DIR.mkdir(exist_ok=True)

def retrieve_minutes(ticker: str) -> pd.DataFrame:
    cache_path = DATA_DIR / f"{ticker.replace('.', '_')}.parquet"
    existing_path = pd.read_parquet(cache_path) if cache_path.exists() else None
    print(f"Fetching data for {ticker}")

    df = yf.download(
        tickers = ticker,
        period = "7d",
        interval = "1m", 
        auto_adjust = True,
        progress = False
    )

    if df.empty:
        print(f"No data returned for {ticker}")
        return df
    
    df = df[["Open", "High", "Low", "Close", "Volume"]]
    df.columns = df.columns.get_level_values(0)
    df.index = pd.to_datetime(df.index)
    df.index = df.index.tz_convert("Asia/Kolkata")
    df.dropna(inplace=True)
    
    print(f"  Saved {len(df)} candles to {cache_path}")
    combined_df = pd.concat([existing_path, df]) if existing_path is not None else df
    combined = combined_df[~combined_df.index.duplicated(keep='last')]
    combined.sort_index(inplace=True)
    combined.to_parquet(cache_path)
    return combined

def fetch_all(force_refresh: bool = False) -> dict:
    if force_refresh:
        print("Force refresh — deleting existing cache files...")
        for f in DATA_DIR.glob("*.parquet"):
            f.unlink()
    data = {}
    for ticker in WATCHLIST:
        df = retrieve_minutes(ticker=ticker)
        if not df.empty:
            data[ticker] = df
    return data

if __name__=="__main__":
    all_data = fetch_all()
    print(type(all_data))
    print(all_data)