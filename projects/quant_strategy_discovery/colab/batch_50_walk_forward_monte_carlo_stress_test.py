#!/usr/bin/env python3
"""
===============================================================================
BATCH 50: INSTITUTIONAL WALK-FORWARD, MONTE CARLO & STRESS TESTING
===============================================================================
Comprehensive institutional audit of the newly discovered champions:
- S700: Centennial Sovereign Millennium Apex (Multi-TF Intermarket Governed)
- S682: Early London Ignite (06:00 - 10:00 UTC Breakout Specialist, PF 1.540)
- S724 / S725: Dual Sovereign Ensemble (S700 + S682 Combined)

Evaluated under 100% strict adherence to Constitution V5.1 (Rules D.1 to D.7):
- Rule D.1: Pessimistic Sequence Mandate (SL triggered first if both hit in 1 bar)
- Rule D.2: Strict Bar-Close Trailing Mandate (effective next bar Open)
- Rule D.3: Intra-Bar Equity Tracking Mandate (Max DD measured from deepest intra-bar adverse dip)
- Rule D.4: Negative Slippage on Stop Loss (-$0.10/trade on all SL fills)
- Rule D.5: 100% Bar-by-Bar Discrete Simulation (Zero Synthetic Multipliers)
- Rule D.6: Lot Step Realism (0.10 lot baseline or exact 0.01 lot increments)
- Rule D.7: Institutional Frictions ($0.25 spread + $6.00 comm + -$18/lot swap)
- Strict Anti-Lookahead Causality: H1 closed bar only (+1H shift), M15 closed bar only (+15M shift)

Investigative Matrices:
1. Walk-Forward In-Sample (2020-2023, 48 mo) vs Out-of-Sample (2024-2025, 24 mo)
2. Severe Institutional Friction Shocks (Spread 1.5x - 2.5x, Slippage -$0.20 to -$0.30, Swap 2x)
3. Convex Parameter Plateau Mesh (ST Multipliers, ATR Filters, Daily Governors)
4. Portfolio Ensemble Synergies (S700 + S682)
5. 1,000-Run Monte Carlo Permutation Analysis (50th, 95th, 99th Pct DD, Prob of Ruin)
===============================================================================
"""

import os
import sys
import time
import json
import gc
import numpy as np
import pandas as pd
from datetime import datetime, timezone

# Determine repository root (support Colab and Local paths)
REPO_ROOT = "/content/CFD-Trading-ML" if os.path.exists("/content/CFD-Trading-ML") else "/root/CFD-Trading-ML"
DATA_DIR = os.path.join(REPO_ROOT, "projects/quant_strategy_discovery/data")
RESULTS_DIR = os.path.join(REPO_ROOT, "projects/quant_strategy_discovery/results")
os.makedirs(RESULTS_DIR, exist_ok=True)

# -----------------------------------------------------------------------------
# Indicator Computations (Pure NumPy)
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
    start_date=None,
    end_date=None
):
    n = len(closes)
    trades = []
    unit_size = lot_size * 100.0
    comm_total = (commission_per_lot / 100.0) * unit_size

    pos = 0
    entry_price = 0.0
    entry_time = None
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
            trend_flipped = (closes[i] < st_bands[i])

            # Rule D.1: Pessimistic Sequence Mandate
            if sl_touched:
                exit_hit = True
                exit_price = current_sl - sl_slippage
                exit_reason = "SL"
            elif trend_flipped:
                exit_hit = True
                exit_price = opens[i + 1] - (spread * 0.5)
                exit_reason = "TrendFlip"

            if exit_hit:
                days_held = (dates[i].date() - entry_time.date()).days
                swap_cost = max(0, days_held) * (swap_long_daily / 100.0) * unit_size
                net_pnl = (exit_price - entry_price) * unit_size - (spread * unit_size) - comm_total - swap_cost

                # Window check
                in_window = True
                if start_date and entry_time < start_date: in_window = False
                if end_date and entry_time > end_date: in_window = False

                if in_window:
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
            trend_flipped = (closes[i] > st_bands[i])

            if sl_touched:
                exit_hit = True
                exit_price = current_sl + sl_slippage
                exit_reason = "SL"
            elif trend_flipped:
                exit_hit = True
                exit_price = opens[i + 1] + (spread * 0.5)
                exit_reason = "TrendFlip"

            if exit_hit:
                net_pnl = (entry_price - exit_price) * unit_size - (spread * unit_size) - comm_total

                in_window = True
                if start_date and entry_time < start_date: in_window = False
                if end_date and entry_time > end_date: in_window = False

                if in_window:
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

        # Fresh Entry at Bar i Close -> Execute at Bar i+1 Open
        if pos == 0 and entry_signals[i] != 0:
            pos = entry_signals[i]
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
# Portfolio Analysis
# -----------------------------------------------------------------------------
def analyze_trades(all_trades, max_daily_loss=0.0, years=6.0):
    if not all_trades:
        return {"net_profit": 0, "pf": 0, "total_trades": 0, "annual_trades": 0, "max_dd": 1.0, "romad": 0, "win_rate": 0, "mcr": 0, "avg_profit_per_trade": 0, "filtered_trades": []}

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
        return {"net_profit": 0, "pf": 0, "total_trades": 0, "annual_trades": 0, "max_dd": 1.0, "romad": 0, "win_rate": 0, "mcr": 0, "avg_profit_per_trade": 0, "filtered_trades": []}

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
    ann_tr = len(filtered_trades) / years
    avg_trade = total_net / len(filtered_trades) if len(filtered_trades) > 0 else 0.0

    total_months = int(years * 12.0)
    pos_m = sum(1 for v in m_dict.values() if v > 0)
    mcr = (pos_m / max(1, total_months)) * 100.0

    return {
        "net_profit": total_net,
        "pf": pf,
        "total_trades": len(filtered_trades),
        "annual_trades": ann_tr,
        "max_dd": max_dd,
        "romad": romad,
        "win_rate": wr,
        "mcr": mcr,
        "avg_profit_per_trade": avg_trade,
        "filtered_trades": filtered_trades
    }

# -----------------------------------------------------------------------------
# Monte Carlo Permutation Engine (1,000 Runs)
# -----------------------------------------------------------------------------
def run_monte_carlo(trades, num_simulations=1000, initial_capital=10000.0):
    if not trades or len(trades) < 10:
        return {}

    pnls = np.array([t["pnl"] for t in trades], dtype=np.float64)
    dips = np.array([t["deepest_dip"] for t in trades], dtype=np.float64)
    n = len(pnls)

    mc_max_dds = np.zeros(num_simulations, dtype=np.float64)
    mc_net_profits = np.zeros(num_simulations, dtype=np.float64)
    ruin_count = 0
    max_losing_streaks = np.zeros(num_simulations, dtype=np.int32)

    rng = np.random.default_rng(seed=42)

    for s in range(num_simulations):
        idx = rng.permutation(n)
        perm_pnls = pnls[idx]
        perm_dips = dips[idx]

        cum_equity = 0.0
        peak_equity = 0.0
        max_dd = 0.0
        curr_streak = 0
        max_streak = 0
        is_ruined = False

        for p, d in zip(perm_pnls, perm_dips):
            if p < 0:
                curr_streak += 1
                if curr_streak > max_streak:
                    max_streak = curr_streak
            else:
                curr_streak = 0

            # Intra-bar check
            intra_dip = cum_equity + d
            intra_dd = peak_equity - intra_dip
            if intra_dd > max_dd:
                max_dd = intra_dd

            cum_equity += p
            if cum_equity > peak_equity:
                peak_equity = cum_equity

            closed_dd = peak_equity - cum_equity
            if closed_dd > max_dd:
                max_dd = closed_dd

            if (initial_capital + cum_equity + d) <= 0:
                is_ruined = True

        if is_ruined:
            ruin_count += 1

        mc_max_dds[s] = max_dd
        mc_net_profits[s] = cum_equity
        max_losing_streaks[s] = max_streak

    return {
        "num_simulations": num_simulations,
        "median_max_dd": float(np.percentile(mc_max_dds, 50)),
        "pct_95_max_dd": float(np.percentile(mc_max_dds, 95)),
        "pct_99_max_dd": float(np.percentile(mc_max_dds, 99)),
        "median_net_profit": float(np.percentile(mc_net_profits, 50)),
        "prob_of_ruin_pct": (ruin_count / num_simulations) * 100.0,
        "median_max_loss_streak": int(np.percentile(max_losing_streaks, 50)),
        "pct_95_max_loss_streak": int(np.percentile(max_losing_streaks, 95)),
    }

# -----------------------------------------------------------------------------
# Main Execution Pipeline
# -----------------------------------------------------------------------------
def main():
    t_start = time.time()
    now_str = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')
    print("=" * 80)
    print("🚀 BATCH 50: INSTITUTIONAL WALK-FORWARD, MONTE CARLO & STRESS TESTING")
    print(f"Timestamp: {now_str}")
    print(f"Hardware Environment: {'Google Colab VM' if 'content' in REPO_ROOT else 'Local Controller'}")
    print("=" * 80)

    # 1. Load Parquet Data
    print(f"[*] Loading Parquet Caches from {DATA_DIR}...")
    df_m15 = pd.read_parquet(os.path.join(DATA_DIR, "XAUUSD_M15.parquet"))
    df_h1 = pd.read_parquet(os.path.join(DATA_DIR, "XAUUSD_H1.parquet"))
    df_eu = pd.read_parquet(os.path.join(DATA_DIR, "EURUSD_M15.parquet"))

    m15_highs = df_m15["high"].values.astype(np.float64)
    m15_lows = df_m15["low"].values.astype(np.float64)
    m15_closes = df_m15["close"].values.astype(np.float64)
    m15_opens = df_m15["open"].values.astype(np.float64)
    m15_dates = pd.to_datetime(df_m15.index).to_pydatetime()
    n_m15 = len(m15_closes)

    h1_highs = df_h1["high"].values.astype(np.float64)
    h1_lows = df_h1["low"].values.astype(np.float64)
    h1_closes = df_h1["close"].values.astype(np.float64)

    eu_closes = df_eu["close"].values.astype(np.float64)

    # 2. Compute Core Indicators
    print("[*] Computing Multi-Timeframe Multi-Asset Indicators...")
    m15_atr14 = compute_atr(m15_highs, m15_lows, m15_closes, 14)
    m15_ema200 = compute_ema(m15_closes, 200)

    # Precompute Supertrend Grids on M15
    st_m15_dict = {}
    for mult in [2.75, 3.0, 3.25]:
        t_arr, b_arr = compute_supertrend(m15_highs, m15_lows, m15_closes, m15_atr14, mult)
        st_m15_dict[mult] = (t_arr, b_arr)

    # Precompute H1 Indicators with Strict +1H Shift
    h1_atr14 = compute_atr(h1_highs, h1_lows, h1_closes, 14)
    h1_ema200 = compute_ema(h1_closes, 200)
    h1_tr30, h1_st30 = compute_supertrend(h1_highs, h1_lows, h1_closes, h1_atr14, 3.0)

    h1_closed_time = pd.to_datetime(df_h1.index) + pd.Timedelta(hours=1)
    df_h1_state = pd.DataFrame({
        "time": h1_closed_time,
        "h1_tr": h1_tr30,
        "h1_st": h1_st30,
        "h1_ema": h1_ema200
    }).sort_values("time")

    df_m15_time = pd.DataFrame({"time": pd.to_datetime(df_m15.index)})
    m15_merged_h1 = pd.merge_asof(df_m15_time, df_h1_state, on="time", direction="backward")
    m15_h1_trend = m15_merged_h1["h1_tr"].fillna(1).values.astype(np.int32)
    m15_h1_st = m15_merged_h1["h1_st"].bfill().values.astype(np.float64)
    m15_h1_ema = m15_merged_h1["h1_ema"].bfill().values.astype(np.float64)

    # Precompute EURUSD Regime
    eu_ema50 = compute_ema(eu_closes, 50)
    eu_trend = np.where(eu_closes > eu_ema50, 1, -1)
    df_eu_state = pd.DataFrame({"time": pd.to_datetime(df_eu.index), "eu_trend": eu_trend}).sort_values("time")
    m15_merged_eu = pd.merge_asof(df_m15_time, df_eu_state, on="time", direction="backward")
    m15_eu_trend = m15_merged_eu["eu_trend"].fillna(1).values.astype(np.int32)

    del df_h1, df_h1_state, df_eu, df_eu_state, m15_merged_h1, m15_merged_eu, df_m15_time
    gc.collect()

    print(f"[+] Synchronized {n_m15:,} M15 bars under strict causality.")

    # 3. Helper Functions for Signal Generation
    def generate_triangulated_signals(st_mult=3.0, session_start=7, session_end=17, min_atr=1.50):
        t_arr, _ = st_m15_dict[st_mult]
        sig = np.zeros(n_m15, dtype=np.int32)
        for i in range(200, n_m15 - 1):
            h = m15_dates[i].hour
            if session_start <= h <= session_end:
                if min_atr <= 0.0 or m15_atr14[i] >= min_atr:
                    if t_arr[i] == 1 and t_arr[i - 1] == -1 and m15_closes[i] > m15_ema200[i]:
                        if m15_h1_trend[i] == 1 and m15_eu_trend[i] == 1:
                            sig[i] = 1
                    elif t_arr[i] == -1 and t_arr[i - 1] == 1 and m15_closes[i] < m15_ema200[i]:
                        if m15_h1_trend[i] == -1 and m15_eu_trend[i] == -1:
                            sig[i] = -1
        return sig

    def generate_macro_h1_signals(session_start=7, session_end=17):
        sig = np.zeros(n_m15, dtype=np.int32)
        for i in range(200, n_m15 - 1):
            h = m15_dates[i].hour
            if session_start <= h <= session_end and not (21 <= h < 23):
                if m15_h1_trend[i] == 1 and m15_h1_trend[i - 1] == -1 and m15_closes[i] > m15_h1_ema[i] and m15_eu_trend[i] == 1:
                    sig[i] = 1
                elif m15_h1_trend[i] == -1 and m15_h1_trend[i - 1] == 1 and m15_closes[i] < m15_h1_ema[i] and m15_eu_trend[i] == -1:
                    sig[i] = -1
        return sig

    _, st_b30 = st_m15_dict[3.0]
    _, st_b275 = st_m15_dict[2.75]
    _, st_b325 = st_m15_dict[3.25]

    split_date = datetime(2024, 1, 1, 0, 0, 0)

    # Base Signals
    sig_s700_m15 = generate_triangulated_signals(st_mult=3.0, session_start=7, session_end=17, min_atr=1.50)
    sig_s700_h1 = generate_macro_h1_signals(session_start=7, session_end=17)
    sig_s682_m15 = generate_triangulated_signals(st_mult=3.0, session_start=6, session_end=10, min_atr=1.50)

    # 4. Construct S700 and S682 Runner Suites
    def run_s700_trades(spread=0.25, comm=6.0, slippage=0.10, swap=18.0, st_b=st_b30, sig_m15=sig_s700_m15, sig_h1=sig_s700_h1, start=None, end=None, lot=0.10):
        t1 = simulate_discrete_engine(m15_opens, m15_highs, m15_lows, m15_closes, m15_dates, sig_m15, m15_atr14, st_b, "M15_Session", lot_size=lot, spread=spread, commission_per_lot=comm, sl_slippage=slippage, swap_long_daily=swap, start_date=start, end_date=end)
        t2 = simulate_discrete_engine(m15_opens, m15_highs, m15_lows, m15_closes, m15_dates, sig_h1, m15_atr14, m15_h1_st, "Macro_H1", lot_size=lot, spread=spread, commission_per_lot=comm, sl_slippage=slippage, swap_long_daily=swap, start_date=start, end_date=end)
        return t1 + t2

    def run_s682_trades(spread=0.25, comm=6.0, slippage=0.10, swap=18.0, start=None, end=None, lot=0.10):
        return simulate_discrete_engine(m15_opens, m15_highs, m15_lows, m15_closes, m15_dates, sig_s682_m15, m15_atr14, st_b30, "S682_EarlyLondon", lot_size=lot, spread=spread, commission_per_lot=comm, sl_slippage=slippage, swap_long_daily=swap, start_date=start, end_date=end)

    # 5. Define Strategy Matrix (S701 to S725)
    print("\n[+] Constructing 25 Institutional Strategies (S701 - S725)...")
    strategy_definitions = [
        # Walk-Forward Robustness
        ("S701", "S700 Centennial Apex Baseline (Full 6Y)", lambda: run_s700_trades(), 160.0, 6.0, "Full 6Y Production Benchmark"),
        ("S702", "S700 In-Sample (IS: 2020-2023)", lambda: run_s700_trades(end=split_date), 160.0, 4.0, "In-Sample (48 Months)"),
        ("S703", "S700 Out-of-Sample (OOS: 2024-2025)", lambda: run_s700_trades(start=split_date), 160.0, 2.0, "Out-of-Sample (24 Months)"),
        ("S704", "S682 Early London Baseline (Full 6Y)", lambda: run_s682_trades(), 0.0, 6.0, "Early London Benchmark"),
        ("S705", "S682 In-Sample (IS: 2020-2023)", lambda: run_s682_trades(end=split_date), 0.0, 4.0, "In-Sample (48 Months)"),
        ("S706", "S682 Out-of-Sample (OOS: 2024-2025)", lambda: run_s682_trades(start=split_date), 0.0, 2.0, "Out-of-Sample (24 Months)"),

        # Severe Institutional Friction Shocks on S700
        ("S707", "S700 Spread Shock 1.5x ($0.375)", lambda: run_s700_trades(spread=0.375), 160.0, 6.0, "Friction Shock: 1.5x Spread"),
        ("S708", "S700 Spread Shock 2.0x ($0.500)", lambda: run_s700_trades(spread=0.500), 160.0, 6.0, "Friction Shock: 2.0x Spread"),
        ("S709", "S700 Spread Shock 2.5x ($0.625)", lambda: run_s700_trades(spread=0.625), 160.0, 6.0, "Friction Shock: 2.5x Spread"),
        ("S710", "S700 Slippage Shock (-$0.20/oz)", lambda: run_s700_trades(slippage=0.20), 160.0, 6.0, "Slippage Shock: -$0.20/oz"),
        ("S711", "S700 Slippage Shock (-$0.30/oz)", lambda: run_s700_trades(slippage=0.30), 160.0, 6.0, "Slippage Shock: -$0.30/oz"),
        ("S712", "S700 Swap Shock 2x (-$36/lot)", lambda: run_s700_trades(swap=36.0), 160.0, 6.0, "Swap Shock: -$36.00/lot"),
        ("S713", "S700 Combined Extreme Crisis", lambda: run_s700_trades(spread=0.50, slippage=0.20, swap=36.0), 160.0, 6.0, "Combined Crisis: 2x Spread + Slip + Swap"),

        # Friction Shocks on S682 Early London
        ("S714", "S682 Spread Shock 1.5x ($0.375)", lambda: run_s682_trades(spread=0.375), 0.0, 6.0, "S682 Spread Shock 1.5x"),
        ("S715", "S682 Spread Shock 2.0x ($0.500)", lambda: run_s682_trades(spread=0.500), 0.0, 6.0, "S682 Spread Shock 2.0x"),

        # Convex Parameter Plateau Mesh around S700
        ("S716", "S700 ST Mult 2.75x Plateau", lambda: run_s700_trades(st_b=st_b275, sig_m15=generate_triangulated_signals(st_mult=2.75, session_start=7, session_end=17, min_atr=1.50)), 160.0, 6.0, "Convex Plateau Mult 2.75x"),
        ("S717", "S700 ST Mult 3.25x Plateau", lambda: run_s700_trades(st_b=st_b325, sig_m15=generate_triangulated_signals(st_mult=3.25, session_start=7, session_end=17, min_atr=1.50)), 160.0, 6.0, "Convex Plateau Mult 3.25x"),
        ("S718", "S700 ATR Floor $1.25 Plateau", lambda: run_s700_trades(sig_m15=generate_triangulated_signals(st_mult=3.0, session_start=7, session_end=17, min_atr=1.25)), 160.0, 6.0, "Convex Plateau ATR $1.25"),
        ("S719", "S700 ATR Floor $1.75 Plateau", lambda: run_s700_trades(sig_m15=generate_triangulated_signals(st_mult=3.0, session_start=7, session_end=17, min_atr=1.75)), 160.0, 6.0, "Convex Plateau ATR $1.75"),

        # Governor Sensitivity
        ("S720", "S700 Governor $100 Sweep", lambda: run_s700_trades(), 100.0, 6.0, "Tight $100 Daily Governor"),
        ("S721", "S700 Governor $120 Sweep", lambda: run_s700_trades(), 120.0, 6.0, "Proven $120 Daily Governor"),
        ("S722", "S700 Governor $140 Sweep", lambda: run_s700_trades(), 140.0, 6.0, "Balanced $140 Daily Governor"),
        ("S723", "S700 Governor $200 Sweep", lambda: run_s700_trades(), 200.0, 6.0, "Relaxed $200 Daily Governor"),

        # Multi-Engine Ensemble Synergy
        ("S724", "Dual Sovereign Ensemble (S700+S682 @ 0.07 lot)", lambda: run_s700_trades(lot=0.07) + run_s682_trades(lot=0.07), 160.0, 6.0, "Dual Session Diversification"),
        ("S725", "Triple Sovereign Master (S700+S682 @ 0.07 lot + $200 Gov)", lambda: run_s700_trades(lot=0.07) + run_s682_trades(lot=0.07), 200.0, 6.0, "All-Weather Sovereign Ensemble"),
    ]

    # 6. Evaluation and Reporting
    results_table = []
    trade_collections = {}

    print("\n" + "=" * 125)
    print(f"{'ID':<6} {'Strategy Name':<42} {'Ann.Tr':<8} {'Tot.Tr':<8} {'Net PnL ($)':<14} {'PF':<8} {'WR%':<8} {'Intra DD ($)':<14} {'RoMaD':<8} {'MCR%':<8}")
    print("=" * 125)

    for sid, name, fn, gov, yrs, role in strategy_definitions:
        trades = fn()
        m = analyze_trades(trades, max_daily_loss=gov, years=yrs)
        row = {
            "Strategy_ID": sid,
            "Strategy_Name": name,
            "Role": role,
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

        if sid in ["S701", "S703", "S704", "S706", "S724", "S725"]:
            trade_collections[sid] = m.get("filtered_trades", [])

        print(f"{sid:<6} {name:<42} {m['annual_trades']:<8.1f} {m['total_trades']:<8} {m['net_profit']:<14.2f} {m['pf']:<8.3f} {m['win_rate']:<8.1f} {m['max_dd']:<14.2f} {m['romad']:<8.2f} {m['mcr']:<8.1f}")

    print("=" * 125)

    # 7. 1,000-Permutation Monte Carlo Audit
    print("\n🎲 Running 1,000-Permutation Monte Carlo Audit on Core Champions...")
    mc_results = {}
    for sid, tr_list in trade_collections.items():
        mc_res = run_monte_carlo(tr_list, num_simulations=1000, initial_capital=10000.0)
        mc_results[sid] = mc_res
        print(f"  [MC Audit] {sid}: Median DD=${mc_res.get('median_max_dd', 0):.2f} | 95th Pct DD=${mc_res.get('pct_95_max_dd', 0):.2f} | 99th Pct DD=${mc_res.get('pct_99_max_dd', 0):.2f} | Ruin Prob={mc_res.get('prob_of_ruin_pct', 0):.2f}% | Max Loss Streak(95th)={mc_res.get('pct_95_max_loss_streak', 0)}")

    # 8. Save Artifacts
    json_path = os.path.join(RESULTS_DIR, "batch_50_walk_forward_monte_carlo_results.json")
    csv_path = os.path.join(RESULTS_DIR, "batch_50_walk_forward_monte_carlo_matrix.csv")

    with open(json_path, "w") as f:
        json.dump({"strategies": results_table, "monte_carlo": mc_results}, f, indent=2)
    pd.DataFrame(results_table).to_csv(csv_path, index=False)

    print(f"\n[+] Batch 50 Completed in {time.time()-t_start:.2f} seconds.")
    print(f"    Results saved to:\n    - {json_path}\n    - {csv_path}")

if __name__ == "__main__":
    main()
