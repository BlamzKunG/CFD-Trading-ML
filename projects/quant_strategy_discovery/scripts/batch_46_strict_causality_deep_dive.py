#!/usr/bin/env python3
"""
===============================================================================
BATCH 46: STRICT CAUSALITY & HIGH-EXPECTANCY M15 STRATEGY OPTIMIZATION
===============================================================================
100% Anti-Lookahead Causality Verification:
- When using H1 data on M15 bars, H1 state timestamp MUST be shifted by +1 Hour:
  H1 bar at T closes at T + 1 Hour. Therefore, its state is only accessible at T + 1H.
- When using M15 on M5 bars, M15 state is shifted by +15 Minutes.
- All rules D.1 to D.7 enforced 100%.

Research Focus:
We take our top genuine M15 performers:
1. S651: M15 EURUSD Macro Gated ST (3.0, 14) - The S644 Baseline (PF 1.069, +$3,652)
2. S652: M15 EURUSD Macro Gated ST (3.5, 14) - Wider trend bands to cut whipsaw
3. S653: M15 EURUSD Macro Gated ST (4.0, 14) - Ultra-wide trend bands (S648 tuned)
4. S654: M15 EURUSD Macro Gated ST (3.0, 20) - Slower ATR period for smoother trailing
5. S655: H1 Macro ST (3.0, 14) with STRICT +1 Hour Shift (Zero Lookahead)
6. S656: H1 Macro ST (2.5, 14) with STRICT +1 Hour Shift
7. S657: H1 Macro ST (3.5, 14) with STRICT +1 Hour Shift
8. S658: M15 Dual-Confirmation ST (M15 ST 3.0 + Strict H1 ST 3.0 Alignment)
9. S659: Composite Dual-Timeframe Portfolio (S652 M15 + S655 Strict H1)
10. S660: Sovereign High-Expectancy Production Engine with $200 Daily Circuit Breaker
===============================================================================
"""

import os
import sys
import time
import json
import gc
import numpy as np
import pandas as pd
from datetime import datetime

REPO_ROOT = "/root/CFD-Trading-ML"
DATA_DIR = os.path.join(REPO_ROOT, "projects/quant_strategy_discovery/data")
RESULTS_DIR = os.path.join(REPO_ROOT, "projects/quant_strategy_discovery/results")
DOCS_DIR = os.path.join(REPO_ROOT, "projects/quant_strategy_discovery/docs")
os.makedirs(RESULTS_DIR, exist_ok=True)
os.makedirs(DOCS_DIR, exist_ok=True)

# -----------------------------------------------------------------------------
# Indicator Computations
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
# Discrete Simulator (Constitution Rules D.1 to D.7)
# -----------------------------------------------------------------------------
def simulate_discrete_engine(
    opens, highs, lows, closes, dates,
    entry_signals,
    atr_values,
    st_bands,
    engine_name="Engine",
    lot_size=0.10,
    spread=0.25,
    commission_per_lot=6.00,
    sl_slippage=0.10,
    swap_long_daily=18.00,
    initial_sl_atr_mult=3.0
):
    n = len(closes)
    trades = []
    unit_size = lot_size * 100.0
    comm_total = (commission_per_lot / 100.0) * unit_size

    pos = 0
    entry_price = 0.0
    entry_time = None
    entry_idx = 0
    current_sl = 0.0
    deepest_dip = 0.0

    for i in range(200, n - 2):
        if pos == 1: # Long
            bar_low = lows[i]
            dip = min(0.0, (bar_low - entry_price) * unit_size)
            if dip < deepest_dip:
                deepest_dip = dip

            exit_hit = False
            exit_price = 0.0
            exit_reason = ""

            sl_touched = (bar_low <= current_sl)
            if sl_touched:
                exit_hit = True
                exit_price = current_sl - sl_slippage
                exit_reason = "SL"

            # Trend flip check at bar close
            if not exit_hit and closes[i] < st_bands[i]:
                exit_hit = True
                exit_price = opens[i + 1] - (spread * 0.5)
                exit_reason = "TrendFlip"

            if exit_hit:
                days_held = (dates[i].date() - entry_time.date()).days
                swap_cost = max(0, days_held) * (swap_long_daily / 100.0) * unit_size
                net_pnl = (exit_price - entry_price) * unit_size - (spread * unit_size) - comm_total - swap_cost

                trades.append({
                    "engine": engine_name,
                    "pos": 1,
                    "entry_time": entry_time,
                    "exit_time": dates[i],
                    "entry_price": entry_price,
                    "exit_price": exit_price,
                    "pnl": net_pnl,
                    "deepest_dip": deepest_dip,
                    "year": entry_time.year,
                    "month": f"{entry_time.year}-{entry_time.month:02d}",
                    "exit_reason": exit_reason
                })
                pos = 0
            else:
                # Rule D.2: Bar-close trailing ratchet (Effective next bar Open)
                if st_bands[i] > current_sl:
                    current_sl = st_bands[i]

        elif pos == -1: # Short
            bar_high = highs[i]
            dip = min(0.0, (entry_price - bar_high) * unit_size)
            if dip < deepest_dip:
                deepest_dip = dip

            exit_hit = False
            exit_price = 0.0
            exit_reason = ""

            sl_touched = (bar_high >= current_sl)
            if sl_touched:
                exit_hit = True
                exit_price = current_sl + sl_slippage
                exit_reason = "SL"

            if not exit_hit and closes[i] > st_bands[i]:
                exit_hit = True
                exit_price = opens[i + 1] + (spread * 0.5)
                exit_reason = "TrendFlip"

            if exit_hit:
                net_pnl = (entry_price - exit_price) * unit_size - (spread * unit_size) - comm_total
                trades.append({
                    "engine": engine_name,
                    "pos": -1,
                    "entry_time": entry_time,
                    "exit_time": dates[i],
                    "entry_price": entry_price,
                    "exit_price": exit_price,
                    "pnl": net_pnl,
                    "deepest_dip": deepest_dip,
                    "year": entry_time.year,
                    "month": f"{entry_time.year}-{entry_time.month:02d}",
                    "exit_reason": exit_reason
                })
                pos = 0
            else:
                if st_bands[i] < current_sl:
                    current_sl = st_bands[i]

        # Check entries at bar i Close -> Execute at i+1 Open
        if pos == 0 and entry_signals[i] != 0:
            pos = entry_signals[i]
            entry_idx = i + 1
            entry_time = dates[i + 1]
            deepest_dip = 0.0

            if pos == 1:
                entry_price = opens[i + 1] + (spread * 0.5)
                current_sl = entry_price - (initial_sl_atr_mult * atr_values[i])
            else:
                entry_price = opens[i + 1] - (spread * 0.5)
                current_sl = entry_price + (initial_sl_atr_mult * atr_values[i])

    return trades

# -----------------------------------------------------------------------------
# Analysis Function
# -----------------------------------------------------------------------------
def analyze_trades(all_trades, max_daily_loss=0.0):
    if not all_trades:
        return {"net_profit": 0, "pf": 0, "total_trades": 0, "annual_trades": 0, "max_dd": 1.0, "romad": 0, "win_rate": 0, "mcr": 0, "avg_profit_per_trade": 0}

    all_trades = sorted(all_trades, key=lambda x: x["entry_time"])
    filtered_trades = []
    daily_pnl = {}

    for t in all_trades:
        day_key = t["entry_time"].strftime("%Y-%m-%d")
        day_curr = daily_pnl.get(day_key, 0.0)

        if max_daily_loss > 0 and day_curr <= -max_daily_loss:
            continue

        pnl = t["pnl"]
        daily_pnl[day_key] = day_curr + pnl
        filtered_trades.append(t)

    if not filtered_trades:
        return {"net_profit": 0, "pf": 0, "total_trades": 0, "annual_trades": 0, "max_dd": 1.0, "romad": 0, "win_rate": 0, "mcr": 0, "avg_profit_per_trade": 0}

    cum_equity = 0.0
    peak_equity = 0.0
    max_intra_dd = 0.0
    pnls = []
    m_dict = {}

    for t in filtered_trades:
        pnl = t["pnl"]
        dip = t["deepest_dip"]

        intra_dip = cum_equity + dip
        intra_dd = peak_equity - intra_dip
        if intra_dd > max_intra_dd:
            max_intra_dd = intra_dd

        cum_equity += pnl
        if cum_equity > peak_equity:
            peak_equity = cum_equity

        closed_dd = peak_equity - cum_equity
        if closed_dd > max_intra_dd:
            max_intra_dd = closed_dd

        pnls.append(pnl)
        m = t["month"]
        m_dict[m] = m_dict.get(m, 0.0) + pnl

    total_net = cum_equity
    wins = [p for p in pnls if p > 0]
    losses = [abs(p) for p in pnls if p < 0]
    tot_win = sum(wins)
    tot_loss = sum(losses)

    pf = tot_win / tot_loss if tot_loss > 0 else (99.0 if tot_win > 0 else 0.0)
    wr = (len(wins) / len(pnls)) * 100.0 if len(pnls) > 0 else 0.0
    max_dd = max_intra_dd if max_intra_dd > 0 else 1.0
    romad = total_net / max_dd if max_dd > 0 else 0.0
    ann_tr = len(filtered_trades) / 6.0
    avg_trade = total_net / len(filtered_trades) if len(filtered_trades) > 0 else 0.0

    pos_m = sum(1 for v in m_dict.values() if v > 0)
    mcr = (pos_m / 72.0) * 100.0

    return {
        "net_profit": total_net,
        "pf": pf,
        "total_trades": len(filtered_trades),
        "annual_trades": ann_tr,
        "max_dd": max_dd,
        "romad": romad,
        "win_rate": wr,
        "mcr": mcr,
        "avg_profit_per_trade": avg_trade
    }

# -----------------------------------------------------------------------------
# Main Execution
# -----------------------------------------------------------------------------
def main():
    t_start = time.time()
    print("=" * 80)
    print("STARTING BATCH 46: STRICT CAUSALITY & HIGH-EXPECTANCY DISCOVERY (S651 - S660)")
    print("Zero Lookahead Guarantee (+1H Shift on H1 Bars) | Rules D.1 - D.7 Compliant")
    print("=" * 80)

    # 1. Load M15 Gold Data
    print("[*] Loading XAUUSD M15 Data...")
    df_m15 = pd.read_parquet(os.path.join(DATA_DIR, "XAUUSD_M15.parquet"))
    m15_highs = df_m15["high"].values.astype(np.float64)
    m15_lows = df_m15["low"].values.astype(np.float64)
    m15_closes = df_m15["close"].values.astype(np.float64)
    m15_opens = df_m15["open"].values.astype(np.float64)
    m15_dates = pd.to_datetime(df_m15.index).to_pydatetime()
    n_m15 = len(m15_closes)

    m15_atr_14 = compute_atr(m15_highs, m15_lows, m15_closes, 14)
    m15_atr_20 = compute_atr(m15_highs, m15_lows, m15_closes, 20)
    m15_ema200 = compute_ema(m15_closes, 200)

    # Supertrend variations
    m15_tr_30_14, m15_st_30_14 = compute_supertrend(m15_highs, m15_lows, m15_closes, m15_atr_14, 3.0)
    m15_tr_35_14, m15_st_35_14 = compute_supertrend(m15_highs, m15_lows, m15_closes, m15_atr_14, 3.5)
    m15_tr_40_14, m15_st_40_14 = compute_supertrend(m15_highs, m15_lows, m15_closes, m15_atr_14, 4.0)
    m15_tr_30_20, m15_st_30_20 = compute_supertrend(m15_highs, m15_lows, m15_closes, m15_atr_20, 3.0)

    # 2. Load EURUSD M15 Data (Synchronous timestamps)
    print("[*] Loading EURUSD M15 Data...")
    df_eu = pd.read_parquet(os.path.join(DATA_DIR, "EURUSD_M15.parquet"))
    eu_closes = df_eu["close"].values.astype(np.float64)
    eu_ema50 = compute_ema(eu_closes, 50)
    eu_trend = np.where(eu_closes > eu_ema50, 1, -1)
    df_eu_state = pd.DataFrame({"time": pd.to_datetime(df_eu.index), "eu_trend": eu_trend}).sort_values("time")

    df_m15_time = pd.DataFrame({"time": pd.to_datetime(df_m15.index)})
    m15_merged_eu = pd.merge_asof(df_m15_time, df_eu_state, on="time", direction="backward")
    m15_eu_trend = m15_merged_eu["eu_trend"].fillna(1).values.astype(np.int32)
    del df_eu, df_eu_state, m15_merged_eu
    gc.collect()

    # 3. Load H1 Gold Data with STRICT +1 HOUR SHIFT (Zero Lookahead)
    print("[*] Loading XAUUSD H1 Data (Applying Strict +1 Hour Shift for Causality)...")
    df_h1 = pd.read_parquet(os.path.join(DATA_DIR, "XAUUSD_H1.parquet"))
    h1_highs = df_h1["high"].values.astype(np.float64)
    h1_lows = df_h1["low"].values.astype(np.float64)
    h1_closes = df_h1["close"].values.astype(np.float64)
    h1_atr_14 = compute_atr(h1_highs, h1_lows, h1_closes, 14)
    h1_ema200 = compute_ema(h1_closes, 200)

    h1_tr_30, h1_st_30 = compute_supertrend(h1_highs, h1_lows, h1_closes, h1_atr_14, 3.0)
    h1_tr_25, h1_st_25 = compute_supertrend(h1_highs, h1_lows, h1_closes, h1_atr_14, 2.5)
    h1_tr_35, h1_st_35 = compute_supertrend(h1_highs, h1_lows, h1_closes, h1_atr_14, 3.5)

    # CRITICAL: An H1 bar opening at T is only closed and finalized at T + 1 Hour!
    # Therefore, its state can only be merged into M15 at or after T + 1 Hour!
    h1_closed_time = pd.to_datetime(df_h1.index) + pd.Timedelta(hours=1)
    df_h1_state = pd.DataFrame({
        "time": h1_closed_time,
        "h1_tr_30": h1_tr_30,
        "h1_st_30": h1_st_30,
        "h1_tr_25": h1_tr_25,
        "h1_st_25": h1_st_25,
        "h1_tr_35": h1_tr_35,
        "h1_st_35": h1_st_35,
        "h1_ema200": h1_ema200
    }).sort_values("time")

    m15_merged_h1 = pd.merge_asof(df_m15_time, df_h1_state, on="time", direction="backward")
    m15_h1_tr_30 = m15_merged_h1["h1_tr_30"].fillna(1).values.astype(np.int32)
    m15_h1_st_30 = m15_merged_h1["h1_st_30"].bfill().values.astype(np.float64)
    m15_h1_tr_25 = m15_merged_h1["h1_tr_25"].fillna(1).values.astype(np.int32)
    m15_h1_st_25 = m15_merged_h1["h1_st_25"].bfill().values.astype(np.float64)
    m15_h1_tr_35 = m15_merged_h1["h1_tr_35"].fillna(1).values.astype(np.int32)
    m15_h1_st_35 = m15_merged_h1["h1_st_35"].bfill().values.astype(np.float64)
    m15_h1_ema200 = m15_merged_h1["h1_ema200"].bfill().values.astype(np.float64)
    del df_h1, df_h1_state, m15_merged_h1, df_m15_time
    gc.collect()

    # =========================================================================
    # Strategy Signal Generation
    # =========================================================================
    print("\n[+] Generating Signals for Batch 46...")

    # S651: M15 EURUSD Macro Gated ST (3.0, 14) [Baseline]
    sig_s651 = np.zeros(n_m15, dtype=np.int32)
    for i in range(200, n_m15 - 1):
        if not (21 <= m15_dates[i].hour < 23):
            if m15_tr_30_14[i] == 1 and m15_tr_30_14[i - 1] == -1 and m15_closes[i] > m15_ema200[i] and m15_eu_trend[i] == 1:
                sig_s651[i] = 1
            elif m15_tr_30_14[i] == -1 and m15_tr_30_14[i - 1] == 1 and m15_closes[i] < m15_ema200[i] and m15_eu_trend[i] == -1:
                sig_s651[i] = -1

    # S652: M15 EURUSD Macro Gated ST (3.5, 14)
    sig_s652 = np.zeros(n_m15, dtype=np.int32)
    for i in range(200, n_m15 - 1):
        if not (21 <= m15_dates[i].hour < 23):
            if m15_tr_35_14[i] == 1 and m15_tr_35_14[i - 1] == -1 and m15_closes[i] > m15_ema200[i] and m15_eu_trend[i] == 1:
                sig_s652[i] = 1
            elif m15_tr_35_14[i] == -1 and m15_tr_35_14[i - 1] == 1 and m15_closes[i] < m15_ema200[i] and m15_eu_trend[i] == -1:
                sig_s652[i] = -1

    # S653: M15 EURUSD Macro Gated ST (4.0, 14)
    sig_s653 = np.zeros(n_m15, dtype=np.int32)
    for i in range(200, n_m15 - 1):
        if not (21 <= m15_dates[i].hour < 23):
            if m15_tr_40_14[i] == 1 and m15_tr_40_14[i - 1] == -1 and m15_closes[i] > m15_ema200[i] and m15_eu_trend[i] == 1:
                sig_s653[i] = 1
            elif m15_tr_40_14[i] == -1 and m15_tr_40_14[i - 1] == 1 and m15_closes[i] < m15_ema200[i] and m15_eu_trend[i] == -1:
                sig_s653[i] = -1

    # S654: M15 EURUSD Macro Gated ST (3.0, 20)
    sig_s654 = np.zeros(n_m15, dtype=np.int32)
    for i in range(200, n_m15 - 1):
        if not (21 <= m15_dates[i].hour < 23):
            if m15_tr_30_20[i] == 1 and m15_tr_30_20[i - 1] == -1 and m15_closes[i] > m15_ema200[i] and m15_eu_trend[i] == 1:
                sig_s654[i] = 1
            elif m15_tr_30_20[i] == -1 and m15_tr_30_20[i - 1] == 1 and m15_closes[i] < m15_ema200[i] and m15_eu_trend[i] == -1:
                sig_s654[i] = -1

    # S655: H1 Macro ST (3.0, 14) with STRICT Zero-Lookahead Shift
    sig_s655 = np.zeros(n_m15, dtype=np.int32)
    for i in range(200, n_m15 - 1):
        if not (21 <= m15_dates[i].hour < 23):
            if m15_h1_tr_30[i] == 1 and m15_h1_tr_30[i - 1] == -1 and m15_closes[i] > m15_h1_ema200[i]:
                sig_s655[i] = 1
            elif m15_h1_tr_30[i] == -1 and m15_h1_tr_30[i - 1] == 1 and m15_closes[i] < m15_h1_ema200[i]:
                sig_s655[i] = -1

    # S656: H1 Macro ST (2.5, 14) with STRICT Zero-Lookahead Shift
    sig_s656 = np.zeros(n_m15, dtype=np.int32)
    for i in range(200, n_m15 - 1):
        if not (21 <= m15_dates[i].hour < 23):
            if m15_h1_tr_25[i] == 1 and m15_h1_tr_25[i - 1] == -1 and m15_closes[i] > m15_h1_ema200[i]:
                sig_s656[i] = 1
            elif m15_h1_tr_25[i] == -1 and m15_h1_tr_25[i - 1] == 1 and m15_closes[i] < m15_h1_ema200[i]:
                sig_s656[i] = -1

    # S657: H1 Macro ST (3.5, 14) with STRICT Zero-Lookahead Shift
    sig_s657 = np.zeros(n_m15, dtype=np.int32)
    for i in range(200, n_m15 - 1):
        if not (21 <= m15_dates[i].hour < 23):
            if m15_h1_tr_35[i] == 1 and m15_h1_tr_35[i - 1] == -1 and m15_closes[i] > m15_h1_ema200[i]:
                sig_s657[i] = 1
            elif m15_h1_tr_35[i] == -1 and m15_h1_tr_35[i - 1] == 1 and m15_closes[i] < m15_h1_ema200[i]:
                sig_s657[i] = -1

    # S658: M15 Dual-Confirmation ST (M15 ST 3.0 trigger + H1 ST 3.0 alignment + EURUSD alignment)
    sig_s658 = np.zeros(n_m15, dtype=np.int32)
    for i in range(200, n_m15 - 1):
        if not (21 <= m15_dates[i].hour < 23):
            if m15_tr_30_14[i] == 1 and m15_tr_30_14[i - 1] == -1 and m15_closes[i] > m15_ema200[i]:
                if m15_h1_tr_30[i] == 1 and m15_eu_trend[i] == 1:
                    sig_s658[i] = 1
            elif m15_tr_30_14[i] == -1 and m15_tr_30_14[i - 1] == 1 and m15_closes[i] < m15_ema200[i]:
                if m15_h1_tr_30[i] == -1 and m15_eu_trend[i] == -1:
                    sig_s658[i] = -1

    # =========================================================================
    # Run Discrete Event Simulations (Rules D.1 - D.7)
    # =========================================================================
    print("\n[+] Running Discrete Event Simulators (Rules D.1 - D.7)...")

    tr_s651 = simulate_discrete_engine(m15_opens, m15_highs, m15_lows, m15_closes, m15_dates, sig_s651, m15_atr_14, m15_st_30_14, engine_name="S651_M15_ST_3.0_14")
    tr_s652 = simulate_discrete_engine(m15_opens, m15_highs, m15_lows, m15_closes, m15_dates, sig_s652, m15_atr_14, m15_st_35_14, engine_name="S652_M15_ST_3.5_14")
    tr_s653 = simulate_discrete_engine(m15_opens, m15_highs, m15_lows, m15_closes, m15_dates, sig_s653, m15_atr_14, m15_st_40_14, engine_name="S653_M15_ST_4.0_14")
    tr_s654 = simulate_discrete_engine(m15_opens, m15_highs, m15_lows, m15_closes, m15_dates, sig_s654, m15_atr_20, m15_st_30_20, engine_name="S654_M15_ST_3.0_20")

    tr_s655 = simulate_discrete_engine(m15_opens, m15_highs, m15_lows, m15_closes, m15_dates, sig_s655, m15_atr_14, m15_h1_st_30, engine_name="S655_Strict_H1_3.0")
    tr_s656 = simulate_discrete_engine(m15_opens, m15_highs, m15_lows, m15_closes, m15_dates, sig_s656, m15_atr_14, m15_h1_st_25, engine_name="S656_Strict_H1_2.5")
    tr_s657 = simulate_discrete_engine(m15_opens, m15_highs, m15_lows, m15_closes, m15_dates, sig_s657, m15_atr_14, m15_h1_st_35, engine_name="S657_Strict_H1_3.5")

    tr_s658 = simulate_discrete_engine(m15_opens, m15_highs, m15_lows, m15_closes, m15_dates, sig_s658, m15_atr_14, m15_st_30_14, engine_name="S658_Dual_Confirm")

    # S659: Composite Dual-Timeframe Portfolio (S652 M15 + S655 Strict H1)
    tr_s659 = tr_s652 + tr_s655

    # S660: Sovereign High-Expectancy Production Engine with $200 Daily Circuit Breaker
    tr_s660 = tr_s659

    # =========================================================================
    # Strategy Results Compilation
    # =========================================================================
    strategies_raw = [
        ("S651", "M15 EURUSD Gated ST (3.0,14)", "M15 ST (3.0,14) + EURUSD Macro Gate", tr_s651, 0.0),
        ("S652", "M15 EURUSD Gated ST (3.5,14)", "M15 ST (3.5,14) + EURUSD Macro Gate", tr_s652, 0.0),
        ("S653", "M15 EURUSD Gated ST (4.0,14)", "M15 ST (4.0,14) + EURUSD Macro Gate", tr_s653, 0.0),
        ("S654", "M15 EURUSD Gated ST (3.0,20)", "M15 ST (3.0,20) + EURUSD Macro Gate", tr_s654, 0.0),
        ("S655", "Strict H1 Macro ST (3.0,14)", "Strict +1H Causal H1 ST (3.0,14) on M15", tr_s655, 0.0),
        ("S656", "Strict H1 Macro ST (2.5,14)", "Strict +1H Causal H1 ST (2.5,14) on M15", tr_s656, 0.0),
        ("S657", "Strict H1 Macro ST (3.5,14)", "Strict +1H Causal H1 ST (3.5,14) on M15", tr_s657, 0.0),
        ("S658", "M15 Triangulated Alignment", "M15 Trigger + H1 Trend + EURUSD Gate", tr_s658, 0.0),
        ("S659", "Causal Dual-Timeframe Ensemble", "S652 M15 + S655 Strict H1 Portfolio", tr_s659, 0.0),
        ("S660", "Sovereign High-Expectancy Master", "S659 Ensemble + $200 Daily Circuit Breaker", tr_s660, 200.0)
    ]

    results_table = []
    print("\n" + "=" * 120)
    print(f"{'ID':<6} {'Strategy Name':<32} {'Architecture':<35} {'Ann.Tr':<8} {'Tot.Tr':<8} {'Net PnL ($)':<14} {'PF':<8} {'WR%':<8} {'Intra DD ($)':<14} {'RoMaD':<8} {'MCR%':<8}")
    print("=" * 120)

    for sid, name, arch, tr_list, gov in strategies_raw:
        m = analyze_trades(tr_list, max_daily_loss=gov)
        row = {
            "Strategy_ID": sid,
            "Strategy_Name": name,
            "Architecture": arch,
            "Annual_Trades": m["annual_trades"],
            "Total_Trades": m["total_trades"],
            "Net_Profit": m["net_profit"],
            "Profit_Factor": m["pf"],
            "Win_Rate_Pct": m["win_rate"],
            "True_Intra_Max_DD": m["max_dd"],
            "RoMaD": m["romad"],
            "Monthly_Consistency_Pct": m["mcr"],
            "Avg_Profit_Per_Trade": m["avg_profit_per_trade"]
        }
        results_table.append(row)
        print(f"{sid:<6} {name:<32} {arch:<35} {m['annual_trades']:<8.1f} {m['total_trades']:<8} {m['net_profit']:<14.2f} {m['pf']:<8.3f} {m['win_rate']:<8.1f} {m['max_dd']:<14.2f} {m['romad']:<8.2f} {m['mcr']:<8.1f}")

    print("=" * 120)

    # Save Results JSON & CSV
    json_path = os.path.join(RESULTS_DIR, "batch_46_strict_causality_discovery.json")
    csv_path = os.path.join(RESULTS_DIR, "batch_46_strict_causality_discovery.csv")
    with open(json_path, "w") as f:
        json.dump(results_table, f, indent=2)
    pd.DataFrame(results_table).to_csv(csv_path, index=False)
    print(f"\n[+] Results saved to:\n    - {json_path}\n    - {csv_path}")

    # Check Profitable Models
    profitable = [r for r in results_table if r["Net_Profit"] > 0]
    if profitable:
        best_strat = max(profitable, key=lambda x: x["Net_Profit"])
        print(f"\n🏆 BATCH 46 CHAMPION: {best_strat['Strategy_ID']} - {best_strat['Strategy_Name']}")
        print(f"   Net Profit: ${best_strat['Net_Profit']:,.2f} | PF: {best_strat['Profit_Factor']:.3f} | Trades/Yr: {best_strat['Annual_Trades']:.1f} | Avg Win/Trade: ${best_strat['Avg_Profit_Per_Trade']:.2f}")
    else:
        print("\n⚠️ No strategy achieved Net Profit > 0.")

    print(f"\nBatch 46 completed in {time.time()-t_start:.2f} seconds.")

if __name__ == "__main__":
    main()
