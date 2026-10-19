#!/usr/bin/env python3
"""
===============================================================================
BATCH 51: DYNAMIC VOLATILITY TARGETING & MULTI-ASSET SOVEREIGN PORTFOLIOS
===============================================================================
Executes 30 Strategies (S726 to S755) on Google Colab Cloud VM
under 100% strict adherence to Constitution V5.1 (Rules D.1 to D.7):
- Rule D.1: Pessimistic Sequence Mandate (SL triggered first if both hit in 1 bar)
- Rule D.2: Strict Bar-Close Trailing Mandate (effective next bar Open)
- Rule D.3: Intra-Bar Equity Tracking Mandate (Max DD measured from deepest intra-bar adverse dip)
- Rule D.4: Negative Slippage on Stop Loss (-$0.10/trade on Gold, -0.5 pip on EURUSD)
- Rule D.5: 100% Bar-by-Bar Discrete Simulation (Zero Synthetic Multipliers)
- Rule D.6: Lot Step Realism (Exact 0.01 lot multiples, max 2-3 tranches)
- Rule D.7: Institutional Frictions (Gold: $0.25 spd + $6 comm + -$18 swap; EURUSD: 1.0 pip spd + $6 comm + -$4 swap)
- Strict Anti-Lookahead Causality: H1 closed bar only (+1H shift), M15 closed bar only

Exploration Matrices (30 Strategies: S726 - S755):
1. S726 - S735: Dynamic Volatility Targeting on S700 & S682 (Dollar Risk Sweeps $150 - $350)
2. S736 - S745: Multi-Tranche Partial Take-Profit Optimization (2-Tranche vs 3-Tranche Staged Scale-outs)
3. S746 - S755: Multi-Asset Sovereign Expansion (Direct EURUSD M15 Trading + Joint XAU/EUR Portfolio)
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
# Discrete Event Simulator Supporting Dynamic Sizing & Tranches (Rules D.1 to D.7)
# -----------------------------------------------------------------------------
def simulate_discrete_engine_advanced(
    opens, highs, lows, closes, dates,
    entry_signals,
    atr_values,
    st_bands,
    engine_name="Engine",
    lot_size=0.10,
    dynamic_vol_risk=0.0, # Target dollar risk (e.g. $200) -> lot = risk / (ATR * unit)
    min_lot=0.04,
    max_lot=0.20,
    point_value=100.0, # 100 for Gold, 100,000 for Forex
    spread=0.25,
    commission_per_lot=6.00,
    sl_slippage=0.10,
    swap_long_daily=18.00,
    initial_sl_atr_mult=3.0,
    tranche_mode="runner", # "runner", "staged_2", "staged_3"
    tp1_atr_mult=2.5,
    tp2_atr_mult=4.0
):
    n = len(closes)
    trades = []

    pos = 0
    entry_price = 0.0
    entry_time = None
    entry_idx = 0
    current_sl = 0.0
    active_lot = lot_size
    deepest_dip = 0.0

    tp1_hit = False
    tp2_hit = False

    for i in range(200, n - 2):
        if pos == 1: # Long
            unit_size = active_lot * point_value
            comm_total = (commission_per_lot / 100.0) * unit_size if point_value == 100 else commission_per_lot * active_lot
            bar_low = lows[i]
            bar_high = highs[i]

            dip = min(0.0, (bar_low - entry_price) * unit_size)
            if dip < deepest_dip:
                deepest_dip = dip

            exit_hit = False
            exit_price = 0.0
            exit_reason = ""

            sl_touched = (bar_low <= current_sl)
            trend_flipped = (closes[i] < st_bands[i])

            # Tranche checks
            tp1_target = entry_price + tp1_atr_mult * atr_values[entry_idx - 1]
            tp2_target = entry_price + tp2_atr_mult * atr_values[entry_idx - 1]

            tp1_touched = (bar_high >= tp1_target) if (tranche_mode in ["staged_2", "staged_3"] and not tp1_hit) else False
            tp2_touched = (bar_high >= tp2_target) if (tranche_mode == "staged_3" and tp1_hit and not tp2_hit) else False

            # Rule D.1: Pessimistic Sequence Mandate (SL first)
            if sl_touched and (tp1_touched or tp2_touched):
                exit_hit = True
                exit_price = current_sl - sl_slippage
                exit_reason = "SL_Pessimistic"
            elif sl_touched:
                exit_hit = True
                exit_price = current_sl - sl_slippage
                exit_reason = "SL"
            else:
                if tp1_touched:
                    tp1_hit = True
                    current_sl = max(current_sl, entry_price + 0.20) # Breakeven buffer
                if tp2_touched:
                    tp2_hit = True
                    current_sl = max(current_sl, tp1_target)

                if trend_flipped:
                    exit_hit = True
                    exit_price = opens[i + 1] - (spread * 0.5)
                    exit_reason = "TrendFlip"

            if exit_hit:
                days_held = (dates[i].date() - entry_time.date()).days
                swap_cost = max(0, days_held) * (swap_long_daily / 100.0) * unit_size if point_value == 100 else max(0, days_held) * swap_long_daily * active_lot

                if tranche_mode == "staged_2" and tp1_hit and exit_reason != "SL_Pessimistic":
                    pnl_leg1 = (tp1_target - entry_price) * (unit_size * 0.5) - (spread * unit_size * 0.5) - (comm_total * 0.5)
                    pnl_leg2 = (exit_price - entry_price) * (unit_size * 0.5) - (spread * unit_size * 0.5) - (comm_total * 0.5) - swap_cost
                    net_pnl = pnl_leg1 + pnl_leg2
                elif tranche_mode == "staged_3" and tp2_hit and exit_reason != "SL_Pessimistic":
                    pnl_leg1 = (tp1_target - entry_price) * (unit_size * 0.33) - (spread * unit_size * 0.33) - (comm_total * 0.33)
                    pnl_leg2 = (tp2_target - entry_price) * (unit_size * 0.33) - (spread * unit_size * 0.33) - (comm_total * 0.33)
                    pnl_leg3 = (exit_price - entry_price) * (unit_size * 0.34) - (spread * unit_size * 0.34) - (comm_total * 0.34) - swap_cost
                    net_pnl = pnl_leg1 + pnl_leg2 + pnl_leg3
                elif tranche_mode == "staged_3" and tp1_hit and exit_reason != "SL_Pessimistic":
                    pnl_leg1 = (tp1_target - entry_price) * (unit_size * 0.33) - (spread * unit_size * 0.33) - (comm_total * 0.33)
                    pnl_leg23 = (exit_price - entry_price) * (unit_size * 0.67) - (spread * unit_size * 0.67) - (comm_total * 0.67) - swap_cost
                    net_pnl = pnl_leg1 + pnl_leg23
                else:
                    net_pnl = (exit_price - entry_price) * unit_size - (spread * unit_size) - comm_total - swap_cost

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
            comm_total = (commission_per_lot / 100.0) * unit_size if point_value == 100 else commission_per_lot * active_lot
            bar_low = lows[i]
            bar_high = highs[i]

            dip = min(0.0, (entry_price - bar_high) * unit_size)
            if dip < deepest_dip:
                deepest_dip = dip

            exit_hit = False
            exit_price = 0.0
            exit_reason = ""

            sl_touched = (bar_high >= current_sl)
            trend_flipped = (closes[i] > st_bands[i])

            tp1_target = entry_price - tp1_atr_mult * atr_values[entry_idx - 1]
            tp2_target = entry_price - tp2_atr_mult * atr_values[entry_idx - 1]

            tp1_touched = (bar_low <= tp1_target) if (tranche_mode in ["staged_2", "staged_3"] and not tp1_hit) else False
            tp2_touched = (bar_low <= tp2_target) if (tranche_mode == "staged_3" and tp1_hit and not tp2_hit) else False

            if sl_touched and (tp1_touched or tp2_touched):
                exit_hit = True
                exit_price = current_sl + sl_slippage
                exit_reason = "SL_Pessimistic"
            elif sl_touched:
                exit_hit = True
                exit_price = current_sl + sl_slippage
                exit_reason = "SL"
            else:
                if tp1_touched:
                    tp1_hit = True
                    current_sl = min(current_sl, entry_price - 0.20)
                if tp2_touched:
                    tp2_hit = True
                    current_sl = min(current_sl, tp1_target)

                if trend_flipped:
                    exit_hit = True
                    exit_price = opens[i + 1] + (spread * 0.5)
                    exit_reason = "TrendFlip"

            if exit_hit:
                if tranche_mode == "staged_2" and tp1_hit and exit_reason != "SL_Pessimistic":
                    pnl_leg1 = (entry_price - tp1_target) * (unit_size * 0.5) - (spread * unit_size * 0.5) - (comm_total * 0.5)
                    pnl_leg2 = (entry_price - exit_price) * (unit_size * 0.5) - (spread * unit_size * 0.5) - (comm_total * 0.5)
                    net_pnl = pnl_leg1 + pnl_leg2
                elif tranche_mode == "staged_3" and tp2_hit and exit_reason != "SL_Pessimistic":
                    pnl_leg1 = (entry_price - tp1_target) * (unit_size * 0.33) - (spread * unit_size * 0.33) - (comm_total * 0.33)
                    pnl_leg2 = (entry_price - tp2_target) * (unit_size * 0.33) - (spread * unit_size * 0.33) - (comm_total * 0.33)
                    pnl_leg3 = (entry_price - exit_price) * (unit_size * 0.34) - (spread * unit_size * 0.34) - (comm_total * 0.34)
                    net_pnl = pnl_leg1 + pnl_leg2 + pnl_leg3
                elif tranche_mode == "staged_3" and tp1_hit and exit_reason != "SL_Pessimistic":
                    pnl_leg1 = (entry_price - tp1_target) * (unit_size * 0.33) - (spread * unit_size * 0.33) - (comm_total * 0.33)
                    pnl_leg23 = (entry_price - exit_price) * (unit_size * 0.67) - (spread * unit_size * 0.67) - (comm_total * 0.67)
                    net_pnl = pnl_leg1 + pnl_leg23
                else:
                    net_pnl = (entry_price - exit_price) * unit_size - (spread * unit_size) - comm_total

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
            entry_idx = i + 1
            entry_time = dates[i + 1]
            deepest_dip = 0.0
            tp1_hit = False
            tp2_hit = False

            # Dynamic Volatility Sizing (Rule D.6 Realism: exact 0.01 lot steps)
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
# Portfolio Analysis
# -----------------------------------------------------------------------------
def analyze_trades(all_trades, max_daily_loss=0.0, years=6.0):
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
# Main Execution Pipeline
# -----------------------------------------------------------------------------
def main():
    t_start = time.time()
    now_str = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')
    print("=" * 80)
    print("🚀 BATCH 51: DYNAMIC VOLATILITY TARGETING & MULTI-ASSET SOVEREIGN PORTFOLIOS")
    print(f"Timestamp: {now_str}")
    print(f"Hardware Environment: {'Google Colab VM' if 'content' in REPO_ROOT else 'Local Controller'}")
    print("=" * 80)

    # 1. Load Parquet Data
    print(f"[*] Loading Multi-Asset Parquet Caches from {DATA_DIR}...")
    df_xau_m15 = pd.read_parquet(os.path.join(DATA_DIR, "XAUUSD_M15.parquet"))
    df_xau_h1  = pd.read_parquet(os.path.join(DATA_DIR, "XAUUSD_H1.parquet"))
    df_eu_m15  = pd.read_parquet(os.path.join(DATA_DIR, "EURUSD_M15.parquet"))
    df_eu_h1   = pd.read_parquet(os.path.join(DATA_DIR, "EURUSD_H1.parquet"))

    # Process XAUUSD Buffers
    xau_highs = df_xau_m15["high"].values.astype(np.float64)
    xau_lows  = df_xau_m15["low"].values.astype(np.float64)
    xau_closes = df_xau_m15["close"].values.astype(np.float64)
    xau_opens  = df_xau_m15["open"].values.astype(np.float64)
    xau_dates  = pd.to_datetime(df_xau_m15.index).to_pydatetime()
    n_xau = len(xau_closes)

    # Process EURUSD Buffers
    eu_highs = df_eu_m15["high"].values.astype(np.float64)
    eu_lows  = df_eu_m15["low"].values.astype(np.float64)
    eu_closes = df_eu_m15["close"].values.astype(np.float64)
    eu_opens  = df_eu_m15["open"].values.astype(np.float64)
    eu_dates  = pd.to_datetime(df_eu_m15.index).to_pydatetime()
    n_eu = len(eu_closes)

    # Indicators on XAUUSD
    xau_atr14 = compute_atr(xau_highs, xau_lows, xau_closes, 14)
    xau_ema200 = compute_ema(xau_closes, 200)
    xau_st_tr, xau_st_band = compute_supertrend(xau_highs, xau_lows, xau_closes, xau_atr14, 3.0)

    # Indicators on XAU H1 (Shifted +1H Causal)
    h1_xau_atr14 = compute_atr(df_xau_h1["high"].values.astype(np.float64), df_xau_h1["low"].values.astype(np.float64), df_xau_h1["close"].values.astype(np.float64), 14)
    h1_xau_tr, h1_xau_band = compute_supertrend(df_xau_h1["high"].values.astype(np.float64), df_xau_h1["low"].values.astype(np.float64), df_xau_h1["close"].values.astype(np.float64), h1_xau_atr14, 3.0)
    h1_xau_ema = compute_ema(df_xau_h1["close"].values.astype(np.float64), 200)

    df_xau_h1_state = pd.DataFrame({
        "time": pd.to_datetime(df_xau_h1.index) + pd.Timedelta(hours=1),
        "h1_tr": h1_xau_tr,
        "h1_band": h1_xau_band,
        "h1_ema": h1_xau_ema
    }).sort_values("time")

    df_xau_time = pd.DataFrame({"time": pd.to_datetime(df_xau_m15.index)})
    xau_merged_h1 = pd.merge_asof(df_xau_time, df_xau_h1_state, on="time", direction="backward")
    xau_h1_tr = xau_merged_h1["h1_tr"].fillna(1).values.astype(np.int32)
    xau_h1_band = xau_merged_h1["h1_band"].bfill().values.astype(np.float64)
    xau_h1_ema = xau_merged_h1["h1_ema"].bfill().values.astype(np.float64)

    # EURUSD Macro Gate for Gold
    eu_ema50 = compute_ema(eu_closes, 50)
    eu_regime = np.where(eu_closes > eu_ema50, 1, -1)
    df_eu_state = pd.DataFrame({"time": pd.to_datetime(df_eu_m15.index), "eu_regime": eu_regime}).sort_values("time")
    xau_merged_eu = pd.merge_asof(df_xau_time, df_eu_state, on="time", direction="backward")
    xau_eu_regime = xau_merged_eu["eu_regime"].fillna(1).values.astype(np.int32)

    # Direct EURUSD Trading Indicators
    eu_atr14 = compute_atr(eu_highs, eu_lows, eu_closes, 14)
    eu_ema200 = compute_ema(eu_closes, 200)
    eu_st_tr, eu_st_band = compute_supertrend(eu_highs, eu_lows, eu_closes, eu_atr14, 3.0)

    h1_eu_atr14 = compute_atr(df_eu_h1["high"].values.astype(np.float64), df_eu_h1["low"].values.astype(np.float64), df_eu_h1["close"].values.astype(np.float64), 14)
    h1_eu_tr, h1_eu_band = compute_supertrend(df_eu_h1["high"].values.astype(np.float64), df_eu_h1["low"].values.astype(np.float64), df_eu_h1["close"].values.astype(np.float64), h1_eu_atr14, 3.0)
    h1_eu_ema = compute_ema(df_eu_h1["close"].values.astype(np.float64), 200)

    df_eu_h1_state = pd.DataFrame({
        "time": pd.to_datetime(df_eu_h1.index) + pd.Timedelta(hours=1),
        "h1_tr": h1_eu_tr,
        "h1_band": h1_eu_band,
        "h1_ema": h1_eu_ema
    }).sort_values("time")

    df_eu_time = pd.DataFrame({"time": pd.to_datetime(df_eu_m15.index)})
    eu_merged_h1 = pd.merge_asof(df_eu_time, df_eu_h1_state, on="time", direction="backward")
    eu_h1_tr = eu_merged_h1["h1_tr"].fillna(1).values.astype(np.int32)
    eu_h1_band = eu_merged_h1["h1_band"].bfill().values.astype(np.float64)

    print(f"[+] Synchronized {n_xau:,} XAUUSD bars and {n_eu:,} EURUSD bars under strict causality.")

    # Signal Generators
    def generate_xau_signals(session_start=7, session_end=17, min_atr=1.50):
        sig = np.zeros(n_xau, dtype=np.int32)
        for i in range(200, n_xau - 1):
            h = xau_dates[i].hour
            if session_start <= h <= session_end and xau_atr14[i] >= min_atr:
                if xau_st_tr[i] == 1 and xau_st_tr[i - 1] == -1 and xau_closes[i] > xau_ema200[i]:
                    if xau_h1_tr[i] == 1 and xau_eu_regime[i] == 1:
                        sig[i] = 1
                elif xau_st_tr[i] == -1 and xau_st_tr[i - 1] == 1 and xau_closes[i] < xau_ema200[i]:
                    if xau_h1_tr[i] == -1 and xau_eu_regime[i] == -1:
                        sig[i] = -1
        return sig

    def generate_xau_h1_signals(session_start=7, session_end=17):
        sig = np.zeros(n_xau, dtype=np.int32)
        for i in range(200, n_xau - 1):
            h = xau_dates[i].hour
            if session_start <= h <= session_end and not (21 <= h < 23):
                if xau_h1_tr[i] == 1 and xau_h1_tr[i - 1] == -1 and xau_closes[i] > xau_h1_ema[i] and xau_eu_regime[i] == 1:
                    sig[i] = 1
                elif xau_h1_tr[i] == -1 and xau_h1_tr[i - 1] == 1 and xau_closes[i] < xau_h1_ema[i] and xau_eu_regime[i] == -1:
                    sig[i] = -1
        return sig

    def generate_eu_signals(session_start=7, session_end=17, min_atr=0.0008):
        sig = np.zeros(n_eu, dtype=np.int32)
        for i in range(200, n_eu - 1):
            h = eu_dates[i].hour
            if session_start <= h <= session_end and eu_atr14[i] >= min_atr:
                if eu_st_tr[i] == 1 and eu_st_tr[i - 1] == -1 and eu_closes[i] > eu_ema200[i] and eu_h1_tr[i] == 1:
                    sig[i] = 1
                elif eu_st_tr[i] == -1 and eu_st_tr[i - 1] == 1 and eu_closes[i] < eu_ema200[i] and eu_h1_tr[i] == -1:
                    sig[i] = -1
        return sig

    sig_xau_s700 = generate_xau_signals(7, 17, 1.50)
    sig_xau_h1 = generate_xau_h1_signals(7, 17)
    sig_xau_s682 = generate_xau_signals(6, 10, 1.50)
    sig_eu_s700 = generate_eu_signals(7, 17, 0.0008)

    # -------------------------------------------------------------------------
    # Helper to generate XAU S700 suite
    # -------------------------------------------------------------------------
    def run_xau_s700(dyn_risk=0.0, tranche="runner", lot=0.10, tp1=2.5, tp2=4.0):
        t1 = simulate_discrete_engine_advanced(xau_opens, xau_highs, xau_lows, xau_closes, xau_dates, sig_xau_s700, xau_atr14, xau_st_band, "XAU_M15", lot_size=lot, dynamic_vol_risk=dyn_risk, tranche_mode=tranche, tp1_atr_mult=tp1, tp2_atr_mult=tp2)
        t2 = simulate_discrete_engine_advanced(xau_opens, xau_highs, xau_lows, xau_closes, xau_dates, sig_xau_h1, xau_atr14, xau_h1_band, "XAU_H1", lot_size=lot, dynamic_vol_risk=dyn_risk, tranche_mode=tranche, tp1_atr_mult=tp1, tp2_atr_mult=tp2)
        return t1 + t2

    def run_xau_s682(dyn_risk=0.0, tranche="runner", lot=0.10):
        return simulate_discrete_engine_advanced(xau_opens, xau_highs, xau_lows, xau_closes, xau_dates, sig_xau_s682, xau_atr14, xau_st_band, "XAU_S682", lot_size=lot, dynamic_vol_risk=dyn_risk, tranche_mode=tranche)

    def run_eu_sovereign(lot=0.10, dyn_risk=0.0):
        # EURUSD: point_value=100000, spread=0.00010 (1 pip), comm=$6/lot, slippage=0.00005, swap=$4/lot
        return simulate_discrete_engine_advanced(eu_opens, eu_highs, eu_lows, eu_closes, eu_dates, sig_eu_s700, eu_atr14, eu_st_band, "EURUSD_M15", lot_size=lot, point_value=100000.0, spread=0.00010, commission_per_lot=6.00, sl_slippage=0.00005, swap_long_daily=4.0, dynamic_vol_risk=dyn_risk)

    # -------------------------------------------------------------------------
    # Define Strategy Matrix (S726 - S755)
    # -------------------------------------------------------------------------
    print("\n[+] Constructing 30 Parallel Strategies (S726 - S755)...")
    strategy_definitions = [
        # Group 1: Dynamic Volatility Targeting on XAU S700 (S726 - S735)
        ("S726", "S700 Dynamic Vol Risk $150", lambda: run_xau_s700(dyn_risk=150.0), 160.0, "Dynamic Risk $150 (Lot 0.04-0.20)"),
        ("S727", "S700 Dynamic Vol Risk $180", lambda: run_xau_s700(dyn_risk=180.0), 160.0, "Dynamic Risk $180"),
        ("S728", "S700 Dynamic Vol Risk $200", lambda: run_xau_s700(dyn_risk=200.0), 160.0, "Dynamic Risk $200 (Benchmark Target)"),
        ("S729", "S700 Dynamic Vol Risk $220", lambda: run_xau_s700(dyn_risk=220.0), 160.0, "Dynamic Risk $220"),
        ("S730", "S700 Dynamic Vol Risk $250", lambda: run_xau_s700(dyn_risk=250.0), 160.0, "Dynamic Risk $250"),
        ("S731", "S700 Dynamic Vol Risk $300", lambda: run_xau_s700(dyn_risk=300.0), 180.0, "Dynamic Risk $300 (Aggressive)"),
        ("S732", "S682 Dynamic Vol Risk $150", lambda: run_xau_s682(dyn_risk=150.0), 0.0, "S682 Early London Dynamic $150"),
        ("S733", "S682 Dynamic Vol Risk $200", lambda: run_xau_s682(dyn_risk=200.0), 0.0, "S682 Early London Dynamic $200"),
        ("S734", "Dual Ensemble Dynamic Vol $150", lambda: run_xau_s700(dyn_risk=100.0) + run_xau_s682(dyn_risk=100.0), 160.0, "Dual Ensemble Dynamic $100+$100"),
        ("S735", "Dual Ensemble Dynamic Vol $200", lambda: run_xau_s700(dyn_risk=120.0) + run_xau_s682(dyn_risk=120.0), 180.0, "Dual Ensemble Dynamic $120+$120"),

        # Group 2: Asymmetric Multi-Tranche Partial Take-Profit Optimization (S736 - S745)
        ("S736", "S700 2-Tranche 50/50 @ 2.0x ATR", lambda: run_xau_s700(tranche="staged_2", tp1=2.0), 160.0, "2-Tranche 50/50 @ 2.0x"),
        ("S737", "S700 2-Tranche 50/50 @ 2.5x ATR", lambda: run_xau_s700(tranche="staged_2", tp1=2.5), 160.0, "2-Tranche 50/50 @ 2.5x"),
        ("S738", "S700 2-Tranche 50/50 @ 3.0x ATR", lambda: run_xau_s700(tranche="staged_2", tp1=3.0), 160.0, "2-Tranche 50/50 @ 3.0x"),
        ("S739", "S700 3-Tranche (33/33/34) @ 2.0x & 3.5x", lambda: run_xau_s700(tranche="staged_3", tp1=2.0, tp2=3.5), 160.0, "3-Tranche (33/33/34) Standard"),
        ("S740", "S700 3-Tranche (33/33/34) @ 2.5x & 4.0x", lambda: run_xau_s700(tranche="staged_3", tp1=2.5, tp2=4.0), 160.0, "3-Tranche (33/33/34) Wide"),
        ("S741", "S700 3-Tranche (33/33/34) @ 2.0x & 4.5x", lambda: run_xau_s700(tranche="staged_3", tp1=2.0, tp2=4.5), 160.0, "3-Tranche (33/33/34) Asymmetric"),
        ("S742", "Dual Ensemble 2-Tranche @ 2.5x", lambda: run_xau_s700(tranche="staged_2", tp1=2.5, lot=0.07) + run_xau_s682(tranche="staged_2", lot=0.07), 160.0, "Dual Ensemble 2-Tranche"),
        ("S743", "Dual Ensemble 3-Tranche @ 2.5x & 4.0x", lambda: run_xau_s700(tranche="staged_3", tp1=2.5, tp2=4.0, lot=0.07) + run_xau_s682(lot=0.07), 160.0, "Dual Ensemble S700 3-Tranche + S682"),
        ("S744", "Dynamic Vol $180 + 2-Tranche 50/50", lambda: run_xau_s700(dyn_risk=180.0, tranche="staged_2", tp1=2.5), 160.0, "Dynamic Risk + Staged 50/50"),
        ("S745", "Dynamic Vol $200 + 3-Tranche (33/33/34)", lambda: run_xau_s700(dyn_risk=200.0, tranche="staged_3", tp1=2.5, tp2=4.0), 160.0, "Dynamic Risk + 3-Tranche"),

        # Group 3: Multi-Asset Expansion: EURUSD & Joint XAU/EUR Portfolio (S746 - S755)
        ("S746", "EURUSD Sovereign M15 Baseline", lambda: run_eu_sovereign(lot=0.10), 0.0, "EURUSD Standalone Baseline (0.10 lot)"),
        ("S747", "EURUSD Sovereign M15 Dynamic $150", lambda: run_eu_sovereign(dyn_risk=150.0), 0.0, "EURUSD Dynamic Risk $150"),
        ("S748", "EURUSD Sovereign M15 Governed $100", lambda: run_eu_sovereign(lot=0.10), 100.0, "EURUSD Governed $100 Stop"),
        ("S749", "Joint XAU+EUR Balanced (0.05 lot each)", lambda: run_xau_s700(lot=0.05) + run_eu_sovereign(lot=0.05), 160.0, "Joint Portfolio Equal Lot (0.05 lot)"),
        ("S750", "Joint XAU (0.07) + EUR (0.05) Core", lambda: run_xau_s700(lot=0.07) + run_eu_sovereign(lot=0.05), 180.0, "Joint Portfolio Core Allocation"),
        ("S751", "Joint XAU (0.07) + EUR (0.10) Forex Overweight", lambda: run_xau_s700(lot=0.07) + run_eu_sovereign(lot=0.10), 180.0, "Forex Overweight Joint Model"),
        ("S752", "Triple Sovereign Suite (S700+S682+EURUSD)", lambda: run_xau_s700(lot=0.05) + run_xau_s682(lot=0.05) + run_eu_sovereign(lot=0.05), 200.0, "Triple Multi-Session Multi-Asset Suite"),
        ("S753", "Triple Sovereign Dynamic Vol Suite", lambda: run_xau_s700(dyn_risk=80.0) + run_xau_s682(dyn_risk=80.0) + run_eu_sovereign(dyn_risk=80.0), 200.0, "Triple Dynamic Risk Parity Suite"),
        ("S754", "Grand Sovereign Multi-Asset Apex", lambda: run_xau_s700(lot=0.07) + run_xau_s682(lot=0.05) + run_eu_sovereign(lot=0.05), 200.0, "Grand Sovereign Multi-Asset Apex"),
        ("S755", "Centennial Multi-Asset Millennium Monument", lambda: run_xau_s700(lot=0.07, dyn_risk=150.0) + run_xau_s682(lot=0.05) + run_eu_sovereign(lot=0.05), 220.0, "All-Weather Multi-Asset Monument")
    ]

    # Evaluation
    results_table = []
    print("\n" + "=" * 125)
    print(f"{'ID':<6} {'Strategy Name':<42} {'Ann.Tr':<8} {'Tot.Tr':<8} {'Net PnL ($)':<14} {'PF':<8} {'WR%':<8} {'Intra DD ($)':<14} {'RoMaD':<8} {'MCR%':<8}")
    print("=" * 125)

    for sid, name, fn, gov, role in strategy_definitions:
        trades = fn()
        m = analyze_trades(trades, max_daily_loss=gov, years=6.0)
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
        print(f"{sid:<6} {name:<42} {m['annual_trades']:<8.1f} {m['total_trades']:<8} {m['net_profit']:<14.2f} {m['pf']:<8.3f} {m['win_rate']:<8.1f} {m['max_dd']:<14.2f} {m['romad']:<8.2f} {m['mcr']:<8.1f}")

    print("=" * 125)

    # Save Results
    json_path = os.path.join(RESULTS_DIR, "batch_51_dynamic_vol_multi_asset_results.json")
    csv_path = os.path.join(RESULTS_DIR, "batch_51_dynamic_vol_multi_asset_matrix.csv")

    with open(json_path, "w") as f:
        json.dump(results_table, f, indent=2)
    pd.DataFrame(results_table).to_csv(csv_path, index=False)

    print(f"\n[+] Batch 51 Completed in {time.time()-t_start:.2f} seconds.")
    print(f"    Results saved to:\n    - {json_path}\n    - {csv_path}")

if __name__ == "__main__":
    main()
