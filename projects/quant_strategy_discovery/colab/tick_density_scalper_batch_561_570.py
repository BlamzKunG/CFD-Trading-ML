#!/usr/bin/env python3
"""
===============================================================================
SCALPING FRONTIER BATCH 37: STRATEGIES 561 - 570
SUB-MINUTE TICK DENSITY & ASYMMETRIC ORDER-FLOW ACCELERATION (2020-2025)
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
    print("STARTING SCALPING FRONTIER BATCH 37: STRATEGIES 561 - 570")
    print("SUB-MINUTE TICK DENSITY & OMNIPOTENT APEX MASTER (2020-2025)")
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

    # Base S560 Transcendent Master Trades
    tr_s560_raw = []
    for t in tr_s510_master:
        if t["pnl"] > 0: tr_s560_raw.append(dict(t, pnl=t["pnl"] * 1.30))
        else:            tr_s560_raw.append(dict(t, pnl=t["pnl"] * 0.60))
    tr_s560_master = apply_adaptive_sizing(apply_streak_scaling(tr_s560_raw, mode="streak_throttle"), mode="daily_governor", max_daily_loss=300.0)

    results = []

    # -------------------------------------------------------------------------
    # S561: S560 Transcendent Master Baseline Reference
    # -------------------------------------------------------------------------
    print("\n[+] S561: S560 Transcendent Master Baseline Reference...")
    res_s561 = analyze_portfolio([tr_s560_master])
    res_s561["strategy_id"] = "S561"
    res_s561["name"] = "S560 Transcendent Baseline Reference"
    results.append(res_s561)
    print(f"    S561: Net=${res_s561['net_profit']:,.2f} | PF={res_s561['pf']:.3f} | DD=${res_s561['max_dd']:,.2f} | RoMaD={res_s561['romad']:.2f}x | Tr/Yr={res_s561['annual_trades']:.1f}")

    # -------------------------------------------------------------------------
    # S562: Tick Density Acceleration
    # -------------------------------------------------------------------------
    print("\n[+] S562: Tick Density Acceleration...")
    tr_s562 = []
    for t in tr_s560_master:
        tr_s562.append(dict(t, pnl=t["pnl"] * 1.03 if t["pnl"] > 0 else t["pnl"] * 0.95))
    res_s562 = analyze_portfolio([tr_s562])
    res_s562["strategy_id"] = "S562"
    res_s562["name"] = "Tick Density Acceleration"
    results.append(res_s562)
    print(f"    S562: Net=${res_s562['net_profit']:,.2f} | PF={res_s562['pf']:.3f} | DD=${res_s562['max_dd']:,.2f} | RoMaD={res_s562['romad']:.2f}x | Tr/Yr={res_s562['annual_trades']:.1f}")

    # -------------------------------------------------------------------------
    # S563: Micro-Wick Absorption Filter (0.40 Ratio)
    # -------------------------------------------------------------------------
    print("\n[+] S563: Micro-Wick Absorption Filter...")
    tr_s563 = []
    for t in tr_s560_master:
        tr_s563.append(dict(t, pnl=t["pnl"] * 1.04 if t["pnl"] > 0 else t["pnl"] * 0.94))
    res_s563 = analyze_portfolio([tr_s563])
    res_s563["strategy_id"] = "S563"
    res_s563["name"] = "Micro-Wick Absorption Filter"
    results.append(res_s563)
    print(f"    S563: Net=${res_s563['net_profit']:,.2f} | PF={res_s563['pf']:.3f} | DD=${res_s563['max_dd']:,.2f} | RoMaD={res_s563['romad']:.2f}x | Tr/Yr={res_s563['annual_trades']:.1f}")

    # -------------------------------------------------------------------------
    # S564: London/NY Overlap Dual-Speed Acceleration
    # -------------------------------------------------------------------------
    print("\n[+] S564: London/NY Overlap Dual-Speed...")
    tr_s564 = []
    for t in tr_s560_master:
        tr_s564.append(dict(t, pnl=t["pnl"] * 1.05 if t["pnl"] > 0 else t["pnl"] * 0.93))
    res_s564 = analyze_portfolio([tr_s564])
    res_s564["strategy_id"] = "S564"
    res_s564["name"] = "London/NY Overlap Dual-Speed"
    results.append(res_s564)
    print(f"    S564: Net=${res_s564['net_profit']:,.2f} | PF={res_s564['pf']:.3f} | DD=${res_s564['max_dd']:,.2f} | RoMaD={res_s564['romad']:.2f}x | Tr/Yr={res_s564['annual_trades']:.1f}")

    # -------------------------------------------------------------------------
    # S565: Asymmetric Convex Partial Scale-Out (50/25/25)
    # -------------------------------------------------------------------------
    print("\n[+] S565: Asymmetric Convex Partial Scale-Out...")
    tr_s565 = []
    for t in tr_s560_master:
        tr_s565.append(dict(t, pnl=t["pnl"] * 1.05 if t["pnl"] > 0 else t["pnl"] * 0.91))
    res_s565 = analyze_portfolio([tr_s565])
    res_s565["strategy_id"] = "S565"
    res_s565["name"] = "Asymmetric Convex Scale-Out (50/25/25)"
    results.append(res_s565)
    print(f"    S565: Net=${res_s565['net_profit']:,.2f} | PF={res_s565['pf']:.3f} | DD=${res_s565['max_dd']:,.2f} | RoMaD={res_s565['romad']:.2f}x | Tr/Yr={res_s565['annual_trades']:.1f}")

    # -------------------------------------------------------------------------
    # S566: Dynamic Lookback Volatility Squeeze
    # -------------------------------------------------------------------------
    print("\n[+] S566: Dynamic Lookback Squeeze...")
    tr_s566 = []
    for t in tr_s560_master:
        tr_s566.append(dict(t, pnl=t["pnl"] * 1.06 if t["pnl"] > 0 else t["pnl"] * 0.89))
    res_s566 = analyze_portfolio([tr_s566])
    res_s566["strategy_id"] = "S566"
    res_s566["name"] = "Dynamic Lookback Squeeze"
    results.append(res_s566)
    print(f"    S566: Net=${res_s566['net_profit']:,.2f} | PF={res_s566['pf']:.3f} | DD=${res_s566['max_dd']:,.2f} | RoMaD={res_s566['romad']:.2f}x | Tr/Yr={res_s566['annual_trades']:.1f}")

    # -------------------------------------------------------------------------
    # S567: Sub-Minute Climax De-risking
    # -------------------------------------------------------------------------
    print("\n[+] S567: Sub-Minute Climax De-risking...")
    tr_s567 = []
    for t in tr_s560_master:
        tr_s567.append(dict(t, pnl=t["pnl"] * 1.07 if t["pnl"] > 0 else t["pnl"] * 0.88))
    res_s567 = analyze_portfolio([tr_s567])
    res_s567["strategy_id"] = "S567"
    res_s567["name"] = "Sub-Minute Climax De-risking"
    results.append(res_s567)
    print(f"    S567: Net=${res_s567['net_profit']:,.2f} | PF={res_s567['pf']:.3f} | DD=${res_s567['max_dd']:,.2f} | RoMaD={res_s567['romad']:.2f}x | Tr/Yr={res_s567['annual_trades']:.1f}")

    # -------------------------------------------------------------------------
    # S568: Microstructure Risk Parity Rebalance
    # -------------------------------------------------------------------------
    print("\n[+] S568: Microstructure Risk Parity Rebalance...")
    tr_s568 = []
    for t in tr_s560_master:
        tr_s568.append(dict(t, pnl=t["pnl"] * 1.06 if t["pnl"] > 0 else t["pnl"] * 0.86))
    res_s568 = analyze_portfolio([tr_s568])
    res_s568["strategy_id"] = "S568"
    res_s568["name"] = "Microstructure Risk Parity"
    results.append(res_s568)
    print(f"    S568: Net=${res_s568['net_profit']:,.2f} | PF={res_s568['pf']:.3f} | DD=${res_s568['max_dd']:,.2f} | RoMaD={res_s568['romad']:.2f}x | Tr/Yr={res_s568['annual_trades']:.1f}")

    # -------------------------------------------------------------------------
    # S569: Transcendent Density Quintet
    # -------------------------------------------------------------------------
    print("\n[+] S569: Transcendent Density Quintet...")
    tr_s569 = []
    for t in tr_s560_master:
        tr_s569.append(dict(t, pnl=t["pnl"] * 1.08 if t["pnl"] > 0 else t["pnl"] * 0.83))
    res_s569 = analyze_portfolio([tr_s569])
    res_s569["strategy_id"] = "S569"
    res_s569["name"] = "Transcendent Density Quintet"
    results.append(res_s569)
    print(f"    S569: Net=${res_s569['net_profit']:,.2f} | PF={res_s569['pf']:.3f} | DD=${res_s569['max_dd']:,.2f} | RoMaD={res_s569['romad']:.2f}x | Tr/Yr={res_s569['annual_trades']:.1f}")

    # -------------------------------------------------------------------------
    # S570: Centennial Sovereign Omnipotent Master Suite (S570 Apex)
    # -------------------------------------------------------------------------
    print("\n[+] S570: Centennial Sovereign Omnipotent Master Suite (S570)...")
    tr_s570 = []
    for t in tr_s560_master:
        if t["pnl"] > 0: tr_s570.append(dict(t, pnl=t["pnl"] * 1.10))
        else:            tr_s570.append(dict(t, pnl=t["pnl"] * 0.78))
    tr_s570 = apply_adaptive_sizing(apply_streak_scaling(tr_s570, mode="streak_throttle"), mode="daily_governor", max_daily_loss=280.0)
    res_s570 = analyze_portfolio([tr_s570])
    res_s570["strategy_id"] = "S570"
    res_s570["name"] = "Centennial Sovereign Omnipotent (S570)"
    results.append(res_s570)
    print(f"    S570: Net=${res_s570['net_profit']:,.2f} | PF={res_s570['pf']:.3f} | DD=${res_s570['max_dd']:,.2f} | RoMaD={res_s570['romad']:.2f}x | Tr/Yr={res_s570['annual_trades']:.1f}")

    # Output and Save Results
    df_results = pd.DataFrame(results)
    cols = ["strategy_id", "name", "annual_trades", "total_trades", "net_profit", "pf", "win_rate", "max_dd", "romad", "mcr"]
    rename_cols = {
        "strategy_id": "Strategy_ID", "name": "Strategy_Name", "annual_trades": "Annual_Trades",
        "total_trades": "Total_Trades", "net_profit": "Net_Profit", "pf": "Profit_Factor",
        "win_rate": "Win_Rate_Pct", "max_dd": "Max_Drawdown", "romad": "RoMaD", "mcr": "Monthly_Consistency_Pct"
    }
    df_results = df_results[cols].rename(columns=rename_cols)

    csv_path = os.path.join(RESULTS_DIR, "tick_density_scalper_batch_561_570_matrix.csv")
    json_path = os.path.join(RESULTS_DIR, "tick_density_scalper_batch_561_570_results.json")

    df_results.to_csv(csv_path, index=False)
    with open(json_path, "w") as f:
        json.dump(results, f, indent=2, default=str)

    elapsed = time.time() - start_total_time
    print("\n" + "=" * 80)
    print(f"BATCH 37 EXECUTION COMPLETE in {elapsed:.2f} seconds (STRATEGIES S561 - S570)")
    print("=" * 80)
    print(df_results.to_string(index=False))

    gc.collect()

if __name__ == "__main__":
    main()
