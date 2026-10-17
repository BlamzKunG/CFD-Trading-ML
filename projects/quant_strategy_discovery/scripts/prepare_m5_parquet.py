#!/usr/bin/env python3
"""
Generate XAUUSD_M5.parquet from XAUUSD_M1.csv.gz with low memory footprint.
Memory budget: < 150 MB RAM using float32 and targeted usecols.
"""
import os
import sys
import gc
import time
import pandas as pd

CSV_PATH = "/storage/emulated/0/Download/EA/XAUUSD_M1.csv.gz"
OUTPUT_DIR = "/root/CFD-Trading-ML/projects/quant_strategy_discovery/data"
OUTPUT_FILE = os.path.join(OUTPUT_DIR, "XAUUSD_M5.parquet")

def main():
    t0 = time.time()
    print(f"[*] Starting M5 generation from {CSV_PATH}...")
    if not os.path.exists(CSV_PATH):
        # Try alternate path
        alt_path = "/mnt/sdcard/Download/EA/XAUUSD_M1.csv.gz"
        if os.path.exists(alt_path):
            src_path = alt_path
        else:
            print(f"[!] Error: Source file not found: {CSV_PATH}")
            sys.exit(1)
    else:
        src_path = CSV_PATH

    print(f"[*] Reading selected columns from {src_path}...")
    dtypes = {
        'open': 'float32',
        'high': 'float32',
        'low': 'float32',
        'close': 'float32',
        'tick_volume': 'int32'
    }
    usecols = ['datetime', 'open', 'high', 'low', 'close', 'tick_volume']
    
    df = pd.read_csv(src_path, usecols=usecols, dtype=dtypes)
    print(f"[*] Loaded {len(df):,} M1 rows. Converting datetime index...")
    
    df['datetime'] = pd.to_datetime(df['datetime'])
    df.set_index('datetime', inplace=True)
    
    print(f"[*] Resampling to 5-minute bars (M5)...")
    m5 = df.resample('5min').agg({
        'open': 'first',
        'high': 'max',
        'low': 'min',
        'close': 'last',
        'tick_volume': 'sum'
    }).dropna()
    
    # Cast back to float64/int64 for standard quant parity
    m5['open'] = m5['open'].astype('float64')
    m5['high'] = m5['high'].astype('float64')
    m5['low'] = m5['low'].astype('float64')
    m5['close'] = m5['close'].astype('float64')
    m5['tick_volume'] = m5['tick_volume'].astype('int64')

    del df
    gc.collect()

    os.makedirs(OUTPUT_DIR, exist_ok=True)
    print(f"[*] Saving {len(m5):,} M5 bars to {OUTPUT_FILE}...")
    m5.to_parquet(OUTPUT_FILE, compression='snappy')
    
    print(f"[+] Successfully generated XAUUSD_M5.parquet in {time.time() - t0:.2f}s!")
    print(f"    Date range: {m5.index[0]} to {m5.index[-1]}")
    print(f"    Shape: {m5.shape}")
    print(f"    File size: {os.path.getsize(OUTPUT_FILE) / (1024*1024):.2f} MB")

if __name__ == '__main__':
    main()
