import pandas as pd
import numpy as np
from pathlib import Path
from shared.config import WATCHLIST

TICKER_ENCODING = {ticker:i for i,ticker in enumerate(WATCHLIST)}

OUTPUT_DIR = Path(__file__).parent / "outputs"
OUTPUT_DIR.mkdir(exist_ok=True)
SIGNAL_ENCODING = {
    "BUY": 1,
    "SELL": 0
}

def _safe_divide(num:float, denom: float, fallback:float = 0) -> float:
    if denom == 0 or np.isnan(denom):
        return fallback
    return num/denom

def build_feature(signal_row: pd.Series, day_data: pd.DataFrame, ticker_avg_volume: float, nifty_data: pd.DataFrame) -> dict:
    day_data = day_data.sort_index()
    if len(day_data)<2:
        return None
    
    orb=day_data.iloc[0]
    entry = signal_row['entry']

    if entry is None or entry == 0:
        return None
    
    range_size_pct = _safe_divide(signal_row['range_size'], entry)*100 #to normalize the range size to ticker, so model doesnt think some tickers have a bigger range just because of their prices

    #to see how much of the orb candle's full range was the body, to determine conviction or indecision
    # nearer to 1 -> strong conviction, nearer to 0 -> indecision and rejection
    orb_full_body = orb['High'] - orb['Low']
    orb_body = abs(orb['Open'] - orb['Close'])
    orb_body_ratio = _safe_divide(orb_body, orb_full_body)

    # A large upper wick on a BUY signal = sellers rejected higher prices during
    # the ORB = warning sign that the bullish breakout may not hold.
    orb_upper_wick = orb['High'] - max(orb['Open'],orb['Close'])
    orb_lower_wick = min(orb['Open'], orb['Close']) - orb['Low']
    orb_upper_wick_ratio = _safe_divide(orb_upper_wick, orb_full_body)
    orb_lower_wick_ratio = _safe_divide(orb_lower_wick, orb_full_body)

    # How much did the stock gap at open vs the previous day's close?
    # We use the ORB candle's open as today's open.
    # Positive = gap up, negative = gap down.
    # Large gaps often mean the easy money has already been made before
    # the market opened — the stock may reverse during the ORB window.
    if len(day_data.index) > 0:
        today_open = orb["Open"]
        # Previous close = last close of data before today's date
        date = day_data.index[0].date()
        # This is passed in pre-computed below in build_feature_matrix()
        # Placeholder — will be filled by build_feature_matrix
        gap_pct = 0.0   # overwritten in build_feature_matrix
    else:
        gap_pct = 0.0

    orb_volume = orb['Volume'] #more volume -> more participants

    volume_ratio = _safe_divide(orb_volume, ticker_avg_volume) #to normalize volume across tickers. A value of 2 means twice normal activity -> unusual, potentially useful

    day_of_week = day_data.index[0].dayofweek #Mon - 0, Fri - 4

    signal_encoded = SIGNAL_ENCODING.get(signal_row['signal'], -1)
    ticker_encoded =TICKER_ENCODING.get(signal_row['ticker'], -1)

    nifty_data = nifty_data.sort_index()
    if len(nifty_data)<2:
        return None
    
    nifty_orb=nifty_data.iloc[0]
    nifty_orb_return = (nifty_orb['Close'] - nifty_orb['Open'])/nifty_orb['Open']*100
    nifty_orb_range = (nifty_orb['High'] - nifty_orb['Low'])/nifty_orb['Open']*100
    

    return {
        "range_size_pct"      : round(range_size_pct, 4),
        "orb_body_ratio"      : round(orb_body_ratio, 4),
        "orb_upper_wick_ratio": round(orb_upper_wick_ratio, 4),
        "orb_lower_wick_ratio": round(orb_lower_wick_ratio, 4),
        "gap_pct"             : round(gap_pct, 4),   # filled by build_feature_matrix
        "orb_volume"          : float(orb_volume),
        "volume_ratio"        : round(volume_ratio, 4),
        "day_of_week"         : int(day_of_week),
        "signal_encoded"      : int(signal_encoded),
        "ticker_encoded"      : int(ticker_encoded),
        "nifty_orb_return"    : round(nifty_orb_return, 4),
        "nifty_orb_range"     : round(nifty_orb_range, 4),
    }

def build_feature_matrix(signals: pd.DataFrame, trades: pd.DataFrame, data:dict) -> pd.DataFrame:
    # join signals -> trades -> raw candle data to produce one feature vector per trade, then add the exit reason for supervised learning

    avg_volumes = {
        ticker: df['Volume'].replace(0, np.nan).mean() for ticker, df in data.items()
    }


    prev_closes = {}
    for ticker, df in data.items():
        df_copy = df.copy()
        df_copy["date"] = df_copy.index.date
        daily_open = df_copy.groupby("date")["Open"].first()
        daily_close = df_copy.groupby("date")["Close"].last()
        prev_close = daily_close.shift(1)
        prev_closes[ticker] = prev_close

    vol_5 = {}
    for ticker, df in data.items():
        daily = df.resample("D").agg({
            "Open": "first",
            "High": "max",
            "Low": "min",
            "Close": "last"
        }).dropna()
        daily["range_pct"] = (daily["High"] - daily["Low"]) / daily["Open"] * 100
        daily["volatility_5d"] = daily["range_pct"].shift(1).rolling(5).mean()
        daily.index = daily.index.date  
        vol_5[ticker] = daily["volatility_5d"]

    rows = []

    for _, trade in trades.iterrows():
        ticker = trade['ticker']
        date = trade['date']

        df = data[ticker].copy()
        df['date'] = df.index.date
        day_data = df[df['date'] == date]

        nifty_df = data['NIFTY'].copy()
        nifty_df['date'] = nifty_df.index.date
        nifty_data = nifty_df[nifty_df['date'] == date]


        signal_match = signals[
            (signals['ticker'] == ticker) &
            (signals['date'] == date)
        ]

        if signal_match.empty:
            continue
        signal_row = signal_match.iloc[0]
        feat = build_feature(
            signal_row=signal_row,
            day_data=day_data,
            ticker_avg_volume=avg_volumes.get(ticker, 1.0),
            nifty_data = nifty_data
        )

        if feat is None:
            print(f"None returned for {ticker} on {date}")
            continue
        try:
            prev_close_series = prev_closes[ticker]
            prev_close_value = prev_close_series.loc[date]
            orb_open = day_data.sort_index().iloc[0]['Open']
            if pd.notna(prev_close_value) and prev_close_value>0:
                feat['gap_pct'] = round(
                    (orb_open-prev_close_value)/prev_close_value*100,4
                )
        except (KeyError, IndexError):
            feat['gap_pct'] = 0.0

        try:
            vol_5_series = vol_5[ticker]
            vol_5_value = vol_5_series.loc[date]
            feat['volatility_5d'] = round(
                    vol_5_value,4
                )
        except (KeyError, IndexError):
            feat['volatility_5d'] = 0.0

        feat['date'] = date
        feat['ticker'] = ticker
        feat['signal'] = trade['signal']
        feat['label'] = trade['exit_reason'] #TARGET, STOP, TIME, EOD

        rows.append(feat)

    feature_df = pd.DataFrame(rows)

    feature_df['label'] = feature_df['label'].replace('EOD', 'TIME')
    feature_df = feature_df.sort_values(['date', 'ticker']).reset_index(drop=True)

    print(f"Feature matrix built: {len(feature_df)} rows, "
          f"{len([c for c in feature_df.columns if c not in ['date','ticker','signal','label']])} features")
    print(f"\nLabel distribution:\n{feature_df['label'].value_counts()}")
 
    return feature_df
 
 
if __name__ == "__main__":
    from shared.data import fetch_all
    from orb.strategy import run_strategy
    from orb.backtest import run_backtest
 
    data    = fetch_all(interval="1h")
    signals = run_strategy(data)
    trades  = run_backtest(signals, data, time_exit_hour=14)
 
    feature_df = build_feature_matrix(signals, trades, data)
    print("\nSample rows:")
    print(feature_df.head(5).to_string(index=False))
    feature_df.to_csv(OUTPUT_DIR/"features.csv", index=False)
    print("\nSaved to features.csv")
 
