#!/usr/bin/env python3
"""
===============================================================================
SCALPING FRONTIER BATCH 19: STRATEGIES 381 - 390
EXECUTION LATENCY, LIMIT-ORDER FILLS & REALISTIC SLIPPAGE STRESS MATRIX
===============================================================================
Objective:
Audit the impact of real-world order execution mechanics on Strategy 296 and 300:
1. Market Orders vs Limit-Order Pullback Entries (-0.2x, -0.4x, -0.6x ATR).
   - Quantify fill probability vs price improvement trade-off.
2. Latency Lag Shock: Simulating 1-bar execution delay (15-min terminal lag).
3. Random Asymmetric Slippage: Modeling real institutional fill slippage [0, $0.40/oz].
4. Hybrid Execution: Trend at Market vs Squeeze at Limit Retest.
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

# -----------------------------------------------------------------------------
# Fast Technical Indicator Helpers
# -----------------------------------------------------------------------------
def compute_atr(highs: np.ndarray, lows: np.ndarray, closes: np.ndarray, period: int = 14) -> np.ndarray:
    n = len(closes)
    atr = np.zeros(n, dtype=np.float64)
    tr = np.zeros(n, dtype=np.float64)
    tr[0] = highs[0] - lows[0]
    for i in range(1, n):
        hl = highs[i] - lows[i]
        hc = abs(highs[i] - closes[i - 1])
        lc = abs(lows[i] - closes[i - 1])
        tr[i] = max(hl, max(hc, lc))
    atr[period - 1] = np.mean(tr[:period])
    alpha = 1.0 / period
    for i in range(period, n):
        atr[i] = (tr[i] * alpha) + (atr[i - 1] * (1.0 - alpha))
    return atr

def compute_ema(series: np.ndarray, period: int) -> np.ndarray:
    n = len(series)
    ema = np.zeros(n, dtype=np.float64)
    ema[0] = series[0]
    alpha = 2.0 / (period + 1.0)
    for i in range(1, n):
        ema[i] = (series[i] * alpha) + (ema[i - 1] * (1.0 - alpha))
    return ema

# -----------------------------------------------------------------------------
# Engine 03: Supertrend with Flexible Execution Mechanics
# -----------------------------------------------------------------------------
def run_supertrend_exec(opens, highs, lows, closes, atr, ema200, dates,
                        exec_mode="market", limit_pullback_atr=0.0,
                        latency_bars=0, slippage_drag=0.0, random_slip=False,
                        multiplier=3.0, unit_size=10.0, spread=0.25, comm=0.60,
                        seed=42):
    np.random.seed(seed)
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

    # Pending Limit Order Tracking
    pending_pos = 0
    pending_limit_p = 0.0
    pending_placed_idx = 0

    for i in range(200, n - 2):
        cur_t = trend[i]
        prev_t = trend[i - 1]
        cur_st = st[i]

        # 1. Manage Active Position
        if pos == 1:
            hit = False
            exit_p = 0.0
            if lows[i] <= cur_st:
                exit_p = cur_st if opens[i] >= cur_st else opens[i]
                hit = True
            elif cur_t == -1:
                exit_p = opens[i + 1] - spread * 0.5
                hit = True
            if hit:
                # Apply slippage on exit
                exit_slip = np.random.uniform(0.0, 0.40) if random_slip else slippage_drag
                exit_p -= exit_slip
                pnl = (exit_p - entry_p) * unit_size - (spread + (comm / unit_size)) * unit_size
                trades.append({
                    "pnl": pnl, "entry_time": dates[entry_idx], "exit_time": dates[i],
                    "year": dates[entry_idx].year, "month": f"{dates[entry_idx].year}-{dates[entry_idx].month:02d}",
                    "entry_idx": entry_idx, "exit_idx": i, "engine": "Supertrend"
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
            if hit:
                exit_slip = np.random.uniform(0.0, 0.40) if random_slip else slippage_drag
                exit_p += exit_slip
                pnl = (entry_p - exit_p) * unit_size - (spread + (comm / unit_size)) * unit_size
                trades.append({
                    "pnl": pnl, "entry_time": dates[entry_idx], "exit_time": dates[i],
                    "year": dates[entry_idx].year, "month": f"{dates[entry_idx].year}-{dates[entry_idx].month:02d}",
                    "entry_idx": entry_idx, "exit_idx": i, "engine": "Supertrend"
                })
                pos = 0

        # 2. Check Pending Limit Order Fill
        if pos == 0 and pending_pos != 0:
            if i == pending_placed_idx:
                # Same bar as order placement: check if bar price penetrated limit
                if pending_pos == 1 and lows[i] <= pending_limit_p:
                    pos = 1
                    entry_p = pending_limit_p + spread * 0.5
                    entry_idx = i
                    pending_pos = 0
                elif pending_pos == -1 and highs[i] >= pending_limit_p:
                    pos = -1
                    entry_p = pending_limit_p - spread * 0.5
                    entry_idx = i
                    pending_pos = 0
                else:
                    # Unfilled: order expires after 1 bar
                    pending_pos = 0
            else:
                pending_pos = 0

        # 3. New Entry Triggers
        if pos == 0 and pending_pos == 0:
            if cur_t == 1 and prev_t == -1 and closes[i] > ema200[i]:
                target_idx = i + 1 + latency_bars
                if target_idx < n:
                    if exec_mode == "market":
                        entry_slip = np.random.uniform(0.0, 0.40) if random_slip else slippage_drag
                        pos = 1
                        entry_p = opens[target_idx] + spread * 0.5 + entry_slip
                        entry_idx = target_idx
                    elif exec_mode == "limit":
                        pending_pos = 1
                        pending_limit_p = opens[i + 1] - (limit_pullback_atr * atr[i])
                        pending_placed_idx = i + 1

            elif cur_t == -1 and prev_t == 1 and closes[i] < ema200[i]:
                target_idx = i + 1 + latency_bars
                if target_idx < n:
                    if exec_mode == "market":
                        entry_slip = np.random.uniform(0.0, 0.40) if random_slip else slippage_drag
                        pos = -1
                        entry_p = opens[target_idx] - spread * 0.5 - entry_slip
                        entry_idx = target_idx
                    elif exec_mode == "limit":
                        pending_pos = -1
                        pending_limit_p = opens[i + 1] + (limit_pullback_atr * atr[i])
                        pending_placed_idx = i + 1

    return trades

# -----------------------------------------------------------------------------
# Engine 04: TTM Squeeze with Flexible Execution Mechanics
# -----------------------------------------------------------------------------
def run_ttm_squeeze_exec(opens, highs, lows, closes, atr, ema200, dates,
                         exec_mode="market", limit_pullback_atr=0.0,
                         latency_bars=0, slippage_drag=0.0, random_slip=False,
                         bb_p=20, bb_mult=2.0, kc_mult=2.0, min_squeeze=8,
                         sl_mult=3.0, tp_mult=3.0, unit_size=10.0, spread=0.25, comm=0.60,
                         seed=43):
    np.random.seed(seed)
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

    pending_pos = 0
    pending_limit_p = 0.0
    pending_placed_idx = 0
    pending_atr = 0.0

    for i in range(bb_p * 2, n - 2):
        if pos == 1:
            hit = False
            exit_p = 0.0
            if lows[i] <= sl_p: hit = True; exit_p = sl_p
            elif highs[i] >= tp_p: hit = True; exit_p = tp_p
            if hit:
                exit_slip = np.random.uniform(0.0, 0.40) if random_slip else slippage_drag
                exit_p -= exit_slip
                pnl = (exit_p - entry_p) * unit_size - (spread + (comm / unit_size)) * unit_size
                trades.append({
                    "pnl": pnl, "entry_time": dates[entry_idx], "exit_time": dates[i],
                    "year": dates[entry_idx].year, "month": f"{dates[entry_idx].year}-{dates[entry_idx].month:02d}",
                    "entry_idx": entry_idx, "exit_idx": i, "engine": "TTM_Squeeze"
                })
                pos = 0

        elif pos == -1:
            hit = False
            exit_p = 0.0
            if highs[i] >= sl_p: hit = True; exit_p = sl_p
            elif lows[i] <= tp_p: hit = True; exit_p = tp_p
            if hit:
                exit_slip = np.random.uniform(0.0, 0.40) if random_slip else slippage_drag
                exit_p += exit_slip
                pnl = (entry_p - exit_p) * unit_size - (spread + (comm / unit_size)) * unit_size
                trades.append({
                    "pnl": pnl, "entry_time": dates[entry_idx], "exit_time": dates[i],
                    "year": dates[entry_idx].year, "month": f"{dates[entry_idx].year}-{dates[entry_idx].month:02d}",
                    "entry_idx": entry_idx, "exit_idx": i, "engine": "TTM_Squeeze"
                })
                pos = 0

        # Pending Limit Fill
        if pos == 0 and pending_pos != 0:
            if i == pending_placed_idx:
                if pending_pos == 1 and lows[i] <= pending_limit_p:
                    pos = 1
                    entry_p = pending_limit_p + spread * 0.5
                    entry_idx = i
                    sl_dist = sl_mult * pending_atr
                    sl_p = entry_p - sl_dist
                    tp_p = entry_p + (tp_mult * sl_dist)
                    pending_pos = 0
                elif pending_pos == -1 and highs[i] >= pending_limit_p:
                    pos = -1
                    entry_p = pending_limit_p - spread * 0.5
                    entry_idx = i
                    sl_dist = sl_mult * pending_atr
                    sl_p = entry_p + sl_dist
                    tp_p = entry_p - (tp_mult * sl_dist)
                    pending_pos = 0
                else:
                    pending_pos = 0
            else:
                pending_pos = 0

        if pos == 0 and pending_pos == 0:
            if squeeze_bars[i - 1] >= min_squeeze and not squeeze[i]:
                if closes[i] > bb_mid[i] and closes[i] > ema200[i]:
                    target_idx = i + 1 + latency_bars
                    if target_idx < n:
                        if exec_mode == "market":
                            entry_slip = np.random.uniform(0.0, 0.40) if random_slip else slippage_drag
                            pos = 1
                            entry_idx = target_idx
                            entry_p = opens[target_idx] + spread * 0.5 + entry_slip
                            sl_dist = sl_mult * atr[i]
                            sl_p = entry_p - sl_dist
                            tp_p = entry_p + (tp_mult * sl_dist)
                        elif exec_mode == "limit":
                            pending_pos = 1
                            pending_limit_p = opens[i + 1] - (limit_pullback_atr * atr[i])
                            pending_placed_idx = i + 1
                            pending_atr = atr[i]

                elif closes[i] < bb_mid[i] and closes[i] < ema200[i]:
                    target_idx = i + 1 + latency_bars
                    if target_idx < n:
                        if exec_mode == "market":
                            entry_slip = np.random.uniform(0.0, 0.40) if random_slip else slippage_drag
                            pos = -1
                            entry_idx = target_idx
                            entry_p = opens[target_idx] - spread * 0.5 - entry_slip
                            sl_dist = sl_mult * atr[i]
                            sl_p = entry_p + sl_dist
                            tp_p = entry_p - (tp_mult * sl_dist)
                        elif exec_mode == "limit":
                            pending_pos = -1
                            pending_limit_p = opens[i + 1] + (limit_pullback_atr * atr[i])
                            pending_placed_idx = i + 1
                            pending_atr = atr[i]

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
    print("STARTING SCALPING BATCH 19: STRATEGIES 381 - 390")
    print("EXECUTION LATENCY, LIMIT-ORDER FILLS & REALISTIC SLIPPAGE MATRIX")
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

    results = []

    # S381: Baseline S296 Tactical Duo (Market Order at Next Bar Open)
    print("\nSimulating S381: Baseline S296 Market Order Benchmark...")
    t_st_base = run_supertrend_exec(opens, highs, lows, closes, atr14, ema200, dates, exec_mode="market")
    t_ttm_base = run_ttm_squeeze_exec(opens, highs, lows, closes, atr14, ema200, dates, exec_mode="market")
    results.append(analyze_trades(t_st_base + t_ttm_base, "Baseline S296 Market Order Benchmark", "S381"))

    # S382: S296 Shallow Limit-Order Pullback (-0.2x ATR Pullback Limit)
    print("Simulating S382: S296 Shallow Limit-Order Pullback (-0.2x ATR)...")
    t_st_lim2 = run_supertrend_exec(opens, highs, lows, closes, atr14, ema200, dates, exec_mode="limit", limit_pullback_atr=0.2)
    t_ttm_lim2 = run_ttm_squeeze_exec(opens, highs, lows, closes, atr14, ema200, dates, exec_mode="limit", limit_pullback_atr=0.2)
    results.append(analyze_trades(t_st_lim2 + t_ttm_lim2, "S296 Shallow Limit Pullback (-0.2x ATR)", "S382"))

    # S383: S296 Moderate Limit-Order Pullback (-0.4x ATR Pullback Limit)
    print("Simulating S383: S296 Moderate Limit-Order Pullback (-0.4x ATR)...")
    t_st_lim4 = run_supertrend_exec(opens, highs, lows, closes, atr14, ema200, dates, exec_mode="limit", limit_pullback_atr=0.4)
    t_ttm_lim4 = run_ttm_squeeze_exec(opens, highs, lows, closes, atr14, ema200, dates, exec_mode="limit", limit_pullback_atr=0.4)
    results.append(analyze_trades(t_st_lim4 + t_ttm_lim4, "S296 Moderate Limit Pullback (-0.4x ATR)", "S383"))

    # S384: S296 Deep Limit-Order Pullback (-0.6x ATR Pullback Limit)
    print("Simulating S384: S296 Deep Limit-Order Pullback (-0.6x ATR)...")
    t_st_lim6 = run_supertrend_exec(opens, highs, lows, closes, atr14, ema200, dates, exec_mode="limit", limit_pullback_atr=0.6)
    t_ttm_lim6 = run_ttm_squeeze_exec(opens, highs, lows, closes, atr14, ema200, dates, exec_mode="limit", limit_pullback_atr=0.6)
    results.append(analyze_trades(t_st_lim6 + t_ttm_lim6, "S296 Deep Limit Pullback (-0.6x ATR)", "S384"))

    # S385: S296 Execution Latency Lag Shock (1-Bar Delay / 15-Minute Latency Shock)
    print("Simulating S385: S296 Execution Latency Lag Shock (1-Bar Delay)...")
    t_st_lat = run_supertrend_exec(opens, highs, lows, closes, atr14, ema200, dates, exec_mode="market", latency_bars=1)
    t_ttm_lat = run_ttm_squeeze_exec(opens, highs, lows, closes, atr14, ema200, dates, exec_mode="market", latency_bars=1)
    results.append(analyze_trades(t_st_lat + t_ttm_lat, "S296 Latency Lag Shock (1-Bar Delay)", "S385"))

    # S386: S296 Random Asymmetric Slippage Shock ([0, $0.40/oz] Uniform Random Drag)
    print("Simulating S386: S296 Random Asymmetric Slippage Shock...")
    t_st_slip = run_supertrend_exec(opens, highs, lows, closes, atr14, ema200, dates, exec_mode="market", random_slip=True)
    t_ttm_slip = run_ttm_squeeze_exec(opens, highs, lows, closes, atr14, ema200, dates, exec_mode="market", random_slip=True)
    results.append(analyze_trades(t_st_slip + t_ttm_slip, "S296 Random Asymmetric Slippage Shock [0, 40c]", "S386"))

    # S387: S300 Master Quartet with Shallow Limit Orders (-0.2x ATR)
    print("Simulating S387: S300 Master Quartet with Shallow Limit Orders...")
    from simulate_scalping_master_ensemble_batch_291_300 import run_engine_zl_macd, run_engine_fvg_retest
    months = np.array([f"{d.year}-{d.month:02d}" for d in dates])
    t_macd = run_engine_zl_macd(opens, highs, lows, closes, atr14, months)
    t_fvg = run_engine_fvg_retest(opens, highs, lows, closes, atr14, ema200, months)
    for t in t_macd: t["entry_time"] = dates[t["entry_idx"]]
    for t in t_fvg: t["entry_time"] = dates[t["entry_idx"]]

    t_s300_lim = []
    for t in t_st_lim2: tw = dict(t); tw["pnl"] = t["pnl"] * 1.0; t_s300_lim.append(tw)
    for t in t_macd: tw = dict(t); tw["pnl"] = t["pnl"] * 0.7; t_s300_lim.append(tw)
    for t in t_ttm_lim2: tw = dict(t); tw["pnl"] = t["pnl"] * 0.8; t_s300_lim.append(tw)
    for t in t_fvg: tw = dict(t); tw["pnl"] = t["pnl"] * 0.5; t_s300_lim.append(tw)
    results.append(analyze_trades(t_s300_lim, "S300 Master Quartet Shallow Limit Orders (-0.2x)", "S387"))

    # S388: S300 Master Quartet with Severe Adverse Slippage Shock ($0.20/oz Drag)
    print("Simulating S388: S300 Master Quartet Adverse Slippage Shock...")
    t_s300_slip = []
    for t in t_st_slip: tw = dict(t); tw["pnl"] = t["pnl"] * 1.0; t_s300_slip.append(tw)
    for t in t_macd: tw = dict(t); tw["pnl"] = (t["pnl"] - 0.20 * 10.0) * 0.7; t_s300_slip.append(tw)
    for t in t_ttm_slip: tw = dict(t); tw["pnl"] = t["pnl"] * 0.8; t_s300_slip.append(tw)
    for t in t_fvg: tw = dict(t); tw["pnl"] = (t["pnl"] - 0.20 * 10.0) * 0.5; t_s300_slip.append(tw)
    results.append(analyze_trades(t_s300_slip, "S300 Master Quartet Slippage Shock ($0.20/oz)", "S388"))

    # S389: Hybrid Execution (Supertrend Market + TTM Squeeze Limit Retest)
    print("Simulating S389: Hybrid Execution (Supertrend Market + TTM Limit)...")
    results.append(analyze_trades(t_st_base + t_ttm_lim2, "Hybrid Execution: ST Market + TTM Limit (-0.2x)", "S389"))

    # S390: Sovereign Production Execution Standard
    print("Simulating S390: Sovereign Production Execution Standard...")
    # Production EA uses Market on next bar open + 2-bar timeout
    results.append(analyze_trades(t_st_base + t_ttm_base, "Sovereign Production Execution Standard (S296 Market)", "S390"))

    # Export Results
    df_out = pd.DataFrame(results)
    csv_path = os.path.join(RESULTS_DIR, "massive_scalping_execution_latency_batch_381_390_matrix.csv")
    json_path = os.path.join(RESULTS_DIR, "massive_scalping_execution_latency_batch_381_390_results.json")

    df_out.to_csv(csv_path, index=False)
    with open(json_path, "w") as f:
        json.dump({"generated_at": time.strftime("%Y-%m-%d %H:%M:%S"), "total_runtime_s": round(time.time() - t0, 2), "results": results}, f, indent=2)

    print("\n" + "=" * 80)
    print("BATCH 19 (S381 - S390) COMPLETED IN {:.2f}s".format(time.time() - t0))
    print("=" * 80)
    print(df_out[["strategy_id", "strategy_name", "annual_trades", "net_profit", "pf", "win_rate", "max_dd", "romad", "mcr", "status"]].to_string(index=False))
    print("=" * 80)

if __name__ == "__main__":
    main()
