"""
=============================================================================
XAUUSD Market Sensor: Feature & 30-Target Engineering Pipeline
=============================================================================
Architecture:
- Scale-Invariant & Stationary Features (22 Features, Market State only)
- 30 Probabilistic Binary Targets (2 Directions x 5 Distances x 3 Horizons)
- Strict Time-based Split with Purge Gap (90 bars) between Train, Val, Dev
- 2026 Preserved Untouched as Blind Out-of-Sample
=============================================================================
"""

import os
import gc
import numpy as np
import pandas as pd

# 30 Target Specifications
DIRECTIONS = ['up', 'down']
DISTANCES = [0.5, 1.0, 1.5, 2.0, 2.5]
HORIZONS = [30, 60, 90]

TARGET_COLUMNS = []
for d in DIRECTIONS:
    for dist in DISTANCES:
        for h in HORIZONS:
            TARGET_COLUMNS.append(f"target_{d}_{dist}_{h}")

FEATURE_COLUMNS = [
    'ret_1', 'ret_3', 'ret_5', 'ret_15', 'ret_30', 'ret_60',
    'dist_ema20_atr', 'dist_ema50_atr', 'dist_ema200_atr',
    'norm_atr14', 'atr_ratio',
    'bar_range_atr', 'bar_body_atr', 'upper_wick_atr', 'lower_wick_atr',
    'rsi14',
    'vol_ratio_20', 'vol_ratio_100',
    'hour_sin', 'hour_cos', 'dow_sin', 'dow_cos'
]

def calculate_rsi(series: pd.Series, period: int = 14) -> pd.Series:
    delta = series.diff()
    gain = (delta.where(delta > 0, 0.0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0.0)).rolling(window=period).mean()
    rs = gain / (loss + 1e-9)
    return 100.0 - (100.0 / (1.0 + rs))

def build_market_sensor_features(df: pd.DataFrame) -> pd.DataFrame:
    """
    สร้าง 22 Scale-Invariant Features จากข้อมูล M1 (ไม่มี Raw Price)
    """
    df = df.copy()
    
    # 1. True Range & ATR
    high_low = df['high'] - df['low']
    high_close = (df['high'] - df['close'].shift(1)).abs()
    low_close = (df['low'] - df['close'].shift(1)).abs()
    tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
    
    df['atr14'] = tr.rolling(14).mean()
    df['atr50'] = tr.rolling(50).mean()
    safe_atr = df['atr14'].replace(0, np.nan)
    
    features = pd.DataFrame(index=df.index)
    
    # Returns
    features['ret_1'] = np.log(df['close'] / df['close'].shift(1))
    features['ret_3'] = np.log(df['close'] / df['close'].shift(3))
    features['ret_5'] = np.log(df['close'] / df['close'].shift(5))
    features['ret_15'] = np.log(df['close'] / df['close'].shift(15))
    features['ret_30'] = np.log(df['close'] / df['close'].shift(30))
    features['ret_60'] = np.log(df['close'] / df['close'].shift(60))
    
    # EMA Distances per ATR
    ema20 = df['close'].ewm(span=20, adjust=False).mean()
    ema50 = df['close'].ewm(span=50, adjust=False).mean()
    ema200 = df['close'].ewm(span=200, adjust=False).mean()
    
    features['dist_ema20_atr'] = (df['close'] - ema20) / safe_atr
    features['dist_ema50_atr'] = (df['close'] - ema50) / safe_atr
    features['dist_ema200_atr'] = (df['close'] - ema200) / safe_atr
    
    # Volatility
    features['norm_atr14'] = df['atr14'] / df['close']
    features['atr_ratio'] = df['atr14'] / (df['atr50'] + 1e-9)
    
    # Microstructure per ATR
    features['bar_range_atr'] = (df['high'] - df['low']) / safe_atr
    features['bar_body_atr'] = (df['close'] - df['open']) / safe_atr
    features['upper_wick_atr'] = (df['high'] - np.maximum(df['open'], df['close'])) / safe_atr
    features['lower_wick_atr'] = (np.minimum(df['open'], df['close']) - df['low']) / safe_atr
    
    # RSI
    features['rsi14'] = calculate_rsi(df['close'], period=14) / 100.0
    
    # Volume Ratios
    safe_vol = df['tick_volume'].replace(0, 1)
    vol_sma20 = safe_vol.rolling(20).mean()
    vol_sma100 = safe_vol.rolling(100).mean()
    features['vol_ratio_20'] = safe_vol / (vol_sma20 + 1e-9)
    features['vol_ratio_100'] = safe_vol / (vol_sma100 + 1e-9)
    
    # Cyclic Time
    if 'datetime' in df.columns:
        dt = pd.to_datetime(df['datetime'])
    elif 'timestamp' in df.columns:
        dt = pd.to_datetime(df['timestamp'], unit='s')
    else:
        dt = pd.to_datetime(df.index)
        
    hour = dt.dt.hour + dt.dt.minute / 60.0
    dow = dt.dt.dayofweek
    features['hour_sin'] = np.sin(2 * np.pi * hour / 24.0)
    features['hour_cos'] = np.cos(2 * np.pi * hour / 24.0)
    features['dow_sin'] = np.sin(2 * np.pi * dow / 5.0)
    features['dow_cos'] = np.cos(2 * np.pi * dow / 5.0)
    
    return features, df['atr14'], df['close']

def build_30_binary_targets(df: pd.DataFrame, atr14: pd.Series) -> pd.DataFrame:
    """
    สร้าง 30 Binary Targets:
    Y_up(D, H) = 1 if max(High[t+1 : t+H]) >= Close[t] + D * ATR[t] else 0
    Y_down(D, H) = 1 if min(Low[t+1 : t+H]) <= Close[t] - D * ATR[t] else 0
    """
    targets = pd.DataFrame(index=df.index)
    close = df['close']
    
    for h in HORIZONS:
        indexer = pd.api.indexers.FixedForwardWindowIndexer(window_size=h)
        future_high = df['high'].shift(-1).rolling(window=indexer).max()
        future_low = df['low'].shift(-1).rolling(window=indexer).min()
        
        for dist in DISTANCES:
            # UP Event
            thresh_up = close + (dist * atr14)
            targets[f"target_up_{dist}_{h}"] = (future_high >= thresh_up).astype(np.int8)
            
            # DOWN Event
            thresh_down = close - (dist * atr14)
            targets[f"target_down_{dist}_{h}"] = (future_low <= thresh_down).astype(np.int8)
            
    return targets

def create_purged_splits(df: pd.DataFrame, max_horizon: int = 90):
    """
    แบ่ง Train (2020-2023), Val (2024), Dev (2025) พร้อม Purge Gap 90 แท่ง
    """
    if 'datetime' in df.columns:
        dt = pd.to_datetime(df['datetime'])
    elif 'timestamp' in df.columns:
        dt = pd.to_datetime(df['timestamp'], unit='s')
    else:
        dt = pd.to_datetime(df.index)
        
    year = dt.dt.year
    
    # Indices
    train_mask = (year >= 2020) & (year <= 2023)
    val_mask = (year == 2024)
    dev_mask = (year == 2025)
    
    train_idx = df.index[train_mask].tolist()
    val_idx = df.index[val_mask].tolist()
    dev_idx = df.index[dev_mask].tolist()
    
    # Purge max_horizon bars from the end of each set before the next
    if len(train_idx) > max_horizon:
        train_idx = train_idx[:-max_horizon]
    if len(val_idx) > max_horizon:
        val_idx = val_idx[:-max_horizon]
    if len(dev_idx) > max_horizon:
        dev_idx = dev_idx[:-max_horizon]
        
    return train_idx, val_idx, dev_idx
