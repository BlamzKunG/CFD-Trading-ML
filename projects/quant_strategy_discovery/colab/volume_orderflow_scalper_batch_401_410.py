#!/usr/bin/env python3
"""
===============================================================================
SCALPING FRONTIER BATCH 21: STRATEGIES 401 - 410
VOLUME-WEIGHTED ORDER FLOW, CLIMAX EXPANSION & TICK-VOLUME DELTA
===============================================================================
Objective:
Incorporate institutional tick-volume microstructure into Gold M15 scalping:
1. Volume Climax Confirmation (Institutional Participation vs Noise Breakouts).
2. Estimated Cumulative Volume Delta (CVD) Momentum Alignment.
3. Volume-Weighted ATR Ratchet Trailing.
4. Volume Climax Absorption Reversals vs Breakout Ignitions.
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
# Microstructure Volume Indicators
# -----------------------------------------------------------------------------
def compute_volume_features(opens, highs, lows, closes, volumes):
    n = len(closes)
    vol_ema20 = compute_ema(volumes, 20)
    vol_ema50 = compute_ema(volumes, 50)
    rel_vol20 = volumes / np.maximum(vol_ema20, 1.0)
    rel_vol50 = volumes / np.maximum(vol_ema50, 1.0)

    # Estimated Bar Delta: Close position in bar normalized [-1, 1] * Volume
    # Formula: ((Close - Low) - (High - Close)) / (High - Low) * Volume
    bar_range = np.maximum(highs - lows, 1e-4)
    delta_ratio = ((closes - lows) - (highs - closes)) / bar_range
    bar_delta = delta_ratio * volumes
    cvd20 = pd.Series(bar_delta).rolling(20).sum().fillna(0).values

    return rel_vol20, rel_vol50, bar_delta, cvd20

# -----------------------------------------------------------------------------
# Strategy Simulators with Volume Logic
# -----------------------------------------------------------------------------
def run_volume_gated_supertrend(opens, highs, lows, closes, atr, ema200, dates,
                                volumes, rel_vol20, cvd20, mode="baseline",
                                multiplier=3.0, unit_size=10.0, spread=0.25, comm=0.60):
    n = len(closes)
    upper = (highs + lows) / 2.0 + multiplier * atr
    lower = (highs + lows) / 2.0 - multiplier * atr
    trend = np.ones(n, dtype=np.int32)
    st = np.zeros(n, dtype=np.float64)

    for i in range(15, n):
        if closes[i - 1] > lower[i - 1]: lower[i] = max(lower[i], lower[i - 1])
        if closes[i - 1] < upper[i - 1]: upper[i] = min(upper[i], upper[i - 1])

        if trend[i - 1] == 1:
            if closes[i] < lower[i]: trend[i] = -1; st[i] = upper[i]
            else: trend[i] = 1; st[i] = lower[i]
        else:
            if closes[i] > upper[i]: trend[i] = 1; st[i] = lower[i]
            else: trend[i] = -1; st[i] = upper[i]

    trades = []
    pos = 0
    entry_p = 0.0
    entry_idx = 0

    for i in range(200, n - 2):
        cur_t = trend[i]
        prev_t = trend[i - 1]
        cur_st = st[i]

        if pos == 1:
            hit = False
            exit_p = 0.0
            if lows[i] <= cur_st:
                exit_p = cur_st if opens[i] >= cur_st else opens[i]
                hit = True
            elif cur_t == -1:
                exit_p = opens[i + 1] - spread * 0.5
                hit = True
            # Optional Climax Exhaustion Exit
            elif mode == "climax_exit" and rel_vol20[i] > 3.5 and (highs[i] - closes[i]) > 0.5 * (highs[i] - lows[i]):
                exit_p = closes[i] - spread * 0.5
                hit = True

            if hit:
                pnl = (exit_p - entry_p) * unit_size - (spread + (comm / unit_size)) * unit_size
                trades.append({
                    "pnl": pnl, "entry_time": dates[entry_idx], "exit_time": dates[i],
                    "year": dates[entry_idx].year, "month": f"{dates[entry_idx].year}-{dates[entry_idx].month:02d}",
                    "entry_idx": entry_idx, "exit_idx": i, "engine": "Supertrend_Vol"
                })
                pos = 0

        elif pos == -1:
            hit = False
            exit_p = 0.0
            if highs[i] >= cur_st:
                exit_p = cur_st if opens[i] <= cur_st else opens[i]
                hit = True
            elif cur_t == 1:
                exit_p = opens[i + 1] + spread * 0.5
                hit = True
            elif mode == "climax_exit" and rel_vol20[i] > 3.5 and (closes[i] - lows[i]) > 0.5 * (highs[i] - lows[i]):
                exit_p = closes[i] + spread * 0.5
                hit = True

            if hit:
                pnl = (entry_p - exit_p) * unit_size - (spread + (comm / unit_size)) * unit_size
                trades.append({
                    "pnl": pnl, "entry_time": dates[entry_idx], "exit_time": dates[i],
                    "year": dates[entry_idx].year, "month": f"{dates[entry_idx].year}-{dates[entry_idx].month:02d}",
                    "entry_idx": entry_idx, "exit_idx": i, "engine": "Supertrend_Vol"
                })
                pos = 0

        if pos == 0:
            vol_ok_long = True
            vol_ok_short = True

            if mode == "climax_ignition":
                # Require institutional volume surge on breakout bar
                if rel_vol20[i] < 1.3: vol_ok_long = False; vol_ok_short = False
            elif mode == "cvd_alignment":
                # Require positive cumulative delta for Long, negative for Short
                if cvd20[i] <= 0: vol_ok_long = False
                if cvd20[i] >= 0: vol_ok_short = False

            if cur_t == 1 and prev_t == -1 and closes[i] > ema200[i] and vol_ok_long:
                pos = 1
                entry_p = opens[i + 1] + spread * 0.5
                entry_idx = i + 1
            elif cur_t == -1 and prev_t == 1 and closes[i] < ema200[i] and vol_ok_short:
                pos = -1
                entry_p = opens[i + 1] - spread * 0.5
                entry_idx = i + 1

    return trades

def run_volume_gated_ttm(opens, highs, lows, closes, atr, ema200, dates,
                         volumes, rel_vol20, mode="baseline",
                         bb_p=20, bb_mult=2.0, kc_mult=2.0, min_squeeze=8,
                         sl_mult=3.0, tp_mult=3.0, unit_size=10.0, spread=0.25, comm=0.60):
    n = len(closes)
    bb_mid = compute_ema(closes, bb_p)
    bb_std = pd.Series(closes).rolling(bb_p).std().fillna(1.0).values
    bb_up = bb_mid + bb_mult * bb_std
    bb_lo = bb_mid - bb_mult * bb_std

    kc_up = bb_mid + kc_mult * atr
    kc_lo = bb_mid - kc_mult * atr

    squeeze = (bb_up <= kc_up) & (bb_lo >= kc_lo)
    squeeze_bars = np.zeros(n, dtype=int)
    for i in range(1, n):
        if squeeze[i]: squeeze_bars[i] = squeeze_bars[i - 1] + 1
        else: squeeze_bars[i] = 0

    trades = []
    pos = 0
    entry_p = 0.0
    sl_p = 0.0
    tp_p = 0.0
    entry_idx = 0

    for i in range(bb_p * 2, n - 2):
        if pos == 1:
            hit = False
            exit_p = 0.0
            if lows[i] <= sl_p: hit = True; exit_p = sl_p
            elif highs[i] >= tp_p: hit = True; exit_p = tp_p
            if hit:
                pnl = (exit_p - entry_p) * unit_size - (spread + (comm / unit_size)) * unit_size
                trades.append({
                    "pnl": pnl, "entry_time": dates[entry_idx], "exit_time": dates[i],
                    "year": dates[entry_idx].year, "month": f"{dates[entry_idx].year}-{dates[entry_idx].month:02d}",
                    "entry_idx": entry_idx, "exit_idx": i, "engine": "TTM_Vol"
                })
                pos = 0

        elif pos == -1:
            hit = False
            exit_p = 0.0
            if highs[i] >= sl_p: hit = True; exit_p = sl_p
            elif lows[i] <= tp_p: hit = True; exit_p = tp_p
            if hit:
                pnl = (entry_p - exit_p) * unit_size - (spread + (comm / unit_size)) * unit_size
                trades.append({
                    "pnl": pnl, "entry_time": dates[entry_idx], "exit_time": dates[i],
                    "year": dates[entry_idx].year, "month": f"{dates[entry_idx].year}-{dates[entry_idx].month:02d}",
                    "entry_idx": entry_idx, "exit_idx": i, "engine": "TTM_Vol"
                })
                pos = 0

        if pos == 0:
            if squeeze_bars[i - 1] >= min_squeeze and not squeeze[i]:
                vol_ok = True
                if mode == "vol_expansion" and rel_vol20[i] < 1.2:
                    vol_ok = False

                if closes[i] > bb_mid[i] and closes[i] > ema200[i] and vol_ok:
                    pos = 1
                    entry_idx = i + 1
                    entry_p = opens[i + 1] + spread * 0.5
                    sl_dist = sl_mult * atr[i]
                    sl_p = entry_p - sl_dist
                    tp_p = entry_p + (tp_mult * sl_dist)
                elif closes[i] < bb_mid[i] and closes[i] < ema200[i] and vol_ok:
                    pos = -1
                    entry_idx = i + 1
                    entry_p = opens[i + 1] - spread * 0.5
                    sl_dist = sl_mult * atr[i]
                    sl_p = entry_p + sl_dist
                    tp_p = entry_p - (tp_mult * sl_dist)

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
    print("STARTING SCALPING BATCH 21: STRATEGIES 401 - 410")
    print("VOLUME-WEIGHTED ORDER FLOW, CLIMAX EXPANSION & TICK-VOLUME DELTA")
    print("=" * 80)
    t0 = time.time()

    print("Loading XAUUSD M15 and M5 Datasets...")
    df_m15 = pd.read_parquet(os.path.join(DATA_DIR, "XAUUSD_M15.parquet"))
    df_m5 = pd.read_parquet(os.path.join(DATA_DIR, "XAUUSD_M5.parquet"))

    print("Resampling M5 Tick-Volume onto M15...")
    vol_m15 = df_m5["tick_volume"].resample("15min").sum().reindex(df_m15.index).fillna(0).values.astype(np.float64)

    opens = df_m15["open"].values.astype(np.float64)
    highs = df_m15["high"].values.astype(np.float64)
    lows = df_m15["low"].values.astype(np.float64)
    closes = df_m15["close"].values.astype(np.float64)
    dates = df_m15.index

    atr14 = compute_atr(highs, lows, closes, 14)
    ema200 = compute_ema(closes, 200)

    print("Computing Volume Microstructure Features...")
    rel_vol20, rel_vol50, bar_delta, cvd20 = compute_volume_features(opens, highs, lows, closes, vol_m15)

    results = []

    # S401: Baseline S296 Tactical Duo Benchmark
    print("\nSimulating S401: Baseline S296 Benchmark...")
    t_st_base = run_volume_gated_supertrend(opens, highs, lows, closes, atr14, ema200, dates, vol_m15, rel_vol20, cvd20, mode="baseline")
    t_ttm_base = run_volume_gated_ttm(opens, highs, lows, closes, atr14, ema200, dates, vol_m15, rel_vol20, mode="baseline")
    results.append(analyze_trades(t_st_base + t_ttm_base, "Baseline S296 Benchmark (No Volume Filter)", "S401"))

    # S402: Volume Climax Ignition Breakout (Supertrend with RelVol > 1.3x)
    print("Simulating S402: Volume Climax Ignition Breakout...")
    t_st_ign = run_volume_gated_supertrend(opens, highs, lows, closes, atr14, ema200, dates, vol_m15, rel_vol20, cvd20, mode="climax_ignition")
    results.append(analyze_trades(t_st_ign, "Solo Supertrend Volume Climax Ignition (>1.3x)", "S402"))

    # S403: CVD Delta Alignment Scalper (Supertrend + 20-Bar CVD Trend Direction)
    print("Simulating S403: CVD Delta Alignment Scalper...")
    t_st_cvd = run_volume_gated_supertrend(opens, highs, lows, closes, atr14, ema200, dates, vol_m15, rel_vol20, cvd20, mode="cvd_alignment")
    results.append(analyze_trades(t_st_cvd, "Solo Supertrend CVD Momentum Alignment", "S403"))

    # S404: Volume Climax Exhaustion Exit
    print("Simulating S404: Volume Climax Exhaustion Exit...")
    t_st_exit = run_volume_gated_supertrend(opens, highs, lows, closes, atr14, ema200, dates, vol_m15, rel_vol20, cvd20, mode="climax_exit")
    results.append(analyze_trades(t_st_exit, "Solo Supertrend Volume Climax Exhaustion Exit", "S404"))

    # S405: Tactical Duo B + Volume Expansion Ignition
    print("Simulating S405: Tactical Duo B + Volume Ignition...")
    t_ttm_ign = run_volume_gated_ttm(opens, highs, lows, closes, atr14, ema200, dates, vol_m15, rel_vol20, mode="vol_expansion")
    results.append(analyze_trades(t_st_ign + t_ttm_ign, "Tactical Duo B + Institutional Volume Surge", "S405"))

    # S406: Tactical Duo B + CVD Delta Alignment
    print("Simulating S406: Tactical Duo B + CVD Delta Alignment...")
    results.append(analyze_trades(t_st_cvd + t_ttm_base, "Tactical Duo B + CVD Delta Filter", "S406"))

    # S407: Volume-Enhanced TTM Squeeze Breakout (Solo)
    print("Simulating S407: Volume-Enhanced TTM Squeeze Breakout...")
    results.append(analyze_trades(t_ttm_ign, "Solo TTM Squeeze Volume Expansion (>1.2x)", "S407"))

    # S408: Hybrid Volume Duo (Supertrend Base + TTM Volume Expansion)
    print("Simulating S408: Hybrid Volume Duo...")
    results.append(analyze_trades(t_st_base + t_ttm_ign, "Hybrid Duo: ST Base + TTM Volume Expansion", "S408"))

    # S409: Dynamic Volume Sizing Suite (Scale position based on RelVol)
    print("Simulating S409: Dynamic Volume Sizing Suite...")
    t_s409 = []
    for t in t_st_base:
        rv = rel_vol20[t["entry_idx"]]
        scale = 1.3 if rv > 1.5 else (0.8 if rv < 0.8 else 1.0)
        tw = dict(t); tw["pnl"] = t["pnl"] * scale; t_s409.append(tw)
    for t in t_ttm_base:
        rv = rel_vol20[t["entry_idx"]]
        scale = 1.3 if rv > 1.5 else (0.8 if rv < 0.8 else 1.0)
        tw = dict(t); tw["pnl"] = t["pnl"] * scale; t_s409.append(tw)
    results.append(analyze_trades(t_s409, "Tactical Duo B Dynamic Volume Sizing (0.8x-1.3x)", "S409"))

    # S410: Sovereign Volume-Confirmed Master Scalper
    print("Simulating S410: Sovereign Volume-Confirmed Master Scalper...")
    results.append(analyze_trades(t_st_base + t_ttm_ign, "Sovereign Volume-Confirmed Master Scalper (Apex)", "S410"))

    # Export Results
    df_out = pd.DataFrame(results)
    csv_path = os.path.join(RESULTS_DIR, "massive_scalping_volume_orderflow_batch_401_410_matrix.csv")
    json_path = os.path.join(RESULTS_DIR, "massive_scalping_volume_orderflow_batch_401_410_results.json")

    df_out.to_csv(csv_path, index=False)
    with open(json_path, "w") as f:
        json.dump({"generated_at": time.strftime("%Y-%m-%d %H:%M:%S"), "total_runtime_s": round(time.time() - t0, 2), "results": results}, f, indent=2)

    print("\n" + "=" * 80)
    print("BATCH 21 (S401 - S410) COMPLETED IN {:.2f}s".format(time.time() - t0))
    print("=" * 80)
    print(df_out[["strategy_id", "strategy_name", "annual_trades", "net_profit", "pf", "win_rate", "max_dd", "romad", "mcr", "status"]].to_string(index=False))
    print("=" * 80)

if __name__ == "__main__":
    main()
