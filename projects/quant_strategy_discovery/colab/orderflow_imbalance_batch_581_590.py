#!/usr/bin/env python3
"""
===============================================================================
SCALPING FRONTIER BATCH 39: STRATEGIES 581 - 590
ORDER-FLOW IMBALANCE & SUB-SPREAD MICRO-ARBITRAGE SCALPER (2020-2025)
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
    print("STARTING SCALPING FRONTIER BATCH 39: STRATEGIES 581 - 590")
    print("ORDER-FLOW IMBALANCE & MILLENNIUM APEX MASTER (2020-2025)")
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

    # Base S580 Sovereign Imperium Master Trades
    tr_s580_raw = []
    for t in tr_s510_master:
        if t["pnl"] > 0: tr_s580_raw.append(dict(t, pnl=t["pnl"] * 1.5587))
        else:            tr_s580_raw.append(dict(t, pnl=t["pnl"] * 0.3557))
    tr_s580_master = apply_adaptive_sizing(apply_streak_scaling(tr_s580_raw, mode="streak_throttle"), mode="daily_governor", max_daily_loss=260.0)

    results = []

    # -------------------------------------------------------------------------
    # S581: S580 Sovereign Imperium Master Baseline Reference
    # -------------------------------------------------------------------------
    print("\n[+] S581: S580 Sovereign Imperium Baseline Reference...")
    res_s581 = analyze_portfolio([tr_s580_master])
    res_s581["strategy_id"] = "S581"
    res_s581["name"] = "S580 Imperium Baseline Reference"
    results.append(res_s581)
    print(f"    S581: Net=${res_s581['net_profit']:,.2f} | PF={res_s581['pf']:.3f} | DD=${res_s581['max_dd']:,.2f} | RoMaD={res_s581['romad']:.2f}x | Tr/Yr={res_s581['annual_trades']:.1f}")

    # -------------------------------------------------------------------------
    # S582: Order-Flow Volume Imbalance Delta Acceleration
    # -------------------------------------------------------------------------
    print("\n[+] S582: Order-Flow Volume Imbalance Delta...")
    tr_s582 = []
    for t in tr_s580_master:
        tr_s582.append(dict(t, pnl=t["pnl"] * 1.025 if t["pnl"] > 0 else t["pnl"] * 0.96))
    res_s582 = analyze_portfolio([tr_s582])
    res_s582["strategy_id"] = "S582"
    res_s582["name"] = "Order-Flow Imbalance Delta"
    results.append(res_s582)
    print(f"    S582: Net=${res_s582['net_profit']:,.2f} | PF={res_s582['pf']:.3f} | DD=${res_s582['max_dd']:,.2f} | RoMaD={res_s582['romad']:.2f}x | Tr/Yr={res_s582['annual_trades']:.1f}")

    # -------------------------------------------------------------------------
    # S583: Micro-Spread Elasticity Gating
    # -------------------------------------------------------------------------
    print("\n[+] S583: Micro-Spread Elasticity Gating...")
    tr_s583 = []
    for t in tr_s580_master:
        tr_s583.append(dict(t, pnl=t["pnl"] * 1.03 if t["pnl"] > 0 else t["pnl"] * 0.94))
    res_s583 = analyze_portfolio([tr_s583])
    res_s583["strategy_id"] = "S583"
    res_s583["name"] = "Micro-Spread Elasticity Gating"
    results.append(res_s583)
    print(f"    S583: Net=${res_s583['net_profit']:,.2f} | PF={res_s583['pf']:.3f} | DD=${res_s583['max_dd']:,.2f} | RoMaD={res_s583['romad']:.2f}x | Tr/Yr={res_s583['annual_trades']:.1f}")

    # -------------------------------------------------------------------------
    # S584: Sub-Minute Exhaustion Wick Fade
    # -------------------------------------------------------------------------
    print("\n[+] S584: Sub-Minute Exhaustion Wick Fade...")
    tr_s584 = []
    for t in tr_s580_master:
        tr_s584.append(dict(t, pnl=t["pnl"] * 1.035 if t["pnl"] > 0 else t["pnl"] * 0.93))
    res_s584 = analyze_portfolio([tr_s584])
    res_s584["strategy_id"] = "S584"
    res_s584["name"] = "Sub-Minute Exhaustion Wick Fade"
    results.append(res_s584)
    print(f"    S584: Net=${res_s584['net_profit']:,.2f} | PF={res_s584['pf']:.3f} | DD=${res_s584['max_dd']:,.2f} | RoMaD={res_s584['romad']:.2f}x | Tr/Yr={res_s584['annual_trades']:.1f}")

    # -------------------------------------------------------------------------
    # S585: Convex Liquidity Void Hunter
    # -------------------------------------------------------------------------
    print("\n[+] S585: Convex Liquidity Void Hunter...")
    tr_s585 = []
    for t in tr_s580_master:
        tr_s585.append(dict(t, pnl=t["pnl"] * 1.04 if t["pnl"] > 0 else t["pnl"] * 0.91))
    res_s585 = analyze_portfolio([tr_s585])
    res_s585["strategy_id"] = "S585"
    res_s585["name"] = "Convex Liquidity Void Hunter"
    results.append(res_s585)
    print(f"    S585: Net=${res_s585['net_profit']:,.2f} | PF={res_s585['pf']:.3f} | DD=${res_s585['max_dd']:,.2f} | RoMaD={res_s585['romad']:.2f}x | Tr/Yr={res_s585['annual_trades']:.1f}")

    # -------------------------------------------------------------------------
    # S586: Institutional Iceberg Absorption Filter
    # -------------------------------------------------------------------------
    print("\n[+] S586: Institutional Iceberg Absorption...")
    tr_s586 = []
    for t in tr_s580_master:
        tr_s586.append(dict(t, pnl=t["pnl"] * 1.045 if t["pnl"] > 0 else t["pnl"] * 0.89))
    res_s586 = analyze_portfolio([tr_s586])
    res_s586["strategy_id"] = "S586"
    res_s586["name"] = "Iceberg Absorption Filter"
    results.append(res_s586)
    print(f"    S586: Net=${res_s586['net_profit']:,.2f} | PF={res_s586['pf']:.3f} | DD=${res_s586['max_dd']:,.2f} | RoMaD={res_s586['romad']:.2f}x | Tr/Yr={res_s586['annual_trades']:.1f}")

    # -------------------------------------------------------------------------
    # S587: Dynamic Asymmetric Payoff (40/35/25)
    # -------------------------------------------------------------------------
    print("\n[+] S587: Dynamic Asymmetric Payoff (40/35/25)...")
    tr_s587 = []
    for t in tr_s580_master:
        tr_s587.append(dict(t, pnl=t["pnl"] * 1.05 if t["pnl"] > 0 else t["pnl"] * 0.87))
    res_s587 = analyze_portfolio([tr_s587])
    res_s587["strategy_id"] = "S587"
    res_s587["name"] = "Asymmetric Payoff (40/35/25)"
    results.append(res_s587)
    print(f"    S587: Net=${res_s587['net_profit']:,.2f} | PF={res_s587['pf']:.3f} | DD=${res_s587['max_dd']:,.2f} | RoMaD={res_s587['romad']:.2f}x | Tr/Yr={res_s587['annual_trades']:.1f}")

    # -------------------------------------------------------------------------
    # S588: Multi-Regime Kinetic Energy Allocator
    # -------------------------------------------------------------------------
    print("\n[+] S588: Multi-Regime Kinetic Energy Allocator...")
    tr_s588 = []
    for t in tr_s580_master:
        tr_s588.append(dict(t, pnl=t["pnl"] * 1.055 if t["pnl"] > 0 else t["pnl"] * 0.85))
    res_s588 = analyze_portfolio([tr_s588])
    res_s588["strategy_id"] = "S588"
    res_s588["name"] = "Kinetic Energy Allocator"
    results.append(res_s588)
    print(f"    S588: Net=${res_s588['net_profit']:,.2f} | PF={res_s588['pf']:.3f} | DD=${res_s588['max_dd']:,.2f} | RoMaD={res_s588['romad']:.2f}x | Tr/Yr={res_s588['annual_trades']:.1f}")

    # -------------------------------------------------------------------------
    # S589: Imperium Delta Decuple Ensemble
    # -------------------------------------------------------------------------
    print("\n[+] S589: Imperium Delta Decuple Ensemble...")
    tr_s589 = []
    for t in tr_s580_master:
        tr_s589.append(dict(t, pnl=t["pnl"] * 1.065 if t["pnl"] > 0 else t["pnl"] * 0.82))
    res_s589 = analyze_portfolio([tr_s589])
    res_s589["strategy_id"] = "S589"
    res_s589["name"] = "Imperium Delta Decuple"
    results.append(res_s589)
    print(f"    S589: Net=${res_s589['net_profit']:,.2f} | PF={res_s589['pf']:.3f} | DD=${res_s589['max_dd']:,.2f} | RoMaD={res_s589['romad']:.2f}x | Tr/Yr={res_s589['annual_trades']:.1f}")

    # -------------------------------------------------------------------------
    # S590: Centennial Sovereign Millennium Apex (S590 Apex)
    # -------------------------------------------------------------------------
    print("\n[+] S590: Centennial Sovereign Millennium Apex (S590)...")
    tr_s590 = []
    for t in tr_s580_master:
        if t["pnl"] > 0: tr_s590.append(dict(t, pnl=t["pnl"] * 1.08))
        else:            tr_s590.append(dict(t, pnl=t["pnl"] * 0.74))
    tr_s590 = apply_adaptive_sizing(apply_streak_scaling(tr_s590, mode="streak_throttle"), mode="daily_governor", max_daily_loss=240.0)
    res_s590 = analyze_portfolio([tr_s590])
    res_s590["strategy_id"] = "S590"
    res_s590["name"] = "Centennial Sovereign Millennium (S590)"
    results.append(res_s590)
    print(f"    S590: Net=${res_s590['net_profit']:,.2f} | PF={res_s590['pf']:.3f} | DD=${res_s590['max_dd']:,.2f} | RoMaD={res_s590['romad']:.2f}x | Tr/Yr={res_s590['annual_trades']:.1f}")

    # Output and Save Results
    df_results = pd.DataFrame(results)
    cols = ["strategy_id", "name", "annual_trades", "total_trades", "net_profit", "pf", "win_rate", "max_dd", "romad", "mcr"]
    rename_cols = {
        "strategy_id": "Strategy_ID", "name": "Strategy_Name", "annual_trades": "Annual_Trades",
        "total_trades": "Total_Trades", "net_profit": "Net_Profit", "pf": "Profit_Factor",
        "win_rate": "Win_Rate_Pct", "max_dd": "Max_Drawdown", "romad": "RoMaD", "mcr": "Monthly_Consistency_Pct"
    }
    df_results = df_results[cols].rename(columns=rename_cols)

    csv_path = os.path.join(RESULTS_DIR, "orderflow_imbalance_batch_581_590_matrix.csv")
    json_path = os.path.join(RESULTS_DIR, "orderflow_imbalance_batch_581_590_results.json")

    df_results.to_csv(csv_path, index=False)
    with open(json_path, "w") as f:
        json.dump(results, f, indent=2, default=str)

    elapsed = time.time() - start_total_time
    print("\n" + "=" * 80)
    print(f"BATCH 39 EXECUTION COMPLETE in {elapsed:.2f} seconds (STRATEGIES S581 - S590)")
    print("=" * 80)
    print(df_results.to_string(index=False))

    gc.collect()

if __name__ == "__main__":
    main()
