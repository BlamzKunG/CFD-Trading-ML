#!/usr/bin/env python3
"""
===============================================================================
BATCH 47: APEX TRIANGULATED HIGH-EXPECTANCY PRODUCTION ENGINES (S661 - S670)
===============================================================================
Constitution V5.1 Fully Compliant 100%:
- 100% Anti-Lookahead Causality (H1 bar shifted +1H to reflect bar close)
- Rule D.1: Pessimistic Sequence Mandate (SL hit first if both TP & SL touched)
- Rule D.2: Strict Bar-Close Trailing Mandate (effective at next bar Open)
- Rule D.3: Intra-Bar Equity Tracking Mandate (Max DD includes intra-bar adverse dip)
- Rule D.4: Negative Slippage on Stop Loss (-$0.10/trade on SL fills)
- Rule D.5: 100% Bar-by-Bar Discrete Event Simulation (Zero Synthetic Multipliers)
- Rule D.6: Lot Step Realism & Tranche Limit (0.10 lot, 50/50 staged tranches)
- Rule D.7: Realistic Institutional Frictions ($0.25 spread + $6.00 comm + -$18/lot swap)

Research Focus:
Refining the proven champion architecture from Batch 46:
- M15 Supertrend + Strict H1 Supertrend + EURUSD Macro Triangulation (S658)
- Integrating Session Gating (London/NY Open: 07-17 UTC)
- Volatility Thresholds (ATR filtering)
- 50/50 Staged Scale-out with Bar-Close Breakeven Ratchet
- Daily Loss Risk Governors ($150 - $200)
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
# Discrete Event Simulator (Full Rules D.1 to D.7)
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
    initial_sl_atr_mult=3.0,
    use_staged_50_50=False,
    tp1_atr_mult=2.5
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
    current_tp1 = 0.0
    tp1_hit = False
    deepest_dip = 0.0

    for i in range(200, n - 2):
        if pos == 1: # Long
            bar_low = lows[i]
            bar_high = highs[i]
            dip = min(0.0, (bar_low - entry_price) * unit_size)
            if dip < deepest_dip:
                deepest_dip = dip

            exit_hit = False
            exit_price = 0.0
            exit_reason = ""

            sl_touched = (bar_low <= current_sl)
            tp_touched = (bar_high >= current_tp1) if (use_staged_50_50 and not tp1_hit) else False

            # Rule D.1: Pessimistic Sequence Mandate
            if sl_touched and tp_touched:
                exit_hit = True
                exit_price = current_sl - sl_slippage
                exit_reason = "SL_Pessimistic"
            elif sl_touched:
                exit_hit = True
                exit_price = current_sl - sl_slippage
                exit_reason = "SL"
            elif tp_touched:
                tp1_hit = True

            if not exit_hit and closes[i] < st_bands[i]:
                exit_hit = True
                exit_price = opens[i + 1] - (spread * 0.5)
                exit_reason = "TrendFlip"

            if exit_hit:
                days_held = (dates[i].date() - entry_time.date()).days
                swap_cost = max(0, days_held) * (swap_long_daily / 100.0) * unit_size

                if use_staged_50_50 and tp1_hit and exit_reason != "SL_Pessimistic":
                    pnl_leg1 = ((entry_price + tp1_atr_mult * atr_values[entry_idx - 1]) - entry_price) * (unit_size * 0.5) - (spread * unit_size * 0.5) - (comm_total * 0.5)
                    pnl_leg2 = (exit_price - entry_price) * (unit_size * 0.5) - (spread * unit_size * 0.5) - (comm_total * 0.5) - swap_cost
                    net_pnl = pnl_leg1 + pnl_leg2
                else:
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
                if tp1_hit:
                    current_sl = max(current_sl, entry_price + 0.10)
                if st_bands[i] > current_sl:
                    current_sl = st_bands[i]

        elif pos == -1: # Short
            bar_low = lows[i]
            bar_high = highs[i]
            dip = min(0.0, (entry_price - bar_high) * unit_size)
            if dip < deepest_dip:
                deepest_dip = dip

            exit_hit = False
            exit_price = 0.0
            exit_reason = ""

            sl_touched = (bar_high >= current_sl)
            tp_touched = (bar_low <= current_tp1) if (use_staged_50_50 and not tp1_hit) else False

            # Rule D.1: Pessimistic Sequence Mandate
            if sl_touched and tp_touched:
                exit_hit = True
                exit_price = current_sl + sl_slippage
                exit_reason = "SL_Pessimistic"
            elif sl_touched:
                exit_hit = True
                exit_price = current_sl + sl_slippage
                exit_reason = "SL"
            elif tp_touched:
                tp1_hit = True

            if not exit_hit and closes[i] > st_bands[i]:
                exit_hit = True
                exit_price = opens[i + 1] + (spread * 0.5)
                exit_reason = "TrendFlip"

            if exit_hit:
                if use_staged_50_50 and tp1_hit and exit_reason != "SL_Pessimistic":
                    pnl_leg1 = (entry_price - (entry_price - tp1_atr_mult * atr_values[entry_idx - 1])) * (unit_size * 0.5) - (spread * unit_size * 0.5) - (comm_total * 0.5)
                    pnl_leg2 = (entry_price - exit_price) * (unit_size * 0.5) - (spread * unit_size * 0.5) - (comm_total * 0.5)
                    net_pnl = pnl_leg1 + pnl_leg2
                else:
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
                if tp1_hit:
                    current_sl = min(current_sl, entry_price - 0.10)
                if st_bands[i] < current_sl:
                    current_sl = st_bands[i]

        # Fresh Entry at Bar i Close -> Execute at Bar i+1 Open
        if pos == 0 and entry_signals[i] != 0:
            pos = entry_signals[i]
            entry_idx = i + 1
            entry_time = dates[i + 1]
            deepest_dip = 0.0
            tp1_hit = False

            if pos == 1:
                entry_price = opens[i + 1] + (spread * 0.5)
                current_sl = entry_price - (initial_sl_atr_mult * atr_values[i])
                current_tp1 = entry_price + (tp1_atr_mult * atr_values[i])
            else:
                entry_price = opens[i + 1] - (spread * 0.5)
                current_sl = entry_price + (initial_sl_atr_mult * atr_values[i])
                current_tp1 = entry_price - (tp1_atr_mult * atr_values[i])

    return trades

# -----------------------------------------------------------------------------
# Portfolio Analysis
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
# Main Execution Pipeline
# -----------------------------------------------------------------------------
def main():
    t_start = time.time()
    print("=" * 80)
    print("STARTING BATCH 47: APEX TRIANGULATED DISCOVERY (S661 - S670)")
    print("Strict Anti-Lookahead (+1H H1) | Rules D.1 - D.7 Compliant")
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

    m15_atr = compute_atr(m15_highs, m15_lows, m15_closes, 14)
    m15_ema200 = compute_ema(m15_closes, 200)
    m15_trend_3, m15_st_3 = compute_supertrend(m15_highs, m15_lows, m15_closes, m15_atr, 3.0)

    # 2. Load EURUSD M15 Data
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

    # 3. Load H1 Gold Data with STRICT +1 HOUR SHIFT
    print("[*] Loading XAUUSD H1 Data (Strict +1 Hour Shift)...")
    df_h1 = pd.read_parquet(os.path.join(DATA_DIR, "XAUUSD_H1.parquet"))
    h1_highs = df_h1["high"].values.astype(np.float64)
    h1_lows = df_h1["low"].values.astype(np.float64)
    h1_closes = df_h1["close"].values.astype(np.float64)
    h1_atr = compute_atr(h1_highs, h1_lows, h1_closes, 14)
    h1_ema200 = compute_ema(h1_closes, 200)
    h1_trend_3, h1_st_3 = compute_supertrend(h1_highs, h1_lows, h1_closes, h1_atr, 3.0)

    h1_closed_time = pd.to_datetime(df_h1.index) + pd.Timedelta(hours=1)
    df_h1_state = pd.DataFrame({
        "time": h1_closed_time,
        "h1_trend": h1_trend_3,
        "h1_st": h1_st_3,
        "h1_ema200": h1_ema200
    }).sort_values("time")

    m15_merged_h1 = pd.merge_asof(df_m15_time, df_h1_state, on="time", direction="backward")
    m15_h1_trend = m15_merged_h1["h1_trend"].fillna(1).values.astype(np.int32)
    m15_h1_st = m15_merged_h1["h1_st"].bfill().values.astype(np.float64)
    m15_h1_ema = m15_merged_h1["h1_ema200"].bfill().values.astype(np.float64)
    del df_h1, df_h1_state, m15_merged_h1, df_m15_time
    gc.collect()

    # =========================================================================
    # Strategy Generation
    # =========================================================================
    print("\n[+] Generating Signals for Batch 47 (S661 - S670)...")

    # S661: S658 Baseline (M15 ST + H1 Trend + EURUSD Gate, 24h except rollover)
    sig_s661 = np.zeros(n_m15, dtype=np.int32)
    for i in range(200, n_m15 - 1):
        if not (21 <= m15_dates[i].hour < 23):
            if m15_trend_3[i] == 1 and m15_trend_3[i - 1] == -1 and m15_closes[i] > m15_ema200[i]:
                if m15_h1_trend[i] == 1 and m15_eu_trend[i] == 1:
                    sig_s661[i] = 1
            elif m15_trend_3[i] == -1 and m15_trend_3[i - 1] == 1 and m15_closes[i] < m15_ema200[i]:
                if m15_h1_trend[i] == -1 and m15_eu_trend[i] == -1:
                    sig_s661[i] = -1

    # S662: S658 + London/NY Session Gate (07:00 - 17:00 UTC)
    sig_s662 = np.zeros(n_m15, dtype=np.int32)
    for i in range(200, n_m15 - 1):
        hour = m15_dates[i].hour
        if 7 <= hour <= 17:
            if m15_trend_3[i] == 1 and m15_trend_3[i - 1] == -1 and m15_closes[i] > m15_ema200[i]:
                if m15_h1_trend[i] == 1 and m15_eu_trend[i] == 1:
                    sig_s662[i] = 1
            elif m15_trend_3[i] == -1 and m15_trend_3[i - 1] == 1 and m15_closes[i] < m15_ema200[i]:
                if m15_h1_trend[i] == -1 and m15_eu_trend[i] == -1:
                    sig_s662[i] = -1

    # S663: S658 + Volatility Filter (ATR >= $1.50)
    sig_s663 = np.zeros(n_m15, dtype=np.int32)
    for i in range(200, n_m15 - 1):
        if not (21 <= m15_dates[i].hour < 23) and m15_atr[i] >= 1.50:
            if m15_trend_3[i] == 1 and m15_trend_3[i - 1] == -1 and m15_closes[i] > m15_ema200[i]:
                if m15_h1_trend[i] == 1 and m15_eu_trend[i] == 1:
                    sig_s663[i] = 1
            elif m15_trend_3[i] == -1 and m15_trend_3[i - 1] == 1 and m15_closes[i] < m15_ema200[i]:
                if m15_h1_trend[i] == -1 and m15_eu_trend[i] == -1:
                    sig_s663[i] = -1

    # S664: Strict H1 ST (S655 Baseline)
    sig_s664 = np.zeros(n_m15, dtype=np.int32)
    for i in range(200, n_m15 - 1):
        if not (21 <= m15_dates[i].hour < 23):
            if m15_h1_trend[i] == 1 and m15_h1_trend[i - 1] == -1 and m15_closes[i] > m15_h1_ema[i]:
                sig_s664[i] = 1
            elif m15_h1_trend[i] == -1 and m15_h1_trend[i - 1] == 1 and m15_closes[i] < m15_h1_ema[i]:
                sig_s664[i] = -1

    # S665: Strict H1 ST + EURUSD Macro Gate
    sig_s665 = np.zeros(n_m15, dtype=np.int32)
    for i in range(200, n_m15 - 1):
        if not (21 <= m15_dates[i].hour < 23):
            if m15_h1_trend[i] == 1 and m15_h1_trend[i - 1] == -1 and m15_closes[i] > m15_h1_ema[i] and m15_eu_trend[i] == 1:
                sig_s665[i] = 1
            elif m15_h1_trend[i] == -1 and m15_h1_trend[i - 1] == 1 and m15_closes[i] < m15_h1_ema[i] and m15_eu_trend[i] == -1:
                sig_s665[i] = -1

    # =========================================================================
    # Run Discrete Event Simulators (Rules D.1 - D.7)
    # =========================================================================
    print("\n[+] Running Discrete Event Simulators (Rules D.1 - D.7)...")

    # S661: S658 Baseline Runner
    tr_s661 = simulate_discrete_engine(m15_opens, m15_highs, m15_lows, m15_closes, m15_dates, sig_s661, m15_atr, m15_st_3, engine_name="S661_Triangulated_Runner")

    # S662: S658 Session Gated Runner (07-17 UTC)
    tr_s662 = simulate_discrete_engine(m15_opens, m15_highs, m15_lows, m15_closes, m15_dates, sig_s662, m15_atr, m15_st_3, engine_name="S662_Session_Runner")

    # S663: S658 Volatility Filtered Runner (ATR >= 1.50)
    tr_s663 = simulate_discrete_engine(m15_opens, m15_highs, m15_lows, m15_closes, m15_dates, sig_s663, m15_atr, m15_st_3, engine_name="S663_Vol_Runner")

    # S664: S658 with 50/50 Staged Scale-out (TP1 @ 3.0x ATR + Runner)
    tr_s664 = simulate_discrete_engine(m15_opens, m15_highs, m15_lows, m15_closes, m15_dates, sig_s661, m15_atr, m15_st_3, engine_name="S664_Staged_50_50", use_staged_50_50=True, tp1_atr_mult=3.0)

    # S665: Strict H1 ST Baseline
    tr_s665 = simulate_discrete_engine(m15_opens, m15_highs, m15_lows, m15_closes, m15_dates, sig_s664, m15_atr, m15_h1_st, engine_name="S665_H1_Baseline")

    # S666: Strict H1 ST + EURUSD Macro Gate
    tr_s666 = simulate_discrete_engine(m15_opens, m15_highs, m15_lows, m15_closes, m15_dates, sig_s665, m15_atr, m15_h1_st, engine_name="S666_H1_Macro_Gated")

    # S667: Dual Triangulated Ensemble (S661 M15 Triangulated + S665 Strict H1)
    tr_s667 = tr_s661 + tr_s665

    # S668: Dual Triangulated Ensemble (S662 Session M15 + S666 Macro H1)
    tr_s668 = tr_s662 + tr_s666

    # S669: Sovereign Triangulated Master with $180 Daily Governor
    tr_s669 = tr_s667

    # S670: Apex Sovereign Production Engine with $180 Daily Governor & Session Discipline
    tr_s670 = tr_s668

    # =========================================================================
    # Strategy Results Compilation
    # =========================================================================
    strategies_raw = [
        ("S661", "M15 Triangulated Runner", "M15 ST + H1 Trend + EURUSD Gate", tr_s661, 0.0),
        ("S662", "M15 Session Triangulated", "S661 + London/NY Session Gate (07-17)", tr_s662, 0.0),
        ("S663", "M15 Volatility Triangulated", "S661 + ATR >= $1.50 Vol Filter", tr_s663, 0.0),
        ("S664", "M15 Staged 50/50 Triangulated", "S661 + 50% TP1 @ 3.0x ATR + Runner", tr_s664, 0.0),
        ("S665", "Strict H1 Macro ST Runner", "Strict +1H Causal H1 ST (3.0,14)", tr_s665, 0.0),
        ("S666", "Strict H1 Macro ST + EU Gate", "Strict H1 ST + EURUSD Macro Gate", tr_s666, 0.0),
        ("S667", "Dual Triangulated Ensemble", "S661 M15 + S665 H1 Composite", tr_s667, 0.0),
        ("S668", "Session Dual Ensemble", "S662 Session M15 + S666 Macro H1", tr_s668, 0.0),
        ("S669", "Sovereign Triangulated Gov", "S667 Ensemble + $180 Daily Governor", tr_s669, 180.0),
        ("S670", "Apex Sovereign Production Master", "S668 Ensemble + $180 Daily Governor", tr_s670, 180.0)
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
    json_path = os.path.join(RESULTS_DIR, "batch_47_apex_triangulated_discovery.json")
    csv_path = os.path.join(RESULTS_DIR, "batch_47_apex_triangulated_discovery.csv")
    with open(json_path, "w") as f:
        json.dump(results_table, f, indent=2)
    pd.DataFrame(results_table).to_csv(csv_path, index=False)
    print(f"\n[+] Results saved to:\n    - {json_path}\n    - {csv_path}")

    # Identify Champion
    profitable = [r for r in results_table if r["Net_Profit"] > 0]
    if profitable:
        best_strat = max(profitable, key=lambda x: x["Net_Profit"])
        print(f"\n🏆 BATCH 47 CHAMPION: {best_strat['Strategy_ID']} - {best_strat['Strategy_Name']}")
        print(f"   Net Profit: ${best_strat['Net_Profit']:,.2f} | PF: {best_strat['Profit_Factor']:.3f} | Trades/Yr: {best_strat['Annual_Trades']:.1f} | Avg Win/Trade: ${best_strat['Avg_Profit_Per_Trade']:.2f}")

    print(f"\nBatch 47 completed in {time.time()-t_start:.2f} seconds.")

if __name__ == "__main__":
    main()
