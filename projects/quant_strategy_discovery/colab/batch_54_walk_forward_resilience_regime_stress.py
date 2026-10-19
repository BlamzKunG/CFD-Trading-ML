#!/usr/bin/env python3
"""
===============================================================================
BATCH 54: WALK-FORWARD STABILITY, REGIME RESILIENCE & 1,000-RUN MONTE CARLO
===============================================================================
Comprehensive institutional audit across 30 strategies (S816 to S845) on Google Colab Cloud VM
under 100% strict adherence to Constitution V5.1 (Rules D.1 to D.7):
- Rule D.1: Pessimistic Sequence Mandate (SL triggered first if both hit in 1 bar)
- Rule D.2: Strict Bar-Close Trailing Mandate (effective next bar Open)
- Rule D.3: Intra-Bar Equity Tracking Mandate (Max DD measured from deepest intra-bar adverse excursion)
- Rule D.4: Negative Slippage on Stop Loss (-$0.10/trade baseline on all SL fills)
- Rule D.5: 100% Bar-by-Bar Discrete Simulation (Zero Synthetic Multipliers)
- Rule D.6: Lot Step Realism (Exact 0.01 lot multiples, clamped between 0.04 and 0.25)
- Rule D.7: Institutional Frictions ($0.25 spread + $6.00 comm + -$18/lot swap)
- Strict Anti-Lookahead Causality: H1 closed bar only (+1H shift), M15 closed bar only

Core Research Themes:
1. S816 - S825: Walk-Forward Multi-Year Stability (2020-2023 IS vs 2024-2025 OOS)
   Auditing S731 Dynamic Vol Apex (+$24k), S809 Regime Master ($1,000 DD), S802 Sniper (PF 2.934)
2. S826 - S835: Friction Shocks & Multi-Crisis Stress Testing (1.5x - 3.0x spread, -$0.35 slippage)
3. S836 - S845: Advanced Sovereign Synthesis, Multi-Pillar Architecture & Dynamic Ensembles
4. Full 1,000-Run Monte Carlo Permutation Analysis for every strategy configuration
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

# Repository Root Setup
REPO_ROOT = "/content/CFD-Trading-ML" if os.path.exists("/content/CFD-Trading-ML") else "/root/CFD-Trading-ML"
DATA_DIR = os.path.join(REPO_ROOT, "projects/quant_strategy_discovery/data")
RESULTS_DIR = os.path.join(REPO_ROOT, "projects/quant_strategy_discovery/results")
os.makedirs(RESULTS_DIR, exist_ok=True)

# -----------------------------------------------------------------------------
# Fast Pure-NumPy Indicators
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

def compute_efficiency_ratio(closes: np.ndarray, period: int = 14) -> np.ndarray:
    n = len(closes)
    er = np.zeros(n, dtype=np.float64)
    for i in range(period, n):
        change = abs(closes[i] - closes[i - period])
        volatility = np.sum(np.abs(np.diff(closes[i - period : i + 1])))
        if volatility > 0.0:
            er[i] = change / volatility
        else:
            er[i] = 0.0
    return er

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
# Discrete Event Simulator Supporting Sizing & Windowing (Rules D.1 to D.7)
# -----------------------------------------------------------------------------
def simulate_discrete_engine(
    opens, highs, lows, closes, dates,
    entry_signals,
    atr_values,
    st_bands,
    engine_name="Engine",
    lot_size=0.10,
    dynamic_vol_risk=0.0,
    min_lot=0.04,
    max_lot=0.25,
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
    point_value = 100.0

    pos = 0
    entry_price = 0.0
    entry_time = None
    current_sl = 0.0
    active_lot = lot_size
    deepest_dip = 0.0

    for i in range(200, n - 2):
        if pos == 1: # Long
            unit_size = active_lot * point_value
            comm_total = (commission_per_lot / 100.0) * unit_size
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

                # Window filter
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
                        "lot": active_lot,
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
            unit_size = active_lot * point_value
            comm_total = (commission_per_lot / 100.0) * unit_size
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
                        "lot": active_lot,
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

            if dynamic_vol_risk > 0.0 and atr_values[i] > 0.0:
                calc_lot = dynamic_vol_risk / (initial_sl_atr_mult * atr_values[i] * point_value)
                active_lot = round(max(min_lot, min(max_lot, calc_lot)), 2)
            else:
                active_lot = lot_size

            if pos == 1:
                entry_price = opens[i + 1] + (spread * 0.5)
                current_sl = entry_price - (initial_sl_atr_mult * atr_values[i])
            else:
                entry_price = opens[i + 1] - (spread * 0.5)
                current_sl = entry_price + (initial_sl_atr_mult * atr_values[i])

    return trades

# -----------------------------------------------------------------------------
# Portfolio Analysis & Monte Carlo Engine (1,000 Runs)
# -----------------------------------------------------------------------------
def analyze_trades(all_trades, max_daily_loss=0.0, years=6.0):
    if not all_trades:
        return {
            "net_profit": 0.0, "pf": 0.0, "total_trades": 0, "annual_trades": 0.0,
            "max_dd": 1.0, "romad": 0.0, "win_rate": 0.0, "mcr": 0.0, "avg_trade": 0.0,
            "filtered_trades": []
        }

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
        return {
            "net_profit": 0.0, "pf": 0.0, "total_trades": 0, "annual_trades": 0.0,
            "max_dd": 1.0, "romad": 0.0, "win_rate": 0.0, "mcr": 0.0, "avg_trade": 0.0,
            "filtered_trades": []
        }

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

    total_months = max(1, int(years * 12.0))
    pos_m = sum(1 for v in m_dict.values() if v > 0)
    mcr = (pos_m / total_months) * 100.0

    return {
        "net_profit": total_net,
        "pf": pf,
        "total_trades": len(filtered_trades),
        "annual_trades": ann_tr,
        "max_dd": max_dd,
        "romad": romad,
        "win_rate": wr,
        "mcr": mcr,
        "avg_trade": avg_trade,
        "filtered_trades": filtered_trades
    }

def run_monte_carlo(trades, num_simulations=1000, initial_capital=10000.0):
    if not trades or len(trades) < 5:
        return {
            "mc_p50_dd": 0.0, "mc_p95_dd": 0.0, "mc_p99_dd": 0.0,
            "mc_p50_profit": 0.0, "mc_p5_profit": 0.0, "ruin_prob": 0.0,
            "max_consec_loss": 0
        }

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

            if (initial_capital + cum_equity + d) <= (initial_capital * 0.5):
                is_ruined = True

        mc_max_dds[s] = max_dd
        mc_net_profits[s] = cum_equity
        max_losing_streaks[s] = max_streak
        if is_ruined:
            ruin_count += 1

    return {
        "mc_p50_dd": float(np.percentile(mc_max_dds, 50)),
        "mc_p95_dd": float(np.percentile(mc_max_dds, 95)),
        "mc_p99_dd": float(np.percentile(mc_max_dds, 99)),
        "mc_p50_profit": float(np.percentile(mc_net_profits, 50)),
        "mc_p5_profit": float(np.percentile(mc_net_profits, 5)),
        "ruin_prob": (ruin_count / num_simulations) * 100.0,
        "max_consec_loss": int(np.percentile(max_losing_streaks, 95))
    }

# -----------------------------------------------------------------------------
# Main Execution Pipeline
# -----------------------------------------------------------------------------
def main():
    t_start = time.time()
    now_str = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')
    print("=" * 80)
    print("🚀 BATCH 54: WALK-FORWARD STABILITY, REGIME RESILIENCE & MONTE CARLO")
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
    print("[*] Computing Indicators, Kaufman Efficiency Ratios, and Volatility Expansion Ratios...")
    m15_atr14 = compute_atr(m15_highs, m15_lows, m15_closes, 14)
    m15_atr100 = compute_atr(m15_highs, m15_lows, m15_closes, 100)
    m15_vol_ratio = np.divide(m15_atr14, np.where(m15_atr100 > 0, m15_atr100, 1.0))
    m15_er14 = compute_efficiency_ratio(m15_closes, 14)
    m15_ema200 = compute_ema(m15_closes, 200)
    st_t30, st_b30 = compute_supertrend(m15_highs, m15_lows, m15_closes, m15_atr14, 3.0)

    # Precompute H1 with strict +1H shift
    h1_atr14 = compute_atr(h1_highs, h1_lows, h1_closes, 14)
    h1_tr30, h1_st30 = compute_supertrend(h1_highs, h1_lows, h1_closes, h1_atr14, 3.0)
    h1_ema200 = compute_ema(h1_closes, 200)

    df_h1_state = pd.DataFrame({
        "time": pd.to_datetime(df_h1.index) + pd.Timedelta(hours=1),
        "h1_tr": h1_tr30,
        "h1_st": h1_st30,
        "h1_ema": h1_ema200
    }).sort_values("time")

    df_m15_time = pd.DataFrame({"time": pd.to_datetime(df_m15.index)})
    m15_merged_h1 = pd.merge_asof(df_m15_time, df_h1_state, on="time", direction="backward")
    m15_h1_trend = m15_merged_h1["h1_tr"].fillna(1).values.astype(np.int32)
    m15_h1_st = m15_merged_h1["h1_st"].bfill().values.astype(np.float64)
    m15_h1_ema = m15_merged_h1["h1_ema"].bfill().values.astype(np.float64)

    # EURUSD Macro Gate
    eu_ema50 = compute_ema(eu_closes, 50)
    eu_trend = np.where(eu_closes > eu_ema50, 1, -1)
    df_eu_state = pd.DataFrame({"time": pd.to_datetime(df_eu.index), "eu_trend": eu_trend}).sort_values("time")
    m15_merged_eu = pd.merge_asof(df_m15_time, df_eu_state, on="time", direction="backward")
    m15_eu_trend = m15_merged_eu["eu_trend"].fillna(1).values.astype(np.int32)

    del df_h1, df_h1_state, df_eu, df_eu_state, m15_merged_h1, m15_merged_eu, df_m15_time
    gc.collect()

    print(f"[+] Synchronized {n_m15:,} M15 bars under strict causality.")

    # 3. Flexible Signal Generator
    def generate_regime_signals(session_start=7, session_end=17, min_atr=1.50, min_er=0.0, min_vr=0.0):
        sig = np.zeros(n_m15, dtype=np.int32)
        for i in range(200, n_m15 - 1):
            h = m15_dates[i].hour
            if session_start <= h <= session_end:
                if min_atr <= 0.0 or m15_atr14[i] >= min_atr:
                    if min_er > 0.0 and m15_er14[i] < min_er:
                        continue
                    if min_vr > 0.0 and m15_vol_ratio[i] < min_vr:
                        continue

                    if st_t30[i] == 1 and st_t30[i - 1] == -1 and m15_closes[i] > m15_ema200[i]:
                        if m15_h1_trend[i] == 1 and m15_eu_trend[i] == 1:
                            sig[i] = 1
                    elif st_t30[i] == -1 and st_t30[i - 1] == 1 and m15_closes[i] < m15_ema200[i]:
                        if m15_h1_trend[i] == -1 and m15_eu_trend[i] == -1:
                            sig[i] = -1
        return sig

    def generate_h1_macro_signals(session_start=7, session_end=17, min_er=0.0, min_vr=0.0):
        sig = np.zeros(n_m15, dtype=np.int32)
        for i in range(200, n_m15 - 1):
            h = m15_dates[i].hour
            if session_start <= h <= session_end and not (21 <= h < 23):
                if min_er > 0.0 and m15_er14[i] < min_er:
                    continue
                if min_vr > 0.0 and m15_vol_ratio[i] < min_vr:
                    continue

                if m15_h1_trend[i] == 1 and m15_h1_trend[i - 1] == -1 and m15_closes[i] > m15_h1_ema[i] and m15_eu_trend[i] == 1:
                    sig[i] = 1
                elif m15_h1_trend[i] == -1 and m15_h1_trend[i - 1] == 1 and m15_closes[i] < m15_h1_ema[i] and m15_eu_trend[i] == -1:
                    sig[i] = -1
        return sig

    # Engine runners
    def run_s700(min_er=0.0, min_vr=0.0, lot=0.10, dyn_risk=0.0, spread=0.25, comm=6.0, slip=0.10, swap=18.0, start=None, end=None):
        sig_m15 = generate_regime_signals(7, 17, 1.50, min_er=min_er, min_vr=min_vr)
        sig_h1 = generate_h1_macro_signals(7, 17, min_er=min_er, min_vr=min_vr)
        t1 = simulate_discrete_engine(m15_opens, m15_highs, m15_lows, m15_closes, m15_dates, sig_m15, m15_atr14, st_b30, "M15_Core", lot_size=lot, dynamic_vol_risk=dyn_risk, spread=spread, commission_per_lot=comm, sl_slippage=slip, swap_long_daily=swap, start_date=start, end_date=end)
        t2 = simulate_discrete_engine(m15_opens, m15_highs, m15_lows, m15_closes, m15_dates, sig_h1, m15_atr14, m15_h1_st, "H1_Core", lot_size=lot, dynamic_vol_risk=dyn_risk, spread=spread, commission_per_lot=comm, sl_slippage=slip, swap_long_daily=swap, start_date=start, end_date=end)
        return t1 + t2

    def run_s682(min_er=0.0, min_vr=0.0, lot=0.10, dyn_risk=0.0, spread=0.25, comm=6.0, slip=0.10, swap=18.0, start=None, end=None):
        sig_s682 = generate_regime_signals(6, 10, 1.50, min_er=min_er, min_vr=min_vr)
        return simulate_discrete_engine(m15_opens, m15_highs, m15_lows, m15_closes, m15_dates, sig_s682, m15_atr14, st_b30, "S682_London", lot_size=lot, dynamic_vol_risk=dyn_risk, spread=spread, commission_per_lot=comm, sl_slippage=slip, swap_long_daily=swap, start_date=start, end_date=end)

    # Date partitions for Walk-Forward
    dt_is_start = datetime(2020, 1, 1)
    dt_is_end   = datetime(2023, 12, 31, 23, 59, 59)
    dt_oos_start = datetime(2024, 1, 1)
    dt_oos_end   = datetime(2025, 12, 31, 23, 59, 59)

    # 4. Construct Strategy Definitions (S816 to S845)
    print("\n[+] Constructing 30 Strategies (S816 - S845)...")
    strategy_definitions = [
        # Group 1: Walk-Forward Multi-Year Stability (S816 - S825)
        ("S816", "S731 Dynamic Vol Risk $300 (Full 6Y)", lambda: run_s700(dyn_risk=300.0), 0.0, 6.0, "S731 Benchmark 6-Year"),
        ("S817", "S731 Dynamic Vol Risk $300 (In-Sample 2020-23)", lambda: run_s700(dyn_risk=300.0, start=dt_is_start, end=dt_is_end), 0.0, 4.0, "S731 In-Sample Audit (48 Mo)"),
        ("S818", "S731 Dynamic Vol Risk $300 (Out-Sample 2024-25)", lambda: run_s700(dyn_risk=300.0, start=dt_oos_start, end=dt_oos_end), 0.0, 2.0, "S731 Out-of-Sample Audit (24 Mo)"),

        ("S819", "S809 Dual Sovereign VR 1.10 (Full 6Y)", lambda: run_s700(min_vr=1.10, lot=0.07) + run_s682(min_vr=1.10, lot=0.07), 160.0, 6.0, "S809 Regime Master 6-Year"),
        ("S820", "S809 Dual Sovereign VR 1.10 (In-Sample 2020-23)", lambda: run_s700(min_vr=1.10, lot=0.07, start=dt_is_start, end=dt_is_end) + run_s682(min_vr=1.10, lot=0.07, start=dt_is_start, end=dt_is_end), 160.0, 4.0, "S809 In-Sample Audit (48 Mo)"),
        ("S821", "S809 Dual Sovereign VR 1.10 (Out-Sample 2024-25)", lambda: run_s700(min_vr=1.10, lot=0.07, start=dt_oos_start, end=dt_oos_end) + run_s682(min_vr=1.10, lot=0.07, start=dt_oos_start, end=dt_oos_end), 160.0, 2.0, "S809 Out-of-Sample Audit (24 Mo)"),

        ("S822", "S802 Early London VR 1.10 (Full 6Y)", lambda: run_s682(min_vr=1.10, lot=0.10), 0.0, 6.0, "S802 Sniper 6-Year (PF 2.934)"),
        ("S823", "S802 Early London VR 1.10 (In-Sample 2020-23)", lambda: run_s682(min_vr=1.10, lot=0.10, start=dt_is_start, end=dt_is_end), 0.0, 4.0, "S802 In-Sample Audit (48 Mo)"),
        ("S824", "S802 Early London VR 1.10 (Out-Sample 2024-25)", lambda: run_s682(min_vr=1.10, lot=0.10, start=dt_oos_start, end=dt_oos_end), 0.0, 2.0, "S802 Out-of-Sample Audit (24 Mo)"),

        ("S825", "S814 Centennial ER 0.30 + Dyn $300 (OOS)", lambda: run_s700(min_er=0.30, dyn_risk=300.0, start=dt_oos_start, end=dt_oos_end), 180.0, 2.0, "S814 Out-of-Sample Audit (24 Mo)"),

        # Group 2: Friction Shocks & Multi-Crisis Stress Testing (S826 - S835)
        ("S826", "S731 Dynamic Vol (Spread $0.40, Comm $8)", lambda: run_s700(dyn_risk=300.0, spread=0.40, comm=8.0, slip=0.15, swap=24.0), 0.0, 6.0, "Elevated Friction Stress Test"),
        ("S827", "S731 Dynamic Vol (Spread $0.50, Comm $10)", lambda: run_s700(dyn_risk=300.0, spread=0.50, comm=10.0, slip=0.25, swap=30.0), 0.0, 6.0, "Liquidity Shock Stress Test"),
        ("S828", "S731 Dynamic Vol (Crisis Shock: Spread $0.75)", lambda: run_s700(dyn_risk=300.0, spread=0.75, comm=12.0, slip=0.35, swap=36.0), 0.0, 6.0, "Crisis Volatility Stress Test"),

        ("S829", "S809 Regime Master (Spread $0.40, Comm $8)", lambda: run_s700(min_vr=1.10, lot=0.07, spread=0.40, comm=8.0, slip=0.15, swap=24.0) + run_s682(min_vr=1.10, lot=0.07, spread=0.40, comm=8.0, slip=0.15, swap=24.0), 160.0, 6.0, "S809 Elevated Friction Stress"),
        ("S830", "S809 Regime Master (Spread $0.50, Comm $10)", lambda: run_s700(min_vr=1.10, lot=0.07, spread=0.50, comm=10.0, slip=0.25, swap=30.0) + run_s682(min_vr=1.10, lot=0.07, spread=0.50, comm=10.0, slip=0.25, swap=30.0), 160.0, 6.0, "S809 Liquidity Shock Stress"),
        ("S831", "S809 Regime Master (Crisis Shock: Spread $0.75)", lambda: run_s700(min_vr=1.10, lot=0.07, spread=0.75, comm=12.0, slip=0.35, swap=36.0) + run_s682(min_vr=1.10, lot=0.07, spread=0.75, comm=12.0, slip=0.35, swap=36.0), 160.0, 6.0, "S809 Crisis Volatility Stress"),

        ("S832", "S802 London Sniper (Spread $0.40, Comm $8)", lambda: run_s682(min_vr=1.10, lot=0.10, spread=0.40, comm=8.0, slip=0.15, swap=24.0), 0.0, 6.0, "S802 Elevated Friction Stress"),
        ("S833", "S802 London Sniper (Spread $0.50, Comm $10)", lambda: run_s682(min_vr=1.10, lot=0.10, spread=0.50, comm=10.0, slip=0.25, swap=30.0), 0.0, 6.0, "S802 Liquidity Shock Stress"),
        ("S834", "S802 London Sniper (Crisis Shock: Spread $0.75)", lambda: run_s682(min_vr=1.10, lot=0.10, spread=0.75, comm=12.0, slip=0.35, swap=36.0), 0.0, 6.0, "S802 Crisis Volatility Stress"),

        ("S835", "Dual Sovereign + Dynamic Risk $250", lambda: run_s700(min_vr=1.10, dyn_risk=150.0) + run_s682(min_vr=1.10, dyn_risk=100.0), 180.0, 6.0, "Dual Sovereign Dynamic Sizing Suite"),

        # Group 3: Sovereign Synthesis, Multi-Pillar Architecture & Ensembles (S836 - S845)
        ("S836", "Balanced Sovereign (S731 DynVol + S809 Regime)", lambda: run_s700(dyn_risk=200.0) + run_s700(min_vr=1.10, lot=0.05) + run_s682(min_vr=1.10, lot=0.05), 200.0, 6.0, "Balanced Sovereign Synthesis"),
        ("S837", "Tri-Pillar Sovereign Architecture", lambda: run_s700(dyn_risk=200.0) + run_s700(min_vr=1.10, lot=0.05) + run_s682(min_vr=1.10, lot=0.08), 220.0, 6.0, "Tri-Pillar Sovereign (Core+Regime+Sniper)"),
        ("S838", "Governed Sovereign Trinity ($180 Gov)", lambda: run_s700(dyn_risk=200.0) + run_s700(min_vr=1.10, lot=0.05) + run_s682(min_vr=1.10, lot=0.08), 180.0, 6.0, "Conservative Joint Governor $180"),
        ("S839", "Governed Sovereign Trinity ($240 Gov)", lambda: run_s700(dyn_risk=200.0) + run_s700(min_vr=1.10, lot=0.05) + run_s682(min_vr=1.10, lot=0.08), 240.0, 6.0, "Moderate Joint Governor $240"),
        ("S840", "Governed Sovereign Trinity ($300 Gov)", lambda: run_s700(dyn_risk=200.0) + run_s700(min_vr=1.10, lot=0.05) + run_s682(min_vr=1.10, lot=0.08), 300.0, 6.0, "Growth Joint Governor $300"),

        ("S841", "Prop-Firm Low-Drawdown Master ($140 Gov)", lambda: run_s700(min_vr=1.10, lot=0.05) + run_s682(min_vr=1.10, lot=0.05), 140.0, 6.0, "Prop-Firm Conservative Master"),
        ("S842", "High-Expectancy Titan Suite ($350 DynVol)", lambda: run_s700(dyn_risk=350.0) + run_s682(min_vr=1.10, lot=0.10), 250.0, 6.0, "Titan High-Expectancy Suite"),
        ("S843", "Adaptive Multi-Regime Volatility Master", lambda: run_s700(min_vr=1.05, lot=0.07) + run_s682(min_vr=1.15, lot=0.07), 160.0, 6.0, "Adaptive Dual VR Master"),
        ("S844", "Non-Stationary Regime Shield (ER+VR Dual)", lambda: run_s700(min_er=0.25, min_vr=1.10, lot=0.07) + run_s682(min_er=0.25, min_vr=1.10, lot=0.07), 160.0, 6.0, "Joint ER & VR Dual Shield"),
        ("S845", "Centennial Sovereign Millennium Monument 2026", lambda: run_s700(min_er=0.25, min_vr=1.05, dyn_risk=220.0) + run_s682(min_vr=1.10, lot=0.08), 220.0, 6.0, "Flagship Centennial Monument 2026")
    ]

    # 5. Execute and Evaluate All Strategies
    results_table = []
    print("\n" + "=" * 145)
    print(f"{'ID':<6} {'Strategy Name':<42} {'Ann.Tr':<8} {'Tot.Tr':<8} {'Net PnL ($)':<14} {'PF':<8} {'WR%':<8} {'Intra DD ($)':<14} {'MC P95 DD':<12} {'Ruin%':<8} {'RoMaD':<8}")
    print("=" * 145)

    for sid, name, fn, gov, span_years, role in strategy_definitions:
        trades = fn()
        m = analyze_trades(trades, max_daily_loss=gov, years=span_years)
        mc = run_monte_carlo(m["filtered_trades"], num_simulations=1000, initial_capital=10000.0)

        row = {
            "Strategy_ID": sid,
            "Strategy_Name": name,
            "Role": role,
            "Span_Years": span_years,
            "Annual_Trades": round(m["annual_trades"], 1),
            "Total_Trades": m["total_trades"],
            "Net_Profit": round(m["net_profit"], 2),
            "Profit_Factor": round(m["pf"], 3),
            "Win_Rate_Pct": round(m["win_rate"], 1),
            "True_Intra_Max_DD": round(m["max_dd"], 2),
            "RoMaD": round(m["romad"], 2),
            "MCR_Pct": round(m["mcr"], 1),
            "Avg_Trade_PnL": round(m["avg_trade"], 2),
            "MC_P50_DD": round(mc["mc_p50_dd"], 2),
            "MC_P95_DD": round(mc["mc_p95_dd"], 2),
            "MC_P99_DD": round(mc["mc_p99_dd"], 2),
            "MC_P50_Profit": round(mc["mc_p50_profit"], 2),
            "MC_P5_Profit": round(mc["mc_p5_profit"], 2),
            "Ruin_Probability_Pct": round(mc["ruin_prob"], 2),
            "Max_Consec_Losses": mc["max_consec_loss"]
        }
        results_table.append(row)

        print(f"{sid:<6} {name:<42} {row['Annual_Trades']:<8.1f} {row['Total_Trades']:<8} ${row['Net_Profit']:<13.2f} {row['Profit_Factor']:<8.3f} {row['Win_Rate_Pct']:<7.1f}% ${row['True_Intra_Max_DD']:<13.2f} ${row['MC_P95_DD']:<11.2f} {row['Ruin_Probability_Pct']:<7.2f}% {row['RoMaD']:<8.2f}x")

    # 6. Save Matrix Results
    csv_path = os.path.join(RESULTS_DIR, "batch_54_walk_forward_resilience_matrix.csv")
    json_path = os.path.join(RESULTS_DIR, "batch_54_walk_forward_resilience_results.json")

    df_res = pd.DataFrame(results_table)
    df_res.to_csv(csv_path, index=False)

    with open(json_path, "w") as f:
        json.dump(results_table, f, indent=2)

    elapsed = time.time() - t_start
    print("=" * 145)
    print(f"\n[+] Batch 54 Execution Completed in {elapsed:.2f} seconds.")
    print(f"[+] Saved Matrix CSV: {csv_path}")
    print(f"[+] Saved Results JSON: {json_path}")

if __name__ == "__main__":
    main()
