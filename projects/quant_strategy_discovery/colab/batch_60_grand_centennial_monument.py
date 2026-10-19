"""
Batch 60: Strategy 1,000 Grand Centennial Monument (Strategies S996 - S1025)
=============================================================================
CFD Quantitative Strategy Discovery Campaign
Asset: XAUUSD (Gold CFD) + EURUSD Macro Anchor Gate
Regulatory Framework: Strict Constitution V5.1 Compliant (Rules D.1 - D.7)

Grand Milestone: Reaching and celebrating the 1,000th Quantitative Trading Strategy!
Synthesizes:
1. Multi-Frequency Confluence (M5 Micro-Structure EMA50 + M15 Supertrend + H1 Macro Trend + EURUSD Gate)
2. Asymmetric Liquidity Routing (Pristine Early London Overweight, London Midday, NY Open)
3. Staged Partial Take-Profit Scaling (2.0R ATR Tranche 1 Scale-Out + Trailing Ratchet Runner)
4. Institutional Risk Protection (Fixed-Fractional Micro-Compounding & Intraday Trailing Lock-In Governor)
5. 1,000-Run Monte Carlo Resampling for every strategy
"""

import os
import sys
import gc
import time
import json
import numpy as np
import pandas as pd

# -----------------------------------------------------------------------------
# Fast Technical Indicator Calculation Routines
# -----------------------------------------------------------------------------
def compute_atr(highs, lows, closes, period=14):
    n = len(closes)
    tr = np.zeros(n, dtype=np.float64)
    tr[0] = highs[0] - lows[0]
    for i in range(1, n):
        hl = highs[i] - lows[i]
        hc = abs(highs[i] - closes[i - 1])
        lc = abs(lows[i] - closes[i - 1])
        tr[i] = max(hl, hc, lc)
    atr = np.zeros(n, dtype=np.float64)
    if n < period:
        return atr
    atr[period - 1] = np.mean(tr[:period])
    alpha = 1.0 / period
    for i in range(period, n):
        atr[i] = (tr[i] * alpha) + (atr[i - 1] * (1.0 - alpha))
    return atr

def compute_ema(closes, period):
    n = len(closes)
    ema = np.zeros(n, dtype=np.float64)
    if n < period:
        return ema
    ema[period - 1] = np.mean(closes[:period])
    alpha = 2.0 / (period + 1.0)
    for i in range(period, n):
        ema[i] = (closes[i] * alpha) + (ema[i - 1] * (1.0 - alpha))
    return ema

def compute_supertrend(highs, lows, closes, atr, multiplier=3.0):
    n = len(closes)
    trend = np.ones(n, dtype=np.int32)
    band = np.zeros(n, dtype=np.float64)
    hl2 = (highs + lows) / 2.0
    upper_basic = hl2 + (multiplier * atr)
    lower_basic = hl2 - (multiplier * atr)

    upper_final = np.zeros(n, dtype=np.float64)
    lower_final = np.zeros(n, dtype=np.float64)
    upper_final[0] = upper_basic[0]
    lower_final[0] = lower_basic[0]
    band[0] = lower_final[0]

    for i in range(1, n):
        if lower_basic[i] > lower_final[i - 1] or closes[i - 1] < lower_final[i - 1]:
            lower_final[i] = lower_basic[i]
        else:
            lower_final[i] = lower_final[i - 1]

        if upper_basic[i] < upper_final[i - 1] or closes[i - 1] > upper_final[i - 1]:
            upper_final[i] = upper_basic[i]
        else:
            upper_final[i] = upper_final[i - 1]

        if trend[i - 1] == 1:
            if closes[i] < lower_final[i]:
                trend[i] = -1
                band[i] = upper_final[i]
            else:
                trend[i] = 1
                band[i] = lower_final[i]
        else:
            if closes[i] > upper_final[i]:
                trend[i] = 1
                band[i] = lower_final[i]
            else:
                trend[i] = -1
                band[i] = upper_final[i]

    return trend, band

# -----------------------------------------------------------------------------
# Discrete Engine Simulator under Strict Constitution V5.1 (Rules D.1 - D.7)
# -----------------------------------------------------------------------------
def simulate_discrete_centennial_engine(
    opens, highs, lows, closes, dates,
    entry_signals, atr_values, st_bands, engine_name,
    point_value=100.0, lot_size=0.10, spread=0.25, commission_per_lot=6.00,
    sl_slippage=0.10, swap_long_daily=-18.0,
    initial_sl_atr_mult=3.0, compounding_risk_pct=0.0,
    partial_tp_atr_mult=0.0, start_date=None, end_date=None
):
    n = len(closes)
    trades = []
    pos = 0
    entry_price = 0.0
    current_sl = 0.0
    tp_target = 0.0
    tranche_taken = False
    active_lot = lot_size
    curr_unit = active_lot * point_value
    entry_time = None
    deepest_dip = 0.0
    current_equity = 10000.0

    for i in range(1, n - 1):
        bar_open = opens[i]
        bar_high = highs[i]
        bar_low = lows[i]
        bar_close = closes[i]

        if pos == 1:
            intra_lowest_pnl = (bar_low - entry_price) * curr_unit - (spread * curr_unit) - (commission_per_lot * active_lot)
            if intra_lowest_pnl < deepest_dip:
                deepest_dip = intra_lowest_pnl

            # Tranche 1 Partial Take-Profit Scale-Out
            if partial_tp_atr_mult > 0.0 and not tranche_taken:
                if bar_high >= tp_target:
                    tranche_lot = round(active_lot * 0.5, 2)
                    remain_lot = round(active_lot - tranche_lot, 2)
                    tranche_unit = tranche_lot * point_value
                    p_pnl = (tp_target - entry_price) * tranche_unit - (spread * tranche_unit) - (commission_per_lot * tranche_lot)

                    trades.append({
                        "engine": f"{engine_name}_Tranche1",
                        "pos": 1,
                        "entry_time": entry_time,
                        "exit_time": dates[i],
                        "entry_price": entry_price,
                        "exit_price": tp_target,
                        "lot": tranche_lot,
                        "pnl": p_pnl,
                        "deepest_dip": deepest_dip,
                        "year": entry_time.year,
                        "month": f"{entry_time.year}-{entry_time.month:02d}",
                        "exit_reason": "PartialTP"
                    })
                    tranche_taken = True
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
                hold_days = max(1, (dates[i] - entry_time).days)
                swap_cost = hold_days * (swap_long_daily * active_lot)
                net_pnl = (exit_price - entry_price) * curr_unit - (spread * curr_unit) - (commission_per_lot * active_lot) + swap_cost

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

        elif pos == -1:
            intra_lowest_pnl = (entry_price - bar_high) * curr_unit - (spread * curr_unit) - (commission_per_lot * active_lot)
            if intra_lowest_pnl < deepest_dip:
                deepest_dip = intra_lowest_pnl

            # Tranche 1 Partial Take-Profit Scale-Out
            if partial_tp_atr_mult > 0.0 and not tranche_taken:
                if bar_low <= tp_target:
                    tranche_lot = round(active_lot * 0.5, 2)
                    remain_lot = round(active_lot - tranche_lot, 2)
                    tranche_unit = tranche_lot * point_value
                    p_pnl = (entry_price - tp_target) * tranche_unit - (spread * tranche_unit) - (commission_per_lot * tranche_lot)

                    trades.append({
                        "engine": f"{engine_name}_Tranche1",
                        "pos": -1,
                        "entry_time": entry_time,
                        "exit_time": dates[i],
                        "entry_price": entry_price,
                        "exit_price": tp_target,
                        "lot": tranche_lot,
                        "pnl": p_pnl,
                        "deepest_dip": deepest_dip,
                        "year": entry_time.year,
                        "month": f"{entry_time.year}-{entry_time.month:02d}",
                        "exit_reason": "PartialTP"
                    })
                    tranche_taken = True
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
                risk_cash = current_equity * (compounding_risk_pct / 100.0)
                sl_pts = (initial_sl_atr_mult * atr_values[i]) + spread + sl_slippage
                computed_lot = risk_cash / (sl_pts * point_value)
                active_lot = round(max(0.04, min(0.40, computed_lot)), 2)
            else:
                active_lot = lot_size

            curr_unit = active_lot * point_value

            if pos == 1:
                entry_price = opens[i + 1] + (spread * 0.5)
                current_sl = entry_price - (initial_sl_atr_mult * atr_values[i])
                tp_target = entry_price + (partial_tp_atr_mult * atr_values[i])
            else:
                entry_price = opens[i + 1] - (spread * 0.5)
                current_sl = entry_price + (initial_sl_atr_mult * atr_values[i])
                tp_target = entry_price - (partial_tp_atr_mult * atr_values[i])

    return trades

# -----------------------------------------------------------------------------
# Intraday Trailing Lock-In Governor Analytics
# -----------------------------------------------------------------------------
def analyze_trades_with_trailing_governor(trades, base_daily_limit=200.0, lock_in_ratio=0.50, years=6.0):
    if not trades:
        return {
            "net_profit": 0.0, "pf": 0.0, "total_trades": 0, "annual_trades": 0.0,
            "max_dd": 0.0, "romad": 0.0, "win_rate": 0.0, "mcr": 0.0,
            "avg_trade": 0.0, "filtered_trades": []
        }

    trades_sorted = sorted(trades, key=lambda t: t["exit_time"])
    daily_groups = {}
    for t in trades_sorted:
        d = t["exit_time"].strftime("%Y-%m-%d")
        daily_groups.setdefault(d, []).append(t)

    filtered_trades = []
    for d, day_trades in daily_groups.items():
        running_day_pnl = 0.0
        peak_day_pnl = 0.0
        effective_limit = base_daily_limit
        circuit_tripped = False

        for t in day_trades:
            if circuit_tripped:
                continue

            filtered_trades.append(t)
            running_day_pnl += t["pnl"]

            if running_day_pnl > peak_day_pnl:
                peak_day_pnl = running_day_pnl
                if lock_in_ratio > 0.0 and peak_day_pnl > 50.0:
                    lock_floor = peak_day_pnl * (1.0 - lock_in_ratio)
                    effective_limit = min(base_daily_limit, peak_day_pnl - lock_floor)

            if running_day_pnl <= -effective_limit:
                circuit_tripped = True

    cum_equity = 0.0
    peak_equity = 0.0
    max_intra_dd = 0.0
    pnls = []
    m_dict = {}

    for t in filtered_trades:
        pnl = t["pnl"]
        deepest = t.get("deepest_dip", 0.0)
        intra_low = cum_equity + deepest
        dd = peak_equity - intra_low
        if dd > max_intra_dd:
            max_intra_dd = dd

        cum_equity += pnl
        if cum_equity > peak_equity:
            peak_equity = cum_equity

        dd_after = peak_equity - cum_equity
        if dd_after > max_intra_dd:
            max_intra_dd = dd_after

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
        if np.min(equity_curve) <= (initial_capital * 0.70):
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
    t0 = time.time()
    print("=" * 100)
    print("BATCH 60: STRATEGY 1,000 GRAND CENTENNIAL MONUMENT (Strategies S996 - S1025)")
    print("=" * 100)

    REPO_ROOT = "/content/CFD-Trading-ML" if os.path.exists("/content/CFD-Trading-ML") else "/root/CFD-Trading-ML"
    DATA_DIR = os.path.join(REPO_ROOT, "projects/quant_strategy_discovery/data")
    RESULTS_DIR = os.path.join(REPO_ROOT, "projects/quant_strategy_discovery/results")
    os.makedirs(RESULTS_DIR, exist_ok=True)

    print(f"[+] Loading multi-frequency Gold and EURUSD datasets from {DATA_DIR}...")
    df_m5 = pd.read_parquet(os.path.join(DATA_DIR, "XAUUSD_M5.parquet"))
    df_m15 = pd.read_parquet(os.path.join(DATA_DIR, "XAUUSD_M15.parquet"))
    df_h1 = pd.read_parquet(os.path.join(DATA_DIR, "XAUUSD_H1.parquet"))
    df_eu = pd.read_parquet(os.path.join(DATA_DIR, "EURUSD_M15.parquet"))

    # Convert to NumPy
    m15_opens  = df_m15["open"].values.astype(np.float64)
    m15_highs  = df_m15["high"].values.astype(np.float64)
    m15_lows   = df_m15["low"].values.astype(np.float64)
    m15_closes = df_m15["close"].values.astype(np.float64)
    m15_dates  = pd.to_datetime(df_m15.index).to_pydatetime()
    n_m15      = len(m15_closes)

    m5_closes  = df_m5["close"].values.astype(np.float64)
    h1_highs   = df_h1["high"].values.astype(np.float64)
    h1_lows    = df_h1["low"].values.astype(np.float64)
    h1_closes  = df_h1["close"].values.astype(np.float64)
    eu_closes  = df_eu["close"].values.astype(np.float64)

    # 1. Indicator Calculations
    print("[+] Calculating multi-timeframe indicators...")
    m15_atr14 = compute_atr(m15_highs, m15_lows, m15_closes, 14)
    m15_atr100 = compute_atr(m15_highs, m15_lows, m15_closes, 100)
    m15_vol_ratio = np.divide(m15_atr14, m15_atr100, out=np.ones_like(m15_atr14), where=m15_atr100 > 0)
    st_t30, st_b30 = compute_supertrend(m15_highs, m15_lows, m15_closes, m15_atr14, 3.0)
    st_t25, st_b25 = compute_supertrend(m15_highs, m15_lows, m15_closes, m15_atr14, 2.5)
    st_t35, st_b35 = compute_supertrend(m15_highs, m15_lows, m15_closes, m15_atr14, 3.5)
    m15_ema200 = compute_ema(m15_closes, 200)

    # M5 Micro-Structure Alignment
    m5_ema50 = compute_ema(m5_closes, 50)
    m5_trend = np.where(m5_closes > m5_ema50, 1, -1)
    df_m5_state = pd.DataFrame({
        "time": pd.to_datetime(df_m5.index) + pd.Timedelta(minutes=5),
        "m5_tr": m5_trend
    }).sort_values("time")

    # H1 Macro Trend Alignment
    h1_atr14 = compute_atr(h1_highs, h1_lows, h1_closes, 14)
    h1_tr30, h1_st30 = compute_supertrend(h1_highs, h1_lows, h1_closes, h1_atr14, 3.0)
    df_h1_state = pd.DataFrame({
        "time": pd.to_datetime(df_h1.index) + pd.Timedelta(hours=1),
        "h1_tr": h1_tr30
    }).sort_values("time")

    # EURUSD Macro Alignment
    eu_ema50 = compute_ema(eu_closes, 50)
    eu_trend = np.where(eu_closes > eu_ema50, 1, -1)
    df_eu_state = pd.DataFrame({
        "time": pd.to_datetime(df_eu.index) + pd.Timedelta(minutes=15),
        "eu_trend": eu_trend
    }).sort_values("time")

    # Synchronize onto M15 Timeline
    df_m15_time = pd.DataFrame({"time": pd.to_datetime(df_m15.index)})
    m15_merged_h1 = pd.merge_asof(df_m15_time, df_h1_state, on="time", direction="backward")
    m15_h1_trend = m15_merged_h1["h1_tr"].fillna(1).values.astype(np.int32)

    m15_merged_eu = pd.merge_asof(df_m15_time, df_eu_state, on="time", direction="backward")
    m15_eu_trend = m15_merged_eu["eu_trend"].fillna(1).values.astype(np.int32)

    m15_merged_m5 = pd.merge_asof(df_m15_time, df_m5_state, on="time", direction="backward")
    m15_m5_trend = m15_merged_m5["m5_tr"].fillna(1).values.astype(np.int32)

    del df_m5, df_m5_state, df_h1, df_h1_state, df_eu, df_eu_state, m15_merged_h1, m15_merged_eu, m15_merged_m5, df_m15_time
    gc.collect()

    print(f"[+] Synchronized {n_m15:,} Gold M15 bars under multi-frequency causal alignment.")

    # 2. Confluence Signal Generators
    def generate_gold_signals(start_h, end_h, min_atr=1.50, min_vr=0.0, custom_st_t=st_t30):
        sig = np.zeros(n_m15, dtype=np.int32)
        for i in range(200, n_m15 - 1):
            h = m15_dates[i].hour
            if start_h <= h <= end_h:
                if min_atr <= 0.0 or m15_atr14[i] >= min_atr:
                    if min_vr > 0.0 and m15_vol_ratio[i] < min_vr:
                        continue
                    if custom_st_t[i] == 1 and custom_st_t[i - 1] == -1 and m15_closes[i] > m15_ema200[i]:
                        if m15_h1_trend[i] == 1 and m15_eu_trend[i] == 1 and m15_m5_trend[i] == 1:
                            sig[i] = 1
                    elif custom_st_t[i] == -1 and custom_st_t[i - 1] == 1 and m15_closes[i] < m15_ema200[i]:
                        if m15_h1_trend[i] == -1 and m15_eu_trend[i] == -1 and m15_m5_trend[i] == -1:
                            sig[i] = -1
        return sig

    sig_early_lon = generate_gold_signals(6, 9, 1.50, min_vr=1.10)
    sig_mid_lon   = generate_gold_signals(9, 12, 1.50, min_vr=1.05)
    sig_ny_open   = generate_gold_signals(12, 16, 1.80, min_vr=1.15)

    sig_early_lon_25 = generate_gold_signals(6, 9, 1.50, min_vr=1.10, custom_st_t=st_t25)
    sig_mid_lon_25   = generate_gold_signals(9, 12, 1.50, min_vr=1.05, custom_st_t=st_t25)
    sig_ny_open_25   = generate_gold_signals(12, 16, 1.80, min_vr=1.15, custom_st_t=st_t25)

    sig_early_lon_35 = generate_gold_signals(6, 9, 1.50, min_vr=1.10, custom_st_t=st_t35)
    sig_mid_lon_35   = generate_gold_signals(9, 12, 1.50, min_vr=1.05, custom_st_t=st_t35)
    sig_ny_open_35   = generate_gold_signals(12, 16, 1.80, min_vr=1.15, custom_st_t=st_t35)

    def run_centennial_router(w_early=0.12, w_mid=0.06, w_ny=0.06, comp_pct=0.0, part_tp=2.0, st_band_custom=st_b30, sig_tuple=None):
        if sig_tuple is None:
            s1, s2, s3 = sig_early_lon, sig_mid_lon, sig_ny_open
        else:
            s1, s2, s3 = sig_tuple

        t1 = simulate_discrete_centennial_engine(m15_opens, m15_highs, m15_lows, m15_closes, m15_dates, s1, m15_atr14, st_band_custom, "Early_London", point_value=100.0, lot_size=w_early, compounding_risk_pct=comp_pct*0.5 if comp_pct>0 else 0.0, partial_tp_atr_mult=part_tp)
        t2 = simulate_discrete_centennial_engine(m15_opens, m15_highs, m15_lows, m15_closes, m15_dates, s2, m15_atr14, st_band_custom, "London_Mid", point_value=100.0, lot_size=w_mid, compounding_risk_pct=comp_pct*0.25 if comp_pct>0 else 0.0, partial_tp_atr_mult=part_tp)
        t3 = simulate_discrete_centennial_engine(m15_opens, m15_highs, m15_lows, m15_closes, m15_dates, s3, m15_atr14, st_band_custom, "NY_Open", point_value=100.0, lot_size=w_ny, compounding_risk_pct=comp_pct*0.35 if comp_pct>0 else 0.0, partial_tp_atr_mult=part_tp)
        return t1 + t2 + t3

    # 3. Strategy Definitions (S996 - S1025)
    print("\n[+] Assembling Grand Centennial Strategy Suite (S996 - S1025)...")
    strategy_definitions = [
        # Group 1: The Centennial Threshold (S996 - S1000)
        ("S996", "Grand Centennial Benchmark", lambda: run_centennial_router(0.12, 0.06, 0.06, part_tp=2.0), 180.0, 0.0, "Centennial Benchmark"),
        ("S997", "Grand Centennial Extreme Benchmark", lambda: run_centennial_router(0.15, 0.08, 0.04, part_tp=2.0), 200.0, 0.0, "Centennial Extreme Benchmark"),
        ("S998", "Grand Centennial Sub-Risk", lambda: run_centennial_router(0.10, 0.05, 0.05, part_tp=2.0), 150.0, 0.0, "Centennial Sub-Risk"),
        ("S999", "Grand Centennial Prop-Firm Shield", lambda: run_centennial_router(0.06, 0.04, 0.04, part_tp=2.0), 120.0, 0.0, "Centennial Prop-Firm Shield"),
        ("S1000", "GRAND CENTENNIAL MONUMENT FLAGSHIP", lambda: run_centennial_router(0.12, 0.06, 0.06, part_tp=2.0), 180.0, 0.50, "👑 CENTENNIAL MONUMENT FLAGSHIP (THE 1,000TH STRATEGY)"),

        # Group 2: Fixed-Fractional Centennial Compounding (S1001 - S1010)
        ("S1001", "Centennial 0.5% Compounding Shield", lambda: run_centennial_router(0.10, 0.05, 0.05, comp_pct=0.5, part_tp=2.0), 140.0, 0.0, "Centennial 0.5% Compounding"),
        ("S1002", "Centennial 0.75% Compounding Apex", lambda: run_centennial_router(0.10, 0.05, 0.05, comp_pct=0.75, part_tp=2.0), 150.0, 0.0, "Centennial 0.75% Compounding"),
        ("S1003", "Centennial 1.0% Compounding Engine", lambda: run_centennial_router(0.10, 0.05, 0.05, comp_pct=1.0, part_tp=2.0), 180.0, 0.0, "Centennial 1.0% Compounding"),
        ("S1004", "Centennial 1.25% Compounding Growth", lambda: run_centennial_router(0.10, 0.05, 0.05, comp_pct=1.25, part_tp=2.0), 200.0, 0.0, "Centennial 1.25% Compounding"),
        ("S1005", "Centennial 1.5% Compounding Titan", lambda: run_centennial_router(0.10, 0.05, 0.05, comp_pct=1.5, part_tp=2.0), 200.0, 0.0, "Centennial 1.5% Compounding"),
        ("S1006", "Centennial 2.0% Compounding Apex", lambda: run_centennial_router(0.10, 0.05, 0.05, comp_pct=2.0, part_tp=2.0), 220.0, 0.0, "Centennial 2.0% Compounding"),
        ("S1007", "Centennial 2.5% Compounding Maximum", lambda: run_centennial_router(0.10, 0.05, 0.05, comp_pct=2.5, part_tp=2.0), 250.0, 0.0, "Centennial 2.5% Compounding"),
        ("S1008", "Centennial 1.0% Comp + 50% Lock-In", lambda: run_centennial_router(0.10, 0.05, 0.05, comp_pct=1.0, part_tp=2.0), 180.0, 0.50, "Centennial 1.0% Comp + Lock"),
        ("S1009", "Centennial 1.5% Comp + 50% Lock-In", lambda: run_centennial_router(0.10, 0.05, 0.05, comp_pct=1.5, part_tp=2.0), 200.0, 0.50, "Centennial 1.5% Comp + Lock"),
        ("S1010", "Centennial 2.0% Comp + 50% Lock-In", lambda: run_centennial_router(0.10, 0.05, 0.05, comp_pct=2.0, part_tp=2.0), 220.0, 0.50, "Centennial 2.0% Comp + Lock"),

        # Group 3: Extreme Asymmetric Centennial Suites (S1011 - S1018)
        ("S1011", "Centennial Extreme + 1.0% Comp", lambda: run_centennial_router(0.15, 0.08, 0.04, comp_pct=1.0, part_tp=2.0), 200.0, 0.0, "Centennial Extreme 1.0% Comp"),
        ("S1012", "Centennial Extreme + 1.5% Comp", lambda: run_centennial_router(0.15, 0.08, 0.04, comp_pct=1.5, part_tp=2.0), 220.0, 0.0, "Centennial Extreme 1.5% Comp"),
        ("S1013", "Centennial Extreme + 2.0% Comp", lambda: run_centennial_router(0.15, 0.08, 0.04, comp_pct=2.0, part_tp=2.0), 250.0, 0.0, "Centennial Extreme 2.0% Comp"),
        ("S1014", "Centennial Extreme + 50% Lock", lambda: run_centennial_router(0.15, 0.08, 0.04, part_tp=2.0), 200.0, 0.50, "Centennial Extreme 50% Lock"),
        ("S1015", "Centennial Fortress + 0.4% Comp", lambda: run_centennial_router(0.05, 0.03, 0.03, comp_pct=0.4, part_tp=2.0), 100.0, 0.0, "Centennial Fortress 0.4% Comp"),
        ("S1016", "Centennial Fortress + 0.5% Comp", lambda: run_centennial_router(0.05, 0.03, 0.03, comp_pct=0.5, part_tp=2.0), 110.0, 0.0, "Centennial Fortress 0.5% Comp"),
        ("S1017", "Centennial Fortress + 0.75% Comp", lambda: run_centennial_router(0.05, 0.03, 0.03, comp_pct=0.75, part_tp=2.0), 120.0, 0.0, "Centennial Fortress 0.75% Comp"),
        ("S1018", "Centennial Fortress + 50% Lock", lambda: run_centennial_router(0.05, 0.03, 0.03, part_tp=2.0), 100.0, 0.50, "Centennial Fortress 50% Lock"),

        # Group 4: Dynamic Ratchet & Frontier Architectures (S1019 - S1025)
        ("S1019", "Centennial Staged 1.5R Tranche", lambda: run_centennial_router(0.12, 0.06, 0.06, part_tp=1.5), 180.0, 0.0, "Centennial Staged 1.5R"),
        ("S1020", "Centennial Staged 2.5R Tranche", lambda: run_centennial_router(0.12, 0.06, 0.06, part_tp=2.5), 180.0, 0.0, "Centennial Staged 2.5R"),
        ("S1021", "Centennial Tight Ratchet (2.5x ST)", lambda: run_centennial_router(0.12, 0.06, 0.06, part_tp=2.0, st_band_custom=st_b25, sig_tuple=(sig_early_lon_25, sig_mid_lon_25, sig_ny_open_25)), 180.0, 0.0, "Centennial Tight Ratchet 2.5x"),
        ("S1022", "Centennial Wide Ratchet (3.5x ST)", lambda: run_centennial_router(0.12, 0.06, 0.06, part_tp=2.0, st_band_custom=st_b35, sig_tuple=(sig_early_lon_35, sig_mid_lon_35, sig_ny_open_35)), 180.0, 0.0, "Centennial Wide Ratchet 3.5x"),
        ("S1023", "Centennial Asymmetry Plus (0.16 Lon)", lambda: run_centennial_router(0.16, 0.08, 0.03, part_tp=2.0), 200.0, 0.0, "Centennial Asymmetry Plus"),
        ("S1024", "Centennial Millennial Vault (60% Lock)", lambda: run_centennial_router(0.10, 0.05, 0.05, part_tp=2.0), 150.0, 0.60, "Centennial Millennial Vault"),
        ("S1025", "Centennial Millennium Sovereign Titan", lambda: run_centennial_router(0.15, 0.08, 0.04, comp_pct=1.0, part_tp=2.0), 200.0, 0.50, "👑 Centennial Millennium Sovereign Titan")
    ]

    # 4. Evaluation Loop
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
            "Ruin_Probability_Pct": round(mc["ruin_prob"], 1)
        }
        results_table.append(row)

        print(f"{sid:<6} {name:<42} {row['Annual_Trades']:<8} {row['Total_Trades']:<8} {row['Net_Profit']:<14.2f} {row['Profit_Factor']:<8.3f} {row['Win_Rate_Pct']:<8.1f} {row['True_Intra_Max_DD']:<14.2f} {row['MC_P95_DD']:<12.2f} {row['Ruin_Probability_Pct']:<8.1f} {row['RoMaD']:<8.2f}")

    print("=" * 145)

    # 5. Export Results
    out_csv = os.path.join(RESULTS_DIR, "batch_60_centennial_monument_matrix.csv")
    out_json = os.path.join(RESULTS_DIR, "batch_60_centennial_monument_results.json")
    df_res = pd.DataFrame(results_table)
    df_res.to_csv(out_csv, index=False)
    with open(out_json, "w") as f:
        json.dump(results_table, f, indent=2)

    elapsed = time.time() - t0
    print(f"\n[+] Batch 60 Centennial Monument Execution Complete in {elapsed:.2f}s!")
    print(f"[+] Saved results matrix to {out_csv}")
    print(f"[+] Saved results JSON to {out_json}")

if __name__ == "__main__":
    main()
