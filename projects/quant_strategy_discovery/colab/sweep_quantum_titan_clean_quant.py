#!/usr/bin/env python3
"""
===============================================================================
STRATEGY REVERSE-ENGINEERING: QUANTUM TITAN CLEAN QUANT EDITION
===============================================================================
Source: /storage/emulated/0/Download/EA/QuantumTitanbyFuckFickFock.mq5
Asset: XAUUSD (Gold CFD)
Timeframe: H1 (2020-01-01 to 2025-12-30, 72 Calendar Months)
Execution Platform: Google Colab Cloud VM (x86_64)

Directives:
  1. Complete removal of Recovery Mode / Martingale / Averaging Down (0% Tolerance).
  2. Strict Stop Loss and Take Profit per trade (Disciplined Risk Control).
  3. Compare Original Fixed-Dollar Baseline vs. Quant-Enhanced Dynamic ATR Model.
  4. Incorporate Macro Trend (EMA200) and Noise Gating (Katz Fractal Dimension).
===============================================================================
"""

import os
import sys
import time
import json
import itertools
import numpy as np
import pandas as pd

REPO_ROOT = "/content/CFD-Trading-ML"
DATA_DIR = os.path.join(REPO_ROOT, "projects/quant_strategy_discovery/data")
OUT_DIR = os.path.join(REPO_ROOT, "projects/quant_strategy_discovery/results")

if not os.path.exists(DATA_DIR):
    if os.path.exists("projects/quant_strategy_discovery/data"):
        DATA_DIR = "projects/quant_strategy_discovery/data"
    elif os.path.exists("/root/CFD-Trading-ML/projects/quant_strategy_discovery/data"):
        DATA_DIR = "/root/CFD-Trading-ML/projects/quant_strategy_discovery/data"

os.makedirs(OUT_DIR, exist_ok=True)

# -----------------------------------------------------------------
# INDICATOR UTILITIES
# -----------------------------------------------------------------
def compute_atr(highs: np.ndarray, lows: np.ndarray, closes: np.ndarray, period: int = 14) -> np.ndarray:
    n = len(closes)
    atr = np.zeros(n, dtype=np.float64)
    tr = np.zeros(n, dtype=np.float64)
    tr[0] = highs[0] - lows[0]
    for i in range(1, n):
        hl = highs[i] - lows[i]
        hc = abs(highs[i] - closes[i - 1])
        lc = abs(lows[i] - closes[i - 1])
        tr[i] = max(hl, max(hc, lc))
    atr[period - 1] = np.mean(tr[:period])
    alpha = 1.0 / period
    for i in range(period, n):
        atr[i] = (tr[i] * alpha) + (atr[i - 1] * (1.0 - alpha))
    return atr

def compute_ema(series: np.ndarray, period: int) -> np.ndarray:
    n = len(series)
    ema = np.zeros(n, dtype=np.float64)
    ema[0] = series[0]
    alpha = 2.0 / (period + 1.0)
    for i in range(1, n):
        ema[i] = (series[i] * alpha) + (ema[i - 1] * (1.0 - alpha))
    return ema

def compute_katz_fractal_dimension(closes: np.ndarray, period: int = 24) -> np.ndarray:
    n = len(closes)
    kfd = np.full(n, 1.5, dtype=np.float64)
    for i in range(period, n):
        window = closes[i - period:i + 1]
        ll = np.sum(np.abs(np.diff(window)))
        d = np.max(np.abs(window - window[0]))
        if ll > 0 and d > 0:
            k = np.log10(period) / (np.log10(period) + np.log10(d / ll))
            kfd[i] = max(1.0, min(2.0, k))
        else:
            kfd[i] = 1.5
    return kfd

# -----------------------------------------------------------------
# CORE A: DAILY HIGH/LOW BREAKOUT SIMULATION
# -----------------------------------------------------------------
def simulate_core_a(opens, highs, lows, closes, prev_h, prev_l, atr14, ema200, kfd24,
                    hours, months, dates,
                    mode="dynamic", sl_val=2.0, tp_val=4.5, buffer_mult=0.15,
                    use_ema=True, use_kfd=True, kfd_thresh=1.40, use_trailing=True,
                    plock=200.0, lbreak=250.0):
    """
    mode: 'fixed' (Original: sl_val/tp_val in dollars) or 'dynamic' (sl_val/tp_val as ATR multiplier)
    """
    n = len(closes)
    trades = []
    in_pos = False
    pos_type = 0
    entry_price = 0.0
    sl_price = 0.0
    tp_price = 0.0
    entry_idx = 0
    trailed = False

    curr_m = months[0]
    m_pnl = 0.0
    m_locked = False

    spread_pts = 0.25
    comm_dollars = 0.60
    point_value = 100.0

    # Traded today flags to prevent duplicate entries on the same calendar day
    curr_day = -1
    day_buy_done = False
    day_sell_done = False

    for i in range(200, n - 1):
        d_key = dates[i].date()
        if d_key != curr_day:
            curr_day = d_key
            day_buy_done = False
            day_sell_done = False

        if months[i] != curr_m:
            curr_m = months[i]
            m_pnl = 0.0
            m_locked = False

        c_atr = atr14[i]

        # Manage open position
        if in_pos:
            hit_tp = False
            hit_sl = False
            exit_price = 0.0

            # Trailing stop logic (adapted from Trail() in Quantum Titan)
            if use_trailing and not trailed:
                trail_trigger = 1.0 * c_atr if mode == "dynamic" else 1.0
                trail_step = 0.5 * c_atr if mode == "dynamic" else 0.5
                if pos_type == 1 and highs[i] >= entry_price + trail_trigger:
                    new_sl = entry_price + trail_step
                    if new_sl > sl_price:
                        sl_price = new_sl
                        trailed = True
                elif pos_type == -1 and lows[i] <= entry_price - trail_trigger:
                    new_sl = entry_price - trail_step
                    if new_sl < sl_price:
                        sl_price = new_sl
                        trailed = True

            if pos_type == 1:
                if lows[i] <= sl_price:
                    hit_sl = True
                    exit_price = sl_price
                elif highs[i] >= tp_price:
                    hit_tp = True
                    exit_price = tp_price
            elif pos_type == -1:
                if highs[i] >= sl_price:
                    hit_sl = True
                    exit_price = sl_price
                elif lows[i] <= tp_price:
                    hit_tp = True
                    exit_price = tp_price

            if hit_tp or hit_sl:
                if pos_type == 1:
                    pnl = (exit_price - entry_price) * point_value - comm_dollars
                else:
                    pnl = (entry_price - exit_price) * point_value - comm_dollars

                trades.append({
                    "entry_idx": entry_idx, "exit_idx": i,
                    "pos_type": pos_type, "entry_price": entry_price, "exit_price": exit_price,
                    "pnl": pnl, "month": months[entry_idx], "date": pd.to_datetime(dates[i]),
                    "engine": "CORE_A_BREAKOUT"
                })
                m_pnl += pnl
                if m_pnl >= plock or m_pnl <= -lbreak:
                    m_locked = True
                in_pos = False
                continue

        # Check for new entry signals
        if not in_pos and not m_locked and hours[i] >= 1:
            h_prev = prev_h[i]
            l_prev = prev_l[i]
            if h_prev <= 0 or l_prev <= 0:
                continue

            buf = buffer_mult * c_atr if mode == "dynamic" else 0.20
            buy_trig = h_prev + buf
            sell_trig = l_prev - buf

            kfd_ok = (kfd24[i] <= kfd_thresh) if use_kfd else True
            trend_bull = (closes[i] > ema200[i]) if use_ema else True
            trend_bear = (closes[i] < ema200[i]) if use_ema else True

            # Confirmed bar breakout
            buy_sig = (highs[i] >= buy_trig) and (closes[i - 1] < buy_trig) and trend_bull and kfd_ok and not day_buy_done
            sell_sig = (lows[i] <= sell_trig) and (closes[i - 1] > sell_trig) and trend_bear and kfd_ok and not day_sell_done

            if buy_sig:
                in_pos = True
                pos_type = 1
                entry_idx = i + 1
                entry_price = opens[i + 1] + spread_pts
                sl_dist = sl_val * c_atr if mode == "dynamic" else sl_val
                tp_dist = tp_val * c_atr if mode == "dynamic" else tp_val
                sl_price = entry_price - sl_dist
                tp_price = entry_price + tp_dist
                trailed = False
                day_buy_done = True
            elif sell_sig:
                in_pos = True
                pos_type = -1
                entry_idx = i + 1
                entry_price = opens[i + 1]
                sl_dist = sl_val * c_atr if mode == "dynamic" else sl_val
                tp_dist = tp_val * c_atr if mode == "dynamic" else tp_val
                sl_price = entry_price + sl_dist
                tp_price = entry_price - tp_dist
                trailed = False
                day_sell_done = True

    return trades

# -----------------------------------------------------------------
# CORE B: H1 SWING PIVOT PULLBACK SIMULATION
# -----------------------------------------------------------------
def simulate_core_b(opens, highs, lows, closes, atr14, ema200, kfd24,
                    months, dates,
                    lookback=30, pullback_atr=0.8, sl_mult=2.0, tp_mult=4.0,
                    use_ema=True, use_kfd=True, kfd_thresh=1.40,
                    plock=200.0, lbreak=250.0):
    n = len(closes)
    trades = []
    in_pos = False
    pos_type = 0
    entry_price = 0.0
    sl_price = 0.0
    tp_price = 0.0
    entry_idx = 0

    curr_m = months[0]
    m_pnl = 0.0
    m_locked = False

    spread_pts = 0.25
    comm_dollars = 0.60
    point_value = 100.0

    # Rolling pivot highs and lows
    p_high = pd.Series(highs).rolling(lookback).max().shift(1).values
    p_low = pd.Series(lows).rolling(lookback).min().shift(1).values

    for i in range(200, n - 1):
        if months[i] != curr_m:
            curr_m = months[i]
            m_pnl = 0.0
            m_locked = False

        c_atr = atr14[i]

        if in_pos:
            hit_tp = False
            hit_sl = False
            exit_price = 0.0

            if pos_type == 1:
                if lows[i] <= sl_price:
                    hit_sl = True
                    exit_price = sl_price
                elif highs[i] >= tp_price:
                    hit_tp = True
                    exit_price = tp_price
            elif pos_type == -1:
                if highs[i] >= sl_price:
                    hit_sl = True
                    exit_price = sl_price
                elif lows[i] <= tp_price:
                    hit_tp = True
                    exit_price = tp_price

            if hit_tp or hit_sl:
                if pos_type == 1:
                    pnl = (exit_price - entry_price) * point_value - comm_dollars
                else:
                    pnl = (entry_price - exit_price) * point_value - comm_dollars

                trades.append({
                    "entry_idx": entry_idx, "exit_idx": i,
                    "pos_type": pos_type, "entry_price": entry_price, "exit_price": exit_price,
                    "pnl": pnl, "month": months[entry_idx], "date": pd.to_datetime(dates[i]),
                    "engine": "CORE_B_PIVOT_PULLBACK"
                })
                m_pnl += pnl
                if m_pnl >= plock or m_pnl <= -lbreak:
                    m_locked = True
                in_pos = False
                continue

        if not in_pos and not m_locked:
            kfd_ok = (kfd24[i] <= kfd_thresh) if use_kfd else True
            trend_bull = (closes[i] > ema200[i]) if use_ema else True
            trend_bear = (closes[i] < ema200[i]) if use_ema else True

            # Pullback to pivot zone in trend direction
            # Long: trend bull, price pulled back from recent swing high by pullback_atr
            buy_pullback = (closes[i] <= p_high[i] - pullback_atr * c_atr) and (closes[i - 1] > p_high[i] - pullback_atr * c_atr)
            sell_pullback = (closes[i] >= p_low[i] + pullback_atr * c_atr) and (closes[i - 1] < p_low[i] + pullback_atr * c_atr)

            buy_sig = buy_pullback and trend_bull and kfd_ok
            sell_sig = sell_pullback and trend_bear and kfd_ok

            if buy_sig:
                in_pos = True
                pos_type = 1
                entry_idx = i + 1
                entry_price = opens[i + 1] + spread_pts
                sl_price = entry_price - (sl_mult * c_atr)
                tp_price = entry_price + (tp_mult * c_atr)
            elif sell_sig:
                in_pos = True
                pos_type = -1
                entry_idx = i + 1
                entry_price = opens[i + 1]
                sl_price = entry_price + (sl_mult * c_atr)
                tp_price = entry_price - (tp_mult * c_atr)

    return trades

def evaluate_metrics(trades, label="Model"):
    if len(trades) == 0:
        return {"label": label, "total_trades": 0, "net_profit": 0.0, "pf": 0.0, "win_rate": 0.0, "max_dd": 0.0, "romad": 0.0, "mcr": 0.0, "pos_months": 0, "total_months": 72}
    df_tr = pd.DataFrame(trades)
    pnls = df_tr["pnl"].values
    net_profit = float(np.sum(pnls))
    wins = pnls[pnls > 0]
    losses = pnls[pnls < 0]
    gross_win = float(np.sum(wins)) if len(wins) > 0 else 0.0
    gross_loss = float(abs(np.sum(losses))) if len(losses) > 0 else 1e-4
    pf = float(gross_win / gross_loss)
    win_rate = float(len(wins) / len(pnls) * 100.0)

    equity = np.cumsum(pnls)
    peak = np.maximum.accumulate(equity)
    dd = peak - equity
    max_dd = float(np.max(dd)) if len(dd) > 0 else 1e-4
    romad = float(net_profit / max_dd)

    m_pnl = df_tr.groupby("month")["pnl"].sum()
    pos_m = int((m_pnl > 0).sum())
    total_m = 72
    mcr = float(pos_m / total_m * 100.0)

    return {
        "label": label,
        "total_trades": len(trades),
        "net_profit": round(net_profit, 2),
        "pf": round(pf, 3),
        "win_rate": round(win_rate, 2),
        "max_dd": round(max_dd, 2),
        "romad": round(romad, 2),
        "mcr": round(mcr, 2),
        "pos_months": pos_m,
        "total_months": total_m
    }

def main():
    print("=" * 110, flush=True)
    print("QUANTUM TITAN REVERSE-ENGINEERING & SCIENTIFIC OPTIMIZATION ON GOOGLE COLAB", flush=True)
    print("=" * 110, flush=True)

    t0 = time.time()
    gold_path = os.path.join(DATA_DIR, "XAUUSD_H1.parquet")
    print(f"[*] Loading Gold H1 dataset from {gold_path}...", flush=True)
    df = pd.read_parquet(gold_path)

    opens = df["open"].values.astype(np.float64)
    highs = df["high"].values.astype(np.float64)
    lows = df["low"].values.astype(np.float64)
    closes = df["close"].values.astype(np.float64)
    dates = df.index
    hours = dates.hour.values.astype(np.int32)
    months = (dates.year.values * 100 + dates.month.values).astype(np.int32)
    n = len(closes)

    atr14 = compute_atr(highs, lows, closes, 14)
    ema200 = compute_ema(closes, 200)
    kfd24 = compute_katz_fractal_dimension(closes, 24)

    # Compute previous day High & Low with strict zero lookahead
    df["bar_date"] = dates.date
    daily_h = df.groupby("bar_date")["high"].max()
    daily_l = df.groupby("bar_date")["low"].min()
    unique_dates = sorted(daily_h.index)

    date_to_prev_h = {}
    date_to_prev_l = {}
    for idx in range(1, len(unique_dates)):
        d_curr = unique_dates[idx]
        d_prev = unique_dates[idx - 1]
        date_to_prev_h[d_curr] = daily_h[d_prev]
        date_to_prev_l[d_curr] = daily_l[d_prev]

    prev_h_arr = np.zeros(n, dtype=np.float64)
    prev_l_arr = np.zeros(n, dtype=np.float64)
    for idx in range(n):
        d_k = dates[idx].date()
        prev_h_arr[idx] = date_to_prev_h.get(d_k, 0.0)
        prev_l_arr[idx] = date_to_prev_l.get(d_k, 0.0)

    print(f"[*] Preprocessing complete. Evaluating {n} bars across 72 calendar months.", flush=True)

    # -------------------------------------------------------------
    # 1. EVALUATE ORIGINAL BASELINE (FIXED-DOLLAR, ZERO RECOVERY)
    # -------------------------------------------------------------
    print("\n[1] Evaluating Original Quantum Titan Baseline (Fixed Dollar, No Recovery)...", flush=True)
    # Mode 1: SL $5, TP $25
    tr_orig_m1 = simulate_core_a(opens, highs, lows, closes, prev_h_arr, prev_l_arr, atr14, ema200, kfd24,
                                 hours, months, dates, mode="fixed", sl_val=5.0, tp_val=25.0, buffer_mult=0.0,
                                 use_ema=False, use_kfd=False, use_trailing=True)
    m_orig_m1 = evaluate_metrics(tr_orig_m1, "Quantum Titan Core A (Original Mode 1: $5 SL, $25 TP)")

    # Mode 2: SL $10, TP $50
    tr_orig_m2 = simulate_core_a(opens, highs, lows, closes, prev_h_arr, prev_l_arr, atr14, ema200, kfd24,
                                 hours, months, dates, mode="fixed", sl_val=10.0, tp_val=50.0, buffer_mult=0.0,
                                 use_ema=False, use_kfd=False, use_trailing=True)
    m_orig_m2 = evaluate_metrics(tr_orig_m2, "Quantum Titan Core A (Original Mode 2: $10 SL, $50 TP)")

    # -------------------------------------------------------------
    # 2. OPTIMIZATION SWEEP: QUANT-ENHANCED CORE A (DYNAMIC ATR)
    # -------------------------------------------------------------
    print("\n[2] Running High-Density Sweep for Quant-Enhanced Core A (Adaptive ATR & Regime)...", flush=True)
    sl_mults = [1.5, 2.0, 2.5]
    tp_mults = [3.5, 4.5, 5.5]
    buf_mults = [0.10, 0.20, 0.30]
    use_emas = [True, False]
    kfd_threshs = [1.38, 1.42]

    combos_a = list(itertools.product(sl_mults, tp_mults, buf_mults, use_emas, kfd_threshs))
    best_core_a = None
    best_score_a = -999.0
    all_core_a_results = []

    for sl_m, tp_m, buf_m, u_ema, kfd_th in combos_a:
        tr = simulate_core_a(opens, highs, lows, closes, prev_h_arr, prev_l_arr, atr14, ema200, kfd24,
                             hours, months, dates, mode="dynamic", sl_val=sl_m, tp_val=tp_m, buffer_mult=buf_m,
                             use_ema=u_ema, use_kfd=True, kfd_thresh=kfd_th, use_trailing=True)
        m = evaluate_metrics(tr, f"Core A Dynamic (SL:{sl_m}x, TP:{tp_m}x, Buf:{buf_m}x, EMA:{u_ema}, KFD:{kfd_th})")
        m["params"] = {"sl_mult": sl_m, "tp_mult": tp_m, "buf_mult": buf_m, "use_ema": u_ema, "kfd_thresh": kfd_th}
        all_core_a_results.append(m)

        if m["total_trades"] >= 45 and m["pf"] >= 1.50:
            score = m["pf"] * m["romad"] * (m["mcr"] / 50.0)
            if score > best_score_a:
                best_score_a = score
                best_core_a = (m, tr)

    # -------------------------------------------------------------
    # 3. OPTIMIZATION SWEEP: CORE B (H1 PIVOT PULLBACK)
    # -------------------------------------------------------------
    print("\n[3] Running High-Density Sweep for Quantum Titan Core B (Pivot Pullback)...", flush=True)
    lookbacks = [24, 36, 48]
    pb_atrs = [0.5, 0.8, 1.2]
    sl_b_mults = [1.5, 2.0, 2.5]
    tp_b_mults = [3.5, 4.5, 5.5]
    kfd_b_threshs = [1.38, 1.42]

    combos_b = list(itertools.product(lookbacks, pb_atrs, sl_b_mults, tp_b_mults, kfd_b_threshs))
    best_core_b = None
    best_score_b = -999.0
    all_core_b_results = []

    for lb, pb, sl_b, tp_b, kfd_th in combos_b:
        tr = simulate_core_b(opens, highs, lows, closes, atr14, ema200, kfd24,
                             months, dates, lookback=lb, pullback_atr=pb, sl_mult=sl_b, tp_mult=tp_b,
                             use_ema=True, use_kfd=True, kfd_thresh=kfd_th)
        m = evaluate_metrics(tr, f"Core B Pivot (LB:{lb}, PB:{pb}x, SL:{sl_b}x, TP:{tp_b}x, KFD:{kfd_th})")
        m["params"] = {"lookback": lb, "pullback_atr": pb, "sl_mult": sl_b, "tp_mult": tp_b, "kfd_thresh": kfd_th}
        all_core_b_results.append(m)

        if m["total_trades"] >= 40 and m["pf"] >= 1.40:
            score = m["pf"] * m["romad"] * (m["mcr"] / 50.0)
            if score > best_score_b:
                best_score_b = score
                best_core_b = (m, tr)

    # -------------------------------------------------------------
    # 4. HYBRID ENSEMBLE (CORE A + CORE B ASYNCHRONOUS COMPOSITE)
    # -------------------------------------------------------------
    m_champion_a = best_core_a[0] if best_core_a else evaluate_metrics([], "Core A")
    tr_champion_a = best_core_a[1] if best_core_a else []

    m_champion_b = best_core_b[0] if best_core_b else evaluate_metrics([], "Core B")
    tr_champion_b = best_core_b[1] if best_core_b else []

    tr_hybrid = sorted(tr_champion_a + tr_champion_b, key=lambda x: x["date"])
    m_hybrid = evaluate_metrics(tr_hybrid, "QUANTUM TITAN CLEAN QUANT HYBRID (CORE A + CORE B)")

    # -------------------------------------------------------------
    # PRINT PERFORMANCE SCORECARD
    # -------------------------------------------------------------
    print("\n" + "=" * 115, flush=True)
    print("QUANTUM TITAN REVERSE-ENGINEERING BENCHMARK & DISCOVERY AUDIT", flush=True)
    print("=" * 115, flush=True)
    print(f"{'Strategy Architecture / Model':<55} | {'Trades':<7} | {'Net Profit':<12} | {'PF':<6} | {'Max DD':<9} | {'RoMaD':<6} | MCR", flush=True)
    print("-" * 115, flush=True)
    print(f"{m_orig_m1['label']:<55} | {m_orig_m1['total_trades']:<7} | ${m_orig_m1['net_profit']:<11.2f} | {m_orig_m1['pf']:<6.3f} | ${m_orig_m1['max_dd']:<8.2f} | {m_orig_m1['romad']:<6.2f} | {m_orig_m1['mcr']:.1f}% ({m_orig_m1['pos_months']}/{m_orig_m1['total_months']})", flush=True)
    print(f"{m_orig_m2['label']:<55} | {m_orig_m2['total_trades']:<7} | ${m_orig_m2['net_profit']:<11.2f} | {m_orig_m2['pf']:<6.3f} | ${m_orig_m2['max_dd']:<8.2f} | {m_orig_m2['romad']:<6.2f} | {m_orig_m2['mcr']:.1f}% ({m_orig_m2['pos_months']}/{m_orig_m2['total_months']})", flush=True)
    print("-" * 115, flush=True)
    print(f"{m_champion_a['label']:<55} | {m_champion_a['total_trades']:<7} | ${m_champion_a['net_profit']:<11.2f} | {m_champion_a['pf']:<6.3f} | ${m_champion_a['max_dd']:<8.2f} | {m_champion_a['romad']:<6.2f} | {m_champion_a['mcr']:.1f}% ({m_champion_a['pos_months']}/{m_champion_a['total_months']})", flush=True)
    print(f"{m_champion_b['label']:<55} | {m_champion_b['total_trades']:<7} | ${m_champion_b['net_profit']:<11.2f} | {m_champion_b['pf']:<6.3f} | ${m_champion_b['max_dd']:<8.2f} | {m_champion_b['romad']:<6.2f} | {m_champion_b['mcr']:.1f}% ({m_champion_b['pos_months']}/{m_champion_b['total_months']})", flush=True)
    print("=" * 115, flush=True)
    print(f"{m_hybrid['label']:<55} | {m_hybrid['total_trades']:<7} | ${m_hybrid['net_profit']:<11.2f} | {m_hybrid['pf']:<6.3f} | ${m_hybrid['max_dd']:<8.2f} | {m_hybrid['romad']:<6.2f} | {m_hybrid['mcr']:.1f}% ({m_hybrid['pos_months']}/{m_hybrid['total_months']})", flush=True)
    print("=" * 115, flush=True)

    out_file = os.path.join(OUT_DIR, "quantum_titan_clean_quant_results.json")
    with open(out_file, "w") as f:
        json.dump({
            "study": "Quantum Titan Reverse Engineering",
            "source_ea": "QuantumTitanbyFuckFickFock.mq5",
            "original_mode_1": m_orig_m1,
            "original_mode_2": m_orig_m2,
            "champion_core_a": m_champion_a,
            "champion_core_b": m_champion_b,
            "hybrid_composite": m_hybrid,
            "runtime_seconds": round(time.time() - t0, 2)
        }, f, indent=2)
    print(f"\n[+] Results saved to {out_file}", flush=True)

if __name__ == "__main__":
    main()
