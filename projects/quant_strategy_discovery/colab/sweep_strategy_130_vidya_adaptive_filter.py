#!/usr/bin/env python3
"""
===============================================================================
STRATEGY 130: VARIABLE INDEX DYNAMIC AVERAGE (VIDYA) OPTIMIZATION SWEEP
===============================================================================
Asset: XAUUSD (Gold CFD)
Timeframe: H1
Execution Platform: Google Colab Cloud VM (x86_64)
Hypothesis:
  Tushar Chande's VIDYA modulates exponential smoothing weight dynamically
  using the Chande Momentum Oscillator (CMO) as the volatility/trend index.
  By optimizing the CMO lookback, base EMA length, CMO acceleration thresholds,
  and asymmetric reward-to-risk (TP/SL), we capture early trend transitions
  while filtering out choppy market regimes via Katz Fractal Dimension (KFD).
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

def compute_vidya(closes: np.ndarray, cmo_period: int = 9, ema_period: int = 21):
    n = len(closes)
    diff = np.diff(closes, prepend=closes[0])
    gains = np.where(diff > 0, diff, 0.0)
    losses = np.where(diff < 0, -diff, 0.0)
    g_sum = pd.Series(gains).rolling(cmo_period).sum().values
    l_sum = pd.Series(losses).rolling(cmo_period).sum().values
    total = g_sum + l_sum
    cmo = np.where(total > 0, 100.0 * (g_sum - l_sum) / total, 0.0)
    
    vidya = np.copy(closes)
    alpha = 2.0 / (ema_period + 1.0)
    for i in range(1, n):
        k = abs(cmo[i]) / 100.0 * alpha
        vidya[i] = k * closes[i] + (1.0 - k) * vidya[i - 1]
    return vidya, cmo

def simulate_vidya(opens, highs, lows, closes, atr14, ema200, kfd24, vidya, cmo, months, dates,
                   cmo_thresh=15.0, kfd_thresh=1.40, tp_mult=4.5, sl_mult=2.5, plock=200.0, lbreak=250.0):
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

    cross_up = (closes > vidya) & (pd.Series(closes <= vidya).shift(1).fillna(False).values)
    cross_dn = (closes < vidya) & (pd.Series(closes >= vidya).shift(1).fillna(False).values)

    for i in range(200, n - 1):
        if months[i] != curr_m:
            curr_m = months[i]
            m_pnl = 0.0
            m_locked = False

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
                    "pnl": pnl, "month": months[entry_idx], "date": pd.to_datetime(dates[i])
                })
                m_pnl += pnl
                if m_pnl >= plock or m_pnl <= -lbreak:
                    m_locked = True
                in_pos = False
                continue

        if not in_pos and not m_locked:
            kfd_ok = kfd24[i] <= kfd_thresh
            trend_bull = closes[i] > ema200[i]
            trend_bear = closes[i] < ema200[i]

            bull_sig = cross_up[i] and (cmo[i] > cmo_thresh) and trend_bull and kfd_ok
            bear_sig = cross_dn[i] and (cmo[i] < -cmo_thresh) and trend_bear and kfd_ok

            atr_val = atr14[i]
            if bull_sig:
                in_pos = True
                pos_type = 1
                entry_idx = i + 1
                entry_price = opens[i + 1] + spread_pts
                sl_price = entry_price - (sl_mult * atr_val)
                tp_price = entry_price + (tp_mult * atr_val)
            elif bear_sig:
                in_pos = True
                pos_type = -1
                entry_idx = i + 1
                entry_price = opens[i + 1]
                sl_price = entry_price + (sl_mult * atr_val)
                tp_price = entry_price - (tp_mult * atr_val)

    return trades

def evaluate_metrics(trades):
    if len(trades) == 0:
        return {"total_trades": 0, "net_profit": 0.0, "pf": 0.0, "win_rate": 0.0, "max_dd": 0.0, "romad": 0.0, "mcr": 0.0}
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
    print("=" * 100, flush=True)
    print("STRATEGY 130: VIDYA ADAPTIVE FILTER HIGH-DENSITY OPTIMIZATION SWEEP", flush=True)
    print("=" * 100, flush=True)

    t0 = time.time()
    gold_path = os.path.join(DATA_DIR, "XAUUSD_H1.parquet")
    df = pd.read_parquet(gold_path)
    opens = df["open"].values.astype(np.float64)
    highs = df["high"].values.astype(np.float64)
    lows = df["low"].values.astype(np.float64)
    closes = df["close"].values.astype(np.float64)
    dates = df.index
    months = (dates.year.values * 100 + dates.month.values).astype(np.int32)

    atr14 = compute_atr(highs, lows, closes, 14)
    ema200 = compute_ema(closes, 200)
    kfd24 = compute_katz_fractal_dimension(closes, 24)

    # Grid search space
    cmo_periods = [7, 9, 12]
    ema_periods = [14, 21, 28]
    cmo_thresholds = [10.0, 15.0, 20.0]
    tp_mults = [3.5, 4.5, 5.5]
    sl_mults = [1.5, 2.0, 2.5]
    kfd_threshs = [1.38, 1.42]

    # Precompute VIDYA for (cmo_p, ema_p)
    vidya_cache = {}
    for cp, ep in itertools.product(cmo_periods, ema_periods):
        vidya_cache[(cp, ep)] = compute_vidya(closes, cmo_period=cp, ema_period=ep)

    combos = list(itertools.product(cmo_periods, ema_periods, cmo_thresholds, tp_mults, sl_mults, kfd_threshs))
    print(f"[*] Testing {len(combos)} parameter combinations on Gold H1 (72 months)...", flush=True)

    best_res = None
    best_score = -999.0
    all_results = []

    for idx, (cp, ep, c_th, tp, sl, kfd_th) in enumerate(combos):
        v, c = vidya_cache[(cp, ep)]
        trades = simulate_vidya(
            opens=opens, highs=highs, lows=lows, closes=closes,
            atr14=atr14, ema200=ema200, kfd24=kfd24,
            vidya=v, cmo=c, months=months, dates=dates,
            cmo_thresh=c_th, kfd_thresh=kfd_th,
            tp_mult=tp, sl_mult=sl
        )
        m = evaluate_metrics(trades)
        m["params"] = {
            "cmo_period": cp, "ema_period": ep, "cmo_thresh": c_th,
            "tp_mult": tp, "sl_mult": sl, "kfd_thresh": kfd_th
        }
        all_results.append(m)

        # Fitness: PF >= 1.5, min 40 trades, score = PF * log(net_profit) * romad
        if m["total_trades"] >= 40 and m["pf"] >= 1.50 and m["net_profit"] > 5000:
            score = m["pf"] * m["romad"] * (m["mcr"] / 50.0)
            if score > best_score:
                best_score = score
                best_res = m

    print("\n" + "=" * 100, flush=True)
    print("TOP 5 OPTIMIZATION CANDIDATES (RANKED BY BALANCED FITNESS)", flush=True)
    print("=" * 100, flush=True)
    sorted_res = sorted([r for r in all_results if r["total_trades"] >= 40], key=lambda x: x["pf"] * x["romad"], reverse=True)[:5]
    for r in sorted_res:
        p = r["params"]
        print(f"CMO:{p['cmo_period']} EMA:{p['ema_period']} Thresh:{p['cmo_thresh']} TP:{p['tp_mult']} SL:{p['sl_mult']} KFD:{p['kfd_thresh']} | "
              f"Trades:{r['total_trades']} Net:${r['net_profit']} PF:{r['pf']} DD:${r['max_dd']} RoMaD:{r['romad']}x MCR:{r['mcr']}%", flush=True)
    print("=" * 100, flush=True)

    if best_res:
        out_file = os.path.join(OUT_DIR, "strategy_130_champion.json")
        with open(out_file, "w") as f:
            json.dump({
                "strategy_id": "STRATEGY_130",
                "strategy_name": "Gold H1 VIDYA Adaptive Filter",
                "champion": best_res,
                "runtime_seconds": round(time.time() - t0, 2)
            }, f, indent=2)
        print(f"[+] Champion saved to {out_file}", flush=True)

if __name__ == "__main__":
    main()
