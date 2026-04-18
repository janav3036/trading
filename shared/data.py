import yfinance as yf
import pandas as pd
from pathlib import Path
from shared.config import WATCHLIST, BACKTEST_START, BACKTEST_END

DATA_DIR = Path(__file__).parent.parent/"data"
DATA_DIR.mkdir(exist_ok=True)

def fetch_historical(ticker: str, interval: str="1h") -> pd.DataFrame: #for 1 singular ticker
    cache_path = DATA_DIR / f"{ticker.replace('.', '_')}.parquet"
    if cache_path.exists():
        print(f"Loading {ticker} from cache...")
        df = pd.read_parquet(cache_path)
        return df


    print(f"Fetching data for {ticker}")

    df = yf.download(
        tickers = ticker,
        start = BACKTEST_START,
        end = BACKTEST_END,
        interval = interval, #1hr since 1 min only available for past 7 days data
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
    
    df.to_parquet(cache_path)
    print(f"  Saved {len(df)} candles to {cache_path}")
    return df

def fetch_nifty(interval: str = "1h") -> pd.DataFrame: #for NIFTY
    ticker = "^NSEI"  # Nifty 50 ticker
    cache_path = DATA_DIR / f"{ticker.replace('^', '')}.parquet"
    if cache_path.exists():
        print(f"Loading {ticker} from cache...")
        df = pd.read_parquet(cache_path)
        return df


    print(f"Fetching data for {ticker}")

    df = yf.download(
        tickers = ticker,
        start = BACKTEST_START,
        end = BACKTEST_END,
        interval = interval, #1hr since 1 min only available for past 7 days data
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
    
    df.to_parquet(cache_path)
    print(f"  Saved {len(df)} candles to {cache_path}")
    return df

def fetch_all(interval: str = "1h", force_refresh: bool = False) -> dict:
    if force_refresh:
        print("Force refresh — deleting existing cache files...")
        for f in DATA_DIR.glob("*.parquet"):
            f.unlink()
    data = {}
    for ticker in WATCHLIST:
        df = fetch_historical(ticker=ticker, interval=interval)
        if not df.empty:
            data[ticker] = df
    nifty_df = fetch_nifty(interval=interval)
    if not nifty_df.empty:
        data["NIFTY"] = nifty_df
    return data
    
if __name__=="__main__":
    all_data = fetch_all()
    print(type(all_data))
    print(all_data)