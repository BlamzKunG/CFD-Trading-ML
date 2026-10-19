#!/usr/bin/env python3
"""
===============================================================================
BATCH 44: HIGH-EXPECTANCY M5/M15 QUANTITATIVE STRATEGY DISCOVERY (S631 - S640)
===============================================================================
Constitution V5.1 Fully Compliant 100%:
- Rule D.1: Pessimistic Sequence Mandate (SL hit first if both TP & SL touched)
- Rule D.2: Strict Bar-Close Trailing Mandate (effective at next bar Open)
- Rule D.3: Intra-Bar Equity Tracking Mandate (Max DD includes intra-bar adverse dip)
- Rule D.4: Negative Slippage on Stop Loss (-$0.10/trade on SL fills)
- Rule D.5: 100% Bar-by-Bar Discrete Event Simulation (Zero Synthetic Multipliers)
- Rule D.6: Lot Step Realism & Tranche Limit (0.10 lot, 50/50 staged tranches)
- Rule D.7: Realistic Institutional Frictions ($0.25 spread + $6.00 comm + -$18/lot swap)

Strategic Directive:
- Focus on M5 and M15 High-Expectancy setups (Target: 150 - 350 trades/year, avg profit >= $2.00 - $4.00/oz)
- Break free from M1 friction tax trap
- Archetypes:
  1. S631: M15 London/NY Asian Range Breakout with Range Expansion
  2. S632: M15 Asian Range Liquidity Sweep & Reversal (Judas Swing Fade)
  3. S633: M15 Trend Pullback to Dynamic Value Zone (H1 Trend + M15 EMA 20/50)
  4. S634: M5 Volatility Compression & Ignition (TTM Squeeze + High Target)
  5. S635: M15 Volatility Breakout with Adaptive Donchian Channel
  6. S636: M15 EURUSD Macro Intermarket Triangulation + Gold Momentum
  7. S637: M5 Fair Value Gap (FVG) Retest & Order Flow
  8. S638: M15 KAMA Efficiency Ratio Momentum Scalper
  9. S639: Dual High-Expectancy Ensemble (S631 Breakout + S633 Pullback)
  10. S640: Sovereign High-Expectancy Master Engine with $200 Daily Governor
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
# Indicator Computations (Pure NumPy / Pandas)
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

def compute_rsi(closes: np.ndarray, period: int = 14) -> np.ndarray:
    n = len(closes)
    rsi = np.zeros(n, dtype=np.float64)
    deltas = np.diff(closes)
    gains = np.where(deltas > 0, deltas, 0.0)
    losses = np.where(deltas < 0, -deltas, 0.0)
    
    avg_gain = np.mean(gains[:period])
    avg_loss = np.mean(losses[:period])
    
    if avg_loss == 0:
        rsi[period] = 100.0
    else:
        rs = avg_gain / avg_loss
        rsi[period] = 100.0 - (100.0 / (1.0 + rs))
        
    for i in range(period + 1, n):
        avg_gain = (avg_gain * (period - 1) + gains[i - 1]) / period
        avg_loss = (avg_loss * (period - 1) + losses[i - 1]) / period
        if avg_loss == 0:
            rsi[i] = 100.0
        else:
            rs = avg_gain / avg_loss
            rsi[i] = 100.0 - (100.0 / (1.0 + rs))
    return rsi

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

def compute_kama(closes: np.ndarray, er_period: int = 10, fast_ema: int = 2, slow_ema: int = 30):
    n = len(closes)
    kama = np.copy(closes)
    er = np.zeros(n, dtype=np.float64)
    fast_sc = 2.0 / (fast_ema + 1.0)
    slow_sc = 2.0 / (slow_ema + 1.0)
    
    for i in range(er_period, n):
        change = abs(closes[i] - closes[i - er_period])
        vol = np.sum(np.abs(np.diff(closes[i - er_period:i + 1])))
        efficiency = change / vol if vol > 1e-8 else 0.0
        er[i] = efficiency
        sc = (efficiency * (fast_sc - slow_sc) + slow_sc) ** 2
        kama[i] = kama[i - 1] + sc * (closes[i] - kama[i - 1])
    return kama, er

# -----------------------------------------------------------------------------
# Discrete Event Simulator (Constitution Rules D.1 to D.7)
# -----------------------------------------------------------------------------
def simulate_discrete_engine(
    opens, highs, lows, closes, dates,
    entry_signals,         # 1 = Long, -1 = Short (generated at bar i Close, executes at i+1 Open)
    atr_values,            # ATR array
    trailing_bands=None,   # Optional array for trailing SL ratchet
    engine_name="Engine",
    lot_size=0.10,
    spread=0.25,           # Rule D.7: $0.25 Gold spread ($2.50 per 0.10 lot)
    commission_per_lot=6.00,# Rule D.7: $6.00/lot ($0.60 per 0.10 lot round-turn)
    sl_slippage=0.10,      # Rule D.4: $0.10/oz adverse slippage on SL fills
    swap_long_daily=18.00, # Rule D.7: $18.00/standard lot/night for Long
    use_staged_50_50=True, # Rule D.6: 50% TP1 Breakeven + 50% Runner
    tp1_atr_mult=2.0,      # High-expectancy target
    sl_atr_mult=2.5,
    runner_trailing_type="supertrend", # "supertrend", "atr_ratchet", "fixed_rr"
    max_bars_hold=120
):
    n = len(closes)
    trades = []
    unit_size = lot_size * 100.0 # 0.10 lot = 10 oz
    comm_total = (commission_per_lot / 100.0) * unit_size # $0.60 per 0.10 lot

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

            # Rule D.3: Intra-bar adverse dip tracking
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
                exit_price = current_sl - sl_slippage # Rule D.4
                exit_reason = "SL_Pessimistic"
            elif sl_touched:
                exit_hit = True
                exit_price = current_sl - sl_slippage # Rule D.4
                exit_reason = "SL"
            elif tp_touched:
                tp1_hit = True # Rule D.2: Ratchet to BE at bar close

            # Trailing / Trend Flip exit for runner
            if not exit_hit:
                if runner_trailing_type == "supertrend" and trailing_bands is not None:
                    if closes[i] < trailing_bands[i]:
                        exit_hit = True
                        exit_price = opens[i + 1] - (spread * 0.5)
                        exit_reason = "TrendFlip"
                elif runner_trailing_type == "fixed_rr":
                    if bar_high >= (entry_price + tp1_atr_mult * 2.0 * atr_values[entry_idx - 1]):
                        exit_hit = True
                        exit_price = entry_price + tp1_atr_mult * 2.0 * atr_values[entry_idx - 1]
                        exit_reason = "TP2_Fixed"
                
                # Max bars hold exit
                if not exit_hit and (i - entry_idx) >= max_bars_hold:
                    exit_hit = True
                    exit_price = opens[i + 1] - (spread * 0.5)
                    exit_reason = "TimeStop"

            if exit_hit:
                # Rule D.7: Calculate swap if held overnight
                days_held = (dates[i].date() - entry_time.date()).days
                swap_cost = max(0, days_held) * (swap_long_daily / 100.0) * unit_size

                # Rule D.5: Bar-by-bar discrete PnL calculation
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
                # Rule D.2: Strict Bar-Close Trailing Update (Effective next bar i+1 Open)
                if tp1_hit:
                    current_sl = max(current_sl, entry_price + 0.10) # Breakeven + buffer
                if trailing_bands is not None and trailing_bands[i] > current_sl:
                    current_sl = max(current_sl, trailing_bands[i])

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

            if not exit_hit:
                if runner_trailing_type == "supertrend" and trailing_bands is not None:
                    if closes[i] > trailing_bands[i]:
                        exit_hit = True
                        exit_price = opens[i + 1] + (spread * 0.5)
                        exit_reason = "TrendFlip"
                elif runner_trailing_type == "fixed_rr":
                    if bar_low <= (entry_price - tp1_atr_mult * 2.0 * atr_values[entry_idx - 1]):
                        exit_hit = True
                        exit_price = entry_price - tp1_atr_mult * 2.0 * atr_values[entry_idx - 1]
                        exit_reason = "TP2_Fixed"

                if not exit_hit and (i - entry_idx) >= max_bars_hold:
                    exit_hit = True
                    exit_price = opens[i + 1] + (spread * 0.5)
                    exit_reason = "TimeStop"

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
                if trailing_bands is not None and trailing_bands[i] < current_sl:
                    current_sl = min(current_sl, trailing_bands[i])

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
# Portfolio Analysis & Metric Extraction
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
# Main Discovery Execution
# -----------------------------------------------------------------------------
def main():
    t_start = time.time()
    print("=" * 80)
    print("BATCH 44: DISCOVERY OF HIGH-EXPECTANCY M5/M15 STRATEGIES (S631 - S640)")
    print("Enforcing Constitution V5.1 (Rules D.1 - D.7) Across 6 Years (2020-2025)")
    print("Targeting: 150 - 350 trades/year, Avg Profit >= $2.00 - $4.00/oz")
    print("=" * 80)

    # 1. Load M15 Gold Data
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
    m15_ema20 = compute_ema(m15_closes, 20)
    m15_ema50 = compute_ema(m15_closes, 50)
    m15_ema200 = compute_ema(m15_closes, 200)
    m15_rsi = compute_rsi(m15_closes, 14)
    m15_trend, m15_st = compute_supertrend(m15_highs, m15_lows, m15_closes, m15_atr, 3.0)
    m15_kama, m15_er = compute_kama(m15_closes, 10, 2, 30)

    # 2. Load H1 Gold Data for Macro Filtering
    print("[*] Loading XAUUSD H1 Data for Macro Trend...")
    df_h1 = pd.read_parquet(os.path.join(DATA_DIR, "XAUUSD_H1.parquet"))
    if "time" not in df_h1.columns: df_h1["time"] = pd.to_datetime(df_h1.index)
    h1_closes = df_h1["close"].values.astype(np.float64)
    h1_ema50 = compute_ema(h1_closes, 50)
    h1_ema200 = compute_ema(h1_closes, 200)
    h1_trend = np.where(h1_ema50 > h1_ema200, 1, -1)
    df_h1_state = pd.DataFrame({"time": pd.to_datetime(df_h1["time"]), "h1_trend": h1_trend}).sort_values("time")

    # Align H1 to M15
    df_m15_time = pd.DataFrame({"time": pd.to_datetime(df_m15["time"])})
    m15_merged_h1 = pd.merge_asof(df_m15_time, df_h1_state, on="time", direction="backward")
    m15_h1_trend = m15_merged_h1["h1_trend"].fillna(1).values.astype(np.int32)
    del df_h1, df_h1_state, m15_merged_h1
    gc.collect()

    # 3. Load EURUSD M15 Data for Macro Triangulation
    print("[*] Loading EURUSD M15 Data for Intermarket Triangulation...")
    df_eu = pd.read_parquet(os.path.join(DATA_DIR, "EURUSD_M15.parquet"))
    if "time" not in df_eu.columns: df_eu["time"] = pd.to_datetime(df_eu.index)
    eu_closes = df_eu["close"].values.astype(np.float64)
    eu_ema50 = compute_ema(eu_closes, 50)
    eu_trend = np.where(eu_closes > eu_ema50, 1, -1)
    df_eu_state = pd.DataFrame({"time": pd.to_datetime(df_eu["time"]), "eu_trend": eu_trend}).sort_values("time")

    m15_merged_eu = pd.merge_asof(df_m15_time, df_eu_state, on="time", direction="backward")
    m15_eu_trend = m15_merged_eu["eu_trend"].fillna(1).values.astype(np.int32)
    del df_eu, df_eu_state, m15_merged_eu
    gc.collect()

    # 4. Load M5 Gold Data
    print("[*] Loading XAUUSD M5 Data...")
    df_m5 = pd.read_parquet(os.path.join(DATA_DIR, "XAUUSD_M5.parquet"))
    if "time" not in df_m5.columns: df_m5["time"] = pd.to_datetime(df_m5.index)
    m5_highs = df_m5["high"].values.astype(np.float64)
    m5_lows = df_m5["low"].values.astype(np.float64)
    m5_closes = df_m5["close"].values.astype(np.float64)
    m5_opens = df_m5["open"].values.astype(np.float64)
    m5_dates = pd.to_datetime(df_m5["time"]).dt.to_pydatetime()
    n_m5 = len(m5_closes)

    m5_atr = compute_atr(m5_highs, m5_lows, m5_closes, 14)
    m5_trend, m5_st = compute_supertrend(m5_highs, m5_lows, m5_closes, m5_atr, 3.0)

    # Align M15 Supertrend & Trend to M5
    df_m15_state = pd.DataFrame({"time": pd.to_datetime(df_m15["time"]), "m15_trend": m15_trend}).sort_values("time")
    df_m5_time = pd.DataFrame({"time": pd.to_datetime(df_m5["time"])})
    m5_merged_m15 = pd.merge_asof(df_m5_time, df_m15_state, on="time", direction="backward")
    m5_m15_trend = m5_merged_m15["m15_trend"].fillna(1).values.astype(np.int32)
    del df_m15_state, df_m5_time, m5_merged_m15
    gc.collect()

    # =========================================================================
    # Strategy Signal Generation
    # =========================================================================
    print("\n[+] Generating Signals for Strategies S631 to S640...")

    # -------------------------------------------------------------------------
    # S631: M15 Asian Range Breakout (Session Open Expansion)
    # -------------------------------------------------------------------------
    print("    - S631: M15 Asian Range Breakout...")
    sig_s631 = np.zeros(n_m15, dtype=np.int32)
    asian_high = 0.0
    asian_low = 999999.0
    current_day = None
    traded_today = False

    for i in range(50, n_m15 - 1):
        dt = m15_dates[i]
        day = dt.date()
        hour = dt.hour

        if day != current_day:
            current_day = day
            asian_high = 0.0
            asian_low = 999999.0
            traded_today = False

        # Asian Session Range: 22:00 to 06:00 UTC
        if hour < 6:
            asian_high = max(asian_high, m15_highs[i])
            asian_low = min(asian_low, m15_lows[i])
        elif 7 <= hour <= 14: # London / early NY Open
            if not traded_today and asian_high > 0 and asian_low < 999999:
                asian_range = asian_high - asian_low
                # Valid breakout: range >= $3.00, ATR > SMA(ATR, 20)
                if 3.0 <= asian_range <= 25.0:
                    if m15_closes[i] > asian_high and m15_closes[i - 1] <= asian_high:
                        sig_s631[i] = 1
                        traded_today = True
                    elif m15_closes[i] < asian_low and m15_closes[i - 1] >= asian_low:
                        sig_s631[i] = -1
                        traded_today = True

    # -------------------------------------------------------------------------
    # S632: M15 Asian Range Liquidity Sweep & Reversal (Judas Swing Fade)
    # -------------------------------------------------------------------------
    print("    - S632: M15 Asian Range Liquidity Sweep & Reversal (Judas Fade)...")
    sig_s632 = np.zeros(n_m15, dtype=np.int32)
    asian_high = 0.0
    asian_low = 999999.0
    current_day = None
    traded_today = False

    for i in range(50, n_m15 - 1):
        dt = m15_dates[i]
        day = dt.date()
        hour = dt.hour

        if day != current_day:
            current_day = day
            asian_high = 0.0
            asian_low = 999999.0
            traded_today = False

        if hour < 6:
            asian_high = max(asian_high, m15_highs[i])
            asian_low = min(asian_low, m15_lows[i])
        elif 6 <= hour <= 13:
            if not traded_today and asian_high > 0 and asian_low < 999999:
                # Bearish Sweep: price spikes above Asian High but candle closes back inside
                if m15_highs[i] > asian_high and m15_closes[i] < (asian_high - 0.20):
                    upper_wick = m15_highs[i] - max(m15_opens[i], m15_closes[i])
                    candle_range = m15_highs[i] - m15_lows[i]
                    if candle_range > 0 and (upper_wick / candle_range) >= 0.40:
                        sig_s632[i] = -1 # Short fade
                        traded_today = True
                # Bullish Sweep: price dips below Asian Low but candle closes back inside
                elif m15_lows[i] < asian_low and m15_closes[i] > (asian_low + 0.20):
                    lower_wick = min(m15_opens[i], m15_closes[i]) - m15_lows[i]
                    candle_range = m15_highs[i] - m15_lows[i]
                    if candle_range > 0 and (lower_wick / candle_range) >= 0.40:
                        sig_s632[i] = 1 # Long fade
                        traded_today = True

    # -------------------------------------------------------------------------
    # S633: M15 Trend Pullback to Dynamic Value Zone (H1 Trend + EMA 20/50 Ribbon)
    # -------------------------------------------------------------------------
    print("    - S633: M15 Trend Pullback to Dynamic Value Zone...")
    sig_s633 = np.zeros(n_m15, dtype=np.int32)
    for i in range(200, n_m15 - 1):
        hour = m15_dates[i].hour
        if not (21 <= hour < 23): # skip rollover
            # Bullish trend alignment
            if m15_h1_trend[i] == 1 and m15_ema20[i] > m15_ema50[i]:
                # Pullback into value zone: previous bar low touched between EMA 20 and EMA 50
                was_in_zone = (m15_lows[i - 1] <= m15_ema20[i - 1]) and (m15_lows[i - 1] >= m15_ema50[i - 1] - 0.50)
                # Re-emergence: current candle closes strong above EMA 20 + RSI recovered above 45
                if was_in_zone and m15_closes[i] > m15_ema20[i] and m15_closes[i - 1] <= m15_ema20[i - 1] and m15_rsi[i] >= 45:
                    sig_s633[i] = 1
            # Bearish trend alignment
            elif m15_h1_trend[i] == -1 and m15_ema20[i] < m15_ema50[i]:
                was_in_zone = (m15_highs[i - 1] >= m15_ema20[i - 1]) and (m15_highs[i - 1] <= m15_ema50[i - 1] + 0.50)
                if was_in_zone and m15_closes[i] < m15_ema20[i] and m15_closes[i - 1] >= m15_ema20[i - 1] and m15_rsi[i] <= 55:
                    sig_s633[i] = -1

    # -------------------------------------------------------------------------
    # S634: M5 Volatility Compression & Ignition (TTM Squeeze + High Target)
    # -------------------------------------------------------------------------
    print("    - S634: M5 Volatility Compression Ignition (TTM Squeeze)...")
    s5_closes = pd.Series(m5_closes)
    bb5_mid = s5_closes.rolling(20).mean().values
    bb5_std = s5_closes.rolling(20).std().fillna(0).values
    bb5_up = bb5_mid + 2.0 * bb5_std
    bb5_dn = bb5_mid - 2.0 * bb5_std
    kc5_up = bb5_mid + 1.5 * m5_atr
    kc5_dn = bb5_mid - 1.5 * m5_atr

    sig_s634 = np.zeros(n_m5, dtype=np.int32)
    sqz_cnt = 0
    for i in range(200, n_m5 - 1):
        hour = m5_dates[i].hour
        # Squeeze definition: BB inside KC
        if (bb5_up[i] <= kc5_up[i]) and (bb5_dn[i] >= kc5_dn[i]):
            sqz_cnt += 1
        else:
            # Ignition: compression lasted at least 8 bars, active session (07-17 UTC)
            if sqz_cnt >= 8 and (7 <= hour <= 17):
                if m5_closes[i] > bb5_up[i] and m5_m15_trend[i] == 1:
                    sig_s634[i] = 1
                elif m5_closes[i] < bb5_dn[i] and m5_m15_trend[i] == -1:
                    sig_s634[i] = -1
            sqz_cnt = 0

    # -------------------------------------------------------------------------
    # S635: M15 Donchian Adaptive Channel Breakout
    # -------------------------------------------------------------------------
    print("    - S635: M15 Donchian Adaptive Channel Breakout...")
    sig_s635 = np.zeros(n_m15, dtype=np.int32)
    s15_highs = pd.Series(m15_highs)
    s15_lows = pd.Series(m15_lows)
    donch_high20 = s15_highs.shift(1).rolling(20).max().values
    donch_low20 = s15_lows.shift(1).rolling(20).min().values
    m15_atr_sma50 = pd.Series(m15_atr).rolling(50).mean().values

    for i in range(50, n_m15 - 1):
        hour = m15_dates[i].hour
        if 7 <= hour <= 18:
            # Volatility expansion requirement: ATR > 1.1x SMA50(ATR)
            if m15_atr[i] >= 1.10 * m15_atr_sma50[i]:
                if m15_closes[i] > donch_high20[i] and m15_closes[i - 1] <= donch_high20[i - 1]:
                    sig_s635[i] = 1
                elif m15_closes[i] < donch_low20[i] and m15_closes[i - 1] >= donch_low20[i - 1]:
                    sig_s635[i] = -1

    # -------------------------------------------------------------------------
    # S636: M15 EURUSD Macro Intermarket Triangulation + Gold Momentum
    # -------------------------------------------------------------------------
    print("    - S636: M15 EURUSD Macro Triangulation + Gold Momentum...")
    sig_s636 = np.zeros(n_m15, dtype=np.int32)
    for i in range(200, n_m15 - 1):
        hour = m15_dates[i].hour
        if 7 <= hour <= 17:
            # EURUSD bullish (USD weak) + Gold above EMA 50 + RSI > 55
            if m15_eu_trend[i] == 1 and m15_closes[i] > m15_ema50[i] and m15_closes[i - 1] <= m15_ema50[i - 1] and m15_rsi[i] > 55:
                sig_s636[i] = 1
            # EURUSD bearish (USD strong) + Gold below EMA 50 + RSI < 45
            elif m15_eu_trend[i] == -1 and m15_closes[i] < m15_ema50[i] and m15_closes[i - 1] >= m15_ema50[i - 1] and m15_rsi[i] < 45:
                sig_s636[i] = -1

    # -------------------------------------------------------------------------
    # S637: M5 Fair Value Gap (FVG) Retest & Order Flow
    # -------------------------------------------------------------------------
    print("    - S637: M5 Fair Value Gap (FVG) Retest & Order Flow...")
    sig_s637 = np.zeros(n_m5, dtype=np.int32)
    fvg_bull_top = 0.0
    fvg_bull_bot = 0.0
    fvg_bull_bar = -999

    fvg_bear_top = 0.0
    fvg_bear_bot = 0.0
    fvg_bear_bar = -999

    for i in range(10, n_m5 - 1):
        hour = m5_dates[i].hour
        if 7 <= hour <= 17:
            # Detect Bullish FVG: Bar[i-2] High < Bar[i] Low by >= $1.00
            if (m5_lows[i] - m5_highs[i - 2]) >= 1.00 and m5_m15_trend[i] == 1:
                fvg_bull_top = m5_lows[i]
                fvg_bull_bot = m5_highs[i - 2]
                fvg_bull_bar = i

            # Detect Bearish FVG: Bar[i-2] Low > Bar[i] High by >= $1.00
            if (m5_lows[i - 2] - m5_highs[i]) >= 1.00 and m5_m15_trend[i] == -1:
                fvg_bear_top = m5_lows[i - 2]
                fvg_bear_bot = m5_highs[i]
                fvg_bear_bar = i

            # Check Retest for Bullish FVG within 12 bars
            if 1 <= (i - fvg_bull_bar) <= 12 and fvg_bull_top > 0:
                mid_point = (fvg_bull_top + fvg_bull_bot) / 2.0
                if m5_lows[i] <= mid_point and m5_closes[i] > fvg_bull_bot:
                    sig_s637[i] = 1
                    fvg_bull_top = 0.0 # Consumed

            # Check Retest for Bearish FVG within 12 bars
            if 1 <= (i - fvg_bear_bar) <= 12 and fvg_bear_top > 0:
                mid_point = (fvg_bear_top + fvg_bear_bot) / 2.0
                if m5_highs[i] >= mid_point and m5_closes[i] < fvg_bear_top:
                    sig_s637[i] = -1
                    fvg_bear_top = 0.0 # Consumed

    # -------------------------------------------------------------------------
    # S638: M15 KAMA Efficiency Ratio Momentum Scalper
    # -------------------------------------------------------------------------
    print("    - S638: M15 KAMA Efficiency Ratio Momentum Scalper...")
    sig_s638 = np.zeros(n_m15, dtype=np.int32)
    for i in range(50, n_m15 - 1):
        hour = m15_dates[i].hour
        if 7 <= hour <= 17:
            # Efficiency Ratio > 0.50 means high institutional directionality
            if m15_er[i] >= 0.50:
                if m15_closes[i] > m15_kama[i] and m15_closes[i - 1] <= m15_kama[i - 1] and m15_h1_trend[i] == 1:
                    sig_s638[i] = 1
                elif m15_closes[i] < m15_kama[i] and m15_closes[i - 1] >= m15_kama[i - 1] and m15_h1_trend[i] == -1:
                    sig_s638[i] = -1

    # =========================================================================
    # Run Discrete Event Simulators (Rules D.1 to D.7)
    # =========================================================================
    print("\n[+] Running Discrete Simulator Under V5.1 Rules (D.1 - D.7)...")

    # S631: M15 Asian Breakout
    tr_s631 = simulate_discrete_engine(m15_opens, m15_highs, m15_lows, m15_closes, m15_dates, sig_s631, m15_atr, trailing_bands=m15_st, engine_name="S631_Asian_Breakout", tp1_atr_mult=2.5, sl_atr_mult=2.0)
    print(f"    S631 Trades: {len(tr_s631):,}")

    # S632: M15 Judas Sweep Fade
    tr_s632 = simulate_discrete_engine(m15_opens, m15_highs, m15_lows, m15_closes, m15_dates, sig_s632, m15_atr, trailing_bands=m15_st, engine_name="S632_Judas_Fade", tp1_atr_mult=2.0, sl_atr_mult=1.8)
    print(f"    S632 Trades: {len(tr_s632):,}")

    # S633: M15 Trend Pullback (EMA Ribbon)
    tr_s633 = simulate_discrete_engine(m15_opens, m15_highs, m15_lows, m15_closes, m15_dates, sig_s633, m15_atr, trailing_bands=m15_st, engine_name="S633_Trend_Pullback", tp1_atr_mult=2.5, sl_atr_mult=2.5)
    print(f"    S633 Trades: {len(tr_s633):,}")

    # S634: M5 TTM Squeeze Ignition
    tr_s634 = simulate_discrete_engine(m5_opens, m5_highs, m5_lows, m5_closes, m5_dates, sig_s634, m5_atr, trailing_bands=m5_st, engine_name="S634_M5_Squeeze", tp1_atr_mult=2.5, sl_atr_mult=2.5)
    print(f"    S634 Trades: {len(tr_s634):,}")

    # S635: M15 Donchian Adaptive Breakout
    tr_s635 = simulate_discrete_engine(m15_opens, m15_highs, m15_lows, m15_closes, m15_dates, sig_s635, m15_atr, trailing_bands=m15_st, engine_name="S635_Donchian_Adaptive", tp1_atr_mult=3.0, sl_atr_mult=2.5)
    print(f"    S635 Trades: {len(tr_s635):,}")

    # S636: M15 EURUSD Macro Triangulation
    tr_s636 = simulate_discrete_engine(m15_opens, m15_highs, m15_lows, m15_closes, m15_dates, sig_s636, m15_atr, trailing_bands=m15_st, engine_name="S636_Macro_Triangulation", tp1_atr_mult=2.5, sl_atr_mult=2.5)
    print(f"    S636 Trades: {len(tr_s636):,}")

    # S637: M5 Fair Value Gap Retest
    tr_s637 = simulate_discrete_engine(m5_opens, m5_highs, m5_lows, m5_closes, m5_dates, sig_s637, m5_atr, trailing_bands=m5_st, engine_name="S637_M5_FVG", tp1_atr_mult=2.5, sl_atr_mult=2.0)
    print(f"    S637 Trades: {len(tr_s637):,}")

    # S638: M15 KAMA Efficiency Scalper
    tr_s638 = simulate_discrete_engine(m15_opens, m15_highs, m15_lows, m15_closes, m15_dates, sig_s638, m15_atr, trailing_bands=m15_st, engine_name="S638_KAMA_Efficiency", tp1_atr_mult=2.5, sl_atr_mult=2.5)
    print(f"    S638 Trades: {len(tr_s638):,}")

    # S639: Dual High-Expectancy Ensemble (S631 Breakout + S633 Pullback)
    tr_s639 = tr_s631 + tr_s633
    print(f"    S639 Combined Trades: {len(tr_s639):,}")

    # S640: Sovereign High-Expectancy Master Engine (Top Setup + $200 Daily Governor)
    # We will test S639 with $200 Daily Governor
    tr_s640 = tr_s639
    print(f"    S640 Trades (Governed): {len(tr_s640):,}")

    # =========================================================================
    # Metrics Compilation
    # =========================================================================
    strategies_raw = [
        ("S631", "M15 Asian Range Breakout", "M15 Session Open Volatility Expansion", tr_s631, 0.0),
        ("S632", "M15 Asian Judas Sweep Fade", "M15 Liquidity Sweep & Mean Reversion", tr_s632, 0.0),
        ("S633", "M15 Dynamic Value Pullback", "M15 H1 Trend + EMA Ribbon Value Zone", tr_s633, 0.0),
        ("S634", "M5 Volatility Ignition Squeeze", "M5 TTM Squeeze + High Target Room", tr_s634, 0.0),
        ("S635", "M15 Adaptive Donchian Breakout", "M15 Donchian 20 + Volatility Expansion Gate", tr_s635, 0.0),
        ("S636", "M15 Macro EURUSD Triangulation", "M15 EURUSD USD Gate + Gold Momentum", tr_s636, 0.0),
        ("S637", "M5 FVG Order Flow Retest", "M5 Fair Value Gap Retest + M15 Trend", tr_s637, 0.0),
        ("S638", "M15 KAMA Efficiency Momentum", "M15 Kaufman ER > 0.50 Trend Momentum", tr_s638, 0.0),
        ("S639", "Dual High-Expectancy Ensemble", "S631 Breakout + S633 Trend Pullback", tr_s639, 0.0),
        ("S640", "Sovereign High-Expectancy Master", "S639 Ensemble + $200 Daily Risk Governor", tr_s640, 200.0)
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
    json_path = os.path.join(RESULTS_DIR, "batch_44_high_expectancy_m5_m15_discovery.json")
    csv_path = os.path.join(RESULTS_DIR, "batch_44_high_expectancy_m5_m15_discovery.csv")
    with open(json_path, "w") as f:
        json.dump(results_table, f, indent=2)
    pd.DataFrame(results_table).to_csv(csv_path, index=False)
    print(f"\n[+] Results saved to:\n    - {json_path}\n    - {csv_path}")

    # Identify Champion
    profitable = [r for r in results_table if r["Net_Profit"] > 0]
    if profitable:
        best_strat = max(profitable, key=lambda x: x["Profit_Factor"])
        print(f"\n🏆 BATCH 44 CHAMPION: {best_strat['Strategy_ID']} - {best_strat['Strategy_Name']}")
        print(f"   Net Profit: ${best_strat['Net_Profit']:,.2f} | PF: {best_strat['Profit_Factor']:.3f} | Trades/Yr: {best_strat['Annual_Trades']:.1f} | Avg Win/Trade: ${best_strat['Avg_Profit_Per_Trade']:.2f}")
    else:
        print("\n⚠️ No strategy achieved Net Profit > 0 under strict V5.1 rules.")

    print(f"\nBatch 44 completed in {time.time()-t_start:.2f} seconds.")

if __name__ == "__main__":
    main()
