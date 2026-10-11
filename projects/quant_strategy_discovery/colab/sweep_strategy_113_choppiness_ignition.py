#!/usr/bin/env python3
"""
===============================================================================
STRATEGY 113: CHOPPINESS INDEX COMPRESSION TO EXPLOSION IGNITION SWEEP (COLAB)
===============================================================================
Asset: XAUUSD (Gold CFD)
Timeframe: H1
Execution Platform: Google Colab Cloud VM (x86_64)
Hypothesis:
  When the Choppiness Index compresses below a critical consolidation threshold (CHOP < 38.2),
  the market is in extreme fractal consolidation. The subsequent expansion bar ignites explosive
  momentum. Gating with Katz Fractal Dimension (KFD <= 1.40) and secular trend (EMA200) captures
  directional breakouts with high asymmetric payoff.
===============================================================================
"""

import os
import sys
import time
import json
import numpy as np
import pandas as pd

REPO_ROOT = "/content/CFD-Trading-ML"
DATA_DIR = os.path.join(REPO_ROOT, "projects/quant_strategy_discovery/data")

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

def compute_katz_fractal_dimension(closes: np.ndarray, atr: np.ndarray, period: int = 24) -> np.ndarray:
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

def compute_chop(highs: np.ndarray, lows: np.ndarray, atr: np.ndarray, period: int = 14) -> np.ndarray:
    n = len(highs)
    range_high = pd.Series(highs).rolling(period).max().values
    range_low = pd.Series(lows).rolling(period).min().values
    atr_sum = pd.Series(atr).rolling(period).sum().values
    denom = range_high - range_low
    return np.where(denom > 0, 100.0 * np.log10(atr_sum / denom) / np.log10(period), 50.0)

def simulate_chop(opens, highs, lows, closes, atr14, ema200, kfd24, chop, months, dates, chop_thresh=38.2, kfd_thresh=1.40, tp_mult=4.5, sl_mult=2.0, plock=250.0, lbreak=250.0):
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
                    "pnl": pnl, "month": months[entry_idx], "date": dates[i]
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

            # Ignition: CHOP crosses below threshold from above
            ignition = (chop[i] < chop_thresh) and (chop[i - 1] >= chop_thresh)
            bull_sig = ignition and trend_bull and kfd_ok
            bear_sig = ignition and trend_bear and kfd_ok

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

    if not trades:
        return {"total_trades": 0, "net_profit": 0.0, "pf": 0.0, "win_rate": 0.0, "max_dd": 0.0, "romad": 0.0, "mcr": 0.0}

    pnls = [t["pnl"] for t in trades]
    net_p = sum(pnls)
    gross_win = sum([p for p in pnls if p > 0])
    gross_loss = abs(sum([p for p in pnls if p < 0]))
    pf = (gross_win / gross_loss) if gross_loss > 0 else (99.0 if gross_win > 0 else 0.0)
    wr = (len([p for p in pnls if p > 0]) / len(pnls)) * 100.0

    equity = np.cumsum(pnls)
    peak = np.maximum.accumulate(equity)
    dd = peak - equity
    mdd = float(np.max(dd)) if len(dd) > 0 else 0.0
    romad = (net_p / mdd) if mdd > 0 else 0.0

    df_tr = pd.DataFrame(trades)
    m_pnl = df_tr.groupby("month")["pnl"].sum()
    pos_m = int((m_pnl > 0).sum())
    mcr = round((pos_m / 72.0) * 100.0, 2)

    return {
        "total_trades": len(trades), "net_profit": round(net_p, 2), "pf": round(pf, 3),
        "win_rate": round(wr, 2), "max_dd": round(mdd, 2), "romad": round(romad, 2),
        "mcr": mcr, "pos_months": pos_m, "total_months": 72
    }

def main():
    t_start = time.time()
    print("=" * 95)
    print("🚀 OPTIMIZATION SWEEP: STRATEGY 113 (CHOPPINESS IGNITION) ON GOOGLE COLAB")
    print("=" * 95)

    data_path = os.path.join(DATA_DIR, "XAUUSD_H1.parquet")
    df = pd.read_parquet(data_path)
    opens = df["open"].values.astype(np.float64)
    highs = df["high"].values.astype(np.float64)
    lows = df["low"].values.astype(np.float64)
    closes = df["close"].values.astype(np.float64)
    dates = df.index
    months = (dates.year.values * 100 + dates.month.values).astype(np.int32)

    atr14 = compute_atr(highs, lows, closes, 14)
    ema200 = compute_ema(closes, 200)
    kfd24 = compute_katz_fractal_dimension(closes, atr14, 24)

    chop_periods = [10, 14, 20]
    chop_thresholds = [35.0, 38.2, 42.0]
    tp_mults = [3.5, 4.5, 5.5]
    sl_mults = [1.5, 2.0, 2.5]
    kfd_threshs = [1.38, 1.42]

    chop_cache = {}
    for p in chop_periods:
        chop_cache[p] = compute_chop(highs, lows, atr14, p)

    results = []
    print(f"[*] Running 162 Parameter Grid Combinations on Google Colab VM...")
    for p in chop_periods:
        c_series = chop_cache[p]
        for c_th in chop_thresholds:
            for tp_m in tp_mults:
                for sl_m in sl_mults:
                    for kfd_t in kfd_threshs:
                        m = simulate_chop(opens, highs, lows, closes, atr14, ema200, kfd24, c_series, months, dates, chop_thresh=c_th, kfd_thresh=kfd_t, tp_mult=tp_m, sl_mult=sl_m, plock=250.0)
                        cfg = {"chop_period": p, "chop_thresh": c_th, "tp_mult": tp_m, "sl_mult": sl_m, "kfd_thresh": kfd_t}
                        results.append({**cfg, **m})

    df_res = pd.DataFrame(results)
    df_res.sort_values(by=["pf", "net_profit"], ascending=[False, False], inplace=True)
    out_csv = os.path.join(REPO_ROOT, "projects/quant_strategy_discovery/results/strategy_113_chop_sweep_results.csv")
    df_res.to_csv(out_csv, index=False)
    print(f"[+] Saved {len(df_res)} sweep results to {out_csv}")
    print("\nTOP 5 CONFIGURATIONS:")
    print(df_res.head(5)[["chop_period", "chop_thresh", "tp_mult", "sl_mult", "kfd_thresh", "total_trades", "net_profit", "pf", "max_dd", "romad", "mcr"]].to_string(index=False))

    champ = df_res.iloc[0].to_dict()
    out_json = os.path.join(REPO_ROOT, "projects/quant_strategy_discovery/results/strategy_113_champion.json")
    with open(out_json, "w") as f:
        json.dump({"strategy_id": "STRATEGY_113", "champion": champ, "runtime_seconds": round(time.time() - t_start, 2)}, f, indent=2)
    print(f"[+] Saved Champion to {out_json}")

if __name__ == "__main__":
    main()
