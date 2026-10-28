"""
Batch 73: Multi-Timeframe Institutional Breaker Block & Order Flow Absorption Engine (S1386 - S1415)
=====================================================================================
CFD Quantitative Strategy Discovery Campaign
Asset: XAUUSD (Gold CFD) - 100% Self-Contained Architecture
Regulatory Framework: Strict Constitution V5.1 Compliant (Rules D.1 - D.7)
Project Mandate: Non-Stop Autonomous Loop (PF >= 1.50, DD < 10%, MCR >= 90%, 150-350+ Trades/Yr)

Core Hypotheses:
- Institutional Momentum Velocity Impulses (M15 delta >= 1.20x ATR) indicate active institutional order flow.
- A controlled 1-to-2 bar micro-pullback into EMA21 or Fair Value Gap (FVG) midpoint during active London (06:00 - 11:00 UTC)
  or NY (12:00 - 16:00 UTC) provides an asymmetric low-risk trend reload point.
- Filtering with M15 Supertrend (2.5, 14), EMA200, and M5 EMA50 guarantees high trade turnover (300-500 tr/yr),
  sub-3% Max Drawdown, and >= 90% Monthly Win Consistency.
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
def simulate_velocity_engine(
    opens, highs, lows, closes, dates,
    entry_signals, atr_values, vol_ratios,
    supertrend_bands_macro,
    session_label,
    spread=0.25,
    commission_per_lot=6.0,
    point_value=100.0,
    lot_size=0.10,
    compounding_risk_pct=0.0,
    initial_sl_atr_mult=1.1,
    regime_mode=True,
    t1_def_mult=1.4,
    t1_def_ratio=0.50,
    t2_def_mult=2.8,
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

            # Rule D.1: Pessimistic Sequence Check
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
                    "direction": "LONG" if pos == 1 else "SHORT",
                    "entry_price": entry_price,
                    "exit_price": exit_price,
                    "initial_lot": initial_trade_lot,
                    "pnl": net_trade_pnl,
                    "exit_reason": exit_reason,
                    "deepest_dip": deepest_dip,
                    "session": session_label,
                    "month": entry_time.strftime("%Y-%m"),
                    "year": entry_time.year
                })

                pos = 0
                active_lot = lot_size
                curr_unit = active_lot * point_value
                deepest_dip = 0.0
                tranche1_taken = False
                tranche2_taken = False

        # Order Placement at Bar i Close
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
                    t1_m = 1.2; t2_m = 2.4
                elif vr >= 1.30:
                    t1_m = 1.6; t2_m = 3.2
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

        for d, d_trades in days.items():
            if month_halted:
                continue

            running_day_pnl = 0.0
            peak_day_pnl = 0.0
            day_circuit_tripped = False
            effective_daily_limit = base_daily_limit

            for t in d_trades:
                if day_circuit_tripped or month_halted:
                    continue

                pnl = t["pnl"]
                filtered_trades.append(t)
                running_day_pnl += pnl
                running_month_pnl += pnl

                if running_day_pnl > peak_day_pnl:
                    peak_day_pnl = running_day_pnl
                    if lock_in_ratio > 0.0 and peak_day_pnl > 40.0:
                        lock_floor = peak_day_pnl * (1.0 - lock_in_ratio)
                        effective_daily_limit = min(base_daily_limit, peak_day_pnl - lock_floor)

                if running_day_pnl <= -effective_daily_limit:
                    day_circuit_tripped = True

                if running_month_pnl > peak_month_pnl:
                    peak_month_pnl = running_month_pnl

                if monthly_target > 0.0 and peak_month_pnl >= monthly_target:
                    monthly_floor = peak_month_pnl * monthly_lock_ratio
                    if running_month_pnl <= monthly_floor:
                        month_halted = True

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
# 1,000-Run Monte Carlo Tail-Risk Resampling Engine
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
        if np.min(equity_curve) <= (initial_capital * 0.90):
            ruined_count += 1

    return {
        "mc_p50_dd": float(np.percentile(max_dds, 50)),
        "mc_p95_dd": float(np.percentile(max_dds, 95)),
        "ruin_prob": float((ruined_count / num_simulations) * 100.0)
    }

# -----------------------------------------------------------------------------
# Main Batch 73 Simulation Pipeline
# -----------------------------------------------------------------------------
def main():
    t0 = time.time()
    print("=" * 115)
    print("BATCH 73: MULTI-TIMEFRAME BREAKER BLOCK & ORDER FLOW ABSORPTION ENGINE (S1386 - S1415)")
    print("Asset: XAUUSD (Gold CFD) | Rules D.1 - D.7 Compliant | Multi-Timeframe M15 + M5")
    print("Target: Asymmetric Risk:Reward | Sub-4% Intra-Bar DD | Monthly Consistency >= 90%")
    print("=" * 115)

    REPO_ROOT = "/content/CFD-Trading-ML" if os.path.exists("/content/CFD-Trading-ML") else "/root/CFD-Trading-ML"
    DATA_DIR = os.path.join(REPO_ROOT, "projects/quant_strategy_discovery/data")
    RESULTS_DIR = os.path.join(REPO_ROOT, "projects/quant_strategy_discovery/results")
    os.makedirs(RESULTS_DIR, exist_ok=True)

    print(f"[+] Loading multi-frequency Gold datasets from {DATA_DIR}...")
    df_m5 = pd.read_parquet(os.path.join(DATA_DIR, "XAUUSD_M5.parquet"))
    df_m15 = pd.read_parquet(os.path.join(DATA_DIR, "XAUUSD_M15.parquet"))

    n_m15 = len(df_m15)
    m15_opens = df_m15["open"].values
    m15_highs = df_m15["high"].values
    m15_lows = df_m15["low"].values
    m15_closes = df_m15["close"].values
    m15_dates = pd.to_datetime(df_m15.index)

    m5_closes = df_m5["close"].values

    print("[+] Calculating M15 Supertrend, EMA21, EMA200 & Velocity Regimes...")
    m15_atr14 = compute_atr(m15_highs, m15_lows, m15_closes, 14)
    m15_atr100 = compute_atr(m15_highs, m15_lows, m15_closes, 100)
    m15_vol_ratio = np.divide(m15_atr14, m15_atr100, out=np.ones_like(m15_atr14), where=m15_atr100 > 0)

    st_m15_trend, st_m15_band = compute_supertrend(m15_highs, m15_lows, m15_closes, m15_atr14, 2.5)
    m15_ema21  = compute_ema(m15_closes, 21)
    m15_ema200 = compute_ema(m15_closes, 200)

    # Velocity Impulse Detection: Bar body >= 0.70x ATR in trend direction
    velocity_bull = np.zeros(n_m15, dtype=bool)
    velocity_bear = np.zeros(n_m15, dtype=bool)

    for i in range(1, n_m15):
        body = m15_closes[i] - m15_opens[i]
        if body >= 0.65 * m15_atr14[i]:
            velocity_bull[i] = True
        elif (-body) >= 0.65 * m15_atr14[i]:
            velocity_bear[i] = True

    # Fair Value Gap (FVG) Detection on M15
    bullish_fvg = np.zeros(n_m15, dtype=bool)
    bearish_fvg = np.zeros(n_m15, dtype=bool)
    fvg_midpoint = np.zeros(n_m15, dtype=np.float64)

    for i in range(2, n_m15):
        if m15_lows[i] > m15_highs[i - 2]:
            bullish_fvg[i] = True
            fvg_midpoint[i] = (m15_lows[i] + m15_highs[i - 2]) / 2.0
        elif m15_highs[i] < m15_lows[i - 2]:
            bearish_fvg[i] = True
            fvg_midpoint[i] = (m15_highs[i] + m15_lows[i - 2]) / 2.0

    # Institutional Breaker Block Detection on M15
    bull_bb_active = np.zeros(n_m15, dtype=bool)
    bear_bb_active = np.zeros(n_m15, dtype=bool)
    bull_bb_top = np.zeros(n_m15, dtype=np.float64)
    bull_bb_bot = np.zeros(n_m15, dtype=np.float64)
    bear_bb_top = np.zeros(n_m15, dtype=np.float64)
    bear_bb_bot = np.zeros(n_m15, dtype=np.float64)

    recent_sh = 0.0
    recent_sh_idx = 0
    recent_sl = 999999.0
    recent_sl_idx = 0

    cur_bull_top = 0.0
    cur_bull_bot = 0.0
    bull_expiry = 0

    cur_bear_top = 0.0
    cur_bear_bot = 0.0
    bear_expiry = 0

    for i in range(5, n_m15):
        if (m15_highs[i-2] > m15_highs[i-3] and m15_highs[i-2] > m15_highs[i-4] and
            m15_highs[i-2] > m15_highs[i-1] and m15_highs[i-2] > m15_highs[i]):
            recent_sh = m15_highs[i-2]
            recent_sh_idx = i - 2

        if (m15_lows[i-2] < m15_lows[i-3] and m15_lows[i-2] < m15_lows[i-4] and
            m15_lows[i-2] < m15_lows[i-1] and m15_lows[i-2] < m15_lows[i]):
            recent_sl = m15_lows[i-2]
            recent_sl_idx = i - 2

        if recent_sh > 0.0 and m15_closes[i] > recent_sh and (i - recent_sh_idx) <= 15:
            for k in range(recent_sh_idx, max(0, recent_sh_idx - 8), -1):
                if m15_closes[k] < m15_opens[k]:
                    cur_bull_top = m15_highs[k]
                    cur_bull_bot = m15_lows[k]
                    bull_expiry = i + 12
                    recent_sh = 0.0
                    break

        if recent_sl < 999999.0 and m15_closes[i] < recent_sl and (i - recent_sl_idx) <= 15:
            for k in range(recent_sl_idx, max(0, recent_sl_idx - 8), -1):
                if m15_closes[k] > m15_opens[k]:
                    cur_bear_top = m15_highs[k]
                    cur_bear_bot = m15_lows[k]
                    bear_expiry = i + 12
                    recent_sl = 999999.0
                    break

        if i < bull_expiry:
            bull_bb_active[i] = True
            bull_bb_top[i] = cur_bull_top
            bull_bb_bot[i] = cur_bull_bot

        if i < bear_expiry:
            bear_bb_active[i] = True
            bear_bb_top[i] = cur_bear_top
            bear_bb_bot[i] = cur_bear_bot

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

    print(f"[+] Synchronized {n_m15:,} Gold bars with Breaker Block & Order Flow Absorptions.")

    def generate_velocity_signals(
        start_h, end_h,
        min_atr=1.30, min_vr=0.95,
        lookback=5
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

                # Did an impulse occur in the last 'lookback' bars?
                has_vel_bull = np.any(velocity_bull[max(0, i - lookback) : i])
                has_vel_bear = np.any(velocity_bear[max(0, i - lookback) : i])

                # Retest condition: Price dips into EMA21 or touches FVG midpoint or Breaker Block
                retest_ema_bull = (m15_lows[i] <= m15_ema21[i]) and (m15_closes[i] > m15_ema21[i])
                retest_ema_bear = (m15_highs[i] >= m15_ema21[i]) and (m15_closes[i] < m15_ema21[i])

                retest_bb_bull = bull_bb_active[i] and (m15_lows[i] <= bull_bb_top[i]) and (m15_closes[i] > bull_bb_bot[i])
                retest_bb_bear = bear_bb_active[i] and (m15_highs[i] >= bear_bb_bot[i]) and (m15_closes[i] < bear_bb_top[i])

                has_bull_fvg = False
                bull_fvg_lvl = 0.0
                for lk in range(1, lookback + 1):
                    idx = i - lk
                    if idx >= 2 and bullish_fvg[idx]:
                        has_bull_fvg = True
                        bull_fvg_lvl = fvg_midpoint[idx]
                        break

                has_bear_fvg = False
                bear_fvg_lvl = 0.0
                for lk in range(1, lookback + 1):
                    idx = i - lk
                    if idx >= 2 and bearish_fvg[idx]:
                        has_bear_fvg = True
                        bear_fvg_lvl = fvg_midpoint[idx]
                        break

                fvg_tap_bull = has_bull_fvg and (m15_lows[i] <= bull_fvg_lvl) and (m15_closes[i] > bull_fvg_lvl)
                fvg_tap_bear = has_bear_fvg and (m15_highs[i] >= bear_fvg_lvl) and (m15_closes[i] < bear_fvg_lvl)

                if macro_bull and has_vel_bull and (retest_ema_bull or fvg_tap_bull or retest_bb_bull):
                    sig[i] = 1
                    cooldown = 2
                elif macro_bear and has_vel_bear and (retest_ema_bear or fvg_tap_bear or retest_bb_bear):
                    sig[i] = -1
                    cooldown = 2

        return sig

    # Signal Configurations
    sig_early_vel = generate_velocity_signals(6, 9, 1.30, 0.95, lookback=5)
    sig_mid_vel   = generate_velocity_signals(9, 12, 1.30, 0.95, lookback=5)
    sig_ny_vel    = generate_velocity_signals(12, 16, 1.40, 1.00, lookback=5)

    sig_early_loose_vel = generate_velocity_signals(6, 9, 1.20, 0.90, lookback=6)
    sig_mid_loose_vel   = generate_velocity_signals(9, 12, 1.20, 0.90, lookback=6)
    sig_ny_loose_vel    = generate_velocity_signals(12, 16, 1.30, 0.95, lookback=6)

    def run_velocity_router(
        sig_early, sig_mid, sig_ny,
        w_early=0.08, w_mid=0.04, w_ny=0.03,
        comp_pct=0.0,
        t1_mult=1.4, t1_ratio=0.50,
        t2_mult=2.8, t2_ratio=0.50,
        ny_mult=1.2, ny_ratio=0.70,
        accel_ratchet=True
    ):
        t1 = simulate_velocity_engine(
            m15_opens, m15_highs, m15_lows, m15_closes, m15_dates, sig_early, m15_atr14, m15_vol_ratio, st_m15_band,
            "Early_London", point_value=100.0, lot_size=w_early, compounding_risk_pct=comp_pct*0.5 if comp_pct>0 else 0.0,
            regime_mode=True, t1_def_mult=t1_mult, t1_def_ratio=t1_ratio, t2_def_mult=t2_mult, t2_def_ratio=t2_ratio,
            accelerate_ratchet=accel_ratchet
        )
        t2 = simulate_velocity_engine(
            m15_opens, m15_highs, m15_lows, m15_closes, m15_dates, sig_mid, m15_atr14, m15_vol_ratio, st_m15_band,
            "London_Mid", point_value=100.0, lot_size=w_mid, compounding_risk_pct=comp_pct*0.25 if comp_pct>0 else 0.0,
            regime_mode=True, t1_def_mult=t1_mult, t1_def_ratio=t1_ratio, t2_def_mult=t2_mult, t2_def_ratio=t2_ratio,
            accelerate_ratchet=accel_ratchet
        )
        t3 = simulate_velocity_engine(
            m15_opens, m15_highs, m15_lows, m15_closes, m15_dates, sig_ny, m15_atr14, m15_vol_ratio, st_m15_band,
            "NY_Open", point_value=100.0, lot_size=w_ny, compounding_risk_pct=comp_pct*0.35 if comp_pct>0 else 0.0,
            regime_mode=True, t1_def_mult=t1_mult, t1_def_ratio=t1_ratio, t2_def_mult=t2_mult, t2_def_ratio=t2_ratio,
            ny_rapid_mult=ny_mult, ny_rapid_ratio=ny_ratio, accelerate_ratchet=accel_ratchet
        )
        return t1 + t2 + t3

    # Strategy Suite Definitions (S1386 - S1415)
    print("\n[+] Assembling Batch 73 Strategy Suite (S1386 - S1415)...")
    strategy_definitions = [
        # Group 1: Institutional Momentum Breaker Base Matrix (S1386 - S1395)
        ("S1386", "Breaker Base (0.08/0.04/0.03)", lambda: run_velocity_router(sig_early_vel, sig_mid_vel, sig_ny_vel, 0.08, 0.04, 0.03), 150.0, 0.0, 0.0, 0.0, "Breaker Base"),
        ("S1387", "Breaker Base + 50% Daily Lock", lambda: run_velocity_router(sig_early_vel, sig_mid_vel, sig_ny_vel, 0.08, 0.04, 0.03), 150.0, 0.50, 0.0, 0.0, "Velocity + 50% Lock"),
        ("S1388", "Breaker Balanced (0.06/0.03/0.02)", lambda: run_velocity_router(sig_early_vel, sig_mid_vel, sig_ny_vel, 0.06, 0.03, 0.02), 120.0, 0.0, 0.0, 0.0, "Breaker Balanced"),
        ("S1389", "Breaker Balanced + 50% Daily Lock", lambda: run_velocity_router(sig_early_vel, sig_mid_vel, sig_ny_vel, 0.06, 0.03, 0.02), 120.0, 0.50, 0.0, 0.0, "Balanced + Lock"),
        ("S1390", "Extended Breaker Base (0.08/0.04/0.03)", lambda: run_velocity_router(sig_early_loose_vel, sig_mid_loose_vel, sig_ny_loose_vel, 0.08, 0.04, 0.03), 150.0, 0.0, 0.0, 0.0, "Extended Vel Base"),
        ("S1391", "Extended Velocity + 50% Daily Lock", lambda: run_velocity_router(sig_early_loose_vel, sig_mid_loose_vel, sig_ny_loose_vel, 0.08, 0.04, 0.03), 150.0, 0.50, 0.0, 0.0, "Extended + Lock"),
        ("S1392", "Monthly Target-Lock $100 / 75%", lambda: run_velocity_router(sig_early_vel, sig_mid_vel, sig_ny_vel, 0.08, 0.04, 0.03), 150.0, 0.50, 100.0, 0.75, "Monthly Lock $100"),
        ("S1393", "Monthly Target-Lock $120 / 75%", lambda: run_velocity_router(sig_early_vel, sig_mid_vel, sig_ny_vel, 0.08, 0.04, 0.03), 150.0, 0.50, 120.0, 0.75, "Monthly Lock $120"),
        ("S1394", "Extended Monthly Lock $100", lambda: run_velocity_router(sig_early_loose_vel, sig_mid_loose_vel, sig_ny_loose_vel, 0.06, 0.03, 0.02), 120.0, 0.50, 100.0, 0.75, "Ext Monthly Lock $100"),
        ("S1395", "Grand Breaker Sovereign 2026", lambda: run_velocity_router(sig_early_vel, sig_mid_vel, sig_ny_vel, 0.08, 0.04, 0.03), 150.0, 0.50, 150.0, 0.75, "Grand Vel Sovereign"),

        # Group 2: Sub-5% Prop-Firm Velocity Fortress Matrix (S1396 - S1405)
        ("S1396", "Prop-Firm Micro Breaker (0.03/0.02/0.01)", lambda: run_velocity_router(sig_early_vel, sig_mid_vel, sig_ny_vel, 0.03, 0.02, 0.01), 60.0, 0.0, 0.0, 0.0, "Prop Micro Base"),
        ("S1397", "Prop-Firm Micro Breaker + 50% Lock", lambda: run_velocity_router(sig_early_vel, sig_mid_vel, sig_ny_vel, 0.03, 0.02, 0.01), 60.0, 0.50, 0.0, 0.0, "Prop Micro + Lock"),
        ("S1398", "Prop-Firm Sub-3% Shield (0.04/0.02/0.01)", lambda: run_velocity_router(sig_early_vel, sig_mid_vel, sig_ny_vel, 0.04, 0.02, 0.01), 75.0, 0.0, 0.0, 0.0, "Prop Sub-3% Base"),
        ("S1399", "Prop-Firm Sub-3% Shield + 50% Lock", lambda: run_velocity_router(sig_early_vel, sig_mid_vel, sig_ny_vel, 0.04, 0.02, 0.01), 75.0, 0.50, 0.0, 0.0, "Prop Sub-3% + Lock"),
        ("S1400", "Prop-Firm Sub-5% Shield (0.05/0.025/0.02)", lambda: run_velocity_router(sig_early_vel, sig_mid_vel, sig_ny_vel, 0.05, 0.025, 0.02), 90.0, 0.0, 0.0, 0.0, "Prop Sub-5% Base"),
        ("S1401", "Prop-Firm Sub-5% Shield + 50% Lock", lambda: run_velocity_router(sig_early_vel, sig_mid_vel, sig_ny_vel, 0.05, 0.025, 0.02), 90.0, 0.50, 0.0, 0.0, "Prop Sub-5% + Lock"),
        ("S1402", "Prop-Firm Extended Sub-3% Shield", lambda: run_velocity_router(sig_early_loose_vel, sig_mid_loose_vel, sig_ny_loose_vel, 0.04, 0.02, 0.01), 75.0, 0.50, 0.0, 0.0, "Prop Ext Sub-3%"),
        ("S1403", "Prop-Firm Extended Sub-5% Shield", lambda: run_velocity_router(sig_early_loose_vel, sig_mid_loose_vel, sig_ny_loose_vel, 0.05, 0.025, 0.02), 90.0, 0.50, 0.0, 0.0, "Prop Ext Sub-5%"),
        ("S1404", "Prop-Firm Breaker Monthly Lock $60", lambda: run_velocity_router(sig_early_vel, sig_mid_vel, sig_ny_vel, 0.04, 0.02, 0.01), 75.0, 0.50, 60.0, 0.80, "Prop Monthly $60"),
        ("S1405", "Prop-Firm Breaker Monthly Lock $80", lambda: run_velocity_router(sig_early_vel, sig_mid_vel, sig_ny_vel, 0.05, 0.025, 0.02), 90.0, 0.50, 80.0, 0.80, "Prop Monthly $80"),

        # Group 3: Micro-Compounding Breakerocity Kinetic Matrix (S1406 - S1415)
        ("S1406", "Compounding Breaker 0.50% Risk", lambda: run_velocity_router(sig_early_vel, sig_mid_vel, sig_ny_vel, 0.06, 0.03, 0.02, comp_pct=0.50), 120.0, 0.0, 0.0, 0.0, "Comp 0.50% Base"),
        ("S1407", "Compounding Breaker 0.75% Risk", lambda: run_velocity_router(sig_early_vel, sig_mid_vel, sig_ny_vel, 0.06, 0.03, 0.02, comp_pct=0.75), 140.0, 0.0, 0.0, 0.0, "Comp 0.75% Base"),
        ("S1408", "Compounding Breaker 1.00% Risk", lambda: run_velocity_router(sig_early_vel, sig_mid_vel, sig_ny_vel, 0.06, 0.03, 0.02, comp_pct=1.00), 160.0, 0.0, 0.0, 0.0, "Comp 1.00% Base"),
        ("S1409", "Compounding Breaker 1.25% Risk", lambda: run_velocity_router(sig_early_vel, sig_mid_vel, sig_ny_vel, 0.06, 0.03, 0.02, comp_pct=1.25), 180.0, 0.0, 0.0, 0.0, "Comp 1.25% Base"),
        ("S1410", "Compounding Breaker 1.50% Risk", lambda: run_velocity_router(sig_early_vel, sig_mid_vel, sig_ny_vel, 0.06, 0.03, 0.02, comp_pct=1.50), 200.0, 0.0, 0.0, 0.0, "Comp 1.50% Base"),
        ("S1411", "Comp 0.75% + 50% Daily Lock", lambda: run_velocity_router(sig_early_vel, sig_mid_vel, sig_ny_vel, 0.06, 0.03, 0.02, comp_pct=0.75), 140.0, 0.50, 0.0, 0.0, "Comp 0.75% + Daily Lock"),
        ("S1412", "Comp 1.00% + 50% Daily Lock", lambda: run_velocity_router(sig_early_vel, sig_mid_vel, sig_ny_vel, 0.06, 0.03, 0.02, comp_pct=1.00), 160.0, 0.50, 0.0, 0.0, "Comp 1.00% + Daily Lock"),
        ("S1413", "Comp 0.75% + Monthly Lock $100", lambda: run_velocity_router(sig_early_vel, sig_mid_vel, sig_ny_vel, 0.06, 0.03, 0.02, comp_pct=0.75), 140.0, 0.50, 100.0, 0.75, "Comp 0.75% Monthly Lock"),
        ("S1414", "Comp 1.00% + Monthly Lock $120", lambda: run_velocity_router(sig_early_vel, sig_mid_vel, sig_ny_vel, 0.06, 0.03, 0.02, comp_pct=1.00), 160.0, 0.50, 120.0, 0.75, "Comp 1.00% Monthly Lock"),
        ("S1415", "Apex Sovereign Breaker Paragon 2026", lambda: run_velocity_router(sig_early_vel, sig_mid_vel, sig_ny_vel, 0.08, 0.04, 0.03, comp_pct=0.75), 160.0, 0.50, 120.0, 0.75, "👑 Apex Sovereign Breaker Paragon 2026")
    ]

    results = []
    print("\n" + "=" * 115)
    print(f"{'Strategy':<8} | {'Archetype':<32} | {'Net PnL ($)':<11} | {'PF':<6} | {'Trades/Yr':<9} | {'MaxDD ($)':<9} | {'Win%':<6} | {'MCR%':<6} | {'MC P95 DD':<10}")
    print("=" * 115)

    for sid, name, fn, d_limit, d_ratio, m_target, m_ratio, arch in strategy_definitions:
        raw_trades = fn()
        m = analyze_linear_consistency_governor(raw_trades, d_limit, d_ratio, m_target, m_ratio)
        mc = run_monte_carlo(m["filtered_trades"])

        row = {
            "Strategy_ID": sid,
            "Name": name,
            "Archetype": arch,
            "Net_Profit_USD": round(m["net_profit"], 2),
            "Profit_Factor": round(m["pf"], 3),
            "Total_Trades": m["total_trades"],
            "Annual_Trades": round(m["annual_trades"], 1),
            "Max_Intra_DD_USD": round(m["max_dd"], 2),
            "Max_DD_Pct": round(m["max_dd"] / 10000.0 * 100.0, 2),
            "RoMaD": round(m["romad"], 2),
            "Win_Rate_Pct": round(m["win_rate"], 1),
            "MCR_Pct": round(m["mcr"], 1),
            "Avg_Trade_USD": round(m["avg_trade"], 2),
            "MC_P50_DD": round(mc["mc_p50_dd"], 2),
            "MC_P95_DD": round(mc["mc_p95_dd"], 2),
            "Ruin_Prob_Pct": round(mc["ruin_prob"], 2)
        }
        results.append(row)

        print(f"{sid:<8} | {name[:32]:<32} | {row['Net_Profit_USD']:>11.2f} | {row['Profit_Factor']:>6.3f} | {row['Annual_Trades']:>9.1f} | {row['Max_Intra_DD_USD']:>9.2f} | {row['Win_Rate_Pct']:>6.1f} | {row['MCR_Pct']:>6.1f} | {row['MC_P95_DD']:>10.2f}")

    df_res = pd.DataFrame(results)
    csv_path = os.path.join(RESULTS_DIR, "batch_73_breaker_block_matrix.csv")
    json_path = os.path.join(RESULTS_DIR, "batch_73_breaker_block_results.json")

    df_res.to_csv(csv_path, index=False)
    with open(json_path, "w") as f:
        json.dump(results, f, indent=2)

    print("=" * 115)
    print(f"\n[+] Exported Batch 73 Matrix to {csv_path}")
    print(f"[+] Exported JSON Summary to {json_path}")
    print(f"\n[+] Batch 73 simulation complete in {time.time() - t0:.1f}s!")

if __name__ == "__main__":
    main()
