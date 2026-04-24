import yfinance as yf
import pandas as pd
import pytz
import time
from shared.config import WATCHLIST, CAPITAL_PER_TRADE, BROKERAGE_PER_ORDER, STT_RATE, EXCHANGE_RATE, SEBI_RATE, STAMP_RATE, GST_RATE
from datetime import datetime
from orb.strategy import get_signal
IST = pytz.timezone("Asia/Kolkata")
TIME_EXIT_HOUR = 14
TIME_EXIT_MINUTE = 30

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

def fetch_today(ticker: str) -> pd.DataFrame: 

    print(f"Fetching data for {ticker}")

    df = yf.download(
        tickers = ticker,
        period = "2d",
        interval = "1h", #1hr since 1 min only available for past 7 days data
        auto_adjust = True,
        progress = False
    )

    if df.empty:
        print(f"No data returned for {ticker}")
        return df
    
    df = df[["Open", "High", "Low", "Close", "Volume"]]
    df.columns = df.columns.get_level_values(0)
    df.index = df.index.tz_convert("Asia/Kolkata")
    df = df[df.index.date == datetime.now(IST).date()]
    df.dropna(inplace=True)
    return df

def generate_signals():
    try:
        trades = pd.read_csv("paper_trades.csv")
    except Exception as e:
        trades = pd.DataFrame(columns = [
        "signal" ,
        "entry",
        "stop_loss",
        "target",
        "range_high",
        "range_low",
        "range_size", 
        "status",
        "date",
        "ticker",
        "entry_time",
        "exit_price",
        "exit_reason",
        "exit_time",
        "shares",
        "gross_pnl",
        "costs",
        "net_pnl",
        "win"

        ])
    
    trade_signals = []
    for ticker in WATCHLIST:
        df = fetch_today(ticker)
        signals = get_signal(df)
        if signals['signal']!="NONE":
            if ((trades["ticker"] == ticker) & (trades["date"] == str(datetime.now(IST).date()))).any():
                continue
            else:
                signals["ticker"] = ticker 
                signals["date"] = datetime.now(IST).date()
                signals["status"] = "OPEN"
                signals["entry_time"] = datetime.now(IST).strftime("%Y-%m-%d %H:%M:%S")
                signals["shares"] = CAPITAL_PER_TRADE/signals["entry"]
                trade_signals.append(signals)

    if not trade_signals:
        return
    trades_df = pd.DataFrame(trade_signals)
    result = pd.concat([trades, trades_df], axis=0)
    result.to_csv("paper_trades.csv", index=False)

def check_exits(force_exit: bool = False):
    try:
        trades = pd.read_csv("paper_trades.csv")
    except Exception as e:
        print("No trades to check")
        return
    
    open_trades = trades[(trades['status']=="OPEN") & (trades["date"]== str(datetime.now(IST).date()))].copy()

    for idx, row in open_trades.iterrows():
        ticker = row["ticker"]
        df = fetch_today(ticker)
        try:
            current_price = df.iloc[-1]["Close"]
        except IndexError:
            print(f"Error occurred while fetching data for {ticker}")
            continue
        if row["signal"] == "BUY":
            if force_exit==False:
                if current_price>= row["target"]:
                    trades.at[idx, "exit_price"] = row["target"]
                    trades.at[idx, "exit_reason"] = "TARGET"
                    trades.at[idx, "exit_time"] = datetime.now(IST).strftime("%Y-%m-%d %H:%M:%S")
                    trades.at[idx, "gross_pnl"] = (row["target"] - row["entry"])*row["shares"] 
                    trades.at[idx, "costs"] = calculate_costs(row["entry"], row["target"], row["shares"], row['signal'])
                    trades.at[idx, "net_pnl"] = trades.at[idx, "gross_pnl"] - trades.at[idx, "costs"]
                    trades.at[idx, "win"] = trades.at[idx, "net_pnl"] > 0
                    trades.at[idx, "status"] = "CLOSED"
                elif current_price <= row["stop_loss"]:
                    trades.at[idx, "exit_price"] = row["stop_loss"]
                    trades.at[idx, "exit_reason"] = "STOP_LOSS"
                    trades.at[idx, "exit_time"] = datetime.now(IST).strftime("%Y-%m-%d %H:%M:%S")
                    trades.at[idx, "gross_pnl"] = (row["stop_loss"] - row["entry"])*row["shares"] 
                    trades.at[idx, "costs"] = calculate_costs(row["entry"], row["stop_loss"], row["shares"], row['signal'])
                    trades.at[idx, "net_pnl"] = trades.at[idx, "gross_pnl"] - trades.at[idx, "costs"]
                    trades.at[idx, "win"] = trades.at[idx, "net_pnl"] > 0
                    trades.at[idx, "status"] = "CLOSED"
            else:
                    trades.at[idx, "exit_price"] = current_price
                    trades.at[idx, "exit_reason"] = "FORCE_EXIT"
                    trades.at[idx, "exit_time"] = datetime.now(IST).strftime("%Y-%m-%d %H:%M:%S")
                    trades.at[idx, "gross_pnl"] = (current_price - row["entry"])*row["shares"] 
                    trades.at[idx, "costs"] = calculate_costs(row["entry"], current_price, row["shares"], row['signal'])
                    trades.at[idx, "net_pnl"] = trades.at[idx, "gross_pnl"] - trades.at[idx, "costs"]
                    trades.at[idx, "win"] = trades.at[idx, "net_pnl"] > 0
                    trades.at[idx, "status"] = "CLOSED"


        if row["signal"] == "SELL":
            if force_exit==False:
                if current_price<= row["target"]:
                    trades.at[idx, "exit_price"] = row["target"]
                    trades.at[idx, "exit_reason"] = "TARGET"
                    trades.at[idx, "exit_time"] = datetime.now(IST).strftime("%Y-%m-%d %H:%M:%S")
                    trades.at[idx, "gross_pnl"] = (row["entry"] - row["target"]) * row["shares"]
                    trades.at[idx, "costs"] = calculate_costs(row["entry"], row["target"], row["shares"], row['signal'])
                    trades.at[idx, "net_pnl"] = trades.at[idx, "gross_pnl"] - trades.at[idx, "costs"]
                    trades.at[idx, "win"] = trades.at[idx, "net_pnl"] > 0
                    trades.at[idx, "status"] = "CLOSED"
                elif current_price >= row["stop_loss"]:
                    trades.at[idx, "exit_price"] = row["stop_loss"]
                    trades.at[idx, "exit_reason"] = "STOP_LOSS"
                    trades.at[idx, "exit_time"] = datetime.now(IST).strftime("%Y-%m-%d %H:%M:%S")
                    trades.at[idx, "gross_pnl"] = (row["entry"] - row["stop_loss"]) * row["shares"]
                    trades.at[idx, "costs"] = calculate_costs(row["entry"], row["stop_loss"], row["shares"], row['signal'])
                    trades.at[idx, "net_pnl"] = trades.at[idx, "gross_pnl"] - trades.at[idx, "costs"]
                    trades.at[idx, "win"] = trades.at[idx, "net_pnl"] > 0
                    trades.at[idx, "status"] = "CLOSED"
            else:
                    trades.at[idx, "exit_price"] = current_price
                    trades.at[idx, "exit_reason"] = "FORCE_EXIT"
                    trades.at[idx, "exit_time"] = datetime.now(IST).strftime("%Y-%m-%d %H:%M:%S")
                    trades.at[idx, "gross_pnl"] = (row["entry"] - current_price)*row["shares"] 
                    trades.at[idx, "costs"] = calculate_costs(row["entry"], current_price, row["shares"], row['signal'])
                    trades.at[idx, "net_pnl"] = trades.at[idx, "gross_pnl"] - trades.at[idx, "costs"]
                    trades.at[idx, "win"] = trades.at[idx, "net_pnl"] > 0
                    trades.at[idx, "status"] = "CLOSED"
            
    trades.to_csv("paper_trades.csv", index=False)

def run():
    while True:
        current_time = datetime.now(IST).time()
        if current_time.hour < 10 :
            print("SLEEPING... waiting for ORB window to complete")
            time.sleep(3600)
        elif current_time.hour == 10:
            if current_time.minute<15:
                print("SLEEPING... waiting for ORB window to complete")
                time.sleep(3600)
            elif current_time.minute>=15:
                generate_signals()
                check_exits()
                time.sleep(3600)
        elif current_time.hour>10 and current_time.hour < TIME_EXIT_HOUR:
            check_exits()
            time.sleep(3600)
        elif current_time.hour == TIME_EXIT_HOUR and current_time.minute >= TIME_EXIT_MINUTE:
            check_exits(force_exit=True)
            print("FORCE EXIT executed for all open trades")
            break
        else:
            print("OUTSIDE MARKET HOURS")
            break

if __name__ == "__main__":
    run()