#!/usr/bin/env python3
"""
=============================================================================
XAUUSD Scale-Invariant Machine Learning Training Script
Designed for Google Colab Execution
=============================================================================
"""

import os
import sys
import time
import json
import gc
import numpy as np
import pandas as pd
import lightgbm as lgb
from sklearn.metrics import mean_absolute_error, mean_squared_error
import joblib

def calculate_rsi(series, period=14):
    delta = series.diff()
    gain = (delta.where(delta > 0, 0.0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0.0)).rolling(window=period).mean()
    rs = gain / (loss + 1e-9)
    return 100.0 - (100.0 / (1.0 + rs))

def main():
    print("=" * 65)
    print("🚀 เริ่มต้นกระบวนการเทรนโมเดล XAUUSD Scale-Invariant บน Google Colab")
    print("=" * 65)
    start_time = time.time()
    
    # 1. หาที่อยู่ไฟล์ Dataset
    data_files = [
        "XAUUSD_M1.csv.gz",
        "XAUUSD.iux_M1_20200102_to_20251230.csv",
        "XAUUSD_M1.csv"
    ]
    csv_file = None
    for f in data_files:
        if os.path.exists(f):
            csv_file = f
            break
            
    if csv_file is None:
        print("❌ ไม่พบไฟล์ Dataset ใน Working Directory!")
        sys.exit(1)
        
    print(f"📂 กำลังโหลดข้อมูลจากไฟล์: {csv_file}")
    
    dtypes = {
        'open': 'float32',
        'high': 'float32',
        'low': 'float32',
        'close': 'float32',
        'tick_volume': 'int32',
        'spread': 'int16'
    }
    
    df = pd.read_csv(csv_file, usecols=['datetime', 'open', 'high', 'low', 'close', 'tick_volume', 'spread'], dtype=dtypes)
    df['datetime'] = pd.to_datetime(df['datetime'])
    df.sort_values('datetime', inplace=True)
    df.reset_index(drop=True, inplace=True)
    
    total_raw_rows = len(df)
    print(f"✅ โหลดข้อมูลสำเร็จ: {total_raw_rows:,} แถว (ตั้งแต่ {df.iloc[0]['datetime']} ถึง {df.iloc[-1]['datetime']})")
    
    # 2. ตั้งค่าพารามิเตอร์
    N_FORWARD = 15  # จำนวนแท่งข้างหน้า (15 แท่ง)
    print(f"🎯 กำหนด Target Horizon: อีก {N_FORWARD} แท่งข้างหน้า")
    
    # 3. คำนวณ True Range และ ATR
    print("⚙️ กำลังคำนวณ ATR และ Features (Scale-Invariant)...")
    high_low = df['high'] - df['low']
    high_close = (df['high'] - df['close'].shift(1)).abs()
    low_close = (df['low'] - df['close'].shift(1)).abs()
    tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
    atr14 = tr.rolling(14).mean()
    atr50 = tr.rolling(50).mean()
    safe_atr = atr14.replace(0, np.nan)
    
    # 4. สร้าง 22 Stationary Features (ไม่มีราคาดิบ)
    X = pd.DataFrame(index=df.index)
    
    # Returns
    for lag in [1, 3, 5, 15, 30, 60]:
        X[f'ret_{lag}'] = np.log(df['close'] / df['close'].shift(lag))
        
    # Moving Average Distance per ATR
    ema20 = df['close'].ewm(span=20, adjust=False).mean()
    ema50 = df['close'].ewm(span=50, adjust=False).mean()
    ema200 = df['close'].ewm(span=200, adjust=False).mean()
    X['dist_ema20_atr'] = (df['close'] - ema20) / safe_atr
    X['dist_ema50_atr'] = (df['close'] - ema50) / safe_atr
    X['dist_ema200_atr'] = (df['close'] - ema200) / safe_atr
    
    # Volatility
    X['norm_atr14'] = atr14 / df['close']
    X['atr_ratio'] = atr14 / (atr50 + 1e-9)
    
    # Candlestick Shapes
    X['bar_range_atr'] = (df['high'] - df['low']) / safe_atr
    X['bar_body_atr'] = (df['close'] - df['open']) / safe_atr
    X['upper_wick_atr'] = (df['high'] - np.maximum(df['open'], df['close'])) / safe_atr
    X['lower_wick_atr'] = (np.minimum(df['open'], df['close']) - df['low']) / safe_atr
    
    # Oscillators & Volume
    X['rsi14'] = calculate_rsi(df['close'], period=14) / 100.0
    safe_vol = df['tick_volume'].replace(0, 1)
    X['vol_ratio_20'] = safe_vol / (safe_vol.rolling(20).mean() + 1e-9)
    X['vol_ratio_100'] = safe_vol / (safe_vol.rolling(100).mean() + 1e-9)
    
    # Cyclic Session Time
    hour = df['datetime'].dt.hour + df['datetime'].dt.minute / 60.0
    dow = df['datetime'].dt.dayofweek
    X['hour_sin'] = np.sin(2 * np.pi * hour / 24.0)
    X['hour_cos'] = np.cos(2 * np.pi * hour / 24.0)
    X['dow_sin'] = np.sin(2 * np.pi * dow / 5.0)
    X['dow_cos'] = np.cos(2 * np.pi * dow / 5.0)
    
    # 5. คำนวณ Targets (Upside & Downside in ATR units)
    print("🎯 กำลังคำนวณ Target Upside & Downside...")
    indexer = pd.api.indexers.FixedForwardWindowIndexer(window_size=N_FORWARD)
    future_max_high = df['high'].shift(-1).rolling(window=indexer).max()
    future_min_low = df['low'].shift(-1).rolling(window=indexer).min()
    
    y_up = (np.maximum(0.0, future_max_high - df['close']) / safe_atr).clip(upper=25.0)
    y_down = (np.maximum(0.0, df['close'] - future_min_low) / safe_atr).clip(upper=25.0)
    
    # Clean NaN
    valid_mask = ~(X.isna().any(axis=1) | y_up.isna() | y_down.isna())
    X_clean = X[valid_mask].astype('float32')
    y_up_clean = y_up[valid_mask].astype('float32')
    y_down_clean = y_down[valid_mask].astype('float32')
    df_clean = df[valid_mask]
    
    print(f"📊 ข้อมูลพร้อมใช้งานทั้งหมด: {len(X_clean):,} แถว (Features: {X_clean.shape[1]} ตัว)")
    
    # 6. Time-Series Split (80% Train, 20% Test)
    split_idx = int(len(X_clean) * 0.80)
    X_train, X_test = X_clean.iloc[:split_idx], X_clean.iloc[split_idx:]
    y_up_train, y_up_test = y_up_clean.iloc[:split_idx], y_up_clean.iloc[split_idx:]
    y_down_train, y_down_test = y_down_clean.iloc[:split_idx], y_down_clean.iloc[split_idx:]
    
    print(f"📚 Train set: {len(X_train):,} แถว ({df_clean.iloc[0]['datetime']} -> {df_clean.iloc[split_idx]['datetime']})")
    print(f"🧪 Test set:  {len(X_test):,} แถว ({df_clean.iloc[split_idx]['datetime']} -> {df_clean.iloc[-1]['datetime']})")
    
    # Free memory
    del df, tr, ema20, ema50, ema200, future_max_high, future_min_low
    gc.collect()
    
    # 7. Model Training ด้วย LightGBM
    lgb_params = {
        'objective': 'regression_l1',  # MAE Loss
        'metric': 'mae',
        'boosting_type': 'gbdt',
        'n_estimators': 600,
        'learning_rate': 0.05,
        'num_leaves': 31,
        'subsample': 0.8,
        'colsample_bytree': 0.8,
        'random_state': 42,
        'n_jobs': -1,
        'verbose': -1
    }
    
    print("\n" + "=" * 50)
    print("🔥 [1/2] กำลังเทรน Model 1: UPSIDE PREDICTOR...")
    print("=" * 50)
    model_upside = lgb.LGBMRegressor(**lgb_params)
    model_upside.fit(
        X_train, y_up_train,
        eval_set=[(X_test, y_up_test)],
        callbacks=[lgb.early_stopping(stopping_rounds=30, verbose=False)]
    )
    
    print("\n" + "=" * 50)
    print("🔥 [2/2] กำลังเทรน Model 2: DOWNSIDE PREDICTOR...")
    print("=" * 50)
    model_downside = lgb.LGBMRegressor(**lgb_params)
    model_downside.fit(
        X_train, y_down_train,
        eval_set=[(X_test, y_down_test)],
        callbacks=[lgb.early_stopping(stopping_rounds=30, verbose=False)]
    )
    
    # 8. ประเมินผลโมเดลบน Test Set (Out-of-Time 2024-2025)
    print("\n" + "=" * 50)
    print("📈 สรุปผลการประเมินบนชุดข้อมูลทดสอบ (Out-of-Time Test Set)")
    print("=" * 50)
    pred_up = model_upside.predict(X_test)
    pred_down = model_downside.predict(X_test)
    
    up_mae = mean_absolute_error(y_up_test, pred_up)
    down_mae = mean_absolute_error(y_down_test, pred_down)
    up_corr = np.corrcoef(y_up_test, pred_up)[0, 1]
    down_corr = np.corrcoef(y_down_test, pred_down)[0, 1]
    
    print(f"✅ Upside Prediction MAE:   {up_mae:.4f} ATR | Correlation: {up_corr * 100:.2f}%")
    print(f"✅ Downside Prediction MAE: {down_mae:.4f} ATR | Correlation: {down_corr * 100:.2f}%")
    
    # Feature Importances Top 5
    up_imp = sorted(zip(X_clean.columns, model_upside.feature_importances_), key=lambda x: x[1], reverse=True)[:5]
    down_imp = sorted(zip(X_clean.columns, model_downside.feature_importances_), key=lambda x: x[1], reverse=True)[:5]
    print("\n🏆 Top 5 Features (Upside Model):", [f[0] for f in up_imp])
    print("🏆 Top 5 Features (Downside Model):", [f[0] for f in down_imp])
    
    # 9. บันทึกโมเดล
    print("\n💾 กำลังบันทึกไฟล์โมเดล...")
    joblib.dump(model_upside, 'xauusd_upside_model.joblib')
    joblib.dump(model_downside, 'xauusd_downside_model.joblib')
    
    # บันทึกเป็น Native LightGBM Text Format ด้วย (MQL5 / C++ Friendly)
    model_upside.booster_.save_model('xauusd_upside_model.txt')
    model_downside.booster_.save_model('xauusd_downside_model.txt')
    
    summary = {
        'total_rows': total_raw_rows,
        'features_count': int(X_clean.shape[1]),
        'feature_names': list(X_clean.columns),
        'n_forward': N_FORWARD,
        'test_rows': len(X_test),
        'upside_mae_atr': float(up_mae),
        'upside_corr': float(up_corr),
        'downside_mae_atr': float(down_mae),
        'downside_corr': float(down_corr),
        'training_time_sec': float(time.time() - start_time)
    }
    with open('training_summary.json', 'w', encoding='utf-8') as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)
        
    print(f"\n🎉 การเทรนเสร็จสมบูรณ์ในเวลา: {time.time() - start_time:.1f} วินาที!")
    print("=" * 65)

if __name__ == '__main__':
    main()
