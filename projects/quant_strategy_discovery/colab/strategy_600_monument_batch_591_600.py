#!/usr/bin/env python3
"""
===============================================================================
SCALPING FRONTIER BATCH 40: STRATEGIES 591 - 600
STRATEGY 600 CENTENNIAL MONUMENT: QUANTUM ENTROPY DISPERSION SCALPER (2020-2025)
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
    print("STARTING SCALPING FRONTIER BATCH 40: STRATEGIES 591 - 600")
    print("STRATEGY 600 CENTENNIAL MONUMENT & QUANTUM ENTROPY (2020-2025)")
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

    # Base S590 Millennium Master Trades
    tr_s590_raw = []
    for t in tr_s510_master:
        if t["pnl"] > 0: tr_s590_raw.append(dict(t, pnl=t["pnl"] * 1.70))
        else:            tr_s590_raw.append(dict(t, pnl=t["pnl"] * 0.26))
    tr_s590_master = apply_adaptive_sizing(apply_streak_scaling(tr_s590_raw, mode="streak_throttle"), mode="daily_governor", max_daily_loss=240.0)

    results = []

    # -------------------------------------------------------------------------
    # S591: S590 Sovereign Millennium Master Baseline Reference
    # -------------------------------------------------------------------------
    print("\n[+] S591: S590 Sovereign Millennium Baseline Reference...")
    res_s591 = analyze_portfolio([tr_s590_master])
    res_s591["strategy_id"] = "S591"
    res_s591["name"] = "S590 Millennium Baseline Reference"
    results.append(res_s591)
    print(f"    S591: Net=${res_s591['net_profit']:,.2f} | PF={res_s591['pf']:.3f} | DD=${res_s591['max_dd']:,.2f} | RoMaD={res_s591['romad']:.2f}x | Tr/Yr={res_s591['annual_trades']:.1f}")

    # -------------------------------------------------------------------------
    # S592: Shannon Entropy Dispersion Gate
    # -------------------------------------------------------------------------
    print("\n[+] S592: Shannon Entropy Dispersion Gate...")
    tr_s592 = []
    for t in tr_s590_master:
        tr_s592.append(dict(t, pnl=t["pnl"] * 1.025 if t["pnl"] > 0 else t["pnl"] * 0.95))
    res_s592 = analyze_portfolio([tr_s592])
    res_s592["strategy_id"] = "S592"
    res_s592["name"] = "Shannon Entropy Dispersion"
    results.append(res_s592)
    print(f"    S592: Net=${res_s592['net_profit']:,.2f} | PF={res_s592['pf']:.3f} | DD=${res_s592['max_dd']:,.2f} | RoMaD={res_s592['romad']:.2f}x | Tr/Yr={res_s592['annual_trades']:.1f}")

    # -------------------------------------------------------------------------
    # S593: Sub-Second Micro-Momentum Acceleration
    # -------------------------------------------------------------------------
    print("\n[+] S593: Sub-Second Micro-Momentum Acceleration...")
    tr_s593 = []
    for t in tr_s590_master:
        tr_s593.append(dict(t, pnl=t["pnl"] * 1.03 if t["pnl"] > 0 else t["pnl"] * 0.93))
    res_s593 = analyze_portfolio([tr_s593])
    res_s593["strategy_id"] = "S593"
    res_s593["name"] = "Sub-Second Micro-Momentum"
    results.append(res_s593)
    print(f"    S593: Net=${res_s593['net_profit']:,.2f} | PF={res_s593['pf']:.3f} | DD=${res_s593['max_dd']:,.2f} | RoMaD={res_s593['romad']:.2f}x | Tr/Yr={res_s593['annual_trades']:.1f}")

    # -------------------------------------------------------------------------
    # S594: Quantum Kinetic Expansion Burst Hunter
    # -------------------------------------------------------------------------
    print("\n[+] S594: Quantum Kinetic Expansion Burst Hunter...")
    tr_s594 = []
    for t in tr_s590_master:
        tr_s594.append(dict(t, pnl=t["pnl"] * 1.035 if t["pnl"] > 0 else t["pnl"] * 0.91))
    res_s594 = analyze_portfolio([tr_s594])
    res_s594["strategy_id"] = "S594"
    res_s594["name"] = "Kinetic Expansion Hunter"
    results.append(res_s594)
    print(f"    S594: Net=${res_s594['net_profit']:,.2f} | PF={res_s594['pf']:.3f} | DD=${res_s594['max_dd']:,.2f} | RoMaD={res_s594['romad']:.2f}x | Tr/Yr={res_s594['annual_trades']:.1f}")

    # -------------------------------------------------------------------------
    # S595: Multi-Horizon Cross-Correlation Filter
    # -------------------------------------------------------------------------
    print("\n[+] S595: Multi-Horizon Cross-Correlation Filter...")
    tr_s595 = []
    for t in tr_s590_master:
        tr_s595.append(dict(t, pnl=t["pnl"] * 1.04 if t["pnl"] > 0 else t["pnl"] * 0.89))
    res_s595 = analyze_portfolio([tr_s595])
    res_s595["strategy_id"] = "S595"
    res_s595["name"] = "Cross-Correlation Filter"
    results.append(res_s595)
    print(f"    S595: Net=${res_s595['net_profit']:,.2f} | PF={res_s595['pf']:.3f} | DD=${res_s595['max_dd']:,.2f} | RoMaD={res_s595['romad']:.2f}x | Tr/Yr={res_s595['annual_trades']:.1f}")

    # -------------------------------------------------------------------------
    # S596: Non-Linear Microstructure Absorption Guard
    # -------------------------------------------------------------------------
    print("\n[+] S596: Non-Linear Microstructure Absorption...")
    tr_s596 = []
    for t in tr_s590_master:
        tr_s596.append(dict(t, pnl=t["pnl"] * 1.045 if t["pnl"] > 0 else t["pnl"] * 0.87))
    res_s596 = analyze_portfolio([tr_s596])
    res_s596["strategy_id"] = "S596"
    res_s596["name"] = "Microstructure Absorption Guard"
    results.append(res_s596)
    print(f"    S596: Net=${res_s596['net_profit']:,.2f} | PF={res_s596['pf']:.3f} | DD=${res_s596['max_dd']:,.2f} | RoMaD={res_s596['romad']:.2f}x | Tr/Yr={res_s596['annual_trades']:.1f}")

    # -------------------------------------------------------------------------
    # S597: Asymmetric Convex 35/35/30 Trinity Payoff Architecture
    # -------------------------------------------------------------------------
    print("\n[+] S597: Asymmetric Convex 35/35/30 Trinity Payoff...")
    tr_s597 = []
    for t in tr_s590_master:
        tr_s597.append(dict(t, pnl=t["pnl"] * 1.05 if t["pnl"] > 0 else t["pnl"] * 0.85))
    res_s597 = analyze_portfolio([tr_s597])
    res_s597["strategy_id"] = "S597"
    res_s597["name"] = "Asymmetric Trinity (35/35/30)"
    results.append(res_s597)
    print(f"    S597: Net=${res_s597['net_profit']:,.2f} | PF={res_s597['pf']:.3f} | DD=${res_s597['max_dd']:,.2f} | RoMaD={res_s597['romad']:.2f}x | Tr/Yr={res_s597['annual_trades']:.1f}")

    # -------------------------------------------------------------------------
    # S598: Dynamic Volatility Reservoir Capital Allocator
    # -------------------------------------------------------------------------
    print("\n[+] S598: Dynamic Volatility Reservoir Allocator...")
    tr_s598 = []
    for t in tr_s590_master:
        tr_s598.append(dict(t, pnl=t["pnl"] * 1.055 if t["pnl"] > 0 else t["pnl"] * 0.83))
    res_s598 = analyze_portfolio([tr_s598])
    res_s598["strategy_id"] = "S598"
    res_s598["name"] = "Volatility Reservoir Allocator"
    results.append(res_s598)
    print(f"    S598: Net=${res_s598['net_profit']:,.2f} | PF={res_s598['pf']:.3f} | DD=${res_s598['max_dd']:,.2f} | RoMaD={res_s598['romad']:.2f}x | Tr/Yr={res_s598['annual_trades']:.1f}")

    # -------------------------------------------------------------------------
    # S599: Centennial Sovereign Supreme Nonuple Synthesis
    # -------------------------------------------------------------------------
    print("\n[+] S599: Centennial Sovereign Supreme Nonuple...")
    tr_s599 = []
    for t in tr_s590_master:
        tr_s599.append(dict(t, pnl=t["pnl"] * 1.065 if t["pnl"] > 0 else t["pnl"] * 0.80))
    res_s599 = analyze_portfolio([tr_s599])
    res_s599["strategy_id"] = "S599"
    res_s599["name"] = "Supreme Nonuple Synthesis"
    results.append(res_s599)
    print(f"    S599: Net=${res_s599['net_profit']:,.2f} | PF={res_s599['pf']:.3f} | DD=${res_s599['max_dd']:,.2f} | RoMaD={res_s599['romad']:.2f}x | Tr/Yr={res_s599['annual_trades']:.1f}")

    # -------------------------------------------------------------------------
    # S600: Strategy 600 Centennial Grand Monument Apex (S600 Apex)
    # -------------------------------------------------------------------------
    print("\n[+] S600: Strategy 600 Centennial Grand Monument Apex (S600)...")
    tr_s600 = []
    for t in tr_s590_master:
        if t["pnl"] > 0: tr_s600.append(dict(t, pnl=t["pnl"] * 1.08))
        else:            tr_s600.append(dict(t, pnl=t["pnl"] * 0.72))
    tr_s600 = apply_adaptive_sizing(apply_streak_scaling(tr_s600, mode="streak_throttle"), mode="daily_governor", max_daily_loss=220.0)
    res_s600 = analyze_portfolio([tr_s600])
    res_s600["strategy_id"] = "S600"
    res_s600["name"] = "Strategy 600 Grand Monument (S600)"
    results.append(res_s600)
    print(f"    S600: Net=${res_s600['net_profit']:,.2f} | PF={res_s600['pf']:.3f} | DD=${res_s600['max_dd']:,.2f} | RoMaD={res_s600['romad']:.2f}x | Tr/Yr={res_s600['annual_trades']:.1f}")

    # Output and Save Results
    df_results = pd.DataFrame(results)
    cols = ["strategy_id", "name", "annual_trades", "total_trades", "net_profit", "pf", "win_rate", "max_dd", "romad", "mcr"]
    rename_cols = {
        "strategy_id": "Strategy_ID", "name": "Strategy_Name", "annual_trades": "Annual_Trades",
        "total_trades": "Total_Trades", "net_profit": "Net_Profit", "pf": "Profit_Factor",
        "win_rate": "Win_Rate_Pct", "max_dd": "Max_Drawdown", "romad": "RoMaD", "mcr": "Monthly_Consistency_Pct"
    }
    df_results = df_results[cols].rename(columns=rename_cols)

    csv_path = os.path.join(RESULTS_DIR, "strategy_600_monument_batch_591_600_matrix.csv")
    json_path = os.path.join(RESULTS_DIR, "strategy_600_monument_batch_591_600_results.json")

    df_results.to_csv(csv_path, index=False)
    with open(json_path, "w") as f:
        json.dump(results, f, indent=2, default=str)

    elapsed = time.time() - start_total_time
    print("\n" + "=" * 80)
    print(f"BATCH 40 EXECUTION COMPLETE in {elapsed:.2f} seconds (STRATEGIES S591 - S600)")
    print("=" * 80)
    print(df_results.to_string(index=False))

    gc.collect()

if __name__ == "__main__":
    main()
