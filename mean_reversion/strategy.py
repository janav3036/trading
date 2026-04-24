from datetime import time
import numpy as np
import pandas as pd
import pandas_ta as ta

def get_signal(stock_df: pd.DataFrame, nifty_df: pd.DataFrame) -> pd.DataFrame:
    market_start = time(9, 15)
    market_end = time(15,30)

    nifty_df  = nifty_df[(nifty_df.index.time >= market_start) & (nifty_df.index.time <= market_end) ].copy()
    stock_df  = stock_df[(stock_df.index.time >= market_start) & (stock_df.index.time <= market_end) ].copy()

    result = ta.adx(nifty_df['high'], nifty_df['low'], nifty_df['close'], length=14)
    nifty_df['adx'] = result['ADX_14']

    bb = ta.bbands(stock_df['close'], length = 20, std = 2)

    stock_df['bb_lower'] = bb['BBL_20_2.0_2.0']
    stock_df['bb_middle'] = bb['BBM_20_2.0_2.0']
    stock_df['bb_upper'] = bb['BBU_20_2.0_2.0']

    stock_df = pd.merge_asof(stock_df, nifty_df['adx'], left_index=True, right_index=True, direction="backward")
    stock_df['sigma'] = (stock_df['bb_upper'] - stock_df['bb_middle'])/2
    """stock_df['entry_lower'] = stock_df['bb_middle'] - 2.5 * stock_df['sigma']
    stock_df['entry_upper'] = stock_df['bb_middle'] + 2.5 * stock_df['sigma']
    """
    stock_df['target_long'] = stock_df['bb_middle'] - stock_df['sigma']
    stock_df['target_short'] = stock_df['bb_middle'] + stock_df['sigma']
    stock_df['signal'] = np.where(
        (stock_df['adx']<22.5) & (stock_df['close']<=stock_df['bb_lower']),
        "LONG", 
        np.where(
            (stock_df['adx']<22.5) & (stock_df['close']>=stock_df['bb_upper']), 
            "SHORT", 
            "NONE"
            )
        )
    
    
    return stock_df