import pandas as pd
import numpy as np
from datetime import time

def backtest(stock_df):
    trades = []
    in_trade = False
    entry_price = target = stop = direction = None

    for timestamp, row in stock_df.iterrows():
        if in_trade:
            if timestamp.time() >= time(15, 15):
                trades.append({
                    'entry': entry_price,
                    'entry_time': entry_time,
                    'exit': row['close'],
                    'exit_time': timestamp,
                    'target':target,
                    'stop': stop,
                    'direction':direction,
                    'reason': "TIME",
                })
                in_trade = False
                entry_price = target = stop = direction = entry_time = None
                continue
            # check if target or stop hit
            if direction == "LONG":
                if row['high']>=target:
                    trades.append({
                        'entry': entry_price,
                        'entry_time': entry_time,
                        'exit': target,
                        'exit_time': timestamp,
                        'target':target,
                        'stop': stop,
                        'direction':direction,
                        'reason': "TARGET",
                    })
                    in_trade = False
                    entry_price = target = stop = direction = entry_time = None
                elif row['low'] <=stop:
                    trades.append({
                        'entry': entry_price,
                        'entry_time': entry_time,
                        'exit': stop,
                        'exit_time': timestamp,
                        'target':target,
                        'stop': stop,
                        'direction':direction,
                        'reason': "STOP",
                    })
                    in_trade = False
                    entry_price = target = stop = direction = entry_time = None
            else:
                if row['low']<=target:
                    trades.append({
                        'entry': entry_price,
                        'entry_time': entry_time,
                        'exit': target,
                        'exit_time': timestamp,
                        'target':target,
                        'stop': stop,
                        'direction':direction,
                        'reason': "TARGET",
                    })
                    in_trade = False
                    entry_price = target = stop = direction = entry_time = None
                elif row['high'] >=stop:
                    trades.append({
                        'entry': entry_price,
                        'entry_time': entry_time,
                        'exit': stop,
                        'exit_time': timestamp,
                        'target':target,
                        'stop': stop,
                        'direction':direction,
                        'reason': "STOP",
                    })
                    in_trade = False
                    entry_price = target = stop = direction = entry_time = None
                

            pass
        else:
            # check for new signal
            if row['signal'] == "LONG":
                entry_price = row['close']
                target = row['target_long']
                stop = row['bb_lower'] - 3*row['sigma']
                in_trade = True
                entry_time = timestamp
                direction = row['signal']
                
            elif row['signal'] == "SHORT":
                entry_price = row['close']
                target = row['target_short']
                stop = row['bb_upper'] + 3*row['sigma']
                in_trade = True
                entry_time = timestamp
                direction = row['signal']
            pass
    
    return pd.DataFrame(trades)