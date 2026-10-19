#!/usr/bin/env python3
"""
===============================================================================
RIGOROUS QUANTITATIVE RE-BACKTEST UNDER ALL NEW EXECUTION MANDATES (V5.1)
===============================================================================
Strictly enforces:
- D.1: Pessimistic Sequence Mandate (SL triggered first if both hit in 1 bar)
- D.2: Strict Bar-Close Trailing Mandate (SL ratchet at Bar Close -> effective next Open)
- D.3: Intra-Bar Equity Tracking Mandate (DD measured from deepest intra-bar adverse dip)
- D.4: Negative Slippage on Stop Loss (-$0.10/trade on SL fills)
- D.5: 100% Bar-by-Bar Discrete Simulation (Zero Synthetic Multipliers)
- D.6: Lot Step Realism & Tranche Limit (Max 2 tranches: 50% TP1 BE + 50% Runner)
- D.7: Realistic Institutional Frictions ($0.25 spread + $6.00 comm + -$18/lot Long swap)
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
# Rigorous Bar-by-Bar Discrete Simulator with All Rules D.1 - D.7
# -----------------------------------------------------------------------------
def simulate_discrete_engine(
    opens, highs, lows, closes, dates,
    entry_signals,        # 1 for Buy, -1 for Sell on Bar i Close (Executes at i+1 Open)
    atr_values,           # ATR for SL / TP sizing
    st_bands,             # Supertrend bands for Bar-Close ratchets
    engine_name="Engine",
    lot_size=0.10,
    spread=0.25,
    commission_per_lot=6.00,
    sl_slippage=0.10,     # Rule D.4: $0.10 negative slippage on SL
    swap_long_daily=18.00,# Rule D.7: $18.00/standard lot/night
    use_staged_50_50=False,# Rule D.6: 50% TP1 Breakeven + 50% Runner
    tp1_atr_mult=1.0,
    sl_atr_mult=3.0,
    runner_ratchet=True
):
    n = len(closes)
    trades = []
    unit_size = lot_size * 100.0 # 0.10 lot = 10 oz
    comm_total = (commission_per_lot / 100.0) * unit_size # $0.60 per 0.10 lot round-turn

    pos = 0
    entry_price = 0.0
    entry_time = None
    entry_idx = 0
    current_sl = 0.0
    current_tp1 = 0.0
    tp1_hit = False
    deepest_dip = 0.0 # Rule D.3: Intra-bar Adverse Excursion tracking

    for i in range(200, n - 2):
        # 1. Manage Active Position (Rules D.1, D.2, D.3, D.4)
        if pos == 1: # Long
            bar_low = lows[i]
            bar_high = highs[i]
            bar_open = opens[i]

            # Intra-bar adverse dip tracking
            dip = min(0.0, (bar_low - entry_price) * unit_size)
            if dip < deepest_dip:
                deepest_dip = dip

            # Check exits during bar i
            exit_hit = False
            exit_price = 0.0
            exit_reason = ""

            # Check if SL or TP1 are hit
            sl_touched = (bar_low <= current_sl)
            tp_touched = (bar_high >= current_tp1) if (use_staged_50_50 and not tp1_hit) else False

            # Rule D.1: Pessimistic Sequence Mandate
            if sl_touched and tp_touched:
                # Assume SL hit first!
                exit_hit = True
                exit_price = current_sl - sl_slippage # Rule D.4
                exit_reason = "SL_Pessimistic"
            elif sl_touched:
                exit_hit = True
                exit_price = current_sl - sl_slippage # Rule D.4
                exit_reason = "SL"
            elif tp_touched:
                # TP1 reached (50% scale-out)
                tp1_hit = True
                # Rule D.2: SL moves to Breakeven at Bar Close, effective NEXT bar!

            # Supertrend trend flip exit
            if not exit_hit and runner_ratchet and closes[i] < st_bands[i]:
                exit_hit = True
                exit_price = opens[i + 1] - (spread * 0.5)
                exit_reason = "TrendFlip"

            if exit_hit:
                # Calculate swap if held overnight
                days_held = (dates[i].date() - entry_time.date()).days
                swap_cost = max(0, days_held) * (swap_long_daily / 100.0) * unit_size

                # Calculate PnL
                if use_staged_50_50 and tp1_hit and exit_reason != "SL_Pessimistic":
                    # Leg 1 made TP1 profit, Leg 2 made exit_price
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
                # Rule D.2: Strict Bar-Close Trailing Update (Effective next bar i+1 Open)
                if tp1_hit:
                    # Move SL to Breakeven (+1 tick above entry to cover costs)
                    current_sl = max(current_sl, entry_price + 0.05)
                if runner_ratchet and st_bands[i] > current_sl:
                    current_sl = st_bands[i] # Ratchet up

        elif pos == -1: # Short
            bar_low = lows[i]
            bar_high = highs[i]
            bar_open = opens[i]

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

            if not exit_hit and runner_ratchet and closes[i] > st_bands[i]:
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
                    current_sl = min(current_sl, entry_price - 0.05)
                if runner_ratchet and st_bands[i] < current_sl:
                    current_sl = st_bands[i]

        # 2. Check Fresh Entries at Bar i Close -> Execute Bar i+1 Open
        if pos == 0 and entry_signals[i] != 0:
            pos = entry_signals[i]
            entry_idx = i + 1
            entry_time = dates[i + 1]
            deepest_dip = 0.0
            tp1_hit = False

            if pos == 1:
                entry_price = opens[i + 1] + (spread * 0.5)
                sl_dist = sl_atr_mult * atr_values[i]
                current_sl = entry_price - sl_dist
                current_tp1 = entry_price + (tp1_atr_mult * atr_values[i])
            else:
                entry_price = opens[i + 1] - (spread * 0.5)
                sl_dist = sl_atr_mult * atr_values[i]
                current_sl = entry_price + sl_dist
                current_tp1 = entry_price - (tp1_atr_mult * atr_values[i])

    return trades

# -----------------------------------------------------------------------------
# Portfolio Analysis with Intra-Bar Equity Tracking (Rule D.3) & Risk Governors
# -----------------------------------------------------------------------------
def analyze_rigorous_portfolio(all_trades, max_daily_loss=0.0, use_streak_downscale=False):
    if not all_trades:
        return {"net_profit": 0, "pf": 0, "total_trades": 0, "annual_trades": 0, "max_dd": 1.0, "romad": 0, "win_rate": 0, "mcr": 0}

    # Sort chronologically by entry time
    all_trades = sorted(all_trades, key=lambda x: x["entry_time"])

    filtered_trades = []
    daily_pnl = {}
    streak_losses = 0

    for t in all_trades:
        day_key = t["entry_time"].strftime("%Y-%m-%d")
        day_curr_loss = daily_pnl.get(day_key, 0.0)

        # Daily loss circuit breaker check
        if max_daily_loss > 0 and day_curr_loss <= -max_daily_loss:
            continue # Skipped by daily risk governor!

        # Streak downscaling
        sizing = 1.0
        if use_streak_downscale and streak_losses >= 2:
            sizing = 0.75

        pnl = t["pnl"] * sizing
        dip = t["deepest_dip"] * sizing

        daily_pnl[day_key] = day_curr_loss + pnl
        if pnl < 0: streak_losses += 1
        elif pnl > 0: streak_losses = 0

        filtered_trades.append(dict(t, pnl=pnl, deepest_dip=dip))

    if not filtered_trades:
        return {"net_profit": 0, "pf": 0, "total_trades": 0, "annual_trades": 0, "max_dd": 1.0, "romad": 0, "win_rate": 0, "mcr": 0}

    # Rule D.3: Calculate Intra-Bar Equity Tracking Max Drawdown
    cum_equity = 0.0
    peak_equity = 0.0
    max_intra_dd = 0.0

    pnls = []
    m_dict = {}

    for t in filtered_trades:
        pnl = t["pnl"]
        dip = t["deepest_dip"]

        # Check lowest intra-bar equity reached during this trade
        intra_equity_dip = cum_equity + dip
        intra_dd = peak_equity - intra_equity_dip
        if intra_dd > max_intra_dd:
            max_intra_dd = intra_dd

        # Update closed equity
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

    pf = tot_win / tot_loss if tot_loss > 0 else 99.0
    wr = (len(wins) / len(pnls)) * 100.0 if len(pnls) > 0 else 0.0
    max_dd = max_intra_dd if max_intra_dd > 0 else 1.0
    romad = total_net / max_dd if max_dd > 0 else 0.0
    ann_tr = len(filtered_trades) / 6.0 # 6 years (2020-2025)

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
        "mcr": mcr
    }

# -----------------------------------------------------------------------------
# Main Execution Pipeline
# -----------------------------------------------------------------------------
def main():
    t_start = time.time()
    print("=" * 80)
    print("STARTING RIGOROUS RE-BACKTEST UNDER ALL NEW EXECUTION MANDATES (V5.1)")
    print("XAUUSD Gold CFD (2020-2025) | 6 Years / 72 Months")
    print("Enforcing Rules D.1 to D.7 | Zero Synthetic Multipliers | True Intra-Bar DD")
    print("=" * 80)

    # 1. Load M15 Gold Data
    print(f"[*] Loading M15 Data from: {os.path.join(DATA_DIR, 'XAUUSD_M15.parquet')}")
    df_m15 = pd.read_parquet(os.path.join(DATA_DIR, "XAUUSD_M15.parquet"))
    if "time" not in df_m15.columns: df_m15["time"] = pd.to_datetime(df_m15.index)
    m15_highs = df_m15["high"].values.astype(np.float64)
    m15_lows = df_m15["low"].values.astype(np.float64)
    m15_closes = df_m15["close"].values.astype(np.float64)
    m15_opens = df_m15["open"].values.astype(np.float64)
    m15_dates = pd.to_datetime(df_m15["time"]).dt.to_pydatetime()
    m15_atr = compute_atr(m15_highs, m15_lows, m15_closes, 14)
    m15_ema200 = compute_ema(m15_closes, 200)
    m15_trend, m15_st = compute_supertrend(m15_highs, m15_lows, m15_closes, m15_atr, 3.0)

    # 2. Load EURUSD M15 Data for Macro Gating
    print(f"[*] Loading EURUSD M15 Data for Macro Triangulation...")
    df_eu = pd.read_parquet(os.path.join(DATA_DIR, "EURUSD_M15.parquet"))
    if "time" not in df_eu.columns: df_eu["time"] = pd.to_datetime(df_eu.index)
    eu_closes = df_eu["close"].values.astype(np.float64)
    eu_ema50 = compute_ema(eu_closes, 50)
    eu_trend = np.where(eu_closes > eu_ema50, 1, -1)
    df_eu_state = pd.DataFrame({"time": pd.to_datetime(df_eu["time"]), "eu_trend": eu_trend}).sort_values("time")

    # Align EURUSD trend to M15 Gold
    df_m15_time = pd.DataFrame({"time": pd.to_datetime(df_m15["time"])})
    m15_merged_eu = pd.merge_asof(df_m15_time, df_eu_state, on="time", direction="backward")
    m15_macro_gating = m15_merged_eu["eu_trend"].fillna(1).values.astype(np.int32)
    del df_eu, df_eu_state, df_m15_time, m15_merged_eu
    gc.collect()

    # Generate M15 Entry Signals
    n_m15 = len(m15_closes)
    m15_signals_solo = np.zeros(n_m15, dtype=np.int32)
    m15_signals_gated = np.zeros(n_m15, dtype=np.int32)

    for i in range(200, n_m15 - 1):
        hour = m15_dates[i].hour
        session_ok = not (21 <= hour < 23) # skip rollover
        if session_ok:
            if m15_trend[i] == 1 and m15_trend[i - 1] == -1 and m15_closes[i] > m15_ema200[i]:
                m15_signals_solo[i] = 1
                if m15_macro_gating[i] == 1: # EURUSD confirms USD weakness
                    m15_signals_gated[i] = 1
            elif m15_trend[i] == -1 and m15_trend[i - 1] == 1 and m15_closes[i] < m15_ema200[i]:
                m15_signals_solo[i] = -1
                if m15_macro_gating[i] == -1:
                    m15_signals_gated[i] = -1

    # 3. Load M5 Gold Data
    print(f"[*] Loading M5 Data from: {os.path.join(DATA_DIR, 'XAUUSD_M5.parquet')}")
    df_m5 = pd.read_parquet(os.path.join(DATA_DIR, "XAUUSD_M5.parquet"))
    if "time" not in df_m5.columns: df_m5["time"] = pd.to_datetime(df_m5.index)
    m5_highs = df_m5["high"].values.astype(np.float64)
    m5_lows = df_m5["low"].values.astype(np.float64)
    m5_closes = df_m5["close"].values.astype(np.float64)
    m5_opens = df_m5["open"].values.astype(np.float64)
    m5_dates = pd.to_datetime(df_m5["time"]).dt.to_pydatetime()
    m5_atr = compute_atr(m5_highs, m5_lows, m5_closes, 14)
    m5_trend, m5_st = compute_supertrend(m5_highs, m5_lows, m5_closes, m5_atr, 3.0)

    # TTM Squeeze on M5
    s5_closes = pd.Series(m5_closes)
    bb5_mid = s5_closes.rolling(20).mean().values
    bb5_std = s5_closes.rolling(20).std().fillna(0).values
    bb5_up = bb5_mid + 2.0 * bb5_std
    bb5_dn = bb5_mid - 2.0 * bb5_std
    kc5_up = bb5_mid + 2.0 * m5_atr
    kc5_dn = bb5_mid - 2.0 * m5_atr

    # Align M15 macro trend to M5
    df_m15_state = pd.DataFrame({"time": pd.to_datetime(df_m15["time"]), "m15_trend": m15_trend}).sort_values("time")
    df_m5_time = pd.DataFrame({"time": pd.to_datetime(df_m5["time"])})
    m5_merged_m15 = pd.merge_asof(df_m5_time, df_m15_state, on="time", direction="backward")
    m5_macro_t = m5_merged_m15["m15_trend"].fillna(1).values.astype(np.int32)
    del df_m5, df_m5_time, m5_merged_m15
    gc.collect()

    n_m5 = len(m5_closes)
    m5_signals = np.zeros(n_m5, dtype=np.int32)
    sqz_cnt = 0
    for i in range(200, n_m5 - 1):
        hour = m5_dates[i].hour
        if (bb5_up[i] <= kc5_up[i]) and (bb5_dn[i] >= kc5_dn[i]):
            sqz_cnt += 1
        else:
            if sqz_cnt >= 6 and not (21 <= hour < 23):
                if m5_closes[i] > bb5_up[i] and m5_macro_t[i] == 1:
                    m5_signals[i] = 1
                elif m5_closes[i] < bb5_dn[i] and m5_macro_t[i] == -1:
                    m5_signals[i] = -1
            sqz_cnt = 0

    # 4. Load M1 Gold Data
    print(f"[*] Loading M1 Data from: {os.path.join(DATA_DIR, 'XAUUSD_M1.parquet')}")
    df_m1 = pd.read_parquet(os.path.join(DATA_DIR, "XAUUSD_M1.parquet"))
    if "time" not in df_m1.columns: df_m1["time"] = pd.to_datetime(df_m1.index)
    m1_highs = df_m1["high"].values.astype(np.float64)
    m1_lows = df_m1["low"].values.astype(np.float64)
    m1_closes = df_m1["close"].values.astype(np.float64)
    m1_opens = df_m1["open"].values.astype(np.float64)
    m1_dates = pd.to_datetime(df_m1["time"]).dt.to_pydatetime()
    m1_atr = compute_atr(m1_highs, m1_lows, m1_closes, 14)
    m1_trend, m1_st = compute_supertrend(m1_highs, m1_lows, m1_closes, m1_atr, 3.0)

    # Align M15 macro trend to M1
    df_m1_time = pd.DataFrame({"time": pd.to_datetime(df_m1["time"])})
    m1_merged_m15 = pd.merge_asof(df_m1_time, df_m15_state, on="time", direction="backward")
    m1_macro_t = m1_merged_m15["m15_trend"].fillna(1).values.astype(np.int32)
    del df_m1, df_m1_time, m1_merged_m15, df_m15_state
    gc.collect()

    n_m1 = len(m1_closes)
    m1_signals = np.zeros(n_m1, dtype=np.int32)
    for i in range(200, n_m1 - 1):
        hour = m1_dates[i].hour
        if 12 <= hour < 17 and m1_atr[i] >= 1.00: # NY Session + Volatility Filter
            if m1_trend[i] == 1 and m1_trend[i - 1] == -1 and m1_macro_t[i] == 1:
                m1_signals[i] = 1
            elif m1_trend[i] == -1 and m1_trend[i - 1] == 1 and m1_macro_t[i] == -1:
                m1_signals[i] = -1

    # -------------------------------------------------------------------------
    # Execute Simulators (100% Bar-by-Bar Discrete Event Engine)
    # -------------------------------------------------------------------------
    print("\n[+] Running Discrete Simulator under Strict Rules D.1 - D.7...")

    # Engine 1: M15 Core (Solo)
    t0 = time.time()
    tr_m15_solo = simulate_discrete_engine(m15_opens, m15_highs, m15_lows, m15_closes, m15_dates, m15_signals_solo, m15_atr, m15_st, engine_name="M15_Solo", lot_size=0.10)
    print(f"    M15 Solo Generated: {len(tr_m15_solo):,} trades in {time.time()-t0:.1f}s")

    # Engine 1 Gated: M15 Core + Macro Gate + 50/50 Staged
    tr_m15_gated_staged = simulate_discrete_engine(m15_opens, m15_highs, m15_lows, m15_closes, m15_dates, m15_signals_gated, m15_atr, m15_st, engine_name="M15_Gated", lot_size=0.10, use_staged_50_50=True)

    # Engine 2: M5 Ratchet
    t0 = time.time()
    tr_m5 = simulate_discrete_engine(m5_opens, m5_highs, m5_lows, m5_closes, m5_dates, m5_signals, m5_atr, m5_st, engine_name="M5_Ratchet", lot_size=0.08, use_staged_50_50=True)
    print(f"    M5 Ratchet Generated: {len(tr_m5):,} trades in {time.time()-t0:.1f}s")

    # Engine 3: M1 NY Sniper
    t0 = time.time()
    tr_m1 = simulate_discrete_engine(m1_opens, m1_highs, m1_lows, m1_closes, m1_dates, m1_signals, m1_atr, m1_st, engine_name="M1_Sniper", lot_size=0.07, use_staged_50_50=True)
    print(f"    M1 Sniper Generated: {len(tr_m1):,} trades in {time.time()-t0:.1f}s")

    # Clean large arrays
    del m1_opens, m1_highs, m1_lows, m1_closes, m1_dates, m1_atr, m1_trend, m1_st
    del m5_opens, m5_highs, m5_lows, m5_closes, m5_dates, m5_atr, m5_trend, m5_st
    del m15_opens, m15_highs, m15_lows, m15_closes, m15_dates, m15_atr, m15_trend, m15_st
    gc.collect()

    # -------------------------------------------------------------------------
    # Analyze Candidates under All Strict Rules
    # -------------------------------------------------------------------------
    candidates = []

    # Model 1: M15 Solo Supertrend Scalper (S421)
    res_m1 = analyze_rigorous_portfolio(tr_m15_solo)
    res_m1["Strategy_ID"] = "S421"
    res_m1["Strategy_Name"] = "M15 Solo Supertrend Scalper"
    res_m1["Architecture"] = "Solo M15 Trend Following"
    candidates.append(res_m1)

    # Model 2: M1 NY Micro Sniper (S446)
    res_m2 = analyze_rigorous_portfolio(tr_m1)
    res_m2["Strategy_ID"] = "S446"
    res_m2["Strategy_Name"] = "M1 NY Micro Sniper"
    res_m2["Architecture"] = "Solo M1 NY Session Sniper (12-17 UTC)"
    candidates.append(res_m2)

    # Model 3: M15 Tactical Duo Hybrid (S430)
    res_m3 = analyze_rigorous_portfolio(tr_m15_gated_staged + tr_m5)
    res_m3["Strategy_ID"] = "S430"
    res_m3["Strategy_Name"] = "M15 Tactical Duo Hybrid"
    res_m3["Architecture"] = "Hybrid Dual Engine (M15 Core + M5 Squeeze)"
    candidates.append(res_m3)

    # Model 4: Triple-Timeframe Matrix Master (S450)
    res_m4 = analyze_rigorous_portfolio(tr_m15_solo + tr_m5 + tr_m1)
    res_m4["Strategy_ID"] = "S450"
    res_m4["Strategy_Name"] = "Triple-Timeframe Matrix Master"
    res_m4["Architecture"] = "Tri-Engine Pure Price Action (M15+M5+M1)"
    candidates.append(res_m4)

    # Model 5: Tri-Engine + Macro Gating + 50/50 Staged (S530 Architecture)
    res_m5 = analyze_rigorous_portfolio(tr_m15_gated_staged + tr_m5 + tr_m1)
    res_m5["Strategy_ID"] = "S530"
    res_m5["Strategy_Name"] = "Sovereign Intermarket Tri-Engine"
    res_m5["Architecture"] = "Tri-Engine + EURUSD Macro Gate + 50/50 Staged"
    candidates.append(res_m5)

    # Model 6: Tri-Engine + Daily Governor ($200)
    res_m6 = analyze_rigorous_portfolio(tr_m15_gated_staged + tr_m5 + tr_m1, max_daily_loss=200.0)
    res_m6["Strategy_ID"] = "S570"
    res_m6["Strategy_Name"] = "Sovereign Governor Tri-Engine"
    res_m6["Architecture"] = "Tri-Engine + Macro Gate + $200 Daily Governor"
    candidates.append(res_m6)

    # Model 7: Full Sovereign Centennial Chronos Apex (S630 Architecture)
    # Combines Tri-Engine + Macro Gating + 50/50 Staged + $160 Daily Governor + Streak Downscaling
    res_m7 = analyze_rigorous_portfolio(tr_m15_gated_staged + tr_m5 + tr_m1, max_daily_loss=160.0, use_streak_downscale=True)
    res_m7["Strategy_ID"] = "S630"
    res_m7["Strategy_Name"] = "Centennial Sovereign Chronos Apex"
    res_m7["Architecture"] = "Tri-Engine + Macro Gate + 50/50 Staged + $160 Gov + Streak Downscale"
    candidates.append(res_m7)

    # Output Results Table
    df_res = pd.DataFrame(candidates)
    cols = ["Strategy_ID", "Strategy_Name", "Architecture", "annual_trades", "total_trades", "net_profit", "pf", "win_rate", "max_dd", "romad", "mcr"]
    rename_cols = {
        "annual_trades": "Annual_Trades", "total_trades": "Total_Trades",
        "net_profit": "Net_Profit", "pf": "Profit_Factor", "win_rate": "Win_Rate_Pct",
        "max_dd": "True_Intra_Max_DD", "romad": "RoMaD", "mcr": "Monthly_Consistency_Pct"
    }
    df_res = df_res[cols].rename(columns=rename_cols)

    # Save to CSV and JSON
    csv_file = os.path.join(RESULTS_DIR, "rigorous_scalping_rebacktest_v5_1.csv")
    json_file = os.path.join(RESULTS_DIR, "rigorous_scalping_rebacktest_v5_1.json")
    df_res.to_csv(csv_file, index=False)
    with open(json_file, "w") as f:
        json.dump(candidates, f, indent=2, default=str)

    elapsed = time.time() - t_start
    print("\n" + "=" * 80)
    print(f"RIGOROUS RE-BACKTEST COMPLETED IN {elapsed:.2f}s")
    print("=" * 80)
    print(df_res.to_string(index=False))

    gc.collect()

if __name__ == "__main__":
    main()
