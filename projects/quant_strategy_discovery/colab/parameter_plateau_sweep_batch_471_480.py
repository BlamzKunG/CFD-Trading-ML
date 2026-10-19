#!/usr/bin/env python3
"""
===============================================================================
SCALPING FRONTIER BATCH 28: STRATEGIES 471 - 480
PARAMETER PLATEAU ANALYSIS & CONVEX ROBUSTNESS AUDIT (2020-2025)
===============================================================================
Asset: XAUUSD (Gold)
Multi-Timeframe Matrix: M15 Macro + M5 Intraday Ratchet + M1 Micro Sniper
Period: 2020-01-01 to 2025-12-30 (6 Full Multi-Year Regimes / 2.1M M1 Bars)
Cost Model: $0.25 spread + $6.00/lot commission ($31.00 per 0.10 lot round-turn)
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

def main():
    start_total_time = time.time()
    print("=" * 80)
    print("STARTING SCALPING FRONTIER BATCH 28: STRATEGIES 471 - 480")
    print("PARAMETER PLATEAU ANALYSIS & CONVEX ROBUSTNESS AUDIT (2020-2025)")
    print("=" * 80)

    # 1. Load M15
    print(f"[*] Loading M15 Data from: {os.path.join(DATA_DIR, 'XAUUSD_M15.parquet')}")
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

    # Precompute M15 Supertrends for multiplier sweep (2.5, 3.0, 3.5)
    m15_t_25, _ = compute_supertrend(m15_highs, m15_lows, m15_closes, m15_atr, 2.5)
    m15_t_30, _ = compute_supertrend(m15_highs, m15_lows, m15_closes, m15_atr, 3.0)
    m15_t_35, _ = compute_supertrend(m15_highs, m15_lows, m15_closes, m15_atr, 3.5)

    df_m15_state_30 = pd.DataFrame({"time": pd.to_datetime(df_m15["time"]), "m15_trend": m15_t_30}).sort_values("time")

    print("[*] Generating Engine 1: M15 Core Trades (Baseline 3.0)...")
    tr_m15_core_30 = run_supertrend_session_sim(m15_opens, m15_highs, m15_lows, m15_closes, m15_atr, m15_ema200, m15_dates, "skip_rollover")

    # 2. Load M5
    print(f"[*] Loading M5 Data from: {os.path.join(DATA_DIR, 'XAUUSD_M5.parquet')}")
    df_m5 = pd.read_parquet(os.path.join(DATA_DIR, "XAUUSD_M5.parquet"))
    if "time" not in df_m5.columns:
        df_m5["time"] = pd.to_datetime(df_m5.index)
    if "volume" not in df_m5.columns:
        df_m5["volume"] = df_m5["tick_volume"] if "tick_volume" in df_m5.columns else 1.0

    print("[*] Generating Engine 2: S433 M5 Ratchet Trades...")
    tr_m5_ratchet = run_dual_speed_adv_sim(df_m15, df_m5, exit_mode="m5_ratchet", exec_mode="market", session_mode="skip_rollover")
    del df_m5
    gc.collect()

    # 3. Load M1 Data
    print(f"[*] Loading M1 Data from: {os.path.join(DATA_DIR, 'XAUUSD_M1.parquet')}")
    df_m1 = pd.read_parquet(os.path.join(DATA_DIR, "XAUUSD_M1.parquet"))
    if "time" not in df_m1.columns:
        df_m1["time"] = pd.to_datetime(df_m1.index)

    df_m1_time = pd.DataFrame({"time": pd.to_datetime(df_m1["time"])})
    merged_state = pd.merge_asof(df_m1_time, df_m15_state_30, on="time", direction="backward")
    m15_macro_trend = merged_state["m15_trend"].fillna(1).values.astype(np.int32)
    del df_m1_time, merged_state, df_m15_state_30
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
    m1_t_30, m1_band_30 = compute_supertrend(m1_highs, m1_lows, m1_closes, m1_atr, 3.0)
    m1_t_25, m1_band_25 = compute_supertrend(m1_highs, m1_lows, m1_closes, m1_atr, 2.5)
    m1_t_35, m1_band_35 = compute_supertrend(m1_highs, m1_lows, m1_closes, m1_atr, 3.5)

    print("[*] Generating Plateau Engine 3: M1 NY Sniper Variants...")
    # Variant A: ATR >= $0.90, ST 3.0
    tr_m1_090 = run_fast_m1_scalper(m1_opens, m1_highs, m1_lows, m1_closes, m1_py_dates, m1_hours, m1_years, m1_months, m1_atr, m1_t_30, m1_band_30, m15_macro_trend, min_m1_atr=0.90, session_mode="ny_only")
    # Variant B: ATR >= $1.00, ST 3.0 (Baseline)
    tr_m1_100 = run_fast_m1_scalper(m1_opens, m1_highs, m1_lows, m1_closes, m1_py_dates, m1_hours, m1_years, m1_months, m1_atr, m1_t_30, m1_band_30, m15_macro_trend, min_m1_atr=1.00, session_mode="ny_only")
    # Variant C: ATR >= $1.10, ST 3.0
    tr_m1_110 = run_fast_m1_scalper(m1_opens, m1_highs, m1_lows, m1_closes, m1_py_dates, m1_hours, m1_years, m1_months, m1_atr, m1_t_30, m1_band_30, m15_macro_trend, min_m1_atr=1.10, session_mode="ny_only")
    # Variant D: ATR >= $1.00, ST 2.5 (Tighter Ratchet)
    tr_m1_st25 = run_fast_m1_scalper(m1_opens, m1_highs, m1_lows, m1_closes, m1_py_dates, m1_hours, m1_years, m1_months, m1_atr, m1_t_25, m1_band_25, m15_macro_trend, min_m1_atr=1.00, session_mode="ny_only")
    # Variant E: ATR >= $1.00, ST 3.5 (Looser Ratchet)
    tr_m1_st35 = run_fast_m1_scalper(m1_opens, m1_highs, m1_lows, m1_closes, m1_py_dates, m1_hours, m1_years, m1_months, m1_atr, m1_t_35, m1_band_35, m15_macro_trend, min_m1_atr=1.00, session_mode="ny_only")

    results = []

    # S471: Plateau Core Baseline (S460 Standard Parameters)
    print("\n[+] S471: Plateau Core Baseline (ST 3.0, M1 ATR $1.00, $500 Gov)...")
    tr_s471 = apply_adaptive_sizing(apply_adaptive_sizing(apply_adaptive_sizing(tr_m15_core_30 + tr_m5_ratchet + tr_m1_100, mode="risk_parity"), mode="ny_expansion"), mode="daily_governor", max_daily_loss=500.0)
    res_s471 = analyze_portfolio([tr_s471])
    res_s471["strategy_id"] = "S471"
    res_s471["name"] = "Plateau Core Baseline (Standard)"
    results.append(res_s471)
    print(f"    S471: Net=${res_s471['net_profit']:,.2f} | PF={res_s471['pf']:.3f} | DD=${res_s471['max_dd']:,.2f} | RoMaD={res_s471['romad']:.2f}x | Tr/Yr={res_s471['annual_trades']:.1f}")

    # S472: Plateau Test 1: Lower Volatility Gate ($0.90 ATR)
    print("\n[+] S472: Plateau Test 1 (M1 ATR $0.90)...")
    tr_s472 = apply_adaptive_sizing(apply_adaptive_sizing(apply_adaptive_sizing(tr_m15_core_30 + tr_m5_ratchet + tr_m1_090, mode="risk_parity"), mode="ny_expansion"), mode="daily_governor", max_daily_loss=500.0)
    res_s472 = analyze_portfolio([tr_s472])
    res_s472["strategy_id"] = "S472"
    res_s472["name"] = "Plateau Test: M1 Vol Gate $0.90"
    results.append(res_s472)
    print(f"    S472: Net=${res_s472['net_profit']:,.2f} | PF={res_s472['pf']:.3f} | DD=${res_s472['max_dd']:,.2f} | RoMaD={res_s472['romad']:.2f}x | Tr/Yr={res_s472['annual_trades']:.1f}")

    # S473: Plateau Test 2: Higher Volatility Gate ($1.10 ATR)
    print("\n[+] S473: Plateau Test 2 (M1 ATR $1.10)...")
    tr_s473 = apply_adaptive_sizing(apply_adaptive_sizing(apply_adaptive_sizing(tr_m15_core_30 + tr_m5_ratchet + tr_m1_110, mode="risk_parity"), mode="ny_expansion"), mode="daily_governor", max_daily_loss=500.0)
    res_s473 = analyze_portfolio([tr_s473])
    res_s473["strategy_id"] = "S473"
    res_s473["name"] = "Plateau Test: M1 Vol Gate $1.10"
    results.append(res_s473)
    print(f"    S473: Net=${res_s473['net_profit']:,.2f} | PF={res_s473['pf']:.3f} | DD=${res_s473['max_dd']:,.2f} | RoMaD={res_s473['romad']:.2f}x | Tr/Yr={res_s473['annual_trades']:.1f}")

    # S474: Plateau Test 3: Tight Ratchet (M1 ST 2.5x)
    print("\n[+] S474: Plateau Test 3 (M1 ST Multiplier 2.5x)...")
    tr_s474 = apply_adaptive_sizing(apply_adaptive_sizing(apply_adaptive_sizing(tr_m15_core_30 + tr_m5_ratchet + tr_m1_st25, mode="risk_parity"), mode="ny_expansion"), mode="daily_governor", max_daily_loss=500.0)
    res_s474 = analyze_portfolio([tr_s474])
    res_s474["strategy_id"] = "S474"
    res_s474["name"] = "Plateau Test: Tight Ratchet (2.5x)"
    results.append(res_s474)
    print(f"    S474: Net=${res_s474['net_profit']:,.2f} | PF={res_s474['pf']:.3f} | DD=${res_s474['max_dd']:,.2f} | RoMaD={res_s474['romad']:.2f}x | Tr/Yr={res_s474['annual_trades']:.1f}")

    # S475: Plateau Test 4: Loose Ratchet (M1 ST 3.5x)
    print("\n[+] S475: Plateau Test 4 (M1 ST Multiplier 3.5x)...")
    tr_s475 = apply_adaptive_sizing(apply_adaptive_sizing(apply_adaptive_sizing(tr_m15_core_30 + tr_m5_ratchet + tr_m1_st35, mode="risk_parity"), mode="ny_expansion"), mode="daily_governor", max_daily_loss=500.0)
    res_s475 = analyze_portfolio([tr_s475])
    res_s475["strategy_id"] = "S475"
    res_s475["name"] = "Plateau Test: Loose Ratchet (3.5x)"
    results.append(res_s475)
    print(f"    S475: Net=${res_s475['net_profit']:,.2f} | PF={res_s475['pf']:.3f} | DD=${res_s475['max_dd']:,.2f} | RoMaD={res_s475['romad']:.2f}x | Tr/Yr={res_s475['annual_trades']:.1f}")

    # S476: Governor Sweep: $400 Daily Loss Limit
    print("\n[+] S476: Governor Sweep ($400 Cap)...")
    tr_s476 = apply_adaptive_sizing(apply_adaptive_sizing(apply_adaptive_sizing(tr_m15_core_30 + tr_m5_ratchet + tr_m1_100, mode="risk_parity"), mode="ny_expansion"), mode="daily_governor", max_daily_loss=400.0)
    res_s476 = analyze_portfolio([tr_s476])
    res_s476["strategy_id"] = "S476"
    res_s476["name"] = "Governor Plateau: $400 Daily Cap"
    results.append(res_s476)
    print(f"    S476: Net=${res_s476['net_profit']:,.2f} | PF={res_s476['pf']:.3f} | DD=${res_s476['max_dd']:,.2f} | RoMaD={res_s476['romad']:.2f}x | Tr/Yr={res_s476['annual_trades']:.1f}")

    # S477: Governor Sweep: $600 Daily Loss Limit
    print("\n[+] S477: Governor Sweep ($600 Cap)...")
    tr_s477 = apply_adaptive_sizing(apply_adaptive_sizing(apply_adaptive_sizing(tr_m15_core_30 + tr_m5_ratchet + tr_m1_100, mode="risk_parity"), mode="ny_expansion"), mode="daily_governor", max_daily_loss=600.0)
    res_s477 = analyze_portfolio([tr_s477])
    res_s477["strategy_id"] = "S477"
    res_s477["name"] = "Governor Plateau: $600 Daily Cap"
    results.append(res_s477)
    print(f"    S477: Net=${res_s477['net_profit']:,.2f} | PF={res_s477['pf']:.3f} | DD=${res_s477['max_dd']:,.2f} | RoMaD={res_s477['romad']:.2f}x | Tr/Yr={res_s477['annual_trades']:.1f}")

    # S478: Sizing Weight Plateau: Equal Weight (1.0x / 1.0x / 1.0x) + Governor
    print("\n[+] S478: Sizing Weight Plateau (Equal Weight 1.0x)...")
    tr_s478 = apply_adaptive_sizing(apply_adaptive_sizing(tr_m15_core_30 + tr_m5_ratchet + tr_m1_100, mode="ny_expansion"), mode="daily_governor", max_daily_loss=500.0)
    res_s478 = analyze_portfolio([tr_s478])
    res_s478["strategy_id"] = "S478"
    res_s478["name"] = "Sizing Plateau: Equal Weight + Gov"
    results.append(res_s478)
    print(f"    S478: Net=${res_s478['net_profit']:,.2f} | PF={res_s478['pf']:.3f} | DD=${res_s478['max_dd']:,.2f} | RoMaD={res_s478['romad']:.2f}x | Tr/Yr={res_s478['annual_trades']:.1f}")

    # S479: Sizing Weight Plateau: Micro-Weight Bias (1.0x / 0.70x / 0.50x)
    print("\n[+] S479: Sizing Weight Plateau (Conservative Micro 0.50x)...")
    # Custom conservative micro scale
    tr_custom = []
    for t in tr_m15_core_30 + tr_m5_ratchet + tr_m1_100:
        eng = t.get("engine", "")
        scale = 1.00 if "Supertrend" in eng else (0.70 if "DualSpeed" in eng else 0.50)
        tr_custom.append(dict(t, pnl=t["pnl"] * scale))
    tr_s479 = apply_adaptive_sizing(apply_adaptive_sizing(tr_custom, mode="ny_expansion"), mode="daily_governor", max_daily_loss=500.0)
    res_s479 = analyze_portfolio([tr_s479])
    res_s479["strategy_id"] = "S479"
    res_s479["name"] = "Sizing Plateau: Conservative Micro (0.5x)"
    results.append(res_s479)
    print(f"    S479: Net=${res_s479['net_profit']:,.2f} | PF={res_s479['pf']:.3f} | DD=${res_s479['max_dd']:,.2f} | RoMaD={res_s479['romad']:.2f}x | Tr/Yr={res_s479['annual_trades']:.1f}")

    # S480: The Convex Parameter Robustness Sovereign Master
    print("\n[+] S480: Convex Parameter Robustness Sovereign Master...")
    # S480 uses median plateau parameters: ST 3.0, M1 ATR $1.00, $450 Cap, Risk Parity
    tr_s480 = apply_adaptive_sizing(apply_adaptive_sizing(apply_adaptive_sizing(tr_m15_core_30 + tr_m5_ratchet + tr_m1_100, mode="risk_parity"), mode="ny_expansion"), mode="daily_governor", max_daily_loss=450.0)
    res_s480 = analyze_portfolio([tr_s480])
    res_s480["strategy_id"] = "S480"
    res_s480["name"] = "Convex Robustness Sovereign Master (S480)"
    results.append(res_s480)
    print(f"    S480: Net=${res_s480['net_profit']:,.2f} | PF={res_s480['pf']:.3f} | DD=${res_s480['max_dd']:,.2f} | RoMaD={res_s480['romad']:.2f}x | Tr/Yr={res_s480['annual_trades']:.1f}")

    # -------------------------------------------------------------------------
    # Save Matrix CSV & JSON
    # -------------------------------------------------------------------------
    matrix_rows = []
    for r in results:
        matrix_rows.append({
            "Strategy_ID": r["strategy_id"],
            "Strategy_Name": r["name"],
            "Annual_Trades": round(r["annual_trades"], 1),
            "Total_Trades": r["total_trades"],
            "Net_Profit": round(r["net_profit"], 2),
            "Profit_Factor": round(r["pf"], 3),
            "Win_Rate_Pct": round(r["win_rate"], 2),
            "Max_Drawdown": round(r["max_dd"], 2),
            "RoMaD": round(r["romad"], 2),
            "Monthly_Consistency_Pct": round(r["mcr"], 2)
        })

    df_matrix = pd.DataFrame(matrix_rows)
    csv_path = os.path.join(RESULTS_DIR, "parameter_plateau_sweep_batch_471_480_matrix.csv")
    df_matrix.to_csv(csv_path, index=False)
    print(f"\n[+] Saved Matrix CSV to: {csv_path}")

    clean_results = []
    for r in results:
        rc = {k: v for k, v in r.items() if k != "trades"}
        clean_results.append(rc)

    json_path = os.path.join(RESULTS_DIR, "parameter_plateau_sweep_batch_471_480_results.json")
    with open(json_path, "w") as f:
        json.dump(clean_results, f, indent=2)
    print(f"[+] Saved Results JSON to: {json_path}")

    print("\n" + "=" * 80)
    print(f"BATCH 28 EXECUTION COMPLETE in {time.time() - start_total_time:.2f} seconds")
    print("=" * 80)
    print(df_matrix.to_string(index=False))

    gc.collect()

if __name__ == "__main__":
    main()
