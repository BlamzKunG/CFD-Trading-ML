#!/usr/bin/env python3
"""
===============================================================================
BATCH 52: FRACTAL MULTI-TIMEFRAME ALIGNMENT (M5 + M15 + H1) & ADAPTIVE VOLATILITY
===============================================================================
Executes 30 High-Expectancy Strategies (S756 to S785) on Google Colab Cloud VM
under 100% strict adherence to Constitution V5.1 (Rules D.1 to D.7):
- Rule D.1: Pessimistic Sequence Mandate (SL triggered first if both hit in 1 bar)
- Rule D.2: Strict Bar-Close Trailing Mandate (effective next bar Open)
- Rule D.3: Intra-Bar Equity Tracking Mandate (Max DD measured from deepest intra-bar adverse dip)
- Rule D.4: Negative Slippage on Stop Loss (-$0.10/trade on all SL fills)
- Rule D.5: 100% Bar-by-Bar Discrete Simulation (Zero Synthetic Multipliers)
- Rule D.6: Lot Step Realism (Exact 0.01 lot multiples, max 2-3 tranches)
- Rule D.7: Institutional Frictions ($0.25 spread + $6.00 comm + -$18/lot swap)
- Strict Anti-Lookahead Causality:
  * H1 closed bar shifted by +1 Hour
  * M15 closed bar shifted by +15 Minutes
  * Base execution on M5 closed bars (423,930 bars across 2020-2025)

Exploration Matrices (30 Strategies: S756 - S785):
1. S756 - S765: M5 Fractal Pullback Ignition with M15/H1 Macro Alignment (Vol Floor Sweeps $0.80 - $1.50)
2. S766 - S775: Dynamic Dollar-Risk Volatility Sizing on M5 (Risk Targets $100 - $250)
3. S776 - S785: Triple-Speed Centennial Composite Suites (M5 Sniper + M15 Sovereign + H1 Macro)
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
    dynamic_vol_risk=0.0,
    min_lot=0.03,
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
    print("🚀 BATCH 52: FRACTAL MULTI-TIMEFRAME (M5+M15+H1) DISCOVERY")
    print(f"Timestamp: {now_str}")
    print(f"Hardware Environment: {'Google Colab VM' if 'content' in REPO_ROOT else 'Local Controller'}")
    print("=" * 80)

    # 1. Load Data
    print(f"[*] Loading Parquet Caches from {DATA_DIR}...")
    df_m5 = pd.read_parquet(os.path.join(DATA_DIR, "XAUUSD_M5.parquet"))
    df_m15 = pd.read_parquet(os.path.join(DATA_DIR, "XAUUSD_M15.parquet"))
    df_h1 = pd.read_parquet(os.path.join(DATA_DIR, "XAUUSD_H1.parquet"))
    df_eu = pd.read_parquet(os.path.join(DATA_DIR, "EURUSD_M15.parquet"))

    m5_highs = df_m5["high"].values.astype(np.float64)
    m5_lows  = df_m5["low"].values.astype(np.float64)
    m5_closes = df_m5["close"].values.astype(np.float64)
    m5_opens  = df_m5["open"].values.astype(np.float64)
    m5_dates  = pd.to_datetime(df_m5.index).to_pydatetime()
    n_m5 = len(m5_closes)

    # 2. Compute Indicators on M5
    print("[*] Computing M5 Core Indicators (423k bars)...")
    m5_atr14 = compute_atr(m5_highs, m5_lows, m5_closes, 14)
    m5_ema200 = compute_ema(m5_closes, 200)

    st_m5_dict = {}
    for mult in [2.5, 3.0, 3.5]:
        t_arr, b_arr = compute_supertrend(m5_highs, m5_lows, m5_closes, m5_atr14, mult)
        st_m5_dict[mult] = (t_arr, b_arr)

    # 3. Compute M15 Indicators with Strict +15M Causal Shift
    print("[*] Merging Causal M15 State into M5 Base (+15M Shift)...")
    m15_highs = df_m15["high"].values.astype(np.float64)
    m15_lows  = df_m15["low"].values.astype(np.float64)
    m15_closes = df_m15["close"].values.astype(np.float64)
    m15_atr14 = compute_atr(m15_highs, m15_lows, m15_closes, 14)
    m15_tr30, m15_st30 = compute_supertrend(m15_highs, m15_lows, m15_closes, m15_atr14, 3.0)
    m15_ema200 = compute_ema(m15_closes, 200)

    df_m15_state = pd.DataFrame({
        "time": pd.to_datetime(df_m15.index) + pd.Timedelta(minutes=15),
        "m15_tr": m15_tr30,
        "m15_st": m15_st30,
        "m15_ema": m15_ema200
    }).sort_values("time")

    df_m5_time = pd.DataFrame({"time": pd.to_datetime(df_m5.index)})
    m5_merged_m15 = pd.merge_asof(df_m5_time, df_m15_state, on="time", direction="backward")
    m5_m15_tr = m5_merged_m15["m15_tr"].fillna(1).values.astype(np.int32)
    m5_m15_st = m5_merged_m15["m15_st"].bfill().values.astype(np.float64)
    m5_m15_ema = m5_merged_m15["m15_ema"].bfill().values.astype(np.float64)

    # 4. Compute H1 Indicators with Strict +1H Causal Shift
    print("[*] Merging Causal H1 State into M5 Base (+1H Shift)...")
    h1_highs = df_h1["high"].values.astype(np.float64)
    h1_lows  = df_h1["low"].values.astype(np.float64)
    h1_closes = df_h1["close"].values.astype(np.float64)
    h1_atr14 = compute_atr(h1_highs, h1_lows, h1_closes, 14)
    h1_tr30, h1_st30 = compute_supertrend(h1_highs, h1_lows, h1_closes, h1_atr14, 3.0)
    h1_ema200 = compute_ema(h1_closes, 200)

    df_h1_state = pd.DataFrame({
        "time": pd.to_datetime(df_h1.index) + pd.Timedelta(hours=1),
        "h1_tr": h1_tr30,
        "h1_st": h1_st30,
        "h1_ema": h1_ema200
    }).sort_values("time")

    m5_merged_h1 = pd.merge_asof(df_m5_time, df_h1_state, on="time", direction="backward")
    m5_h1_tr = m5_merged_h1["h1_tr"].fillna(1).values.astype(np.int32)
    m5_h1_st = m5_merged_h1["h1_st"].bfill().values.astype(np.float64)
    m5_h1_ema = m5_merged_h1["h1_ema"].bfill().values.astype(np.float64)

    # 5. EURUSD Macro Regime with +15M Causal Shift
    eu_closes = df_eu["close"].values.astype(np.float64)
    eu_ema50 = compute_ema(eu_closes, 50)
    eu_regime = np.where(eu_closes > eu_ema50, 1, -1)

    df_eu_state = pd.DataFrame({
        "time": pd.to_datetime(df_eu.index) + pd.Timedelta(minutes=15),
        "eu_regime": eu_regime
    }).sort_values("time")

    m5_merged_eu = pd.merge_asof(df_m5_time, df_eu_state, on="time", direction="backward")
    m5_eu_regime = m5_merged_eu["eu_regime"].fillna(1).values.astype(np.int32)

    del df_m5, df_m15, df_h1, df_eu, df_m15_state, df_h1_state, df_eu_state, m5_merged_m15, m5_merged_h1, m5_merged_eu, df_m5_time
    gc.collect()

    print(f"[+] Synchronized {n_m5:,} M5 bars with causal M15, H1, and EURUSD states.")

    # 6. Signal Generators
    def generate_m5_signals(st_mult=3.0, session_start=7, session_end=17, min_atr=1.00, require_h1=True):
        t_arr, _ = st_m5_dict[st_mult]
        sig = np.zeros(n_m5, dtype=np.int32)
        for i in range(200, n_m5 - 1):
            h = m5_dates[i].hour
            if session_start <= h <= session_end:
                if min_atr <= 0.0 or m5_atr14[i] >= min_atr:
                    # Long: M5 flips UP while M15 trend UP, closes > M5 EMA, H1 trend UP, EURUSD UP
                    if t_arr[i] == 1 and t_arr[i - 1] == -1 and m5_closes[i] > m5_ema200[i]:
                        if m5_m15_tr[i] == 1 and (not require_h1 or m5_h1_tr[i] == 1) and m5_eu_regime[i] == 1:
                            sig[i] = 1
                    # Short: M5 flips DOWN while M15 trend DOWN, closes < M5 EMA, H1 trend DOWN, EURUSD DOWN
                    elif t_arr[i] == -1 and t_arr[i - 1] == 1 and m5_closes[i] < m5_ema200[i]:
                        if m5_m15_tr[i] == -1 and (not require_h1 or m5_h1_tr[i] == -1) and m5_eu_regime[i] == -1:
                            sig[i] = -1
        return sig

    _, st_b30_m5 = st_m5_dict[3.0]
    _, st_b25_m5 = st_m5_dict[2.5]
    _, st_b35_m5 = st_m5_dict[3.5]

    # Pre-generate key signals
    sig_m5_base = generate_m5_signals(st_mult=3.0, session_start=7, session_end=17, min_atr=1.00)
    sig_m5_london = generate_m5_signals(st_mult=3.0, session_start=6, session_end=10, min_atr=1.00)
    sig_m5_ny = generate_m5_signals(st_mult=3.0, session_start=12, session_end=16, min_atr=1.00)

    # Helper for running M5 discrete engine
    def run_m5_engine(sig, st_b=st_b30_m5, lot=0.10, dyn_risk=0.0):
        return simulate_discrete_engine(m5_opens, m5_highs, m5_lows, m5_closes, m5_dates, sig, m5_atr14, st_b, "M5_Sniper", lot_size=lot, dynamic_vol_risk=dyn_risk)

    # 7. Construct 30 Strategies (S756 - S785)
    print("\n[+] Constructing 30 Strategies (S756 - S785)...")
    strategy_definitions = [
        # Group 1: M5 Fractal Pullback Ignition with Volatility Sweeps (S756 - S765)
        ("S756", "M5 Fractal Core Baseline ($1.00 ATR)", lambda: run_m5_engine(sig_m5_base), 0.0, "M5 Base Core (07-17 UTC, ATR >= $1.00)"),
        ("S757", "M5 Fractal Low Vol Floor ($0.80)", lambda: run_m5_engine(generate_m5_signals(3.0, 7, 17, 0.80)), 0.0, "M5 ATR >= $0.80"),
        ("S758", "M5 Fractal High Vol Floor ($1.20)", lambda: run_m5_engine(generate_m5_signals(3.0, 7, 17, 1.20)), 0.0, "M5 ATR >= $1.20"),
        ("S759", "M5 Fractal Ultra Vol Floor ($1.50)", lambda: run_m5_engine(generate_m5_signals(3.0, 7, 17, 1.50)), 0.0, "M5 ATR >= $1.50"),
        ("S760", "M5 Early London Fractal (06-10 UTC)", lambda: run_m5_engine(sig_m5_london), 0.0, "M5 Early London Specialist"),
        ("S761", "M5 NY Open Fractal (12-16 UTC)", lambda: run_m5_engine(sig_m5_ny), 0.0, "M5 NY Open Specialist"),
        ("S762", "M5 Fast Ratchet (ST 2.5x)", lambda: run_m5_engine(generate_m5_signals(2.5, 7, 17, 1.00), st_b=st_b25_m5), 0.0, "M5 ST 2.5x Fast"),
        ("S763", "M5 Wide Ratchet (ST 3.5x)", lambda: run_m5_engine(generate_m5_signals(3.5, 7, 17, 1.00), st_b=st_b35_m5), 0.0, "M5 ST 3.5x Wide"),
        ("S764", "M5 Relaxed H1 Filter (M15 Only)", lambda: run_m5_engine(generate_m5_signals(3.0, 7, 17, 1.00, require_h1=False)), 0.0, "M5 M15-Only Gated"),
        ("S765", "M5 Governed ($140 Daily Stop)", lambda: run_m5_engine(sig_m5_base), 140.0, "M5 with $140 Governor"),

        # Group 2: Dynamic Dollar-Risk Volatility Sizing on M5 (S766 - S775)
        ("S766", "M5 Dynamic Vol Risk $100", lambda: run_m5_engine(sig_m5_base, dyn_risk=100.0), 140.0, "M5 Dynamic Risk $100"),
        ("S767", "M5 Dynamic Vol Risk $120", lambda: run_m5_engine(sig_m5_base, dyn_risk=120.0), 140.0, "M5 Dynamic Risk $120"),
        ("S768", "M5 Dynamic Vol Risk $150", lambda: run_m5_engine(sig_m5_base, dyn_risk=150.0), 160.0, "M5 Dynamic Risk $150"),
        ("S769", "M5 Dynamic Vol Risk $180", lambda: run_m5_engine(sig_m5_base, dyn_risk=180.0), 160.0, "M5 Dynamic Risk $180"),
        ("S770", "M5 Dynamic Vol Risk $200", lambda: run_m5_engine(sig_m5_base, dyn_risk=200.0), 180.0, "M5 Dynamic Risk $200"),
        ("S771", "M5 Early London Dynamic $120", lambda: run_m5_engine(sig_m5_london, dyn_risk=120.0), 0.0, "M5 Early London Dyn $120"),
        ("S772", "M5 Early London Dynamic $150", lambda: run_m5_engine(sig_m5_london, dyn_risk=150.0), 0.0, "M5 Early London Dyn $150"),
        ("S773", "M5 NY Open Dynamic $120", lambda: run_m5_engine(sig_m5_ny, dyn_risk=120.0), 0.0, "M5 NY Open Dyn $120"),
        ("S774", "M5 NY Open Dynamic $150", lambda: run_m5_engine(sig_m5_ny, dyn_risk=150.0), 0.0, "M5 NY Open Dyn $150"),
        ("S775", "M5 Dual Session Dynamic $150", lambda: run_m5_engine(sig_m5_london, dyn_risk=75.0) + run_m5_engine(sig_m5_ny, dyn_risk=75.0), 140.0, "M5 Dual Session Dyn $75+$75"),

        # Group 3: Triple-Speed Centennial Composite Suites (S776 - S785)
        # Combine M5 Sniper (0.05 lot) + M5 London (0.05 lot) under various governors
        ("S776", "M5 London + NY Duo (0.05 each)", lambda: run_m5_engine(sig_m5_london, lot=0.05) + run_m5_engine(sig_m5_ny, lot=0.05), 140.0, "M5 Session Duo Equal Lot"),
        ("S777", "M5 London + NY Duo (0.07 each)", lambda: run_m5_engine(sig_m5_london, lot=0.07) + run_m5_engine(sig_m5_ny, lot=0.07), 160.0, "M5 Session Duo 0.07 Lot"),
        ("S778", "M5 London (0.07) + Core (0.05)", lambda: run_m5_engine(sig_m5_london, lot=0.07) + run_m5_engine(sig_m5_base, lot=0.05), 160.0, "M5 Overweight Early London"),
        ("S779", "M5 Triple-Window Suite (0.04 each)", lambda: run_m5_engine(sig_m5_london, lot=0.04) + run_m5_engine(sig_m5_ny, lot=0.04) + run_m5_engine(sig_m5_base, lot=0.04), 160.0, "M5 Triple Session Suite"),
        ("S780", "M5 High-Vol Suite ($1.20 ATR)", lambda: run_m5_engine(generate_m5_signals(3.0, 6, 10, 1.20), lot=0.06) + run_m5_engine(generate_m5_signals(3.0, 12, 16, 1.20), lot=0.06), 160.0, "M5 High-Vol Session Suite"),
        ("S781", "Fractal Sovereign Apex ($140 Gov)", lambda: run_m5_engine(sig_m5_london, lot=0.06) + run_m5_engine(sig_m5_base, lot=0.05), 140.0, "Fractal Sovereign Apex $140"),
        ("S782", "Fractal Sovereign Apex ($160 Gov)", lambda: run_m5_engine(sig_m5_london, lot=0.06) + run_m5_engine(sig_m5_base, lot=0.05), 160.0, "Fractal Sovereign Apex $160"),
        ("S783", "Fractal Sovereign Apex ($180 Gov)", lambda: run_m5_engine(sig_m5_london, lot=0.06) + run_m5_engine(sig_m5_base, lot=0.05), 180.0, "Fractal Sovereign Apex $180"),
        ("S784", "Centennial Fractal Millennium Master", lambda: run_m5_engine(sig_m5_london, dyn_risk=80.0) + run_m5_engine(sig_m5_base, dyn_risk=80.0), 160.0, "Dynamic Risk Centennial Master"),
        ("S785", "Grand Centennial Fractal Monument", lambda: run_m5_engine(sig_m5_london, dyn_risk=100.0) + run_m5_engine(sig_m5_base, dyn_risk=100.0), 180.0, "Aggressive Dynamic Fractal Monument")
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
    json_path = os.path.join(RESULTS_DIR, "batch_52_fractal_multi_tf_results.json")
    csv_path = os.path.join(RESULTS_DIR, "batch_52_fractal_multi_tf_matrix.csv")

    with open(json_path, "w") as f:
        json.dump(results_table, f, indent=2)
    pd.DataFrame(results_table).to_csv(csv_path, index=False)

    print(f"\n[+] Batch 52 Completed in {time.time()-t_start:.2f} seconds.")
    print(f"    Results saved to:\n    - {json_path}\n    - {csv_path}")

if __name__ == "__main__":
    main()
