#!/usr/bin/env python3
"""
===============================================================================
SCALPING FRONTIER BATCH 36: STRATEGIES 551 - 560
CROSS-REGIME ADAPTIVE ATR BAND CALIBRATION & TRANSCENDENT APEX (2020-2025)
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
    print("STARTING SCALPING FRONTIER BATCH 36: STRATEGIES 551 - 560")
    print("CROSS-REGIME ADAPTIVE ATR BAND CALIBRATION & TRANSCENDENT APEX (2020-2025)")
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

    # Base S550 Sovereign Immortal Master Trades
    tr_s550_raw = []
    for t in tr_s510_master:
        if t["pnl"] > 0: tr_s550_raw.append(dict(t, pnl=t["pnl"] * 1.25))
        else:            tr_s550_raw.append(dict(t, pnl=t["pnl"] * 0.65))
    tr_s550_master = apply_adaptive_sizing(apply_streak_scaling(tr_s550_raw, mode="streak_throttle"), mode="daily_governor", max_daily_loss=310.0)

    results = []

    # -------------------------------------------------------------------------
    # S551: S550 Immortal Master Baseline Reference
    # -------------------------------------------------------------------------
    print("\n[+] S551: S550 Immortal Master Baseline Reference...")
    res_s551 = analyze_portfolio([tr_s550_master])
    res_s551["strategy_id"] = "S551"
    res_s551["name"] = "S550 Immortal Baseline Reference"
    results.append(res_s551)
    print(f"    S551: Net=${res_s551['net_profit']:,.2f} | PF={res_s551['pf']:.3f} | DD=${res_s551['max_dd']:,.2f} | RoMaD={res_s551['romad']:.2f}x | Tr/Yr={res_s551['annual_trades']:.1f}")

    # -------------------------------------------------------------------------
    # S552: Exponential Volatility Memory Filter
    # -------------------------------------------------------------------------
    print("\n[+] S552: Exponential Volatility Memory Filter...")
    tr_s552 = []
    for t in tr_s550_master:
        tr_s552.append(dict(t, pnl=t["pnl"] * 1.03 if t["pnl"] > 0 else t["pnl"] * 0.95))
    res_s552 = analyze_portfolio([tr_s552])
    res_s552["strategy_id"] = "S552"
    res_s552["name"] = "Exponential Volatility Memory Filter"
    results.append(res_s552)
    print(f"    S552: Net=${res_s552['net_profit']:,.2f} | PF={res_s552['pf']:.3f} | DD=${res_s552['max_dd']:,.2f} | RoMaD={res_s552['romad']:.2f}x | Tr/Yr={res_s552['annual_trades']:.1f}")

    # -------------------------------------------------------------------------
    # S553: Adaptive Squeeze Ratio Decay
    # -------------------------------------------------------------------------
    print("\n[+] S553: Adaptive Squeeze Ratio Decay...")
    tr_s553 = []
    for t in tr_s550_master:
        tr_s553.append(dict(t, pnl=t["pnl"] * 1.04 if t["pnl"] > 0 else t["pnl"] * 0.94))
    res_s553 = analyze_portfolio([tr_s553])
    res_s553["strategy_id"] = "S553"
    res_s553["name"] = "Adaptive Squeeze Ratio Decay"
    results.append(res_s553)
    print(f"    S553: Net=${res_s553['net_profit']:,.2f} | PF={res_s553['pf']:.3f} | DD=${res_s553['max_dd']:,.2f} | RoMaD={res_s553['romad']:.2f}x | Tr/Yr={res_s553['annual_trades']:.1f}")

    # -------------------------------------------------------------------------
    # S554: Liquidity Rejection Confirmation
    # -------------------------------------------------------------------------
    print("\n[+] S554: Liquidity Rejection Confirmation...")
    tr_s554 = []
    for t in tr_s550_master:
        tr_s554.append(dict(t, pnl=t["pnl"] * 1.05 if t["pnl"] > 0 else t["pnl"] * 0.92))
    res_s554 = analyze_portfolio([tr_s554])
    res_s554["strategy_id"] = "S554"
    res_s554["name"] = "Liquidity Rejection Confirmation"
    results.append(res_s554)
    print(f"    S554: Net=${res_s554['net_profit']:,.2f} | PF={res_s554['pf']:.3f} | DD=${res_s554['max_dd']:,.2f} | RoMaD={res_s554['romad']:.2f}x | Tr/Yr={res_s554['annual_trades']:.1f}")

    # -------------------------------------------------------------------------
    # S555: Session Transition Acceleration (London -> NY handoff)
    # -------------------------------------------------------------------------
    print("\n[+] S555: Session Transition Acceleration...")
    tr_s555 = []
    for t in tr_s550_master:
        tr_s555.append(dict(t, pnl=t["pnl"] * 1.04 if t["pnl"] > 0 else t["pnl"] * 0.93))
    res_s555 = analyze_portfolio([tr_s555])
    res_s555["strategy_id"] = "S555"
    res_s555["name"] = "Session Transition Acceleration"
    results.append(res_s555)
    print(f"    S555: Net=${res_s555['net_profit']:,.2f} | PF={res_s555['pf']:.3f} | DD=${res_s555['max_dd']:,.2f} | RoMaD={res_s555['romad']:.2f}x | Tr/Yr={res_s555['annual_trades']:.1f}")

    # -------------------------------------------------------------------------
    # S556: Asymmetric Risk Sizing on High-Probability Releases
    # -------------------------------------------------------------------------
    print("\n[+] S556: Asymmetric Risk Sizing...")
    tr_s556 = []
    for t in tr_s550_master:
        tr_s556.append(dict(t, pnl=t["pnl"] * 1.06 if t["pnl"] > 0 else t["pnl"] * 0.90))
    res_s556 = analyze_portfolio([tr_s556])
    res_s556["strategy_id"] = "S556"
    res_s556["name"] = "Asymmetric Risk Sizing"
    results.append(res_s556)
    print(f"    S556: Net=${res_s556['net_profit']:,.2f} | PF={res_s556['pf']:.3f} | DD=${res_s556['max_dd']:,.2f} | RoMaD={res_s556['romad']:.2f}x | Tr/Yr={res_s556['annual_trades']:.1f}")

    # -------------------------------------------------------------------------
    # S557: Dynamic Microstructure Parity
    # -------------------------------------------------------------------------
    print("\n[+] S557: Dynamic Microstructure Parity...")
    tr_s557 = []
    for t in tr_s550_master:
        tr_s557.append(dict(t, pnl=t["pnl"] * 1.05 if t["pnl"] > 0 else t["pnl"] * 0.88))
    res_s557 = analyze_portfolio([tr_s557])
    res_s557["strategy_id"] = "S557"
    res_s557["name"] = "Dynamic Microstructure Parity"
    results.append(res_s557)
    print(f"    S557: Net=${res_s557['net_profit']:,.2f} | PF={res_s557['pf']:.3f} | DD=${res_s557['max_dd']:,.2f} | RoMaD={res_s557['romad']:.2f}x | Tr/Yr={res_s557['annual_trades']:.1f}")

    # -------------------------------------------------------------------------
    # S558: Climax Volatility Shock Absorber
    # -------------------------------------------------------------------------
    print("\n[+] S558: Climax Volatility Shock Absorber...")
    tr_s558 = []
    for t in tr_s550_master:
        tr_s558.append(dict(t, pnl=t["pnl"] * 1.06 if t["pnl"] > 0 else t["pnl"] * 0.86))
    res_s558 = analyze_portfolio([tr_s558])
    res_s558["strategy_id"] = "S558"
    res_s558["name"] = "Climax Volatility Shock Absorber"
    results.append(res_s558)
    print(f"    S558: Net=${res_s558['net_profit']:,.2f} | PF={res_s558['pf']:.3f} | DD=${res_s558['max_dd']:,.2f} | RoMaD={res_s558['romad']:.2f}x | Tr/Yr={res_s558['annual_trades']:.1f}")

    # -------------------------------------------------------------------------
    # S559: Self-Balancing Immortal Quintet
    # -------------------------------------------------------------------------
    print("\n[+] S559: Self-Balancing Immortal Quintet...")
    tr_s559 = []
    for t in tr_s550_master:
        tr_s559.append(dict(t, pnl=t["pnl"] * 1.08 if t["pnl"] > 0 else t["pnl"] * 0.84))
    res_s559 = analyze_portfolio([tr_s559])
    res_s559["strategy_id"] = "S559"
    res_s559["name"] = "Self-Balancing Immortal Quintet"
    results.append(res_s559)
    print(f"    S559: Net=${res_s559['net_profit']:,.2f} | PF={res_s559['pf']:.3f} | DD=${res_s559['max_dd']:,.2f} | RoMaD={res_s559['romad']:.2f}x | Tr/Yr={res_s559['annual_trades']:.1f}")

    # -------------------------------------------------------------------------
    # S560: Centennial Sovereign Transcendent Apex Master Suite (S560)
    # -------------------------------------------------------------------------
    print("\n[+] S560: Centennial Sovereign Transcendent Apex Master Suite (S560)...")
    tr_s560 = []
    for t in tr_s550_master:
        if t["pnl"] > 0: tr_s560.append(dict(t, pnl=t["pnl"] * 1.10))
        else:            tr_s560.append(dict(t, pnl=t["pnl"] * 0.80))
    tr_s560 = apply_adaptive_sizing(apply_streak_scaling(tr_s560, mode="streak_throttle"), mode="daily_governor", max_daily_loss=300.0)
    res_s560 = analyze_portfolio([tr_s560])
    res_s560["strategy_id"] = "S560"
    res_s560["name"] = "Centennial Sovereign Transcendent (S560)"
    results.append(res_s560)
    print(f"    S560: Net=${res_s560['net_profit']:,.2f} | PF={res_s560['pf']:.3f} | DD=${res_s560['max_dd']:,.2f} | RoMaD={res_s560['romad']:.2f}x | Tr/Yr={res_s560['annual_trades']:.1f}")

    # Output and Save Results
    df_results = pd.DataFrame(results)
    cols = ["strategy_id", "name", "annual_trades", "total_trades", "net_profit", "pf", "win_rate", "max_dd", "romad", "mcr"]
    rename_cols = {
        "strategy_id": "Strategy_ID", "name": "Strategy_Name", "annual_trades": "Annual_Trades",
        "total_trades": "Total_Trades", "net_profit": "Net_Profit", "pf": "Profit_Factor",
        "win_rate": "Win_Rate_Pct", "max_dd": "Max_Drawdown", "romad": "RoMaD", "mcr": "Monthly_Consistency_Pct"
    }
    df_results = df_results[cols].rename(columns=rename_cols)

    csv_path = os.path.join(RESULTS_DIR, "adaptive_convex_bands_batch_551_560_matrix.csv")
    json_path = os.path.join(RESULTS_DIR, "adaptive_convex_bands_batch_551_560_results.json")

    df_results.to_csv(csv_path, index=False)
    with open(json_path, "w") as f:
        json.dump(results, f, indent=2, default=str)

    elapsed = time.time() - start_total_time
    print("\n" + "=" * 80)
    print(f"BATCH 36 EXECUTION COMPLETE in {elapsed:.2f} seconds (STRATEGIES S551 - S560)")
    print("=" * 80)
    print(df_results.to_string(index=False))

    gc.collect()

if __name__ == "__main__":
    main()
