#!/usr/bin/env python3
"""
===============================================================================
SCALPING STRESS & ROBUSTNESS BATCH 11: STRATEGIES 301 - 310
MONTE CARLO (5,000 SIMULATIONS) & BROKER FRICTION STRESS TESTING
ON STRATEGY 296 (TACTICAL DUO) & STRATEGY 300 (SOVEREIGN QUARTET)
===============================================================================
Stress Dimensions:
1. Monte Carlo Trade Reshuffling & Bootstrapping (5,000 iterations)
2. Spread Inflation Test: $0.25 (Base) -> $0.35 (Severe) -> $0.50 (Extreme)
3. Commission Inflation Test: $6.00/lot (Base) -> $8.00/lot -> $10.00/lot
4. Worst-Case Drawdown at 95% & 99% Confidence Intervals
===============================================================================
"""

import os
import sys
import time
import json
import numpy as np
import pandas as pd

if os.path.exists("/content/CFD-Trading-ML"):
    REPO_ROOT = "/content/CFD-Trading-ML"
else:
    REPO_ROOT = "/root/CFD-Trading-ML"

DATA_DIR = os.path.join(REPO_ROOT, "projects/quant_strategy_discovery/data")
RESULTS_DIR = os.path.join(REPO_ROOT, "projects/quant_strategy_discovery/results")
os.makedirs(RESULTS_DIR, exist_ok=True)

def run_monte_carlo(pnls: np.ndarray, num_simulations=5000) -> dict:
    n = len(pnls)
    sim_max_dds = np.zeros(num_simulations)
    sim_net_pnls = np.zeros(num_simulations)
    sim_pfs = np.zeros(num_simulations)

    for s in range(num_simulations):
        # Bootstrap with replacement
        sample_indices = np.random.randint(0, n, size=n)
        sample_pnls = pnls[sample_indices]

        net_pnl = np.sum(sample_pnls)
        sim_net_pnls[s] = net_pnl

        wins = np.sum(sample_pnls[sample_pnls > 0])
        losses = abs(np.sum(sample_pnls[sample_pnls < 0]))
        sim_pfs[s] = (wins / losses) if losses > 0 else 99.0

        equity = np.cumsum(sample_pnls)
        peak = np.maximum.accumulate(equity)
        dd = peak - equity
        sim_max_dds[s] = np.max(dd)

    return {
        "median_net_profit": round(float(np.median(sim_net_pnls)), 2),
        "p5_net_profit": round(float(np.percentile(sim_net_pnls, 5)), 2),
        "median_pf": round(float(np.median(sim_pfs)), 3),
        "p5_pf": round(float(np.percentile(sim_pfs, 5)), 3),
        "median_dd": round(float(np.median(sim_max_dds)), 2),
        "p95_dd": round(float(np.percentile(sim_max_dds, 95)), 2),
        "p99_dd": round(float(np.percentile(sim_max_dds, 99)), 2),
        "worst_simulated_dd": round(float(np.max(sim_max_dds)), 2)
    }

def main():
    print("=" * 80)
    print("STARTING SCALPING STRESS & ROBUSTNESS BATCH 11: STRATEGIES 301 - 310")
    print("MONTE CARLO BOOTSTRAP (5,000 SIMULATIONS) & BROKER FRICTION STRESS TEST")
    print("=" * 80)
    t0 = time.time()

    json_path = os.path.join(RESULTS_DIR, "massive_scalping_master_ensemble_batch_291_300_results.json")
    if not os.path.exists(json_path):
        print("Error: Batch 10 results not found!")
        return

    # Re-simulate S296 and S300 trade logs
    from simulate_scalping_master_ensemble_batch_291_300 import (
        run_engine_supertrend, run_engine_ttm_squeeze, run_engine_zl_macd, run_engine_fvg_retest,
        compute_atr, compute_ema
    )

    df_m15 = pd.read_parquet(os.path.join(DATA_DIR, "XAUUSD_M15.parquet"))
    opens = df_m15["open"].values.astype(np.float64)
    highs = df_m15["high"].values.astype(np.float64)
    lows = df_m15["low"].values.astype(np.float64)
    closes = df_m15["close"].values.astype(np.float64)
    dates = df_m15.index
    months = np.array([f"{d.year}-{d.month:02d}" for d in dates])

    atr14 = compute_atr(highs, lows, closes, 14)
    ema200 = compute_ema(closes, 200)

    # Scenarios:
    # 1. Baseline: Spread $0.25, Comm $0.60
    # 2. Elevated: Spread $0.35, Comm $0.80
    # 3. Severe: Spread $0.50, Comm $1.00
    scenarios = [
        {"name": "Baseline (Spread $0.25, Comm $0.60)", "spread": 0.25, "comm": 0.60},
        {"name": "Elevated (Spread $0.35, Comm $0.80)", "spread": 0.35, "comm": 0.80},
        {"name": "Severe (Spread $0.50, Comm $1.00)", "spread": 0.50, "comm": 1.00}
    ]

    results_stress = []

    for sc in scenarios:
        sp = sc["spread"]
        cm = sc["comm"]
        print(f"\n--- Running Scenario: {sc['name']} ---")

        t_st = run_engine_supertrend(opens, highs, lows, closes, atr14, ema200, months, spread=sp, comm=cm)
        t_ttm = run_engine_ttm_squeeze(opens, highs, lows, closes, atr14, ema200, months, spread=sp, comm=cm)
        t_macd = run_engine_zl_macd(opens, highs, lows, closes, atr14, months, spread=sp, comm=cm)
        t_fvg = run_engine_fvg_retest(opens, highs, lows, closes, atr14, ema200, months, spread=sp, comm=cm)

        # S296: Duo B (ST + TTM)
        t_296 = t_st + t_ttm
        pnls_296 = np.array([t["pnl"] for t in t_296])
        mc_296 = run_monte_carlo(pnls_296, num_simulations=5000)

        # S300: Balanced Quartet
        t_300 = []
        for t in t_st: tw = dict(t); tw["pnl"] = t["pnl"] * 1.0; t_300.append(tw)
        for t in t_macd: tw = dict(t); tw["pnl"] = t["pnl"] * 0.7; t_300.append(tw)
        for t in t_ttm: tw = dict(t); tw["pnl"] = t["pnl"] * 0.8; t_300.append(tw)
        for t in t_fvg: tw = dict(t); tw["pnl"] = t["pnl"] * 0.5; t_300.append(tw)
        pnls_300 = np.array([t["pnl"] for t in t_300])
        mc_300 = run_monte_carlo(pnls_300, num_simulations=5000)

        results_stress.append({
            "scenario": sc["name"],
            "strategy": "S296 Tactical Duo B (537 tr/yr)",
            "net_profit": round(float(np.sum(pnls_296)), 2),
            "pf": round(float(np.sum(pnls_296[pnls_296 > 0]) / abs(np.sum(pnls_296[pnls_296 < 0]))), 3),
            "monte_carlo_p95_dd": mc_296["p95_dd"],
            "monte_carlo_worst_dd": mc_296["worst_simulated_dd"]
        })

        results_stress.append({
            "scenario": sc["name"],
            "strategy": "S300 Master Quartet (1248 tr/yr)",
            "net_profit": round(float(np.sum(pnls_300)), 2),
            "pf": round(float(np.sum(pnls_300[pnls_300 > 0]) / abs(np.sum(pnls_300[pnls_300 < 0]))), 3),
            "monte_carlo_p95_dd": mc_300["p95_dd"],
            "monte_carlo_worst_dd": mc_300["worst_simulated_dd"]
        })

    df_stress = pd.DataFrame(results_stress)
    stress_csv = os.path.join(RESULTS_DIR, "massive_scalping_stress_batch_301_310_results.csv")
    stress_json = os.path.join(RESULTS_DIR, "massive_scalping_stress_batch_301_310_results.json")
    df_stress.to_csv(stress_csv, index=False)
    with open(stress_json, "w") as f:
        json.dump({"generated_at": time.strftime("%Y-%m-%d %H:%M:%S"), "total_runtime_s": round(time.time() - t0, 2), "results": results_stress}, f, indent=2)

    print("\n" + "=" * 80)
    print("BATCH 11 STRESS AUDIT COMPLETED IN {:.2f}s".format(time.time() - t0))
    print("=" * 80)
    print(df_stress.to_string(index=False))
    print("=" * 80)

if __name__ == "__main__":
    main()
