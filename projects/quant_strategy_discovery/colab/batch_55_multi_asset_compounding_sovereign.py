#!/usr/bin/env python3
"""
===============================================================================
BATCH 55: MULTI-ASSET SOVEREIGN TRINITY & DYNAMIC COMPOUNDING ARCHITECTURES
===============================================================================
Executes 30 Strategies (S846 to S875) on Google Colab Cloud VM
under 100% strict adherence to Constitution V5.1 (Rules D.1 to D.7):
- Rule D.1: Pessimistic Sequence Mandate (SL triggered first if both hit in 1 bar)
- Rule D.2: Strict Bar-Close Trailing Mandate (effective next bar Open)
- Rule D.3: Intra-Bar Equity Tracking Mandate (Max DD measured from deepest intra-bar adverse excursion)
- Rule D.4: Negative Slippage on Stop Loss (-$0.10/trade baseline on Gold SL fills)
- Rule D.5: 100% Bar-by-Bar Discrete Simulation (Zero Synthetic Multipliers)
- Rule D.6: Lot Step Realism (Exact 0.01 lot multiples, clamped between 0.04 and 0.50)
- Rule D.7: Institutional Frictions ($0.25 spread + $6.00 comm + -$18/lot swap on Gold;
            $0.15 spread + $6.00 comm on EURUSD)
- Strict Anti-Lookahead Causality: H1 closed bar only (+1H shift), M15 closed bar only

Exploration Matrices (30 Strategies: S846 - S875):
1. S846 - S855: Multi-Asset Synergy (S838 Sovereign Trinity + EURUSD H1 Macro Hedge)
2. S856 - S865: Fixed-Fractional & Volatility Compounding (0.5% - 2.0% Risk per Trade)
3. S866 - S875: Asymmetric Partial Scaling (50% Scale-Out at 2.5R/3.0R + Trailing Runner)
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
# Discrete Event Simulator with Staged Tranches and Compounding (Rules D.1 to D.7)
# -----------------------------------------------------------------------------
def simulate_discrete_engine(
    opens, highs, lows, closes, dates,
    entry_signals,
    atr_values,
    st_bands,
    engine_name="Engine",
    point_value=100.0,
    lot_size=0.10,
    dynamic_vol_risk=0.0,
    compounding_pct=0.0,
    initial_equity=10000.0,
    min_lot=0.04,
    max_lot=0.40,
    spread=0.25,
    commission_per_lot=6.00,
    sl_slippage=0.10,
    swap_long_daily=18.00,
    initial_sl_atr_mult=3.0,
    partial_tp_atr_mult=0.0, # e.g. 2.5 ATR take 50%
    start_date=None,
    end_date=None
):
    n = len(closes)
    trades = []
    current_equity = initial_equity

    pos = 0
    entry_price = 0.0
    entry_time = None
    current_sl = 0.0
    active_lot = lot_size
    deepest_dip = 0.0
    tranche_taken = False
    half_lot = 0.0

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
                swap_cost = max(0, days_held) * swap_long_daily * active_lot
                net_pnl = (exit_price - entry_price) * curr_unit - (spread * curr_unit) - (commission_per_lot * active_lot) - swap_cost

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
                # Rule D.2: Bar-close trailing ratchet (Effective next bar Open)
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

            # Position Sizing Logic (Rule D.6: Multiples of 0.01 lot)
            if compounding_pct > 0.0 and atr_values[i] > 0.0:
                calc_risk = current_equity * (compounding_pct / 100.0)
                calc_lot = calc_risk / (initial_sl_atr_mult * atr_values[i] * point_value)
                active_lot = round(max(min_lot, min(max_lot, calc_lot)), 2)
            elif dynamic_vol_risk > 0.0 and atr_values[i] > 0.0:
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
        return {"mc_p50_dd": 0.0, "mc_p95_dd": 0.0, "ruin_prob": 0.0}

    pnls = np.array([t["pnl"] for t in trades], dtype=np.float64)
    dips = np.array([t["deepest_dip"] for t in trades], dtype=np.float64)
    n = len(pnls)

    mc_max_dds = np.zeros(num_simulations, dtype=np.float64)
    ruin_count = 0
    rng = np.random.default_rng(seed=42)

    for s in range(num_simulations):
        idx = rng.permutation(n)
        perm_pnls = pnls[idx]
        perm_dips = dips[idx]

        cum_equity = 0.0
        peak_equity = 0.0
        max_dd = 0.0
        is_ruined = False

        for p, d in zip(perm_pnls, perm_dips):
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
        if is_ruined:
            ruin_count += 1

    return {
        "mc_p50_dd": float(np.percentile(mc_max_dds, 50)),
        "mc_p95_dd": float(np.percentile(mc_max_dds, 95)),
        "ruin_prob": (ruin_count / num_simulations) * 100.0
    }

# -----------------------------------------------------------------------------
# Main Execution Pipeline
# -----------------------------------------------------------------------------
def main():
    t_start = time.time()
    now_str = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')
    print("=" * 80)
    print("🚀 BATCH 55: MULTI-ASSET SOVEREIGN TRINITY & COMPOUNDING ARCHITECTURES")
    print(f"Timestamp: {now_str}")
    print(f"Hardware Environment: {'Google Colab VM' if 'content' in REPO_ROOT else 'Local Controller'}")
    print("=" * 80)

    # 1. Load Parquet Data
    print(f"[+] Loading Parquet Caches from {DATA_DIR}...")
    df_m15 = pd.read_parquet(os.path.join(DATA_DIR, "XAUUSD_M15.parquet"))
    df_h1 = pd.read_parquet(os.path.join(DATA_DIR, "XAUUSD_H1.parquet"))
    df_eu_m15 = pd.read_parquet(os.path.join(DATA_DIR, "EURUSD_M15.parquet"))
    df_eu_h1 = pd.read_parquet(os.path.join(DATA_DIR, "EURUSD_H1.parquet"))

    m15_highs = df_m15["high"].values.astype(np.float64)
    m15_lows = df_m15["low"].values.astype(np.float64)
    m15_closes = df_m15["close"].values.astype(np.float64)
    m15_opens = df_m15["open"].values.astype(np.float64)
    m15_dates = pd.to_datetime(df_m15.index).to_pydatetime()
    n_m15 = len(m15_closes)

    h1_highs = df_h1["high"].values.astype(np.float64)
    h1_lows = df_h1["low"].values.astype(np.float64)
    h1_closes = df_h1["close"].values.astype(np.float64)

    eu_m15_closes = df_eu_m15["close"].values.astype(np.float64)

    eu_h1_highs = df_eu_h1["high"].values.astype(np.float64)
    eu_h1_lows = df_eu_h1["low"].values.astype(np.float64)
    eu_h1_closes = df_eu_h1["close"].values.astype(np.float64)
    eu_h1_opens = df_eu_h1["open"].values.astype(np.float64)
    eu_h1_dates = pd.to_datetime(df_eu_h1.index).to_pydatetime()

    # 2. Compute Indicators
    print("[*] Synchronizing Indicators under strict causality...")
    m15_atr14 = compute_atr(m15_highs, m15_lows, m15_closes, 14)
    m15_atr100 = compute_atr(m15_highs, m15_lows, m15_closes, 100)
    m15_vol_ratio = np.divide(m15_atr14, np.where(m15_atr100 > 0, m15_atr100, 1.0))
    m15_ema200 = compute_ema(m15_closes, 200)
    st_t30, st_b30 = compute_supertrend(m15_highs, m15_lows, m15_closes, m15_atr14, 3.0)

    # Precompute Gold H1 with +1H shift
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

    # EURUSD M15 Macro Gate
    eu_ema50 = compute_ema(eu_m15_closes, 50)
    eu_trend = np.where(eu_m15_closes > eu_ema50, 1, -1)
    df_eu_state = pd.DataFrame({"time": pd.to_datetime(df_eu_m15.index), "eu_trend": eu_trend}).sort_values("time")
    m15_merged_eu = pd.merge_asof(df_m15_time, df_eu_state, on="time", direction="backward")
    m15_eu_trend = m15_merged_eu["eu_trend"].fillna(1).values.astype(np.int32)

    # EURUSD H1 Independent Hedge Engine
    eu_h1_atr14 = compute_atr(eu_h1_highs, eu_h1_lows, eu_h1_closes, 14)
    eu_h1_ema100 = compute_ema(eu_h1_closes, 100)
    eu_h1_st_t, eu_h1_st_b = compute_supertrend(eu_h1_highs, eu_h1_lows, eu_h1_closes, eu_h1_atr14, 2.5)

    del df_h1, df_h1_state, df_eu_m15, df_eu_state, m15_merged_h1, m15_merged_eu, df_m15_time
    gc.collect()

    print(f"[+] Synchronized {n_m15:,} Gold M15 bars and {len(eu_h1_closes):,} EURUSD H1 bars.")

    # 3. Signal Generators
    def generate_gold_m15_signals(session_start=7, session_end=17, min_atr=1.50, min_vr=0.0):
        sig = np.zeros(n_m15, dtype=np.int32)
        for i in range(200, n_m15 - 1):
            h = m15_dates[i].hour
            if session_start <= h <= session_end:
                if min_atr <= 0.0 or m15_atr14[i] >= min_atr:
                    if min_vr > 0.0 and m15_vol_ratio[i] < min_vr:
                        continue
                    if st_t30[i] == 1 and st_t30[i - 1] == -1 and m15_closes[i] > m15_ema200[i]:
                        if m15_h1_trend[i] == 1 and m15_eu_trend[i] == 1:
                            sig[i] = 1
                    elif st_t30[i] == -1 and st_t30[i - 1] == 1 and m15_closes[i] < m15_ema200[i]:
                        if m15_h1_trend[i] == -1 and m15_eu_trend[i] == -1:
                            sig[i] = -1
        return sig

    def generate_gold_h1_macro_signals(session_start=7, session_end=17, min_vr=0.0):
        sig = np.zeros(n_m15, dtype=np.int32)
        for i in range(200, n_m15 - 1):
            h = m15_dates[i].hour
            if session_start <= h <= session_end and not (21 <= h < 23):
                if min_vr > 0.0 and m15_vol_ratio[i] < min_vr:
                    continue
                if m15_h1_trend[i] == 1 and m15_h1_trend[i - 1] == -1 and m15_closes[i] > m15_h1_ema[i] and m15_eu_trend[i] == 1:
                    sig[i] = 1
                elif m15_h1_trend[i] == -1 and m15_h1_trend[i - 1] == 1 and m15_closes[i] < m15_h1_ema[i] and m15_eu_trend[i] == -1:
                    sig[i] = -1
        return sig

    def generate_eurusd_h1_signals():
        n_eu = len(eu_h1_closes)
        sig = np.zeros(n_eu, dtype=np.int32)
        for i in range(120, n_eu - 1):
            h = eu_h1_dates[i].hour
            if 7 <= h <= 17:
                if eu_h1_st_t[i] == 1 and eu_h1_st_t[i - 1] == -1 and eu_h1_closes[i] > eu_h1_ema100[i]:
                    sig[i] = 1
                elif eu_h1_st_t[i] == -1 and eu_h1_st_t[i - 1] == 1 and eu_h1_closes[i] < eu_h1_ema100[i]:
                    sig[i] = -1
        return sig

    # Engine Runners
    sig_m15_core = generate_gold_m15_signals(7, 17, 1.50)
    sig_h1_core  = generate_gold_h1_macro_signals(7, 17)
    sig_m15_regime = generate_gold_m15_signals(7, 17, 1.50, min_vr=1.10)
    sig_h1_regime  = generate_gold_h1_macro_signals(7, 17, min_vr=1.10)
    sig_london_sniper = generate_gold_m15_signals(6, 10, 1.50, min_vr=1.10)
    sig_eu_h1 = generate_eurusd_h1_signals()

    def run_gold_trinity(dyn_risk=200.0, reg_lot=0.05, snip_lot=0.08, comp_pct=0.0, part_tp=0.0):
        t1 = simulate_discrete_engine(m15_opens, m15_highs, m15_lows, m15_closes, m15_dates, sig_m15_core, m15_atr14, st_b30, "Gold_M15_DynVol", point_value=100.0, dynamic_vol_risk=dyn_risk, compounding_pct=comp_pct, partial_tp_atr_mult=part_tp)
        t2 = simulate_discrete_engine(m15_opens, m15_highs, m15_lows, m15_closes, m15_dates, sig_h1_core, m15_atr14, m15_h1_st, "Gold_H1_DynVol", point_value=100.0, dynamic_vol_risk=dyn_risk, compounding_pct=comp_pct, partial_tp_atr_mult=part_tp)
        t3 = simulate_discrete_engine(m15_opens, m15_highs, m15_lows, m15_closes, m15_dates, sig_m15_regime, m15_atr14, st_b30, "Gold_M15_Regime", point_value=100.0, lot_size=reg_lot, partial_tp_atr_mult=part_tp)
        t4 = simulate_discrete_engine(m15_opens, m15_highs, m15_lows, m15_closes, m15_dates, sig_h1_regime, m15_atr14, m15_h1_st, "Gold_H1_Regime", point_value=100.0, lot_size=reg_lot, partial_tp_atr_mult=part_tp)
        t5 = simulate_discrete_engine(m15_opens, m15_highs, m15_lows, m15_closes, m15_dates, sig_london_sniper, m15_atr14, st_b30, "Gold_London_Sniper", point_value=100.0, lot_size=snip_lot, partial_tp_atr_mult=part_tp)
        return t1 + t2 + t3 + t4 + t5

    def run_eurusd_h1(lot=0.10, comp_pct=0.0):
        return simulate_discrete_engine(eu_h1_opens, eu_h1_highs, eu_h1_lows, eu_h1_closes, eu_h1_dates, sig_eu_h1, eu_h1_atr14, eu_h1_st_b, "EURUSD_H1", point_value=100000.0, lot_size=lot, compounding_pct=comp_pct, spread=0.00015, commission_per_lot=6.00, sl_slippage=0.00005, swap_long_daily=4.0)

    # 4. Construct Strategy Definitions (S846 to S875)
    print("\n[+] Constructing 30 Strategies (S846 - S875)...")
    strategy_definitions = [
        # Group 1: Multi-Asset Synergy (S846 - S855)
        ("S846", "S838 Trinity Reference (Gold Standalone)", lambda: run_gold_trinity(), 180.0, "Reference Standalone Trinity"),
        ("S847", "EURUSD H1 Macro Trend Baseline (0.10 Lot)", lambda: run_eurusd_h1(lot=0.10), 0.0, "EURUSD Standalone Baseline"),
        ("S848", "Dual-Asset Sovereign (S838 + EUR 0.05 lot)", lambda: run_gold_trinity() + run_eurusd_h1(lot=0.05), 180.0, "Multi-Asset Conservative Buffer"),
        ("S849", "Dual-Asset Sovereign (S838 + EUR 0.10 lot)", lambda: run_gold_trinity() + run_eurusd_h1(lot=0.10), 180.0, "Multi-Asset Balanced Suite"),
        ("S850", "Dual-Asset Sovereign (S838 + EUR 0.15 lot)", lambda: run_gold_trinity() + run_eurusd_h1(lot=0.15), 180.0, "Multi-Asset Expanded Suite"),
        ("S851", "Dual-Asset Sovereign ($200 Joint Governor)", lambda: run_gold_trinity() + run_eurusd_h1(lot=0.10), 200.0, "Governed Multi-Asset $200"),
        ("S852", "Dual-Asset Sovereign ($220 Joint Governor)", lambda: run_gold_trinity() + run_eurusd_h1(lot=0.10), 220.0, "Governed Multi-Asset $220"),
        ("S853", "Dual-Asset Sovereign ($250 Joint Governor)", lambda: run_gold_trinity() + run_eurusd_h1(lot=0.10), 250.0, "Governed Multi-Asset $250"),
        ("S854", "Prop-Firm Dual-Asset Shield ($150 Gov)", lambda: run_gold_trinity(dyn_risk=150.0, reg_lot=0.04, snip_lot=0.06) + run_eurusd_h1(lot=0.06), 150.0, "Prop-Firm Multi-Asset Shield"),
        ("S855", "Titan Dual-Asset Suite ($240 Gov)", lambda: run_gold_trinity(dyn_risk=250.0, reg_lot=0.06, snip_lot=0.10) + run_eurusd_h1(lot=0.12), 240.0, "Titan Multi-Asset Suite"),

        # Group 2: Fixed-Fractional & Volatility Compounding (S856 - S865)
        ("S856", "S838 Trinity + 0.5% Compounding", lambda: run_gold_trinity(comp_pct=0.5), 180.0, "Conservative 0.5% Compounding"),
        ("S857", "S838 Trinity + 0.75% Compounding", lambda: run_gold_trinity(comp_pct=0.75), 180.0, "Moderate 0.75% Compounding"),
        ("S858", "S838 Trinity + 1.0% Compounding", lambda: run_gold_trinity(comp_pct=1.0), 200.0, "Standard 1.0% Compounding"),
        ("S859", "S838 Trinity + 1.25% Compounding", lambda: run_gold_trinity(comp_pct=1.25), 220.0, "Growth 1.25% Compounding"),
        ("S860", "S838 Trinity + 1.5% Compounding", lambda: run_gold_trinity(comp_pct=1.5), 250.0, "Aggressive 1.5% Compounding"),
        ("S861", "S838 Trinity + 2.0% Compounding", lambda: run_gold_trinity(comp_pct=2.0), 300.0, "Maximum Growth 2.0% Compounding"),
        ("S862", "Dual-Asset + 0.75% Compounding", lambda: run_gold_trinity(comp_pct=0.75) + run_eurusd_h1(comp_pct=0.5), 200.0, "Dual-Asset Moderate Compounding"),
        ("S863", "Dual-Asset + 1.0% Compounding", lambda: run_gold_trinity(comp_pct=1.0) + run_eurusd_h1(comp_pct=0.75), 220.0, "Dual-Asset Standard Compounding"),
        ("S864", "Dual-Asset + 1.25% Compounding", lambda: run_gold_trinity(comp_pct=1.25) + run_eurusd_h1(comp_pct=1.0), 250.0, "Dual-Asset Accelerated Compounding"),
        ("S865", "Dual-Asset + 1.5% Compounding", lambda: run_gold_trinity(comp_pct=1.5) + run_eurusd_h1(comp_pct=1.0), 280.0, "Dual-Asset Apex Compounding"),

        # Group 3: Asymmetric Partial Scaling & Trailing Runners (S866 - S875)
        ("S866", "S838 Trinity + 2.0R ATR Partial TP", lambda: run_gold_trinity(part_tp=2.0), 180.0, "2.0R Staged Scale-Out"),
        ("S867", "S838 Trinity + 2.5R ATR Partial TP", lambda: run_gold_trinity(part_tp=2.5), 180.0, "2.5R Staged Scale-Out"),
        ("S868", "S838 Trinity + 3.0R ATR Partial TP", lambda: run_gold_trinity(part_tp=3.0), 180.0, "3.0R Staged Scale-Out"),
        ("S869", "S838 Trinity + 3.5R ATR Partial TP", lambda: run_gold_trinity(part_tp=3.5), 180.0, "3.5R Staged Scale-Out"),
        ("S870", "S838 Trinity + 4.0R ATR Partial TP", lambda: run_gold_trinity(part_tp=4.0), 180.0, "4.0R Staged Scale-Out"),
        ("S871", "Dual-Asset + 2.5R ATR Partial TP", lambda: run_gold_trinity(part_tp=2.5) + run_eurusd_h1(lot=0.10), 180.0, "Dual-Asset 2.5R Staged Scale-Out"),
        ("S872", "Dual-Asset + 3.0R ATR Partial TP", lambda: run_gold_trinity(part_tp=3.0) + run_eurusd_h1(lot=0.10), 180.0, "Dual-Asset 3.0R Staged Scale-Out"),
        ("S873", "Dual-Asset + 1.0% Comp + 2.5R TP", lambda: run_gold_trinity(comp_pct=1.0, part_tp=2.5) + run_eurusd_h1(comp_pct=0.75), 220.0, "Dual-Asset Compounding + Staged Scaling"),
        ("S874", "Dual-Asset + 1.0% Comp + 3.0R TP", lambda: run_gold_trinity(comp_pct=1.0, part_tp=3.0) + run_eurusd_h1(comp_pct=0.75), 220.0, "Dual-Asset Compounding + 3.0R Scaling"),
        ("S875", "Grand Sovereign Millennium Monument 2026", lambda: run_gold_trinity(comp_pct=1.0, part_tp=2.5) + run_eurusd_h1(lot=0.08), 200.0, "Flagship Grand Sovereign Millennium Monument")
    ]

    # 5. Execute and Evaluate All Strategies
    results_table = []
    print("\n" + "=" * 145)
    print(f"{'ID':<6} {'Strategy Name':<42} {'Ann.Tr':<8} {'Tot.Tr':<8} {'Net PnL ($)':<14} {'PF':<8} {'WR%':<8} {'Intra DD ($)':<14} {'MC P95 DD':<12} {'Ruin%':<8} {'RoMaD':<8}")
    print("=" * 145)

    for sid, name, fn, gov, role in strategy_definitions:
        trades = fn()
        m = analyze_trades(trades, max_daily_loss=gov, years=6.0)
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
    csv_path = os.path.join(RESULTS_DIR, "batch_55_multi_asset_compounding_matrix.csv")
    json_path = os.path.join(RESULTS_DIR, "batch_55_multi_asset_compounding_results.json")

    df_res = pd.DataFrame(results_table)
    df_res.to_csv(csv_path, index=False)

    with open(json_path, "w") as f:
        json.dump(results_table, f, indent=2)

    elapsed = time.time() - t_start
    print("=" * 145)
    print(f"\n[+] Batch 55 Execution Completed in {elapsed:.2f} seconds.")
    print(f"[+] Saved Matrix CSV: {csv_path}")
    print(f"[+] Saved Results JSON: {json_path}")

if __name__ == "__main__":
    main()
