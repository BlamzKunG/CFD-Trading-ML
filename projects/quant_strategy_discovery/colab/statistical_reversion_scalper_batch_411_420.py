#!/usr/bin/env python3
"""
===============================================================================
SCALPING FRONTIER BATCH 22: STRATEGIES 411 - 420
STATISTICAL ARBITRAGE, Z-SCORE EXTREMES & SESSION-REGIME MEAN REVERSION
===============================================================================
Objective:
Develop an orthogonal Statistical Mean-Reversion Scalper to hedge trend drawdowns:
1. Rolling Price Z-Score Extreme Reversions (|Z| >= 2.5 sigma).
2. Session-Gated Asian Mean-Reversion (22:00 - 07:00 UTC).
3. Hurst Exponent / ADX Regime-Switched Mean Reversion.
4. Orthogonal Ensemble Pairing (Trend Core + Mean Reversion Cushion).
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

# -----------------------------------------------------------------------------
# Fast Statistical Calculations
# -----------------------------------------------------------------------------
def compute_zscore(series: np.ndarray, period: int = 50):
    s = pd.Series(series)
    mean = s.rolling(period).mean().values
    std = s.rolling(period).std().fillna(1.0).values
    z = (series - mean) / np.maximum(std, 1e-4)
    return z, mean, std

def compute_rsi(closes: np.ndarray, period: int = 2):
    n = len(closes)
    deltas = np.diff(closes)
    gains = np.where(deltas > 0, deltas, 0.0)
    losses = np.where(deltas < 0, -deltas, 0.0)

    avg_gain = np.zeros(n)
    avg_loss = np.zeros(n)

    avg_gain[period] = np.mean(gains[:period])
    avg_loss[period] = np.mean(losses[:period])

    for i in range(period + 1, n):
        avg_gain[i] = (avg_gain[i - 1] * (period - 1) + gains[i - 1]) / period
        avg_loss[i] = (avg_loss[i - 1] * (period - 1) + losses[i - 1]) / period

    rs = avg_gain / np.maximum(avg_loss, 1e-6)
    rsi = 100.0 - (100.0 / (1.0 + rs))
    return rsi

# -----------------------------------------------------------------------------
# Statistical Mean Reversion Simulators
# -----------------------------------------------------------------------------
def run_zscore_reversion(opens, highs, lows, closes, atr, dates,
                         z_thresh=2.5, period=50, sl_mult=2.0, max_bars_hold=16,
                         session_filter=None, unit_size=10.0, spread=0.25, comm=0.60):
    n = len(closes)
    z, mean, std = compute_zscore(closes, period)
    hours = np.array([d.hour for d in dates])

    trades = []
    pos = 0
    entry_p = 0.0
    sl_p = 0.0
    entry_idx = 0

    for i in range(period + 5, n - 2):
        # 1. Manage Active Position
        if pos == 1:
            hit = False
            exit_p = 0.0
            if lows[i] <= sl_p:
                hit = True; exit_p = sl_p
            elif closes[i] >= mean[i]:  # Reverted to mean
                hit = True; exit_p = opens[i + 1] - spread * 0.5
            elif (i - entry_idx) >= max_bars_hold:  # Time stop
                hit = True; exit_p = opens[i + 1] - spread * 0.5

            if hit:
                pnl = (exit_p - entry_p) * unit_size - (spread + (comm / unit_size)) * unit_size
                trades.append({
                    "pnl": pnl, "entry_time": dates[entry_idx], "exit_time": dates[i],
                    "year": dates[entry_idx].year, "month": f"{dates[entry_idx].year}-{dates[entry_idx].month:02d}",
                    "entry_idx": entry_idx, "exit_idx": i, "engine": "ZScore_MR"
                })
                pos = 0

        elif pos == -1:
            hit = False
            exit_p = 0.0
            if highs[i] >= sl_p:
                hit = True; exit_p = sl_p
            elif closes[i] <= mean[i]:  # Reverted to mean
                hit = True; exit_p = opens[i + 1] + spread * 0.5
            elif (i - entry_idx) >= max_bars_hold:  # Time stop
                hit = True; exit_p = opens[i + 1] + spread * 0.5

            if hit:
                pnl = (entry_p - exit_p) * unit_size - (spread + (comm / unit_size)) * unit_size
                trades.append({
                    "pnl": pnl, "entry_time": dates[entry_idx], "exit_time": dates[i],
                    "year": dates[entry_idx].year, "month": f"{dates[entry_idx].year}-{dates[entry_idx].month:02d}",
                    "entry_idx": entry_idx, "exit_idx": i, "engine": "ZScore_MR"
                })
                pos = 0

        # 2. Entry Triggers
        if pos == 0:
            time_ok = True
            if session_filter == "asian":
                # 22:00 to 07:00 UTC
                if not (hours[i] >= 22 or hours[i] <= 7):
                    time_ok = False

            if time_ok:
                if z[i] <= -z_thresh and z[i - 1] > -z_thresh:
                    pos = 1
                    entry_idx = i + 1
                    entry_p = opens[i + 1] + spread * 0.5
                    sl_p = entry_p - (sl_mult * atr[i])
                elif z[i] >= z_thresh and z[i - 1] < z_thresh:
                    pos = -1
                    entry_idx = i + 1
                    entry_p = opens[i + 1] - spread * 0.5
                    sl_p = entry_p + (sl_mult * atr[i])

    return trades

def run_connors_rsi2_scalper(opens, highs, lows, closes, atr, ema200, dates,
                             rsi_lo=10.0, rsi_hi=90.0, sl_mult=2.0, max_bars_hold=8,
                             unit_size=10.0, spread=0.25, comm=0.60):
    n = len(closes)
    rsi2 = compute_rsi(closes, 2)
    ema5 = compute_ema(closes, 5)

    trades = []
    pos = 0
    entry_p = 0.0
    sl_p = 0.0
    entry_idx = 0

    for i in range(200, n - 2):
        if pos == 1:
            hit = False
            exit_p = 0.0
            if lows[i] <= sl_p: hit = True; exit_p = sl_p
            elif closes[i] >= ema5[i]: hit = True; exit_p = opens[i + 1] - spread * 0.5
            elif (i - entry_idx) >= max_bars_hold: hit = True; exit_p = opens[i + 1] - spread * 0.5
            if hit:
                pnl = (exit_p - entry_p) * unit_size - (spread + (comm / unit_size)) * unit_size
                trades.append({
                    "pnl": pnl, "entry_time": dates[entry_idx], "exit_time": dates[i],
                    "year": dates[entry_idx].year, "month": f"{dates[entry_idx].year}-{dates[entry_idx].month:02d}",
                    "entry_idx": entry_idx, "exit_idx": i, "engine": "RSI2_Scalper"
                })
                pos = 0

        elif pos == -1:
            hit = False
            exit_p = 0.0
            if highs[i] >= sl_p: hit = True; exit_p = sl_p
            elif closes[i] <= ema5[i]: hit = True; exit_p = opens[i + 1] + spread * 0.5
            elif (i - entry_idx) >= max_bars_hold: hit = True; exit_p = opens[i + 1] + spread * 0.5
            if hit:
                pnl = (entry_p - exit_p) * unit_size - (spread + (comm / unit_size)) * unit_size
                trades.append({
                    "pnl": pnl, "entry_time": dates[entry_idx], "exit_time": dates[i],
                    "year": dates[entry_idx].year, "month": f"{dates[entry_idx].year}-{dates[entry_idx].month:02d}",
                    "entry_idx": entry_idx, "exit_idx": i, "engine": "RSI2_Scalper"
                })
                pos = 0

        if pos == 0:
            # Trend-Aligned Mean Reversion: Buy extreme dip in uptrend, Sell extreme rally in downtrend
            if closes[i] > ema200[i] and rsi2[i] <= rsi_lo:
                pos = 1
                entry_idx = i + 1
                entry_p = opens[i + 1] + spread * 0.5
                sl_p = entry_p - (sl_mult * atr[i])
            elif closes[i] < ema200[i] and rsi2[i] >= rsi_hi:
                pos = -1
                entry_idx = i + 1
                entry_p = opens[i + 1] - spread * 0.5
                sl_p = entry_p + (sl_mult * atr[i])

    return trades

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

    status = "CHAMPION" if (pf >= 1.20 and annual_trades >= 300) else ("TACTICAL CANDIDATE" if net_profit > 0 else "REJECTED")

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
    print("STARTING SCALPING BATCH 22: STRATEGIES 411 - 420")
    print("STATISTICAL ARBITRAGE, Z-SCORE EXTREMES & SESSION-REGIME MEAN REVERSION")
    print("=" * 80)
    t0 = time.time()

    print("Loading XAUUSD M15 Dataset...")
    df_m15 = pd.read_parquet(os.path.join(DATA_DIR, "XAUUSD_M15.parquet"))
    opens = df_m15["open"].values.astype(np.float64)
    highs = df_m15["high"].values.astype(np.float64)
    lows = df_m15["low"].values.astype(np.float64)
    closes = df_m15["close"].values.astype(np.float64)
    dates = df_m15.index

    atr14 = compute_atr(highs, lows, closes, 14)
    ema200 = compute_ema(closes, 200)

    print("Running Base Trend & Squeeze Drivers...")
    t_st = run_supertrend_exec(opens, highs, lows, closes, atr14, ema200, dates, exec_mode="market")
    t_ttm = run_ttm_squeeze_exec(opens, highs, lows, closes, atr14, ema200, dates, exec_mode="market")
    t_s296 = t_st + t_ttm

    results = []

    # S411: Rolling 50-Bar Price Z-Score Extreme Reversion (|Z| >= 2.5 sigma)
    print("\nSimulating S411: Rolling 50-Bar Z-Score Reversion (|Z| >= 2.5)...")
    t_z25 = run_zscore_reversion(opens, highs, lows, closes, atr14, dates, z_thresh=2.5, period=50, sl_mult=2.0)
    results.append(analyze_trades(t_z25, "Solo Z-Score Extreme Reversion (|Z| >= 2.5)", "S411"))

    # S412: High-Frequency Z-Score Reversion (|Z| >= 2.0 sigma)
    print("Simulating S412: High-Frequency Z-Score Reversion (|Z| >= 2.0)...")
    t_z20 = run_zscore_reversion(opens, highs, lows, closes, atr14, dates, z_thresh=2.0, period=50, sl_mult=2.0)
    results.append(analyze_trades(t_z20, "High-Frequency Z-Score Reversion (|Z| >= 2.0)", "S412"))

    # S413: Session-Gated Asian Z-Score Mean Reversion (22:00 - 07:00 UTC)
    print("Simulating S413: Session-Gated Asian Z-Score Reversion...")
    t_z_asian = run_zscore_reversion(opens, highs, lows, closes, atr14, dates, z_thresh=2.2, period=50, sl_mult=2.0, session_filter="asian")
    results.append(analyze_trades(t_z_asian, "Asian Session Z-Score Reversion (22-07 UTC)", "S413"))

    # S414: Trend-Aligned Connors RSI-2 Extreme Pullback Scalper
    print("Simulating S414: Trend-Aligned Connors RSI-2 Pullback Scalper...")
    t_rsi2 = run_connors_rsi2_scalper(opens, highs, lows, closes, atr14, ema200, dates, rsi_lo=10.0, rsi_hi=90.0, sl_mult=2.0)
    results.append(analyze_trades(t_rsi2, "Trend-Aligned Connors RSI-2 Pullback Scalper", "S414"))

    # S415: Aggressive Connors RSI-2 Extreme Pullback Scalper (RSI <= 5 or >= 95)
    print("Simulating S415: Aggressive Connors RSI-2 Pullback Scalper...")
    t_rsi2_agg = run_connors_rsi2_scalper(opens, highs, lows, closes, atr14, ema200, dates, rsi_lo=5.0, rsi_hi=95.0, sl_mult=2.0)
    results.append(analyze_trades(t_rsi2_agg, "Aggressive Connors RSI-2 Extremes (<=5 / >=95)", "S415"))

    # S416: Orthogonal Ensemble A: S296 Tactical Duo + Z-Score Extreme Reversion
    print("Simulating S416: Orthogonal Ensemble A (S296 + Z-Score Reversion)...")
    t_s416 = t_s296 + t_z25
    results.append(analyze_trades(t_s416, "Orthogonal Ensemble A: S296 + Z-Score Reversion", "S416"))

    # S417: Orthogonal Ensemble B: S296 Tactical Duo + Asian Z-Score Reversion
    print("Simulating S417: Orthogonal Ensemble B (S296 + Asian Reversion)...")
    t_s417 = t_s296 + t_z_asian
    results.append(analyze_trades(t_s417, "Orthogonal Ensemble B: S296 + Asian Reversion", "S417"))

    # S418: Orthogonal Ensemble C: S296 Tactical Duo + Connors RSI-2 Pullback
    print("Simulating S418: Orthogonal Ensemble C (S296 + Connors RSI-2)...")
    t_s418 = t_s296 + t_rsi2
    results.append(analyze_trades(t_s418, "Orthogonal Ensemble C: S296 + Connors RSI-2", "S418"))

    # S419: Triple Orthogonal Suite: Supertrend (Trend) + TTM (Breakout) + RSI-2 (Pullback)
    print("Simulating S419: Triple Orthogonal Multi-Regime Suite...")
    # Balanced weights: ST (1.0), TTM (0.8), RSI2 (0.6)
    t_s419 = []
    for t in t_st: tw = dict(t); tw["pnl"] = t["pnl"] * 1.0; t_s419.append(tw)
    for t in t_ttm: tw = dict(t); tw["pnl"] = t["pnl"] * 0.8; t_s419.append(tw)
    for t in t_rsi2: tw = dict(t); tw["pnl"] = t["pnl"] * 0.6; t_s419.append(tw)
    results.append(analyze_trades(t_s419, "Triple Orthogonal Suite (ST + TTM + RSI2)", "S419"))

    # S420: Centennial Statistical-Trend Hybrid Master Suite (Apex Multi-Regime)
    print("Simulating S420: Centennial Statistical-Trend Hybrid Master Suite...")
    # ST (1.0) + TTM (0.8) + RSI2 (0.6) + Asian Z-Score (0.4)
    t_s420 = []
    for t in t_st: tw = dict(t); tw["pnl"] = t["pnl"] * 1.0; t_s420.append(tw)
    for t in t_ttm: tw = dict(t); tw["pnl"] = t["pnl"] * 0.8; t_s420.append(tw)
    for t in t_rsi2: tw = dict(t); tw["pnl"] = t["pnl"] * 0.6; t_s420.append(tw)
    for t in t_z_asian: tw = dict(t); tw["pnl"] = t["pnl"] * 0.4; t_s420.append(tw)
    results.append(analyze_trades(t_s420, "Centennial Statistical-Trend Hybrid Master (Apex)", "S420"))

    # Export Results
    df_out = pd.DataFrame(results)
    csv_path = os.path.join(RESULTS_DIR, "massive_scalping_statistical_reversion_batch_411_420_matrix.csv")
    json_path = os.path.join(RESULTS_DIR, "massive_scalping_statistical_reversion_batch_411_420_results.json")

    df_out.to_csv(csv_path, index=False)
    with open(json_path, "w") as f:
        json.dump({"generated_at": time.strftime("%Y-%m-%d %H:%M:%S"), "total_runtime_s": round(time.time() - t0, 2), "results": results}, f, indent=2)

    print("\n" + "=" * 80)
    print("BATCH 22 (S411 - S420) COMPLETED IN {:.2f}s".format(time.time() - t0))
    print("=" * 80)
    print(df_out[["strategy_id", "strategy_name", "annual_trades", "net_profit", "pf", "win_rate", "max_dd", "romad", "mcr", "status"]].to_string(index=False))
    print("=" * 80)

if __name__ == "__main__":
    main()
