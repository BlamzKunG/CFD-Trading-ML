#!/usr/bin/env python3
"""
===============================================================================
STRATEGY 93: GOLD H1 TILLSON T3 MOVING AVERAGE ADAPTIVE TREND (T3-KFD) SWEEP
===============================================================================
Asset: XAUUSD (Gold CFD)
Timeframe: H1
Data Source: Lightweight Parquet Cache (Mobile Hardware Protected, Zero OOM)
Horizon: 2020-01-01 to 2025-12-30 (72 Calendar Months)
Execution Model: Next-Bar Open Fill, $0.25 Spread ($2.50/0.10 lot), $6/lot Comm ($0.60/0.10 lot)
Hypothesis:
  Tim Tillson's T3 Moving Average uses generalized DEMA (GD) recursively applied 3 times:
    GD(series, period, v) = EMA(series, period) * (1 + v) - EMA(EMA(series, period), period) * v
    T3 = GD(GD(GD(price, period, v), period, v), period, v)
  With volume factor v = 0.7, T3 eliminates moving average lag without introducing spurious overshoot.
  When combined with Katz Fractal Dimension (KFD <= 1.40) and EMA200 secular trend gating,
  T3 slope inflections provide an institutional edge for Gold H1 swing continuation.
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

def compute_gd(series: np.ndarray, period: int, v: float = 0.7) -> np.ndarray:
    ema1 = compute_ema(series, period)
    ema2 = compute_ema(ema1, period)
    return ema1 * (1.0 + v) - ema2 * v

def compute_tillson_t3(closes: np.ndarray, period: int = 14, v: float = 0.7) -> np.ndarray:
    gd1 = compute_gd(closes, period, v)
    gd2 = compute_gd(gd1, period, v)
    t3 = compute_gd(gd2, period, v)
    return t3

def compute_katz_fractal_dimension(closes: np.ndarray, atr: np.ndarray, period: int = 24) -> np.ndarray:
    n = len(closes)
    kfd = np.full(n, 1.5, dtype=np.float64)
    for i in range(period, n):
        sub = closes[i - period + 1 : i + 1]
        c_first = sub[0]
        c_last = sub[-1]
        euclid_d = abs(c_last - c_first)
        diffs = np.abs(np.diff(sub))
        total_len = np.sum(diffs)
        if total_len > 1e-6 and euclid_d > 1e-6:
            val = np.log10(period) / (np.log10(period) + np.log10(euclid_d / total_len))
            kfd[i] = max(1.0, min(2.0, val))
        else:
            kfd[i] = 1.5
    return kfd

def simulate_t3_strategy(
    opens: np.ndarray,
    highs: np.ndarray,
    lows: np.ndarray,
    closes: np.ndarray,
    atr14: np.ndarray,
    ema200: np.ndarray,
    kfd: np.ndarray,
    t3: np.ndarray,
    months: np.ndarray,
    dates: pd.DatetimeIndex,
    use_kfd: bool = True,
    kfd_thresh: float = 1.40,
    tp_mult: float = 4.0,
    sl_mult: float = 2.0,
    monthly_profit_lock: float = 200.0,
    monthly_loss_breaker: float = 250.0,
    lot_size: float = 0.10,
    spread: float = 0.25,
    commission: float = 6.0
):
    n = len(closes)
    trades = []
    pos = 0 # 1 = Long, -1 = Short, 0 = Flat
    entry_p = 0.0
    sl_p = 0.0
    tp_p = 0.0
    entry_i = 0

    fixed_friction = (spread * lot_size * 100.0) + (commission * lot_size) # $3.10 / 0.10 lot

    cur_m = months[0]
    cur_m_pnl = 0.0
    locked_m = False

    for i in range(50, n - 1):
        bar_m = months[i]
        if bar_m != cur_m:
            cur_m = bar_m
            cur_m_pnl = 0.0
            locked_m = False

        if pos != 0:
            nxt_h = highs[i]
            nxt_l = lows[i]
            hit_tp = False
            hit_sl = False

            if pos == 1:
                if nxt_l <= sl_p: hit_sl = True
                elif nxt_h >= tp_p: hit_tp = True
            elif pos == -1:
                if nxt_h >= sl_p: hit_sl = True
                elif nxt_l <= tp_p: hit_tp = True

            if hit_sl and hit_tp:
                hit_tp = False; hit_sl = True

            if hit_sl or hit_tp:
                exit_p = tp_p if hit_tp else sl_p
                raw_diff = (exit_p - entry_p) if pos == 1 else (entry_p - exit_p)
                pnl = (raw_diff * lot_size * 100.0) - fixed_friction
                cur_m_pnl += pnl
                trades.append({
                    "entry_date": str(dates[entry_i]),
                    "exit_date": str(dates[i]),
                    "pos": pos,
                    "pnl": round(pnl, 2),
                    "month": cur_m,
                    "reason": "TP" if hit_tp else "SL",
                    "holding_bars": i - entry_i
                })
                pos = 0

                if monthly_profit_lock > 0 and cur_m_pnl >= monthly_profit_lock:
                    locked_m = True
                if monthly_loss_breaker > 0 and cur_m_pnl <= -monthly_loss_breaker:
                    locked_m = True

        if pos == 0 and not locked_m:
            c_atr = atr14[i]
            if c_atr < 0.5: continue

            kfd_ok = (kfd[i] <= kfd_thresh) if use_kfd else True
            ema_long_ok = (closes[i] > ema200[i])
            ema_short_ok = (closes[i] < ema200[i])

            # T3 slope inflection & crossover
            t3_slope_up = t3[i] > t3[i - 1]
            t3_slope_dn = t3[i] < t3[i - 1]

            bull_cross = (closes[i] > t3[i]) and (closes[i - 1] <= t3[i - 1]) and t3_slope_up and ema_long_ok and kfd_ok
            bear_cross = (closes[i] < t3[i]) and (closes[i - 1] >= t3[i - 1]) and t3_slope_dn and ema_short_ok and kfd_ok

            if bull_cross:
                pos = 1
                entry_i = i + 1
                entry_p = opens[i + 1]
                sl_p = entry_p - sl_mult * c_atr
                tp_p = entry_p + tp_mult * c_atr
            elif bear_cross:
                pos = -1
                entry_i = i + 1
                entry_p = opens[i + 1]
                sl_p = entry_p + sl_mult * c_atr
                tp_p = entry_p - tp_mult * c_atr

    return trades

def evaluate_metrics(trades, total_months=72):
    if not trades:
        return {"total_trades": 0, "net_profit": 0.0, "pf": 0.0, "win_rate": 0.0, "max_dd": 0.0, "romad": 0.0, "mcr": 0.0}
    df = pd.DataFrame(trades)
    pnls = df["pnl"].values
    net_p = float(np.sum(pnls))
    wins = pnls[pnls > 0]
    losses = pnls[pnls < 0]
    gw = float(np.sum(wins)) if len(wins) > 0 else 0.0
    gl = float(abs(np.sum(losses))) if len(losses) > 0 else 1e-4
    pf = float(gw / gl)
    wr = float(len(wins) / len(pnls) * 100.0)

    eq = np.cumsum(pnls)
    pk = np.maximum.accumulate(eq)
    dd = pk - eq
    mdd = float(np.max(dd)) if len(dd) > 0 else 0.0
    romad = float(net_p / mdd) if mdd > 0 else 0.0

    monthly = df.groupby("month")["pnl"].sum().to_dict()
    pos_m = sum(1 for m, val in monthly.items() if val > 0.0)
    mcr = float(round(pos_m / total_months * 100.0, 2))
    tpy = float(round(len(trades) / (total_months / 12.0), 1))

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
    parser = argparse.ArgumentParser(description="Sweep Strategy 93: Tillson T3 Moving Average")
    parser.add_argument("--data_path", type=str, default="projects/quant_strategy_discovery/data/XAUUSD_H1.parquet")
    parser.add_argument("--out_dir", type=str, default="projects/quant_strategy_discovery/results")
    args = parser.parse_args()
    os.makedirs(args.out_dir, exist_ok=True)

    t0 = time.time()
    print("[*] Loading XAUUSD H1 Lightweight Parquet Cache...")
    df = pd.read_parquet(args.data_path)
    opens = df["open"].values.astype(np.float64)
    highs = df["high"].values.astype(np.float64)
    lows = df["low"].values.astype(np.float64)
    closes = df["close"].values.astype(np.float64)
    dates = df.index
    months = (dates.year.values * 100 + dates.month.values).astype(np.int32)

    print("[*] Precomputing Technical Indicators (ATR, EMA200, KFD)...")
    atr14 = compute_atr(highs, lows, closes, 14)
    ema200 = compute_ema(closes, 200)
    kfd24 = compute_katz_fractal_dimension(closes, atr14, 24)

    t3_periods = [10, 14, 20]
    v_factors = [0.7]
    tp_mults = [3.5, 4.0, 4.5]
    sl_mults = [2.0, 2.5]
    kfd_threshs = [1.40, 1.45]
    profit_locks = [200.0, 250.0]

    t3_dict = {}
    for p in t3_periods:
        for v in v_factors:
            t3_dict[(p, v)] = compute_tillson_t3(closes, period=p, v=v)

    results = []
    print("[*] Running Targeted Parameter Grid Sweep (36 Configurations)...")
    for p in t3_periods:
        for v in v_factors:
            t3_series = t3_dict[(p, v)]
            for tp in tp_mults:
                for sl_m in sl_mults:
                    for kfd_t in kfd_threshs:
                        for plock in profit_locks:
                            trades = simulate_t3_strategy(
                                opens=opens, highs=highs, lows=lows, closes=closes,
                                atr14=atr14, ema200=ema200, kfd=kfd24, t3=t3_series,
                                months=months, dates=dates,
                                use_kfd=True, kfd_thresh=kfd_t,
                                tp_mult=tp, sl_mult=sl_m,
                                monthly_profit_lock=plock, monthly_loss_breaker=250.0
                            )
                            m = evaluate_metrics(trades)
                            cfg = {
                                "t3_period": p, "v_factor": v,
                                "tp_mult": tp, "sl_mult": sl_m,
                                "kfd_thresh": kfd_t, "monthly_profit_lock": plock
                            }
                            results.append({**cfg, **m})

    df_res = pd.DataFrame(results)
    out_csv = os.path.join(args.out_dir, "strategy_93_t3_sweep_results.csv")
    df_res.to_csv(out_csv, index=False)
    print(f"[+] Saved {len(df_res)} sweep configurations to {out_csv}")

    df_cand = df_res[(df_res["total_trades"] >= 60) & (df_res["net_profit"] > 0)].copy()
    if not df_cand.empty:
        df_cand.sort_values(by=["pf", "net_profit"], ascending=[False, False], inplace=True)
        top5 = df_cand.head(5)
        print("\n" + "=" * 95)
        print("TOP 5 PERFORMING CONFIGURATIONS - STRATEGY 93: GOLD H1 TILLSON T3")
        print("=" * 95)
        print(top5[["t3_period", "tp_mult", "sl_mult", "kfd_thresh", "monthly_profit_lock", "total_trades", "trades_per_year", "net_profit", "pf", "max_dd", "romad", "mcr"]].to_string(index=False))
        print("=" * 95)

        champ = top5.iloc[0].to_dict()
        champ_file = os.path.join(args.out_dir, "strategy_93_champion.json")
        with open(champ_file, "w") as f:
            json.dump({
                "strategy_id": "STRATEGY_93",
                "strategy_name": "Gold H1 Tillson T3 Moving Average Adaptive Trend (T3-KFD)",
                "champion_metrics": champ,
                "runtime_seconds": round(time.time() - t0, 2)
            }, f, indent=2)
        print(f"[+] Saved Strategy 93 Champion to {champ_file}")

    del df
    gc.collect()

if __name__ == "__main__":
    main()
