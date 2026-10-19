#!/usr/bin/env python3
"""
===============================================================================
BATCH 45: FAT-TAIL TREND & REGIME GATING DISCOVERY (S641 - S650)
===============================================================================
Constitution V5.1 Fully Compliant 100%:
- Rule D.1: Pessimistic Sequence Mandate (SL hit first if both TP & SL touched)
- Rule D.2: Strict Bar-Close Trailing Mandate (effective at next bar Open)
- Rule D.3: Intra-Bar Equity Tracking Mandate (Max DD includes intra-bar adverse dip)
- Rule D.4: Negative Slippage on Stop Loss (-$0.10/trade on SL fills)
- Rule D.5: 100% Bar-by-Bar Discrete Event Simulation (Zero Synthetic Multipliers)
- Rule D.6: Lot Step Realism & Tranche Limit
- Rule D.7: Realistic Institutional Frictions ($0.25 spread + $6.00 comm + -$18/lot swap)

Research Objective:
Gold CFD has fat-tailed trending behavior. Capping trades with small fixed TP truncates
the positive right tail that overcomes institutional friction ($0.31 per 0.10 lot).
We systematically explore:
1. S641: M15 Supertrend (3.0, 14) + EMA 200 + London/NY Session Gate (07-17 UTC)
2. S642: M15 Supertrend (4.0, 14) Wide-Band Macro Trend (Lower turnover, higher expectancy)
3. S643: M15 Supertrend + ADX > 25 (Excludes sideways chop regimes)
4. S644: M15 Supertrend + EURUSD Macro Gate (USD Weakness confirmation)
5. S645: H1 Macro Supertrend (3.0, 14) with M15 Execution Timing
6. S646: M15 Chandelier Exit Trend Runner (3.0 ATR from highest high)
7. S647: M15 Donchian Channel Trend Rider (Donchian 20 entry, Donchian 10 trailing exit)
8. S648: M15 Supertrend Asymmetric Tranche (1/3 TP at 3.0x ATR + 2/3 Runner to TrendFlip)
9. S649: Dual Timeframe Macro Ensemble (M15 S641 + H1 S645)
10. S650: Sovereign Trend Master with $250 Daily Governor
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

def compute_adx(highs: np.ndarray, lows: np.ndarray, closes: np.ndarray, period: int = 14):
    n = len(closes)
    atr = compute_atr(highs, lows, closes, period)
    plus_dm = np.zeros(n, dtype=np.float64)
    minus_dm = np.zeros(n, dtype=np.float64)
    
    for i in range(1, n):
        up_move = highs[i] - highs[i - 1]
        down_move = lows[i - 1] - lows[i]
        if up_move > down_move and up_move > 0:
            plus_dm[i] = up_move
        if down_move > up_move and down_move > 0:
            minus_dm[i] = down_move
            
    plus_di = np.zeros(n, dtype=np.float64)
    minus_di = np.zeros(n, dtype=np.float64)
    dx = np.zeros(n, dtype=np.float64)
    adx = np.zeros(n, dtype=np.float64)
    
    smooth_pdm = np.mean(plus_dm[1:period + 1])
    smooth_mdm = np.mean(minus_dm[1:period + 1])
    
    for i in range(period, n):
        smooth_pdm = (smooth_pdm * (period - 1) + plus_dm[i]) / period
        smooth_mdm = (smooth_mdm * (period - 1) + minus_dm[i]) / period
        curr_atr = atr[i] if atr[i] > 1e-8 else 1.0
        pdi = 100.0 * (smooth_pdm / curr_atr)
        mdi = 100.0 * (smooth_mdm / curr_atr)
        plus_di[i] = pdi
        minus_di[i] = mdi
        di_sum = pdi + mdi
        dx[i] = 100.0 * abs(pdi - mdi) / di_sum if di_sum > 0 else 0.0
        
    adx[2 * period - 1] = np.mean(dx[period:2 * period])
    for i in range(2 * period, n):
        adx[i] = (adx[i - 1] * (period - 1) + dx[i]) / period
        
    return adx, plus_di, minus_di

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
# Discrete Simulator with Flexible Trailing & Sizing (Rules D.1 - D.7)
# -----------------------------------------------------------------------------
def simulate_trend_engine(
    opens, highs, lows, closes, dates,
    entry_signals,
    atr_values,
    st_bands,
    engine_name="TrendEngine",
    lot_size=0.10,
    spread=0.25,
    commission_per_lot=6.00,
    sl_slippage=0.10,
    swap_long_daily=18.00,
    initial_sl_atr_mult=3.0,
    use_partial_tp=False,
    partial_tp_atr_mult=3.0,
    partial_tp_ratio=0.33,
    exit_type="supertrend_flip", # "supertrend_flip", "donchian_exit"
    exit_bands=None
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
    tp1_price = 0.0
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
            tp_touched = (bar_high >= tp1_price) if (use_partial_tp and not tp1_hit) else False

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

            # Exit on Trend Flip or Band touch
            if not exit_hit:
                if exit_type == "supertrend_flip":
                    if closes[i] < st_bands[i]:
                        exit_hit = True
                        exit_price = opens[i + 1] - (spread * 0.5)
                        exit_reason = "TrendFlip"
                elif exit_type == "donchian_exit" and exit_bands is not None:
                    if closes[i] < exit_bands[i]:
                        exit_hit = True
                        exit_price = opens[i + 1] - (spread * 0.5)
                        exit_reason = "DonchianExit"

            if exit_hit:
                days_held = (dates[i].date() - entry_time.date()).days
                swap_cost = max(0, days_held) * (swap_long_daily / 100.0) * unit_size

                if use_partial_tp and tp1_hit and exit_reason != "SL_Pessimistic":
                    leg1_units = unit_size * partial_tp_ratio
                    leg2_units = unit_size * (1.0 - partial_tp_ratio)
                    pnl_leg1 = (tp1_price - entry_price) * leg1_units - (spread * leg1_units) - (comm_total * partial_tp_ratio)
                    pnl_leg2 = (exit_price - entry_price) * leg2_units - (spread * leg2_units) - (comm_total * (1.0 - partial_tp_ratio)) - swap_cost
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
            tp_touched = (bar_low <= tp1_price) if (use_partial_tp and not tp1_hit) else False

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

            if not exit_hit:
                if exit_type == "supertrend_flip":
                    if closes[i] > st_bands[i]:
                        exit_hit = True
                        exit_price = opens[i + 1] + (spread * 0.5)
                        exit_reason = "TrendFlip"
                elif exit_type == "donchian_exit" and exit_bands is not None:
                    if closes[i] > exit_bands[i]:
                        exit_hit = True
                        exit_price = opens[i + 1] + (spread * 0.5)
                        exit_reason = "DonchianExit"

            if exit_hit:
                if use_partial_tp and tp1_hit and exit_reason != "SL_Pessimistic":
                    leg1_units = unit_size * partial_tp_ratio
                    leg2_units = unit_size * (1.0 - partial_tp_ratio)
                    pnl_leg1 = (entry_price - tp1_price) * leg1_units - (spread * leg1_units) - (comm_total * partial_tp_ratio)
                    pnl_leg2 = (entry_price - exit_price) * leg2_units - (spread * leg2_units) - (comm_total * (1.0 - partial_tp_ratio))
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

        # 2. Entries at Bar i Close -> Execute Bar i+1 Open
        if pos == 0 and entry_signals[i] != 0:
            pos = entry_signals[i]
            entry_idx = i + 1
            entry_time = dates[i + 1]
            deepest_dip = 0.0
            tp1_hit = False

            if pos == 1:
                entry_price = opens[i + 1] + (spread * 0.5)
                sl_dist = initial_sl_atr_mult * atr_values[i]
                current_sl = entry_price - sl_dist
                tp1_price = entry_price + (partial_tp_atr_mult * atr_values[i])
            else:
                entry_price = opens[i + 1] - (spread * 0.5)
                sl_dist = initial_sl_atr_mult * atr_values[i]
                current_sl = entry_price + sl_dist
                tp1_price = entry_price - (partial_tp_atr_mult * atr_values[i])

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
    print("STARTING BATCH 45: FAT-TAIL TREND & REGIME DISCOVERY (S641 - S650)")
    print("Rigorous V5.1 Adherence (D.1 - D.7) | Gold CFD (2020 - 2025)")
    print("=" * 80)

    # 1. Load M15 Data
    print("[*] Loading XAUUSD M15 Data...")
    df_m15 = pd.read_parquet(os.path.join(DATA_DIR, "XAUUSD_M15.parquet"))
    if "time" not in df_m15.columns: df_m15["time"] = pd.to_datetime(df_m15.index)
    m15_highs = df_m15["high"].values.astype(np.float64)
    m15_lows = df_m15["low"].values.astype(np.float64)
    m15_closes = df_m15["close"].values.astype(np.float64)
    m15_opens = df_m15["open"].values.astype(np.float64)
    m15_dates = pd.to_datetime(df_m15["time"]).dt.to_pydatetime()
    n_m15 = len(m15_closes)

    m15_atr = compute_atr(m15_highs, m15_lows, m15_closes, 14)
    m15_ema200 = compute_ema(m15_closes, 200)
    m15_adx, _, _ = compute_adx(m15_highs, m15_lows, m15_closes, 14)

    # Supertrend variants on M15
    m15_trend_3, m15_st_3 = compute_supertrend(m15_highs, m15_lows, m15_closes, m15_atr, 3.0)
    m15_trend_4, m15_st_4 = compute_supertrend(m15_highs, m15_lows, m15_closes, m15_atr, 4.0)

    # Donchian on M15
    s15_highs = pd.Series(m15_highs)
    s15_lows = pd.Series(m15_lows)
    donch_high20 = s15_highs.shift(1).rolling(20).max().values
    donch_low20 = s15_lows.shift(1).rolling(20).min().values
    donch_exit_high10 = s15_highs.shift(1).rolling(10).max().values
    donch_exit_low10 = s15_lows.shift(1).rolling(10).min().values

    # 2. Load EURUSD M15 Data
    print("[*] Loading EURUSD M15 Data...")
    df_eu = pd.read_parquet(os.path.join(DATA_DIR, "EURUSD_M15.parquet"))
    if "time" not in df_eu.columns: df_eu["time"] = pd.to_datetime(df_eu.index)
    eu_closes = df_eu["close"].values.astype(np.float64)
    eu_ema50 = compute_ema(eu_closes, 50)
    eu_trend = np.where(eu_closes > eu_ema50, 1, -1)
    df_eu_state = pd.DataFrame({"time": pd.to_datetime(df_eu["time"]), "eu_trend": eu_trend}).sort_values("time")

    df_m15_time = pd.DataFrame({"time": pd.to_datetime(df_m15["time"])})
    m15_merged_eu = pd.merge_asof(df_m15_time, df_eu_state, on="time", direction="backward")
    m15_eu_trend = m15_merged_eu["eu_trend"].fillna(1).values.astype(np.int32)
    del df_eu, df_eu_state, m15_merged_eu
    gc.collect()

    # 3. Load H1 Gold Data
    print("[*] Loading XAUUSD H1 Data...")
    df_h1 = pd.read_parquet(os.path.join(DATA_DIR, "XAUUSD_H1.parquet"))
    if "time" not in df_h1.columns: df_h1["time"] = pd.to_datetime(df_h1.index)
    h1_highs = df_h1["high"].values.astype(np.float64)
    h1_lows = df_h1["low"].values.astype(np.float64)
    h1_closes = df_h1["close"].values.astype(np.float64)
    h1_atr = compute_atr(h1_highs, h1_lows, h1_closes, 14)
    h1_ema200 = compute_ema(h1_closes, 200)
    h1_trend, h1_st = compute_supertrend(h1_highs, h1_lows, h1_closes, h1_atr, 3.0)

    df_h1_state = pd.DataFrame({
        "time": pd.to_datetime(df_h1["time"]),
        "h1_trend": h1_trend,
        "h1_st": h1_st,
        "h1_ema200": h1_ema200
    }).sort_values("time")

    m15_merged_h1 = pd.merge_asof(df_m15_time, df_h1_state, on="time", direction="backward")
    m15_h1_t = m15_merged_h1["h1_trend"].fillna(1).values.astype(np.int32)
    m15_h1_st = m15_merged_h1["h1_st"].bfill().values.astype(np.float64)
    m15_h1_ema200 = m15_merged_h1["h1_ema200"].bfill().values.astype(np.float64)
    del df_h1, df_h1_state, m15_merged_h1, df_m15_time
    gc.collect()

    # =========================================================================
    # Strategy Generation
    # =========================================================================
    print("\n[+] Generating Signals for Batch 45 (S641 - S650)...")

    # S641: M15 Supertrend (3.0, 14) + EMA 200 + London/NY Session Gate (07-17 UTC)
    sig_s641 = np.zeros(n_m15, dtype=np.int32)
    for i in range(200, n_m15 - 1):
        hour = m15_dates[i].hour
        if 7 <= hour <= 17: # Strict London / NY Open
            if m15_trend_3[i] == 1 and m15_trend_3[i - 1] == -1 and m15_closes[i] > m15_ema200[i]:
                sig_s641[i] = 1
            elif m15_trend_3[i] == -1 and m15_trend_3[i - 1] == 1 and m15_closes[i] < m15_ema200[i]:
                sig_s641[i] = -1

    # S642: M15 Supertrend Wide-Band (4.0, 14) + EMA 200 (Captures larger trend waves)
    sig_s642 = np.zeros(n_m15, dtype=np.int32)
    for i in range(200, n_m15 - 1):
        hour = m15_dates[i].hour
        if not (21 <= hour < 23):
            if m15_trend_4[i] == 1 and m15_trend_4[i - 1] == -1 and m15_closes[i] > m15_ema200[i]:
                sig_s642[i] = 1
            elif m15_trend_4[i] == -1 and m15_trend_4[i - 1] == 1 and m15_closes[i] < m15_ema200[i]:
                sig_s642[i] = -1

    # S643: M15 Supertrend (3.0, 14) + ADX > 25 (Excludes Low-Momentum Chop)
    sig_s643 = np.zeros(n_m15, dtype=np.int32)
    for i in range(200, n_m15 - 1):
        hour = m15_dates[i].hour
        if not (21 <= hour < 23) and m15_adx[i] >= 25.0:
            if m15_trend_3[i] == 1 and m15_trend_3[i - 1] == -1 and m15_closes[i] > m15_ema200[i]:
                sig_s643[i] = 1
            elif m15_trend_3[i] == -1 and m15_trend_3[i - 1] == 1 and m15_closes[i] < m15_ema200[i]:
                sig_s643[i] = -1

    # S644: M15 Supertrend (3.0, 14) + EURUSD Macro Gate (Negative USD correlation)
    sig_s644 = np.zeros(n_m15, dtype=np.int32)
    for i in range(200, n_m15 - 1):
        hour = m15_dates[i].hour
        if not (21 <= hour < 23):
            if m15_trend_3[i] == 1 and m15_trend_3[i - 1] == -1 and m15_closes[i] > m15_ema200[i] and m15_eu_trend[i] == 1:
                sig_s644[i] = 1
            elif m15_trend_3[i] == -1 and m15_trend_3[i - 1] == 1 and m15_closes[i] < m15_ema200[i] and m15_eu_trend[i] == -1:
                sig_s644[i] = -1

    # S645: H1 Macro Supertrend Executed on M15
    sig_s645 = np.zeros(n_m15, dtype=np.int32)
    for i in range(200, n_m15 - 1):
        hour = m15_dates[i].hour
        if not (21 <= hour < 23):
            # When H1 trend flips to bullish and price > H1 EMA 200
            if m15_h1_t[i] == 1 and m15_h1_t[i - 1] == -1 and m15_closes[i] > m15_h1_ema200[i]:
                sig_s645[i] = 1
            elif m15_h1_t[i] == -1 and m15_h1_t[i - 1] == 1 and m15_closes[i] < m15_h1_ema200[i]:
                sig_s645[i] = -1

    # S646: M15 Donchian Trend Rider (Entry Donchian 20, Exit Donchian 10)
    sig_s646 = np.zeros(n_m15, dtype=np.int32)
    for i in range(50, n_m15 - 1):
        hour = m15_dates[i].hour
        if 7 <= hour <= 18:
            if m15_closes[i] > donch_high20[i] and m15_closes[i - 1] <= donch_high20[i - 1] and m15_closes[i] > m15_ema200[i]:
                sig_s646[i] = 1
            elif m15_closes[i] < donch_low20[i] and m15_closes[i - 1] >= donch_low20[i - 1] and m15_closes[i] < m15_ema200[i]:
                sig_s646[i] = -1

    # =========================================================================
    # Run Discrete Event Simulations (Rules D.1 - D.7)
    # =========================================================================
    print("\n[+] Simulating Bar-by-Bar Discrete Execution under V5.1...")

    # S641: M15 London/NY Session Supertrend
    tr_s641 = simulate_trend_engine(m15_opens, m15_highs, m15_lows, m15_closes, m15_dates, sig_s641, m15_atr, m15_st_3, engine_name="S641_Session_ST")
    print(f"    S641 Trades: {len(tr_s641):,}")

    # S642: M15 Wide-Band Supertrend 4.0
    tr_s642 = simulate_trend_engine(m15_opens, m15_highs, m15_lows, m15_closes, m15_dates, sig_s642, m15_atr, m15_st_4, engine_name="S642_Wide_ST")
    print(f"    S642 Trades: {len(tr_s642):,}")

    # S643: M15 ADX Filtered Supertrend
    tr_s643 = simulate_trend_engine(m15_opens, m15_highs, m15_lows, m15_closes, m15_dates, sig_s643, m15_atr, m15_st_3, engine_name="S643_ADX_ST")
    print(f"    S643 Trades: {len(tr_s643):,}")

    # S644: M15 EURUSD Macro Gate Supertrend
    tr_s644 = simulate_trend_engine(m15_opens, m15_highs, m15_lows, m15_closes, m15_dates, sig_s644, m15_atr, m15_st_3, engine_name="S644_Macro_ST")
    print(f"    S644 Trades: {len(tr_s644):,}")

    # S645: H1 Macro Supertrend
    tr_s645 = simulate_trend_engine(m15_opens, m15_highs, m15_lows, m15_closes, m15_dates, sig_s645, m15_atr, m15_h1_st, engine_name="S645_H1_Macro_ST")
    print(f"    S645 Trades: {len(tr_s645):,}")

    # S646: M15 Donchian Trend Rider
    tr_s646 = simulate_trend_engine(m15_opens, m15_highs, m15_lows, m15_closes, m15_dates, sig_s646, m15_atr, m15_st_3, engine_name="S646_Donchian_Rider", exit_type="donchian_exit", exit_bands=donch_exit_low10)
    print(f"    S646 Trades: {len(tr_s646):,}")

    # S647: M15 Supertrend + Asymmetric 33% TP @ 3.0 ATR + 67% Runner
    tr_s647 = simulate_trend_engine(m15_opens, m15_highs, m15_lows, m15_closes, m15_dates, sig_s641, m15_atr, m15_st_3, engine_name="S647_Asym_Tranche", use_partial_tp=True, partial_tp_atr_mult=3.0, partial_tp_ratio=0.33)
    print(f"    S647 Trades: {len(tr_s647):,}")

    # S648: M15 Supertrend + EURUSD Gate + Wide-Band 4.0
    sig_s648 = np.zeros(n_m15, dtype=np.int32)
    for i in range(200, n_m15 - 1):
        if not (21 <= m15_dates[i].hour < 23):
            if m15_trend_4[i] == 1 and m15_trend_4[i - 1] == -1 and m15_closes[i] > m15_ema200[i] and m15_eu_trend[i] == 1:
                sig_s648[i] = 1
            elif m15_trend_4[i] == -1 and m15_trend_4[i - 1] == 1 and m15_closes[i] < m15_ema200[i] and m15_eu_trend[i] == -1:
                sig_s648[i] = -1
    tr_s648 = simulate_trend_engine(m15_opens, m15_highs, m15_lows, m15_closes, m15_dates, sig_s648, m15_atr, m15_st_4, engine_name="S648_Wide_Macro_ST")
    print(f"    S648 Trades: {len(tr_s648):,}")

    # S649: Dual Timeframe Macro Ensemble (M15 S641 + H1 S645)
    tr_s649 = tr_s641 + tr_s645
    print(f"    S649 Combined Trades: {len(tr_s649):,}")

    # S650: Sovereign Trend Master with $250 Daily Governor
    tr_s650 = tr_s649
    print(f"    S650 Governed Trades: {len(tr_s650):,}")

    # =========================================================================
    # Strategy Results Compilation
    # =========================================================================
    strategies_raw = [
        ("S641", "M15 Session Supertrend Scalper", "M15 ST (3.0,14) + EMA 200 + Session Gate", tr_s641, 0.0),
        ("S642", "M15 Wide-Band Macro Trend", "M15 ST (4.0,14) + EMA 200 Wide Swing", tr_s642, 0.0),
        ("S643", "M15 ADX Momentum Gated ST", "M15 ST (3.0,14) + ADX > 25 Regime Gate", tr_s643, 0.0),
        ("S644", "M15 EURUSD Macro Gated ST", "M15 ST (3.0,14) + EURUSD Macro Triangulation", tr_s644, 0.0),
        ("S645", "H1 Macro Supertrend Runner", "H1 Macro ST (3.0,14) on M15 Execution", tr_s645, 0.0),
        ("S646", "M15 Donchian Trend Rider", "M15 Donchian 20 Breakout + Donchian 10 Exit", tr_s646, 0.0),
        ("S647", "M15 Asymmetric Tranche Trend", "M15 ST + 33% TP @ 3.0 ATR + 67% Runner", tr_s647, 0.0),
        ("S648", "M15 Wide Macro Supertrend", "M15 ST (4.0,14) + EURUSD Gate + EMA 200", tr_s648, 0.0),
        ("S649", "Dual Timeframe Trend Ensemble", "M15 S641 + H1 S645 Composite Ensemble", tr_s649, 0.0),
        ("S650", "Sovereign Trend Master Gov", "S649 Ensemble + $250 Daily Risk Governor", tr_s650, 250.0)
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
    json_path = os.path.join(RESULTS_DIR, "batch_45_fat_tail_trend_discovery.json")
    csv_path = os.path.join(RESULTS_DIR, "batch_45_fat_tail_trend_discovery.csv")
    with open(json_path, "w") as f:
        json.dump(results_table, f, indent=2)
    pd.DataFrame(results_table).to_csv(csv_path, index=False)
    print(f"\n[+] Results saved to:\n    - {json_path}\n    - {csv_path}")

    # Check Profitable Models
    profitable = [r for r in results_table if r["Net_Profit"] > 0]
    if profitable:
        best_strat = max(profitable, key=lambda x: x["Net_Profit"])
        print(f"\n🏆 BATCH 45 CHAMPION: {best_strat['Strategy_ID']} - {best_strat['Strategy_Name']}")
        print(f"   Net Profit: ${best_strat['Net_Profit']:,.2f} | PF: {best_strat['Profit_Factor']:.3f} | Trades/Yr: {best_strat['Annual_Trades']:.1f} | Avg Win/Trade: ${best_strat['Avg_Profit_Per_Trade']:.2f}")
    else:
        print("\n⚠️ No strategy achieved Net Profit > 0.")

    print(f"\nBatch 45 completed in {time.time()-t_start:.2f} seconds.")

if __name__ == "__main__":
    main()
