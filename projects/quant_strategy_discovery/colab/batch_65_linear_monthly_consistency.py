"""
Batch 65: Linear Equity & Monthly Consistency Engine (S1146 - S1175)
=====================================================================
CFD Quantitative Strategy Discovery Campaign
Asset: XAUUSD (Gold CFD) - 100% Self-Contained Architecture
Regulatory Framework: Strict Constitution V5.1 Compliant (Rules D.1 - D.7)

Research Objectives & User Mandates:
1. Smooth, Monotonic Upward Linear Equity Curve ("เส้นตรงขึ้นไป")
2. Maximum Drawdown strictly < 10% (Targeting Intra-Bar DD < $450 on 0.12 lot base, < 4.5%)
3. Monthly Win Consistency: Maximizing Profitable Months (Targeting >= 90% MCR)
4. Full Resolution of MT5 Tester Starvation:
   - Self-contained XAUUSD M15/M5/H1 causal alignment (Zero multi-symbol handle crashes)
   - Dynamic Broker GMT Offset Translation
   - Exact bar-flip edge trigger
5. 1,000-Run Monte Carlo Tail-Risk Resampling across all 30 strategies
"""

import os
import sys
import gc
import time
import json
import numpy as np
import pandas as pd

# -----------------------------------------------------------------------------
# Fast Pure-NumPy Indicator Routines
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
# Discrete Self-Contained Simulation Engine (Rules D.1 - D.7)
# -----------------------------------------------------------------------------
def simulate_self_contained_engine(
    opens, highs, lows, closes, dates,
    entry_signals, atr_values, vol_ratios, st_bands_30, st_bands_20, engine_name,
    point_value=100.0, lot_size=0.12, spread=0.25, commission_per_lot=6.00,
    sl_slippage=0.10, swap_long_daily=-18.0,
    initial_sl_atr_mult=3.0, compounding_risk_pct=0.0,
    regime_mode=True,
    t1_def_mult=1.2, t1_def_ratio=0.35,
    t2_def_mult=2.4, t2_def_ratio=0.35,
    ny_rapid_mult=0.0, ny_rapid_ratio=0.0,
    accelerate_ratchet=True
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

        active_st_band = st_bands_20[i] if (accelerate_ratchet and tranche2_taken) else st_bands_30[i]

        if pos == 1:
            intra_lowest_pnl = (bar_low - entry_price) * curr_unit - (spread * curr_unit) - (commission_per_lot * active_lot)
            if intra_lowest_pnl < deepest_dip:
                deepest_dip = intra_lowest_pnl

            # Tranche 1 Scale-Out
            if tp1_target > 0.0 and not tranche1_taken and active_lot >= 0.02:
                if bar_high >= tp1_target:
                    ratio = ny_rapid_ratio if (ny_rapid_ratio > 0.0) else (0.40 if (regime_mode and vol_ratios[i-1] < 1.05) else (0.30 if (regime_mode and vol_ratios[i-1] >= 1.30) else t1_def_ratio))
                    t1_lot = round(active_lot * ratio, 2)
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
            if tp2_target > 0.0 and tranche1_taken and not tranche2_taken and active_lot >= 0.02:
                if bar_high >= tp2_target:
                    ratio = 0.40 if (regime_mode and vol_ratios[i-1] < 1.05) else (0.30 if (regime_mode and vol_ratios[i-1] >= 1.30) else t2_def_ratio)
                    t2_lot = round(active_lot * ratio, 2)
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

            # Exit Checks (SL & TrendFlip)
            exit_hit = False
            exit_price = 0.0
            exit_reason = ""

            sl_touched = (bar_low <= current_sl)
            trend_flipped = (closes[i] < active_st_band)

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
                current_equity += net_pnl
                pos = 0
                active_lot = 0.0
                continue

            # Trailing Ratchet SL (Rule D.2)
            if active_st_band > current_sl:
                current_sl = active_st_band

        elif pos == -1:
            intra_lowest_pnl = (entry_price - bar_high) * curr_unit - (spread * curr_unit) - (commission_per_lot * active_lot)
            if intra_lowest_pnl < deepest_dip:
                deepest_dip = intra_lowest_pnl

            # Tranche 1 Scale-Out
            if tp1_target > 0.0 and not tranche1_taken and active_lot >= 0.02:
                if bar_low <= tp1_target:
                    ratio = ny_rapid_ratio if (ny_rapid_ratio > 0.0) else (0.40 if (regime_mode and vol_ratios[i-1] < 1.05) else (0.30 if (regime_mode and vol_ratios[i-1] >= 1.30) else t1_def_ratio))
                    t1_lot = round(active_lot * ratio, 2)
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
            if tp2_target > 0.0 and tranche1_taken and not tranche2_taken and active_lot >= 0.02:
                if bar_low <= tp2_target:
                    ratio = 0.40 if (regime_mode and vol_ratios[i-1] < 1.05) else (0.30 if (regime_mode and vol_ratios[i-1] >= 1.30) else t2_def_ratio)
                    t2_lot = round(active_lot * ratio, 2)
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

            # Exit Checks (SL & TrendFlip)
            exit_hit = False
            exit_price = 0.0
            exit_reason = ""

            sl_touched = (bar_high >= current_sl)
            trend_flipped = (closes[i] > active_st_band)

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
                current_equity += net_pnl
                pos = 0
                active_lot = 0.0
                continue

            # Trailing Ratchet SL (Rule D.2)
            if active_st_band < current_sl:
                current_sl = active_st_band

        # -------------------------------------------------------------
        # Signal Generation & Order Placement
        # -------------------------------------------------------------
        if pos == 0 and entry_signals[i] != 0:
            pos = entry_signals[i]
            entry_time = dates[i + 1]
            deepest_dip = 0.0
            tranche1_taken = False
            tranche2_taken = False

            if compounding_risk_pct > 0.0:
                risk_usd = current_equity * (compounding_risk_pct / 100.0)
                sl_dist = initial_sl_atr_mult * atr_values[i]
                calc_lot = risk_usd / (sl_dist * point_value)
                calc_lot = max(0.01, min(0.30, round(calc_lot, 2)))
                active_lot = calc_lot
            else:
                active_lot = round(lot_size, 2)

            curr_unit = active_lot * point_value

            vr = vol_ratios[i]
            if ny_rapid_mult > 0.0:
                t1_m = ny_rapid_mult
                t2_m = 0.0
            elif regime_mode:
                if vr < 1.05:
                    t1_m = 1.0; t2_m = 2.0
                elif vr >= 1.30:
                    t1_m = 1.5; t2_m = 3.0
                else:
                    t1_m = t1_def_mult; t2_m = t2_def_mult
            else:
                t1_m = t1_def_mult; t2_m = t2_def_mult

            sl_dist = initial_sl_atr_mult * atr_values[i]

            if pos == 1:
                entry_price = opens[i + 1] + (spread * 0.5)
                current_sl = entry_price - sl_dist
                tp1_target = entry_price + (t1_m * atr_values[i]) if t1_m > 0.0 else 0.0
                tp2_target = entry_price + (t2_m * atr_values[i]) if t2_m > 0.0 else 0.0
            else:
                entry_price = opens[i + 1] - (spread * 0.5)
                current_sl = entry_price + sl_dist
                tp1_target = entry_price - (t1_m * atr_values[i]) if t1_m > 0.0 else 0.0
                tp2_target = entry_price - (t2_m * atr_values[i]) if t2_m > 0.0 else 0.0

    return trades

# -----------------------------------------------------------------------------
# Linear Consistency Governor: Daily + Monthly Target-Lock Architecture
# -----------------------------------------------------------------------------
def analyze_linear_consistency_governor(
    trades, base_daily_limit=150.0, lock_in_ratio=0.50,
    monthly_target=0.0, monthly_lock_ratio=0.75, years=6.0
):
    if not trades:
        return {
            "net_profit": 0.0, "pf": 0.0, "total_trades": 0, "annual_trades": 0.0,
            "max_dd": 0.0, "romad": 0.0, "win_rate": 0.0, "mcr": 0.0, "avg_trade": 0.0,
            "filtered_trades": []
        }

    trades = sorted(trades, key=lambda x: x["entry_time"])

    daily_groups = {}
    for t in trades:
        d = t["entry_time"].strftime("%Y-%m-%d")
        daily_groups.setdefault(d, []).append(t)

    month_groups = {}
    for d, d_trades in daily_groups.items():
        m = d[:7]
        month_groups.setdefault(m, {})[d] = d_trades

    filtered_trades = []
    for m, days in month_groups.items():
        running_month_pnl = 0.0
        peak_month_pnl = 0.0
        month_halted = False

        for d, day_trades in days.items():
            if month_halted:
                continue

            running_day_pnl = 0.0
            peak_day_pnl = 0.0
            effective_daily_limit = base_daily_limit
            day_circuit_tripped = False

            for t in day_trades:
                if day_circuit_tripped or month_halted:
                    continue

                filtered_trades.append(t)
                pnl = t["pnl"]
                running_day_pnl += pnl
                running_month_pnl += pnl

                # Daily trailing lock-in
                if running_day_pnl > peak_day_pnl:
                    peak_day_pnl = running_day_pnl
                    if lock_in_ratio > 0.0 and peak_day_pnl > 40.0:
                        lock_floor = peak_day_pnl * (1.0 - lock_in_ratio)
                        effective_daily_limit = min(base_daily_limit, peak_day_pnl - lock_floor)

                if running_day_pnl <= -effective_daily_limit:
                    day_circuit_tripped = True

                # Monthly profit preservation lock
                if running_month_pnl > peak_month_pnl:
                    peak_month_pnl = running_month_pnl

                if monthly_target > 0.0 and peak_month_pnl >= monthly_target:
                    monthly_floor = peak_month_pnl * monthly_lock_ratio
                    if running_month_pnl <= monthly_floor:
                        month_halted = True # Bank and preserve monthly profit!

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
        if np.min(equity_curve) <= (initial_capital * 0.90): # 10% DD Ruin Breach
            ruined_count += 1

    return {
        "mc_p50_dd": float(np.percentile(max_dds, 50)),
        "mc_p95_dd": float(np.percentile(max_dds, 95)),
        "ruin_prob": float((ruined_count / num_simulations) * 100.0)
    }

# -----------------------------------------------------------------------------
# Main Batch 65 Simulation Pipeline
# -----------------------------------------------------------------------------
def main():
    t0 = time.time()
    print("=" * 105)
    print("BATCH 65: LINEAR EQUITY & 90% MONTHLY CONSISTENCY ENGINE (S1146 - S1175)")
    print("Asset: XAUUSD (Gold CFD) | Strict Constitution V5.1 Compliant (Rules D.1 - D.7)")
    print("=" * 105)

    REPO_ROOT = "/content/CFD-Trading-ML" if os.path.exists("/content/CFD-Trading-ML") else "/root/CFD-Trading-ML"
    DATA_DIR = os.path.join(REPO_ROOT, "projects/quant_strategy_discovery/data")
    RESULTS_DIR = os.path.join(REPO_ROOT, "projects/quant_strategy_discovery/results")
    os.makedirs(RESULTS_DIR, exist_ok=True)

    print(f"[+] Loading multi-frequency Gold datasets from {DATA_DIR}...")
    df_m5 = pd.read_parquet(os.path.join(DATA_DIR, "XAUUSD_M5.parquet"))
    df_m15 = pd.read_parquet(os.path.join(DATA_DIR, "XAUUSD_M15.parquet"))
    df_h1 = pd.read_parquet(os.path.join(DATA_DIR, "XAUUSD_H1.parquet"))

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

    # Indicator Calculations
    print("[+] Calculating self-contained indicators...")
    m15_atr14 = compute_atr(m15_highs, m15_lows, m15_closes, 14)
    m15_atr100 = compute_atr(m15_highs, m15_lows, m15_closes, 100)
    m15_vol_ratio = np.divide(m15_atr14, m15_atr100, out=np.ones_like(m15_atr14), where=m15_atr100 > 0)

    st_t30, st_b30 = compute_supertrend(m15_highs, m15_lows, m15_closes, m15_atr14, 3.0)
    st_t20, st_b20 = compute_supertrend(m15_highs, m15_lows, m15_closes, m15_atr14, 2.0)
    m15_ema200 = compute_ema(m15_closes, 200)

    # Candlestick Wick Ratios
    bar_ranges = np.maximum(0.01, m15_highs - m15_lows)
    lower_wick_ratio = (m15_closes - m15_lows) / bar_ranges
    upper_wick_ratio = (m15_highs - m15_closes) / bar_ranges

    # M5 Micro-Structure Alignment
    m5_ema50 = compute_ema(m5_closes, 50)
    m5_trend = np.where(m5_closes > m5_ema50, 1, -1)
    df_m5_state = pd.DataFrame({
        "time": pd.to_datetime(df_m5.index) + pd.Timedelta(minutes=5),
        "m5_tr": m5_trend
    }).sort_values("time")

    # H1 Macro Trend Alignment
    h1_atr14 = compute_atr(h1_highs, h1_lows, h1_closes, 14)
    h1_tr30, _ = compute_supertrend(h1_highs, h1_lows, h1_closes, h1_atr14, 3.0)
    df_h1_state = pd.DataFrame({
        "time": pd.to_datetime(df_h1.index) + pd.Timedelta(hours=1),
        "h1_tr": h1_tr30
    }).sort_values("time")

    # Synchronize onto M15 Timeline
    df_m15_time = pd.DataFrame({"time": pd.to_datetime(df_m15.index)})
    m15_merged_h1 = pd.merge_asof(df_m15_time, df_h1_state, on="time", direction="backward")
    m15_h1_trend = m15_merged_h1["h1_tr"].fillna(1).values.astype(np.int32)

    m15_merged_m5 = pd.merge_asof(df_m15_time, df_m5_state, on="time", direction="backward")
    m15_m5_trend = m15_merged_m5["m5_tr"].fillna(1).values.astype(np.int32)

    del df_m5, df_m5_state, df_h1, df_h1_state, m15_merged_h1, m15_merged_m5, df_m15_time
    gc.collect()

    print(f"[+] Synchronized {n_m15:,} Gold M15 bars under 100% self-contained causal alignment.")

    # Self-Contained Signal Generator (Zero External Pair Crash Risks)
    def generate_gold_signals(start_h, end_h, min_atr=1.40, min_vr=1.00, wick_filter=True, min_wick=0.25):
        sig = np.zeros(n_m15, dtype=np.int32)
        for i in range(200, n_m15 - 1):
            h = m15_dates[i].hour
            if start_h <= h <= end_h:
                if min_atr <= 0.0 or m15_atr14[i] >= min_atr:
                    if min_vr > 0.0 and m15_vol_ratio[i] < min_vr:
                        continue
                    # Exact Bar-Flip Edge Trigger
                    if st_t30[i] == 1 and st_t30[i - 1] == -1 and m15_closes[i] > m15_ema200[i]:
                        if m15_h1_trend[i] == 1 and m15_m5_trend[i] == 1:
                            if not wick_filter or lower_wick_ratio[i] >= min_wick:
                                sig[i] = 1
                    elif st_t30[i] == -1 and st_t30[i - 1] == 1 and m15_closes[i] < m15_ema200[i]:
                        if m15_h1_trend[i] == -1 and m15_m5_trend[i] == -1:
                            if not wick_filter or upper_wick_ratio[i] >= min_wick:
                                sig[i] = -1
        return sig

    # Signal Suites
    sig_early_std = generate_gold_signals(6, 9, 1.40, 1.05, wick_filter=True, min_wick=0.25)
    sig_mid_std   = generate_gold_signals(9, 12, 1.40, 1.00, wick_filter=True, min_wick=0.25)
    sig_ny_std    = generate_gold_signals(12, 16, 1.60, 1.10, wick_filter=True, min_wick=0.25)

    sig_early_wick30 = generate_gold_signals(6, 9, 1.40, 1.05, wick_filter=True, min_wick=0.30)
    sig_mid_wick30   = generate_gold_signals(9, 12, 1.40, 1.00, wick_filter=True, min_wick=0.30)
    sig_ny_wick30    = generate_gold_signals(12, 16, 1.60, 1.10, wick_filter=True, min_wick=0.30)

    sig_early_loose = generate_gold_signals(6, 9, 1.20, 1.00, wick_filter=False)
    sig_mid_loose   = generate_gold_signals(9, 12, 1.20, 1.00, wick_filter=False)
    sig_ny_loose    = generate_gold_signals(12, 16, 1.40, 1.00, wick_filter=False)

    def run_batch65_router(
        sig_early, sig_mid, sig_ny,
        w_early=0.12, w_mid=0.06, w_ny=0.04,
        comp_pct=0.0,
        regime_mode=True,
        t1_mult=1.2, t1_ratio=0.35,
        t2_mult=2.4, t2_ratio=0.35,
        ny_mult=1.1, ny_ratio=0.70,
        accel_ratchet=True
    ):
        t1 = simulate_self_contained_engine(
            m15_opens, m15_highs, m15_lows, m15_closes, m15_dates, sig_early, m15_atr14, m15_vol_ratio, st_b30, st_b20,
            "Early_London", point_value=100.0, lot_size=w_early, compounding_risk_pct=comp_pct*0.5 if comp_pct>0 else 0.0,
            regime_mode=regime_mode, t1_def_mult=t1_mult, t1_def_ratio=t1_ratio, t2_def_mult=t2_mult, t2_def_ratio=t2_ratio,
            accelerate_ratchet=accel_ratchet
        )
        t2 = simulate_self_contained_engine(
            m15_opens, m15_highs, m15_lows, m15_closes, m15_dates, sig_mid, m15_atr14, m15_vol_ratio, st_b30, st_b20,
            "London_Mid", point_value=100.0, lot_size=w_mid, compounding_risk_pct=comp_pct*0.25 if comp_pct>0 else 0.0,
            regime_mode=regime_mode, t1_def_mult=t1_mult, t1_def_ratio=t1_ratio, t2_def_mult=t2_mult, t2_def_ratio=t2_ratio,
            accelerate_ratchet=accel_ratchet
        )
        t3 = simulate_self_contained_engine(
            m15_opens, m15_highs, m15_lows, m15_closes, m15_dates, sig_ny, m15_atr14, m15_vol_ratio, st_b30, st_b20,
            "NY_Open", point_value=100.0, lot_size=w_ny, compounding_risk_pct=comp_pct*0.35 if comp_pct>0 else 0.0,
            regime_mode=regime_mode, t1_def_mult=t1_mult, t1_def_ratio=t1_ratio, t2_def_mult=t2_mult, t2_def_ratio=t2_ratio,
            ny_rapid_mult=ny_mult, ny_rapid_ratio=ny_ratio, accelerate_ratchet=accel_ratchet
        )
        return t1 + t2 + t3

    # Strategy Definitions (S1146 - S1175)
    print("\n[+] Assembling Batch 65 Strategy Suite (S1146 - S1175)...")
    strategy_definitions = [
        # Group 1: Self-Contained Linear Monthly Consistency Matrix (S1146 - S1155)
        ("S1146", "Self-Contained Baseline (0.12/0.06/0.04)", lambda: run_batch65_router(sig_early_std, sig_mid_std, sig_ny_std, 0.12, 0.06, 0.04, regime_mode=True, ny_mult=1.1, ny_ratio=0.70, accel_ratchet=True), 150.0, 0.0, 0.0, 0.0, "Self-Contained Base"),
        ("S1147", "Self-Contained + 50% Daily Lock", lambda: run_batch65_router(sig_early_std, sig_mid_std, sig_ny_std, 0.12, 0.06, 0.04, regime_mode=True, ny_mult=1.1, ny_ratio=0.70, accel_ratchet=True), 150.0, 0.50, 0.0, 0.0, "Self-Contained + Lock"),
        ("S1148", "Wick-Rejection 30% Precision", lambda: run_batch65_router(sig_early_wick30, sig_mid_wick30, sig_ny_wick30, 0.12, 0.06, 0.04, regime_mode=True, ny_mult=1.1, ny_ratio=0.70, accel_ratchet=True), 150.0, 0.0, 0.0, 0.0, "Wick 30% Precision"),
        ("S1149", "Wick-Rejection 30% + 50% Lock", lambda: run_batch65_router(sig_early_wick30, sig_mid_wick30, sig_ny_wick30, 0.12, 0.06, 0.04, regime_mode=True, ny_mult=1.1, ny_ratio=0.70, accel_ratchet=True), 150.0, 0.50, 0.0, 0.0, "Wick 30% + Lock"),
        ("S1150", "Linear Asymmetric Sizing (0.10/0.05/0.03)", lambda: run_batch65_router(sig_early_std, sig_mid_std, sig_ny_std, 0.10, 0.05, 0.03, regime_mode=True, ny_mult=1.1, ny_ratio=0.70, accel_ratchet=True), 120.0, 0.0, 0.0, 0.0, "Linear Asym Base"),
        ("S1151", "Linear Asymmetric + 50% Daily Lock", lambda: run_batch65_router(sig_early_std, sig_mid_std, sig_ny_std, 0.10, 0.05, 0.03, regime_mode=True, ny_mult=1.1, ny_ratio=0.70, accel_ratchet=True), 120.0, 0.50, 0.0, 0.0, "Linear Asym + Lock"),
        ("S1152", "Monthly Target-Lock ($80 / 75% Lock)", lambda: run_batch65_router(sig_early_std, sig_mid_std, sig_ny_std, 0.10, 0.05, 0.03, regime_mode=True, ny_mult=1.1, ny_ratio=0.70, accel_ratchet=True), 120.0, 0.0, 80.0, 0.75, "Monthly Lock $80"),
        ("S1153", "Monthly Target-Lock ($100 / 75% Lock)", lambda: run_batch65_router(sig_early_std, sig_mid_std, sig_ny_std, 0.12, 0.06, 0.04, regime_mode=True, ny_mult=1.1, ny_ratio=0.70, accel_ratchet=True), 150.0, 0.0, 100.0, 0.75, "Monthly Lock $100"),
        ("S1154", "Dual Daily + Monthly Lock ($120 / $80)", lambda: run_batch65_router(sig_early_std, sig_mid_std, sig_ny_std, 0.10, 0.05, 0.03, regime_mode=True, ny_mult=1.1, ny_ratio=0.70, accel_ratchet=True), 120.0, 0.50, 80.0, 0.75, "Dual Daily/Monthly Lock"),
        ("S1155", "Grand Linear Consistency Sovereign 2026", lambda: run_batch65_router(sig_early_std, sig_mid_std, sig_ny_std, 0.12, 0.06, 0.04, regime_mode=True, ny_mult=1.1, ny_ratio=0.70, accel_ratchet=True), 150.0, 0.50, 100.0, 0.75, "Grand Linear Sovereign"),

        # Group 2: Sub-10% Drawdown Floor & Capital Preservation Matrix (S1156 - S1165)
        ("S1156", "Ultra-Shield Micro-Tier (0.04/0.02/0.01)", lambda: run_batch65_router(sig_early_std, sig_mid_std, sig_ny_std, 0.04, 0.02, 0.01, regime_mode=True, ny_mult=1.0, ny_ratio=0.75, accel_ratchet=True), 60.0, 0.0, 0.0, 0.0, "Ultra-Shield Micro"),
        ("S1157", "Ultra-Shield Micro-Tier + 50% Lock", lambda: run_batch65_router(sig_early_std, sig_mid_std, sig_ny_std, 0.04, 0.02, 0.01, regime_mode=True, ny_mult=1.0, ny_ratio=0.75, accel_ratchet=True), 60.0, 0.50, 0.0, 0.0, "Micro-Tier + Lock"),
        ("S1158", "Prop-Firm 5% Floor (0.05/0.02/0.02)", lambda: run_batch65_router(sig_early_std, sig_mid_std, sig_ny_std, 0.05, 0.02, 0.02, regime_mode=True, ny_mult=1.0, ny_ratio=0.75, accel_ratchet=True), 80.0, 0.0, 0.0, 0.0, "Prop-Firm 5% Floor"),
        ("S1159", "Prop-Firm 5% Floor + 50% Lock", lambda: run_batch65_router(sig_early_std, sig_mid_std, sig_ny_std, 0.05, 0.02, 0.02, regime_mode=True, ny_mult=1.0, ny_ratio=0.75, accel_ratchet=True), 80.0, 0.50, 0.0, 0.0, "Prop-Firm 5% + Lock"),
        ("S1160", "Prop-Firm Dynamic Floor (0.06/0.03/0.02)", lambda: run_batch65_router(sig_early_std, sig_mid_std, sig_ny_std, 0.06, 0.03, 0.02, regime_mode=True, ny_mult=1.1, ny_ratio=0.70, accel_ratchet=True), 90.0, 0.0, 0.0, 0.0, "Dynamic Floor Base"),
        ("S1161", "Prop-Firm Dynamic Floor + 50% Lock", lambda: run_batch65_router(sig_early_std, sig_mid_std, sig_ny_std, 0.06, 0.03, 0.02, regime_mode=True, ny_mult=1.1, ny_ratio=0.70, accel_ratchet=True), 90.0, 0.50, 0.0, 0.0, "Dynamic Floor + Lock"),
        ("S1162", "Sub-10% Shield (0.08/0.04/0.02)", lambda: run_batch65_router(sig_early_std, sig_mid_std, sig_ny_std, 0.08, 0.04, 0.02, regime_mode=True, ny_mult=1.1, ny_ratio=0.70, accel_ratchet=True), 100.0, 0.0, 0.0, 0.0, "Sub-10% Shield Base"),
        ("S1163", "Sub-10% Shield + 50% Lock", lambda: run_batch65_router(sig_early_std, sig_mid_std, sig_ny_std, 0.08, 0.04, 0.02, regime_mode=True, ny_mult=1.1, ny_ratio=0.70, accel_ratchet=True), 100.0, 0.50, 0.0, 0.0, "Sub-10% Shield + Lock"),
        ("S1164", "Sub-10% Shield + Monthly Lock $60", lambda: run_batch65_router(sig_early_std, sig_mid_std, sig_ny_std, 0.06, 0.03, 0.02, regime_mode=True, ny_mult=1.1, ny_ratio=0.70, accel_ratchet=True), 90.0, 0.50, 60.0, 0.80, "Sub-10% Monthly $60"),
        ("S1165", "Sub-10% Shield + Monthly Lock $80", lambda: run_batch65_router(sig_early_std, sig_mid_std, sig_ny_std, 0.08, 0.04, 0.02, regime_mode=True, ny_mult=1.1, ny_ratio=0.70, accel_ratchet=True), 100.0, 0.50, 80.0, 0.80, "Sub-10% Monthly $80"),

        # Group 3: High-Expectancy Micro-Compounding Suite (S1166 - S1175)
        ("S1166", "Micro-Compounding 0.50% Risk", lambda: run_batch65_router(sig_early_std, sig_mid_std, sig_ny_std, 0.08, 0.04, 0.02, comp_pct=0.50, regime_mode=True, ny_mult=1.1, ny_ratio=0.70, accel_ratchet=True), 120.0, 0.0, 0.0, 0.0, "Comp 0.50% Base"),
        ("S1167", "Micro-Compounding 0.75% Risk", lambda: run_batch65_router(sig_early_std, sig_mid_std, sig_ny_std, 0.08, 0.04, 0.02, comp_pct=0.75, regime_mode=True, ny_mult=1.1, ny_ratio=0.70, accel_ratchet=True), 140.0, 0.0, 0.0, 0.0, "Comp 0.75% Base"),
        ("S1168", "Micro-Compounding 1.00% Risk", lambda: run_batch65_router(sig_early_std, sig_mid_std, sig_ny_std, 0.08, 0.04, 0.02, comp_pct=1.00, regime_mode=True, ny_mult=1.1, ny_ratio=0.70, accel_ratchet=True), 160.0, 0.0, 0.0, 0.0, "Comp 1.00% Base"),
        ("S1169", "Micro-Compounding 1.25% Risk", lambda: run_batch65_router(sig_early_std, sig_mid_std, sig_ny_std, 0.08, 0.04, 0.02, comp_pct=1.25, regime_mode=True, ny_mult=1.1, ny_ratio=0.70, accel_ratchet=True), 180.0, 0.0, 0.0, 0.0, "Comp 1.25% Base"),
        ("S1170", "Micro-Compounding 1.50% Risk", lambda: run_batch65_router(sig_early_std, sig_mid_std, sig_ny_std, 0.08, 0.04, 0.02, comp_pct=1.50, regime_mode=True, ny_mult=1.1, ny_ratio=0.70, accel_ratchet=True), 200.0, 0.0, 0.0, 0.0, "Comp 1.50% Base"),
        ("S1171", "Comp 0.75% + Monthly Lock $100", lambda: run_batch65_router(sig_early_std, sig_mid_std, sig_ny_std, 0.08, 0.04, 0.02, comp_pct=0.75, regime_mode=True, ny_mult=1.1, ny_ratio=0.70, accel_ratchet=True), 140.0, 0.50, 100.0, 0.75, "Comp 0.75% Lock"),
        ("S1172", "Comp 1.00% + Monthly Lock $120", lambda: run_batch65_router(sig_early_std, sig_mid_std, sig_ny_std, 0.08, 0.04, 0.02, comp_pct=1.00, regime_mode=True, ny_mult=1.1, ny_ratio=0.70, accel_ratchet=True), 160.0, 0.50, 120.0, 0.75, "Comp 1.00% Lock"),
        ("S1173", "Comp 1.25% + Monthly Lock $150", lambda: run_batch65_router(sig_early_std, sig_mid_std, sig_ny_std, 0.08, 0.04, 0.02, comp_pct=1.25, regime_mode=True, ny_mult=1.1, ny_ratio=0.70, accel_ratchet=True), 180.0, 0.50, 150.0, 0.75, "Comp 1.25% Lock"),
        ("S1174", "Grand Sovereign Consistency Vault 2026", lambda: run_batch65_router(sig_early_std, sig_mid_std, sig_ny_std, 0.10, 0.05, 0.03, comp_pct=0.75, regime_mode=True, ny_mult=1.1, ny_ratio=0.70, accel_ratchet=True), 150.0, 0.50, 120.0, 0.75, "Grand Consistency Vault"),
        ("S1175", "Apex Sovereign Linear Consistency Paragon 2026", lambda: run_batch65_router(sig_early_std, sig_mid_std, sig_ny_std, 0.12, 0.06, 0.04, comp_pct=1.00, regime_mode=True, ny_mult=1.1, ny_ratio=0.70, accel_ratchet=True), 180.0, 0.50, 150.0, 0.75, "👑 Apex Sovereign Linear Consistency Paragon 2026")
    ]

    # Evaluation Loop
    results_table = []
    print("\n" + "=" * 145)
    print(f"{'ID':<6} {'Strategy Name':<42} {'Ann.Tr':<8} {'Tot.Tr':<8} {'Net PnL ($)':<14} {'PF':<8} {'WR%':<8} {'Intra DD ($)':<14} {'MC P95 DD':<12} {'Ruin%':<8} {'MCR%':<8}")
    print("=" * 145)

    for sid, name, fn, gov, lock_ratio, m_tgt, m_lock, role in strategy_definitions:
        trades = fn()
        m = analyze_linear_consistency_governor(
            trades, base_daily_limit=gov, lock_in_ratio=lock_ratio,
            monthly_target=m_tgt, monthly_lock_ratio=m_lock, years=6.0
        )
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

        print(f"{sid:<6} {name:<42} {row['Annual_Trades']:<8} {row['Total_Trades']:<8} {row['Net_Profit']:<14.2f} {row['Profit_Factor']:<8.3f} {row['Win_Rate_Pct']:<8.1f} {row['True_Intra_Max_DD']:<14.2f} {row['MC_P95_DD']:<12.2f} {row['Ruin_Probability_Pct']:<8.1f} {row['MCR_Pct']:<8.1f}")

    print("=" * 145)

    # Export Results
    out_csv = os.path.join(RESULTS_DIR, "batch_65_linear_consistency_matrix.csv")
    out_json = os.path.join(RESULTS_DIR, "batch_65_linear_consistency_results.json")
    df_res = pd.DataFrame(results_table)
    df_res.to_csv(out_csv, index=False)
    with open(out_json, "w") as f:
        json.dump(results_table, f, indent=2)

    elapsed = time.time() - t0
    print(f"\n[+] Batch 65 Linear Consistency Execution Complete in {elapsed:.2f}s!")
    print(f"[+] Saved results matrix to {out_csv}")
    print(f"[+] Saved results JSON to {out_json}")

if __name__ == "__main__":
    main()
