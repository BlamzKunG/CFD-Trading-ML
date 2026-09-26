"""
=============================================================================
XAUUSD Machine Learning Pipeline (Scale-Invariant & Stationary Features)
ออกแบบสำหรับใช้ร่วมกับ EA: ทำนายระยะทางที่ราคามีโอกาสวิ่งต่อ (Upside / Downside) ในอีก N แท่ง
=============================================================================
"""

import os
import gc
import numpy as np
import pandas as pd

def calculate_rsi(series, period=14):
    delta = series.diff()
    gain = (delta.where(delta > 0, 0.0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0.0)).rolling(window=period).mean()
    rs = gain / (loss + 1e-9)
    return 100.0 - (100.0 / (1.0 + rs))

def build_features_and_targets(df: pd.DataFrame, n_forward: int = 15, is_training: bool = True):
    """
    สร้าง Stationary Features (ไม่มีระดับราคาดิบ) และ Target (ระยะทางสูงสุดในอีก N แท่ง Normalized ด้วย ATR)
    """
    df = df.copy()
    
    # 1. คำนวณ True Range และ ATR
    high_low = df['high'] - df['low']
    high_close = (df['high'] - df['close'].shift(1)).abs()
    low_close = (df['low'] - df['close'].shift(1)).abs()
    tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
    
    df['atr14'] = tr.rolling(14).mean()
    df['atr50'] = tr.rolling(50).mean()
    
    # หลีกเลี่ยงหารด้วย 0
    safe_atr = df['atr14'].replace(0, np.nan)
    
    features = pd.DataFrame(index=df.index)
    
    # 2. Stationary Features (ระดับราคาและโมเมนตัมสัมพัทธ์ทั้งหมด)
    # Log Returns ในหลายๆ Time Window
    features['ret_1'] = np.log(df['close'] / df['close'].shift(1))
    features['ret_3'] = np.log(df['close'] / df['close'].shift(3))
    features['ret_5'] = np.log(df['close'] / df['close'].shift(5))
    features['ret_15'] = np.log(df['close'] / df['close'].shift(15))
    features['ret_30'] = np.log(df['close'] / df['close'].shift(30))
    features['ret_60'] = np.log(df['close'] / df['close'].shift(60))
    
    # Normalized Moving Averages (ระยะห่างจาก EMA วัดเป็นจำนวนเท่าของ ATR)
    ema20 = df['close'].ewm(span=20, adjust=False).mean()
    ema50 = df['close'].ewm(span=50, adjust=False).mean()
    ema200 = df['close'].ewm(span=200, adjust=False).mean()
    
    features['dist_ema20_atr'] = (df['close'] - ema20) / safe_atr
    features['dist_ema50_atr'] = (df['close'] - ema50) / safe_atr
    features['dist_ema200_atr'] = (df['close'] - ema200) / safe_atr
    
    # Volatility Metrics
    features['norm_atr14'] = df['atr14'] / df['close']  # Relative Volatility ต่อระดับราคา
    features['atr_ratio'] = df['atr14'] / (df['atr50'] + 1e-9)  # Expansion vs Compression
    
    # Candlestick Microstructure (สัดส่วนแท่งเทียนต่อ ATR)
    features['bar_range_atr'] = (df['high'] - df['low']) / safe_atr
    features['bar_body_atr'] = (df['close'] - df['open']) / safe_atr
    features['upper_wick_atr'] = (df['high'] - np.maximum(df['open'], df['close'])) / safe_atr
    features['lower_wick_atr'] = (np.minimum(df['open'], df['close']) - df['low']) / safe_atr
    
    # RSI Oscillator
    features['rsi14'] = calculate_rsi(df['close'], period=14) / 100.0  # Scale 0-1
    
    # Volume Ratios
    safe_vol = df['tick_volume'].replace(0, 1)
    vol_sma20 = safe_vol.rolling(20).mean()
    vol_sma100 = safe_vol.rolling(100).mean()
    features['vol_ratio_20'] = safe_vol / (vol_sma20 + 1e-9)
    features['vol_ratio_100'] = safe_vol / (vol_sma100 + 1e-9)
    
    # Time / Session Encoding (วัฏจักรของเวลาตลาด ลอนดอน/นิวยอร์ก)
    if 'datetime' in df.columns:
        dt = pd.to_datetime(df['datetime'])
        hour = dt.dt.hour + dt.dt.minute / 60.0
        dow = dt.dt.dayofweek
        features['hour_sin'] = np.sin(2 * np.pi * hour / 24.0)
        features['hour_cos'] = np.cos(2 * np.pi * hour / 24.0)
        features['dow_sin'] = np.sin(2 * np.pi * dow / 5.0)
        features['dow_cos'] = np.cos(2 * np.pi * dow / 5.0)
        
    targets = pd.DataFrame(index=df.index)
    
    # 3. Target Calculation (สร้างเฉพาะช่วง Training / Evaluation)
    if is_training:
        indexer = pd.api.indexers.FixedForwardWindowIndexer(window_size=n_forward)
        future_max_high = df['high'].shift(-1).rolling(window=indexer).max()
        future_min_low = df['low'].shift(-1).rolling(window=indexer).min()
        
        # คำนวณระยะ Upside และ Downside เป็น "จำนวนเท่าของ ATR"
        # หากราคาไม่ขึ้นเลย (ลงอย่างเดียว) ให้ Upside = 0
        targets['target_upside_atr'] = np.maximum(0.0, future_max_high - df['close']) / safe_atr
        targets['target_downside_atr'] = np.maximum(0.0, df['close'] - future_min_low) / safe_atr
        
        # ตัดค่า Outlier สุดขั้วที่เกิดจาก Flash Crash / Bug เช่น มากกว่า 30 เท่าของ ATR
        targets['target_upside_atr'] = targets['target_upside_atr'].clip(upper=25.0)
        targets['target_downside_atr'] = targets['target_downside_atr'].clip(upper=25.0)
        
    return features, targets, df[['datetime', 'close', 'atr14']]
