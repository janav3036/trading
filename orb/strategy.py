import pandas as pd
from shared.config import WATCHLIST
from shared.data import fetch_all
from orb.config import RISK_REWARD, BREAKOUT_BUFFER

def get_signal(day_data:pd.DataFrame) -> dict:
    """
    Return following signals - 
    signal - buy, sell or none
    entry - breakout price, float or none
    stop loss - stop loss price, float or none
    target - target price, float or none
    range_high - high of opening range candle
    range_low - low of opening range candle
    range_size - range_high - range_low

    """

    no_signal = {
        "signal" : "NONE",
        "entry": None,
        "stop_loss": None,
        "target": None,
        "range_high": None,
        "range_low": None,
        "range_size": None

    }

    day_data = day_data.sort_index()

    if len(day_data)<2:
        return no_signal

    orb_candle = day_data.iloc[0]
    range_high = orb_candle["High"]
    range_low = orb_candle["Low"]
    range_size = range_high- range_low

    if range_size <=0:
        return no_signal
    
    orb_bullish = orb_candle["Close"] > orb_candle["Open"]
    orb_bearish = orb_candle["Close"] < orb_candle["Open"]
    
    post_orb = day_data.iloc[1:]

    for _, candle in post_orb.iterrows():
        bullish_breakout = orb_bullish and candle["Close"] > range_high * (1 + BREAKOUT_BUFFER)
        bearish_breakout = orb_bearish and candle["Close"] < range_low  * (1 - BREAKOUT_BUFFER)

        if bullish_breakout:
            entry = range_high
            stop_loss = range_low
            target = entry + RISK_REWARD * range_size
            return {
                "signal": "BUY",
                "entry": round(entry, 2),
                "stop_loss": round(stop_loss, 2),
                "target": round(target, 2),
                "range_high": round(range_high, 2),
                "range_low": round(range_low, 2),
                "range_size": round(range_size, 2),
            }
 
        if bearish_breakout:
            entry = range_low
            stop_loss = range_high
            target = entry - RISK_REWARD * range_size
            return {
                "signal": "SELL",
                "entry": round(entry, 2),
                "stop_loss": round(stop_loss, 2),
                "target": round(target, 2),
                "range_high": round(range_high, 2),
                "range_low": round(range_low, 2),
                "range_size": round(range_size, 2),
            }
 
    # No breakout on this day
    return {
        "signal": "NONE",
        "entry": None,
        "stop_loss": None,
        "target": None,
        "range_high": round(range_high, 2),
        "range_low": round(range_low, 2),
        "range_size": round(range_size, 2),
    }
 
def run_strategy(data:dict)  ->  pd.DataFrame:
    all_signals = []

    for ticker, df in data.items():
        df = df.copy()
        df['date'] = df.index.date
        
        for date, day_data in df.groupby("date"):
            result = get_signal(day_data)
            result["ticker"] = ticker
            result["date"] = date
            all_signals.append(result)

    if not all_signals:
        print("No signals generated")
        return pd.DataFrame()
    
    signals_df = pd.DataFrame(all_signals)

    signals_df = signals_df[[
        "date", 
        "ticker",
        "signal",
        "entry",
        "stop_loss",
        "target",
        "range_high",
        "range_low",
        "range_size"

    ]]

    signals_df.sort_values(['date','ticker'], inplace=True)
    signals_df.reset_index(drop=True, inplace=True)

    return signals_df

if __name__ == "__main__":
    print("Fetching data...")
    data = fetch_all()
 
    if not data:
        print("fetch_all() returned empty — check data.py and your cache.")
    else:
        print(f"Loaded {len(data)} tickers.\n")
 
        print("Running ORB strategy...")
        signals = run_strategy(data)
 
        print(f"\nTotal (date × ticker) rows : {len(signals)}")
        print(f"\nSignal breakdown:")
        print(signals["signal"].value_counts())
 
        non_none = signals[signals["signal"] != "NONE"]
        print(f"\nSample active signals ({len(non_none)} total):")
        print(non_none.head(10).to_string(index=False))
 

    