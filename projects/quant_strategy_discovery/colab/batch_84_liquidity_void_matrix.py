"""
Batch 84: Multi-Timeframe High-Frequency Liquidity Void & Fair Value Gap (FVG) Midpoint Rebalance Matrix (S1716 - S1745)
=========================================================================================================================
CFD Quantitative Strategy Discovery Campaign
Asset: XAUUSD (Gold CFD) - 100% Self-Contained Architecture
Regulatory Framework: Strict Constitution V5.1 Compliant (Rules D.1 - D.7)
Compute Platform: Google Colab Cloud High-Performance Runtime
Project Mandate: Non-Stop Autonomous Loop (PF >= 1.50, DD < 10%, MCR >= 90%, 150-350+ Trades/Yr)

Core Hypotheses:
- Institutional order imbalance creates Fair Value Gaps (FVGs) and Liquidity Voids on M15 Gold.
- Price frequently returns to rebalance the 50% Consequent Encroachment (CE) midpoint of recent FVGs.
- When mitigation of the FVG midpoint aligns with M15 Supertrend (2.5, 14) + EMA200 and M5 EMA50 confirmation,
  combined with rejection wicks and swing liquidity sweeps, it yields elite Profit Factors (>= 2.30 - 2.60+),
  tight intra-bar drawdowns (< 2.0%), and >= 90% monthly consistency.
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
    multiplier = 2.0 / (period + 1.0)
    for i in range(period, n):
        ema[i] = (closes[i] * multiplier) + (ema[i - 1] * (1.0 - multiplier))
    return ema

def compute_supertrend(highs, lows, closes, atr, multiplier=2.5):
    n = len(closes)
    trend = np.ones(n, dtype=np.int32)
    upper_band = np.zeros(n, dtype=np.float64)
    lower_band = np.zeros(n, dtype=np.float64)

    basic_upper = ((highs + lows) / 2.0) + (multiplier * atr)
    basic_lower = ((highs + lows) / 2.0) - (multiplier * atr)

    upper_band[0] = basic_upper[0]
    lower_band[0] = basic_lower[0]

    for i in range(1, n):
        if basic_lower[i] > lower_band[i - 1] or closes[i - 1] < lower_band[i - 1]:
            lower_band[i] = basic_lower[i]
        else:
            lower_band[i] = lower_band[i - 1]

        if basic_upper[i] < upper_band[i - 1] or closes[i - 1] > upper_band[i - 1]:
            upper_band[i] = basic_upper[i]
        else:
            upper_band[i] = upper_band[i - 1]

        if trend[i - 1] == 1:
            if closes[i] < lower_band[i]:
                trend[i] = -1
            else:
                trend[i] = 1
        else:
            if closes[i] > upper_band[i]:
                trend[i] = 1
            else:
                trend[i] = -1

    return trend, lower_band if trend[-1] == 1 else upper_band

# -----------------------------------------------------------------------------
# Discrete Event Simulation Engine (Strict Constitution V5.1 Rules D.1 - D.7)
# -----------------------------------------------------------------------------
def simulate_fvg_engine(
    opens, highs, lows, closes, dates,
    entry_signals, atr_values, vol_ratios,
    supertrend_bands_macro,
    session_label,
    spread=0.25,
    commission_per_lot=6.0,
    point_value=100.0,
    lot_size=0.10,
    compounding_risk_pct=0.0,
    initial_sl_atr_mult=1.10,
    regime_mode=True,
    t1_def_mult=1.40,
    t1_def_ratio=0.50,
    t2_def_mult=2.80,
    t2_def_ratio=0.50,
    ny_rapid_mult=0.0,
    ny_rapid_ratio=0.0,
    accelerate_ratchet=True
):
    n = len(closes)
    trades = []

    pos = 0
    entry_price = 0.0
    current_sl = 0.0
    tp1_target = 0.0
    tp2_target = 0.0
    active_lot = lot_size
    curr_unit = active_lot * point_value
    entry_time = None
    deepest_dip = 0.0
    tranche1_taken = False
    tranche2_taken = False
    current_equity = 10000.0

    fixed_slippage = 0.10

    for i in range(n - 1):
        if pos != 0:
            h = highs[i]
            l = lows[i]
            c = closes[i]
            current_bar_time = dates[i]

            adverse_excursion = (l - entry_price) * curr_unit if pos == 1 else (entry_price - h) * curr_unit
            if adverse_excursion < deepest_dip:
                deepest_dip = adverse_excursion

            exit_now = False
            exit_price = 0.0
            exit_reason = ""
            raw_pnl = 0.0

            # Rule D.1: Pessimistic Collision Sequence
            if pos == 1:
                sl_hit = (l <= current_sl)
                tp1_hit = (not tranche1_taken and tp1_target > 0.0 and h >= tp1_target)
                tp2_hit = (tp2_target > 0.0 and h >= tp2_target)

                if sl_hit and (tp1_hit or tp2_hit):
                    exit_now = True
                    exit_price = current_sl - fixed_slippage
                    exit_reason = "SL_Pessimistic_Collision"
                elif sl_hit:
                    exit_now = True
                    exit_price = current_sl - fixed_slippage
                    exit_reason = "SL_Hit"
                else:
                    if tp1_hit:
                        tranche1_taken = True
                        t1_lot = round(active_lot * (ny_rapid_ratio if ny_rapid_mult > 0.0 else t1_def_ratio), 2)
                        t1_pnl = (tp1_target - entry_price) * (t1_lot * point_value)
                        raw_pnl += t1_pnl
                        active_lot = round(active_lot - t1_lot, 2)
                        curr_unit = active_lot * point_value
                        if accelerate_ratchet:
                            current_sl = max(current_sl, entry_price + 0.20)

                    if tp2_hit:
                        tranche2_taken = True
                        t2_lot = active_lot
                        t2_pnl = (tp2_target - entry_price) * (t2_lot * point_value)
                        raw_pnl += t2_pnl
                        exit_now = True
                        exit_price = tp2_target
                        exit_reason = "TP2_Hit"

            else: # Short
                sl_hit = (h >= current_sl)
                tp1_hit = (not tranche1_taken and tp1_target > 0.0 and l <= tp1_target)
                tp2_hit = (tp2_target > 0.0 and l <= tp2_target)

                if sl_hit and (tp1_hit or tp2_hit):
                    exit_now = True
                    exit_price = current_sl + fixed_slippage
                    exit_reason = "SL_Pessimistic_Collision"
                elif sl_hit:
                    exit_now = True
                    exit_price = current_sl + fixed_slippage
                    exit_reason = "SL_Hit"
                else:
                    if tp1_hit:
                        tranche1_taken = True
                        t1_lot = round(active_lot * (ny_rapid_ratio if ny_rapid_mult > 0.0 else t1_def_ratio), 2)
                        t1_pnl = (entry_price - tp1_target) * (t1_lot * point_value)
                        raw_pnl += t1_pnl
                        active_lot = round(active_lot - t1_lot, 2)
                        curr_unit = active_lot * point_value
                        if accelerate_ratchet:
                            current_sl = min(current_sl, entry_price - 0.20)

                    if tp2_hit:
                        tranche2_taken = True
                        t2_lot = active_lot
                        t2_pnl = (entry_price - tp2_target) * (t2_lot * point_value)
                        raw_pnl += t2_pnl
                        exit_now = True
                        exit_price = tp2_target
                        exit_reason = "TP2_Hit"

            # Rule D.2: Strict Bar-Close Trailing Ratchet
            if not exit_now:
                if accelerate_ratchet:
                    r_dist = atr_values[i] * 1.0
                    if pos == 1 and c >= (entry_price + r_dist):
                        current_sl = max(current_sl, entry_price + 0.20)
                    elif pos == -1 and c <= (entry_price - r_dist):
                        current_sl = min(current_sl, entry_price - 0.20)

                st_band = supertrend_bands_macro[i]
                if pos == 1 and st_band > 0.0:
                    current_sl = max(current_sl, st_band)
                elif pos == -1 and st_band > 0.0:
                    current_sl = min(current_sl, st_band)

            if exit_now:
                if exit_reason in ("SL_Hit", "SL_Pessimistic_Collision"):
                    rem_pnl = (exit_price - entry_price) * curr_unit if pos == 1 else (entry_price - exit_price) * curr_unit
                    total_pnl = raw_pnl + rem_pnl
                else:
                    total_pnl = raw_pnl

                initial_trade_lot = (lot_size if compounding_risk_pct == 0.0 else active_lot)
                comm_cost = initial_trade_lot * commission_per_lot
                spread_cost = initial_trade_lot * point_value * spread

                holding_days = max(0, (current_bar_time.date() - entry_time.date()).days)
                swap_cost = holding_days * 18.0 * initial_trade_lot if (pos == 1 and holding_days > 0) else 0.0

                net_trade_pnl = total_pnl - comm_cost - spread_cost - swap_cost
                current_equity += net_trade_pnl

                trades.append({
                    "entry_time": entry_time,
                    "exit_time": current_bar_time,
                    "pos": pos,
                    "entry_price": entry_price,
                    "exit_price": exit_price,
                    "net_pnl": round(net_trade_pnl, 2),
                    "exit_reason": exit_reason,
                    "deepest_dip": round(deepest_dip, 2),
                    "holding_bars": (current_bar_time - entry_time).total_seconds() / 900.0,
                    "session": session_label
                })

                pos = 0
                entry_price = 0.0
                current_sl = 0.0
                tp1_target = 0.0
                tp2_target = 0.0
                deepest_dip = 0.0
                tranche1_taken = False
                tranche2_taken = False

        # Entry Processing
        if pos == 0 and entry_signals[i] != 0:
            sig = entry_signals[i]
            cur_atr = atr_values[i]
            if cur_atr <= 0.05:
                continue

            entry_price = opens[i + 1]
            entry_time = dates[i + 1]
            pos = sig

            if compounding_risk_pct > 0.0:
                risk_usd = current_equity * (compounding_risk_pct / 100.0)
                sl_pt_est = initial_sl_atr_mult * cur_atr
                calc_lot = max(0.01, min(5.0, round(risk_usd / (sl_pt_est * point_value), 2)))
                active_lot = calc_lot
            else:
                active_lot = lot_size

            curr_unit = active_lot * point_value
            sl_dist = initial_sl_atr_mult * cur_atr

            if ny_rapid_mult > 0.0 and session_label == "NY_Open":
                tp1_dist = ny_rapid_mult * cur_atr
            else:
                tp1_dist = t1_def_mult * cur_atr

            tp2_dist = t2_def_mult * cur_atr

            if pos == 1:
                current_sl = entry_price - sl_dist
                tp1_target = entry_price + tp1_dist
                tp2_target = entry_price + tp2_dist
            else:
                current_sl = entry_price + sl_dist
                tp1_target = entry_price - tp1_dist
                tp2_target = entry_price - tp2_dist

            deepest_dip = 0.0
            tranche1_taken = False
            tranche2_taken = False

    return trades

# -----------------------------------------------------------------------------
# Portfolio Analysis & Constitution Guardrails
# -----------------------------------------------------------------------------
def analyze_portfolio(
    trades, initial_capital=10000.0,
    daily_hard_stop=150.0, daily_trail_lock_ratio=0.50,
    monthly_target_lock=0.0, monthly_lock_ratio=0.75
):
    if not trades:
        return {
            "Net_Profit_USD": 0.0, "Profit_Factor": 0.0, "Total_Trades": 0, "Annual_Trades": 0.0,
            "Max_Intra_DD_USD": 0.0, "Max_DD_Pct": 0.0, "RoMaD": 0.0, "Win_Rate_Pct": 0.0,
            "MCR_Pct": 0.0, "Avg_Trade_USD": 0.0, "MC_P50_DD": 0.0, "MC_P95_DD": 0.0, "Ruin_Prob_Pct": 0.0
        }

    sorted_trades = sorted(trades, key=lambda x: x["exit_time"])

    daily_pnl = {}
    monthly_pnl = {}
    cur_day = None
    cur_day_pnl = 0.0
    day_peak = 0.0

    cur_mon = None
    cur_mon_pnl = 0.0
    mon_peak = 0.0

    filtered_trades = []

    for tr in sorted_trades:
        exit_dt = tr["exit_time"]
        d = exit_dt.date()
        m = (exit_dt.year, exit_dt.month)

        if d != cur_day:
            cur_day = d
            cur_day_pnl = 0.0
            day_peak = 0.0

        if m != cur_mon:
            cur_mon = m
            cur_mon_pnl = 0.0
            mon_peak = 0.0

        # Daily loss circuit breaker
        if daily_hard_stop > 0.0 and cur_day_pnl <= -daily_hard_stop:
            continue

        # Daily trailing profit lock
        if daily_trail_lock_ratio > 0.0 and day_peak >= 40.0:
            giveback_limit = day_peak * (1.0 - daily_trail_lock_ratio)
            if cur_day_pnl <= day_peak - giveback_limit:
                continue

        # Monthly profit lock
        if monthly_target_lock > 0.0 and mon_peak >= monthly_target_lock:
            mon_giveback = mon_peak * (1.0 - monthly_lock_ratio)
            if cur_mon_pnl <= mon_peak - mon_giveback:
                continue

        filtered_trades.append(tr)
        pnl = tr["net_pnl"]
        cur_day_pnl += pnl
        cur_mon_pnl += pnl

        if cur_day_pnl > day_peak:
            day_peak = cur_day_pnl
        if cur_mon_pnl > mon_peak:
            mon_peak = cur_mon_pnl

        daily_pnl[d] = daily_pnl.get(d, 0.0) + pnl
        monthly_pnl[m] = monthly_pnl.get(m, 0.0) + pnl

    if not filtered_trades:
        return {
            "Net_Profit_USD": 0.0, "Profit_Factor": 0.0, "Total_Trades": 0, "Annual_Trades": 0.0,
            "Max_Intra_DD_USD": 0.0, "Max_DD_Pct": 0.0, "RoMaD": 0.0, "Win_Rate_Pct": 0.0,
            "MCR_Pct": 0.0, "Avg_Trade_USD": 0.0, "MC_P50_DD": 0.0, "MC_P95_DD": 0.0, "Ruin_Prob_Pct": 0.0
        }

    pnls = np.array([t["net_pnl"] for t in filtered_trades])
    gross_win = np.sum(pnls[pnls > 0])
    gross_loss = abs(np.sum(pnls[pnls < 0]))
    net_pnl = gross_win - gross_loss
    pf = (gross_win / gross_loss) if gross_loss > 0 else 999.0
    wr = (len(pnls[pnls > 0]) / len(pnls)) * 100.0
    tot_trades = len(filtered_trades)

    # Multi-Year Horizon Span
    start_d = sorted_trades[0]["entry_time"]
    end_d = sorted_trades[-1]["exit_time"]
    span_years = max(1.0, (end_d - start_d).total_seconds() / (365.25 * 86400))
    ann_trades = tot_trades / span_years

    # True Intra-Bar Adverse Excursion Drawdown
    equity = initial_capital
    peak_equity = initial_capital
    max_intra_dd = 0.0

    for tr in filtered_trades:
        intra_low = equity + tr["deepest_dip"]
        if peak_equity - intra_low > max_intra_dd:
            max_intra_dd = peak_equity - intra_low
        equity += tr["net_pnl"]
        if equity > peak_equity:
            peak_equity = equity

    max_dd_pct = (max_intra_dd / initial_capital) * 100.0
    romad = (net_pnl / max_intra_dd) if max_intra_dd > 0 else 0.0

    # Monthly Consistency Ratio (MCR)
    total_months = len(monthly_pnl)
    win_months = sum(1 for v in monthly_pnl.values() if v > 0)
    mcr = (win_months / total_months * 100.0) if total_months > 0 else 0.0

    # Monte Carlo Permutations (1,000 runs)
    mc_dds = []
    ruin_count = 0
    rng = np.random.default_rng(42)
    for _ in range(1000):
        shuffled = rng.permutation(pnls)
        sim_eq = initial_capital
        sim_peak = initial_capital
        sim_max_dd = 0.0
        for p in shuffled:
            sim_eq += p
            if sim_eq > sim_peak:
                sim_peak = sim_eq
            dd = sim_peak - sim_eq
            if dd > sim_max_dd:
                sim_max_dd = dd
            if sim_eq <= initial_capital * 0.70: # 30% loss is ruin
                ruin_count += 1
                break
        mc_dds.append(sim_max_dd)

    mc_p50 = float(np.percentile(mc_dds, 50))
    mc_p95 = float(np.percentile(mc_dds, 95))
    ruin_prob = (ruin_count / 1000.0) * 100.0

    return {
        "Net_Profit_USD": round(net_pnl, 2),
        "Profit_Factor": round(pf, 3),
        "Total_Trades": tot_trades,
        "Annual_Trades": round(ann_trades, 1),
        "Max_Intra_DD_USD": round(max_intra_dd, 2),
        "Max_DD_Pct": round(max_dd_pct, 2),
        "RoMaD": round(romad, 2),
        "Win_Rate_Pct": round(wr, 1),
        "MCR_Pct": round(mcr, 1),
        "Avg_Trade_USD": round(net_pnl / tot_trades, 2),
        "MC_P50_DD": round(mc_p50, 2),
        "MC_P95_DD": round(mc_p95, 2),
        "Ruin_Prob_Pct": round(ruin_prob, 2)
    }

# -----------------------------------------------------------------------------
# Main Execution Pipeline
# -----------------------------------------------------------------------------
def run_batch_84():
    print("=" * 80)
    print("Starting Batch 84: Liquidity Void & FVG Midpoint Rebalance Matrix (S1716 - S1745)")
    print("Execution Target: Google Colab Cloud High-Performance Runtime")
    print("Asset: XAUUSD (Gold CFD) | Strict Constitution V5.1 Compliance")
    print("=" * 80)

    start_time = time.time()

    DATA_DIR = "/root/CFD-Trading-ML/projects/quant_strategy_discovery/data"
    if not os.path.exists(DATA_DIR):
        DATA_DIR = "/content/CFD-Trading-ML/projects/quant_strategy_discovery/data"

    m15_path = os.path.join(DATA_DIR, "XAUUSD_M15.parquet")
    m5_path  = os.path.join(DATA_DIR, "XAUUSD_M5.parquet")

    if not os.path.exists(m15_path) or not os.path.exists(m5_path):
        raise FileNotFoundError(f"Missing parquet data files: {m15_path} or {m5_path}")

    print(f"[*] Loading M15 and M5 Parquet data...")
    df_m15 = pd.read_parquet(m15_path)
    df_m5  = pd.read_parquet(m5_path)

    df_m15.sort_index(inplace=True)
    df_m5.sort_index(inplace=True)

    print(f"[+] Loaded {len(df_m15):,} M15 bars and {len(df_m5):,} M5 bars.")

    # Reconstruct true volume
    if 'tick_volume' in df_m5.columns:
        m15_vol_reconstructed = df_m5['tick_volume'].resample('15min').sum().reindex(df_m15.index).ffill().fillna(0).values
    else:
        m15_vol_reconstructed = np.ones(len(df_m15), dtype=np.float64)

    m15_opens  = df_m15['open'].values.astype(np.float64)
    m15_highs  = df_m15['high'].values.astype(np.float64)
    m15_lows   = df_m15['low'].values.astype(np.float64)
    m15_closes = df_m15['close'].values.astype(np.float64)
    m15_dates  = pd.to_datetime(df_m15.index)

    m5_closes = df_m5['close'].values.astype(np.float64)

    n_m15 = len(m15_closes)

    print("[*] Computing indicators across 6 multi-year regimes...")
    m15_atr14  = compute_atr(m15_highs, m15_lows, m15_closes, 14)
    m15_atr100 = compute_atr(m15_highs, m15_lows, m15_closes, 100)
    m15_vol_ratio = np.where(m15_atr100 > 0, m15_atr14 / m15_atr100, 1.0)

    st_m15_trend, st_m15_band = compute_supertrend(m15_highs, m15_lows, m15_closes, m15_atr14, multiplier=2.5)

    m15_ema21  = compute_ema(m15_closes, 21)
    m15_ema200 = compute_ema(m15_closes, 200)

    ranges = m15_highs - m15_lows
    ranges_safe = np.where(ranges > 0, ranges, 1e-4)
    lower_wicks = np.minimum(m15_opens, m15_closes) - m15_lows
    upper_wicks = m15_highs - np.maximum(m15_opens, m15_closes)
    bodies = np.abs(m15_closes - m15_opens)

    # -------------------------------------------------------------------------
    # Liquidity Void & Fair Value Gap (FVG) Detection
    # -------------------------------------------------------------------------
    # Bullish FVG: Low[i] > High[i-2], with void size >= 0.30 ATR
    # Bearish FVG: High[i] < Low[i-2], with void size >= 0.30 ATR
    fvg_bull_top = np.zeros(n_m15, dtype=np.float64)
    fvg_bull_bot = np.zeros(n_m15, dtype=np.float64)
    fvg_bull_mid = np.zeros(n_m15, dtype=np.float64)
    is_bull_fvg  = np.zeros(n_m15, dtype=bool)

    fvg_bear_top = np.zeros(n_m15, dtype=np.float64)
    fvg_bear_bot = np.zeros(n_m15, dtype=np.float64)
    fvg_bear_mid = np.zeros(n_m15, dtype=np.float64)
    is_bear_fvg  = np.zeros(n_m15, dtype=bool)

    for i in range(2, n_m15):
        # Bull FVG
        if m15_lows[i] > m15_highs[i - 2]:
            void_sz = m15_lows[i] - m15_highs[i - 2]
            if void_sz >= 0.30 * m15_atr14[i]:
                is_bull_fvg[i] = True
                fvg_bull_top[i] = m15_lows[i]
                fvg_bull_bot[i] = m15_highs[i - 2]
                fvg_bull_mid[i] = 0.5 * (fvg_bull_top[i] + fvg_bull_bot[i])

        # Bear FVG
        if m15_highs[i] < m15_lows[i - 2]:
            void_sz = m15_lows[i - 2] - m15_highs[i]
            if void_sz >= 0.30 * m15_atr14[i]:
                is_bear_fvg[i] = True
                fvg_bear_top[i] = m15_lows[i - 2]
                fvg_bear_bot[i] = m15_highs[i]
                fvg_bear_mid[i] = 0.5 * (fvg_bear_top[i] + fvg_bear_bot[i])

    # Dynamic Liquidity Sweep (10 bars)
    recent_sh = np.zeros(n_m15, dtype=np.float64)
    recent_sl = np.zeros(n_m15, dtype=np.float64)
    for i in range(10, n_m15):
        recent_sh[i] = np.max(m15_highs[i - 10:i])
        recent_sl[i] = np.min(m15_lows[i - 10:i])

    sweep_bull = np.zeros(n_m15, dtype=bool)
    sweep_bear = np.zeros(n_m15, dtype=bool)
    for i in range(10, n_m15):
        if m15_lows[i] < recent_sl[i] and (m15_closes[i] >= recent_sl[i] or lower_wicks[i] / ranges_safe[i] >= 0.38):
            sweep_bull[i] = True
        if m15_highs[i] > recent_sh[i] and (m15_closes[i] <= recent_sh[i] or upper_wicks[i] / ranges_safe[i] >= 0.38):
            sweep_bear[i] = True

    # M5 Micro-Structure Alignment
    m5_ema50 = compute_ema(m5_closes, 50)
    m5_tr = np.where(m5_closes > m5_ema50, 1, -1)
    df_m5_state = pd.DataFrame({
        "time": pd.to_datetime(df_m5.index) + pd.Timedelta(minutes=5),
        "m5_tr": m5_tr
    }).sort_values("time")

    df_m15_time = pd.DataFrame({"time": pd.to_datetime(df_m15.index)})
    m15_merged_m5 = pd.merge_asof(df_m15_time, df_m5_state, on="time", direction="backward")
    m15_m5_tr = m15_merged_m5["m5_tr"].fillna(1).values.astype(np.int32)

    del df_m5, df_m5_state, df_m15_time, m15_merged_m5
    gc.collect()

    print(f"[+] Synchronized {n_m15:,} Gold bars with FVG Midpoint Rebalance & Sweep Engine.")

    # Signal Generator Function
    def generate_fvg_signals(
        start_h, end_h,
        min_atr=1.30, min_vr=0.95,
        lookback=5,
        min_wick=0.45
    ):
        sig = np.zeros(n_m15, dtype=np.int32)
        cooldown = 0
        for i in range(200, n_m15 - 1):
            if cooldown > 0:
                cooldown -= 1
                continue

            h = m15_dates[i].hour
            if start_h <= h <= end_h:
                if m15_atr14[i] < min_atr or m15_vol_ratio[i] < min_vr:
                    continue

                macro_bull = (st_m15_trend[i] == 1) and (m15_closes[i] > m15_ema200[i]) and (m15_m5_tr[i] == 1)
                macro_bear = (st_m15_trend[i] == -1) and (m15_closes[i] < m15_ema200[i]) and (m15_m5_tr[i] == -1)

                # Check recent Bullish FVG mitigation within lookback
                mitigate_bull_ce = False
                for b in range(max(2, i - lookback), i):
                    if is_bull_fvg[b]:
                        # Price mitigates into void and touches CE midpoint or bottom
                        if m15_lows[i] <= fvg_bull_mid[b] + 0.25 * m15_atr14[i] and m15_closes[i] >= fvg_bull_bot[b]:
                            mitigate_bull_ce = True
                            break

                # Check recent Bearish FVG mitigation within lookback
                mitigate_bear_ce = False
                for b in range(max(2, i - lookback), i):
                    if is_bear_fvg[b]:
                        if m15_highs[i] >= fvg_bear_mid[b] - 0.25 * m15_atr14[i] and m15_closes[i] <= fvg_bear_top[b]:
                            mitigate_bear_ce = True
                            break

                # Rejection wick or dynamic EMA21 bounce
                bull_wick = (lower_wicks[i] / ranges_safe[i] >= min_wick)
                bear_wick = (upper_wicks[i] / ranges_safe[i] >= min_wick)

                retest_ema_bull = (m15_lows[i] <= m15_ema21[i] + 0.35 * m15_atr14[i]) and (m15_closes[i] >= m15_ema21[i])
                retest_ema_bear = (m15_highs[i] >= m15_ema21[i] - 0.35 * m15_atr14[i]) and (m15_closes[i] <= m15_ema21[i])

                if macro_bull and (mitigate_bull_ce or sweep_bull[i]) and (bull_wick or retest_ema_bull):
                    sig[i] = 1
                    cooldown = 2
                elif macro_bear and (mitigate_bear_ce or sweep_bear[i]) and (bear_wick or retest_ema_bear):
                    sig[i] = -1
                    cooldown = 2

        return sig

    # Signal Configurations
    sig_early_fvg = generate_fvg_signals(6, 9, 1.30, 0.95, lookback=5, min_wick=0.45)
    sig_mid_fvg   = generate_fvg_signals(9, 12, 1.30, 0.95, lookback=5, min_wick=0.45)
    sig_ny_fvg    = generate_fvg_signals(12, 16, 1.40, 1.00, lookback=5, min_wick=0.45)

    sig_early_loose = generate_fvg_signals(6, 9, 1.20, 0.90, lookback=6, min_wick=0.40)
    sig_mid_loose   = generate_fvg_signals(9, 12, 1.20, 0.90, lookback=6, min_wick=0.40)
    sig_ny_loose    = generate_fvg_signals(12, 16, 1.30, 0.95, lookback=6, min_wick=0.40)

    def run_fvg_router(
        sig_early, sig_mid, sig_ny,
        w_early=0.08, w_mid=0.04, w_ny=0.03,
        comp_pct=0.0,
        t1_mult=1.40, t1_ratio=0.50,
        t2_mult=2.80, t2_ratio=0.50,
        ny_mult=1.20, ny_ratio=0.70,
        accel_ratchet=True
    ):
        t1 = simulate_fvg_engine(
            m15_opens, m15_highs, m15_lows, m15_closes, m15_dates, sig_early, m15_atr14, m15_vol_ratio, st_m15_band,
            "Early_London", point_value=100.0, lot_size=w_early, compounding_risk_pct=comp_pct*0.5 if comp_pct>0 else 0.0,
            regime_mode=True, t1_def_mult=t1_mult, t1_def_ratio=t1_ratio, t2_def_mult=t2_mult, t2_def_ratio=t2_ratio,
            accelerate_ratchet=accel_ratchet
        )
        t2 = simulate_fvg_engine(
            m15_opens, m15_highs, m15_lows, m15_closes, m15_dates, sig_mid, m15_atr14, m15_vol_ratio, st_m15_band,
            "London_Mid", point_value=100.0, lot_size=w_mid, compounding_risk_pct=comp_pct*0.25 if comp_pct>0 else 0.0,
            regime_mode=True, t1_def_mult=t1_mult, t1_def_ratio=t1_ratio, t2_def_mult=t2_mult, t2_def_ratio=t2_ratio,
            accelerate_ratchet=accel_ratchet
        )
        t3 = simulate_fvg_engine(
            m15_opens, m15_highs, m15_lows, m15_closes, m15_dates, sig_ny, m15_atr14, m15_vol_ratio, st_m15_band,
            "NY_Open", point_value=100.0, lot_size=w_ny, compounding_risk_pct=comp_pct*0.35 if comp_pct>0 else 0.0,
            regime_mode=True, t1_def_mult=t1_mult, t1_def_ratio=t1_ratio, t2_def_mult=t2_mult, t2_def_ratio=t2_ratio,
            ny_rapid_mult=ny_mult, ny_rapid_ratio=ny_ratio, accelerate_ratchet=accel_ratchet
        )
        return t1 + t2 + t3

    # Define 30 Production Strategies (S1716 - S1745)
    strategy_definitions = [
        # Group 1: Liquidity Void Apex Matrix (S1716 - S1725)
        ("S1716", "Liquidity Void Base (0.08/0.04/0.03)", lambda: run_fvg_router(sig_early_fvg, sig_mid_fvg, sig_ny_fvg, 0.08, 0.04, 0.03), 150.0, 0.0, 0.0, 0.0, "Void Base"),
        ("S1717", "Liquidity Void Base + 50% Daily Lock", lambda: run_fvg_router(sig_early_fvg, sig_mid_fvg, sig_ny_fvg, 0.08, 0.04, 0.03), 150.0, 0.50, 0.0, 0.0, "Void + 50% Lock"),
        ("S1718", "Void Balanced (0.06/0.03/0.02)", lambda: run_fvg_router(sig_early_fvg, sig_mid_fvg, sig_ny_fvg, 0.06, 0.03, 0.02), 120.0, 0.0, 0.0, 0.0, "Void Balanced"),
        ("S1719", "Void Balanced + 50% Daily Lock", lambda: run_fvg_router(sig_early_fvg, sig_mid_fvg, sig_ny_fvg, 0.06, 0.03, 0.02), 120.0, 0.50, 0.0, 0.0, "Balanced + Lock"),
        ("S1720", "Extended Void Base (0.08/0.04/0.03)", lambda: run_fvg_router(sig_early_loose, sig_mid_loose, sig_ny_loose, 0.08, 0.04, 0.03), 160.0, 0.0, 0.0, 0.0, "Ext Void Base"),
        ("S1721", "Extended Void + 50% Daily Lock", lambda: run_fvg_router(sig_early_loose, sig_mid_loose, sig_ny_loose, 0.08, 0.04, 0.03), 160.0, 0.50, 0.0, 0.0, "Ext + Lock"),
        ("S1722", "Monthly Target-Lock $100 / 75%", lambda: run_fvg_router(sig_early_fvg, sig_mid_fvg, sig_ny_fvg, 0.08, 0.04, 0.03), 150.0, 0.50, 100.0, 0.75, "Monthly Lock $100"),
        ("S1723", "Monthly Target-Lock $120 / 75%", lambda: run_fvg_router(sig_early_fvg, sig_mid_fvg, sig_ny_fvg, 0.08, 0.04, 0.03), 150.0, 0.50, 120.0, 0.75, "Monthly Lock $120"),
        ("S1724", "Extended Monthly Lock $100", lambda: run_fvg_router(sig_early_loose, sig_mid_loose, sig_ny_loose, 0.06, 0.03, 0.02), 120.0, 0.50, 100.0, 0.75, "Ext Monthly Lock $100"),
        ("S1725", "Grand Void Sovereign 2026", lambda: run_fvg_router(sig_early_fvg, sig_mid_fvg, sig_ny_fvg, 0.08, 0.04, 0.03), 150.0, 0.50, 150.0, 0.75, "Grand Sovereign"),

        # Group 2: Sub-5% Prop-Firm Liquidity Void Shield Matrix (S1726 - S1735)
        ("S1726", "Prop-Firm Micro Void (0.03/0.02/0.01)", lambda: run_fvg_router(sig_early_fvg, sig_mid_fvg, sig_ny_fvg, 0.03, 0.02, 0.01), 60.0, 0.0, 0.0, 0.0, "Prop Micro Base"),
        ("S1727", "Prop-Firm Micro Void + 50% Lock", lambda: run_fvg_router(sig_early_fvg, sig_mid_fvg, sig_ny_fvg, 0.03, 0.02, 0.01), 60.0, 0.50, 0.0, 0.0, "Prop Micro + Lock"),
        ("S1728", "Prop-Firm Sub-3% Shield (0.04/0.02/0.01)", lambda: run_fvg_router(sig_early_fvg, sig_mid_fvg, sig_ny_fvg, 0.04, 0.02, 0.01), 75.0, 0.0, 0.0, 0.0, "Prop Sub-3% Base"),
        ("S1729", "Prop-Firm Sub-3% Shield + 50% Lock", lambda: run_fvg_router(sig_early_fvg, sig_mid_fvg, sig_ny_fvg, 0.04, 0.02, 0.01), 75.0, 0.50, 0.0, 0.0, "Prop Sub-3% + Lock"),
        ("S1730", "Prop-Firm Sub-5% Shield (0.05/0.025/0.02)", lambda: run_fvg_router(sig_early_fvg, sig_mid_fvg, sig_ny_fvg, 0.05, 0.025, 0.02), 90.0, 0.0, 0.0, 0.0, "Prop Sub-5% Base"),
        ("S1731", "Prop-Firm Sub-5% Shield + 50% Lock", lambda: run_fvg_router(sig_early_fvg, sig_mid_fvg, sig_ny_fvg, 0.05, 0.025, 0.02), 90.0, 0.50, 0.0, 0.0, "Prop Sub-5% + Lock"),
        ("S1732", "Prop-Firm Extended Sub-3% Shield", lambda: run_fvg_router(sig_early_loose, sig_mid_loose, sig_ny_loose, 0.04, 0.02, 0.01), 75.0, 0.50, 0.0, 0.0, "Prop Ext Sub-3%"),
        ("S1733", "Prop-Firm Extended Sub-5% Shield", lambda: run_fvg_router(sig_early_loose, sig_mid_loose, sig_ny_loose, 0.05, 0.025, 0.02), 90.0, 0.50, 0.0, 0.0, "Prop Ext Sub-5%"),
        ("S1734", "Prop-Firm Void Monthly Lock $60", lambda: run_fvg_router(sig_early_fvg, sig_mid_fvg, sig_ny_fvg, 0.04, 0.02, 0.01), 75.0, 0.50, 60.0, 0.80, "Prop Monthly $60"),
        ("S1735", "Prop-Firm Void Monthly Lock $80", lambda: run_fvg_router(sig_early_fvg, sig_mid_fvg, sig_ny_fvg, 0.05, 0.025, 0.02), 90.0, 0.50, 80.0, 0.80, "Prop Monthly $80"),

        # Group 3: Micro-Compounding FVG Kinetic Matrix (S1736 - S1745)
        ("S1736", "Compounding Void 0.50% Risk", lambda: run_fvg_router(sig_early_fvg, sig_mid_fvg, sig_ny_fvg, 0.06, 0.03, 0.02, comp_pct=0.50), 120.0, 0.0, 0.0, 0.0, "Comp 0.50% Base"),
        ("S1737", "Compounding Void 0.75% Risk", lambda: run_fvg_router(sig_early_fvg, sig_mid_fvg, sig_ny_fvg, 0.06, 0.03, 0.02, comp_pct=0.75), 140.0, 0.0, 0.0, 0.0, "Comp 0.75% Base"),
        ("S1738", "Compounding Void 1.00% Risk", lambda: run_fvg_router(sig_early_fvg, sig_mid_fvg, sig_ny_fvg, 0.06, 0.03, 0.02, comp_pct=1.00), 160.0, 0.0, 0.0, 0.0, "Comp 1.00% Base"),
        ("S1739", "Compounding Void 1.25% Risk", lambda: run_fvg_router(sig_early_fvg, sig_mid_fvg, sig_ny_fvg, 0.06, 0.03, 0.02, comp_pct=1.25), 180.0, 0.0, 0.0, 0.0, "Comp 1.25% Base"),
        ("S1740", "Compounding Void 1.50% Risk", lambda: run_fvg_router(sig_early_fvg, sig_mid_fvg, sig_ny_fvg, 0.06, 0.03, 0.02, comp_pct=1.50), 200.0, 0.0, 0.0, 0.0, "Comp 1.50% Base"),
        ("S1741", "Comp 0.75% + 50% Daily Lock", lambda: run_fvg_router(sig_early_fvg, sig_mid_fvg, sig_ny_fvg, 0.06, 0.03, 0.02, comp_pct=0.75), 140.0, 0.50, 0.0, 0.0, "Comp 0.75% + Daily Lock"),
        ("S1742", "Comp 1.00% + 50% Daily Lock", lambda: run_fvg_router(sig_early_fvg, sig_mid_fvg, sig_ny_fvg, 0.06, 0.03, 0.02, comp_pct=1.00), 160.0, 0.50, 0.0, 0.0, "Comp 1.00% + Daily Lock"),
        ("S1743", "Comp 0.75% + Monthly Lock $100", lambda: run_fvg_router(sig_early_fvg, sig_mid_fvg, sig_ny_fvg, 0.06, 0.03, 0.02, comp_pct=0.75), 140.0, 0.50, 100.0, 0.75, "Comp 0.75% Monthly Lock"),
        ("S1744", "Comp 1.00% + Monthly Lock $120", lambda: run_fvg_router(sig_early_fvg, sig_mid_fvg, sig_ny_fvg, 0.06, 0.03, 0.02, comp_pct=1.00), 160.0, 0.50, 120.0, 0.75, "Comp 1.00% Monthly Lock"),
        ("S1745", "Apex Sovereign Void Paragon 2026", lambda: run_fvg_router(sig_early_loose, sig_mid_loose, sig_ny_loose, 0.08, 0.04, 0.03, comp_pct=0.75), 160.0, 0.50, 120.0, 0.75, "👑 Apex Sovereign Void Paragon 2026")
    ]

    results = []
    print("\n" + "=" * 115)
    print(f"{'Strategy':<8} | {'Archetype':<32} | {'Net PnL ($)':<11} | {'PF':<6} | {'Trades/Yr':<9} | {'MaxDD ($)':<9} | {'Win%':<6} | {'MCR%':<6} | {'MC P95 DD':<10}")
    print("=" * 115)

    for sid, name, runner, d_stop, d_lock, m_target, m_lock, arch in strategy_definitions:
        trades = runner()
        metrics = analyze_portfolio(
            trades, initial_capital=10000.0,
            daily_hard_stop=d_stop, daily_trail_lock_ratio=d_lock,
            monthly_target_lock=m_target, monthly_lock_ratio=m_lock
        )
        row = {
            "Strategy_ID": sid,
            "Name": name,
            "Archetype": arch,
            **metrics
        }
        results.append(row)
        print(f"{sid:<8} | {name:<32} | ${metrics['Net_Profit_USD']:>10,.2f} | {metrics['Profit_Factor']:>6.3f} | {metrics['Annual_Trades']:>9.1f} | ${metrics['Max_Intra_DD_USD']:>8.2f} | {metrics['Win_Rate_Pct']:>5.1f}% | {metrics['MCR_Pct']:>5.1f}% | ${metrics['MC_P95_DD']:>9.2f}")

    print("=" * 115)

    RESULTS_DIR = "/root/CFD-Trading-ML/projects/quant_strategy_discovery/results"
    if not os.path.exists(RESULTS_DIR):
        RESULTS_DIR = "/content/CFD-Trading-ML/projects/quant_strategy_discovery/results"
    os.makedirs(RESULTS_DIR, exist_ok=True)

    csv_path = os.path.join(RESULTS_DIR, "batch_84_liquidity_void_matrix.csv")
    json_path = os.path.join(RESULTS_DIR, "batch_84_liquidity_void_results.json")

    df_res = pd.DataFrame(results)
    df_res.to_csv(csv_path, index=False)
    with open(json_path, "w") as f:
        json.dump(results, f, indent=2)

    elapsed = time.time() - start_time
    print(f"\n[+] Batch 84 Execution Complete in {elapsed:.2f}s!")
    print(f"[+] Matrix saved to: {csv_path}")
    print(f"[+] Metrics saved to: {json_path}")

if __name__ == "__main__":
    run_batch_84()
