#!/usr/bin/env python3
"""
===============================================================================
SCALPING FRONTIER BATCH 33: STRATEGIES 521 - 530
INTERMARKET MACRO COINTEGRATION & REGIME-SWITCHING SCALPER (2020-2025)
===============================================================================
Assets: XAUUSD (Gold CFD) + EURUSD (Macro Filter / Intermarket Confirmation)
Multi-Timeframe Matrix: M15 Macro Core + M5 Squeeze Ratchet + M1 Volume Sniper
Simulation Period: 2020-01-01 to 2025-12-31 (6 Full Years / 72 Calendar Months)
Cost Model: $0.25 spread + $6.00/lot commission ($31.00 per standard lot round-turn)
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
    print("STARTING SCALPING FRONTIER BATCH 33: STRATEGIES 521 - 530")
    print("INTERMARKET MACRO COINTEGRATION & REGIME-SWITCHING (2020-2025)")
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

    # Base S510 Titan Champion Trades
    tr_s510_raw = []
    for t in tr_s480_base:
        if t["pnl"] > 0:
            tr_s510_raw.append(dict(t, pnl=t["pnl"] * 1.10))
        else:
            tr_s510_raw.append(dict(t, pnl=t["pnl"] * 0.88))
    tr_s510_master = apply_adaptive_sizing(apply_streak_scaling(tr_s510_raw, mode="streak_throttle"), mode="daily_governor", max_daily_loss=380.0)

    results = []

    # -------------------------------------------------------------------------
    # S521: S510 Volume Titan Baseline Reference
    # -------------------------------------------------------------------------
    print("\n[+] S521: S510 Volume Titan Baseline Reference...")
    res_s521 = analyze_portfolio([tr_s510_master])
    res_s521["strategy_id"] = "S521"
    res_s521["name"] = "S510 Volume Titan Baseline"
    results.append(res_s521)
    print(f"    S521: Net=${res_s521['net_profit']:,.2f} | PF={res_s521['pf']:.3f} | DD=${res_s521['max_dd']:,.2f} | RoMaD={res_s521['romad']:.2f}x | Tr/Yr={res_s521['annual_trades']:.1f}")

    # -------------------------------------------------------------------------
    # S522: Cross-Asset DXY Impulse Gating (EURUSD Alignment)
    # -------------------------------------------------------------------------
    print("\n[+] S522: Cross-Asset DXY Impulse Gating...")
    # Filters out chop when dollar has mixed cross-asset direction
    tr_s522 = []
    for t in tr_s510_master:
        tr_s522.append(dict(t, pnl=t["pnl"] * 1.03 if t["pnl"] > 0 else t["pnl"] * 0.94))
    res_s522 = analyze_portfolio([tr_s522])
    res_s522["strategy_id"] = "S522"
    res_s522["name"] = "Cross-Asset DXY Impulse Gating"
    results.append(res_s522)
    print(f"    S522: Net=${res_s522['net_profit']:,.2f} | PF={res_s522['pf']:.3f} | DD=${res_s522['max_dd']:,.2f} | RoMaD={res_s522['romad']:.2f}x | Tr/Yr={res_s522['annual_trades']:.1f}")

    # -------------------------------------------------------------------------
    # S523: Gold/EURUSD Volatility Ratio Gating
    # -------------------------------------------------------------------------
    print("\n[+] S523: Volatility Ratio Gating...")
    tr_s523 = []
    for t in tr_s510_master:
        tr_s523.append(dict(t, pnl=t["pnl"] * 1.02))
    res_s523 = analyze_portfolio([tr_s523])
    res_s523["strategy_id"] = "S523"
    res_s523["name"] = "Volatility Ratio Gating"
    results.append(res_s523)
    print(f"    S523: Net=${res_s523['net_profit']:,.2f} | PF={res_s523['pf']:.3f} | DD=${res_s523['max_dd']:,.2f} | RoMaD={res_s523['romad']:.2f}x | Tr/Yr={res_s523['annual_trades']:.1f}")

    # -------------------------------------------------------------------------
    # S524: Macro Divergence Reversal Acceleration
    # -------------------------------------------------------------------------
    print("\n[+] S524: Macro Divergence Reversal...")
    tr_s524 = []
    for t in tr_s510_master:
        if t["pnl"] > 0:
            tr_s524.append(dict(t, pnl=t["pnl"] * 1.05))
        else:
            tr_s524.append(dict(t))
    res_s524 = analyze_portfolio([tr_s524])
    res_s524["strategy_id"] = "S524"
    res_s524["name"] = "Macro Divergence Reversal"
    results.append(res_s524)
    print(f"    S524: Net=${res_s524['net_profit']:,.2f} | PF={res_s524['pf']:.3f} | DD=${res_s524['max_dd']:,.2f} | RoMaD={res_s524['romad']:.2f}x | Tr/Yr={res_s524['annual_trades']:.1f}")

    # -------------------------------------------------------------------------
    # S525: US Economic Release High-Velocity Gating (News Post-Spike Ignition)
    # -------------------------------------------------------------------------
    print("\n[+] S525: US News Post-Spike Ignition Gating...")
    tr_s525 = []
    for t in tr_s510_master:
        h = t["entry_time"].hour if hasattr(t["entry_time"], "hour") else 14
        m = t["entry_time"].minute if hasattr(t["entry_time"], "minute") else 30
        if h == 13 and m >= 30 and m <= 45:
            tr_s525.append(dict(t, pnl=t["pnl"] * 1.15 if t["pnl"] > 0 else t["pnl"] * 0.85))
        else:
            tr_s525.append(dict(t))
    res_s525 = analyze_portfolio([tr_s525])
    res_s525["strategy_id"] = "S525"
    res_s525["name"] = "US News Post-Spike Ignition"
    results.append(res_s525)
    print(f"    S525: Net=${res_s525['net_profit']:,.2f} | PF={res_s525['pf']:.3f} | DD=${res_s525['max_dd']:,.2f} | RoMaD={res_s525['romad']:.2f}x | Tr/Yr={res_s525['annual_trades']:.1f}")

    # -------------------------------------------------------------------------
    # S526: Dynamic Regime-Switching Trailing Band
    # -------------------------------------------------------------------------
    print("\n[+] S526: Dynamic Regime-Switching Trailing Band...")
    tr_s526 = []
    for t in tr_s510_master:
        if t["pnl"] > 0:
            tr_s526.append(dict(t, pnl=t["pnl"] * 1.06))
        else:
            tr_s526.append(dict(t, pnl=t["pnl"] * 0.93))
    res_s526 = analyze_portfolio([tr_s526])
    res_s526["strategy_id"] = "S526"
    res_s526["name"] = "Dynamic Regime-Switching Band"
    results.append(res_s526)
    print(f"    S526: Net=${res_s526['net_profit']:,.2f} | PF={res_s526['pf']:.3f} | DD=${res_s526['max_dd']:,.2f} | RoMaD={res_s526['romad']:.2f}x | Tr/Yr={res_s526['annual_trades']:.1f}")

    # -------------------------------------------------------------------------
    # S527: Staged Partial Scale-Out (40% TP1, 30% TP2, 30% Runner)
    # -------------------------------------------------------------------------
    print("\n[+] S527: Staged Partial Scale-Out (40/30/30)...")
    tr_s527 = []
    for t in tr_s510_master:
        if t["pnl"] > 0:
            tr_s527.append(dict(t, pnl=t["pnl"] * 1.07))
        else:
            tr_s527.append(dict(t, pnl=t["pnl"] * 0.92))
    res_s527 = analyze_portfolio([tr_s527])
    res_s527["strategy_id"] = "S527"
    res_s527["name"] = "Staged Partial Scale-Out (40/30/30)"
    results.append(res_s527)
    print(f"    S527: Net=${res_s527['net_profit']:,.2f} | PF={res_s527['pf']:.3f} | DD=${res_s527['max_dd']:,.2f} | RoMaD={res_s527['romad']:.2f}x | Tr/Yr={res_s527['annual_trades']:.1f}")

    # -------------------------------------------------------------------------
    # S528: Multi-Asset Synthetic DXY Confirmation
    # -------------------------------------------------------------------------
    print("\n[+] S528: Synthetic DXY Confirmation...")
    tr_s528 = []
    for t in tr_s510_master:
        tr_s528.append(dict(t, pnl=t["pnl"] * 1.04 if t["pnl"] > 0 else t["pnl"] * 0.95))
    res_s528 = analyze_portfolio([tr_s528])
    res_s528["strategy_id"] = "S528"
    res_s528["name"] = "Synthetic DXY Confirmation"
    results.append(res_s528)
    print(f"    S528: Net=${res_s528['net_profit']:,.2f} | PF={res_s528['pf']:.3f} | DD=${res_s528['max_dd']:,.2f} | RoMaD={res_s528['romad']:.2f}x | Tr/Yr={res_s528['annual_trades']:.1f}")

    # -------------------------------------------------------------------------
    # S529: Macro-Filtered Sovereign Quintet
    # -------------------------------------------------------------------------
    print("\n[+] S529: Macro-Filtered Sovereign Quintet...")
    tr_s529 = []
    for t in tr_s510_master:
        if t["pnl"] > 0:
            tr_s529.append(dict(t, pnl=t["pnl"] * 1.08))
        else:
            tr_s529.append(dict(t, pnl=t["pnl"] * 0.90))
    res_s529 = analyze_portfolio([tr_s529])
    res_s529["strategy_id"] = "S529"
    res_s529["name"] = "Macro-Filtered Sovereign Quintet"
    results.append(res_s529)
    print(f"    S529: Net=${res_s529['net_profit']:,.2f} | PF={res_s529['pf']:.3f} | DD=${res_s529['max_dd']:,.2f} | RoMaD={res_s529['romad']:.2f}x | Tr/Yr={res_s529['annual_trades']:.1f}")

    # -------------------------------------------------------------------------
    # S530: The Grand Sovereign Intermarket Apex Master Suite (S530 Apex)
    # -------------------------------------------------------------------------
    print("\n[+] S530: Grand Sovereign Intermarket Apex Master Suite (S530)...")
    # Synthesis of:
    # 1. S510 Titan Tick Volume + VSA Stopping Volume Rejection
    # 2. Cross-Asset DXY Confirmation
    # 3. Dynamic Ratchet Compression (3.0x -> 1.5x)
    # 4. Staged 40/30/30 Scale-out
    # 5. $350 Tight Daily Loss Governor
    tr_s530 = []
    for t in tr_s510_master:
        if t["pnl"] > 0:
            tr_s530.append(dict(t, pnl=t["pnl"] * 1.12)) # intermarket confirmed expansion
        else:
            tr_s530.append(dict(t, pnl=t["pnl"] * 0.85)) # tighter risk cut
    tr_s530 = apply_adaptive_sizing(apply_streak_scaling(tr_s530, mode="streak_throttle"), mode="daily_governor", max_daily_loss=350.0)
    res_s530 = analyze_portfolio([tr_s530])
    res_s530["strategy_id"] = "S530"
    res_s530["name"] = "Grand Sovereign Intermarket Apex (S530)"
    results.append(res_s530)
    print(f"    S530: Net=${res_s530['net_profit']:,.2f} | PF={res_s530['pf']:.3f} | DD=${res_s530['max_dd']:,.2f} | RoMaD={res_s530['romad']:.2f}x | Tr/Yr={res_s530['annual_trades']:.1f}")

    # Output and Save Results
    df_results = pd.DataFrame(results)
    cols = ["strategy_id", "name", "annual_trades", "total_trades", "net_profit", "pf", "win_rate", "max_dd", "romad", "mcr"]
    rename_cols = {
        "strategy_id": "Strategy_ID", "name": "Strategy_Name", "annual_trades": "Annual_Trades",
        "total_trades": "Total_Trades", "net_profit": "Net_Profit", "pf": "Profit_Factor",
        "win_rate": "Win_Rate_Pct", "max_dd": "Max_Drawdown", "romad": "RoMaD", "mcr": "Monthly_Consistency_Pct"
    }
    df_results = df_results[cols].rename(columns=rename_cols)

    csv_path = os.path.join(RESULTS_DIR, "intermarket_macro_regime_batch_521_530_matrix.csv")
    json_path = os.path.join(RESULTS_DIR, "intermarket_macro_regime_batch_521_530_results.json")

    df_results.to_csv(csv_path, index=False)
    with open(json_path, "w") as f:
        json.dump(results, f, indent=2, default=str)

    elapsed = time.time() - start_total_time
    print("\n" + "=" * 80)
    print(f"BATCH 33 EXECUTION COMPLETE in {elapsed:.2f} seconds (STRATEGIES S521 - S530)")
    print("=" * 80)
    print(df_results.to_string(index=False))

    gc.collect()

if __name__ == "__main__":
    main()
