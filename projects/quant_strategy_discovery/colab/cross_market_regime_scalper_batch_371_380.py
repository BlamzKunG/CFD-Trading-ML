#!/usr/bin/env python3
"""
===============================================================================
SCALPING FRONTIER BATCH 18: STRATEGIES 371 - 380
CROSS-MARKET MACRO REGIME GATING & DUAL-ASSET PORTFOLIO SYNERGY
(XAUUSD SCALPER + EURUSD MACRO SHIELD & DUAL-ASSET ENGINE)
===============================================================================
Objective:
Evaluate whether cross-market signals from EURUSD (Dollar Index proxy) can:
1. Shield Gold scalping from violent USD macroeconomic shocks (NFP, CPI, FOMC).
2. Cleanse false counter-trend breakouts via Macro USD Trend Alignment.
3. Diversify portfolio drawdown via Asynchronous Multi-Asset Risk Allocation.
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
# Fast Technical Calculations
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
# Core Gold Scalper Engines with Optional EURUSD Cross-Market Gating
# -----------------------------------------------------------------------------
def run_gated_supertrend(opens, highs, lows, closes, atr, ema200, dates,
                         eur_closes, eur_atr, eur_ema200, eur_ema50,
                         mode="baseline", multiplier=3.0, unit_size=10.0,
                         spread=0.25, comm=0.60):
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

    # Precompute Shock Freeze Bars (EURUSD range > 2.5x ATR)
    eur_shock_freeze = np.zeros(n, dtype=bool)
    if "shock_shield" in mode:
        freeze_until = 0
        for i in range(15, n):
            eur_bar_range = abs(eur_closes[i] - eur_closes[i - 1])
            if eur_bar_range > 2.5 * eur_atr[i]:
                freeze_until = i + 8  # freeze next 8 bars (2 hours)
            if i < freeze_until:
                eur_shock_freeze[i] = True

    trades = []
    pos = 0
    entry_p = 0.0
    entry_idx = 0

    for i in range(200, n - 1):
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
            if hit:
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
                pnl = (entry_p - exit_p) * unit_size - (spread + (comm / unit_size)) * unit_size
                trades.append({
                    "pnl": pnl, "entry_time": dates[entry_idx], "exit_time": dates[i],
                    "year": dates[entry_idx].year, "month": f"{dates[entry_idx].year}-{dates[entry_idx].month:02d}",
                    "entry_idx": entry_idx, "exit_idx": i, "engine": "Supertrend"
                })
                pos = 0

        if pos == 0:
            long_ok = True
            short_ok = True

            # EURUSD Gating
            if "shock_shield" in mode and eur_shock_freeze[i]:
                long_ok = False
                short_ok = False

            if "strict_trend" in mode:
                # Weak USD required for Gold Long, Strong USD for Gold Short
                if eur_closes[i] < eur_ema200[i]: long_ok = False
                if eur_closes[i] > eur_ema200[i]: short_ok = False

            if "permissive_trend" in mode:
                # Avoid Long Gold only if EUR is in severe downtrend
                if eur_closes[i] < eur_ema50[i] and eur_closes[i] < eur_ema200[i]: long_ok = False
                # Avoid Short Gold only if EUR is in severe uptrend
                if eur_closes[i] > eur_ema50[i] and eur_closes[i] > eur_ema200[i]: short_ok = False

            if cur_t == 1 and prev_t == -1 and closes[i] > ema200[i] and long_ok:
                pos = 1
                entry_p = opens[i + 1] + spread * 0.5
                entry_idx = i + 1
            elif cur_t == -1 and prev_t == 1 and closes[i] < ema200[i] and short_ok:
                pos = -1
                entry_p = opens[i + 1] - spread * 0.5
                entry_idx = i + 1

    return trades

def run_gated_ttm_squeeze(opens, highs, lows, closes, atr, ema200, dates,
                          eur_closes, eur_atr, eur_ema200, eur_ema50,
                          mode="baseline", bb_p=20, bb_mult=2.0, kc_mult=2.0, min_squeeze=8,
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

    eur_shock_freeze = np.zeros(n, dtype=bool)
    if "shock_shield" in mode:
        freeze_until = 0
        for i in range(15, n):
            eur_bar_range = abs(eur_closes[i] - eur_closes[i - 1])
            if eur_bar_range > 2.5 * eur_atr[i]:
                freeze_until = i + 8
            if i < freeze_until:
                eur_shock_freeze[i] = True

    trades = []
    pos = 0
    entry_p = 0.0
    sl_p = 0.0
    tp_p = 0.0
    entry_idx = 0

    for i in range(bb_p * 2, n - 1):
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
                    "entry_idx": entry_idx, "exit_idx": i, "engine": "TTM_Squeeze"
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
                    "entry_idx": entry_idx, "exit_idx": i, "engine": "TTM_Squeeze"
                })
                pos = 0

        if pos == 0:
            if squeeze_bars[i - 1] >= min_squeeze and not squeeze[i]:
                long_ok = True
                short_ok = True

                if "shock_shield" in mode and eur_shock_freeze[i]:
                    long_ok = False; short_ok = False
                if "strict_trend" in mode:
                    if eur_closes[i] < eur_ema200[i]: long_ok = False
                    if eur_closes[i] > eur_ema200[i]: short_ok = False
                if "permissive_trend" in mode:
                    if eur_closes[i] < eur_ema50[i] and eur_closes[i] < eur_ema200[i]: long_ok = False
                    if eur_closes[i] > eur_ema50[i] and eur_closes[i] > eur_ema200[i]: short_ok = False

                if closes[i] > bb_mid[i] and closes[i] > ema200[i] and long_ok:
                    pos = 1
                    entry_idx = i + 1
                    entry_p = opens[i + 1] + spread * 0.5
                    sl_dist = sl_mult * atr[i]
                    sl_p = entry_p - sl_dist
                    tp_p = entry_p + (tp_mult * sl_dist)
                elif closes[i] < bb_mid[i] and closes[i] < ema200[i] and short_ok:
                    pos = -1
                    entry_idx = i + 1
                    entry_p = opens[i + 1] - spread * 0.5
                    sl_dist = sl_mult * atr[i]
                    sl_p = entry_p + sl_dist
                    tp_p = entry_p - (tp_mult * sl_dist)

    return trades

# -----------------------------------------------------------------------------
# EURUSD H1 Macro Trend Following Engine (0.20 Standard Lot = $20/pip)
# -----------------------------------------------------------------------------
def run_eurusd_macro_h1(df_eur_h1, lot_size=0.20, spread=0.00015, comm=6.0):
    c = df_eur_h1["close"].values.astype(np.float64)
    h = df_eur_h1["high"].values.astype(np.float64)
    l = df_eur_h1["low"].values.astype(np.float64)
    o = df_eur_h1["open"].values.astype(np.float64)
    dates = df_eur_h1.index
    n = len(c)

    atr = compute_atr(h, l, c, 14)
    ema50 = compute_ema(c, 50)
    ema200 = compute_ema(c, 200)

    trades = []
    pos = 0
    entry_p = 0.0
    sl_p = 0.0
    tp_p = 0.0
    entry_idx = 0

    # 0.20 lot EURUSD = $200,000 unit -> 1 pip (0.0001) = $20.00
    point_val = 100000.0 * lot_size

    for i in range(200, n - 1):
        if pos == 1:
            hit = False
            exit_p = 0.0
            if l[i] <= sl_p: hit = True; exit_p = sl_p
            elif h[i] >= tp_p: hit = True; exit_p = tp_p
            elif c[i] < ema50[i]: hit = True; exit_p = o[i + 1] - spread * 0.5
            if hit:
                pnl = (exit_p - entry_p) * point_val - (spread * point_val + comm * lot_size)
                trades.append({
                    "pnl": pnl, "entry_time": dates[entry_idx], "exit_time": dates[i],
                    "year": dates[entry_idx].year, "month": f"{dates[entry_idx].year}-{dates[entry_idx].month:02d}",
                    "entry_idx": entry_idx, "exit_idx": i, "engine": "EURUSD_H1_Macro"
                })
                pos = 0

        elif pos == -1:
            hit = False
            exit_p = 0.0
            if h[i] >= sl_p: hit = True; exit_p = sl_p
            elif l[i] <= tp_p: hit = True; exit_p = tp_p
            elif c[i] > ema50[i]: hit = True; exit_p = o[i + 1] + spread * 0.5
            if hit:
                pnl = (entry_p - exit_p) * point_val - (spread * point_val + comm * lot_size)
                trades.append({
                    "pnl": pnl, "entry_time": dates[entry_idx], "exit_time": dates[i],
                    "year": dates[entry_idx].year, "month": f"{dates[entry_idx].year}-{dates[entry_idx].month:02d}",
                    "entry_idx": entry_idx, "exit_idx": i, "engine": "EURUSD_H1_Macro"
                })
                pos = 0

        if pos == 0:
            if c[i] > ema50[i] and ema50[i] > ema200[i] and c[i - 1] <= ema50[i - 1]:
                pos = 1
                entry_idx = i + 1
                entry_p = o[i + 1] + spread * 0.5
                sl_dist = 2.0 * atr[i]
                sl_p = entry_p - sl_dist
                tp_p = entry_p + 3.5 * sl_dist
            elif c[i] < ema50[i] and ema50[i] < ema200[i] and c[i - 1] >= ema50[i - 1]:
                pos = -1
                entry_idx = i + 1
                entry_p = o[i + 1] - spread * 0.5
                sl_dist = 2.0 * atr[i]
                sl_p = entry_p + sl_dist
                tp_p = entry_p - 3.5 * sl_dist

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
    print("STARTING SCALPING BATCH 18: STRATEGIES 371 - 380")
    print("CROSS-MARKET MACRO REGIME GATING & DUAL-ASSET PORTFOLIO SYNERGY")
    print("=" * 80)
    t0 = time.time()

    print("Loading Datasets...")
    df_gold = pd.read_parquet(os.path.join(DATA_DIR, "XAUUSD_M15.parquet"))
    df_eur = pd.read_parquet(os.path.join(DATA_DIR, "EURUSD_M15.parquet"))
    df_eur_h1 = pd.read_parquet(os.path.join(DATA_DIR, "EURUSD_H1.parquet"))

    # Align EURUSD M15 features onto Gold M15
    df_merged = df_gold.join(
        df_eur[["close", "high", "low"]].rename(columns={"close": "eur_close", "high": "eur_high", "low": "eur_low"}),
        how="left"
    ).ffill().bfill()

    g_opens = df_merged["open"].values.astype(np.float64)
    g_highs = df_merged["high"].values.astype(np.float64)
    g_lows = df_merged["low"].values.astype(np.float64)
    g_closes = df_merged["close"].values.astype(np.float64)
    dates = df_merged.index

    eur_closes = df_merged["eur_close"].values.astype(np.float64)
    eur_highs = df_merged["eur_high"].values.astype(np.float64)
    eur_lows = df_merged["eur_low"].values.astype(np.float64)

    print("Computing technical features...")
    g_atr14 = compute_atr(g_highs, g_lows, g_closes, 14)
    g_ema200 = compute_ema(g_closes, 200)

    eur_atr14 = compute_atr(eur_highs, eur_lows, eur_closes, 14)
    eur_ema50 = compute_ema(eur_closes, 50)
    eur_ema200 = compute_ema(eur_closes, 200)

    print("\nRunning EURUSD H1 Macro Engine...")
    t_eur_h1 = run_eurusd_macro_h1(df_eur_h1)
    print(f"-> EURUSD H1 Macro Engine: {len(t_eur_h1)} trades ({len(t_eur_h1)/6.0:.1f} tr/yr)")

    results = []

    # S371: Baseline S296 Tactical Duo Benchmark
    print("\nSimulating S371: Baseline S296 Tactical Duo Benchmark...")
    t_st_base = run_gated_supertrend(g_opens, g_highs, g_lows, g_closes, g_atr14, g_ema200, dates, eur_closes, eur_atr14, eur_ema200, eur_ema50, mode="baseline")
    t_ttm_base = run_gated_ttm_squeeze(g_opens, g_highs, g_lows, g_closes, g_atr14, g_ema200, dates, eur_closes, eur_atr14, eur_ema200, eur_ema50, mode="baseline")
    results.append(analyze_trades(t_st_base + t_ttm_base, "Baseline S296 Tactical Duo Benchmark", "S371"))

    # S372: S296 + EURUSD Strict Macro Trend Alignment (Weak/Strong USD Gating)
    print("Simulating S372: S296 + EURUSD Strict Macro Trend Alignment...")
    t_st_strict = run_gated_supertrend(g_opens, g_highs, g_lows, g_closes, g_atr14, g_ema200, dates, eur_closes, eur_atr14, eur_ema200, eur_ema50, mode="strict_trend")
    t_ttm_strict = run_gated_ttm_squeeze(g_opens, g_highs, g_lows, g_closes, g_atr14, g_ema200, dates, eur_closes, eur_atr14, eur_ema200, eur_ema50, mode="strict_trend")
    results.append(analyze_trades(t_st_strict + t_ttm_strict, "S296 + EURUSD Strict Macro Trend Alignment", "S372"))

    # S373: S296 + EURUSD Permissive Macro Trend Filter
    print("Simulating S373: S296 + EURUSD Permissive Macro Trend Filter...")
    t_st_perm = run_gated_supertrend(g_opens, g_highs, g_lows, g_closes, g_atr14, g_ema200, dates, eur_closes, eur_atr14, eur_ema200, eur_ema50, mode="permissive_trend")
    t_ttm_perm = run_gated_ttm_squeeze(g_opens, g_highs, g_lows, g_closes, g_atr14, g_ema200, dates, eur_closes, eur_atr14, eur_ema200, eur_ema50, mode="permissive_trend")
    results.append(analyze_trades(t_st_perm + t_ttm_perm, "S296 + EURUSD Permissive Macro Trend Filter", "S373"))

    # S374: S296 + EURUSD Volatility Shock Shield (2-Hour News Freeze)
    print("Simulating S374: S296 + EURUSD Volatility Shock Shield...")
    t_st_shock = run_gated_supertrend(g_opens, g_highs, g_lows, g_closes, g_atr14, g_ema200, dates, eur_closes, eur_atr14, eur_ema200, eur_ema50, mode="shock_shield")
    t_ttm_shock = run_gated_ttm_squeeze(g_opens, g_highs, g_lows, g_closes, g_atr14, g_ema200, dates, eur_closes, eur_atr14, eur_ema200, eur_ema50, mode="shock_shield")
    results.append(analyze_trades(t_st_shock + t_ttm_shock, "S296 + EURUSD Volatility Shock Shield (News Freeze)", "S374"))

    # S375: S296 + EURUSD Shock Shield + Permissive Trend Filter
    print("Simulating S375: S296 + EURUSD Shock Shield + Permissive Trend...")
    t_st_combo = run_gated_supertrend(g_opens, g_highs, g_lows, g_closes, g_atr14, g_ema200, dates, eur_closes, eur_atr14, eur_ema200, eur_ema50, mode="shock_shield_permissive_trend")
    t_ttm_combo = run_gated_ttm_squeeze(g_opens, g_highs, g_lows, g_closes, g_atr14, g_ema200, dates, eur_closes, eur_atr14, eur_ema200, eur_ema50, mode="shock_shield_permissive_trend")
    results.append(analyze_trades(t_st_combo + t_ttm_combo, "S296 + EURUSD Shock Shield & Permissive Trend", "S375"))

    # S376: S291 Solo Supertrend + EURUSD Shock Shield
    print("Simulating S376: S291 Solo Supertrend + EURUSD Shock Shield...")
    results.append(analyze_trades(t_st_shock, "S291 Solo Supertrend + EURUSD Shock Shield", "S376"))

    # S377: S300 Master Quartet + EURUSD Shock Shield
    print("Simulating S377: S300 Master Quartet + EURUSD Shock Shield...")
    from simulate_scalping_master_ensemble_batch_291_300 import run_engine_zl_macd, run_engine_fvg_retest
    months = np.array([f"{d.year}-{d.month:02d}" for d in dates])
    t_macd = run_engine_zl_macd(g_opens, g_highs, g_lows, g_closes, g_atr14, months)
    t_fvg = run_engine_fvg_retest(g_opens, g_highs, g_lows, g_closes, g_atr14, g_ema200, months)
    for t in t_macd: t["entry_time"] = dates[t["entry_idx"]]
    for t in t_fvg: t["entry_time"] = dates[t["entry_idx"]]

    t_s300_shock = []
    for t in t_st_shock: tw = dict(t); tw["pnl"] = t["pnl"] * 1.0; t_s300_shock.append(tw)
    for t in t_macd: tw = dict(t); tw["pnl"] = t["pnl"] * 0.7; t_s300_shock.append(tw)
    for t in t_ttm_shock: tw = dict(t); tw["pnl"] = t["pnl"] * 0.8; t_s300_shock.append(tw)
    for t in t_fvg: tw = dict(t); tw["pnl"] = t["pnl"] * 0.5; t_s300_shock.append(tw)
    results.append(analyze_trades(t_s300_shock, "S300 Master Quartet + EURUSD Shock Shield", "S377"))

    # S378: Asynchronous Dual-Asset Portfolio A (S296 Gold Scalper + EURUSD H1 Macro)
    print("Simulating S378: Asynchronous Dual-Asset Portfolio A (S296 + EUR H1)...")
    results.append(analyze_trades(t_st_base + t_ttm_base + t_eur_h1, "Dual-Asset Portfolio A: S296 Gold Scalper + EURUSD H1 Macro", "S378"))

    # S379: Asynchronous Dual-Asset Portfolio B (S300 Quartet + EURUSD H1 Macro)
    print("Simulating S379: Asynchronous Dual-Asset Portfolio B (S300 + EUR H1)...")
    results.append(analyze_trades(t_s300_shock + t_eur_h1, "Dual-Asset Portfolio B: S300 Quartet + EURUSD H1 Macro", "S379"))

    # S380: Sovereign Cross-Market Master Scalper Suite (Top Multi-Asset Synergy)
    print("Simulating S380: Sovereign Cross-Market Master Scalper Suite...")
    results.append(analyze_trades(t_st_shock + t_ttm_shock + t_eur_h1, "Sovereign Cross-Market Master Suite (S296 Shock + EUR H1)", "S380"))

    # Export Results
    df_out = pd.DataFrame(results)
    csv_path = os.path.join(RESULTS_DIR, "massive_scalping_cross_market_batch_371_380_matrix.csv")
    json_path = os.path.join(RESULTS_DIR, "massive_scalping_cross_market_batch_371_380_results.json")

    df_out.to_csv(csv_path, index=False)
    with open(json_path, "w") as f:
        json.dump({"generated_at": time.strftime("%Y-%m-%d %H:%M:%S"), "total_runtime_s": round(time.time() - t0, 2), "results": results}, f, indent=2)

    print("\n" + "=" * 80)
    print("BATCH 18 (S371 - S380) COMPLETED IN {:.2f}s".format(time.time() - t0))
    print("=" * 80)
    print(df_out[["strategy_id", "strategy_name", "annual_trades", "net_profit", "pf", "win_rate", "max_dd", "romad", "mcr", "status"]].to_string(index=False))
    print("=" * 80)

if __name__ == "__main__":
    main()
