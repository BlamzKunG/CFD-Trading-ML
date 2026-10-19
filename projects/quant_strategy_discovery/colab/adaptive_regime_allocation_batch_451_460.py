#!/usr/bin/env python3
"""
===============================================================================
SCALPING FRONTIER BATCH 26: STRATEGIES 451 - 460
ADAPTIVE DYNAMIC REGIME ALLOCATION & ASYMMETRIC RISK PARITY (2020-2025)
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

# -----------------------------------------------------------------------------
# Portfolio Dynamic Allocation Simulators
# -----------------------------------------------------------------------------
def apply_adaptive_sizing(trades, mode="fixed", max_daily_loss=500.0):
    """
    Applies adaptive sizing or risk parity rules across trade list.
    """
    if not trades:
        return []

    sorted_trades = sorted(trades, key=lambda x: x["entry_time"])
    scaled_trades = []

    # Daily PnL tracking for prop-firm governor
    daily_pnl = {}

    for t in sorted_trades:
        day_key = f"{t['year']}-{t['month']}-{t['entry_time'].day:02d}"
        cur_day_pnl = daily_pnl.get(day_key, 0.0)

        # Prop firm governor check: if daily loss exceeds limit, block new entries
        if mode == "daily_governor" and cur_day_pnl <= -max_daily_loss:
            continue

        scale = 1.0
        engine = t.get("engine", "")

        if mode == "risk_parity":
            # Scale engines inversely by their historical standalone volatility
            if "M15" in engine or "Supertrend" in engine:
                scale = 1.00  # Baseline Core
            elif "DualSpeed" in engine or "M5" in engine:
                scale = 0.85  # Slightly dialed back to balance drawdown
            elif "M1" in engine:
                scale = 0.70  # Rapid micro turnover scaled down for fee safety
        elif mode == "ny_expansion":
            # Overweight trades during the peak 13:00-16:00 UTC window
            hour = t["entry_time"].hour
            if 13 <= hour <= 16:
                scale = 1.25
            else:
                scale = 0.85
        elif mode == "asymmetric_ratchet":
            # Let winners run with higher weight on macro alignment
            scale = 1.10

        new_t = dict(t)
        new_t["pnl"] = t["pnl"] * scale
        daily_pnl[day_key] = cur_day_pnl + new_t["pnl"]
        scaled_trades.append(new_t)

    return scaled_trades

def main():
    start_total_time = time.time()
    print("=" * 80)
    print("STARTING SCALPING FRONTIER BATCH 26: STRATEGIES 451 - 460")
    print("ADAPTIVE REGIME ALLOCATION & ASYMMETRIC RISK PARITY (2020-2025)")
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
    m15_trend, _ = compute_supertrend(m15_highs, m15_lows, m15_closes, m15_atr, 3.0)

    df_m15_state = pd.DataFrame({"time": pd.to_datetime(df_m15["time"]), "m15_trend": m15_trend}).sort_values("time")

    print("[*] Generating Engine 1: M15 Core Trades...")
    tr_m15_core = run_supertrend_session_sim(m15_opens, m15_highs, m15_lows, m15_closes, m15_atr, m15_ema200, m15_dates, "skip_rollover")

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
    m1_trend, m1_st_band = compute_supertrend(m1_highs, m1_lows, m1_closes, m1_atr, 3.0)

    print("[*] Generating Engine 3: S446 M1 NY Sniper Trades ($1.00 threshold)...")
    tr_m1_ny_100 = run_fast_m1_scalper(
        m1_opens, m1_highs, m1_lows, m1_closes, m1_py_dates, m1_hours, m1_years, m1_months,
        m1_atr, m1_trend, m1_st_band, m15_macro_trend,
        min_m1_atr=1.00, session_mode="ny_only", use_macro_filter=True, use_m1_ratchet=True
    )

    print("[*] Generating Engine 4: S447 M1 NY Sniper Trades ($1.40 high-vol threshold)...")
    tr_m1_ny_140 = run_fast_m1_scalper(
        m1_opens, m1_highs, m1_lows, m1_closes, m1_py_dates, m1_hours, m1_years, m1_months,
        m1_atr, m1_trend, m1_st_band, m15_macro_trend,
        min_m1_atr=1.40, session_mode="ny_only", use_macro_filter=True, use_m1_ratchet=True
    )

    results = []

    # S451: S450 Baseline Reference (Fixed 0.10 Lot Across All 3 Engines)
    print("\n[+] Simulating S451: S450 Baseline Reference (Fixed 0.10 Lot)...")
    res_s451 = analyze_portfolio([tr_m15_core, tr_m5_ratchet, tr_m1_ny_100])
    res_s451["strategy_id"] = "S451"
    res_s451["name"] = "S450 Centennial Baseline (Fixed 0.10 Lot)"
    results.append(res_s451)
    print(f"    S451 Result: Net=${res_s451['net_profit']:,.2f} | PF={res_s451['pf']:.3f} | DD=${res_s451['max_dd']:,.2f} | RoMaD={res_s451['romad']:.2f}x | Tr/Yr={res_s451['annual_trades']:.1f}")

    # S452: Triple-TF Risk Parity Allocation (M15 1.0x, M5 0.85x, M1 0.70x)
    print("\n[+] Simulating S452: Triple-TF Risk Parity Allocation...")
    tr_s452 = apply_adaptive_sizing(tr_m15_core + tr_m5_ratchet + tr_m1_ny_100, mode="risk_parity")
    res_s452 = analyze_portfolio([tr_s452])
    res_s452["strategy_id"] = "S452"
    res_s452["name"] = "Triple-TF Risk Parity (1.0x / 0.85x / 0.70x)"
    results.append(res_s452)
    print(f"    S452 Result: Net=${res_s452['net_profit']:,.2f} | PF={res_s452['pf']:.3f} | DD=${res_s452['max_dd']:,.2f} | RoMaD={res_s452['romad']:.2f}x | Tr/Yr={res_s452['annual_trades']:.1f}")

    # S453: Triple-TF NY Liquidity Overweight (13-16 UTC 1.25x, Off-Peak 0.85x)
    print("\n[+] Simulating S453: Triple-TF NY Liquidity Overweight...")
    tr_s453 = apply_adaptive_sizing(tr_m15_core + tr_m5_ratchet + tr_m1_ny_100, mode="ny_expansion")
    res_s453 = analyze_portfolio([tr_s453])
    res_s453["strategy_id"] = "S453"
    res_s453["name"] = "Triple-TF NY Liquidity Overweight"
    results.append(res_s453)
    print(f"    S453 Result: Net=${res_s453['net_profit']:,.2f} | PF={res_s453['pf']:.3f} | DD=${res_s453['max_dd']:,.2f} | RoMaD={res_s453['romad']:.2f}x | Tr/Yr={res_s453['annual_trades']:.1f}")

    # S454: High-Volatility Precision Triple-TF (M15 Core + M5 Ratchet + M1 NY $1.40 High-Vol)
    print("\n[+] Simulating S454: High-Volatility Precision Triple-TF (S447 M1)...")
    res_s454 = analyze_portfolio([tr_m15_core, tr_m5_ratchet, tr_m1_ny_140])
    res_s454["strategy_id"] = "S454"
    res_s454["name"] = "High-Vol Precision Triple-TF (M1 ATR>=1.40)"
    results.append(res_s454)
    print(f"    S454 Result: Net=${res_s454['net_profit']:,.2f} | PF={res_s454['pf']:.3f} | DD=${res_s454['max_dd']:,.2f} | RoMaD={res_s454['romad']:.2f}x | Tr/Yr={res_s454['annual_trades']:.1f}")

    # S455: Prop-Firm Daily Loss Governed Triple-TF ($500 Max Daily Loss)
    print("\n[+] Simulating S455: Prop-Firm Daily Loss Governed Triple-TF ($500 Cap)...")
    tr_s455 = apply_adaptive_sizing(tr_m15_core + tr_m5_ratchet + tr_m1_ny_100, mode="daily_governor", max_daily_loss=500.0)
    res_s455 = analyze_portfolio([tr_s455])
    res_s455["strategy_id"] = "S455"
    res_s455["name"] = "Prop-Firm Daily Governed Triple-TF ($500 Cap)"
    results.append(res_s455)
    print(f"    S455 Result: Net=${res_s455['net_profit']:,.2f} | PF={res_s455['pf']:.3f} | DD=${res_s455['max_dd']:,.2f} | RoMaD={res_s455['romad']:.2f}x | Tr/Yr={res_s455['annual_trades']:.1f}")

    # S456: Prop-Firm Daily Loss Governed Triple-TF ($350 Tight Cap)
    print("\n[+] Simulating S456: Prop-Firm Tight Daily Governed ($350 Cap)...")
    tr_s456 = apply_adaptive_sizing(tr_m15_core + tr_m5_ratchet + tr_m1_ny_100, mode="daily_governor", max_daily_loss=350.0)
    res_s456 = analyze_portfolio([tr_s456])
    res_s456["strategy_id"] = "S456"
    res_s456["name"] = "Prop-Firm Tight Daily Governed ($350 Cap)"
    results.append(res_s456)
    print(f"    S456 Result: Net=${res_s456['net_profit']:,.2f} | PF={res_s456['pf']:.3f} | DD=${res_s456['max_dd']:,.2f} | RoMaD={res_s456['romad']:.2f}x | Tr/Yr={res_s456['annual_trades']:.1f}")

    # S457: Asymmetric Ratchet Multiplier (1.10x Winning Trend Exposure)
    print("\n[+] Simulating S457: Asymmetric Ratchet Multiplier...")
    tr_s457 = apply_adaptive_sizing(tr_m15_core + tr_m5_ratchet + tr_m1_ny_100, mode="asymmetric_ratchet")
    res_s457 = analyze_portfolio([tr_s457])
    res_s457["strategy_id"] = "S457"
    res_s457["name"] = "Asymmetric Ratchet Multiplier (1.1x)"
    results.append(res_s457)
    print(f"    S457 Result: Net=${res_s457['net_profit']:,.2f} | PF={res_s457['pf']:.3f} | DD=${res_s457['max_dd']:,.2f} | RoMaD={res_s457['romad']:.2f}x | Tr/Yr={res_s457['annual_trades']:.1f}")

    # S458: Combined Risk Parity + NY Liquidity Expansion
    print("\n[+] Simulating S458: Risk Parity + NY Liquidity Expansion...")
    tr_s458_rp = apply_adaptive_sizing(tr_m15_core + tr_m5_ratchet + tr_m1_ny_100, mode="risk_parity")
    tr_s458 = apply_adaptive_sizing(tr_s458_rp, mode="ny_expansion")
    res_s458 = analyze_portfolio([tr_s458])
    res_s458["strategy_id"] = "S458"
    res_s458["name"] = "Risk Parity + NY Liquidity Expansion"
    results.append(res_s458)
    print(f"    S458 Result: Net=${res_s458['net_profit']:,.2f} | PF={res_s458['pf']:.3f} | DD=${res_s458['max_dd']:,.2f} | RoMaD={res_s458['romad']:.2f}x | Tr/Yr={res_s458['annual_trades']:.1f}")

    # S459: Combined Risk Parity + High-Vol Precision (S447)
    print("\n[+] Simulating S459: Risk Parity + High-Vol Precision (S447)...")
    tr_s459_rp = apply_adaptive_sizing(tr_m15_core + tr_m5_ratchet + tr_m1_ny_140, mode="risk_parity")
    res_s459 = analyze_portfolio([tr_s459_rp])
    res_s459["strategy_id"] = "S459"
    res_s459["name"] = "Risk Parity + High-Vol Precision (S447)"
    results.append(res_s459)
    print(f"    S459 Result: Net=${res_s459['net_profit']:,.2f} | PF={res_s459['pf']:.3f} | DD=${res_s459['max_dd']:,.2f} | RoMaD={res_s459['romad']:.2f}x | Tr/Yr={res_s459['annual_trades']:.1f}")

    # S460: Grand Sovereign Centennial Apex (Risk Parity + NY Expansion + $500 Daily Governor)
    print("\n[+] Simulating S460: Grand Sovereign Centennial Apex...")
    tr_s460 = apply_adaptive_sizing(tr_s458, mode="daily_governor", max_daily_loss=500.0)
    res_s460 = analyze_portfolio([tr_s460])
    res_s460["strategy_id"] = "S460"
    res_s460["name"] = "Grand Sovereign Centennial Apex (S460)"
    results.append(res_s460)
    print(f"    S460 Result: Net=${res_s460['net_profit']:,.2f} | PF={res_s460['pf']:.3f} | DD=${res_s460['max_dd']:,.2f} | RoMaD={res_s460['romad']:.2f}x | Tr/Yr={res_s460['annual_trades']:.1f}")

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
    csv_path = os.path.join(RESULTS_DIR, "adaptive_regime_allocation_batch_451_460_matrix.csv")
    df_matrix.to_csv(csv_path, index=False)
    print(f"\n[+] Saved Matrix CSV to: {csv_path}")

    clean_results = []
    for r in results:
        rc = {k: v for k, v in r.items() if k != "trades"}
        clean_results.append(rc)

    json_path = os.path.join(RESULTS_DIR, "adaptive_regime_allocation_batch_451_460_results.json")
    with open(json_path, "w") as f:
        json.dump(clean_results, f, indent=2)
    print(f"[+] Saved Results JSON to: {json_path}")

    print("\n" + "=" * 80)
    print(f"BATCH 26 EXECUTION COMPLETE in {time.time() - start_total_time:.2f} seconds")
    print("=" * 80)
    print(df_matrix.to_string(index=False))

    gc.collect()

if __name__ == "__main__":
    main()
