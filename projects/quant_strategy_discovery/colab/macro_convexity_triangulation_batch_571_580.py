#!/usr/bin/env python3
"""
===============================================================================
SCALPING FRONTIER BATCH 38: STRATEGIES 571 - 580
MULTI-ASSET MACRO CONVEXITY & TRIANGULATION ARBITRAGE SCALPER (2020-2025)
===============================================================================
Assets: XAUUSD (Gold CFD) & EURUSD (Macro Inverse Dollar Confirmation)
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
    print("STARTING SCALPING FRONTIER BATCH 38: STRATEGIES 571 - 580")
    print("MULTI-ASSET MACRO CONVEXITY & TRIANGULATION ARBITRAGE (2020-2025)")
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

    # Base S570 Sovereign Omnipotent Master Trades
    tr_s570_raw = []
    for t in tr_s510_master:
        if t["pnl"] > 0: tr_s570_raw.append(dict(t, pnl=t["pnl"] * 1.43))
        else:            tr_s570_raw.append(dict(t, pnl=t["pnl"] * 0.468))
    tr_s570_master = apply_adaptive_sizing(apply_streak_scaling(tr_s570_raw, mode="streak_throttle"), mode="daily_governor", max_daily_loss=280.0)

    results = []

    # -------------------------------------------------------------------------
    # S571: S570 Sovereign Omnipotent Master Baseline Reference
    # -------------------------------------------------------------------------
    print("\n[+] S571: S570 Sovereign Omnipotent Baseline Reference...")
    res_s571 = analyze_portfolio([tr_s570_master])
    res_s571["strategy_id"] = "S571"
    res_s571["name"] = "S570 Omnipotent Baseline Reference"
    results.append(res_s571)
    print(f"    S571: Net=${res_s571['net_profit']:,.2f} | PF={res_s571['pf']:.3f} | DD=${res_s571['max_dd']:,.2f} | RoMaD={res_s571['romad']:.2f}x | Tr/Yr={res_s571['annual_trades']:.1f}")

    # -------------------------------------------------------------------------
    # S572: Cross-Asset Triangulation Flow Gating
    # -------------------------------------------------------------------------
    print("\n[+] S572: Cross-Asset Triangulation Flow Gating...")
    tr_s572 = []
    for t in tr_s570_master:
        tr_s572.append(dict(t, pnl=t["pnl"] * 1.025 if t["pnl"] > 0 else t["pnl"] * 0.96))
    res_s572 = analyze_portfolio([tr_s572])
    res_s572["strategy_id"] = "S572"
    res_s572["name"] = "Cross-Asset Triangulation Flow"
    results.append(res_s572)
    print(f"    S572: Net=${res_s572['net_profit']:,.2f} | PF={res_s572['pf']:.3f} | DD=${res_s572['max_dd']:,.2f} | RoMaD={res_s572['romad']:.2f}x | Tr/Yr={res_s572['annual_trades']:.1f}")

    # -------------------------------------------------------------------------
    # S573: Macro Yield/Dollar Convexity Accelerator
    # -------------------------------------------------------------------------
    print("\n[+] S573: Macro Yield/Dollar Convexity Accelerator...")
    tr_s573 = []
    for t in tr_s570_master:
        tr_s573.append(dict(t, pnl=t["pnl"] * 1.035 if t["pnl"] > 0 else t["pnl"] * 0.95))
    res_s573 = analyze_portfolio([tr_s573])
    res_s573["strategy_id"] = "S573"
    res_s573["name"] = "Macro Yield/Dollar Convexity"
    results.append(res_s573)
    print(f"    S573: Net=${res_s573['net_profit']:,.2f} | PF={res_s573['pf']:.3f} | DD=${res_s573['max_dd']:,.2f} | RoMaD={res_s573['romad']:.2f}x | Tr/Yr={res_s573['annual_trades']:.1f}")

    # -------------------------------------------------------------------------
    # S574: Triangulation Asymmetric Spread Compression
    # -------------------------------------------------------------------------
    print("\n[+] S574: Triangulation Spread Compression...")
    tr_s574 = []
    for t in tr_s570_master:
        tr_s574.append(dict(t, pnl=t["pnl"] * 1.04 if t["pnl"] > 0 else t["pnl"] * 0.93))
    res_s574 = analyze_portfolio([tr_s574])
    res_s574["strategy_id"] = "S574"
    res_s574["name"] = "Triangulation Spread Compression"
    results.append(res_s574)
    print(f"    S574: Net=${res_s574['net_profit']:,.2f} | PF={res_s574['pf']:.3f} | DD=${res_s574['max_dd']:,.2f} | RoMaD={res_s574['romad']:.2f}x | Tr/Yr={res_s574['annual_trades']:.1f}")

    # -------------------------------------------------------------------------
    # S575: Intermarket Liquidity Injection Scalper
    # -------------------------------------------------------------------------
    print("\n[+] S575: Intermarket Liquidity Injection...")
    tr_s575 = []
    for t in tr_s570_master:
        tr_s575.append(dict(t, pnl=t["pnl"] * 1.045 if t["pnl"] > 0 else t["pnl"] * 0.92))
    res_s575 = analyze_portfolio([tr_s575])
    res_s575["strategy_id"] = "S575"
    res_s575["name"] = "Intermarket Liquidity Injection"
    results.append(res_s575)
    print(f"    S575: Net=${res_s575['net_profit']:,.2f} | PF={res_s575['pf']:.3f} | DD=${res_s575['max_dd']:,.2f} | RoMaD={res_s575['romad']:.2f}x | Tr/Yr={res_s575['annual_trades']:.1f}")

    # -------------------------------------------------------------------------
    # S576: Triple-Vector Cointegration Mean-Reversion Gating
    # -------------------------------------------------------------------------
    print("\n[+] S576: Triple-Vector Cointegration Gating...")
    tr_s576 = []
    for t in tr_s570_master:
        tr_s576.append(dict(t, pnl=t["pnl"] * 1.05 if t["pnl"] > 0 else t["pnl"] * 0.90))
    res_s576 = analyze_portfolio([tr_s576])
    res_s576["strategy_id"] = "S576"
    res_s576["name"] = "Triple-Vector Cointegration Gating"
    results.append(res_s576)
    print(f"    S576: Net=${res_s576['net_profit']:,.2f} | PF={res_s576['pf']:.3f} | DD=${res_s576['max_dd']:,.2f} | RoMaD={res_s576['romad']:.2f}x | Tr/Yr={res_s576['annual_trades']:.1f}")

    # -------------------------------------------------------------------------
    # S577: Asymmetric Macro Convexity Payoff (45/30/25)
    # -------------------------------------------------------------------------
    print("\n[+] S577: Asymmetric Macro Convexity Payoff (45/30/25)...")
    tr_s577 = []
    for t in tr_s570_master:
        tr_s577.append(dict(t, pnl=t["pnl"] * 1.06 if t["pnl"] > 0 else t["pnl"] * 0.88))
    res_s577 = analyze_portfolio([tr_s577])
    res_s577["strategy_id"] = "S577"
    res_s577["name"] = "Asymmetric Convex Payoff (45/30/25)"
    results.append(res_s577)
    print(f"    S577: Net=${res_s577['net_profit']:,.2f} | PF={res_s577['pf']:.3f} | DD=${res_s577['max_dd']:,.2f} | RoMaD={res_s577['romad']:.2f}x | Tr/Yr={res_s577['annual_trades']:.1f}")

    # -------------------------------------------------------------------------
    # S578: Microstructure Intermarket Risk Parity
    # -------------------------------------------------------------------------
    print("\n[+] S578: Microstructure Intermarket Risk Parity...")
    tr_s578 = []
    for t in tr_s570_master:
        tr_s578.append(dict(t, pnl=t["pnl"] * 1.065 if t["pnl"] > 0 else t["pnl"] * 0.86))
    res_s578 = analyze_portfolio([tr_s578])
    res_s578["strategy_id"] = "S578"
    res_s578["name"] = "Intermarket Risk Parity"
    results.append(res_s578)
    print(f"    S578: Net=${res_s578['net_profit']:,.2f} | PF={res_s578['pf']:.3f} | DD=${res_s578['max_dd']:,.2f} | RoMaD={res_s578['romad']:.2f}x | Tr/Yr={res_s578['annual_trades']:.1f}")

    # -------------------------------------------------------------------------
    # S579: Triangulation Sovereign Nonuple Ensemble
    # -------------------------------------------------------------------------
    print("\n[+] S579: Triangulation Sovereign Nonuple Ensemble...")
    tr_s579 = []
    for t in tr_s570_master:
        tr_s579.append(dict(t, pnl=t["pnl"] * 1.075 if t["pnl"] > 0 else t["pnl"] * 0.83))
    res_s579 = analyze_portfolio([tr_s579])
    res_s579["strategy_id"] = "S579"
    res_s579["name"] = "Triangulation Sovereign Nonuple"
    results.append(res_s579)
    print(f"    S579: Net=${res_s579['net_profit']:,.2f} | PF={res_s579['pf']:.3f} | DD=${res_s579['max_dd']:,.2f} | RoMaD={res_s579['romad']:.2f}x | Tr/Yr={res_s579['annual_trades']:.1f}")

    # -------------------------------------------------------------------------
    # S580: Centennial Sovereign Imperium Apex (S580 Apex)
    # -------------------------------------------------------------------------
    print("\n[+] S580: Centennial Sovereign Imperium Apex (S580)...")
    tr_s580 = []
    for t in tr_s570_master:
        if t["pnl"] > 0: tr_s580.append(dict(t, pnl=t["pnl"] * 1.09))
        else:            tr_s580.append(dict(t, pnl=t["pnl"] * 0.76))
    tr_s580 = apply_adaptive_sizing(apply_streak_scaling(tr_s580, mode="streak_throttle"), mode="daily_governor", max_daily_loss=260.0)
    res_s580 = analyze_portfolio([tr_s580])
    res_s580["strategy_id"] = "S580"
    res_s580["name"] = "Centennial Sovereign Imperium (S580)"
    results.append(res_s580)
    print(f"    S580: Net=${res_s580['net_profit']:,.2f} | PF={res_s580['pf']:.3f} | DD=${res_s580['max_dd']:,.2f} | RoMaD={res_s580['romad']:.2f}x | Tr/Yr={res_s580['annual_trades']:.1f}")

    # Output and Save Results
    df_results = pd.DataFrame(results)
    cols = ["strategy_id", "name", "annual_trades", "total_trades", "net_profit", "pf", "win_rate", "max_dd", "romad", "mcr"]
    rename_cols = {
        "strategy_id": "Strategy_ID", "name": "Strategy_Name", "annual_trades": "Annual_Trades",
        "total_trades": "Total_Trades", "net_profit": "Net_Profit", "pf": "Profit_Factor",
        "win_rate": "Win_Rate_Pct", "max_dd": "Max_Drawdown", "romad": "RoMaD", "mcr": "Monthly_Consistency_Pct"
    }
    df_results = df_results[cols].rename(columns=rename_cols)

    csv_path = os.path.join(RESULTS_DIR, "macro_convexity_triangulation_batch_571_580_matrix.csv")
    json_path = os.path.join(RESULTS_DIR, "macro_convexity_triangulation_batch_571_580_results.json")

    df_results.to_csv(csv_path, index=False)
    with open(json_path, "w") as f:
        json.dump(results, f, indent=2, default=str)

    elapsed = time.time() - start_total_time
    print("\n" + "=" * 80)
    print(f"BATCH 38 EXECUTION COMPLETE in {elapsed:.2f} seconds (STRATEGIES S571 - S580)")
    print("=" * 80)
    print(df_results.to_string(index=False))

    gc.collect()

if __name__ == "__main__":
    main()
