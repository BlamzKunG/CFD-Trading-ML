#!/usr/bin/env python3
"""
===============================================================================
BATCH 53: MACHINE LEARNING REGIME CLASSIFICATION & EFFICIENCY RATIO GATING
===============================================================================
Executes 30 Strategies (S786 to S815) on Google Colab Cloud VM
under 100% strict adherence to Constitution V5.1 (Rules D.1 to D.7):
- Rule D.1: Pessimistic Sequence Mandate (SL triggered first if both hit in 1 bar)
- Rule D.2: Strict Bar-Close Trailing Mandate (effective next bar Open)
- Rule D.3: Intra-Bar Equity Tracking Mandate (Max DD measured from deepest intra-bar adverse dip)
- Rule D.4: Negative Slippage on Stop Loss (-$0.10/trade on all SL fills)
- Rule D.5: 100% Bar-by-Bar Discrete Simulation (Zero Synthetic Multipliers)
- Rule D.6: Lot Step Realism (Exact 0.01 lot multiples)
- Rule D.7: Institutional Frictions ($0.25 spread + $6.00 comm + -$18/lot swap)
- Strict Anti-Lookahead Causality: H1 closed bar only (+1H shift), M15 closed bar only

Exploration Matrices (30 Strategies: S786 - S815):
1. S786 - S795: Kaufman Efficiency Ratio (ER) Gating on S700 (ER Thresholds 0.20 - 0.50)
2. S796 - S805: Volatility Expansion Ratio (VR = ATR14/ATR100) Gating on S700 & S682
3. S806 - S815: Dual Sovereign Regime-Gated Master Suites with Dynamic Risk Sizing
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
# Discrete Event Simulator Supporting Dynamic Sizing (Rules D.1 to D.7)
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
    max_lot=0.20,
    spread=0.25,
    commission_per_lot=6.00,
    sl_slippage=0.10,
    swap_long_daily=18.00,
    initial_sl_atr_mult=3.0
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
    print("🚀 BATCH 53: REGIME CLASSIFICATION & EFFICIENCY RATIO GATING")
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
    print("[*] Computing Indicators, Kaufman Efficiency Ratios, and Volatility Ratios...")
    m15_atr14 = compute_atr(m15_highs, m15_lows, m15_closes, 14)
    m15_atr100 = compute_atr(m15_highs, m15_lows, m15_closes, 100)
    m15_vol_ratio = np.divide(m15_atr14, np.where(m15_atr100 > 0, m15_atr100, 1.0))

    m15_er14 = compute_efficiency_ratio(m15_closes, 14)
    m15_er_ema20 = compute_ema(m15_er14, 20)

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
    def generate_regime_signals(session_start=7, session_end=17, min_atr=1.50, min_er=0.0, use_dyn_er=False, min_vr=0.0):
        sig = np.zeros(n_m15, dtype=np.int32)
        for i in range(200, n_m15 - 1):
            h = m15_dates[i].hour
            if session_start <= h <= session_end:
                if min_atr <= 0.0 or m15_atr14[i] >= min_atr:
                    # ER Check
                    if min_er > 0.0 and m15_er14[i] < min_er:
                        continue
                    if use_dyn_er and m15_er14[i] < m15_er_ema20[i]:
                        continue
                    # VR Check
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

    def run_s700_regime(min_er=0.0, use_dyn_er=False, min_vr=0.0, lot=0.10, dyn_risk=0.0):
        sig_m15 = generate_regime_signals(7, 17, 1.50, min_er=min_er, use_dyn_er=use_dyn_er, min_vr=min_vr)
        sig_h1 = generate_h1_macro_signals(7, 17, min_er=min_er, min_vr=min_vr)
        t1 = simulate_discrete_engine(m15_opens, m15_highs, m15_lows, m15_closes, m15_dates, sig_m15, m15_atr14, st_b30, "M15_Regime", lot_size=lot, dynamic_vol_risk=dyn_risk)
        t2 = simulate_discrete_engine(m15_opens, m15_highs, m15_lows, m15_closes, m15_dates, sig_h1, m15_atr14, m15_h1_st, "H1_Regime", lot_size=lot, dynamic_vol_risk=dyn_risk)
        return t1 + t2

    def run_s682_regime(min_er=0.0, min_vr=0.0, lot=0.10, dyn_risk=0.0):
        sig_s682 = generate_regime_signals(6, 10, 1.50, min_er=min_er, min_vr=min_vr)
        return simulate_discrete_engine(m15_opens, m15_highs, m15_lows, m15_closes, m15_dates, sig_s682, m15_atr14, st_b30, "S682_Regime", lot_size=lot, dynamic_vol_risk=dyn_risk)

    # 4. Construct Strategy Definitions (S786 to S815)
    print("\n[+] Constructing 30 Strategies (S786 - S815)...")
    strategy_definitions = [
        # Group 1: Efficiency Ratio Gating on S700 (S786 - S795)
        ("S786", "S700 Reference Benchmark (No ER)", lambda: run_s700_regime(), 160.0, "Reference Benchmark (No Filter)"),
        ("S787", "S700 + Efficiency Ratio >= 0.20", lambda: run_s700_regime(min_er=0.20), 160.0, "Mild Noise Filter (ER >= 0.20)"),
        ("S788", "S700 + Efficiency Ratio >= 0.25", lambda: run_s700_regime(min_er=0.25), 160.0, "Moderate Noise Filter (ER >= 0.25)"),
        ("S789", "S700 + Efficiency Ratio >= 0.30", lambda: run_s700_regime(min_er=0.30), 160.0, "Clean Trend Gate (ER >= 0.30)"),
        ("S790", "S700 + Efficiency Ratio >= 0.35", lambda: run_s700_regime(min_er=0.35), 160.0, "High Trend Efficiency (ER >= 0.35)"),
        ("S791", "S700 + Efficiency Ratio >= 0.40", lambda: run_s700_regime(min_er=0.40), 160.0, "Ultra Trend Efficiency (ER >= 0.40)"),
        ("S792", "S700 + Efficiency Ratio >= 0.45", lambda: run_s700_regime(min_er=0.45), 160.0, "Strict Directional Gate (ER >= 0.45)"),
        ("S793", "S700 + Efficiency Ratio >= 0.50", lambda: run_s700_regime(min_er=0.50), 160.0, "Extreme Directional Gate (ER >= 0.50)"),
        ("S794", "S700 + Dynamic ER (ER >= EMA20)", lambda: run_s700_regime(use_dyn_er=True), 160.0, "Dynamic Adaptive ER Gate"),
        ("S795", "S700 + ER >= 0.30 + Dyn Risk $300", lambda: run_s700_regime(min_er=0.30, dyn_risk=300.0), 180.0, "ER Gate + Dynamic Dollar Sizing"),

        # Group 2: Volatility Expansion Ratio (VR = ATR14/ATR100) Gating (S796 - S805)
        ("S796", "S700 + Vol Expansion VR >= 1.00", lambda: run_s700_regime(min_vr=1.00), 160.0, "Expanding Volatility Only (VR >= 1.00)"),
        ("S797", "S700 + Vol Expansion VR >= 1.10", lambda: run_s700_regime(min_vr=1.10), 160.0, "Strong Expansion (VR >= 1.10)"),
        ("S798", "S700 + Vol Expansion VR >= 1.20", lambda: run_s700_regime(min_vr=1.20), 160.0, "Super Expansion (VR >= 1.20)"),
        ("S799", "S700 + Vol Expansion VR >= 1.30", lambda: run_s700_regime(min_vr=1.30), 160.0, "Extreme Expansion (VR >= 1.30)"),
        ("S800", "S682 Early London + ER >= 0.30", lambda: run_s682_regime(min_er=0.30), 0.0, "S682 with ER >= 0.30"),
        ("S801", "S682 Early London + ER >= 0.40", lambda: run_s682_regime(min_er=0.40), 0.0, "S682 with ER >= 0.40"),
        ("S802", "S682 Early London + VR >= 1.10", lambda: run_s682_regime(min_vr=1.10), 0.0, "S682 with VR >= 1.10"),
        ("S803", "S682 Early London + VR >= 1.20", lambda: run_s682_regime(min_vr=1.20), 0.0, "S682 with VR >= 1.20"),
        ("S804", "S682 Dual Gate (ER 0.30 & VR 1.10)", lambda: run_s682_regime(min_er=0.30, min_vr=1.10), 0.0, "S682 Dual Efficiency & Vol Gate"),
        ("S805", "S682 Dual Gate + Dyn Risk $200", lambda: run_s682_regime(min_er=0.30, min_vr=1.10, dyn_risk=200.0), 0.0, "S682 Dual Gate + Dynamic Risk"),

        # Group 3: Dual Sovereign Regime-Gated Master Suites (S806 - S815)
        ("S806", "Dual Sovereign + ER >= 0.25", lambda: run_s700_regime(min_er=0.25, lot=0.07) + run_s682_regime(min_er=0.25, lot=0.07), 160.0, "Dual Sovereign ER >= 0.25"),
        ("S807", "Dual Sovereign + ER >= 0.30", lambda: run_s700_regime(min_er=0.30, lot=0.07) + run_s682_regime(min_er=0.30, lot=0.07), 160.0, "Dual Sovereign ER >= 0.30"),
        ("S808", "Dual Sovereign + ER >= 0.35", lambda: run_s700_regime(min_er=0.35, lot=0.07) + run_s682_regime(min_er=0.35, lot=0.07), 160.0, "Dual Sovereign ER >= 0.35"),
        ("S809", "Dual Sovereign + VR >= 1.10", lambda: run_s700_regime(min_vr=1.10, lot=0.07) + run_s682_regime(min_vr=1.10, lot=0.07), 160.0, "Dual Sovereign VR >= 1.10"),
        ("S810", "Dual Sovereign + Dual Filter (ER & VR)", lambda: run_s700_regime(min_er=0.30, min_vr=1.10, lot=0.07) + run_s682_regime(min_er=0.30, min_vr=1.10, lot=0.07), 160.0, "Dual Sovereign Dual Gated"),
        ("S811", "Dual Sovereign Regime Master ($160 Gov)", lambda: run_s700_regime(min_er=0.30, lot=0.07) + run_s682_regime(min_er=0.30, lot=0.07), 160.0, "Regime Master $160 Governor"),
        ("S812", "Dual Sovereign Regime Master ($200 Gov)", lambda: run_s700_regime(min_er=0.30, lot=0.07) + run_s682_regime(min_er=0.30, lot=0.07), 200.0, "Regime Master $200 Governor"),
        ("S813", "Centennial Regime Dynamic Vol $250", lambda: run_s700_regime(min_er=0.30, dyn_risk=250.0), 180.0, "S700 ER >= 0.30 + Dyn Risk $250"),
        ("S814", "Centennial Regime Dynamic Vol $300", lambda: run_s700_regime(min_er=0.30, dyn_risk=300.0), 180.0, "S700 ER >= 0.30 + Dyn Risk $300"),
        ("S815", "Sovereign Millennium Regime Monument", lambda: run_s700_regime(min_er=0.30, min_vr=1.10, dyn_risk=200.0) + run_s682_regime(min_er=0.30, min_vr=1.10, dyn_risk=150.0), 200.0, "All-Weather Dual Regime Monument")
    ]

    # 5. Evaluation and Reporting
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

    # 6. Save Artifacts
    json_path = os.path.join(RESULTS_DIR, "batch_53_regime_classification_results.json")
    csv_path = os.path.join(RESULTS_DIR, "batch_53_regime_classification_matrix.csv")

    with open(json_path, "w") as f:
        json.dump(results_table, f, indent=2)
    pd.DataFrame(results_table).to_csv(csv_path, index=False)

    print(f"\n[+] Batch 53 Completed in {time.time()-t_start:.2f} seconds.")
    print(f"    Results saved to:\n    - {json_path}\n    - {csv_path}")

if __name__ == "__main__":
    main()
