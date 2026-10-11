#!/usr/bin/env python3
"""
===============================================================================
STRATEGY 101: GOLD H1 TRIX TRIPLE EXPONENTIAL MOMENTUM ACCELERATION (TRIX-KFD)
===============================================================================
Asset: XAUUSD (Gold CFD)
Timeframe: H1
Data Source: Lightweight Parquet Cache (Mobile Hardware Protected, Zero OOM)
Horizon: 2020-01-01 to 2025-12-30 (72 Calendar Months)
Execution Model: Next-Bar Open Fill, $0.25 Spread ($2.50/0.10 lot), $6/lot Comm ($0.60/0.10 lot)
Hypothesis:
  Jack Hutson's TRIX is a 1-bar rate-of-change of a triple exponentially smoothed EMA:
    EMA1 = EMA(Close, N)
    EMA2 = EMA(EMA1, N)
    EMA3 = EMA(EMA2, N)
    TRIX = ((EMA3[t] - EMA3[t-1]) / EMA3[t-1]) * 10000
    Signal = EMA(TRIX, M)
  By triple-smoothing before calculating momentum rate of change, all high-frequency market
  noise shorter than period N is completely eliminated.
  When TRIX crosses its Signal line (or zero line) in alignment with secular trend (EMA200)
  and Katz Fractal Gating (KFD <= 1.40), it captures pure macroeconomic trend acceleration
  with asymmetric reward-to-risk.
===============================================================================
"""

import os
import sys
import gc
import time
import json
import argparse
import numpy as np
import pandas as pd

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

def compute_trix(closes: np.ndarray, n_period: int = 15, m_signal: int = 9):
    ema1 = compute_ema(closes, n_period)
    ema2 = compute_ema(ema1, n_period)
    ema3 = compute_ema(ema2, n_period)
    n = len(closes)
    trix = np.zeros(n, dtype=np.float64)
    for i in range(1, n):
        if ema3[i - 1] != 0:
            trix[i] = ((ema3[i] - ema3[i - 1]) / ema3[i - 1]) * 10000.0
    signal = compute_ema(trix, m_signal)
    return trix, signal

def simulate_trix_strategy(
    opens: np.ndarray, highs: np.ndarray, lows: np.ndarray, closes: np.ndarray,
    atr14: np.ndarray, ema200: np.ndarray, kfd: np.ndarray,
    trix: np.ndarray, signal: np.ndarray,
    months: np.ndarray, dates,
    use_signal_cross: bool = True,
    use_kfd: bool = True, kfd_thresh: float = 1.40,
    tp_mult: float = 4.5, sl_mult: float = 2.0,
    monthly_profit_lock: float = 200.0, monthly_loss_breaker: float = 250.0
):
    n = len(closes)
    trades = []
    in_pos = False
    pos_type = 0  # +1 long, -1 short
    entry_price = 0.0
    sl_price = 0.0
    tp_price = 0.0
    entry_idx = 0

    curr_m = months[0]
    m_pnl = 0.0
    m_locked = False

    spread_pts = 0.25
    comm_dollars = 0.60
    point_value = 100.0  # $10 per pt on 0.10 lot

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
                if m_pnl >= monthly_profit_lock or m_pnl <= -monthly_loss_breaker:
                    m_locked = True
                in_pos = False
                continue

        if not in_pos and not m_locked:
            kfd_ok = (not use_kfd) or (kfd[i] <= kfd_thresh)
            trend_bull = closes[i] > ema200[i]
            trend_bear = closes[i] < ema200[i]

            if use_signal_cross:
                bull_sig = (trix[i - 1] <= signal[i - 1]) and (trix[i] > signal[i]) and trend_bull and kfd_ok
                bear_sig = (trix[i - 1] >= signal[i - 1]) and (trix[i] < signal[i]) and trend_bear and kfd_ok
            else:
                bull_sig = (trix[i - 1] <= 0.0) and (trix[i] > 0.0) and trend_bull and kfd_ok
                bear_sig = (trix[i - 1] >= 0.0) and (trix[i] < 0.0) and trend_bear and kfd_ok

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

def evaluate_metrics(trades: list, total_months: int = 72) -> dict:
    if not trades:
        return {
            "total_trades": 0, "trades_per_year": 0.0, "net_profit": 0.0,
            "pf": 0.0, "win_rate": 0.0, "max_dd": 0.0, "romad": 0.0, "mcr": 0.0,
            "pos_months": 0, "total_months": total_months
        }

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
    mcr = round((pos_m / total_months) * 100.0, 2)
    tpy = round(len(trades) / (total_months / 12.0), 1)

    return {
        "total_trades": len(trades),
        "trades_per_year": tpy,
        "net_profit": round(net_p, 2),
        "pf": round(pf, 3),
        "win_rate": round(wr, 2),
        "max_dd": round(mdd, 2),
        "romad": round(romad, 2),
        "mcr": mcr,
        "pos_months": pos_m,
        "total_months": total_months
    }

def main():
    parser = argparse.ArgumentParser(description="Sweep Strategy 101: TRIX Momentum Acceleration")
    parser.add_argument("--data_path", type=str, default="projects/quant_strategy_discovery/data/XAUUSD_H1.parquet")
    parser.add_argument("--out_dir", type=str, default="projects/quant_strategy_discovery/results")
    args = parser.parse_args()
    os.makedirs(args.out_dir, exist_ok=True)

    t0 = time.time()
    print("[*] Loading XAUUSD H1 Lightweight Parquet Cache...", flush=True)
    df = pd.read_parquet(args.data_path)
    opens = df["open"].values.astype(np.float64)
    highs = df["high"].values.astype(np.float64)
    lows = df["low"].values.astype(np.float64)
    closes = df["close"].values.astype(np.float64)
    dates = df.index
    months = (dates.year.values * 100 + dates.month.values).astype(np.int32)

    print("[*] Precomputing Technical Indicators (ATR, EMA200, KFD)...", flush=True)
    atr14 = compute_atr(highs, lows, closes, 14)
    ema200 = compute_ema(closes, 200)
    kfd24 = compute_katz_fractal_dimension(closes, atr14, 24)

    trix_periods = [(9, 5), (14, 9), (21, 9)]
    tp_mults = [3.5, 4.5]
    sl_mults = [2.0, 2.5]
    kfd_threshs = [1.40, 1.45]
    profit_locks = [200.0, 250.0]

    trix_cache = {}
    for n_p, m_s in trix_periods:
        trix_cache[(n_p, m_s)] = compute_trix(closes, n_period=n_p, m_signal=m_s)

    results = []
    print("[*] Running Targeted Parameter Grid Sweep (48 Configurations)...", flush=True)
    for n_p, m_s in trix_periods:
        tx, sig = trix_cache[(n_p, m_s)]
        for tp in tp_mults:
            for sl_m in sl_mults:
                for kfd_t in kfd_threshs:
                    for plock in profit_locks:
                        trades = simulate_trix_strategy(
                            opens=opens, highs=highs, lows=lows, closes=closes,
                            atr14=atr14, ema200=ema200, kfd=kfd24,
                            trix=tx, signal=sig,
                            months=months, dates=dates,
                            use_signal_cross=True,
                            use_kfd=True, kfd_thresh=kfd_t,
                            tp_mult=tp, sl_mult=sl_m,
                            monthly_profit_lock=plock, monthly_loss_breaker=250.0
                        )
                        m = evaluate_metrics(trades)
                        cfg = {
                            "trix_period": n_p, "signal_period": m_s,
                            "tp_mult": tp, "sl_mult": sl_m,
                            "kfd_thresh": kfd_t, "monthly_profit_lock": plock
                        }
                        results.append({**cfg, **m})

    df_res = pd.DataFrame(results)
    out_csv = os.path.join(args.out_dir, "strategy_101_trix_sweep_results.csv")
    df_res.to_csv(out_csv, index=False)
    print(f"[+] Saved {len(df_res)} sweep configurations to {out_csv}", flush=True)

    df_cand = df_res[(df_res["total_trades"] >= 50) & (df_res["net_profit"] > 0)].copy()
    if not df_cand.empty:
        df_cand.sort_values(by=["pf", "net_profit"], ascending=[False, False], inplace=True)
        top5 = df_cand.head(5)
        print("\n" + "=" * 95, flush=True)
        print("TOP 5 PERFORMING CONFIGURATIONS - STRATEGY 101: GOLD H1 TRIX MOMENTUM ACCELERATION")
        print("=" * 95, flush=True)
        print(top5[["trix_period", "signal_period", "tp_mult", "sl_mult", "kfd_thresh", "monthly_profit_lock", "total_trades", "trades_per_year", "net_profit", "pf", "max_dd", "romad", "mcr"]].to_string(index=False), flush=True)
        print("=" * 95, flush=True)

        champ = top5.iloc[0].to_dict()
        champ_file = os.path.join(args.out_dir, "strategy_101_champion.json")
        with open(champ_file, "w") as f:
            json.dump({
                "strategy_id": "STRATEGY_101",
                "strategy_name": "Gold H1 TRIX Triple Exponential Momentum Acceleration (TRIX-KFD)",
                "champion_metrics": champ,
                "runtime_seconds": round(time.time() - t0, 2)
            }, f, indent=2)
        print(f"[+] Saved Strategy 101 Champion to {champ_file}", flush=True)

    del df
    gc.collect()

if __name__ == "__main__":
    main()
