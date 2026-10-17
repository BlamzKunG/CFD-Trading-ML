#!/usr/bin/env python3
"""
Convert XAUUSD_M1.csv.gz to XAUUSD_M1.parquet for fast, memory-safe multi-TF access.
"""
import os
import sys
import gc
import time
import pandas as pd

CSV_PATH = "/storage/emulated/0/Download/EA/XAUUSD_M1.csv.gz"
OUTPUT_DIR = "/root/CFD-Trading-ML/projects/quant_strategy_discovery/data"
OUTPUT_FILE = os.path.join(OUTPUT_DIR, "XAUUSD_M1.parquet")

def main():
    t0 = time.time()
    print(f"[*] Starting M1 parquet conversion from {CSV_PATH}...")
    if not os.path.exists(CSV_PATH):
        alt_path = "/mnt/sdcard/Download/EA/XAUUSD_M1.csv.gz"
        if os.path.exists(alt_path):
            src_path = alt_path
        else:
            print(f"[!] Error: Source file not found: {CSV_PATH}")
            sys.exit(1)
    else:
        src_path = CSV_PATH

    dtypes = {
        'open': 'float64',
        'high': 'float64',
        'low': 'float64',
        'close': 'float64',
        'tick_volume': 'int64'
    }
    usecols = ['datetime', 'open', 'high', 'low', 'close', 'tick_volume']
    
    print(f"[*] Reading M1 CSV in chunks to prevent memory spike...")
    chunk_list = []
    for chunk in pd.read_csv(src_path, usecols=usecols, dtype=dtypes, chunksize=300000):
        chunk['datetime'] = pd.to_datetime(chunk['datetime'])
        chunk.set_index('datetime', inplace=True)
        chunk_list.append(chunk)
        print(f"    Processed chunk: total rows so far = {sum(len(c) for c in chunk_list):,}")

    print(f"[*] Concatenating chunks...")
    df = pd.concat(chunk_list)
    del chunk_list
    gc.collect()

    os.makedirs(OUTPUT_DIR, exist_ok=True)
    print(f"[*] Saving {len(df):,} M1 bars to {OUTPUT_FILE}...")
    df.to_parquet(OUTPUT_FILE, compression='snappy')
    
    print(f"[+] Successfully generated XAUUSD_M1.parquet in {time.time() - t0:.2f}s!")
    print(f"    Date range: {df.index[0]} to {df.index[-1]}")
    print(f"    Shape: {df.shape}")
    print(f"    File size: {os.path.getsize(OUTPUT_FILE) / (1024*1024):.2f} MB")

if __name__ == '__main__':
    main()
