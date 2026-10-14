#!/usr/bin/env python3
"""
===============================================================================
QUANTUM TITAN CORE B: MULTI-ASSET REVERSE-ENGINEERING (XAUUSD & EURUSD)
===============================================================================
Assets: XAUUSD H1 & EURUSD H1 (2020-01-01 to 2025-12-30, 72 Calendar Months)
Execution Platform: Google Colab Cloud VM (x86_64)

Core B Engine: H1 Swing Pivot Reaction & Pullback Breakout
Rule: ZERO Martingale, ZERO Averaging Down, Disciplined Fixed/Trailing SL and TP.
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

def simulate_core_b_engine(opens, highs, lows, closes, atr14, ema200, kfd24,
                           months, dates,
                           symbol="XAUUSD", lookback=36, pullback_atr=0.5,
                           sl_mult=2.5, tp_mult=3.5, kfd_thresh=1.42,
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

    if "XAU" in symbol:
        spread_pts = 0.25
        comm_dollars = 0.60
        point_value = 100.0
    else: # EURUSD
        spread_pts = 0.00010
        comm_dollars = 0.60
        point_value = 10000.0

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
                    "symbol": symbol
                })
                m_pnl += pnl
                if m_pnl >= plock or m_pnl <= -lbreak:
                    m_locked = True
                in_pos = False
                continue

        if not in_pos and not m_locked:
            kfd_ok = (kfd24[i] <= kfd_thresh)
            trend_bull = (closes[i] > ema200[i])
            trend_bear = (closes[i] < ema200[i])

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
    print("QUANTUM TITAN CORE B MULTI-ASSET REVERSE-ENGINEERING (XAUUSD & EURUSD)", flush=True)
    print("=" * 110, flush=True)

    t0 = time.time()
    gold_path = os.path.join(DATA_DIR, "XAUUSD_H1.parquet")
    eur_path = os.path.join(DATA_DIR, "EURUSD_H1.parquet")

    df_gold = pd.read_parquet(gold_path)
    df_eur = pd.read_parquet(eur_path)

    # 1. OPTIMIZE CORE B ON GOLD H1
    print("\n[*] Simulating Quantum Titan Core B Fine-Tuning on Gold H1...", flush=True)
    g_opens = df_gold["open"].values.astype(np.float64)
    g_highs = df_gold["high"].values.astype(np.float64)
    g_lows = df_gold["low"].values.astype(np.float64)
    g_closes = df_gold["close"].values.astype(np.float64)
    g_dates = df_gold.index
    g_months = (g_dates.year.values * 100 + g_dates.month.values).astype(np.int32)

    g_atr = compute_atr(g_highs, g_lows, g_closes, 14)
    g_ema = compute_ema(g_closes, 200)
    g_kfd = compute_katz_fractal_dimension(g_closes, 24)

    lookbacks = [24, 30, 36, 42]
    pullback_atrs = [0.4, 0.5, 0.6, 0.8]
    sl_mults = [2.0, 2.5]
    tp_mults = [3.5, 4.0, 4.5]
    kfd_threshs = [1.40, 1.42]

    combos_gold = list(itertools.product(lookbacks, pullback_atrs, sl_mults, tp_mults, kfd_threshs))
    best_gold = None
    best_score_gold = -999.0
    all_gold_results = []

    for lb, pb, sl, tp, kfd_th in combos_gold:
        tr = simulate_core_b_engine(g_opens, g_highs, g_lows, g_closes, g_atr, g_ema, g_kfd,
                                    g_months, g_dates, symbol="XAUUSD",
                                    lookback=lb, pullback_atr=pb, sl_mult=sl, tp_mult=tp, kfd_thresh=kfd_th)
        m = evaluate_metrics(tr, f"Quantum Titan Core B Gold H1 (LB:{lb}, PB:{pb}x, SL:{sl}x, TP:{tp}x, KFD:{kfd_th})")
        m["params"] = {"symbol": "XAUUSD", "lookback": lb, "pullback_atr": pb, "sl_mult": sl, "tp_mult": tp, "kfd_thresh": kfd_th}
        all_gold_results.append(m)

        if m["total_trades"] >= 45 and m["pf"] >= 1.50:
            score = m["pf"] * m["romad"] * (m["mcr"] / 50.0)
            if score > best_score_gold:
                best_score_gold = score
                best_gold = (m, tr)

    # 2. EVALUATE CORE B ON EURUSD H1
    print("\n[*] Simulating Quantum Titan Core B on EURUSD H1...", flush=True)
    e_opens = df_eur["open"].values.astype(np.float64)
    e_highs = df_eur["high"].values.astype(np.float64)
    e_lows = df_eur["low"].values.astype(np.float64)
    e_closes = df_eur["close"].values.astype(np.float64)
    e_dates = df_eur.index
    e_months = (e_dates.year.values * 100 + e_dates.month.values).astype(np.int32)

    e_atr = compute_atr(e_highs, e_lows, e_closes, 14)
    e_ema = compute_ema(e_closes, 200)
    e_kfd = compute_katz_fractal_dimension(e_closes, 24)

    best_eur = None
    best_score_eur = -999.0
    all_eur_results = []

    for lb, pb, sl, tp, kfd_th in combos_gold:
        tr = simulate_core_b_engine(e_opens, e_highs, e_lows, e_closes, e_atr, e_ema, e_kfd,
                                    e_months, e_dates, symbol="EURUSD",
                                    lookback=lb, pullback_atr=pb, sl_mult=sl, tp_mult=tp, kfd_thresh=kfd_th,
                                    plock=150.0, lbreak=200.0)
        m = evaluate_metrics(tr, f"Quantum Titan Core B EURUSD H1 (LB:{lb}, PB:{pb}x, SL:{sl}x, TP:{tp}x, KFD:{kfd_th})")
        m["params"] = {"symbol": "EURUSD", "lookback": lb, "pullback_atr": pb, "sl_mult": sl, "tp_mult": tp, "kfd_thresh": kfd_th}
        all_eur_results.append(m)

        if m["total_trades"] >= 40 and m["pf"] >= 1.30:
            score = m["pf"] * m["romad"] * (m["mcr"] / 50.0)
            if score > best_score_eur:
                best_score_eur = score
                best_eur = (m, tr)

    m_champion_gold = best_gold[0] if best_gold else evaluate_metrics([], "Gold Core B")
    tr_champion_gold = best_gold[1] if best_gold else []

    m_champion_eur = best_eur[0] if best_eur else evaluate_metrics([], "EURUSD Core B")
    tr_champion_eur = best_eur[1] if best_eur else []

    # Combined Gold + EURUSD Portfolio
    tr_portfolio = sorted(tr_champion_gold + tr_champion_eur, key=lambda x: x["date"])
    m_portfolio = evaluate_metrics(tr_portfolio, "QUANTUM TITAN CLEAN QUANT: DUAL-ASSET PORTFOLIO (XAUUSD + EURUSD)")

    print("\n" + "=" * 115, flush=True)
    print("QUANTUM TITAN CORE B MULTI-ASSET REVERSE-ENGINEERING SCORECARD", flush=True)
    print("=" * 115, flush=True)
    print(f"{'Engine / Configuration':<55} | {'Trades':<7} | {'Net Profit':<12} | {'PF':<6} | {'Max DD':<9} | {'RoMaD':<6} | MCR", flush=True)
    print("-" * 115, flush=True)
    print(f"{m_champion_gold['label']:<55} | {m_champion_gold['total_trades']:<7} | ${m_champion_gold['net_profit']:<11.2f} | {m_champion_gold['pf']:<6.3f} | ${m_champion_gold['max_dd']:<8.2f} | {m_champion_gold['romad']:<6.2f} | {m_champion_gold['mcr']:.1f}% ({m_champion_gold['pos_months']}/{m_champion_gold['total_months']})", flush=True)
    print(f"{m_champion_eur['label']:<55} | {m_champion_eur['total_trades']:<7} | ${m_champion_eur['net_profit']:<11.2f} | {m_champion_eur['pf']:<6.3f} | ${m_champion_eur['max_dd']:<8.2f} | {m_champion_eur['romad']:<6.2f} | {m_champion_eur['mcr']:.1f}% ({m_champion_eur['pos_months']}/{m_champion_eur['total_months']})", flush=True)
    print("-" * 115, flush=True)
    print(f"{m_portfolio['label']:<55} | {m_portfolio['total_trades']:<7} | ${m_portfolio['net_profit']:<11.2f} | {m_portfolio['pf']:<6.3f} | ${m_portfolio['max_dd']:<8.2f} | {m_portfolio['romad']:<6.2f} | {m_portfolio['mcr']:.1f}% ({m_portfolio['pos_months']}/{m_portfolio['total_months']})", flush=True)
    print("=" * 115, flush=True)

    out_file = os.path.join(OUT_DIR, "quantum_titan_core_b_multi_asset_results.json")
    with open(out_file, "w") as f:
        json.dump({
            "study": "Quantum Titan Core B Multi-Asset Reverse Engineering",
            "gold_champion": m_champion_gold,
            "eur_champion": m_champion_eur,
            "dual_asset_portfolio": m_portfolio,
            "runtime_seconds": round(time.time() - t0, 2)
        }, f, indent=2)
    print(f"\n[+] Results saved to {out_file}", flush=True)

if __name__ == "__main__":
    main()
