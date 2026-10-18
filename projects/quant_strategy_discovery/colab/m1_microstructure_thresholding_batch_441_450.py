#!/usr/bin/env python3
"""
===============================================================================
SCALPING FRONTIER BATCH 25: STRATEGIES 441 - 450
M1 MICROSTRUCTURE SCALPING & VOLATILITY THRESHOLDING (2020-2025)
===============================================================================
Asset: XAUUSD (Gold)
Multi-Timeframe Matrix: M15 Macro Regime Filter + M5 Squeeze + M1 Micro Sniper Execution
Period: 2020-01-01 to 2025-12-30 (6 Full Multi-Year Regimes / 2,116,595 M1 Bars)
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

# -----------------------------------------------------------------------------
# Fast Technical Indicator Helpers (Numpy Optimized)
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
# Micro M1 Simulator (Pre-Indexed Numpy Arrays for Extreme Speed)
# -----------------------------------------------------------------------------
def run_fast_m1_scalper(
    m1_opens, m1_highs, m1_lows, m1_closes, m1_py_dates, m1_hours, m1_years, m1_months,
    m1_atr, m1_trend, m1_st_band, m15_macro_trend,
    min_m1_atr=0.0, session_mode="skip_rollover", use_macro_filter=True, use_m1_ratchet=True,
    unit_size=10.0, spread=0.25, comm=0.60
):
    n1 = len(m1_closes)
    trades = []
    pos = 0
    entry_p = 0.0
    sl_p = 0.0
    tp_p = 0.0
    entry_idx = 0

    for i in range(200, n1 - 2):
        hour = m1_hours[i]
        cur_t = m1_trend[i]
        prev_t = m1_trend[i - 1]
        cur_st = m1_st_band[i]

        # Check exits
        if pos == 1:
            hit = False
            exit_p = 0.0
            if use_m1_ratchet:
                if m1_lows[i] <= cur_st:
                    exit_p = cur_st if m1_opens[i] >= cur_st else m1_opens[i]
                    hit = True
                elif cur_t == -1:
                    exit_p = m1_opens[i + 1] - spread * 0.5
                    hit = True
            else:
                if m1_lows[i] <= sl_p:
                    exit_p = sl_p if m1_opens[i] >= sl_p else m1_opens[i]
                    hit = True
                elif m1_highs[i] >= tp_p:
                    exit_p = tp_p if m1_opens[i] <= tp_p else m1_opens[i]
                    hit = True

            if hit:
                pnl = (exit_p - entry_p) * unit_size - (spread + (comm / unit_size)) * unit_size
                trades.append({
                    "pnl": pnl, "entry_time": m1_py_dates[entry_idx], "exit_time": m1_py_dates[i],
                    "year": m1_years[entry_idx], "month": m1_months[entry_idx],
                    "entry_idx": entry_idx, "exit_idx": i, "engine": "M1_Scalper"
                })
                pos = 0

        elif pos == -1:
            hit = False
            exit_p = 0.0
            if use_m1_ratchet:
                if m1_highs[i] >= cur_st:
                    exit_p = cur_st if m1_opens[i] <= cur_st else m1_opens[i]
                    hit = True
                elif cur_t == 1:
                    exit_p = m1_opens[i + 1] + spread * 0.5
                    hit = True
            else:
                if m1_highs[i] >= sl_p:
                    exit_p = sl_p if m1_opens[i] <= sl_p else m1_opens[i]
                    hit = True
                elif m1_lows[i] <= tp_p:
                    exit_p = tp_p if m1_opens[i] >= tp_p else m1_opens[i]
                    hit = True

            if hit:
                pnl = (entry_p - exit_p) * unit_size - (spread + (comm / unit_size)) * unit_size
                trades.append({
                    "pnl": pnl, "entry_time": m1_py_dates[entry_idx], "exit_time": m1_py_dates[i],
                    "year": m1_years[entry_idx], "month": m1_months[entry_idx],
                    "entry_idx": entry_idx, "exit_idx": i, "engine": "M1_Scalper"
                })
                pos = 0

        # Check entries on fresh M1 trend flip
        if pos == 0:
            session_ok = True
            if session_mode == "ny_only":
                session_ok = (12 <= hour < 17)
            elif session_mode == "skip_rollover":
                session_ok = not (21 <= hour < 23)

            vol_ok = (m1_atr[i] >= min_m1_atr)

            if session_ok and vol_ok:
                if cur_t == 1 and prev_t == -1:
                    macro_ok = (not use_macro_filter) or (m15_macro_trend[i] == 1)
                    if macro_ok:
                        pos = 1
                        entry_p = m1_opens[i + 1] + spread * 0.5
                        sl_dist = 3.0 * m1_atr[i]
                        sl_p = entry_p - sl_dist
                        tp_p = entry_p + (3.0 * sl_dist)
                        entry_idx = i + 1
                elif cur_t == -1 and prev_t == 1:
                    macro_ok = (not use_macro_filter) or (m15_macro_trend[i] == -1)
                    if macro_ok:
                        pos = -1
                        entry_p = m1_opens[i + 1] - spread * 0.5
                        sl_dist = 3.0 * m1_atr[i]
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
        return {"net_profit": 0, "pf": 0, "total_trades": 0, "annual_trades": 0, "max_dd": 1.0, "romad": 0, "win_rate": 0, "mcr": 0, "trades": []}

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
    start_total_time = time.time()
    print("=" * 80)
    print("STARTING SCALPING FRONTIER BATCH 25: STRATEGIES 441 - 450")
    print("M1 MICROSTRUCTURE SCALPING & VOLATILITY THRESHOLDING (2020-2025)")
    print("=" * 80)

    # 1. Load M15
    print(f"[*] Loading M15 Data from: {os.path.join(DATA_DIR, 'XAUUSD_M15.parquet')}")
    df_m15 = pd.read_parquet(os.path.join(DATA_DIR, "XAUUSD_M15.parquet"))
    if "time" not in df_m15.columns:
        df_m15["time"] = pd.to_datetime(df_m15.index)
    if "volume" not in df_m15.columns:
        df_m15["volume"] = 1.0
    print(f"[+] Loaded M15: {len(df_m15):,} bars")

    # 2. Compute M15 Macro State
    m15_highs = df_m15["high"].values.astype(np.float64)
    m15_lows = df_m15["low"].values.astype(np.float64)
    m15_closes = df_m15["close"].values.astype(np.float64)
    m15_opens = df_m15["open"].values.astype(np.float64)
    m15_dates = pd.to_datetime(df_m15["time"]).dt.to_pydatetime()
    m15_atr = compute_atr(m15_highs, m15_lows, m15_closes, 14)
    m15_ema200 = compute_ema(m15_closes, 200)
    m15_trend, _ = compute_supertrend(m15_highs, m15_lows, m15_closes, m15_atr, 3.0)

    df_m15_state = pd.DataFrame({
        "time": pd.to_datetime(df_m15["time"]),
        "m15_trend": m15_trend
    }).sort_values("time")

    # Import proven M15 Core & M5 Ratchet
    from mtf_session_momentum_scalper_batch_421_430 import run_supertrend_session_sim
    from ny_acceleration_dual_speed_batch_431_440 import run_dual_speed_adv_sim

    print("[*] Generating Baseline M15 Core Trades...")
    tr_m15_core = run_supertrend_session_sim(m15_opens, m15_highs, m15_lows, m15_closes, m15_atr, m15_ema200, m15_dates, "skip_rollover")
    print(f"[+] M15 Core Trades: {len(tr_m15_core):,} trades")

    # Load M5 for triple-timeframe synthesis
    print(f"[*] Loading M5 Data from: {os.path.join(DATA_DIR, 'XAUUSD_M5.parquet')}")
    df_m5 = pd.read_parquet(os.path.join(DATA_DIR, "XAUUSD_M5.parquet"))
    if "time" not in df_m5.columns:
        df_m5["time"] = pd.to_datetime(df_m5.index)
    if "volume" not in df_m5.columns:
        df_m5["volume"] = df_m5["tick_volume"] if "tick_volume" in df_m5.columns else 1.0

    print("[*] Generating S433 M5 Ratchet Trades...")
    tr_m5_ratchet = run_dual_speed_adv_sim(df_m15, df_m5, exit_mode="m5_ratchet", exec_mode="market", session_mode="skip_rollover")
    print(f"[+] M5 Ratchet Trades: {len(tr_m5_ratchet):,} trades")

    # Free M5 memory
    del df_m5
    gc.collect()

    # 3. Load M1 Data
    print(f"\n[*] Loading M1 Data from: {os.path.join(DATA_DIR, 'XAUUSD_M1.parquet')}")
    df_m1 = pd.read_parquet(os.path.join(DATA_DIR, "XAUUSD_M1.parquet"))
    if "time" not in df_m1.columns:
        df_m1["time"] = pd.to_datetime(df_m1.index)
    print(f"[+] Loaded M1: {len(df_m1):,} bars")

    # Align M15 macro trend onto M1 using merge_asof
    print("[*] Merging M15 macro state onto M1...")
    df_m1_time = pd.DataFrame({"time": pd.to_datetime(df_m1["time"])})
    merged_state = pd.merge_asof(df_m1_time, df_m15_state, on="time", direction="backward")
    m15_macro_trend = merged_state["m15_trend"].fillna(1).values.astype(np.int32)
    del df_m1_time, merged_state, df_m15_state
    gc.collect()

    # Extract M1 numpy arrays
    print("[*] Extracting M1 numpy arrays & timestamps...")
    m1_opens = df_m1["open"].values.astype(np.float64)
    m1_highs = df_m1["high"].values.astype(np.float64)
    m1_lows = df_m1["low"].values.astype(np.float64)
    m1_closes = df_m1["close"].values.astype(np.float64)

    m1_time_series = pd.to_datetime(df_m1["time"])
    m1_hours = m1_time_series.dt.hour.values.astype(np.int8)
    m1_years = m1_time_series.dt.year.values.astype(np.int16)
    m1_months = (m1_time_series.dt.year.astype(str) + "-" + m1_time_series.dt.month.astype(str).str.zfill(2)).values
    m1_py_dates = m1_time_series.dt.to_pydatetime()

    # Free df_m1
    del df_m1, m1_time_series
    gc.collect()

    # 4. Compute M1 Indicators ONCE
    print("[*] Pre-computing M1 ATR(14)...")
    m1_atr = compute_atr(m1_highs, m1_lows, m1_closes, 14)
    print(f"[+] M1 ATR(14) computed. Mean ATR = ${np.mean(m1_atr[200:]):.2f}")

    print("[*] Pre-computing M1 Supertrend(3.0)...")
    m1_trend, m1_st_band = compute_supertrend(m1_highs, m1_lows, m1_closes, m1_atr, 3.0)
    print("[+] M1 Supertrend(3.0) computed.")

    results = []

    # S441: Unconstrained M1 Supertrend Baseline
    print("\n[+] Simulating S441: Unconstrained M1 Supertrend Baseline...")
    t0 = time.time()
    tr_s441 = run_fast_m1_scalper(
        m1_opens, m1_highs, m1_lows, m1_closes, m1_py_dates, m1_hours, m1_years, m1_months,
        m1_atr, m1_trend, m1_st_band, m15_macro_trend,
        min_m1_atr=0.0, session_mode="skip_rollover", use_macro_filter=False, use_m1_ratchet=True
    )
    res_s441 = analyze_portfolio([tr_s441])
    res_s441["strategy_id"] = "S441"
    res_s441["name"] = "Unconstrained M1 Supertrend Baseline"
    results.append(res_s441)
    print(f"    S441 Result ({time.time()-t0:.1f}s): Net=${res_s441['net_profit']:,.2f} | PF={res_s441['pf']:.3f} | DD=${res_s441['max_dd']:,.2f} | RoMaD={res_s441['romad']:.2f}x | Tr/Yr={res_s441['annual_trades']:.1f}")

    # S442: M1 Supertrend + Mild Volatility Threshold (ATR >= $0.80)
    print("\n[+] Simulating S442: M1 Supertrend + Mild Volatility Threshold (ATR >= $0.80)...")
    t0 = time.time()
    tr_s442 = run_fast_m1_scalper(
        m1_opens, m1_highs, m1_lows, m1_closes, m1_py_dates, m1_hours, m1_years, m1_months,
        m1_atr, m1_trend, m1_st_band, m15_macro_trend,
        min_m1_atr=0.80, session_mode="skip_rollover", use_macro_filter=True, use_m1_ratchet=True
    )
    res_s442 = analyze_portfolio([tr_s442])
    res_s442["strategy_id"] = "S442"
    res_s442["name"] = "M1 Supertrend + Mild Vol Threshold ($0.80)"
    results.append(res_s442)
    print(f"    S442 Result ({time.time()-t0:.1f}s): Net=${res_s442['net_profit']:,.2f} | PF={res_s442['pf']:.3f} | DD=${res_s442['max_dd']:,.2f} | RoMaD={res_s442['romad']:.2f}x | Tr/Yr={res_s442['annual_trades']:.1f}")

    # S443: M1 Supertrend + Moderate Volatility Threshold (ATR >= $1.20)
    print("\n[+] Simulating S443: M1 Supertrend + Moderate Vol Threshold (ATR >= $1.20)...")
    t0 = time.time()
    tr_s443 = run_fast_m1_scalper(
        m1_opens, m1_highs, m1_lows, m1_closes, m1_py_dates, m1_hours, m1_years, m1_months,
        m1_atr, m1_trend, m1_st_band, m15_macro_trend,
        min_m1_atr=1.20, session_mode="skip_rollover", use_macro_filter=True, use_m1_ratchet=True
    )
    res_s443 = analyze_portfolio([tr_s443])
    res_s443["strategy_id"] = "S443"
    res_s443["name"] = "M1 Supertrend + Moderate Vol Threshold ($1.20)"
    results.append(res_s443)
    print(f"    S443 Result ({time.time()-t0:.1f}s): Net=${res_s443['net_profit']:,.2f} | PF={res_s443['pf']:.3f} | DD=${res_s443['max_dd']:,.2f} | RoMaD={res_s443['romad']:.2f}x | Tr/Yr={res_s443['annual_trades']:.1f}")

    # S444: M1 Supertrend + High Volatility Expansion Threshold (ATR >= $1.60)
    print("\n[+] Simulating S444: M1 Supertrend + High Vol Threshold (ATR >= $1.60)...")
    t0 = time.time()
    tr_s444 = run_fast_m1_scalper(
        m1_opens, m1_highs, m1_lows, m1_closes, m1_py_dates, m1_hours, m1_years, m1_months,
        m1_atr, m1_trend, m1_st_band, m15_macro_trend,
        min_m1_atr=1.60, session_mode="skip_rollover", use_macro_filter=True, use_m1_ratchet=True
    )
    res_s444 = analyze_portfolio([tr_s444])
    res_s444["strategy_id"] = "S444"
    res_s444["name"] = "M1 Supertrend + High Vol Threshold ($1.60)"
    results.append(res_s444)
    print(f"    S444 Result ({time.time()-t0:.1f}s): Net=${res_s444['net_profit']:,.2f} | PF={res_s444['pf']:.3f} | DD=${res_s444['max_dd']:,.2f} | RoMaD={res_s444['romad']:.2f}x | Tr/Yr={res_s444['annual_trades']:.1f}")

    # S445: M1 NY Session Scalper (12:00-17:00 UTC Active Only)
    print("\n[+] Simulating S445: M1 NY Session Scalper (12:00-17:00 UTC)...")
    t0 = time.time()
    tr_s445 = run_fast_m1_scalper(
        m1_opens, m1_highs, m1_lows, m1_closes, m1_py_dates, m1_hours, m1_years, m1_months,
        m1_atr, m1_trend, m1_st_band, m15_macro_trend,
        min_m1_atr=0.0, session_mode="ny_only", use_macro_filter=True, use_m1_ratchet=True
    )
    res_s445 = analyze_portfolio([tr_s445])
    res_s445["strategy_id"] = "S445"
    res_s445["name"] = "M1 NY Session Scalper"
    results.append(res_s445)
    print(f"    S445 Result ({time.time()-t0:.1f}s): Net=${res_s445['net_profit']:,.2f} | PF={res_s445['pf']:.3f} | DD=${res_s445['max_dd']:,.2f} | RoMaD={res_s445['romad']:.2f}x | Tr/Yr={res_s445['annual_trades']:.1f}")

    # S446: M1 NY Session + Volatility Filter (ATR >= $1.00 in NY)
    print("\n[+] Simulating S446: M1 NY Session + Volatility Filter (ATR >= $1.00)...")
    t0 = time.time()
    tr_s446 = run_fast_m1_scalper(
        m1_opens, m1_highs, m1_lows, m1_closes, m1_py_dates, m1_hours, m1_years, m1_months,
        m1_atr, m1_trend, m1_st_band, m15_macro_trend,
        min_m1_atr=1.00, session_mode="ny_only", use_macro_filter=True, use_m1_ratchet=True
    )
    res_s446 = analyze_portfolio([tr_s446])
    res_s446["strategy_id"] = "S446"
    res_s446["name"] = "M1 NY Session + Volatility Filter ($1.00)"
    results.append(res_s446)
    print(f"    S446 Result ({time.time()-t0:.1f}s): Net=${res_s446['net_profit']:,.2f} | PF={res_s446['pf']:.3f} | DD=${res_s446['max_dd']:,.2f} | RoMaD={res_s446['romad']:.2f}x | Tr/Yr={res_s446['annual_trades']:.1f}")

    # S447: M1 NY Session + High Volatility Filter (ATR >= $1.40 in NY)
    print("\n[+] Simulating S447: M1 NY Session + High Vol Filter (ATR >= $1.40)...")
    t0 = time.time()
    tr_s447 = run_fast_m1_scalper(
        m1_opens, m1_highs, m1_lows, m1_closes, m1_py_dates, m1_hours, m1_years, m1_months,
        m1_atr, m1_trend, m1_st_band, m15_macro_trend,
        min_m1_atr=1.40, session_mode="ny_only", use_macro_filter=True, use_m1_ratchet=True
    )
    res_s447 = analyze_portfolio([tr_s447])
    res_s447["strategy_id"] = "S447"
    res_s447["name"] = "M1 NY Session + High Vol Filter ($1.40)"
    results.append(res_s447)
    print(f"    S447 Result ({time.time()-t0:.1f}s): Net=${res_s447['net_profit']:,.2f} | PF={res_s447['pf']:.3f} | DD=${res_s447['max_dd']:,.2f} | RoMaD={res_s447['romad']:.2f}x | Tr/Yr={res_s447['annual_trades']:.1f}")

    # S448: Dual-Timeframe M15 Core + M1 NY Sniper
    print("\n[+] Simulating S448: Dual-Timeframe M15 Core + M1 NY Sniper...")
    res_s448 = analyze_portfolio([tr_m15_core, tr_s446])
    res_s448["strategy_id"] = "S448"
    res_s448["name"] = "Dual-Timeframe M15 Core + M1 NY Sniper"
    results.append(res_s448)
    print(f"    S448 Result: Net=${res_s448['net_profit']:,.2f} | PF={res_s448['pf']:.3f} | DD=${res_s448['max_dd']:,.2f} | RoMaD={res_s448['romad']:.2f}x | Tr/Yr={res_s448['annual_trades']:.1f}")

    # S449: Dual-Timeframe M15 Core + M1 High-Vol Sniper (S447)
    print("\n[+] Simulating S449: Dual-Timeframe M15 Core + M1 High-Vol Sniper...")
    res_s449 = analyze_portfolio([tr_m15_core, tr_s447])
    res_s449["strategy_id"] = "S449"
    res_s449["name"] = "Dual-Timeframe M15 Core + M1 High-Vol Sniper"
    results.append(res_s449)
    print(f"    S449 Result: Net=${res_s449['net_profit']:,.2f} | PF={res_s449['pf']:.3f} | DD=${res_s449['max_dd']:,.2f} | RoMaD={res_s449['romad']:.2f}x | Tr/Yr={res_s449['annual_trades']:.1f}")

    # S450: Triple-Timeframe Centennial Master Suite (M15 Core + M5 Ratchet + M1 NY Sniper)
    print("\n[+] Simulating S450: Triple-Timeframe Centennial Master Suite...")
    res_s450 = analyze_portfolio([tr_m15_core, tr_m5_ratchet, tr_s446])
    res_s450["strategy_id"] = "S450"
    res_s450["name"] = "Triple-Timeframe Centennial Master Suite (M15+M5+M1)"
    results.append(res_s450)
    print(f"    S450 Result: Net=${res_s450['net_profit']:,.2f} | PF={res_s450['pf']:.3f} | DD=${res_s450['max_dd']:,.2f} | RoMaD={res_s450['romad']:.2f}x | Tr/Yr={res_s450['annual_trades']:.1f}")

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
    csv_path = os.path.join(RESULTS_DIR, "scalping_m1_microstructure_batch_441_450_matrix.csv")
    df_matrix.to_csv(csv_path, index=False)
    print(f"\n[+] Saved Matrix CSV to: {csv_path}")

    clean_results = []
    for r in results:
        rc = {k: v for k, v in r.items() if k != "trades"}
        clean_results.append(rc)

    json_path = os.path.join(RESULTS_DIR, "scalping_m1_microstructure_batch_441_450_results.json")
    with open(json_path, "w") as f:
        json.dump(clean_results, f, indent=2)
    print(f"[+] Saved Results JSON to: {json_path}")

    print("\n" + "=" * 80)
    print(f"BATCH 25 EXECUTION COMPLETE in {time.time() - start_total_time:.2f} seconds")
    print("=" * 80)
    print(df_matrix.to_string(index=False))

    gc.collect()

if __name__ == "__main__":
    main()
