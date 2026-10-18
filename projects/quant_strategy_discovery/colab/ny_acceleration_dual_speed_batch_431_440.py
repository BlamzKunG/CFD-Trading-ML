#!/usr/bin/env python3
"""
===============================================================================
SCALPING FRONTIER BATCH 24: STRATEGIES 431 - 440
NEW YORK SESSION ACCELERATION & DUAL-SPEED FINE-TUNING (2020-2025)
===============================================================================
Asset: XAUUSD (Gold)
Multi-Timeframe Matrix: M15 Macro Regime + M5 Micro Trigger Execution
Period: 2020-01-01 to 2025-12-30 (6 Full Multi-Year Regimes / 423,930 M5 Bars)
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
# Fast Technical Indicator Helpers
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
# Microstructure CVD
# -----------------------------------------------------------------------------
def compute_cvd(highs: np.ndarray, lows: np.ndarray, closes: np.ndarray, volumes: np.ndarray, period: int = 20):
    rng = np.maximum(highs - lows, 1e-4)
    delta_ratio = ((closes - lows) - (highs - closes)) / rng
    bar_delta = delta_ratio * volumes
    cvd = pd.Series(bar_delta).rolling(period).sum().fillna(0).values
    return cvd

# -----------------------------------------------------------------------------
# Advanced Multi-Timeframe Simulator
# -----------------------------------------------------------------------------
def run_dual_speed_adv_sim(df_m15, df_m5, exit_mode="fixed_3r", exec_mode="market",
                           session_mode="all", use_dynamic_vol=False, use_cvd=False,
                           unit_size=10.0, spread=0.25, comm=0.60):
    # Compute M15 Indicators
    m15_highs = df_m15["high"].values.astype(np.float64)
    m15_lows = df_m15["low"].values.astype(np.float64)
    m15_closes = df_m15["close"].values.astype(np.float64)
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
    df_m5_merged = pd.merge_asof(df_m5_clean, df_m15_state, on="time", direction="backward")

    m5_opens = df_m5_merged["open"].values.astype(np.float64)
    m5_highs = df_m5_merged["high"].values.astype(np.float64)
    m5_lows = df_m5_merged["low"].values.astype(np.float64)
    m5_closes = df_m5_merged["close"].values.astype(np.float64)
    m5_dates = pd.to_datetime(df_m5_merged["time"]).dt.to_pydatetime()
    m5_vols = df_m5_merged["volume"].values.astype(np.float64)
    n5 = len(m5_closes)

    m5_atr = compute_atr(m5_highs, m5_lows, m5_closes, 14)
    m5_cvd = compute_cvd(m5_highs, m5_lows, m5_closes, m5_vols, 20)

    # Relative volume
    vol_ema20 = compute_ema(m5_vols, 20)
    rel_vol = m5_vols / np.maximum(vol_ema20, 1.0)

    # TTM indicators on M5
    s5_closes = pd.Series(m5_closes)
    bb5_mid = s5_closes.rolling(20).mean().values
    bb5_std = s5_closes.rolling(20).std().fillna(0).values
    bb5_up = bb5_mid + 2.0 * bb5_std
    bb5_dn = bb5_mid - 2.0 * bb5_std
    kc5_up = bb5_mid + 2.0 * m5_atr
    kc5_dn = bb5_mid - 2.0 * m5_atr

    # M5 Supertrend for dual-ratchet mode
    m5_st_trend, m5_st_band = compute_supertrend(m5_highs, m5_lows, m5_closes, m5_atr, 3.0)

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
    cur_lot = 1.0

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
            if exit_mode == "fixed_3r":
                if m5_lows[i] <= sl_p:
                    exit_p = sl_p if m5_opens[i] >= sl_p else m5_opens[i]
                    hit = True
                elif m5_highs[i] >= tp_p:
                    exit_p = tp_p if m5_opens[i] <= tp_p else m5_opens[i]
                    hit = True
                elif m15_t[i] == -1:
                    exit_p = m5_opens[i + 1] - spread * 0.5
                    hit = True
            elif exit_mode == "m5_ratchet":
                cur_st = m5_st_band[i]
                if m5_lows[i] <= cur_st:
                    exit_p = cur_st if m5_opens[i] >= cur_st else m5_opens[i]
                    hit = True
                elif m5_st_trend[i] == -1 or m15_t[i] == -1:
                    exit_p = m5_opens[i + 1] - spread * 0.5
                    hit = True

            if hit:
                pnl = (exit_p - entry_p) * unit_size * cur_lot - (spread + (comm / unit_size)) * unit_size * cur_lot
                trades.append({
                    "pnl": pnl, "entry_time": m5_dates[entry_idx], "exit_time": m5_dates[i],
                    "year": m5_dates[entry_idx].year, "month": f"{m5_dates[entry_idx].year}-{m5_dates[entry_idx].month:02d}",
                    "entry_idx": entry_idx, "exit_idx": i, "engine": "DualSpeed_M5"
                })
                pos = 0

        elif pos == -1:
            hit = False
            exit_p = 0.0
            if exit_mode == "fixed_3r":
                if m5_highs[i] >= sl_p:
                    exit_p = sl_p if m5_opens[i] <= sl_p else m5_opens[i]
                    hit = True
                elif m5_lows[i] <= tp_p:
                    exit_p = tp_p if m5_opens[i] >= tp_p else m5_opens[i]
                    hit = True
                elif m15_t[i] == 1:
                    exit_p = m5_opens[i + 1] + spread * 0.5
                    hit = True
            elif exit_mode == "m5_ratchet":
                cur_st = m5_st_band[i]
                if m5_highs[i] >= cur_st:
                    exit_p = cur_st if m5_opens[i] <= cur_st else m5_opens[i]
                    hit = True
                elif m5_st_trend[i] == 1 or m15_t[i] == 1:
                    exit_p = m5_opens[i + 1] + spread * 0.5
                    hit = True

            if hit:
                pnl = (entry_p - exit_p) * unit_size * cur_lot - (spread + (comm / unit_size)) * unit_size * cur_lot
                trades.append({
                    "pnl": pnl, "entry_time": m5_dates[entry_idx], "exit_time": m5_dates[i],
                    "year": m5_dates[entry_idx].year, "month": f"{m5_dates[entry_idx].year}-{m5_dates[entry_idx].month:02d}",
                    "entry_idx": entry_idx, "exit_idx": i, "engine": "DualSpeed_M5"
                })
                pos = 0

        # Check entries
        if pos == 0 and sqz_fired:
            session_ok = True
            if session_mode == "ny_only":
                session_ok = (12 <= hour < 17)
            elif session_mode == "london_ny":
                session_ok = (7 <= hour < 11) or (12 <= hour < 17)
            elif session_mode == "skip_rollover":
                session_ok = not (21 <= hour < 23)

            cvd_ok_long = (not use_cvd) or (m5_cvd[i] > 0)
            cvd_ok_short = (not use_cvd) or (m5_cvd[i] < 0)

            if session_ok:
                lot_scale = 1.0
                if use_dynamic_vol:
                    lot_scale = np.clip(rel_vol[i], 0.8, 1.3)

                # Long: M15 Macro Bullish & M5 Squeeze Bullish
                if m15_t[i] == 1 and m15_c[i] > m15_ema[i] and m5_closes[i] > bb5_mid[i] and cvd_ok_long:
                    fill_ok = True
                    fill_p = m5_opens[i + 1] + spread * 0.5
                    if exec_mode == "limit_pullback":
                        limit_target = m5_opens[i + 1] - 0.20 * m5_atr[i]
                        # Did price touch limit pullback in bar i+1?
                        if m5_lows[i + 1] <= limit_target:
                            fill_p = limit_target
                        else:
                            fill_ok = False

                    if fill_ok:
                        pos = 1
                        entry_p = fill_p
                        cur_lot = lot_scale
                        sl_dist = 3.0 * m5_atr[i]
                        sl_p = entry_p - sl_dist
                        tp_p = entry_p + (3.0 * sl_dist)
                        entry_idx = i + 1

                # Short: M15 Macro Bearish & M5 Squeeze Bearish
                elif m15_t[i] == -1 and m15_c[i] < m15_ema[i] and m5_closes[i] < bb5_mid[i] and cvd_ok_short:
                    fill_ok = True
                    fill_p = m5_opens[i + 1] - spread * 0.5
                    if exec_mode == "limit_pullback":
                        limit_target = m5_opens[i + 1] + 0.20 * m5_atr[i]
                        if m5_highs[i + 1] >= limit_target:
                            fill_p = limit_target
                        else:
                            fill_ok = False

                    if fill_ok:
                        pos = -1
                        entry_p = fill_p
                        cur_lot = lot_scale
                        sl_dist = 3.0 * m5_atr[i]
                        sl_p = entry_p + sl_dist
                        tp_p = entry_p - (3.0 * sl_dist)
                        entry_idx = i + 1

    return trades

# -----------------------------------------------------------------------------
# Portfolio Analysis Helper with Optional Monthly Governor
# -----------------------------------------------------------------------------
def analyze_portfolio(trades_list, start_year=2020, end_year=2025, monthly_loss_cap=None):
    all_trades = []
    for t_list in trades_list:
        all_trades.extend(t_list)
    if not all_trades:
        return {"net_profit": 0, "pf": 0, "trades": 0, "dd": 0, "romad": 0, "wr": 0, "mcr": 0}

    all_trades.sort(key=lambda x: x["entry_time"])

    # If monthly governor is active, filter trades when monthly loss limit is breached
    filtered_trades = []
    if monthly_loss_cap is not None:
        cur_month = ""
        cur_m_loss = 0.0
        for t in all_trades:
            m = t["month"]
            if m != cur_month:
                cur_month = m
                cur_m_loss = 0.0

            if cur_m_loss <= -monthly_loss_cap:
                continue

            filtered_trades.append(t)
            if t["pnl"] < 0:
                cur_m_loss += t["pnl"]
        all_trades = filtered_trades

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
# Main Simulation Pipeline
# -----------------------------------------------------------------------------
def main():
    print("=" * 80)
    print("STARTING SCALPING FRONTIER BATCH 24: STRATEGIES 431 - 440")
    print("NEW YORK ACCELERATION & DUAL-SPEED FINE-TUNING (2020-2025)")
    print("=" * 80)

    print(f"[*] Loading M15 Data from: {DATA_M15_PATH}")
    df_m15 = pd.read_parquet(DATA_M15_PATH)
    if "time" not in df_m15.columns:
        df_m15["time"] = pd.to_datetime(df_m15.index)
    if "volume" not in df_m15.columns:
        df_m15["volume"] = 1.0
    print(f"[+] Loaded M15: {len(df_m15):,} bars")

    print(f"[*] Loading M5 Data from: {DATA_M5_PATH}")
    df_m5 = pd.read_parquet(DATA_M5_PATH)
    if "time" not in df_m5.columns:
        df_m5["time"] = pd.to_datetime(df_m5.index)
    if "volume" not in df_m5.columns:
        df_m5["volume"] = df_m5["tick_volume"] if "tick_volume" in df_m5.columns else 1.0
    print(f"[+] Loaded M5: {len(df_m5):,} bars")

    # Import baseline M15 engines from Batch 23
    from mtf_session_momentum_scalper_batch_421_430 import (
        run_supertrend_session_sim, run_ttm_squeeze_session_sim
    )

    m15_opens = df_m15["open"].values.astype(np.float64)
    m15_highs = df_m15["high"].values.astype(np.float64)
    m15_lows = df_m15["low"].values.astype(np.float64)
    m15_closes = df_m15["close"].values.astype(np.float64)
    m15_dates = pd.to_datetime(df_m15["time"]).dt.to_pydatetime()
    m15_atr = compute_atr(m15_highs, m15_lows, m15_closes, 14)
    m15_ema200 = compute_ema(m15_closes, 200)

    # Core M15 Supertrend Anchor
    tr_m15_core = run_supertrend_session_sim(m15_opens, m15_highs, m15_lows, m15_closes, m15_atr, m15_ema200, m15_dates, "skip_rollover")

    results = []

    # -------------------------------------------------------------------------
    # S431: Baseline S424 Dual-Speed Duo Benchmark
    # -------------------------------------------------------------------------
    print("\n[+] Simulating S431: Baseline S424 Dual-Speed Duo Benchmark...")
    tr_s431_m5 = run_dual_speed_adv_sim(df_m15, df_m5, exit_mode="fixed_3r", exec_mode="market", session_mode="skip_rollover")
    res_s431 = analyze_portfolio([tr_m15_core, tr_s431_m5])
    res_s431["strategy_id"] = "S431"
    res_s431["name"] = "Baseline S424 Dual-Speed Duo Benchmark"
    results.append(res_s431)
    print(f"    S431 Result: Net=${res_s431['net_profit']:,.2f} | PF={res_s431['pf']:.3f} | DD=${res_s431['max_dd']:,.2f} | RoMaD={res_s431['romad']:.2f}x | Tr/Yr={res_s431['annual_trades']:.1f}")

    # -------------------------------------------------------------------------
    # S432: NY Session Acceleration Dual-Speed (M5 Active Only 12:00-17:00 UTC)
    # -------------------------------------------------------------------------
    print("\n[+] Simulating S432: NY Session Acceleration Dual-Speed...")
    tr_s432_m5 = run_dual_speed_adv_sim(df_m15, df_m5, exit_mode="fixed_3r", exec_mode="market", session_mode="ny_only")
    res_s432 = analyze_portfolio([tr_m15_core, tr_s432_m5])
    res_s432["strategy_id"] = "S432"
    res_s432["name"] = "NY Acceleration Dual-Speed (M15 Core + M5 NY Squeeze)"
    results.append(res_s432)
    print(f"    S432 Result: Net=${res_s432['net_profit']:,.2f} | PF={res_s432['pf']:.3f} | DD=${res_s432['max_dd']:,.2f} | RoMaD={res_s432['romad']:.2f}x | Tr/Yr={res_s432['annual_trades']:.1f}")

    # -------------------------------------------------------------------------
    # S433: Dual Monotonic Ratchet (M5 Ratchet Trailing Exit)
    # -------------------------------------------------------------------------
    print("\n[+] Simulating S433: Dual Monotonic Ratchet (M5 Trailing Ratchet)...")
    tr_s433_m5 = run_dual_speed_adv_sim(df_m15, df_m5, exit_mode="m5_ratchet", exec_mode="market", session_mode="skip_rollover")
    res_s433 = analyze_portfolio([tr_m15_core, tr_s433_m5])
    res_s433["strategy_id"] = "S433"
    res_s433["name"] = "Dual Monotonic Ratchet (M15 Ratchet + M5 Ratchet)"
    results.append(res_s433)
    print(f"    S433 Result: Net=${res_s433['net_profit']:,.2f} | PF={res_s433['pf']:.3f} | DD=${res_s433['max_dd']:,.2f} | RoMaD={res_s433['romad']:.2f}x | Tr/Yr={res_s433['annual_trades']:.1f}")

    # -------------------------------------------------------------------------
    # S434: Hybrid Execution Dual-Speed (M5 Limit Pullback -0.2x ATR)
    # -------------------------------------------------------------------------
    print("\n[+] Simulating S434: Hybrid Execution Dual-Speed (M5 Limit -0.2x ATR)...")
    tr_s434_m5 = run_dual_speed_adv_sim(df_m15, df_m5, exit_mode="fixed_3r", exec_mode="limit_pullback", session_mode="skip_rollover")
    res_s434 = analyze_portfolio([tr_m15_core, tr_s434_m5])
    res_s434["strategy_id"] = "S434"
    res_s434["name"] = "Hybrid Execution Dual-Speed (M15 Market + M5 Limit Pullback)"
    results.append(res_s434)
    print(f"    S434 Result: Net=${res_s434['net_profit']:,.2f} | PF={res_s434['pf']:.3f} | DD=${res_s434['max_dd']:,.2f} | RoMaD={res_s434['romad']:.2f}x | Tr/Yr={res_s434['annual_trades']:.1f}")

    # -------------------------------------------------------------------------
    # S435: Dynamic Volume Sized Dual-Speed (0.8x - 1.3x Lot Scaling)
    # -------------------------------------------------------------------------
    print("\n[+] Simulating S435: Dynamic Volume Sized Dual-Speed...")
    tr_s435_m5 = run_dual_speed_adv_sim(df_m15, df_m5, exit_mode="fixed_3r", exec_mode="market", session_mode="skip_rollover", use_dynamic_vol=True)
    res_s435 = analyze_portfolio([tr_m15_core, tr_s435_m5])
    res_s435["strategy_id"] = "S435"
    res_s435["name"] = "Dynamic Volume Sized Dual-Speed"
    results.append(res_s435)
    print(f"    S435 Result: Net=${res_s435['net_profit']:,.2f} | PF={res_s435['pf']:.3f} | DD=${res_s435['max_dd']:,.2f} | RoMaD={res_s435['romad']:.2f}x | Tr/Yr={res_s435['annual_trades']:.1f}")

    # -------------------------------------------------------------------------
    # S436: NY Limit Acceleration Dual-Speed (NY Session + Limit Pullback)
    # -------------------------------------------------------------------------
    print("\n[+] Simulating S436: NY Limit Acceleration Dual-Speed...")
    tr_s436_m5 = run_dual_speed_adv_sim(df_m15, df_m5, exit_mode="fixed_3r", exec_mode="limit_pullback", session_mode="ny_only")
    res_s436 = analyze_portfolio([tr_m15_core, tr_s436_m5])
    res_s436["strategy_id"] = "S436"
    res_s436["name"] = "NY Limit Acceleration Dual-Speed"
    results.append(res_s436)
    print(f"    S436 Result: Net=${res_s436['net_profit']:,.2f} | PF={res_s436['pf']:.3f} | DD=${res_s436['max_dd']:,.2f} | RoMaD={res_s436['romad']:.2f}x | Tr/Yr={res_s436['annual_trades']:.1f}")

    # -------------------------------------------------------------------------
    # S437: Dual-Speed Trio (M15 ST + M15 TTM + M5 Squeeze)
    # -------------------------------------------------------------------------
    print("\n[+] Simulating S437: Dual-Speed Trio Suite...")
    tr_m15_ttm = run_ttm_squeeze_session_sim(m15_opens, m15_highs, m15_lows, m15_closes, m15_atr, m15_ema200, m15_dates, "skip_rollover")
    res_s437 = analyze_portfolio([tr_m15_core, tr_m15_ttm, tr_s431_m5])
    res_s437["strategy_id"] = "S437"
    res_s437["name"] = "Dual-Speed Multi-Timeframe Trio Suite"
    results.append(res_s437)
    print(f"    S437 Result: Net=${res_s437['net_profit']:,.2f} | PF={res_s437['pf']:.3f} | DD=${res_s437['max_dd']:,.2f} | RoMaD={res_s437['romad']:.2f}x | Tr/Yr={res_s437['annual_trades']:.1f}")

    # -------------------------------------------------------------------------
    # S438: Dual-Speed CVD Microstructure Quartet (Trio + M5 CVD Alignment)
    # -------------------------------------------------------------------------
    print("\n[+] Simulating S438: Dual-Speed CVD Microstructure Quartet...")
    tr_s438_m5 = run_dual_speed_adv_sim(df_m15, df_m5, exit_mode="fixed_3r", exec_mode="market", session_mode="skip_rollover", use_cvd=True)
    res_s438 = analyze_portfolio([tr_m15_core, tr_m15_ttm, tr_s438_m5])
    res_s438["strategy_id"] = "S438"
    res_s438["name"] = "Dual-Speed CVD Microstructure Quartet"
    results.append(res_s438)
    print(f"    S438 Result: Net=${res_s438['net_profit']:,.2f} | PF={res_s438['pf']:.3f} | DD=${res_s438['max_dd']:,.2f} | RoMaD={res_s438['romad']:.2f}x | Tr/Yr={res_s438['annual_trades']:.1f}")

    # -------------------------------------------------------------------------
    # S439: Prop-Firm Governed Dual-Speed S424 ($1,200 Monthly Loss Cap)
    # -------------------------------------------------------------------------
    print("\n[+] Simulating S439: Prop-Firm Governed Dual-Speed S424 ($1,200 Cap)...")
    res_s439 = analyze_portfolio([tr_m15_core, tr_s431_m5], monthly_loss_cap=1200.0)
    res_s439["strategy_id"] = "S439"
    res_s439["name"] = "Prop-Firm Governed Dual-Speed S424 ($1,200 Cap)"
    results.append(res_s439)
    print(f"    S439 Result: Net=${res_s439['net_profit']:,.2f} | PF={res_s439['pf']:.3f} | DD=${res_s439['max_dd']:,.2f} | RoMaD={res_s439['romad']:.2f}x | Tr/Yr={res_s439['annual_trades']:.1f}")

    # -------------------------------------------------------------------------
    # S440: Centennial Dual-Speed Sovereign Apex Suite
    # -------------------------------------------------------------------------
    print("\n[+] Simulating S440: Centennial Dual-Speed Sovereign Apex Suite...")
    res_s440 = analyze_portfolio([tr_m15_core, tr_s434_m5, tr_s436_m5], monthly_loss_cap=1500.0)
    res_s440["strategy_id"] = "S440"
    res_s440["name"] = "Centennial Dual-Speed Sovereign Apex Suite"
    results.append(res_s440)
    print(f"    S440 Result: Net=${res_s440['net_profit']:,.2f} | PF={res_s440['pf']:.3f} | DD=${res_s440['max_dd']:,.2f} | RoMaD={res_s440['romad']:.2f}x | Tr/Yr={res_s440['annual_trades']:.1f}")

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
    csv_path = os.path.join(RESULTS_DIR, "scalping_ny_dual_speed_batch_431_440_matrix.csv")
    df_matrix.to_csv(csv_path, index=False)
    print(f"\n[+] Saved Matrix CSV to: {csv_path}")

    clean_results = []
    for r in results:
        rc = {k: v for k, v in r.items() if k != "trades"}
        clean_results.append(rc)

    json_path = os.path.join(RESULTS_DIR, "scalping_ny_dual_speed_batch_431_440_results.json")
    with open(json_path, "w") as f:
        json.dump(clean_results, f, indent=2)
    print(f"[+] Saved Results JSON to: {json_path}")

    print("\n" + "=" * 80)
    print("BATCH 24 EXECUTION COMPLETE")
    print("=" * 80)
    print(df_matrix.to_string(index=False))

    gc.collect()

if __name__ == "__main__":
    main()
