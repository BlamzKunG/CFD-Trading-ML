#!/usr/bin/env python3
"""
===============================================================================
SCALPING FRONTIER BATCH 23: STRATEGIES 421 - 430
MULTI-TIMEFRAME DUAL-SPEED MOMENTUM & LONDON/NY SESSION VOLATILITY EXPANSION
===============================================================================
Asset: XAUUSD (Gold)
Multi-Timeframe Matrix: M15 Macro Regime + M5 Micro Trigger Execution
Period: 2020-01-01 to 2025-12-30 (6 Full Multi-Year Regimes)
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

# Path Resolution
if os.path.exists("XAUUSD_M15.parquet"):
    DATA_M15_PATH = "XAUUSD_M15.parquet"
    DATA_M5_PATH = "XAUUSD_M5.parquet" if os.path.exists("XAUUSD_M5.parquet") else "projects/quant_strategy_discovery/data/XAUUSD_M5.parquet"
    RESULTS_DIR = "results"
elif os.path.exists("/content/CFD-Trading-ML"):
    REPO_ROOT = "/content/CFD-Trading-ML"
    DATA_M15_PATH = os.path.join(REPO_ROOT, "projects/quant_strategy_discovery/data/XAUUSD_M15.parquet")
    DATA_M5_PATH = os.path.join(REPO_ROOT, "projects/quant_strategy_discovery/data/XAUUSD_M5.parquet")
    RESULTS_DIR = os.path.join(REPO_ROOT, "projects/quant_strategy_discovery/results")
else:
    REPO_ROOT = "/root/CFD-Trading-ML"
    DATA_M15_PATH = os.path.join(REPO_ROOT, "projects/quant_strategy_discovery/data/XAUUSD_M15.parquet")
    DATA_M5_PATH = os.path.join(REPO_ROOT, "projects/quant_strategy_discovery/data/XAUUSD_M5.parquet")
    RESULTS_DIR = os.path.join(REPO_ROOT, "projects/quant_strategy_discovery/results")

os.makedirs(RESULTS_DIR, exist_ok=True)

# -----------------------------------------------------------------------------
# Core Indicator Functions
# -----------------------------------------------------------------------------
def compute_atr(highs: np.ndarray, lows: np.ndarray, closes: np.ndarray, period: int = 14) -> np.ndarray:
    n = len(closes)
    tr = np.zeros(n, dtype=np.float64)
    tr[0] = highs[0] - lows[0]
    for i in range(1, n):
        hl = highs[i] - lows[i]
        hc = abs(highs[i] - closes[i - 1])
        lc = abs(lows[i] - closes[i - 1])
        tr[i] = max(hl, hc, lc)

    atr = np.zeros(n, dtype=np.float64)
    atr[period - 1] = np.mean(tr[:period])
    for i in range(period, n):
        atr[i] = (atr[i - 1] * (period - 1) + tr[i]) / period
    return atr

def compute_ema(series: np.ndarray, period: int) -> np.ndarray:
    n = len(series)
    ema = np.zeros(n, dtype=np.float64)
    alpha = 2.0 / (period + 1.0)
    ema[period - 1] = np.mean(series[:period])
    for i in range(period, n):
        ema[i] = alpha * series[i] + (1.0 - alpha) * ema[i - 1]
    return ema

def compute_supertrend(highs: np.ndarray, lows: np.ndarray, closes: np.ndarray, atr: np.ndarray, multiplier: float = 3.0):
    n = len(closes)
    upper = (highs + lows) / 2.0 + multiplier * atr
    lower = (highs + lows) / 2.0 - multiplier * atr
    trend = np.ones(n, dtype=np.int32)
    st = np.zeros(n, dtype=np.float64)

    for i in range(15, n):
        if closes[i - 1] > lower[i - 1]: lower[i] = max(lower[i], lower[i - 1])
        if closes[i - 1] < upper[i - 1]: upper[i] = min(upper[i], upper[i - 1])

        if trend[i - 1] == 1:
            if closes[i] < lower[i]:
                trend[i] = -1
                st[i] = upper[i]
            else:
                trend[i] = 1
                st[i] = lower[i]
        else:
            if closes[i] > upper[i]:
                trend[i] = 1
                st[i] = lower[i]
            else:
                trend[i] = -1
                st[i] = upper[i]
    return trend, st

# -----------------------------------------------------------------------------
# Microstructure CVD & Volume
# -----------------------------------------------------------------------------
def compute_cvd(highs: np.ndarray, lows: np.ndarray, closes: np.ndarray, volumes: np.ndarray, period: int = 20):
    rng = np.maximum(highs - lows, 1e-4)
    delta_ratio = ((closes - lows) - (highs - closes)) / rng
    bar_delta = delta_ratio * volumes
    cvd = pd.Series(bar_delta).rolling(period).sum().fillna(0).values
    return cvd

# -----------------------------------------------------------------------------
# Strategy Simulators
# -----------------------------------------------------------------------------
def run_supertrend_session_sim(opens, highs, lows, closes, atr, ema200, dates,
                               session_mode="all", multiplier=3.0, unit_size=10.0,
                               spread=0.25, comm=0.60):
    n = len(closes)
    trend, st = compute_supertrend(highs, lows, closes, atr, multiplier)
    trades = []
    pos = 0
    entry_p = 0.0
    entry_idx = 0

    for i in range(200, n - 2):
        cur_t = trend[i]
        prev_t = trend[i - 1]
        cur_st = st[i]
        hour = dates[i].hour

        # Check exits
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
                    "entry_idx": entry_idx, "exit_idx": i, "engine": "Supertrend_Session"
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
                    "entry_idx": entry_idx, "exit_idx": i, "engine": "Supertrend_Session"
                })
                pos = 0

        # Check entries
        if pos == 0:
            # Session filter logic
            session_ok = True
            if session_mode == "london":
                session_ok = (7 <= hour < 11)
            elif session_mode == "ny":
                session_ok = (12 <= hour < 17)
            elif session_mode == "dual_session":
                session_ok = (7 <= hour < 11) or (12 <= hour < 17)
            elif session_mode == "skip_rollover":
                session_ok = not (21 <= hour < 23)

            if session_ok:
                if cur_t == 1 and prev_t == -1 and closes[i] > ema200[i]:
                    pos = 1
                    entry_p = opens[i + 1] + spread * 0.5
                    entry_idx = i + 1
                elif cur_t == -1 and prev_t == 1 and closes[i] < ema200[i]:
                    pos = -1
                    entry_p = opens[i + 1] - spread * 0.5
                    entry_idx = i + 1

    return trades

def run_ttm_squeeze_session_sim(opens, highs, lows, closes, atr, ema200, dates,
                                session_mode="all", bb_p=20, bb_mult=2.0, kc_mult=2.0,
                                min_squeeze=8, sl_mult=3.0, tp_mult=3.0,
                                unit_size=10.0, spread=0.25, comm=0.60):
    n = len(closes)
    s_closes = pd.Series(closes)
    bb_mid = s_closes.rolling(bb_p).mean().values
    bb_std = s_closes.rolling(bb_p).std().fillna(0).values
    bb_up = bb_mid + bb_mult * bb_std
    bb_dn = bb_mid - bb_mult * bb_std
    kc_up = bb_mid + kc_mult * atr
    kc_dn = bb_mid - kc_mult * atr

    trades = []
    pos = 0
    entry_p = 0.0
    sl_p = 0.0
    tp_p = 0.0
    entry_idx = 0
    sqz_cnt = 0

    for i in range(200, n - 2):
        hour = dates[i].hour
        is_sqz = (bb_up[i] <= kc_up[i]) and (bb_dn[i] >= kc_dn[i])
        sqz_fired = False

        if is_sqz:
            sqz_cnt += 1
        else:
            if sqz_cnt >= min_squeeze:
                sqz_fired = True
            sqz_cnt = 0

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
            if highs[i] >= sl_p:
                exit_p = sl_p if opens[i] <= sl_p else opens[i]
                hit = True
            elif lows[i] <= tp_p:
                exit_p = tp_p if opens[i] >= tp_p else opens[i]
                hit = True

            if hit:
                pnl = (entry_p - exit_p) * unit_size - (spread + (comm / unit_size)) * unit_size
                trades.append({
                    "pnl": pnl, "entry_time": dates[entry_idx], "exit_time": dates[i],
                    "year": dates[entry_idx].year, "month": f"{dates[entry_idx].year}-{dates[entry_idx].month:02d}",
                    "entry_idx": entry_idx, "exit_idx": i, "engine": "TTM_Squeeze"
                })
                pos = 0

        # Check entries
        if pos == 0 and sqz_fired:
            session_ok = True
            if session_mode == "london":
                session_ok = (7 <= hour < 11)
            elif session_mode == "ny":
                session_ok = (12 <= hour < 17)
            elif session_mode == "dual_session":
                session_ok = (7 <= hour < 11) or (12 <= hour < 17)
            elif session_mode == "skip_rollover":
                session_ok = not (21 <= hour < 23)

            if session_ok:
                if closes[i] > bb_mid[i] and closes[i] > ema200[i]:
                    pos = 1
                    entry_p = opens[i + 1] + spread * 0.5
                    sl_dist = sl_mult * atr[i]
                    sl_p = entry_p - sl_dist
                    tp_p = entry_p + (tp_mult * sl_dist)
                    entry_idx = i + 1
                elif closes[i] < bb_mid[i] and closes[i] < ema200[i]:
                    pos = -1
                    entry_p = opens[i + 1] - spread * 0.5
                    sl_dist = sl_mult * atr[i]
                    sl_p = entry_p + sl_dist
                    tp_p = entry_p - (tp_mult * sl_dist)
                    entry_idx = i + 1

    return trades

# -----------------------------------------------------------------------------
# Multi-Timeframe Alignment: M15 Macro + M5 Micro Trigger
# -----------------------------------------------------------------------------
def run_mtf_dual_speed_sim(df_m15, df_m5, trigger_mode="squeeze", session_mode="all",
                           unit_size=10.0, spread=0.25, comm=0.60):
    # Compute M15 Indicators
    m15_highs = df_m15["high"].values
    m15_lows = df_m15["low"].values
    m15_closes = df_m15["close"].values
    m15_atr = compute_atr(m15_highs, m15_lows, m15_closes, 14)
    m15_ema200 = compute_ema(m15_closes, 200)
    m15_trend, m15_st = compute_supertrend(m15_highs, m15_lows, m15_closes, m15_atr, 3.0)

    df_m15_state = pd.DataFrame({
        "time": pd.to_datetime(df_m15["time"]),
        "m15_trend": m15_trend,
        "m15_ema200": m15_ema200,
        "m15_close": m15_closes
    }).sort_values("time")

    df_m5_clean = df_m5.copy()
    df_m5_clean["time"] = pd.to_datetime(df_m5_clean["time"])
    df_m5_clean = df_m5_clean.sort_values("time")

    # Merge forward onto M5
    df_m5_merged = pd.merge_asof(df_m5_clean, df_m15_state,
                                 on="time", direction="backward")

    m5_opens = df_m5_merged["open"].values
    m5_highs = df_m5_merged["high"].values
    m5_lows = df_m5_merged["low"].values
    m5_closes = df_m5_merged["close"].values
    m5_dates = pd.to_datetime(df_m5_merged["time"]).dt.to_pydatetime()
    m5_vols = df_m5_merged["volume"].values
    n5 = len(m5_closes)

    m5_atr = compute_atr(m5_highs, m5_lows, m5_closes, 14)
    m5_ema200 = compute_ema(m5_closes, 200)
    m5_cvd = compute_cvd(m5_highs, m5_lows, m5_closes, m5_vols, 20)

    # TTM indicators on M5
    s5_closes = pd.Series(m5_closes)
    bb5_mid = s5_closes.rolling(20).mean().values
    bb5_std = s5_closes.rolling(20).std().fillna(0).values
    bb5_up = bb5_mid + 2.0 * bb5_std
    bb5_dn = bb5_mid - 2.0 * bb5_std
    kc5_up = bb5_mid + 2.0 * m5_atr
    kc5_dn = bb5_mid - 2.0 * m5_atr

    m15_t = df_m5_merged["m15_trend"].values
    m15_ema = df_m5_merged["m15_ema200"].values
    m15_c = df_m5_merged["m15_close"].values

    trades = []
    pos = 0
    entry_p = 0.0
    sl_p = 0.0
    tp_p = 0.0
    entry_idx = 0
    sqz_cnt = 0

    for i in range(200, n5 - 2):
        hour = m5_dates[i].hour
        is_sqz = (bb5_up[i] <= kc5_up[i]) and (bb5_dn[i] >= kc5_dn[i])
        sqz_fired = False

        if is_sqz:
            sqz_cnt += 1
        else:
            if sqz_cnt >= 6:
                sqz_fired = True
            sqz_cnt = 0

        # Check exits
        if pos == 1:
            hit = False
            exit_p = 0.0
            if m5_lows[i] <= sl_p:
                exit_p = sl_p if m5_opens[i] >= sl_p else m5_opens[i]
                hit = True
            elif m5_highs[i] >= tp_p:
                exit_p = tp_p if m5_opens[i] <= tp_p else m5_opens[i]
                hit = True
            # Macro trend invalidation exit
            elif m15_t[i] == -1:
                exit_p = m5_opens[i + 1] - spread * 0.5
                hit = True

            if hit:
                pnl = (exit_p - entry_p) * unit_size - (spread + (comm / unit_size)) * unit_size
                trades.append({
                    "pnl": pnl, "entry_time": m5_dates[entry_idx], "exit_time": m5_dates[i],
                    "year": m5_dates[entry_idx].year, "month": f"{m5_dates[entry_idx].year}-{m5_dates[entry_idx].month:02d}",
                    "entry_idx": entry_idx, "exit_idx": i, "engine": "MTF_DualSpeed"
                })
                pos = 0

        elif pos == -1:
            hit = False
            exit_p = 0.0
            if m5_highs[i] >= sl_p:
                exit_p = sl_p if m5_opens[i] <= sl_p else m5_opens[i]
                hit = True
            elif m5_lows[i] <= tp_p:
                exit_p = tp_p if m5_opens[i] >= tp_p else m5_opens[i]
                hit = True
            # Macro trend invalidation exit
            elif m15_t[i] == 1:
                exit_p = m5_opens[i + 1] + spread * 0.5
                hit = True

            if hit:
                pnl = (entry_p - exit_p) * unit_size - (spread + (comm / unit_size)) * unit_size
                trades.append({
                    "pnl": pnl, "entry_time": m5_dates[entry_idx], "exit_time": m5_dates[i],
                    "year": m5_dates[entry_idx].year, "month": f"{m5_dates[entry_idx].year}-{m5_dates[entry_idx].month:02d}",
                    "entry_idx": entry_idx, "exit_idx": i, "engine": "MTF_DualSpeed"
                })
                pos = 0

        # Check entries
        if pos == 0:
            session_ok = True
            if session_mode == "london":
                session_ok = (7 <= hour < 11)
            elif session_mode == "ny":
                session_ok = (12 <= hour < 17)
            elif session_mode == "dual_session":
                session_ok = (7 <= hour < 11) or (12 <= hour < 17)
            elif session_mode == "skip_rollover":
                session_ok = not (21 <= hour < 23)

            if session_ok:
                # Trigger conditions
                if trigger_mode == "squeeze" and sqz_fired:
                    # Long: M15 Macro Bullish & M5 Squeeze Bullish
                    if m15_t[i] == 1 and m15_c[i] > m15_ema[i] and m5_closes[i] > bb5_mid[i]:
                        pos = 1
                        entry_p = m5_opens[i + 1] + spread * 0.5
                        sl_dist = 3.0 * m5_atr[i]
                        sl_p = entry_p - sl_dist
                        tp_p = entry_p + (3.0 * sl_dist)
                        entry_idx = i + 1
                    # Short: M15 Macro Bearish & M5 Squeeze Bearish
                    elif m15_t[i] == -1 and m15_c[i] < m15_ema[i] and m5_closes[i] < bb5_mid[i]:
                        pos = -1
                        entry_p = m5_opens[i + 1] - spread * 0.5
                        sl_dist = 3.0 * m5_atr[i]
                        sl_p = entry_p + sl_dist
                        tp_p = entry_p - (3.0 * sl_dist)
                        entry_idx = i + 1

                elif trigger_mode == "cvd_squeeze" and sqz_fired:
                    # Long: M15 Macro Bullish & M5 Squeeze Bullish & CVD > 0
                    if m15_t[i] == 1 and m15_c[i] > m15_ema[i] and m5_closes[i] > bb5_mid[i] and m5_cvd[i] > 0:
                        pos = 1
                        entry_p = m5_opens[i + 1] + spread * 0.5
                        sl_dist = 3.0 * m5_atr[i]
                        sl_p = entry_p - sl_dist
                        tp_p = entry_p + (3.0 * sl_dist)
                        entry_idx = i + 1
                    # Short: M15 Macro Bearish & M5 Squeeze Bearish & CVD < 0
                    elif m15_t[i] == -1 and m15_c[i] < m15_ema[i] and m5_closes[i] < bb5_mid[i] and m5_cvd[i] < 0:
                        pos = -1
                        entry_p = m5_opens[i + 1] - spread * 0.5
                        sl_dist = 3.0 * m5_atr[i]
                        sl_p = entry_p + sl_dist
                        tp_p = entry_p - (3.0 * sl_dist)
                        entry_idx = i + 1

    return trades

# -----------------------------------------------------------------------------
# Portfolio Analysis Helper
# -----------------------------------------------------------------------------
def analyze_portfolio(trades_list, start_year=2020, end_year=2025):
    all_trades = []
    for t_list in trades_list:
        all_trades.extend(t_list)
    if not all_trades:
        return {"net_profit": 0, "pf": 0, "trades": 0, "dd": 0, "romad": 0, "wr": 0, "mcr": 0}

    all_trades.sort(key=lambda x: x["entry_time"])
    pnls = [t["pnl"] for t in all_trades]
    cum = np.cumsum(pnls)
    peak = np.maximum.accumulate(cum)
    dd = peak - cum
    max_dd = float(np.max(dd)) if len(dd) > 0 else 1.0

    wins = [p for p in pnls if p > 0]
    losses = [abs(p) for p in pnls if p < 0]
    tot_win = sum(wins)
    tot_loss = sum(losses)
    pf = tot_win / tot_loss if tot_loss > 0 else 99.0
    wr = len(wins) / len(pnls) * 100.0 if len(pnls) > 0 else 0.0

    net = float(cum[-1]) if len(cum) > 0 else 0.0
    romad = net / max_dd if max_dd > 0 else 0.0
    ann_tr = len(all_trades) / (end_year - start_year + 1)

    # Monthly consistency
    m_dict = {}
    for t in all_trades:
        m = t["month"]
        m_dict[m] = m_dict.get(m, 0.0) + t["pnl"]
    pos_m = sum(1 for v in m_dict.values() if v > 0)
    tot_m = 72
    mcr = (pos_m / tot_m) * 100.0

    return {
        "net_profit": net, "pf": pf, "total_trades": len(all_trades),
        "annual_trades": ann_tr, "max_dd": max_dd, "romad": romad,
        "win_rate": wr, "mcr": mcr, "trades": all_trades
    }

# -----------------------------------------------------------------------------
# Main Execution Pipeline
# -----------------------------------------------------------------------------
def main():
    print("=" * 80)
    print("STARTING SCALPING FRONTIER BATCH 23: STRATEGIES 421 - 430")
    print("MULTI-TIMEFRAME DUAL-SPEED MOMENTUM & SESSION EXPANSION (2020-2025)")
    print("=" * 80)

    print(f"[*] Loading M15 Data from: {DATA_M15_PATH}")
    df_m15 = pd.read_parquet(DATA_M15_PATH)
    if "time" not in df_m15.columns:
        df_m15["time"] = pd.to_datetime(df_m15.index)
    if "volume" not in df_m15.columns:
        df_m15["volume"] = 1.0
    print(f"[+] Loaded M15: {len(df_m15):,} bars ({df_m15['time'].min()} to {df_m15['time'].max()})")

    print(f"[*] Loading M5 Data from: {DATA_M5_PATH}")
    df_m5 = pd.read_parquet(DATA_M5_PATH)
    if "time" not in df_m5.columns:
        df_m5["time"] = pd.to_datetime(df_m5.index)
    if "volume" not in df_m5.columns:
        df_m5["volume"] = df_m5["tick_volume"] if "tick_volume" in df_m5.columns else 1.0
    print(f"[+] Loaded M5: {len(df_m5):,} bars ({df_m5['time'].min()} to {df_m5['time'].max()})")

    # M15 Arrays
    m15_opens = df_m15["open"].values.astype(np.float64)
    m15_highs = df_m15["high"].values.astype(np.float64)
    m15_lows = df_m15["low"].values.astype(np.float64)
    m15_closes = df_m15["close"].values.astype(np.float64)
    m15_dates = pd.to_datetime(df_m15["time"]).dt.to_pydatetime()
    m15_atr = compute_atr(m15_highs, m15_lows, m15_closes, 14)
    m15_ema200 = compute_ema(m15_closes, 200)

    # M5 Arrays
    m5_opens = df_m5["open"].values.astype(np.float64)
    m5_highs = df_m5["high"].values.astype(np.float64)
    m5_lows = df_m5["low"].values.astype(np.float64)
    m5_closes = df_m5["close"].values.astype(np.float64)
    m5_dates = pd.to_datetime(df_m5["time"]).dt.to_pydatetime()
    m5_atr = compute_atr(m5_highs, m5_lows, m5_closes, 14)
    m5_ema200 = compute_ema(m5_closes, 200)

    results = []

    # -------------------------------------------------------------------------
    # S421: M15 Benchmark Supertrend Core (S291)
    # -------------------------------------------------------------------------
    print("\n[+] Simulating S421: M15 Benchmark Supertrend Core (S291)...")
    tr_s421 = run_supertrend_session_sim(m15_opens, m15_highs, m15_lows, m15_closes, m15_atr, m15_ema200, m15_dates, "skip_rollover")
    res_s421 = analyze_portfolio([tr_s421])
    res_s421["strategy_id"] = "S421"
    res_s421["name"] = "M15 Benchmark Solo Supertrend Core"
    results.append(res_s421)
    print(f"    S421 Result: Net=${res_s421['net_profit']:,.2f} | PF={res_s421['pf']:.3f} | DD=${res_s421['max_dd']:,.2f} | RoMaD={res_s421['romad']:.2f}x | Tr/Yr={res_s421['annual_trades']:.1f}")

    # -------------------------------------------------------------------------
    # S422: M5 Solo Supertrend Scalper
    # -------------------------------------------------------------------------
    print("\n[+] Simulating S422: M5 Solo Supertrend Scalper...")
    tr_s422 = run_supertrend_session_sim(m5_opens, m5_highs, m5_lows, m5_closes, m5_atr, m5_ema200, m5_dates, "skip_rollover")
    res_s422 = analyze_portfolio([tr_s422])
    res_s422["strategy_id"] = "S422"
    res_s422["name"] = "M5 Solo Supertrend Scalper"
    results.append(res_s422)
    print(f"    S422 Result: Net=${res_s422['net_profit']:,.2f} | PF={res_s422['pf']:.3f} | DD=${res_s422['max_dd']:,.2f} | RoMaD={res_s422['romad']:.2f}x | Tr/Yr={res_s422['annual_trades']:.1f}")

    # -------------------------------------------------------------------------
    # S423: Dual-Speed Hierarchy A (M15 Trend + M5 Squeeze Breakout)
    # -------------------------------------------------------------------------
    print("\n[+] Simulating S423: Dual-Speed Hierarchy A (M15 Trend + M5 Squeeze)...")
    tr_s423 = run_mtf_dual_speed_sim(df_m15, df_m5, trigger_mode="squeeze", session_mode="skip_rollover")
    res_s423 = analyze_portfolio([tr_s423])
    res_s423["strategy_id"] = "S423"
    res_s423["name"] = "Dual-Speed M15-Trend + M5-Squeeze Breakout"
    results.append(res_s423)
    print(f"    S423 Result: Net=${res_s423['net_profit']:,.2f} | PF={res_s423['pf']:.3f} | DD=${res_s423['max_dd']:,.2f} | RoMaD={res_s423['romad']:.2f}x | Tr/Yr={res_s423['annual_trades']:.1f}")

    # -------------------------------------------------------------------------
    # S424: Dual-Speed Hierarchy B (M15 Trend + M5 Supertrend Ratchet)
    # -------------------------------------------------------------------------
    print("\n[+] Simulating S424: Dual-Speed Duo (M15 Core S421 + M5 Squeeze S423)...")
    res_s424 = analyze_portfolio([tr_s421, tr_s423])
    res_s424["strategy_id"] = "S424"
    res_s424["name"] = "Dual-Speed Multi-Timeframe Duo (M15 ST + M5 Squeeze)"
    results.append(res_s424)
    print(f"    S424 Result: Net=${res_s424['net_profit']:,.2f} | PF={res_s424['pf']:.3f} | DD=${res_s424['max_dd']:,.2f} | RoMaD={res_s424['romad']:.2f}x | Tr/Yr={res_s424['annual_trades']:.1f}")

    # -------------------------------------------------------------------------
    # S425: London Open Volatility Expansion (07:00 - 11:00 UTC)
    # -------------------------------------------------------------------------
    print("\n[+] Simulating S425: London Open Volatility Expansion (07:00-11:00 UTC)...")
    tr_s425_st = run_supertrend_session_sim(m15_opens, m15_highs, m15_lows, m15_closes, m15_atr, m15_ema200, m15_dates, "london")
    tr_s425_ttm = run_ttm_squeeze_session_sim(m15_opens, m15_highs, m15_lows, m15_closes, m15_atr, m15_ema200, m15_dates, "london")
    res_s425 = analyze_portfolio([tr_s425_st, tr_s425_ttm])
    res_s425["strategy_id"] = "S425"
    res_s425["name"] = "London Open Volatility Expansion Duo"
    results.append(res_s425)
    print(f"    S425 Result: Net=${res_s425['net_profit']:,.2f} | PF={res_s425['pf']:.3f} | DD=${res_s425['max_dd']:,.2f} | RoMaD={res_s425['romad']:.2f}x | Tr/Yr={res_s425['annual_trades']:.1f}")

    # -------------------------------------------------------------------------
    # S426: NY Open Volatility Expansion (12:00 - 17:00 UTC)
    # -------------------------------------------------------------------------
    print("\n[+] Simulating S426: NY Open Volatility Expansion (12:00-17:00 UTC)...")
    tr_s426_st = run_supertrend_session_sim(m15_opens, m15_highs, m15_lows, m15_closes, m15_atr, m15_ema200, m15_dates, "ny")
    tr_s426_ttm = run_ttm_squeeze_session_sim(m15_opens, m15_highs, m15_lows, m15_closes, m15_atr, m15_ema200, m15_dates, "ny")
    res_s426 = analyze_portfolio([tr_s426_st, tr_s426_ttm])
    res_s426["strategy_id"] = "S426"
    res_s426["name"] = "NY Open Volatility Expansion Duo"
    results.append(res_s426)
    print(f"    S426 Result: Net=${res_s426['net_profit']:,.2f} | PF={res_s426['pf']:.3f} | DD=${res_s426['max_dd']:,.2f} | RoMaD={res_s426['romad']:.2f}x | Tr/Yr={res_s426['annual_trades']:.1f}")

    # -------------------------------------------------------------------------
    # S427: Dual-Session Liquidity Overlap (London + NY)
    # -------------------------------------------------------------------------
    print("\n[+] Simulating S427: Dual-Session Liquidity Overlap (London + NY)...")
    tr_s427_st = run_supertrend_session_sim(m15_opens, m15_highs, m15_lows, m15_closes, m15_atr, m15_ema200, m15_dates, "dual_session")
    tr_s427_ttm = run_ttm_squeeze_session_sim(m15_opens, m15_highs, m15_lows, m15_closes, m15_atr, m15_ema200, m15_dates, "dual_session")
    res_s427 = analyze_portfolio([tr_s427_st, tr_s427_ttm])
    res_s427["strategy_id"] = "S427"
    res_s427["name"] = "Dual-Session Liquidity Overlap Duo"
    results.append(res_s427)
    print(f"    S427 Result: Net=${res_s427['net_profit']:,.2f} | PF={res_s427['pf']:.3f} | DD=${res_s427['max_dd']:,.2f} | RoMaD={res_s427['romad']:.2f}x | Tr/Yr={res_s427['annual_trades']:.1f}")

    # -------------------------------------------------------------------------
    # S428: Dual-Speed Session Apex (M15 Trend + M5 Squeeze in London/NY)
    # -------------------------------------------------------------------------
    print("\n[+] Simulating S428: Dual-Speed Session Apex...")
    tr_s428 = run_mtf_dual_speed_sim(df_m15, df_m5, trigger_mode="squeeze", session_mode="dual_session")
    res_s428 = analyze_portfolio([tr_s428])
    res_s428["strategy_id"] = "S428"
    res_s428["name"] = "Dual-Speed Session Apex (M15 Trend + M5 Squeeze London/NY)"
    results.append(res_s428)
    print(f"    S428 Result: Net=${res_s428['net_profit']:,.2f} | PF={res_s428['pf']:.3f} | DD=${res_s428['max_dd']:,.2f} | RoMaD={res_s428['romad']:.2f}x | Tr/Yr={res_s428['annual_trades']:.1f}")

    # -------------------------------------------------------------------------
    # S429: Multi-Timeframe CVD Micro-Delta Ignition
    # -------------------------------------------------------------------------
    print("\n[+] Simulating S429: Multi-Timeframe CVD Micro-Delta Ignition...")
    tr_s429 = run_mtf_dual_speed_sim(df_m15, df_m5, trigger_mode="cvd_squeeze", session_mode="skip_rollover")
    res_s429 = analyze_portfolio([tr_s429])
    res_s429["strategy_id"] = "S429"
    res_s429["name"] = "Multi-Timeframe CVD Micro-Delta Ignition"
    results.append(res_s429)
    print(f"    S429 Result: Net=${res_s429['net_profit']:,.2f} | PF={res_s429['pf']:.3f} | DD=${res_s429['max_dd']:,.2f} | RoMaD={res_s429['romad']:.2f}x | Tr/Yr={res_s429['annual_trades']:.1f}")

    # -------------------------------------------------------------------------
    # S430: Centennial Multi-Timeframe Sovereign Suite
    # -------------------------------------------------------------------------
    print("\n[+] Simulating S430: Centennial Multi-Timeframe Sovereign Suite...")
    res_s430 = analyze_portfolio([tr_s421, tr_s427_ttm, tr_s429])
    res_s430["strategy_id"] = "S430"
    res_s430["name"] = "Centennial Multi-Timeframe Sovereign Suite"
    results.append(res_s430)
    print(f"    S430 Result: Net=${res_s430['net_profit']:,.2f} | PF={res_s430['pf']:.3f} | DD=${res_s430['max_dd']:,.2f} | RoMaD={res_s430['romad']:.2f}x | Tr/Yr={res_s430['annual_trades']:.1f}")

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
    csv_path = os.path.join(RESULTS_DIR, "scalping_mtf_session_batch_421_430_matrix.csv")
    df_matrix.to_csv(csv_path, index=False)
    print(f"\n[+] Saved Matrix CSV to: {csv_path}")

    # Remove non-serializable trade objects for JSON export
    clean_results = []
    for r in results:
        rc = {k: v for k, v in r.items() if k != "trades"}
        clean_results.append(rc)

    json_path = os.path.join(RESULTS_DIR, "scalping_mtf_session_batch_421_430_results.json")
    with open(json_path, "w") as f:
        json.dump(clean_results, f, indent=2)
    print(f"[+] Saved Results JSON to: {json_path}")

    print("\n" + "=" * 80)
    print("BATCH 23 EXECUTION COMPLETE")
    print("=" * 80)
    print(df_matrix.to_string(index=False))

    gc.collect()

if __name__ == "__main__":
    main()
