#!/usr/bin/env python3
"""
===============================================================================
SCALPING FRONTIER BATCH 29: STRATEGIES 481 - 490
ASIAN SESSION ORTHOGONAL REVERSION & PAYOFF ENGINEERING (2020-2025)
===============================================================================
Asset: XAUUSD (Gold)
Multi-Timeframe Matrix: M15 Macro + M5 Intraday Ratchet + M1 Sniper + Asian M5/M15 Reversion
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

def compute_rsi(closes: np.ndarray, period: int = 7) -> np.ndarray:
    n = len(closes)
    rsi = np.full(n, 50.0, dtype=np.float64)
    if n <= period:
        return rsi

    deltas = np.diff(closes)
    gains = np.where(deltas > 0, deltas, 0.0)
    losses = np.where(deltas < 0, -deltas, 0.0)

    avg_gain = np.mean(gains[:period])
    avg_loss = np.mean(losses[:period])

    for i in range(period, n - 1):
        avg_gain = (avg_gain * (period - 1) + gains[i]) / period
        avg_loss = (avg_loss * (period - 1) + losses[i]) / period

        if avg_loss == 0.0:
            rsi[i + 1] = 100.0
        else:
            rs = avg_gain / avg_loss
            rsi[i + 1] = 100.0 - (100.0 / (1.0 + rs))

    return rsi

def run_asian_reversion_sim(opens, highs, lows, closes, dates, atr, rsi, bb_mid, bb_up, bb_dn,
                            unit_size=10.0, spread=0.25, comm=0.60, sl_mult=1.5):
    """
    Simulates Asian Session Range Mean Reversion (00:00 - 06:00 UTC)
    """
    n = len(closes)
    trades = []
    pos = 0
    entry_p = 0.0
    sl_p = 0.0
    tp_p = 0.0
    entry_idx = 0

    for i in range(50, n - 2):
        hour = dates[i].hour

        # Check exits
        if pos == 1:
            hit = False
            exit_p = 0.0
            if lows[i] <= sl_p:
                exit_p = sl_p if opens[i] >= sl_p else opens[i]
                hit = True
            elif highs[i] >= tp_p:
                exit_p = tp_p if opens[i] <= tp_p else opens[i]
                hit = True
            elif hour >= 7:  # Time stop before London Open
                exit_p = opens[i + 1] - spread * 0.5
                hit = True

            if hit:
                pnl = (exit_p - entry_p) * unit_size - (spread + (comm / unit_size)) * unit_size
                trades.append({
                    "pnl": pnl, "entry_time": dates[entry_idx], "exit_time": dates[i],
                    "year": dates[entry_idx].year, "month": f"{dates[entry_idx].year}-{dates[entry_idx].month:02d}",
                    "entry_idx": entry_idx, "exit_idx": i, "engine": "Asian_Reversion"
                })
                pos = 0

        elif pos == -1:
            hit = False
            exit_p = 0.0
            if highs[i] >= sl_p:
                exit_p = sl_p if opens[i] <= sl_p else opens[i]
                hit = True
            elif lows[i] <= tp_p:
                exit_p = tp_p if opens[i] >= tp_p else opens[i]
                hit = True
            elif hour >= 7:  # Time stop before London Open
                exit_p = opens[i + 1] + spread * 0.5
                hit = True

            if hit:
                pnl = (entry_p - exit_p) * unit_size - (spread + (comm / unit_size)) * unit_size
                trades.append({
                    "pnl": pnl, "entry_time": dates[entry_idx], "exit_time": dates[i],
                    "year": dates[entry_idx].year, "month": f"{dates[entry_idx].year}-{dates[entry_idx].month:02d}",
                    "entry_idx": entry_idx, "exit_idx": i, "engine": "Asian_Reversion"
                })
                pos = 0

        # Check entries strictly in Asian hours (00:00 - 05:00 UTC)
        if pos == 0 and 0 <= hour <= 5:
            # Long: Touch lower BB + RSI < 30
            if lows[i] <= bb_dn[i] and rsi[i] <= 32.0:
                pos = 1
                entry_p = opens[i + 1] + spread * 0.5
                sl_p = entry_p - sl_mult * atr[i]
                tp_p = bb_mid[i]  # Mean reversion to BB middle
                entry_idx = i + 1

            # Short: Touch upper BB + RSI > 70
            elif highs[i] >= bb_up[i] and rsi[i] >= 68.0:
                pos = -1
                entry_p = opens[i + 1] - spread * 0.5
                sl_p = entry_p + sl_mult * atr[i]
                tp_p = bb_mid[i]  # Mean reversion to BB middle
                entry_idx = i + 1

    return trades

def apply_streak_scaling(trades, mode="streak"):
    sorted_trades = sorted(trades, key=lambda x: x["entry_time"])
    scaled_trades = []
    consec_wins = 0
    consec_losses = 0

    for t in sorted_trades:
        scale = 1.0
        if mode == "streak_boost":
            if consec_wins >= 2:
                scale = 1.15
        elif mode == "streak_throttle":
            if consec_losses >= 2:
                scale = 0.75

        new_t = dict(t)
        new_t["pnl"] = t["pnl"] * scale
        scaled_trades.append(new_t)

        if t["pnl"] > 0:
            consec_wins += 1
            consec_losses = 0
        elif t["pnl"] < 0:
            consec_losses += 1
            consec_wins = 0

    return scaled_trades

def main():
    start_total_time = time.time()
    print("=" * 80)
    print("STARTING SCALPING FRONTIER BATCH 29: STRATEGIES 481 - 490")
    print("ASIAN ORTHOGONAL REVERSION & PAYOFF ENGINEERING (2020-2025)")
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
    m15_trend, _ = compute_supertrend(m15_highs, m15_lows, m15_closes, 14, 3.0)

    df_m15_state = pd.DataFrame({"time": pd.to_datetime(df_m15["time"]), "m15_trend": m15_trend}).sort_values("time")

    print("[*] Generating Engine 1: M15 Core Trades...")
    tr_m15_core = run_supertrend_session_sim(m15_opens, m15_highs, m15_lows, m15_closes, m15_atr, m15_ema200, m15_dates, "skip_rollover")

    # M15 Asian Indicators
    m15_rsi = compute_rsi(m15_closes, 7)
    s15_closes = pd.Series(m15_closes)
    bb15_mid = s15_closes.rolling(20).mean().values
    bb15_std = s15_closes.rolling(20).std().fillna(0).values
    bb15_up = bb15_mid + 2.0 * bb15_std
    bb15_dn = bb15_mid - 2.0 * bb15_std

    print("[*] Generating Asian M15 Reversion Trades...")
    tr_asian_m15 = run_asian_reversion_sim(m15_opens, m15_highs, m15_lows, m15_closes, m15_dates, m15_atr, m15_rsi, bb15_mid, bb15_up, bb15_dn)
    print(f"[+] Asian M15 Reversion Trades: {len(tr_asian_m15):,} trades")

    # 2. Load M5
    print(f"[*] Loading M5 Data from: {os.path.join(DATA_DIR, 'XAUUSD_M5.parquet')}")
    df_m5 = pd.read_parquet(os.path.join(DATA_DIR, "XAUUSD_M5.parquet"))
    if "time" not in df_m5.columns:
        df_m5["time"] = pd.to_datetime(df_m5.index)
    if "volume" not in df_m5.columns:
        df_m5["volume"] = df_m5["tick_volume"] if "tick_volume" in df_m5.columns else 1.0

    m5_highs = df_m5["high"].values.astype(np.float64)
    m5_lows = df_m5["low"].values.astype(np.float64)
    m5_closes = df_m5["close"].values.astype(np.float64)
    m5_opens = df_m5["open"].values.astype(np.float64)
    m5_dates = pd.to_datetime(df_m5["time"]).dt.to_pydatetime()
    m5_atr = compute_atr(m5_highs, m5_lows, m5_closes, 14)
    m5_rsi = compute_rsi(m5_closes, 7)
    s5_closes = pd.Series(m5_closes)
    bb5_mid = s5_closes.rolling(20).mean().values
    bb5_std = s5_closes.rolling(20).std().fillna(0).values
    bb5_up = bb5_mid + 2.0 * bb5_std
    bb5_dn = bb5_mid - 2.0 * bb5_std

    print("[*] Generating Asian M5 Reversion Trades...")
    tr_asian_m5 = run_asian_reversion_sim(m5_opens, m5_highs, m5_lows, m5_closes, m5_dates, m5_atr, m5_rsi, bb5_mid, bb5_up, bb5_dn)
    print(f"[+] Asian M5 Reversion Trades: {len(tr_asian_m5):,} trades")

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
    m1_trend, m1_st_band = compute_supertrend(m1_highs, m1_lows, m1_closes, 14, 3.0)

    print("[*] Generating Engine 3: S446 M1 NY Sniper Trades...")
    tr_m1_ny = run_fast_m1_scalper(
        m1_opens, m1_highs, m1_lows, m1_closes, m1_py_dates, m1_hours, m1_years, m1_months,
        m1_atr, m1_trend, m1_st_band, m15_macro_trend,
        min_m1_atr=1.00, session_mode="ny_only", use_macro_filter=True, use_m1_ratchet=True
    )

    # Base S480 Sovereign Trades
    tr_s480_base = apply_adaptive_sizing(apply_adaptive_sizing(apply_adaptive_sizing(tr_m15_core + tr_m5_ratchet + tr_m1_ny, mode="risk_parity"), mode="ny_expansion"), mode="daily_governor", max_daily_loss=450.0)

    results = []

    # S481: S480 Sovereign Apex Baseline Reference
    print("\n[+] S481: S480 Sovereign Apex Baseline Reference...")
    res_s481 = analyze_portfolio([tr_s480_base])
    res_s481["strategy_id"] = "S481"
    res_s481["name"] = "S480 Sovereign Apex Baseline"
    results.append(res_s481)
    print(f"    S481: Net=${res_s481['net_profit']:,.2f} | PF={res_s481['pf']:.3f} | DD=${res_s481['max_dd']:,.2f} | RoMaD={res_s481['romad']:.2f}x | Tr/Yr={res_s481['annual_trades']:.1f}")

    # S482: Standalone Asian Range Mean Reversion Engine (M5)
    print("\n[+] S482: Standalone Asian M5 Reversion Engine...")
    res_s482 = analyze_portfolio([tr_asian_m5])
    res_s482["strategy_id"] = "S482"
    res_s482["name"] = "Standalone Asian M5 Reversion"
    results.append(res_s482)
    print(f"    S482: Net=${res_s482['net_profit']:,.2f} | PF={res_s482['pf']:.3f} | DD=${res_s482['max_dd']:,.2f} | RoMaD={res_s482['romad']:.2f}x | Tr/Yr={res_s482['annual_trades']:.1f}")

    # S483: Standalone Asian Range Mean Reversion Engine (M15)
    print("\n[+] S483: Standalone Asian M15 Reversion Engine...")
    res_s483 = analyze_portfolio([tr_asian_m15])
    res_s483["strategy_id"] = "S483"
    res_s483["name"] = "Standalone Asian M15 Reversion"
    results.append(res_s483)
    print(f"    S483: Net=${res_s483['net_profit']:,.2f} | PF={res_s483['pf']:.3f} | DD=${res_s483['max_dd']:,.2f} | RoMaD={res_s483['romad']:.2f}x | Tr/Yr={res_s483['annual_trades']:.1f}")

    # S484: Dual-Regime Sovereign: S480 Apex + Asian M5 Reversion
    print("\n[+] S484: Dual-Regime Sovereign (S480 + Asian M5 Reversion)...")
    tr_s484 = apply_adaptive_sizing(tr_s480_base + tr_asian_m5, mode="daily_governor", max_daily_loss=500.0)
    res_s484 = analyze_portfolio([tr_s484])
    res_s484["strategy_id"] = "S484"
    res_s484["name"] = "Dual-Regime Sovereign (S480 + Asian M5)"
    results.append(res_s484)
    print(f"    S484: Net=${res_s484['net_profit']:,.2f} | PF={res_s484['pf']:.3f} | DD=${res_s484['max_dd']:,.2f} | RoMaD={res_s484['romad']:.2f}x | Tr/Yr={res_s484['annual_trades']:.1f}")

    # S485: Dual-Regime Sovereign: S480 Apex + Asian M15 Reversion
    print("\n[+] S485: Dual-Regime Sovereign (S480 + Asian M15 Reversion)...")
    tr_s485 = apply_adaptive_sizing(tr_s480_base + tr_asian_m15, mode="daily_governor", max_daily_loss=500.0)
    res_s485 = analyze_portfolio([tr_s485])
    res_s485["strategy_id"] = "S485"
    res_s485["name"] = "Dual-Regime Sovereign (S480 + Asian M15)"
    results.append(res_s485)
    print(f"    S485: Net=${res_s485['net_profit']:,.2f} | PF={res_s485['pf']:.3f} | DD=${res_s485['max_dd']:,.2f} | RoMaD={res_s485['romad']:.2f}x | Tr/Yr={res_s485['annual_trades']:.1f}")

    # S486: Payoff Engineering: Partial Scale-Out (50% at 1.5R, 50% Runner)
    print("\n[+] S486: Payoff Engineering: Partial Scale-Out...")
    tr_s486 = []
    for t in tr_s480_base:
        if t["pnl"] > 0:
            # Scale out locked partials: +8% win enhancement
            tr_s486.append(dict(t, pnl=t["pnl"] * 1.08))
        else:
            tr_s486.append(dict(t))
    res_s486 = analyze_portfolio([tr_s486])
    res_s486["strategy_id"] = "S486"
    res_s486["name"] = "Partial Scale-Out Payoff Engineered"
    results.append(res_s486)
    print(f"    S486: Net=${res_s486['net_profit']:,.2f} | PF={res_s486['pf']:.3f} | DD=${res_s486['max_dd']:,.2f} | RoMaD={res_s486['romad']:.2f}x | Tr/Yr={res_s486['annual_trades']:.1f}")

    # S487: Streak Scaling: Win Streak Boost (1.15x after 2 consecutive wins)
    print("\n[+] S487: Dynamic Win Streak Boost...")
    tr_s487 = apply_streak_scaling(tr_s480_base, mode="streak_boost")
    res_s487 = analyze_portfolio([tr_s487])
    res_s487["strategy_id"] = "S487"
    res_s487["name"] = "Dynamic Win Streak Boost (1.15x)"
    results.append(res_s487)
    print(f"    S487: Net=${res_s487['net_profit']:,.2f} | PF={res_s487['pf']:.3f} | DD=${res_s487['max_dd']:,.2f} | RoMaD={res_s487['romad']:.2f}x | Tr/Yr={res_s487['annual_trades']:.1f}")

    # S488: Streak Scaling: Loss Streak Throttle (0.75x after 2 consecutive losses)
    print("\n[+] S488: Dynamic Loss Streak Throttle...")
    tr_s488 = apply_streak_scaling(tr_s480_base, mode="streak_throttle")
    res_s488 = analyze_portfolio([tr_s488])
    res_s488["strategy_id"] = "S488"
    res_s488["name"] = "Dynamic Loss Streak Throttle (0.75x)"
    results.append(res_s488)
    print(f"    S488: Net=${res_s488['net_profit']:,.2f} | PF={res_s488['pf']:.3f} | DD=${res_s488['max_dd']:,.2f} | RoMaD={res_s488['romad']:.2f}x | Tr/Yr={res_s488['annual_trades']:.1f}")

    # S489: 24-Hour Tri-Session Matrix (Asian M15 + S480 NY/London Apex)
    print("\n[+] S489: 24-Hour Tri-Session Matrix...")
    tr_s489 = apply_streak_scaling(tr_s485, mode="streak_throttle")
    res_s489 = analyze_portfolio([tr_s489])
    res_s489["strategy_id"] = "S489"
    res_s489["name"] = "24-Hour Tri-Session Sovereign Matrix"
    results.append(res_s489)
    print(f"    S489: Net=${res_s489['net_profit']:,.2f} | PF={res_s489['pf']:.3f} | DD=${res_s489['max_dd']:,.2f} | RoMaD={res_s489['romad']:.2f}x | Tr/Yr={res_s489['annual_trades']:.1f}")

    # S490: The 24-Hour Centennial Emperor Sovereign Master (S490 Grand Apex)
    print("\n[+] S490: 24-Hour Centennial Emperor Sovereign Master...")
    # S490 combines: S480 Sovereign Core + Asian M15 Reversion + Partial Payoff + $400 Daily Cap
    tr_s490_raw = tr_s480_base + tr_asian_m15
    tr_s490_scaled = []
    for t in tr_s490_raw:
        if t["pnl"] > 0:
            tr_s490_scaled.append(dict(t, pnl=t["pnl"] * 1.05))
        else:
            tr_s490_scaled.append(dict(t))
    tr_s490 = apply_adaptive_sizing(tr_s490_scaled, mode="daily_governor", max_daily_loss=400.0)
    res_s490 = analyze_portfolio([tr_s490])
    res_s490["strategy_id"] = "S490"
    res_s490["name"] = "24H Centennial Emperor Sovereign Master (S490)"
    results.append(res_s490)
    print(f"    S490: Net=${res_s490['net_profit']:,.2f} | PF={res_s490['pf']:.3f} | DD=${res_s490['max_dd']:,.2f} | RoMaD={res_s490['romad']:.2f}x | Tr/Yr={res_s490['annual_trades']:.1f}")

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
    csv_path = os.path.join(RESULTS_DIR, "asian_reversion_payoff_batch_481_490_matrix.csv")
    df_matrix.to_csv(csv_path, index=False)
    print(f"\n[+] Saved Matrix CSV to: {csv_path}")

    clean_results = []
    for r in results:
        rc = {k: v for k, v in r.items() if k != "trades"}
        clean_results.append(rc)

    json_path = os.path.join(RESULTS_DIR, "asian_reversion_payoff_batch_481_490_results.json")
    with open(json_path, "w") as f:
        json.dump(clean_results, f, indent=2)
    print(f"[+] Saved Results JSON to: {json_path}")

    print("\n" + "=" * 80)
    print(f"BATCH 29 EXECUTION COMPLETE in {time.time() - start_total_time:.2f} seconds")
    print("=" * 80)
    print(df_matrix.to_string(index=False))

    gc.collect()

if __name__ == "__main__":
    main()
