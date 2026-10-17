#!/usr/bin/env python3
"""
===============================================================================
SCALPING FRONTIER BATCH 20: STRATEGIES 391 - 400
GRAND MASTER PORTFOLIO SYNTHESIS & CENTENNIAL SCALPING SUITE
===============================================================================
Objective:
Synthesize all 20 batches of empirical research (200 scalping variants, 6 years,
141,567 M15 bars, $0.25 spread + $6.00 comm) into the definitive Capital Allocation,
Prop-Firm Governed, and Dynamic Compounding production benchmarks.
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

from execution_latency_scalper_batch_381_390 import (
    compute_atr, compute_ema, run_supertrend_exec, run_ttm_squeeze_exec
)
from simulate_scalping_master_ensemble_batch_291_300 import (
    run_engine_zl_macd, run_engine_fvg_retest
)

# -----------------------------------------------------------------------------
# Compounding and Risk Governor Simulators
# -----------------------------------------------------------------------------
def simulate_compounding_suite(trades_list, initial_capital=10000.0, risk_pct=0.01):
    trades_sorted = sorted(trades_list, key=lambda x: str(x["entry_time"]))
    equity = initial_capital
    comp_trades = []
    
    for t in trades_sorted:
        # Scale lot proportionally to equity (1% risk on $10k = 0.10 lot)
        lot_scale = max(equity / initial_capital, 0.5)
        scaled_pnl = t["pnl"] * lot_scale
        equity += scaled_pnl
        comp_trades.append({
            "pnl": scaled_pnl,
            "entry_time": t.get("entry_time", ""),
            "exit_time": t.get("exit_time", t.get("entry_time", "")),
            "year": t.get("year", 2020),
            "month": t.get("month", ""),
            "engine": t.get("engine", "")
        })
    return comp_trades

def simulate_governed_suite(trades_list, monthly_loss_cap=1200.0):
    trades_sorted = sorted(trades_list, key=lambda x: str(x["entry_time"]))
    governed_trades = []
    
    # Track monthly pnl
    current_month = ""
    month_pnl = 0.0
    month_locked = False
    
    for t in trades_sorted:
        m = t["month"]
        if m != current_month:
            current_month = m
            month_pnl = 0.0
            month_locked = False
            
        if not month_locked:
            month_pnl += t["pnl"]
            governed_trades.append(t)
            if month_pnl <= -monthly_loss_cap:
                month_locked = True  # lock trading for the rest of this month
                
    return governed_trades

# -----------------------------------------------------------------------------
# Performance Metrics
# -----------------------------------------------------------------------------
def analyze_trades(trades_list, name, strategy_id):
    if not trades_list:
        return {
            "strategy_id": strategy_id, "strategy_name": name,
            "annual_trades": 0.0, "net_profit": 0.0, "pf": 0.0,
            "win_rate": 0.0, "max_dd": 0.0, "romad": 0.0, "mcr": 0.0, "status": "REJECTED"
        }
    trades_sorted = sorted(trades_list, key=lambda x: str(x["entry_time"]))
    pnls = np.array([t["pnl"] for t in trades_sorted], dtype=np.float64)
    net_profit = np.sum(pnls)
    gross_win = np.sum(pnls[pnls > 0])
    gross_loss = abs(np.sum(pnls[pnls < 0]))
    pf = (gross_win / gross_loss) if gross_loss > 0 else 99.0
    win_rate = (np.sum(pnls > 0) / len(pnls)) * 100.0

    equity = np.cumsum(pnls)
    peaks = np.maximum.accumulate(equity)
    dds = peaks - equity
    max_dd = np.max(dds) if len(dds) > 0 else 1.0
    romad = (net_profit / max_dd) if max_dd > 0 else 0.0

    df_t = pd.DataFrame(trades_sorted)
    m_pnl = df_t.groupby("month")["pnl"].sum()
    total_months = len(m_pnl)
    win_months = np.sum(m_pnl > 0)
    mcr = (win_months / total_months * 100.0) if total_months > 0 else 0.0
    annual_trades = round(len(trades_sorted) / 6.0, 1)

    status = "CHAMPION" if (pf >= 1.15 and annual_trades >= 300) else ("TACTICAL CANDIDATE" if net_profit > 0 else "REJECTED")

    return {
        "strategy_id": strategy_id,
        "strategy_name": name,
        "total_trades": len(trades_sorted),
        "annual_trades": annual_trades,
        "net_profit": round(float(net_profit), 2),
        "pf": round(float(pf), 3),
        "win_rate": round(float(win_rate), 2),
        "max_dd": round(float(max_dd), 2),
        "romad": round(float(romad), 2),
        "mcr": round(float(mcr), 2),
        "status": status
    }

# -----------------------------------------------------------------------------
# Main Pipeline
# -----------------------------------------------------------------------------
def main():
    print("=" * 80)
    print("STARTING SCALPING BATCH 20: STRATEGIES 391 - 400")
    print("GRAND MASTER PORTFOLIO SYNTHESIS & CENTENNIAL SCALPING SUITE")
    print("=" * 80)
    t0 = time.time()

    print("Loading XAUUSD M15 Dataset (2020 - 2025)...")
    df_m15 = pd.read_parquet(os.path.join(DATA_DIR, "XAUUSD_M15.parquet"))
    opens = df_m15["open"].values.astype(np.float64)
    highs = df_m15["high"].values.astype(np.float64)
    lows = df_m15["low"].values.astype(np.float64)
    closes = df_m15["close"].values.astype(np.float64)
    dates = df_m15.index
    months = np.array([f"{d.year}-{d.month:02d}" for d in dates])

    atr14 = compute_atr(highs, lows, closes, 14)
    ema200 = compute_ema(closes, 200)

    print("Generating Core Scalping Drivers...")
    t_st = run_supertrend_exec(opens, highs, lows, closes, atr14, ema200, dates, exec_mode="market")
    t_ttm_market = run_ttm_squeeze_exec(opens, highs, lows, closes, atr14, ema200, dates, exec_mode="market")
    t_ttm_limit = run_ttm_squeeze_exec(opens, highs, lows, closes, atr14, ema200, dates, exec_mode="limit", limit_pullback_atr=0.2)
    
    t_macd = run_engine_zl_macd(opens, highs, lows, closes, atr14, months)
    t_fvg = run_engine_fvg_retest(opens, highs, lows, closes, atr14, ema200, months)
    for t in t_macd: 
        t["entry_time"] = dates[t["entry_idx"]]
        t["exit_time"] = dates[t["exit_idx"]]
        t["year"] = dates[t["entry_idx"]].year
    for t in t_fvg: 
        t["entry_time"] = dates[t["entry_idx"]]
        t["exit_time"] = dates[t["exit_idx"]]
        t["year"] = dates[t["entry_idx"]].year

    results = []

    # S391: Pure Trend Core (S291 Solo Supertrend)
    print("\nSimulating S391: Pure Trend Core...")
    results.append(analyze_trades(t_st, "Pure Trend Core (S291 Solo Supertrend)", "S391"))

    # S392: Tactical Duo B Standard (S296 Supertrend + TTM Squeeze Market)
    print("Simulating S392: Tactical Duo B Standard...")
    t_s296 = t_st + t_ttm_market
    results.append(analyze_trades(t_s296, "Tactical Duo B Standard (S296 Market)", "S392"))

    # S393: Tactical Duo B Hybrid (S389 ST Market + TTM Limit -0.2x ATR)
    print("Simulating S393: Tactical Duo B Hybrid...")
    t_s389 = t_st + t_ttm_limit
    results.append(analyze_trades(t_s389, "Tactical Duo B Hybrid (S389 Market+Limit)", "S393"))

    # S394: Master Scalper Quartet Standard (S300 Balanced 4-Engine Suite)
    print("Simulating S394: Master Scalper Quartet Standard...")
    t_s300 = []
    for t in t_st: tw = dict(t); tw["pnl"] = t["pnl"] * 1.0; t_s300.append(tw)
    for t in t_macd: tw = dict(t); tw["pnl"] = t["pnl"] * 0.7; t_s300.append(tw)
    for t in t_ttm_market: tw = dict(t); tw["pnl"] = t["pnl"] * 0.8; t_s300.append(tw)
    for t in t_fvg: tw = dict(t); tw["pnl"] = t["pnl"] * 0.5; t_s300.append(tw)
    results.append(analyze_trades(t_s300, "Master Scalper Quartet Standard (S300 Suite)", "S394"))

    # S395: Master Scalper Quartet Governed ($1,200 Monthly Loss Governor)
    print("Simulating S395: Master Scalper Quartet Governed...")
    t_s300_gov = simulate_governed_suite(t_s300, monthly_loss_cap=1200.0)
    results.append(analyze_trades(t_s300_gov, "Master Scalper Quartet Governed ($1.2k Cap)", "S395"))

    # S396: Dynamic Compounding Hybrid Duo (S389 Compounding 1% Risk)
    print("Simulating S396: Dynamic Compounding Hybrid Duo...")
    t_s396_comp = simulate_compounding_suite(t_s389, initial_capital=10000.0, risk_pct=0.01)
    results.append(analyze_trades(t_s396_comp, "Dynamic Compounding Hybrid Duo (1% Risk)", "S396"))

    # S397: Dynamic Compounding Master Quartet (S300 Compounding 1% Risk)
    print("Simulating S397: Dynamic Compounding Master Quartet...")
    t_s397_comp = simulate_compounding_suite(t_s300, initial_capital=10000.0, risk_pct=0.01)
    results.append(analyze_trades(t_s397_comp, "Dynamic Compounding Master Quartet (1% Risk)", "S397"))

    # S398: Risk-Parity Allocated Sovereign Portfolio
    print("Simulating S398: Risk-Parity Allocated Sovereign Portfolio...")
    # Allocations inversely proportional to volatility/drawdown
    t_s398 = []
    for t in t_st: tw = dict(t); tw["pnl"] = t["pnl"] * 1.0; t_s398.append(tw)          # Base: 0.10 lot
    for t in t_ttm_limit: tw = dict(t); tw["pnl"] = t["pnl"] * 0.9; t_s398.append(tw)    # Limit Duo: 0.09 lot
    for t in t_macd: tw = dict(t); tw["pnl"] = t["pnl"] * 0.6; t_s398.append(tw)         # Wave: 0.06 lot
    for t in t_fvg: tw = dict(t); tw["pnl"] = t["pnl"] * 0.4; t_s398.append(tw)          # FVG: 0.04 lot
    results.append(analyze_trades(t_s398, "Risk-Parity Allocated Sovereign Portfolio", "S398"))

    # S399: Conservative Prop-Firm Edition (Strict $1,000 Monthly Cap + Hybrid Execution)
    print("Simulating S399: Conservative Prop-Firm Edition...")
    t_s399 = simulate_governed_suite(t_s389, monthly_loss_cap=1000.0)
    results.append(analyze_trades(t_s399, "Conservative Prop-Firm Edition ($1,000 Cap)", "S399"))

    # S400: Centennial Grand Champion Scalper Suite (Production Apex)
    print("Simulating S400: Centennial Grand Champion Scalper Suite...")
    # The ultimate institutional deployment: Hybrid Duo + Risk-Parity Governor
    t_s400 = simulate_governed_suite(t_s398, monthly_loss_cap=1500.0)
    results.append(analyze_trades(t_s400, "Centennial Grand Champion Scalper Suite (Apex)", "S400"))

    # Export Results
    df_out = pd.DataFrame(results)
    csv_path = os.path.join(RESULTS_DIR, "massive_scalping_grand_synthesis_batch_391_400_matrix.csv")
    json_path = os.path.join(RESULTS_DIR, "massive_scalping_grand_synthesis_batch_391_400_results.json")

    df_out.to_csv(csv_path, index=False)
    with open(json_path, "w") as f:
        json.dump({"generated_at": time.strftime("%Y-%m-%d %H:%M:%S"), "total_runtime_s": round(time.time() - t0, 2), "results": results}, f, indent=2)

    print("\n" + "=" * 80)
    print("BATCH 20 (S391 - S400) COMPLETED IN {:.2f}s".format(time.time() - t0))
    print("=" * 80)
    print(df_out[["strategy_id", "strategy_name", "annual_trades", "net_profit", "pf", "win_rate", "max_dd", "romad", "mcr", "status"]].to_string(index=False))
    print("=" * 80)

if __name__ == "__main__":
    main()
