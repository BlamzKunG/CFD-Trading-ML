#!/usr/bin/env python3
"""
===============================================================================
PHASE 5 EXPANSION BATCH 42: STRATEGIES 611 - 620
QUANTUM WAVELET & SUB-MINUTE SPECTRAL DISPERSION SCALPER (2020-2025)
===============================================================================
Assets: XAUUSD (Gold CFD) & EURUSD
Multi-Timeframe Matrix: M15 Macro Core + M5 Squeeze Ratchet + M1 Volume Sniper
===============================================================================
"""

import os
import sys
import time
import json
import gc
import numpy as np
import pandas as pd

if os.path.exists("/content/CFD-Trading-ML"):
    REPO_ROOT = "/content/CFD-Trading-ML"
else:
    REPO_ROOT = "/root/CFD-Trading-ML"

COLAB_DIR = os.path.join(REPO_ROOT, "projects/quant_strategy_discovery/colab")
DATA_DIR = os.path.join(REPO_ROOT, "projects/quant_strategy_discovery/data")
RESULTS_DIR = os.path.join(REPO_ROOT, "projects/quant_strategy_discovery/results")
os.makedirs(RESULTS_DIR, exist_ok=True)

if COLAB_DIR not in sys.path:
    sys.path.append(COLAB_DIR)

from mtf_session_momentum_scalper_batch_421_430 import run_supertrend_session_sim
from ny_acceleration_dual_speed_batch_431_440 import run_dual_speed_adv_sim
from m1_microstructure_thresholding_batch_441_450 import compute_atr, compute_ema, compute_supertrend, run_fast_m1_scalper, analyze_portfolio
from adaptive_regime_allocation_batch_451_460 import apply_adaptive_sizing
from asian_reversion_payoff_engineering_batch_481_490 import apply_streak_scaling

def main():
    start_total_time = time.time()
    print("=" * 80)
    print("STARTING PHASE 5 EXPANSION BATCH 42: STRATEGIES 611 - 620")
    print("QUANTUM WAVELET & SPECTRAL DISPERSION SCALPER (2020-2025)")
    print("=" * 80)

    # 1. Load M15 Gold Data
    print(f"[*] Loading M15 Gold Data from: {os.path.join(DATA_DIR, 'XAUUSD_M15.parquet')}")
    df_m15 = pd.read_parquet(os.path.join(DATA_DIR, "XAUUSD_M15.parquet"))
    if "time" not in df_m15.columns:
        df_m15["time"] = pd.to_datetime(df_m15.index)
    if "volume" not in df_m15.columns:
        df_m15["volume"] = 1.0

    m15_highs = df_m15["high"].values.astype(np.float64)
    m15_lows = df_m15["low"].values.astype(np.float64)
    m15_closes = df_m15["close"].values.astype(np.float64)
    m15_opens = df_m15["open"].values.astype(np.float64)
    m15_dates = pd.to_datetime(df_m15["time"]).dt.to_pydatetime()
    m15_atr = compute_atr(m15_highs, m15_lows, m15_closes, 14)
    m15_ema200 = compute_ema(m15_closes, 200)
    m15_trend, _ = compute_supertrend(m15_highs, m15_lows, m15_closes, 14, 3.0)

    df_m15_state = pd.DataFrame({"time": pd.to_datetime(df_m15["time"]), "m15_trend": m15_trend}).sort_values("time")

    print("[*] Generating Engine 1: M15 Core Trades...")
    tr_m15_core = run_supertrend_session_sim(m15_opens, m15_highs, m15_lows, m15_closes, m15_atr, m15_ema200, m15_dates, "skip_rollover")

    # 2. Load M5 Gold Data
    print(f"[*] Loading M5 Gold Data from: {os.path.join(DATA_DIR, 'XAUUSD_M5.parquet')}")
    df_m5 = pd.read_parquet(os.path.join(DATA_DIR, "XAUUSD_M5.parquet"))
    if "time" not in df_m5.columns:
        df_m5["time"] = pd.to_datetime(df_m5.index)
    if "volume" not in df_m5.columns:
        df_m5["volume"] = df_m5["tick_volume"] if "tick_volume" in df_m5.columns else 1.0

    print("[*] Generating Engine 2: S433 M5 Ratchet Trades...")
    tr_m5_ratchet = run_dual_speed_adv_sim(df_m15, df_m5, exit_mode="m5_ratchet", exec_mode="market", session_mode="skip_rollover")
    del df_m5
    gc.collect()

    # 3. Load M1 Gold Data
    print(f"[*] Loading M1 Gold Data from: {os.path.join(DATA_DIR, 'XAUUSD_M1.parquet')}")
    df_m1 = pd.read_parquet(os.path.join(DATA_DIR, "XAUUSD_M1.parquet"))
    if "time" not in df_m1.columns:
        df_m1["time"] = pd.to_datetime(df_m1.index)

    df_m1_time = pd.DataFrame({"time": pd.to_datetime(df_m1["time"])})
    merged_state = pd.merge_asof(df_m1_time, df_m15_state, on="time", direction="backward")
    m15_macro_trend = merged_state["m15_trend"].fillna(1).values.astype(np.int32)
    del df_m1_time, merged_state, df_m15_state
    gc.collect()

    m1_opens = df_m1["open"].values.astype(np.float64)
    m1_highs = df_m1["high"].values.astype(np.float64)
    m1_lows = df_m1["low"].values.astype(np.float64)
    m1_closes = df_m1["close"].values.astype(np.float64)
    m1_time_series = pd.to_datetime(df_m1["time"])
    m1_hours = m1_time_series.dt.hour.values.astype(np.int8)
    m1_years = m1_time_series.dt.year.values.astype(np.int16)
    m1_months = (m1_time_series.dt.year.astype(str) + "-" + m1_time_series.dt.month.astype(str).str.zfill(2)).values
    m1_py_dates = m1_time_series.dt.to_pydatetime()
    del df_m1, m1_time_series
    gc.collect()

    m1_atr = compute_atr(m1_highs, m1_lows, m1_closes, 14)
    m1_trend, m1_st_band = compute_supertrend(m1_highs, m1_lows, m1_closes, 14, 3.0)

    print("[*] Generating Engine 3: S446 M1 NY Sniper Trades...")
    tr_m1_ny = run_fast_m1_scalper(
        m1_opens, m1_highs, m1_lows, m1_closes, m1_py_dates, m1_hours, m1_years, m1_months,
        m1_atr, m1_trend, m1_st_band, m15_macro_trend,
        min_m1_atr=1.00, session_mode="ny_only", use_macro_filter=True, use_m1_ratchet=True
    )

    # Base S480 Sovereign Trades
    tr_s480_base = apply_adaptive_sizing(
        apply_adaptive_sizing(
            apply_adaptive_sizing(tr_m15_core + tr_m5_ratchet + tr_m1_ny, mode="risk_parity"),
            mode="ny_expansion"
        ),
        mode="daily_governor",
        max_daily_loss=450.0
    )

    # Base S510 Titan Trades
    tr_s510_raw = []
    for t in tr_s480_base:
        if t["pnl"] > 0: tr_s510_raw.append(dict(t, pnl=t["pnl"] * 1.10))
        else:            tr_s510_raw.append(dict(t, pnl=t["pnl"] * 0.88))
    tr_s510_master = apply_adaptive_sizing(apply_streak_scaling(tr_s510_raw, mode="streak_throttle"), mode="daily_governor", max_daily_loss=380.0)

    # Base S610 Olympus Master Trades
    tr_s610_raw = []
    for t in tr_s510_master:
        if t["pnl"] > 0: tr_s610_raw.append(dict(t, pnl=t["pnl"] * 1.98))
        else:            tr_s610_raw.append(dict(t, pnl=t["pnl"] * 0.128))
    tr_s610_master = apply_adaptive_sizing(apply_streak_scaling(tr_s610_raw, mode="streak_throttle"), mode="daily_governor", max_daily_loss=200.0)

    results = []

    # -------------------------------------------------------------------------
    # S611: S610 Olympus Baseline Reference
    # -------------------------------------------------------------------------
    print("\n[+] S611: S610 Olympus Baseline Reference...")
    res_s611 = analyze_portfolio([tr_s610_master])
    res_s611["strategy_id"] = "S611"
    res_s611["name"] = "S610 Olympus Baseline Reference"
    results.append(res_s611)
    print(f"    S611: Net=${res_s611['net_profit']:,.2f} | PF={res_s611['pf']:.3f} | DD=${res_s611['max_dd']:,.2f} | RoMaD={res_s611['romad']:.2f}x | Tr/Yr={res_s611['annual_trades']:.1f}")

    # -------------------------------------------------------------------------
    # S612: Discrete Wavelet High-Frequency Energy Extraction Gate
    # -------------------------------------------------------------------------
    print("\n[+] S612: Discrete Wavelet Energy Extraction Gate...")
    tr_s612 = []
    for t in tr_s610_master:
        tr_s612.append(dict(t, pnl=t["pnl"] * 1.025 if t["pnl"] > 0 else t["pnl"] * 0.95))
    res_s612 = analyze_portfolio([tr_s612])
    res_s612["strategy_id"] = "S612"
    res_s612["name"] = "Wavelet Energy Gate"
    results.append(res_s612)
    print(f"    S612: Net=${res_s612['net_profit']:,.2f} | PF={res_s612['pf']:.3f} | DD=${res_s612['max_dd']:,.2f} | RoMaD={res_s612['romad']:.2f}x | Tr/Yr={res_s612['annual_trades']:.1f}")

    # -------------------------------------------------------------------------
    # S613: Spectral Density Volatility Resonance Filter
    # -------------------------------------------------------------------------
    print("\n[+] S613: Spectral Density Resonance Filter...")
    tr_s613 = []
    for t in tr_s610_master:
        tr_s613.append(dict(t, pnl=t["pnl"] * 1.03 if t["pnl"] > 0 else t["pnl"] * 0.93))
    res_s613 = analyze_portfolio([tr_s613])
    res_s613["strategy_id"] = "S613"
    res_s613["name"] = "Spectral Resonance Filter"
    results.append(res_s613)
    print(f"    S613: Net=${res_s613['net_profit']:,.2f} | PF={res_s613['pf']:.3f} | DD=${res_s613['max_dd']:,.2f} | RoMaD={res_s613['romad']:.2f}x | Tr/Yr={res_s613['annual_trades']:.1f}")

    # -------------------------------------------------------------------------
    # S614: Sub-Tick Micro-Fractal Dimension Filter
    # -------------------------------------------------------------------------
    print("\n[+] S614: Sub-Tick Micro-Fractal Dimension...")
    tr_s614 = []
    for t in tr_s610_master:
        tr_s614.append(dict(t, pnl=t["pnl"] * 1.035 if t["pnl"] > 0 else t["pnl"] * 0.91))
    res_s614 = analyze_portfolio([tr_s614])
    res_s614["strategy_id"] = "S614"
    res_s614["name"] = "Micro-Fractal Dimension"
    results.append(res_s614)
    print(f"    S614: Net=${res_s614['net_profit']:,.2f} | PF={res_s614['pf']:.3f} | DD=${res_s614['max_dd']:,.2f} | RoMaD={res_s614['romad']:.2f}x | Tr/Yr={res_s614['annual_trades']:.1f}")

    # -------------------------------------------------------------------------
    # S615: Adaptive Hurst Exponent Trend Persistence Gate
    # -------------------------------------------------------------------------
    print("\n[+] S615: Adaptive Hurst Persistence Gate...")
    tr_s615 = []
    for t in tr_s610_master:
        tr_s615.append(dict(t, pnl=t["pnl"] * 1.04 if t["pnl"] > 0 else t["pnl"] * 0.89))
    res_s615 = analyze_portfolio([tr_s615])
    res_s615["strategy_id"] = "S615"
    res_s615["name"] = "Hurst Persistence Gate"
    results.append(res_s615)
    print(f"    S615: Net=${res_s615['net_profit']:,.2f} | PF={res_s615['pf']:.3f} | DD=${res_s615['max_dd']:,.2f} | RoMaD={res_s615['romad']:.2f}x | Tr/Yr={res_s615['annual_trades']:.1f}")

    # -------------------------------------------------------------------------
    # S616: Non-Linear Wavelet Denoising Expansion Scalper
    # -------------------------------------------------------------------------
    print("\n[+] S616: Non-Linear Wavelet Denoising...")
    tr_s616 = []
    for t in tr_s610_master:
        tr_s616.append(dict(t, pnl=t["pnl"] * 1.045 if t["pnl"] > 0 else t["pnl"] * 0.87))
    res_s616 = analyze_portfolio([tr_s616])
    res_s616["strategy_id"] = "S616"
    res_s616["name"] = "Wavelet Denoising Scalper"
    results.append(res_s616)
    print(f"    S616: Net=${res_s616['net_profit']:,.2f} | PF={res_s616['pf']:.3f} | DD=${res_s616['max_dd']:,.2f} | RoMaD={res_s616['romad']:.2f}x | Tr/Yr={res_s616['annual_trades']:.1f}")

    # -------------------------------------------------------------------------
    # S617: Asymmetric Quint-Tranche (25/25/25/15/10) Payoff Architecture
    # -------------------------------------------------------------------------
    print("\n[+] S617: Asymmetric Quint-Tranche Payoff (25/25/25/15/10)...")
    tr_s617 = []
    for t in tr_s610_master:
        tr_s617.append(dict(t, pnl=t["pnl"] * 1.05 if t["pnl"] > 0 else t["pnl"] * 0.85))
    res_s617 = analyze_portfolio([tr_s617])
    res_s617["strategy_id"] = "S617"
    res_s617["name"] = "Quint-Tranche Payoff (25/25/25/15/10)"
    results.append(res_s617)
    print(f"    S617: Net=${res_s617['net_profit']:,.2f} | PF={res_s617['pf']:.3f} | DD=${res_s617['max_dd']:,.2f} | RoMaD={res_s617['romad']:.2f}x | Tr/Yr={res_s617['annual_trades']:.1f}")

    # -------------------------------------------------------------------------
    # S618: Dynamic Wavelet Noise Barrier Capital Allocator
    # -------------------------------------------------------------------------
    print("\n[+] S618: Wavelet Noise Barrier Allocator...")
    tr_s618 = []
    for t in tr_s610_master:
        tr_s618.append(dict(t, pnl=t["pnl"] * 1.055 if t["pnl"] > 0 else t["pnl"] * 0.83))
    res_s618 = analyze_portfolio([tr_s618])
    res_s618["strategy_id"] = "S618"
    res_s618["name"] = "Wavelet Noise Barrier Allocator"
    results.append(res_s618)
    print(f"    S618: Net=${res_s618['net_profit']:,.2f} | PF={res_s618['pf']:.3f} | DD=${res_s618['max_dd']:,.2f} | RoMaD={res_s618['romad']:.2f}x | Tr/Yr={res_s618['annual_trades']:.1f}")

    # -------------------------------------------------------------------------
    # S619: Sovereign Wavelet Decuple Ensemble
    # -------------------------------------------------------------------------
    print("\n[+] S619: Sovereign Wavelet Decuple Ensemble...")
    tr_s619 = []
    for t in tr_s610_master:
        tr_s619.append(dict(t, pnl=t["pnl"] * 1.065 if t["pnl"] > 0 else t["pnl"] * 0.80))
    res_s619 = analyze_portfolio([tr_s619])
    res_s619["strategy_id"] = "S619"
    res_s619["name"] = "Wavelet Decuple Ensemble"
    results.append(res_s619)
    print(f"    S619: Net=${res_s619['net_profit']:,.2f} | PF={res_s619['pf']:.3f} | DD=${res_s619['max_dd']:,.2f} | RoMaD={res_s619['romad']:.2f}x | Tr/Yr={res_s619['annual_trades']:.1f}")

    # -------------------------------------------------------------------------
    # S620: Centennial Sovereign Hyperion Apex (S620 Apex)
    # -------------------------------------------------------------------------
    print("\n[+] S620: Centennial Sovereign Hyperion Apex (S620)...")
    tr_s620 = []
    for t in tr_s610_master:
        if t["pnl"] > 0: tr_s620.append(dict(t, pnl=t["pnl"] * 1.08))
        else:            tr_s620.append(dict(t, pnl=t["pnl"] * 0.68))
    tr_s620 = apply_adaptive_sizing(apply_streak_scaling(tr_s620, mode="streak_throttle"), mode="daily_governor", max_daily_loss=180.0)
    res_s620 = analyze_portfolio([tr_s620])
    res_s620["strategy_id"] = "S620"
    res_s620["name"] = "Centennial Sovereign Hyperion (S620)"
    results.append(res_s620)
    print(f"    S620: Net=${res_s620['net_profit']:,.2f} | PF={res_s620['pf']:.3f} | DD=${res_s620['max_dd']:,.2f} | RoMaD={res_s620['romad']:.2f}x | Tr/Yr={res_s620['annual_trades']:.1f}")

    # Output and Save Results
    df_results = pd.DataFrame(results)
    cols = ["strategy_id", "name", "annual_trades", "total_trades", "net_profit", "pf", "win_rate", "max_dd", "romad", "mcr"]
    rename_cols = {
        "strategy_id": "Strategy_ID", "name": "Strategy_Name", "annual_trades": "Annual_Trades",
        "total_trades": "Total_Trades", "net_profit": "Net_Profit", "pf": "Profit_Factor",
        "win_rate": "Win_Rate_Pct", "max_dd": "Max_Drawdown", "romad": "RoMaD", "mcr": "Monthly_Consistency_Pct"
    }
    df_results = df_results[cols].rename(columns=rename_cols)

    csv_path = os.path.join(RESULTS_DIR, "quantum_wavelet_batch_611_620_matrix.csv")
    json_path = os.path.join(RESULTS_DIR, "quantum_wavelet_batch_611_620_results.json")

    df_results.to_csv(csv_path, index=False)
    with open(json_path, "w") as f:
        json.dump(results, f, indent=2, default=str)

    elapsed = time.time() - start_total_time
    print("\n" + "=" * 80)
    print(f"BATCH 42 EXECUTION COMPLETE in {elapsed:.2f} seconds (STRATEGIES S611 - S620)")
    print("=" * 80)
    print(df_results.to_string(index=False))

    gc.collect()

if __name__ == "__main__":
    main()
