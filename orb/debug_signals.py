# debug_signals.py — paste in your notebooks/ folder and run
import pandas as pd
from data import fetch_all
from strategy import get_signal

data = fetch_all()

# Pick one ticker to inspect
ticker = "RELIANCE.NS"
df = data[ticker].copy()
df["date"] = df.index.date

records = []
for date, day_data in df.groupby("date"):
    day_data = day_data.sort_index()
    if len(day_data) < 2:
        continue

    orb = day_data.iloc[0]
    result = get_signal(day_data)

    # Find which candle triggered the signal
    trigger_candle_idx = None
    trigger_close = None
    for i, (_, c) in enumerate(day_data.iloc[1:].iterrows()):
        if result["signal"] == "BUY" and c["Close"] > orb["High"]:
            trigger_candle_idx = i + 1
            trigger_close = c["Close"]
            break
        if result["signal"] == "SELL" and c["Close"] < orb["Low"]:
            trigger_candle_idx = i + 1
            trigger_close = c["Close"]
            break

    records.append({
        "date": date,
        "signal": result["signal"],
        "orb_open": orb["Open"],
        "orb_high": orb["High"],
        "orb_low": orb["Low"],
        "orb_close": orb["Close"],
        "trigger_candle": trigger_candle_idx,  # 1 = immediately next candle
        "trigger_close": trigger_close,
    })

debug_df = pd.DataFrame(records)

print("=== Signal breakdown ===")
print(debug_df["signal"].value_counts())

print("\n=== Which candle triggers the signal? ===")
print(debug_df["trigger_candle"].value_counts().sort_index())

print("\n=== Sample SELL signals triggered on candle 1 (immediate reversal?) ===")
immediate_sells = debug_df[(debug_df["signal"] == "SELL") & (debug_df["trigger_candle"] == 1)]
print(immediate_sells.head(10).to_string(index=False))

print("\n=== First 5 candle timestamps for one day (checking 9:15 alignment) ===")
first_day = df.groupby("date").first().index[0]
print(df[df["date"] == first_day].index.tolist())