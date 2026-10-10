#!/usr/bin/env python3
"""
One-time Lightweight Cache Generator for Mobile Hardware Protection
Resamples raw M1 data to H1 and M15 Parquet files to prevent Out-Of-Memory (OOM)
and Thermal Shutdown on Android ARM hardware.
"""
import os
import gc
import pandas as pd

OUT_DIR = "projects/quant_strategy_discovery/data"
os.makedirs(OUT_DIR, exist_ok=True)

def process_file(symbol, filepath):
    h1_path = os.path.join(OUT_DIR, f"{symbol}_H1.parquet")
    m15_path = os.path.join(OUT_DIR, f"{symbol}_M15.parquet")
    
    if os.path.exists(h1_path) and os.path.exists(m15_path):
        print(f"[✓] {symbol} caches already exist. Skipping.")
        return

    print(f"[*] Processing {symbol} from {filepath}...")
    df = pd.read_csv(filepath, usecols=["datetime", "open", "high", "low", "close"])
    df["datetime"] = pd.to_datetime(df["datetime"])
    df.set_index("datetime", inplace=True)
    df.sort_index(inplace=True)
    
    print(f"[*] Resampling {symbol} to H1...")
    df_h1 = df.resample("1h").agg({"open": "first", "high": "max", "low": "min", "close": "last"}).dropna()
    df_h1.to_parquet(h1_path, compression="snappy")
    print(f"[+] Saved {h1_path} ({len(df_h1)} bars, {os.path.getsize(h1_path) / 1024:.1f} KB)")
    del df_h1
    gc.collect()

    print(f"[*] Resampling {symbol} to M15...")
    df_m15 = df.resample("15min").agg({"open": "first", "high": "max", "low": "min", "close": "last"}).dropna()
    df_m15.to_parquet(m15_path, compression="snappy")
    print(f"[+] Saved {m15_path} ({len(df_m15)} bars, {os.path.getsize(m15_path) / 1024:.1f} KB)")
    del df_m15
    del df
    gc.collect()
    print(f"[✓] {symbol} processing complete.")

if __name__ == "__main__":
    process_file("XAUUSD", "/mnt/sdcard/Download/EA/XAUUSD_M1.csv.gz")
    process_file("EURUSD", "/mnt/sdcard/Download/EA/EURUSD_M1.csv.gz")
    print("[🎉] All lightweight Parquet caches generated successfully!")
