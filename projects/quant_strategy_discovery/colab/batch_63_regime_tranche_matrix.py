"""
Batch 63: Volatility-Regime Adaptive Tri-Tranche Matrix (S1086 - S1115)
======================================================================
CFD Quantitative Strategy Discovery Campaign
Asset: XAUUSD (Gold CFD) + EURUSD Macro Anchor Gate
Regulatory Framework: Strict Constitution V5.1 Compliant (Rules D.1 - D.7)

Scientific Hypotheses:
1. Dynamic Regime-Adaptive Tri-Tranche Sizing:
   - State A: Low Volatility (VR < 1.05) -> Fast harvest (T1: 1.0R @ 40%, T2: 2.0R @ 40%, Runner: 20%)
   - State B: Normal Volatility (1.05 <= VR < 1.30) -> Precision standard (T1: 1.2R @ 35%, T2: 2.4R @ 35%, Runner: 30%)
   - State C: High Expansion (VR >= 1.30) -> Momentum capture (T1: 1.5R @ 30%, T2: 3.0R @ 30%, Runner: 40%)
2. Session Asymmetric Sizing:
   - Early London: 0.16 lot / London Midday: 0.08 lot / NY Open: 0.04 lot (with ultra-rapid 1.0R / 75% exit)
3. Sub-$140 Drawdown Floor Prop-Firm Challenge Optimization (0.04 / 0.02 / 0.02 lots)
4. Micro-Compounding Matrix (0.5% to 1.5%) with 50% High-Water Mark Trailing Profit Lock
5. Full 1,000-Run Monte Carlo Tail-Risk Resampling
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
# Discrete Regime-Adaptive Tri-Tranche Simulator (Rules D.1 - D.7 Compliant)
# -----------------------------------------------------------------------------
def simulate_regime_tri_tranche_engine(
    opens, highs, lows, closes, dates,
    entry_signals, atr_values, vol_ratios, st_bands, engine_name,
    point_value=100.0, lot_size=0.12, spread=0.25, commission_per_lot=6.00,
    sl_slippage=0.10, swap_long_daily=-18.0,
    initial_sl_atr_mult=3.0, compounding_risk_pct=0.0,
    regime_mode=True, # Dynamic Regime-Adaptive Sizing
    t1_def_mult=1.2, t1_def_ratio=0.35,
    t2_def_mult=2.4, t2_def_ratio=0.35,
    ny_rapid_mult=0.0, ny_rapid_ratio=0.0
):
    n = len(closes)
    trades = []
    pos = 0
    entry_idx = 0
    entry_price = 0.0
    current_sl = 0.0
    active_lot = lot_size
    t1_closed = False
    t2_closed = False

    t1_target = 0.0
    t2_target = 0.0
    t1_close_vol = 0.0
    t2_close_vol = 0.0

    cumulative_pnl = 0.0
    trade_peak_equity = 0.0
    trade_max_adverse = 0.0

    for i in range(1, n):
        cur_open = opens[i]
        cur_high = highs[i]
        cur_low = lows[i]
        cur_close = closes[i]
        cur_date = dates[i]
        cur_atr = atr_values[i - 1]
        cur_vr = vol_ratios[i - 1]
        cur_st_band = st_bands[i - 1]

        # -------------------------------------------------------------
        # Active Position Management
        # -------------------------------------------------------------
        if pos != 0:
            # Intra-bar adverse excursion (Rule D.3)
            if pos == 1:
                worst_price = cur_low
                best_price = cur_high
                unrealized_worst = (worst_price - entry_price) * active_lot * point_value
                unrealized_best = (best_price - entry_price) * active_lot * point_value
            else:
                worst_price = cur_high
                best_price = cur_low
                unrealized_worst = (entry_price - worst_price) * active_lot * point_value
                unrealized_best = (entry_price - best_price) * active_lot * point_value

            if unrealized_best > trade_peak_equity:
                trade_peak_equity = unrealized_best
            dd_drop = trade_peak_equity - unrealized_worst
            if dd_drop > trade_max_adverse:
                trade_max_adverse = dd_drop

            # Check Stop Loss & Bar-Close Ratchet
            sl_hit = False
            sl_exit_price = 0.0

            # Rule D.1 Pessimistic Sequence: If SL is breached intra-bar
            if pos == 1 and cur_low <= current_sl:
                sl_hit = True
                sl_exit_price = current_sl - sl_slippage
            elif pos == -1 and cur_high >= current_sl:
                sl_hit = True
                sl_exit_price = current_sl + sl_slippage

            if sl_hit:
                # Close entire remaining volume at SL
                trade_days = max(1, (cur_date - dates[entry_idx]).total_seconds() / 86400.0)
                swap_cost = (swap_long_daily * active_lot * trade_days) if pos == 1 else 0.0
                comm_cost = commission_per_lot * active_lot * 2.0
                raw_diff = (sl_exit_price - entry_price) if pos == 1 else (entry_price - sl_exit_price)
                realized_pnl = (raw_diff - spread) * active_lot * point_value + swap_cost - comm_cost

                trades.append({
                    "engine": engine_name,
                    "entry_time": dates[entry_idx],
                    "exit_time": cur_date,
                    "pos": pos,
                    "entry_price": entry_price,
                    "exit_price": sl_exit_price,
                    "lot": active_lot,
                    "pnl": realized_pnl,
                    "exit_reason": "SL_Hit",
                    "intra_adverse_dd": trade_max_adverse
                })
                pos = 0
                active_lot = 0.0
                continue

            # Tranche 1 Evaluation
            if not t1_closed and t1_close_vol >= 0.01:
                t1_hit = (cur_high >= t1_target) if pos == 1 else (cur_low <= t1_target)
                if t1_hit:
                    trade_days = max(1, (cur_date - dates[entry_idx]).total_seconds() / 86400.0)
                    swap_cost = (swap_long_daily * t1_close_vol * trade_days) if pos == 1 else 0.0
                    comm_cost = commission_per_lot * t1_close_vol * 2.0
                    raw_diff = (t1_target - entry_price) if pos == 1 else (entry_price - t1_target)
                    t1_pnl = (raw_diff - spread) * t1_close_vol * point_value + swap_cost - comm_cost

                    trades.append({
                        "engine": engine_name,
                        "entry_time": dates[entry_idx],
                        "exit_time": cur_date,
                        "pos": pos,
                        "entry_price": entry_price,
                        "exit_price": t1_target,
                        "lot": t1_close_vol,
                        "pnl": t1_pnl,
                        "exit_reason": "Tranche1_TP",
                        "intra_adverse_dd": trade_max_adverse
                    })
                    active_lot = round(active_lot - t1_close_vol, 2)
                    t1_closed = True

            # Tranche 2 Evaluation
            if not t2_closed and t2_close_vol >= 0.01:
                t2_hit = (cur_high >= t2_target) if pos == 1 else (cur_low <= t2_target)
                if t2_hit:
                    trade_days = max(1, (cur_date - dates[entry_idx]).total_seconds() / 86400.0)
                    swap_cost = (swap_long_daily * t2_close_vol * trade_days) if pos == 1 else 0.0
                    comm_cost = commission_per_lot * t2_close_vol * 2.0
                    raw_diff = (t2_target - entry_price) if pos == 1 else (entry_price - t2_target)
                    t2_pnl = (raw_diff - spread) * t2_close_vol * point_value + swap_cost - comm_cost

                    trades.append({
                        "engine": engine_name,
                        "entry_time": dates[entry_idx],
                        "exit_time": cur_date,
                        "pos": pos,
                        "entry_price": entry_price,
                        "exit_price": t2_target,
                        "lot": t2_close_vol,
                        "pnl": t2_pnl,
                        "exit_reason": "Tranche2_TP",
                        "intra_adverse_dd": trade_max_adverse
                    })
                    active_lot = round(active_lot - t2_close_vol, 2)
                    t2_closed = True

            # Tranche 3 Trailing Ratchet Exit (Rule D.2 Bar-Close Mandate)
            if active_lot >= 0.01:
                close_st_exit = False
                if pos == 1 and cur_close < cur_st_band:
                    close_st_exit = True
                elif pos == -1 and cur_close > cur_st_band:
                    close_st_exit = True

                if close_st_exit:
                    exit_p = cur_close
                    trade_days = max(1, (cur_date - dates[entry_idx]).total_seconds() / 86400.0)
                    swap_cost = (swap_long_daily * active_lot * trade_days) if pos == 1 else 0.0
                    comm_cost = commission_per_lot * active_lot * 2.0
                    raw_diff = (exit_p - entry_price) if pos == 1 else (entry_price - exit_p)
                    realized_pnl = (raw_diff - spread) * active_lot * point_value + swap_cost - comm_cost

                    trades.append({
                        "engine": engine_name,
                        "entry_time": dates[entry_idx],
                        "exit_time": cur_date,
                        "pos": pos,
                        "entry_price": entry_price,
                        "exit_price": exit_p,
                        "lot": active_lot,
                        "pnl": realized_pnl,
                        "exit_reason": "Supertrend_Close",
                        "intra_adverse_dd": trade_max_adverse
                    })
                    pos = 0
                    active_lot = 0.0
                    continue

                # Bar-Close Ratchet SL update (Rule D.2)
                if pos == 1:
                    if cur_st_band > current_sl:
                        current_sl = cur_st_band
                else:
                    if cur_st_band < current_sl:
                        current_sl = cur_st_band

        # -------------------------------------------------------------
        # New Entry Signal Evaluation
        # -------------------------------------------------------------
        if pos == 0 and entry_signals[i] != 0:
            pos = int(entry_signals[i])
            entry_idx = i
            entry_price = cur_open
            t1_closed = False
            t2_closed = False
            trade_peak_equity = 0.0
            trade_max_adverse = 0.0

            # Dynamic Compounding Lot Sizing
            if compounding_risk_pct > 0.0:
                cur_equity = max(2000.0, 10000.0 + cumulative_pnl)
                risk_usd = cur_equity * (compounding_risk_pct / 100.0)
                sl_dist = 3.0 * cur_atr
                calc_lot = risk_usd / (sl_dist * point_value)
                calc_lot = max(0.01, min(0.30, round(calc_lot, 2)))
                active_lot = calc_lot
            else:
                active_lot = round(lot_size, 2)

            # Initial Stop Loss
            if pos == 1:
                current_sl = entry_price - (initial_sl_atr_mult * cur_atr)
            else:
                current_sl = entry_price + (initial_sl_atr_mult * cur_atr)

            # Determine Tranche Configuration
            if ny_rapid_mult > 0.0:
                # NY Rapid Exit Single-Tranche Override
                t1_target = entry_price + (ny_rapid_mult * cur_atr) if pos == 1 else entry_price - (ny_rapid_mult * cur_atr)
                t1_close_vol = round(active_lot * ny_rapid_ratio, 2)
                t2_target = 0.0
                t2_close_vol = 0.0
                t2_closed = True
            elif regime_mode:
                # Tri-Tranche Regime Adaptive Logic:
                if cur_vr < 1.05:
                    # Regime A: Low Volatility (Fast Harvest)
                    t1_m, t1_r = 1.0, 0.40
                    t2_m, t2_r = 2.0, 0.40
                elif cur_vr >= 1.30:
                    # Regime C: High Expansion (Momentum Capture)
                    t1_m, t1_r = 1.5, 0.30
                    t2_m, t2_r = 3.0, 0.30
                else:
                    # Regime B: Normal Volatility (Precision Standard)
                    t1_m, t1_r = 1.2, 0.35
                    t2_m, t2_r = 2.4, 0.35

                t1_target = entry_price + (t1_m * cur_atr) if pos == 1 else entry_price - (t1_m * cur_atr)
                t1_close_vol = round(active_lot * t1_r, 2)
                t2_target = entry_price + (t2_m * cur_atr) if pos == 1 else entry_price - (t2_m * cur_atr)
                t2_close_vol = round(active_lot * t2_r, 2)
            else:
                # Static Tri-Tranche
                t1_target = entry_price + (t1_def_mult * cur_atr) if pos == 1 else entry_price - (t1_def_mult * cur_atr)
                t1_close_vol = round(active_lot * t1_def_ratio, 2)
                t2_target = entry_price + (t2_def_mult * cur_atr) if pos == 1 else entry_price - (t2_def_mult * cur_atr)
                t2_close_vol = round(active_lot * t2_def_ratio, 2)

            # Ensure minimum lot validity
            if t1_close_vol < 0.01: t1_closed = True
            if t2_close_vol < 0.01: t2_closed = True

    return trades

# -----------------------------------------------------------------------------
# Portfolio Trailing Governor & Performance Evaluator
# -----------------------------------------------------------------------------
def analyze_trades_with_trailing_governor(trades, base_daily_limit=200.0, lock_in_ratio=0.50, years=6.0):
    if not trades:
        return {
            "total_trades": 0, "annual_trades": 0.0, "net_profit": 0.0,
            "pf": 0.0, "win_rate": 0.0, "max_dd": 0.0, "romad": 0.0,
            "mcr": 0.0, "avg_trade": 0.0, "filtered_trades": []
        }

    df = pd.DataFrame(trades)
    df["exit_date"] = pd.to_datetime(df["exit_time"]).dt.date
    df = df.sort_values("exit_time").reset_index(drop=True)

    filtered_trades = []
    daily_groups = df.groupby("exit_date")

    for date, group in daily_groups:
        daily_pnl = 0.0
        daily_peak = 0.0
        for _, row in group.iterrows():
            floor = -base_daily_limit
            if lock_in_ratio > 0.0 and daily_peak > 0.0:
                locked_floor = daily_peak * (1.0 - lock_in_ratio)
                floor = max(-base_daily_limit, locked_floor)

            if daily_pnl <= floor:
                continue

            filtered_trades.append(row.to_dict())
            daily_pnl += row["pnl"]
            if daily_pnl > daily_peak:
                daily_peak = daily_pnl

    if not filtered_trades:
        return {
            "total_trades": 0, "annual_trades": 0.0, "net_profit": 0.0,
            "pf": 0.0, "win_rate": 0.0, "max_dd": 0.0, "romad": 0.0,
            "mcr": 0.0, "avg_trade": 0.0, "filtered_trades": []
        }

    fdf = pd.DataFrame(filtered_trades)
    pnls = fdf["pnl"].values
    wins = pnls[pnls > 0]
    losses = pnls[pnls < 0]

    gross_profit = float(np.sum(wins)) if len(wins) > 0 else 0.0
    gross_loss = float(abs(np.sum(losses))) if len(losses) > 0 else 0.0
    net_profit = gross_profit - gross_loss
    pf = (gross_profit / gross_loss) if gross_loss > 0 else (99.0 if gross_profit > 0 else 0.0)
    win_rate = (len(wins) / len(pnls)) * 100.0 if len(pnls) > 0 else 0.0

    # True intra-bar maximum drawdown
    cum_equity = np.cumsum(pnls)
    peak_equity = np.maximum.accumulate(cum_equity)
    closed_dd = peak_equity - cum_equity

    # Include intra-bar excursion
    intra_dds = fdf["intra_adverse_dd"].values
    true_max_dd = float(max(np.max(closed_dd) if len(closed_dd) > 0 else 0.0, np.max(intra_dds) if len(intra_dds) > 0 else 0.0))
    if true_max_dd == 0.0:
        true_max_dd = 1.0

    romad = net_profit / true_max_dd if true_max_dd > 0 else 0.0
    tot_trades = len(pnls)
    ann_trades = tot_trades / years
    avg_pnl = net_profit / tot_trades if tot_trades > 0 else 0.0

    # Maximum Consecutive Losses (MCR)
    loss_streaks = []
    cur_streak = 0
    for p in pnls:
        if p < 0:
            cur_streak += 1
        else:
            if cur_streak > 0:
                loss_streaks.append(cur_streak)
            cur_streak = 0
    if cur_streak > 0:
        loss_streaks.append(cur_streak)
    max_loss_streak = max(loss_streaks) if loss_streaks else 0
    mcr = (max_loss_streak / tot_trades) * 100.0 if tot_trades > 0 else 0.0

    return {
        "total_trades": tot_trades,
        "annual_trades": ann_trades,
        "net_profit": net_profit,
        "pf": pf,
        "win_rate": win_rate,
        "max_dd": true_max_dd,
        "romad": romad,
        "mcr": mcr,
        "avg_trade": avg_pnl,
        "filtered_trades": filtered_trades
    }

# -----------------------------------------------------------------------------
# 1,000-Run Monte Carlo Tail-Risk Simulator
# -----------------------------------------------------------------------------
def run_monte_carlo(trades, num_simulations=1000, initial_capital=10000.0):
    if not trades or len(trades) < 10:
        return {"mc_p50_dd": 0.0, "mc_p95_dd": 0.0, "ruin_prob": 0.0}

    pnls = np.array([t["pnl"] for t in trades], dtype=np.float64)
    n = len(pnls)
    max_dds = np.zeros(num_simulations, dtype=np.float64)
    ruin_count = 0

    np.random.seed(42)
    for s in range(num_simulations):
        sampled_pnls = np.random.choice(pnls, size=n, replace=True)
        equity = initial_capital + np.cumsum(sampled_pnls)
        peaks = np.maximum.accumulate(equity)
        dds = peaks - equity
        max_dd = np.max(dds)
        max_dds[s] = max_dd
        if np.min(equity) <= (initial_capital * 0.70): # 30% catastrophic ruin
            ruin_count += 1

    p50_dd = float(np.percentile(max_dds, 50))
    p95_dd = float(np.percentile(max_dds, 95))
    ruin_prob = float((ruin_count / num_simulations) * 100.0)

    return {
        "mc_p50_dd": p50_dd,
        "mc_p95_dd": p95_dd,
        "ruin_prob": ruin_prob
    }

# -----------------------------------------------------------------------------
# Main Batch 63 Simulation Pipeline
# -----------------------------------------------------------------------------
def main():
    t0 = time.time()
    print("=" * 100)
    print("BATCH 63: VOLATILITY-REGIME ADAPTIVE TRI-TRANCHE MATRIX (S1086 - S1115)")
    print("====================================================================================================")

    # Resolve paths
    base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    DATA_DIR = os.path.join(base_dir, "data")
    RESULTS_DIR = os.path.join(base_dir, "results")
    os.makedirs(RESULTS_DIR, exist_ok=True)

    print(f"[+] Loading multi-frequency Gold and EURUSD datasets from {DATA_DIR}...")
    gold_m15_path = os.path.join(DATA_DIR, "XAUUSD_M15.parquet")
    gold_m5_path  = os.path.join(DATA_DIR, "XAUUSD_M5.parquet")
    gold_h1_path  = os.path.join(DATA_DIR, "XAUUSD_H1.parquet")
    eur_m15_path  = os.path.join(DATA_DIR, "EURUSD_M15.parquet")

    df_m15 = pd.read_parquet(gold_m15_path).sort_values("time").reset_index(drop=True)
    df_m5  = pd.read_parquet(gold_m5_path).sort_values("time").reset_index(drop=True)
    df_h1  = pd.read_parquet(gold_h1_path).sort_values("time").reset_index(drop=True)
    df_eu  = pd.read_parquet(eur_m15_path).sort_values("time").reset_index(drop=True)

    # Standardize time
    df_m15["time"] = pd.to_datetime(df_m15["time"])
    df_m5["time"]  = pd.to_datetime(df_m5["time"])
    df_h1["time"]  = pd.to_datetime(df_h1["time"])
    df_eu["time"]  = pd.to_datetime(df_eu["time"])

    # Compute M5 Alignment EMA
    print("[+] Calculating multi-timeframe indicators...")
    m5_closes = df_m5["close"].values
    m5_ema50 = compute_ema(m5_closes, 50)
    df_m5["m5_ema50"] = m5_ema50
    df_m5["m5_bull"] = df_m5["close"] > df_m5["m5_ema50"]
    df_m5["m5_bear"] = df_m5["close"] < df_m5["m5_ema50"]

    # Compute H1 Supertrend Trend Filter
    h1_highs  = df_h1["high"].values
    h1_lows   = df_h1["low"].values
    h1_closes = df_h1["close"].values
    h1_atr    = compute_atr(h1_highs, h1_lows, h1_closes, 14)
    h1_trend, h1_band = compute_supertrend(h1_highs, h1_lows, h1_closes, h1_atr, 3.0)
    df_h1["h1_trend"] = h1_trend

    # Compute EURUSD Regime EMA
    eu_closes = df_eu["close"].values
    eu_ema50  = compute_ema(eu_closes, 50)
    df_eu["eu_bull"] = df_eu["close"] > eu_ema50
    df_eu["eu_bear"] = df_eu["close"] < eu_ema50

    # Align multi-timeframe data to Gold M15
    m15_opens  = df_m15["open"].values
    m15_highs  = df_m15["high"].values
    m15_lows   = df_m15["low"].values
    m15_closes = df_m15["close"].values
    m15_dates  = df_m15["time"]

    m15_atr14  = compute_atr(m15_highs, m15_lows, m15_closes, 14)
    m15_atr100 = compute_atr(m15_highs, m15_lows, m15_closes, 100)
    m15_vol_ratio = np.divide(m15_atr14, np.where(m15_atr100 == 0, 1.0, m15_atr100))

    st_tr30, st_b30 = compute_supertrend(m15_highs, m15_lows, m15_closes, m15_atr14, 3.0)
    ema200 = compute_ema(m15_closes, 200)

    # Merge H1, M5, EURUSD onto M15
    df_m15_sub = pd.DataFrame({"time": df_m15["time"]})
    df_h1_merge = pd.merge_asof(df_m15_sub, df_h1[["time", "h1_trend"]], on="time", direction="backward")
    df_m5_merge = pd.merge_asof(df_m15_sub, df_m5[["time", "m5_bull", "m5_bear"]], on="time", direction="backward")
    df_eu_merge = pd.merge_asof(df_m15_sub, df_eu[["time", "eu_bull", "eu_bear"]], on="time", direction="backward")

    h1_trend_aligned = df_h1_merge["h1_trend"].values
    m5_bull_aligned  = df_m5_merge["m5_bull"].values
    m5_bear_aligned  = df_m5_merge["m5_bear"].values
    eu_bull_aligned  = df_eu_merge["eu_bull"].values
    eu_bear_aligned  = df_eu_merge["eu_bear"].values

    n_bars = len(m15_closes)
    print(f"[+] Synchronized {n_bars:,} Gold M15 bars under multi-frequency causal alignment.")

    # Generate Session-Specific Entry Signals
    hours = m15_dates.dt.hour.values

    def generate_gold_signals(start_h, end_h, min_atr, min_vr=1.0):
        sig = np.zeros(n_bars, dtype=np.int32)
        for i in range(1, n_bars):
            h = hours[i]
            if start_h <= h < end_h:
                if m15_atr14[i - 1] >= min_atr and m15_vol_ratio[i - 1] >= min_vr:
                    # Bullish Confluence
                    if (m15_closes[i - 1] > ema200[i - 1] and st_tr30[i - 1] == 1 and
                        h1_trend_aligned[i - 1] == 1 and m5_bull_aligned[i - 1] and eu_bull_aligned[i - 1]):
                        sig[i] = 1
                    # Bearish Confluence
                    elif (m15_closes[i - 1] < ema200[i - 1] and st_tr30[i - 1] == -1 and
                          h1_trend_aligned[i - 1] == -1 and m5_bear_aligned[i - 1] and eu_bear_aligned[i - 1]):
                        sig[i] = -1
        return sig

    sig_early_lon = generate_gold_signals(6, 9, 1.50, min_vr=1.10)
    sig_mid_lon   = generate_gold_signals(9, 12, 1.50, min_vr=1.05)
    sig_ny_open   = generate_gold_signals(12, 16, 1.80, min_vr=1.15)

    def run_batch63_router(
        w_early=0.16, w_mid=0.08, w_ny=0.04,
        comp_pct=0.0,
        regime_mode=True,
        t1_mult=1.2, t1_ratio=0.35,
        t2_mult=2.4, t2_ratio=0.35,
        ny_mult=1.0, ny_ratio=0.75
    ):
        t1 = simulate_regime_tri_tranche_engine(
            m15_opens, m15_highs, m15_lows, m15_closes, m15_dates, sig_early_lon, m15_atr14, m15_vol_ratio, st_b30,
            "Early_London", point_value=100.0, lot_size=w_early, compounding_risk_pct=comp_pct*0.5 if comp_pct>0 else 0.0,
            regime_mode=regime_mode, t1_def_mult=t1_mult, t1_def_ratio=t1_ratio, t2_def_mult=t2_mult, t2_def_ratio=t2_ratio
        )
        t2 = simulate_regime_tri_tranche_engine(
            m15_opens, m15_highs, m15_lows, m15_closes, m15_dates, sig_mid_lon, m15_atr14, m15_vol_ratio, st_b30,
            "London_Mid", point_value=100.0, lot_size=w_mid, compounding_risk_pct=comp_pct*0.25 if comp_pct>0 else 0.0,
            regime_mode=regime_mode, t1_def_mult=t1_mult, t1_def_ratio=t1_ratio, t2_def_mult=t2_mult, t2_def_ratio=t2_ratio
        )
        t3 = simulate_regime_tri_tranche_engine(
            m15_opens, m15_highs, m15_lows, m15_closes, m15_dates, sig_ny_open, m15_atr14, m15_vol_ratio, st_b30,
            "NY_Open", point_value=100.0, lot_size=w_ny, compounding_risk_pct=comp_pct*0.35 if comp_pct>0 else 0.0,
            regime_mode=regime_mode, t1_def_mult=t1_mult, t1_def_ratio=t1_ratio, t2_def_mult=t2_mult, t2_def_ratio=t2_ratio,
            ny_rapid_mult=ny_mult, ny_rapid_ratio=ny_ratio
        )
        return t1 + t2 + t3

    # Strategy Definitions (S1086 - S1115)
    print("\n[+] Assembling Batch 63 Strategy Suite (S1086 - S1115)...")
    strategy_definitions = [
        # Group 1: Volatility-Regime Tri-Tranche Adaptation (S1086 - S1095)
        ("S1086", "Regime-Adaptive Tri-Tranche Base", lambda: run_batch63_router(0.16, 0.08, 0.04, regime_mode=True, ny_mult=1.0, ny_ratio=0.75), 200.0, 0.0, "Regime-Adaptive Base"),
        ("S1087", "Regime-Adaptive Tri-Tranche + 50% Lock", lambda: run_batch63_router(0.16, 0.08, 0.04, regime_mode=True, ny_mult=1.0, ny_ratio=0.75), 200.0, 0.50, "Regime-Adaptive + Lock"),
        ("S1088", "Regime-Adaptive (NY 1.1R Rapid 70%)", lambda: run_batch63_router(0.16, 0.08, 0.04, regime_mode=True, ny_mult=1.1, ny_ratio=0.70), 200.0, 0.0, "Regime-Adaptive NY 1.1R"),
        ("S1089", "Regime-Adaptive (NY 1.1R Rapid) + Lock", lambda: run_batch63_router(0.16, 0.08, 0.04, regime_mode=True, ny_mult=1.1, ny_ratio=0.70), 200.0, 0.50, "Regime-Adaptive NY 1.1R + Lock"),
        ("S1090", "Regime-Adaptive (NY 1.2R Rapid 60%)", lambda: run_batch63_router(0.16, 0.08, 0.04, regime_mode=True, ny_mult=1.2, ny_ratio=0.60), 200.0, 0.0, "Regime-Adaptive NY 1.2R"),
        ("S1091", "Regime-Adaptive (NY 1.2R Rapid) + Lock", lambda: run_batch63_router(0.16, 0.08, 0.04, regime_mode=True, ny_mult=1.2, ny_ratio=0.60), 200.0, 0.50, "Regime-Adaptive NY 1.2R + Lock"),
        ("S1092", "Regime-Adaptive Balanced (0.14/0.07/0.05)", lambda: run_batch63_router(0.14, 0.07, 0.05, regime_mode=True, ny_mult=1.1, ny_ratio=0.70), 180.0, 0.0, "Regime-Adaptive Balanced"),
        ("S1093", "Regime-Adaptive Balanced + 50% Lock", lambda: run_batch63_router(0.14, 0.07, 0.05, regime_mode=True, ny_mult=1.1, ny_ratio=0.70), 180.0, 0.50, "Regime Balanced + Lock"),
        ("S1094", "Regime-Adaptive Sub-Risk (0.12/0.06/0.04)", lambda: run_batch63_router(0.12, 0.06, 0.04, regime_mode=True, ny_mult=1.1, ny_ratio=0.70), 160.0, 0.0, "Regime Sub-Risk Base"),
        ("S1095", "Regime-Adaptive Sub-Risk + 50% Lock", lambda: run_batch63_router(0.12, 0.06, 0.04, regime_mode=True, ny_mult=1.1, ny_ratio=0.70), 160.0, 0.50, "Regime Sub-Risk + Lock"),

        # Group 2: Prop-Firm Ultra-Floor Guardian Exploration (S1096 - S1105)
        ("S1096", "Prop-Firm Ultra-Floor (0.04/0.02/0.02)", lambda: run_batch63_router(0.04, 0.02, 0.02, regime_mode=True, ny_mult=1.0, ny_ratio=0.75), 80.0, 0.0, "Prop-Firm Ultra-Floor Base"),
        ("S1097", "Prop-Firm Ultra-Floor + 50% Lock", lambda: run_batch63_router(0.04, 0.02, 0.02, regime_mode=True, ny_mult=1.0, ny_ratio=0.75), 80.0, 0.50, "Prop-Firm Ultra-Floor + Lock"),
        ("S1098", "Prop-Firm Shield Plus (0.05/0.03/0.02)", lambda: run_batch63_router(0.05, 0.03, 0.02, regime_mode=True, ny_mult=1.0, ny_ratio=0.75), 90.0, 0.0, "Prop-Firm Shield Plus"),
        ("S1099", "Prop-Firm Shield Plus + 50% Lock", lambda: run_batch63_router(0.05, 0.03, 0.02, regime_mode=True, ny_mult=1.0, ny_ratio=0.75), 90.0, 0.50, "Prop-Firm Shield Plus + Lock"),
        ("S1100", "Prop-Firm Micro-Sprint (0.06/0.03/0.02)", lambda: run_batch63_router(0.06, 0.03, 0.02, regime_mode=True, ny_mult=1.1, ny_ratio=0.70), 100.0, 0.0, "Prop-Firm Micro-Sprint"),
        ("S1101", "Prop-Firm Micro-Sprint + 50% Lock", lambda: run_batch63_router(0.06, 0.03, 0.02, regime_mode=True, ny_mult=1.1, ny_ratio=0.70), 100.0, 0.50, "Prop-Firm Sprint + Lock"),
        ("S1102", "Prop-Firm Static Tri-Tranche (0.05/0.03)", lambda: run_batch63_router(0.05, 0.03, 0.03, regime_mode=False, t1_mult=1.2, t1_ratio=0.35, t2_mult=2.4, t2_ratio=0.35, ny_mult=1.0, ny_ratio=0.75), 100.0, 0.0, "Static Prop-Firm Tri-Tranche"),
        ("S1103", "Prop-Firm Static Tri-Tranche + Lock", lambda: run_batch63_router(0.05, 0.03, 0.03, regime_mode=False, t1_mult=1.2, t1_ratio=0.35, t2_mult=2.4, t2_ratio=0.35, ny_mult=1.0, ny_ratio=0.75), 100.0, 0.50, "Static Shield + Lock"),
        ("S1104", "Prop-Firm Precision Tight (T1: 1.1R)", lambda: run_batch63_router(0.05, 0.03, 0.03, regime_mode=False, t1_mult=1.1, t1_ratio=0.40, t2_mult=2.2, t2_ratio=0.30, ny_mult=1.0, ny_ratio=0.75), 100.0, 0.0, "Prop-Firm Precision Tight"),
        ("S1105", "Prop-Firm Precision Tight + 50% Lock", lambda: run_batch63_router(0.05, 0.03, 0.03, regime_mode=False, t1_mult=1.1, t1_ratio=0.40, t2_mult=2.2, t2_ratio=0.30, ny_mult=1.0, ny_ratio=0.75), 100.0, 0.50, "Precision Tight + Lock"),

        # Group 3: High-Expectancy Compounding Matrix (S1106 - S1115)
        ("S1106", "Regime Tri-Tranche Compounding 0.5%", lambda: run_batch63_router(0.10, 0.05, 0.05, comp_pct=0.5, regime_mode=True, ny_mult=1.1, ny_ratio=0.70), 140.0, 0.0, "Regime Comp 0.5% Shield"),
        ("S1107", "Regime Tri-Tranche Compounding 0.75%", lambda: run_batch63_router(0.10, 0.05, 0.05, comp_pct=0.75, regime_mode=True, ny_mult=1.1, ny_ratio=0.70), 150.0, 0.0, "Regime Comp 0.75% Apex"),
        ("S1108", "Regime Tri-Tranche Compounding 1.0%", lambda: run_batch63_router(0.10, 0.05, 0.05, comp_pct=1.0, regime_mode=True, ny_mult=1.1, ny_ratio=0.70), 180.0, 0.0, "Regime Comp 1.0% Engine"),
        ("S1109", "Regime Tri-Tranche Compounding 1.25%", lambda: run_batch63_router(0.10, 0.05, 0.05, comp_pct=1.25, regime_mode=True, ny_mult=1.1, ny_ratio=0.70), 190.0, 0.0, "Regime Comp 1.25% Titan"),
        ("S1110", "Regime Tri-Tranche Compounding 1.5%", lambda: run_batch63_router(0.10, 0.05, 0.05, comp_pct=1.5, regime_mode=True, ny_mult=1.1, ny_ratio=0.70), 200.0, 0.0, "Regime Comp 1.5% Maximum"),
        ("S1111", "Regime Tri-Tranche Comp 1.0% + 50% Lock", lambda: run_batch63_router(0.10, 0.05, 0.05, comp_pct=1.0, regime_mode=True, ny_mult=1.1, ny_ratio=0.70), 180.0, 0.50, "Regime Comp 1.0% Lock"),
        ("S1112", "Regime Tri-Tranche Comp 1.25% + 50% Lock", lambda: run_batch63_router(0.10, 0.05, 0.05, comp_pct=1.25, regime_mode=True, ny_mult=1.1, ny_ratio=0.70), 190.0, 0.50, "Regime Comp 1.25% Lock"),
        ("S1113", "Regime Tri-Tranche Comp 1.5% + 50% Lock", lambda: run_batch63_router(0.10, 0.05, 0.05, comp_pct=1.5, regime_mode=True, ny_mult=1.1, ny_ratio=0.70), 200.0, 0.50, "Regime Comp 1.5% Lock"),
        ("S1114", "Grand Asymmetric Regime Vault 2026", lambda: run_batch63_router(0.14, 0.07, 0.05, comp_pct=1.0, regime_mode=True, ny_mult=1.1, ny_ratio=0.70), 180.0, 0.50, "Grand Regime Vault 2026"),
        ("S1115", "Apex Sovereign Regime Paragon 2026", lambda: run_batch63_router(0.16, 0.08, 0.04, comp_pct=1.25, regime_mode=True, ny_mult=1.1, ny_ratio=0.70), 220.0, 0.50, "👑 Apex Sovereign Regime Paragon 2026")
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
    out_csv = os.path.join(RESULTS_DIR, "batch_63_regime_tranche_matrix.csv")
    out_json = os.path.join(RESULTS_DIR, "batch_63_regime_tranche_results.json")
    df_res = pd.DataFrame(results_table)
    df_res.to_csv(out_csv, index=False)
    with open(out_json, "w") as f:
        json.dump(results_table, f, indent=2)

    elapsed = time.time() - t0
    print(f"\n[+] Batch 63 Regime-Adaptive Tranche Execution Complete in {elapsed:.2f}s!")
    print(f"[+] Saved results matrix to {out_csv}")
    print(f"[+] Saved results JSON to {out_json}")

if __name__ == "__main__":
    main()
