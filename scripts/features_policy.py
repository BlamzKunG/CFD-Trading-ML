"""
=============================================================================
XAUUSD Trading Policy: Scale-Invariant Market & Position Feature Pipeline
=============================================================================
Architecture:
- Strictly Scale-Invariant & Stationary Market State (26 features)
- Relative Position State (9 features)
- Zero Raw Price Inputs (No 1500 or 5000 price scale dependency)
- Multi-Horizon Returns, Volatility Normalization, Candlestick Microstructure
=============================================================================
"""

import numpy as np
import pandas as pd

MARKET_FEATURE_NAMES = [
    # 1. Multi-Horizon Log Returns
    'ret_1', 'ret_3', 'ret_5', 'ret_15', 'ret_30', 'ret_60',
    # 2. Volatility & Normalized Movement
    'norm_atr14', 'atr_ratio', 'realized_vol_30',
    'move_5_atr', 'move_15_atr', 'move_60_atr',
    # 3. Normalized Candlestick Microstructure
    'body_atr', 'range_atr', 'upper_wick_ratio', 'lower_wick_ratio', 'close_loc_in_bar',
    # 4. Local Price Distribution (Stationary Percentiles & Z-scores)
    'z_score_20', 'z_score_100', 'pct_rank_60',
    # 5. Momentum & Normalized EMA Distances
    'dist_ema20_atr', 'dist_ema50_atr', 'dist_ema200_atr', 'rsi14_norm',
    # 6. Relative Macro Context
    'macro_ema_ratio',
    # 7. Volume Ratios
    'vol_ratio_20', 'vol_ratio_100',
    # 8. Cyclic Time Context
    'hour_sin', 'hour_cos', 'dow_sin', 'dow_cos'
]

POSITION_FEATURE_NAMES = [
    'pos_dir',                 # -1.0 (Short), 0.0 (Flat), +1.0 (Long)
    'pos_size_frac',           # 0.0 to 1.0 fraction of max risk
    'entry_dist_atr',          # (Close - Entry) / ATR
    'unrealized_pnl_atr',      # Paper PnL in ATR multiples
    'time_in_pos_norm',        # Min(1.0, bars_in_pos / 120.0)
    'dist_to_sl_atr',          # Current distance to SL in ATR
    'dist_to_tp_atr',          # Current distance to TP in ATR
    'max_drawdown_atr',        # Max Adverse Excursion experienced in ATR
    'bars_since_action_norm'   # Min(1.0, bars_since_last_action / 60.0)
]

ALL_POLICY_FEATURE_NAMES = MARKET_FEATURE_NAMES + POSITION_FEATURE_NAMES

def calculate_rsi(series: pd.Series, period: int = 14) -> pd.Series:
    delta = series.diff()
    gain = (delta.where(delta > 0, 0.0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0.0)).rolling(window=period).mean()
    rs = gain / (loss + 1e-9)
    return 100.0 - (100.0 / (1.0 + rs))

def extract_market_state_features(df: pd.DataFrame) -> pd.DataFrame:
    """
    สร้าง 26 Scale-Invariant Market State Features จากข้อมูล M1
    ไม่มี Raw Price (Close = 1500 vs 5000 จะถูก Normalise อยู่ใน Relative Space ทั้งหมด)
    """
    df = df.copy()
    
    # 1. True Range & ATR
    high_low = df['high'] - df['low']
    high_close = (df['high'] - df['close'].shift(1)).abs()
    low_close = (df['low'] - df['close'].shift(1)).abs()
    tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
    
    atr14 = tr.rolling(14).mean().replace(0, np.nan)
    atr50 = tr.rolling(50).mean().replace(0, np.nan)
    close = df['close']
    
    feat = pd.DataFrame(index=df.index)
    
    # 1. Multi-Horizon Log Returns
    feat['ret_1'] = np.log(close / close.shift(1))
    feat['ret_3'] = np.log(close / close.shift(3))
    feat['ret_5'] = np.log(close / close.shift(5))
    feat['ret_15'] = np.log(close / close.shift(15))
    feat['ret_30'] = np.log(close / close.shift(30))
    feat['ret_60'] = np.log(close / close.shift(60))
    
    # 2. Volatility & Normalized Movement
    feat['norm_atr14'] = atr14 / close
    feat['atr_ratio'] = atr14 / (atr50 + 1e-9)
    feat['realized_vol_30'] = feat['ret_1'].rolling(30).std()
    
    feat['move_5_atr'] = (close - close.shift(5)) / atr14
    feat['move_15_atr'] = (close - close.shift(15)) / atr14
    feat['move_60_atr'] = (close - close.shift(60)) / atr14
    
    # 3. Normalized Candlestick Microstructure
    bar_range = (df['high'] - df['low']).replace(0, 1e-9)
    feat['body_atr'] = (close - df['open']) / atr14
    feat['range_atr'] = bar_range / atr14
    feat['upper_wick_ratio'] = (df['high'] - np.maximum(df['open'], close)) / bar_range
    feat['lower_wick_ratio'] = (np.minimum(df['open'], close) - df['low']) / bar_range
    feat['close_loc_in_bar'] = (close - df['low']) / bar_range
    
    # 4. Local Price Distribution
    roll_mean20 = close.rolling(20).mean()
    roll_std20 = close.rolling(20).std().replace(0, 1e-9)
    feat['z_score_20'] = (close - roll_mean20) / roll_std20
    
    roll_mean100 = close.rolling(100).mean()
    roll_std100 = close.rolling(100).std().replace(0, 1e-9)
    feat['z_score_100'] = (close - roll_mean100) / roll_std100
    
    roll_min60 = close.rolling(60).min()
    roll_max60 = close.rolling(60).max()
    feat['pct_rank_60'] = (close - roll_min60) / (roll_max60 - roll_min60 + 1e-9)
    
    # 5. Momentum & Normalized EMA Distances
    ema20 = close.ewm(span=20, adjust=False).mean()
    ema50 = close.ewm(span=50, adjust=False).mean()
    ema200 = close.ewm(span=200, adjust=False).mean()
    
    feat['dist_ema20_atr'] = (close - ema20) / atr14
    feat['dist_ema50_atr'] = (close - ema50) / atr14
    feat['dist_ema200_atr'] = (close - ema200) / atr14
    feat['rsi14_norm'] = calculate_rsi(close, 14) / 100.0
    
    # 6. Relative Macro Context
    feat['macro_ema_ratio'] = np.log(close / ema200)
    
    # 7. Volume Ratios
    safe_vol = df['tick_volume'].replace(0, 1)
    vol_sma20 = safe_vol.rolling(20).mean()
    vol_sma100 = safe_vol.rolling(100).mean()
    feat['vol_ratio_20'] = safe_vol / (vol_sma20 + 1e-9)
    feat['vol_ratio_100'] = safe_vol / (vol_sma100 + 1e-9)
    
    # 8. Cyclic Time Context
    if 'datetime' in df.columns:
        dt = pd.to_datetime(df['datetime'])
    elif 'timestamp' in df.columns:
        dt = pd.to_datetime(df['timestamp'], unit='s')
    else:
        dt = pd.to_datetime(df.index)
        
    hour = dt.dt.hour + dt.dt.minute / 60.0
    dow = dt.dt.dayofweek
    feat['hour_sin'] = np.sin(2 * np.pi * hour / 24.0)
    feat['hour_cos'] = np.cos(2 * np.pi * hour / 24.0)
    feat['dow_sin'] = np.sin(2 * np.pi * dow / 5.0)
    feat['dow_cos'] = np.cos(2 * np.pi * dow / 5.0)
    
    return feat, atr14, close
