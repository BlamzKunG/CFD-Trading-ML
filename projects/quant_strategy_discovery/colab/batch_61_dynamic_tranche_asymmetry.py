"""
Batch 61: Dynamic Tranche Asymmetry & Multi-Session Payoff Engineering (S1026 - S1055)
=====================================================================================
CFD Quantitative Strategy Discovery Campaign
Asset: XAUUSD (Gold CFD) + EURUSD Macro Anchor Gate
Regulatory Framework: Strict Constitution V5.1 Compliant (Rules D.1 - D.7)

Research Objectives:
1. Multi-Tranche Scale-Out (Rule D.6 Compliant: 2 to 3 Tranches Max):
   - Fast de-leveraging (Tranche 1 @ 1.2R - 1.5R ATR)
   - Secondary expansion (Tranche 2 @ 2.5R - 3.0R ATR)
   - Trailing Supertrend ratchet runner (3.0x ST)
2. Dynamic Volatility Regime Targeting:
   - High Expansion ($VR \ge 1.20$): Extended runner targets
   - Normal Expansion ($1.05 \le VR < 1.20$): Rapid 1.5R scale-out
3. Session-Specific Staged Calibration:
   - Early London (06-09 UTC): 0.14 lot + 2-tranche runner
   - London Midday (09-12 UTC): 0.07 lot + 1.5R scale-out
   - NY Open (12-16 UTC): 0.05 lot + Rapid 1.2R scale-out to mitigate late-day reversals
4. 1,000-Run Monte Carlo resampling for all 30 configurations
"""

import os
import sys
import gc
import time
import json
import numpy as np
import pandas as pd

# -----------------------------------------------------------------------------
# Fast Pure-NumPy Indicators
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
# Discrete 3-Tranche Engine Simulator (Constitution V5.1 & Rule D.6 Compliant)
# -----------------------------------------------------------------------------
def simulate_discrete_tranche_engine(
    opens, highs, lows, closes, dates,
    entry_signals, atr_values, st_bands, engine_name,
    point_value=100.0, lot_size=0.12, spread=0.25, commission_per_lot=6.00,
    sl_slippage=0.10, swap_long_daily=-18.0,
    initial_sl_atr_mult=3.0, compounding_risk_pct=0.0,
    tranche1_mult=1.5, tranche1_ratio=0.50,
    tranche2_mult=0.0, tranche2_ratio=0.0,
    start_date=None, end_date=None
):
    n = len(closes)
    trades = []
    pos = 0
    entry_price = 0.0
    current_sl = 0.0
    tp1_target = 0.0
    tp2_target = 0.0
    tranche1_taken = False
    tranche2_taken = False
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

            # Tranche 1 Scale-Out
            if tranche1_mult > 0.0 and not tranche1_taken and active_lot >= 0.02:
                if bar_high >= tp1_target:
                    t1_lot = round(active_lot * tranche1_ratio, 2)
                    t1_lot = max(0.01, min(t1_lot, round(active_lot - 0.01, 2)))
                    remain_lot = round(active_lot - t1_lot, 2)
                    t1_unit = t1_lot * point_value
                    p_pnl = (tp1_target - entry_price) * t1_unit - (spread * t1_unit) - (commission_per_lot * t1_lot)

                    trades.append({
                        "engine": f"{engine_name}_T1",
                        "pos": 1,
                        "entry_time": entry_time,
                        "exit_time": dates[i],
                        "entry_price": entry_price,
                        "exit_price": tp1_target,
                        "lot": t1_lot,
                        "pnl": p_pnl,
                        "deepest_dip": deepest_dip,
                        "year": entry_time.year,
                        "month": f"{entry_time.year}-{entry_time.month:02d}",
                        "exit_reason": "Tranche1"
                    })
                    tranche1_taken = True
                    current_equity += p_pnl
                    active_lot = remain_lot
                    curr_unit = active_lot * point_value

            # Tranche 2 Scale-Out
            if tranche2_mult > 0.0 and tranche1_taken and not tranche2_taken and active_lot >= 0.02:
                if bar_high >= tp2_target:
                    t2_lot = round(active_lot * tranche2_ratio, 2)
                    t2_lot = max(0.01, min(t2_lot, round(active_lot - 0.01, 2)))
                    remain_lot = round(active_lot - t2_lot, 2)
                    t2_unit = t2_lot * point_value
                    p_pnl = (tp2_target - entry_price) * t2_unit - (spread * t2_unit) - (commission_per_lot * t2_lot)

                    trades.append({
                        "engine": f"{engine_name}_T2",
                        "pos": 1,
                        "entry_time": entry_time,
                        "exit_time": dates[i],
                        "entry_price": entry_price,
                        "exit_price": tp2_target,
                        "lot": t2_lot,
                        "pnl": p_pnl,
                        "deepest_dip": deepest_dip,
                        "year": entry_time.year,
                        "month": f"{entry_time.year}-{entry_time.month:02d}",
                        "exit_reason": "Tranche2"
                    })
                    tranche2_taken = True
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
                        "engine": f"{engine_name}_Runner" if (tranche1_taken or tranche2_taken) else engine_name,
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

            # Tranche 1 Scale-Out
            if tranche1_mult > 0.0 and not tranche1_taken and active_lot >= 0.02:
                if bar_low <= tp1_target:
                    t1_lot = round(active_lot * tranche1_ratio, 2)
                    t1_lot = max(0.01, min(t1_lot, round(active_lot - 0.01, 2)))
                    remain_lot = round(active_lot - t1_lot, 2)
                    t1_unit = t1_lot * point_value
                    p_pnl = (entry_price - tp1_target) * t1_unit - (spread * t1_unit) - (commission_per_lot * t1_lot)

                    trades.append({
                        "engine": f"{engine_name}_T1",
                        "pos": -1,
                        "entry_time": entry_time,
                        "exit_time": dates[i],
                        "entry_price": entry_price,
                        "exit_price": tp1_target,
                        "lot": t1_lot,
                        "pnl": p_pnl,
                        "deepest_dip": deepest_dip,
                        "year": entry_time.year,
                        "month": f"{entry_time.year}-{entry_time.month:02d}",
                        "exit_reason": "Tranche1"
                    })
                    tranche1_taken = True
                    current_equity += p_pnl
                    active_lot = remain_lot
                    curr_unit = active_lot * point_value

            # Tranche 2 Scale-Out
            if tranche2_mult > 0.0 and tranche1_taken and not tranche2_taken and active_lot >= 0.02:
                if bar_low <= tp2_target:
                    t2_lot = round(active_lot * tranche2_ratio, 2)
                    t2_lot = max(0.01, min(t2_lot, round(active_lot - 0.01, 2)))
                    remain_lot = round(active_lot - t2_lot, 2)
                    t2_unit = t2_lot * point_value
                    p_pnl = (entry_price - tp2_target) * t2_unit - (spread * t2_unit) - (commission_per_lot * t2_lot)

                    trades.append({
                        "engine": f"{engine_name}_T2",
                        "pos": -1,
                        "entry_time": entry_time,
                        "exit_time": dates[i],
                        "entry_price": entry_price,
                        "exit_price": tp2_target,
                        "lot": t2_lot,
                        "pnl": p_pnl,
                        "deepest_dip": deepest_dip,
                        "year": entry_time.year,
                        "month": f"{entry_time.year}-{entry_time.month:02d}",
                        "exit_reason": "Tranche2"
                    })
                    tranche2_taken = True
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
                        "engine": f"{engine_name}_Runner" if (tranche1_taken or tranche2_taken) else engine_name,
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
            tranche1_taken = False
            tranche2_taken = False

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
                tp1_target = entry_price + (tranche1_mult * atr_values[i])
                tp2_target = entry_price + (tranche2_mult * atr_values[i]) if tranche2_mult > 0 else 0.0
            else:
                entry_price = opens[i + 1] - (spread * 0.5)
                current_sl = entry_price + (initial_sl_atr_mult * atr_values[i])
                tp1_target = entry_price - (tranche1_mult * atr_values[i])
                tp2_target = entry_price - (tranche2_mult * atr_values[i]) if tranche2_mult > 0 else 0.0

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
    print("BATCH 61: DYNAMIC TRANCHE ASYMMETRY & MULTI-SESSION PAYOFF ENGINEERING (S1026 - S1055)")
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

    # Indicator Calculations
    print("[+] Calculating multi-timeframe indicators...")
    m15_atr14 = compute_atr(m15_highs, m15_lows, m15_closes, 14)
    m15_atr100 = compute_atr(m15_highs, m15_lows, m15_closes, 100)
    m15_vol_ratio = np.divide(m15_atr14, m15_atr100, out=np.ones_like(m15_atr14), where=m15_atr100 > 0)
    st_t30, st_b30 = compute_supertrend(m15_highs, m15_lows, m15_closes, m15_atr14, 3.0)
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

    # Signal Generator
    def generate_gold_signals(start_h, end_h, min_atr=1.50, min_vr=0.0):
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

    sig_early_lon = generate_gold_signals(6, 9, 1.50, min_vr=1.10)
    sig_mid_lon   = generate_gold_signals(9, 12, 1.50, min_vr=1.05)
    sig_ny_open   = generate_gold_signals(12, 16, 1.80, min_vr=1.15)

    def run_tranche_router(
        w_early=0.12, w_mid=0.06, w_ny=0.06,
        comp_pct=0.0,
        t1_mult=1.5, t1_ratio=0.50,
        t2_mult=0.0, t2_ratio=0.0,
        ny_rapid=False
    ):
        t1 = simulate_discrete_tranche_engine(
            m15_opens, m15_highs, m15_lows, m15_closes, m15_dates, sig_early_lon, m15_atr14, st_b30,
            "Early_London", point_value=100.0, lot_size=w_early, compounding_risk_pct=comp_pct*0.5 if comp_pct>0 else 0.0,
            tranche1_mult=t1_mult, tranche1_ratio=t1_ratio, tranche2_mult=t2_mult, tranche2_ratio=t2_ratio
        )
        t2 = simulate_discrete_tranche_engine(
            m15_opens, m15_highs, m15_lows, m15_closes, m15_dates, sig_mid_lon, m15_atr14, st_b30,
            "London_Mid", point_value=100.0, lot_size=w_mid, compounding_risk_pct=comp_pct*0.25 if comp_pct>0 else 0.0,
            tranche1_mult=t1_mult, tranche1_ratio=t1_ratio, tranche2_mult=t2_mult, tranche2_ratio=t2_ratio
        )
        # NY Open: optional rapid scale-out to mitigate late reversals
        ny_t1_mult = 1.2 if ny_rapid else t1_mult
        ny_t1_ratio = 0.60 if ny_rapid else t1_ratio
        t3 = simulate_discrete_tranche_engine(
            m15_opens, m15_highs, m15_lows, m15_closes, m15_dates, sig_ny_open, m15_atr14, st_b30,
            "NY_Open", point_value=100.0, lot_size=w_ny, compounding_risk_pct=comp_pct*0.35 if comp_pct>0 else 0.0,
            tranche1_mult=ny_t1_mult, tranche1_ratio=ny_t1_ratio, tranche2_mult=t2_mult, tranche2_ratio=t2_ratio
        )
        return t1 + t2 + t3

    # Strategy Definitions (S1026 - S1055)
    print("\n[+] Assembling Batch 61 Dynamic Tranche Suite (S1026 - S1055)...")
    strategy_definitions = [
        # Group 1: Dual-Tranche Payoff Calibration (S1026 - S1035)
        ("S1026", "Dual-Tranche (T1: 1.2R, T2: 2.5R)", lambda: run_tranche_router(0.12, 0.06, 0.06, t1_mult=1.2, t1_ratio=0.40, t2_mult=2.5, t2_ratio=0.30), 180.0, 0.0, "Dual-Tranche 1.2R/2.5R"),
        ("S1027", "Dual-Tranche (T1: 1.5R, T2: 3.0R)", lambda: run_tranche_router(0.12, 0.06, 0.06, t1_mult=1.5, t1_ratio=0.40, t2_mult=3.0, t2_ratio=0.30), 180.0, 0.0, "Dual-Tranche 1.5R/3.0R"),
        ("S1028", "Dual-Tranche (T1: 1.5R, T2: 2.5R)", lambda: run_tranche_router(0.12, 0.06, 0.06, t1_mult=1.5, t1_ratio=0.40, t2_mult=2.5, t2_ratio=0.30), 180.0, 0.0, "Dual-Tranche 1.5R/2.5R"),
        ("S1029", "Dual-Tranche (T1: 1.8R, T2: 3.5R)", lambda: run_tranche_router(0.12, 0.06, 0.06, t1_mult=1.8, t1_ratio=0.40, t2_mult=3.5, t2_ratio=0.30), 180.0, 0.0, "Dual-Tranche 1.8R/3.5R"),
        ("S1030", "Dual-Tranche (T1: 1.5R, T2: 2.5R) + 50% Lock", lambda: run_tranche_router(0.12, 0.06, 0.06, t1_mult=1.5, t1_ratio=0.40, t2_mult=2.5, t2_ratio=0.30), 180.0, 0.50, "Dual-Tranche 1.5R/2.5R + Lock"),
        ("S1031", "Dual-Tranche (T1: 1.5R, T2: 3.0R) + 50% Lock", lambda: run_tranche_router(0.12, 0.06, 0.06, t1_mult=1.5, t1_ratio=0.40, t2_mult=3.0, t2_ratio=0.30), 180.0, 0.50, "Dual-Tranche 1.5R/3.0R + Lock"),
        ("S1032", "Rapid Single-Tranche 1.2R Scale-Out", lambda: run_tranche_router(0.12, 0.06, 0.06, t1_mult=1.2, t1_ratio=0.50), 180.0, 0.0, "Rapid Tranche 1.2R Scale"),
        ("S1033", "Rapid Single-Tranche 1.4R Scale-Out", lambda: run_tranche_router(0.12, 0.06, 0.06, t1_mult=1.4, t1_ratio=0.50), 180.0, 0.0, "Rapid Tranche 1.4R Scale"),
        ("S1034", "Rapid Single-Tranche 1.6R Scale-Out", lambda: run_tranche_router(0.12, 0.06, 0.06, t1_mult=1.6, t1_ratio=0.50), 180.0, 0.0, "Rapid Tranche 1.6R Scale"),
        ("S1035", "Rapid Single-Tranche 1.8R Scale-Out", lambda: run_tranche_router(0.12, 0.06, 0.06, t1_mult=1.8, t1_ratio=0.50), 180.0, 0.0, "Rapid Tranche 1.8R Scale"),

        # Group 2: Session-Asymmetric De-Leveraging (NY Rapid Exit) (S1036 - S1045)
        ("S1036", "Session Asymmetric (NY Rapid 1.2R Exit)", lambda: run_tranche_router(0.14, 0.07, 0.05, t1_mult=1.5, t1_ratio=0.50, ny_rapid=True), 180.0, 0.0, "NY Rapid De-Leveraging"),
        ("S1037", "Session Asymmetric (NY Rapid) + 50% Lock", lambda: run_tranche_router(0.14, 0.07, 0.05, t1_mult=1.5, t1_ratio=0.50, ny_rapid=True), 180.0, 0.50, "NY Rapid + 50% Lock"),
        ("S1038", "Session Asymmetric Extreme (0.16 Lon / 0.04 NY)", lambda: run_tranche_router(0.16, 0.08, 0.04, t1_mult=1.5, t1_ratio=0.50, ny_rapid=True), 200.0, 0.0, "Session Asymmetric Extreme"),
        ("S1039", "Session Asymmetric Extreme + 50% Lock", lambda: run_tranche_router(0.16, 0.08, 0.04, t1_mult=1.5, t1_ratio=0.50, ny_rapid=True), 200.0, 0.50, "Session Extreme + Lock"),
        ("S1040", "Sub-Risk Tranche Apex (0.10 Lon / 0.05 NY)", lambda: run_tranche_router(0.10, 0.05, 0.05, t1_mult=1.5, t1_ratio=0.50, ny_rapid=True), 150.0, 0.0, "Sub-Risk Tranche Apex"),
        ("S1041", "Sub-Risk Tranche Apex + 50% Lock", lambda: run_tranche_router(0.10, 0.05, 0.05, t1_mult=1.5, t1_ratio=0.50, ny_rapid=True), 150.0, 0.50, "Sub-Risk Apex + Lock"),
        ("S1042", "Dual-Tranche Extreme (0.15 Lon / 0.04 NY)", lambda: run_tranche_router(0.15, 0.08, 0.04, t1_mult=1.5, t1_ratio=0.40, t2_mult=2.5, t2_ratio=0.30, ny_rapid=True), 200.0, 0.0, "Dual-Tranche Extreme"),
        ("S1043", "Dual-Tranche Extreme + 50% Lock", lambda: run_tranche_router(0.15, 0.08, 0.04, t1_mult=1.5, t1_ratio=0.40, t2_mult=2.5, t2_ratio=0.30, ny_rapid=True), 200.0, 0.50, "Dual-Tranche Extreme + Lock"),
        ("S1044", "Prop-Firm Tranche Shield (0.05 Lon / 0.03 NY)", lambda: run_tranche_router(0.05, 0.03, 0.03, t1_mult=1.5, t1_ratio=0.50, ny_rapid=True), 100.0, 0.0, "Prop-Firm Tranche Shield"),
        ("S1045", "Prop-Firm Tranche Shield + 50% Lock", lambda: run_tranche_router(0.05, 0.03, 0.03, t1_mult=1.5, t1_ratio=0.50, ny_rapid=True), 100.0, 0.50, "Prop-Firm Shield + Lock"),

        # Group 3: Compounding Tranche Fusion (S1046 - S1055)
        ("S1046", "Tranche Compounding 0.5% (1.5R Scale)", lambda: run_tranche_router(0.10, 0.05, 0.05, comp_pct=0.5, t1_mult=1.5, t1_ratio=0.50), 140.0, 0.0, "Tranche Comp 0.5% (1.5R)"),
        ("S1047", "Tranche Compounding 0.75% (1.5R Scale)", lambda: run_tranche_router(0.10, 0.05, 0.05, comp_pct=0.75, t1_mult=1.5, t1_ratio=0.50), 150.0, 0.0, "Tranche Comp 0.75% (1.5R)"),
        ("S1048", "Tranche Compounding 1.0% (1.5R Scale)", lambda: run_tranche_router(0.10, 0.05, 0.05, comp_pct=1.0, t1_mult=1.5, t1_ratio=0.50), 180.0, 0.0, "Tranche Comp 1.0% (1.5R)"),
        ("S1049", "Tranche Compounding 1.5% (1.5R Scale)", lambda: run_tranche_router(0.10, 0.05, 0.05, comp_pct=1.5, t1_mult=1.5, t1_ratio=0.50), 200.0, 0.0, "Tranche Comp 1.5% (1.5R)"),
        ("S1050", "Tranche Compounding 2.0% (1.5R Scale)", lambda: run_tranche_router(0.10, 0.05, 0.05, comp_pct=2.0, t1_mult=1.5, t1_ratio=0.50), 220.0, 0.0, "Tranche Comp 2.0% (1.5R)"),
        ("S1051", "Dual-Tranche Compounding 1.0% + 50% Lock", lambda: run_tranche_router(0.10, 0.05, 0.05, comp_pct=1.0, t1_mult=1.5, t1_ratio=0.40, t2_mult=2.5, t2_ratio=0.30), 180.0, 0.50, "Dual-Tranche Comp 1.0% Lock"),
        ("S1052", "Dual-Tranche Compounding 1.5% + 50% Lock", lambda: run_tranche_router(0.10, 0.05, 0.05, comp_pct=1.5, t1_mult=1.5, t1_ratio=0.40, t2_mult=2.5, t2_ratio=0.30), 200.0, 0.50, "Dual-Tranche Comp 1.5% Lock"),
        ("S1053", "Dual-Tranche Compounding 2.0% + 50% Lock", lambda: run_tranche_router(0.10, 0.05, 0.05, comp_pct=2.0, t1_mult=1.5, t1_ratio=0.40, t2_mult=2.5, t2_ratio=0.30), 220.0, 0.50, "Dual-Tranche Comp 2.0% Lock"),
        ("S1054", "Grand Asymmetric Millennium Vault 2026", lambda: run_tranche_router(0.14, 0.07, 0.05, comp_pct=1.0, t1_mult=1.5, t1_ratio=0.40, t2_mult=2.5, t2_ratio=0.30, ny_rapid=True), 180.0, 0.50, "Millennium Vault 2026"),
        ("S1055", "Apex Sovereign Millennium Titan 2026", lambda: run_tranche_router(0.16, 0.08, 0.04, comp_pct=1.5, t1_mult=1.5, t1_ratio=0.40, t2_mult=2.5, t2_ratio=0.30, ny_rapid=True), 220.0, 0.50, "👑 Apex Sovereign Titan 2026")
    ]

    # Evaluation Loop
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

    # Export Results
    out_csv = os.path.join(RESULTS_DIR, "batch_61_dynamic_tranche_matrix.csv")
    out_json = os.path.join(RESULTS_DIR, "batch_61_dynamic_tranche_results.json")
    df_res = pd.DataFrame(results_table)
    df_res.to_csv(out_csv, index=False)
    with open(out_json, "w") as f:
        json.dump(results_table, f, indent=2)

    elapsed = time.time() - t0
    print(f"\n[+] Batch 61 Dynamic Tranche Execution Complete in {elapsed:.2f}s!")
    print(f"[+] Saved results matrix to {out_csv}")
    print(f"[+] Saved results JSON to {out_json}")

if __name__ == "__main__":
    main()
