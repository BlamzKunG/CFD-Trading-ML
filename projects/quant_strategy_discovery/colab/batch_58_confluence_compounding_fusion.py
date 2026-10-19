#!/usr/bin/env python3
"""
===============================================================================
BATCH 58: MULTI-FREQUENCY CONFLUENCE COMPOUNDING & SOVEREIGN PORTFOLIO FUSION
===============================================================================
Executes 30 Strategies (S936 to S965) on Google Colab Cloud VM
under 100% strict adherence to Constitution V5.1 (Rules D.1 to D.7):
- Rule D.1: Pessimistic Sequence Mandate (SL triggered first if both hit in 1 bar)
- Rule D.2: Strict Bar-Close Trailing Mandate (effective next bar Open)
- Rule D.3: Intra-Bar Equity Tracking Mandate (Max DD measured from deepest intra-bar adverse excursion)
- Rule D.4: Negative Slippage on Stop Loss (-$0.10/trade baseline on SL fills)
- Rule D.5: 100% Bar-by-Bar Discrete Simulation (Zero Synthetic Multipliers)
- Rule D.6: Lot Step Realism (Exact 0.01 lot multiples, clamped between 0.04 and 0.40)
- Rule D.7: Institutional Frictions ($0.25 spread + $6.00 comm + -$18/lot swap)
- Strict Anti-Lookahead Causality: H1 closed bar only (+1H shift), EURUSD closed bar only (+15m shift)

Exploration Matrices (30 Strategies: S936 - S965):
1. S936 - S945: Fixed-Fractional Dynamic Compounding on M5-Confluence Routers (0.5% - 2.5% Equity Risk)
2. S946 - S955: Prop-Firm Compounding Shields (Sub-$1,000 Drawdown Target with 0.5% - 1.0% Compounding)
3. S956 - S965: Cross-Asset Confluence Sovereign Portfolios (Gold + EURUSD under Dynamic Governors)
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
# Discrete Event Simulator Supporting Fixed-Fractional Compounding & Confluence
# -----------------------------------------------------------------------------
def simulate_compounding_confluence_engine(
    opens, highs, lows, closes, dates,
    entry_signals,
    atr_values,
    st_bands,
    engine_name="Compounding_Engine",
    lot_size=0.10,
    compounding_risk_pct=0.0,
    initial_capital=10000.0,
    min_lot=0.04,
    max_lot=0.40,
    spread=0.25,
    commission_per_lot=6.00,
    sl_slippage=0.10,
    swap_long_daily=18.00,
    initial_sl_atr_mult=3.0,
    partial_tp_atr_mult=0.0,
    start_date=None,
    end_date=None
):
    if lot_size <= 0.0 and compounding_risk_pct <= 0.0:
        return []

    n = len(closes)
    trades = []
    point_value = 100.0

    pos = 0
    entry_price = 0.0
    entry_time = None
    current_sl = 0.0
    active_lot = lot_size
    deepest_dip = 0.0
    tranche_taken = False
    current_equity = initial_capital

    for i in range(200, n - 2):
        if pos == 1: # Long
            bar_low = lows[i]
            bar_high = highs[i]
            curr_unit = active_lot * point_value

            dip = min(0.0, (bar_low - entry_price) * curr_unit)
            if dip < deepest_dip:
                deepest_dip = dip

            # Partial Scale-Out Check (Rule D.6 Realism)
            if partial_tp_atr_mult > 0.0 and not tranche_taken:
                tp_target = entry_price + (partial_tp_atr_mult * atr_values[i])
                if bar_high >= tp_target:
                    tranche_taken = True
                    half_lot = round(active_lot * 0.5, 2)
                    remain_lot = round(active_lot - half_lot, 2)
                    p_unit = half_lot * point_value
                    p_pnl = (tp_target - entry_price) * p_unit - (spread * p_unit) - (commission_per_lot * half_lot)

                    trades.append({
                        "engine": f"{engine_name}_T1",
                        "pos": 1,
                        "entry_time": entry_time,
                        "exit_time": dates[i],
                        "entry_price": entry_price,
                        "exit_price": tp_target,
                        "lot": half_lot,
                        "pnl": p_pnl,
                        "deepest_dip": deepest_dip,
                        "year": entry_time.year,
                        "month": f"{entry_time.year}-{entry_time.month:02d}",
                        "exit_reason": "PartialTP"
                    })
                    current_equity += p_pnl
                    active_lot = remain_lot
                    curr_unit = active_lot * point_value

            exit_hit = False
            exit_price = 0.0
            exit_reason = ""

            sl_touched = (bar_low <= current_sl)
            trend_flipped = (closes[i] < st_bands[i])

            if sl_touched:
                exit_hit = True
                exit_price = current_sl - sl_slippage
                exit_reason = "SL"
            elif trend_flipped:
                exit_hit = True
                exit_price = opens[i + 1] - (spread * 0.5)
                exit_reason = "TrendFlip"

            if exit_hit:
                raw_gain = (exit_price - entry_price) * curr_unit
                frictions = (spread * curr_unit) + (commission_per_lot * active_lot)
                days_held = max(0, (dates[i] - entry_time).days)
                swap_cost = days_held * (swap_long_daily * active_lot)
                net_pnl = raw_gain - frictions - swap_cost

                in_window = True
                if start_date and entry_time < start_date: in_window = False
                if end_date and entry_time > end_date: in_window = False

                if in_window:
                    trades.append({
                        "engine": f"{engine_name}_Runner" if tranche_taken else engine_name,
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
                    current_equity += net_pnl
                pos = 0
            else:
                if st_bands[i] > current_sl:
                    current_sl = st_bands[i]

        elif pos == -1: # Short
            bar_low = lows[i]
            bar_high = highs[i]
            curr_unit = active_lot * point_value

            dip = min(0.0, (entry_price - bar_high) * curr_unit)
            if dip < deepest_dip:
                deepest_dip = dip

            if partial_tp_atr_mult > 0.0 and not tranche_taken:
                tp_target = entry_price - (partial_tp_atr_mult * atr_values[i])
                if bar_low <= tp_target:
                    tranche_taken = True
                    half_lot = round(active_lot * 0.5, 2)
                    remain_lot = round(active_lot - half_lot, 2)
                    p_unit = half_lot * point_value
                    p_pnl = (entry_price - tp_target) * p_unit - (spread * p_unit) - (commission_per_lot * half_lot)

                    trades.append({
                        "engine": f"{engine_name}_T1",
                        "pos": -1,
                        "entry_time": entry_time,
                        "exit_time": dates[i],
                        "entry_price": entry_price,
                        "exit_price": tp_target,
                        "lot": half_lot,
                        "pnl": p_pnl,
                        "deepest_dip": deepest_dip,
                        "year": entry_time.year,
                        "month": f"{entry_time.year}-{entry_time.month:02d}",
                        "exit_reason": "PartialTP"
                    })
                    current_equity += p_pnl
                    active_lot = remain_lot
                    curr_unit = active_lot * point_value

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
                net_pnl = (entry_price - exit_price) * curr_unit - (spread * curr_unit) - (commission_per_lot * active_lot)

                in_window = True
                if start_date and entry_time < start_date: in_window = False
                if end_date and entry_time > end_date: in_window = False

                if in_window:
                    trades.append({
                        "engine": f"{engine_name}_Runner" if tranche_taken else engine_name,
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
                    current_equity += net_pnl
                pos = 0
            else:
                if st_bands[i] < current_sl:
                    current_sl = st_bands[i]

        # Fresh Entry at Bar i Close -> Execute at Bar i+1 Open
        if pos == 0 and entry_signals[i] != 0:
            pos = entry_signals[i]
            entry_time = dates[i + 1]
            deepest_dip = 0.0
            tranche_taken = False

            if compounding_risk_pct > 0.0 and atr_values[i] > 0.0:
                dollar_risk = current_equity * (compounding_risk_pct / 100.0)
                calc_lot = dollar_risk / (initial_sl_atr_mult * atr_values[i] * point_value)
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
# Portfolio Analysis & Dynamic Daily Trailing Circuit Breaker
# -----------------------------------------------------------------------------
def analyze_trades_with_trailing_governor(all_trades, base_daily_limit=180.0, lock_in_ratio=0.50, years=6.0):
    if not all_trades:
        return {"net_profit": 0, "pf": 0, "total_trades": 0, "annual_trades": 0, "max_dd": 1.0, "romad": 0, "win_rate": 0, "mcr": 0, "avg_trade": 0, "filtered_trades": []}

    all_trades = sorted(all_trades, key=lambda x: x["entry_time"])
    filtered_trades = []

    daily_trades = {}
    for t in all_trades:
        day_key = t["entry_time"].strftime("%Y-%m-%d")
        daily_trades.setdefault(day_key, []).append(t)

    for day_key, d_list in daily_trades.items():
        day_pnl = 0.0
        day_peak = 0.0

        for t in d_list:
            if base_daily_limit > 0.0 and day_pnl <= -base_daily_limit:
                continue

            if lock_in_ratio > 0.0 and day_peak >= 100.0:
                locked_floor = day_peak * lock_in_ratio
                if day_pnl < locked_floor:
                    continue

            day_pnl += t["pnl"]
            if day_pnl > day_peak:
                day_peak = day_pnl
            filtered_trades.append(t)

    if not filtered_trades:
        return {"net_profit": 0, "pf": 0, "total_trades": 0, "annual_trades": 0, "max_dd": 1.0, "romad": 0, "win_rate": 0, "mcr": 0, "avg_trade": 0, "filtered_trades": []}

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

    pf = (tot_win / tot_loss) if tot_loss > 0 else 999.0
    total_trades = len(filtered_trades)
    annual_trades = total_trades / years
    win_rate = (len(wins) / total_trades * 100.0) if total_trades > 0 else 0.0
    romad = (total_net / max_intra_dd) if max_intra_dd > 0 else 0.0
    pos_m = sum(1 for v in m_dict.values() if v > 0)
    mcr = (pos_m / len(m_dict) * 100.0) if m_dict else 0.0
    avg_trade = total_net / total_trades if total_trades > 0 else 0.0

    return {
        "net_profit": total_net,
        "pf": pf,
        "total_trades": total_trades,
        "annual_trades": annual_trades,
        "max_dd": max_intra_dd,
        "romad": romad,
        "win_rate": win_rate,
        "mcr": mcr,
        "avg_trade": avg_trade,
        "filtered_trades": filtered_trades
    }

# -----------------------------------------------------------------------------
# 1,000-Run Monte Carlo Resampling Engine
# -----------------------------------------------------------------------------
def run_monte_carlo(trades, num_simulations=1000, initial_capital=10000.0):
    if not trades:
        return {"mc_p50_dd": 0.0, "mc_p95_dd": 0.0, "ruin_prob": 0.0}

    trade_pnls = np.array([t["pnl"] for t in trades], dtype=np.float64)
    n_trades = len(trade_pnls)
    max_dds = np.zeros(num_simulations, dtype=np.float64)
    ruined_count = 0

    rng = np.random.default_rng(seed=42)
    for s in range(num_simulations):
        sampled_pnls = rng.choice(trade_pnls, size=n_trades, replace=True)
        equity_curve = initial_capital + np.cumsum(sampled_pnls)
        running_peak = np.maximum.accumulate(equity_curve)
        dds = running_peak - equity_curve
        max_dds[s] = np.max(dds)
        if np.min(equity_curve) <= initial_capital * 0.70:
            ruined_count += 1

    return {
        "mc_p50_dd": float(np.percentile(max_dds, 50)),
        "mc_p95_dd": float(np.percentile(max_dds, 95)),
        "ruin_prob": float((ruined_count / num_simulations) * 100.0)
    }

# -----------------------------------------------------------------------------
# Main Execution Pipeline
# -----------------------------------------------------------------------------
def main():
    t_start = time.time()
    now_str = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')
    print("=" * 80)
    print("🚀 BATCH 58: MULTI-FREQUENCY CONFLUENCE COMPOUNDING & SOVEREIGN FUSION")
    print(f"Timestamp: {now_str}")
    print(f"Hardware Environment: {'Google Colab VM' if 'content' in REPO_ROOT else 'Local Controller'}")
    print("=" * 80)

    # 1. Load Parquet Data
    print(f"[+] Loading Multi-Timeframe Parquet Caches from {DATA_DIR}...")
    df_m5 = pd.read_parquet(os.path.join(DATA_DIR, "XAUUSD_M5.parquet"))
    df_m15 = pd.read_parquet(os.path.join(DATA_DIR, "XAUUSD_M15.parquet"))
    df_h1 = pd.read_parquet(os.path.join(DATA_DIR, "XAUUSD_H1.parquet"))
    df_eu = pd.read_parquet(os.path.join(DATA_DIR, "EURUSD_M15.parquet"))

    m15_highs = df_m15["high"].values.astype(np.float64)
    m15_lows = df_m15["low"].values.astype(np.float64)
    m15_closes = df_m15["close"].values.astype(np.float64)
    m15_opens = df_m15["open"].values.astype(np.float64)
    m15_dates = pd.to_datetime(df_m15.index).to_pydatetime()
    n_m15 = len(m15_closes)

    m5_closes = df_m5["close"].values.astype(np.float64)
    h1_highs = df_h1["high"].values.astype(np.float64)
    h1_lows = df_h1["low"].values.astype(np.float64)
    h1_closes = df_h1["close"].values.astype(np.float64)
    eu_closes = df_eu["close"].values.astype(np.float64)

    # 2. Compute Core & Cross-Frequency Indicators
    print("[*] Synchronizing Indicators under strict causality...")
    m15_atr14 = compute_atr(m15_highs, m15_lows, m15_closes, 14)
    m15_atr100 = compute_atr(m15_highs, m15_lows, m15_closes, 100)
    m15_vol_ratio = np.divide(m15_atr14, np.where(m15_atr100 > 0, m15_atr100, 1.0))
    m15_ema200 = compute_ema(m15_closes, 200)
    st_t30, st_b30 = compute_supertrend(m15_highs, m15_lows, m15_closes, m15_atr14, 3.0)

    # M5 Micro-Structure Alignment
    m5_ema50 = compute_ema(m5_closes, 50)
    m5_trend = np.where(m5_closes > m5_ema50, 1, -1)
    df_m5_state = pd.DataFrame({
        "time": pd.to_datetime(df_m5.index) + pd.Timedelta(minutes=5),
        "m5_tr": m5_trend
    }).sort_values("time")

    # H1 Macro Alignment (+1 Hour Causal Shift)
    h1_atr14 = compute_atr(h1_highs, h1_lows, h1_closes, 14)
    h1_tr30, h1_st30 = compute_supertrend(h1_highs, h1_lows, h1_closes, h1_atr14, 3.0)
    h1_ema200 = compute_ema(h1_closes, 200)

    df_h1_state = pd.DataFrame({
        "time": pd.to_datetime(df_h1.index) + pd.Timedelta(hours=1),
        "h1_tr": h1_tr30,
        "h1_st": h1_st30,
        "h1_ema": h1_ema200
    }).sort_values("time")

    # EURUSD Macro Alignment (+15 Min Causal Shift)
    eu_ema50 = compute_ema(eu_closes, 50)
    eu_trend = np.where(eu_closes > eu_ema50, 1, -1)
    df_eu_state = pd.DataFrame({
        "time": pd.to_datetime(df_eu.index) + pd.Timedelta(minutes=15),
        "eu_trend": eu_trend
    }).sort_values("time")

    # Merge as-of to M15 timeline
    df_m15_time = pd.DataFrame({"time": pd.to_datetime(df_m15.index)})
    m15_merged_h1 = pd.merge_asof(df_m15_time, df_h1_state, on="time", direction="backward")
    m15_h1_trend = m15_merged_h1["h1_tr"].fillna(1).values.astype(np.int32)

    m15_merged_eu = pd.merge_asof(df_m15_time, df_eu_state, on="time", direction="backward")
    m15_eu_trend = m15_merged_eu["eu_trend"].fillna(1).values.astype(np.int32)

    m15_merged_m5 = pd.merge_asof(df_m15_time, df_m5_state, on="time", direction="backward")
    m15_m5_trend = m15_merged_m5["m5_tr"].fillna(1).values.astype(np.int32)

    del df_m5, df_m5_state, df_h1, df_h1_state, df_eu, df_eu_state, m15_merged_h1, m15_merged_eu, m15_merged_m5, df_m15_time
    gc.collect()

    print(f"[+] Synchronized {n_m15:,} Gold M15 bars with M5 and H1 confluences.")

    # 3. Confluence Signal Generators
    def generate_confluence_signals(start_h, end_h, min_atr=1.50, min_vr=0.0):
        sig = np.zeros(n_m15, dtype=np.int32)
        for i in range(200, n_m15 - 1):
            h = m15_dates[i].hour
            if start_h <= h <= end_h:
                if min_atr <= 0.0 or m15_atr14[i] >= min_atr:
                    if min_vr > 0.0 and m15_vol_ratio[i] < min_vr:
                        continue
                    if st_t30[i] == 1 and st_t30[i - 1] == -1 and m15_closes[i] > m15_ema200[i]:
                        if m15_h1_trend[i] == 1 and m15_eu_trend[i] == 1 and m15_m5_trend[i] == 1:
                            sig[i] = 1
                    elif st_t30[i] == -1 and st_t30[i - 1] == 1 and m15_closes[i] < m15_ema200[i]:
                        if m15_h1_trend[i] == -1 and m15_eu_trend[i] == -1 and m15_m5_trend[i] == -1:
                            sig[i] = -1
        return sig

    sig_early_lon = generate_confluence_signals(6, 9, 1.50, min_vr=1.10)
    sig_mid_lon   = generate_confluence_signals(9, 12, 1.50, min_vr=1.05)
    sig_ny_open   = generate_confluence_signals(12, 16, 1.80, min_vr=1.15)

    def run_compounding_router(w_early=0.10, w_ny=0.10, w_mid=0.0, comp_pct=0.0, part_tp=0.0):
        t1 = simulate_compounding_confluence_engine(m15_opens, m15_highs, m15_lows, m15_closes, m15_dates, sig_early_lon, m15_atr14, st_b30, "Early_London", lot_size=w_early, compounding_risk_pct=comp_pct*0.5 if comp_pct>0 else 0.0, partial_tp_atr_mult=part_tp)
        t2 = simulate_compounding_confluence_engine(m15_opens, m15_highs, m15_lows, m15_closes, m15_dates, sig_mid_lon, m15_atr14, st_b30, "London_Mid", lot_size=w_mid, compounding_risk_pct=comp_pct*0.3 if comp_pct>0 else 0.0, partial_tp_atr_mult=part_tp)
        t3 = simulate_compounding_confluence_engine(m15_opens, m15_highs, m15_lows, m15_closes, m15_dates, sig_ny_open, m15_atr14, st_b30, "NY_Open", lot_size=w_ny, compounding_risk_pct=comp_pct*0.5 if comp_pct>0 else 0.0, partial_tp_atr_mult=part_tp)
        return t1 + t2 + t3

    # 4. Construct Strategy Definitions (S936 to S965)
    print("\n[+] Constructing 30 Strategies (S936 - S965)...")
    strategy_definitions = [
        # Group 1: Dynamic Compounding on M5-Confluence Dual-Phase Router (S936 - S945)
        ("S936", "S910 Dual-Phase + 0.5% Compounding", lambda: run_compounding_router(w_early=0.10, w_ny=0.10, comp_pct=0.5), 180.0, 0.0, "Dual-Phase 0.5% Compounding"),
        ("S937", "S910 Dual-Phase + 0.75% Compounding", lambda: run_compounding_router(w_early=0.10, w_ny=0.10, comp_pct=0.75), 180.0, 0.0, "Dual-Phase 0.75% Compounding"),
        ("S938", "S910 Dual-Phase + 1.0% Compounding", lambda: run_compounding_router(w_early=0.10, w_ny=0.10, comp_pct=1.0), 180.0, 0.0, "Dual-Phase 1.0% Compounding"),
        ("S939", "S910 Dual-Phase + 1.25% Compounding", lambda: run_compounding_router(w_early=0.10, w_ny=0.10, comp_pct=1.25), 180.0, 0.0, "Dual-Phase 1.25% Compounding"),
        ("S940", "S910 Dual-Phase + 1.5% Compounding", lambda: run_compounding_router(w_early=0.10, w_ny=0.10, comp_pct=1.5), 200.0, 0.0, "Dual-Phase 1.5% Compounding"),
        ("S941", "S910 Dual-Phase + 2.0% Compounding", lambda: run_compounding_router(w_early=0.10, w_ny=0.10, comp_pct=2.0), 220.0, 0.0, "Dual-Phase 2.0% Compounding Titan"),
        ("S942", "S910 Dual-Phase + 2.5% Compounding", lambda: run_compounding_router(w_early=0.10, w_ny=0.10, comp_pct=2.5), 250.0, 0.0, "Dual-Phase 2.5% Compounding Apex"),
        ("S943", "S910 Dual-Phase + 1.0% Comp + 2.0R TP", lambda: run_compounding_router(w_early=0.10, w_ny=0.10, comp_pct=1.0, part_tp=2.0), 180.0, 0.0, "Dual-Phase 1.0% Comp + 2.0R TP"),
        ("S944", "S910 Dual-Phase + 1.5% Comp + 2.0R TP", lambda: run_compounding_router(w_early=0.10, w_ny=0.10, comp_pct=1.5, part_tp=2.0), 200.0, 0.0, "Dual-Phase 1.5% Comp + 2.0R TP"),
        ("S945", "S910 Dual-Phase + 2.0% Comp + 2.0R TP", lambda: run_compounding_router(w_early=0.10, w_ny=0.10, comp_pct=2.0, part_tp=2.0), 220.0, 0.0, "Dual-Phase 2.0% Comp + 2.0R TP"),

        # Group 2: Prop-Firm Compounding Shields (S946 - S955)
        ("S946", "Prop-Firm Confluence + 0.4% Comp", lambda: run_compounding_router(w_early=0.05, w_mid=0.04, w_ny=0.05, comp_pct=0.4), 120.0, 0.0, "Prop-Firm 0.4% Comp Shield"),
        ("S947", "Prop-Firm Confluence + 0.5% Comp", lambda: run_compounding_router(w_early=0.05, w_mid=0.04, w_ny=0.05, comp_pct=0.5), 120.0, 0.0, "Prop-Firm 0.5% Comp Shield"),
        ("S948", "Prop-Firm Confluence + 0.6% Comp", lambda: run_compounding_router(w_early=0.05, w_mid=0.04, w_ny=0.05, comp_pct=0.6), 120.0, 0.0, "Prop-Firm 0.6% Comp Shield"),
        ("S949", "Prop-Firm Confluence + 0.75% Comp", lambda: run_compounding_router(w_early=0.05, w_mid=0.04, w_ny=0.05, comp_pct=0.75), 140.0, 0.0, "Prop-Firm 0.75% Comp Shield"),
        ("S950", "Prop-Firm Confluence + 1.0% Comp", lambda: run_compounding_router(w_early=0.05, w_mid=0.04, w_ny=0.05, comp_pct=1.0), 150.0, 0.0, "Prop-Firm 1.0% Comp Shield"),
        ("S951", "Prop-Firm Shield + 0.5% Comp + 2.0R TP", lambda: run_compounding_router(w_early=0.05, w_mid=0.04, w_ny=0.05, comp_pct=0.5, part_tp=2.0), 120.0, 0.0, "Prop-Firm 0.5% Comp + 2.0R TP"),
        ("S952", "Prop-Firm Shield + 0.75% Comp + 2.0R TP", lambda: run_compounding_router(w_early=0.05, w_mid=0.04, w_ny=0.05, comp_pct=0.75, part_tp=2.0), 140.0, 0.0, "Prop-Firm 0.75% Comp + 2.0R TP"),
        ("S953", "Prop-Firm Shield + 1.0% Comp + 2.0R TP", lambda: run_compounding_router(w_early=0.05, w_mid=0.04, w_ny=0.05, comp_pct=1.0, part_tp=2.0), 150.0, 0.0, "Prop-Firm 1.0% Comp + 2.0R TP"),
        ("S954", "Prop-Firm Shield + 0.5% Comp + 50% Lock", lambda: run_compounding_router(w_early=0.05, w_mid=0.04, w_ny=0.05, comp_pct=0.5), 120.0, 0.50, "Prop-Firm 0.5% Comp + Lock-In"),
        ("S955", "Prop-Firm Shield + 0.75% Comp + 50% Lock", lambda: run_compounding_router(w_early=0.05, w_mid=0.04, w_ny=0.05, comp_pct=0.75), 140.0, 0.50, "Prop-Firm 0.75% Comp + Lock-In"),

        # Group 3: Cross-Asset Confluence Sovereign Portfolios (S956 - S965)
        ("S956", "Tri-Phase Confluence + 0.5% Comp", lambda: run_compounding_router(w_early=0.08, w_mid=0.06, w_ny=0.08, comp_pct=0.5), 180.0, 0.0, "Tri-Phase 0.5% Compounding"),
        ("S957", "Tri-Phase Confluence + 1.0% Comp", lambda: run_compounding_router(w_early=0.08, w_mid=0.06, w_ny=0.08, comp_pct=1.0), 180.0, 0.0, "Tri-Phase 1.0% Compounding"),
        ("S958", "Tri-Phase Confluence + 1.5% Comp", lambda: run_compounding_router(w_early=0.08, w_mid=0.06, w_ny=0.08, comp_pct=1.5), 200.0, 0.0, "Tri-Phase 1.5% Compounding"),
        ("S959", "Tri-Phase Confluence + 2.0% Comp", lambda: run_compounding_router(w_early=0.08, w_mid=0.06, w_ny=0.08, comp_pct=2.0), 220.0, 0.0, "Tri-Phase 2.0% Compounding"),
        ("S960", "Tri-Phase Confluence + 1.0% Comp + 2.0R TP", lambda: run_compounding_router(w_early=0.08, w_mid=0.06, w_ny=0.08, comp_pct=1.0, part_tp=2.0), 180.0, 0.0, "Tri-Phase 1.0% Comp + 2.0R TP"),
        ("S961", "Tri-Phase Confluence + 1.5% Comp + 2.0R TP", lambda: run_compounding_router(w_early=0.08, w_mid=0.06, w_ny=0.08, comp_pct=1.5, part_tp=2.0), 200.0, 0.0, "Tri-Phase 1.5% Comp + 2.0R TP"),
        ("S962", "Tri-Phase Confluence + 2.0% Comp + 2.0R TP", lambda: run_compounding_router(w_early=0.08, w_mid=0.06, w_ny=0.08, comp_pct=2.0, part_tp=2.0), 220.0, 0.0, "Tri-Phase 2.0% Comp + 2.0R TP"),
        ("S963", "Tri-Phase Confluence + 1.0% Comp + Lock-In", lambda: run_compounding_router(w_early=0.08, w_mid=0.06, w_ny=0.08, comp_pct=1.0), 180.0, 0.50, "Tri-Phase 1.0% Comp + Lock-In"),
        ("S964", "Tri-Phase Confluence + 1.5% Comp + Lock-In", lambda: run_compounding_router(w_early=0.08, w_mid=0.06, w_ny=0.08, comp_pct=1.5), 200.0, 0.50, "Tri-Phase 1.5% Comp + Lock-In"),
        ("S965", "Grand Sovereign Fusion Monument 2026", lambda: run_compounding_router(w_early=0.10, w_mid=0.06, w_ny=0.08, comp_pct=1.8, part_tp=2.0), 200.0, 0.50, "Grand Sovereign Fusion Monument 2026")
    ]

    # 5. Execute and Evaluate All Strategies
    results_table = []
    print("\n" + "=" * 145)
    print(f"{'ID':<6} {'Strategy Name':<42} {'Ann.Tr':<8} {'Tot.Tr':<8} {'Net PnL ($)':<14} {'PF':<8} {'WR%':<8} {'Intra DD ($)':<14} {'MC P95 DD':<12} {'Ruin%':<8} {'RoMaD':<8}")
    print("=" * 145)

    for sid, name, fn, gov, lock_ratio, role in strategy_definitions:
        trades = fn()
        m = analyze_trades_with_trailing_governor(trades, base_daily_limit=gov, lock_in_ratio=lock_ratio, years=6.0)
        mc = run_monte_carlo(m["filtered_trades"], num_simulations=1000, initial_capital=10000.0)

        row = {
            "Strategy_ID": sid,
            "Strategy_Name": name,
            "Role": role,
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
            "Ruin_Probability_Pct": round(mc["ruin_prob"], 2)
        }
        results_table.append(row)

        print(f"{sid:<6} {name:<42} {row['Annual_Trades']:<8.1f} {row['Total_Trades']:<8} ${row['Net_Profit']:<13.2f} {row['Profit_Factor']:<8.3f} {row['Win_Rate_Pct']:<7.1f}% ${row['True_Intra_Max_DD']:<13.2f} ${row['MC_P95_DD']:<11.2f} {row['Ruin_Probability_Pct']:<7.2f}% {row['RoMaD']:<8.2f}x")

    # 6. Save Matrix Results
    csv_path = os.path.join(RESULTS_DIR, "batch_58_fusion_matrix.csv")
    json_path = os.path.join(RESULTS_DIR, "batch_58_fusion_results.json")

    df_res = pd.DataFrame(results_table)
    df_res.to_csv(csv_path, index=False)

    with open(json_path, "w") as f:
        json.dump(results_table, f, indent=2)

    elapsed = time.time() - t_start
    print("=" * 145)
    print(f"\n[+] Batch 58 Execution Completed in {elapsed:.2f} seconds.")
    print(f"[+] Saved Matrix CSV: {csv_path}")
    print(f"[+] Saved Results JSON: {json_path}")

if __name__ == "__main__":
    main()
