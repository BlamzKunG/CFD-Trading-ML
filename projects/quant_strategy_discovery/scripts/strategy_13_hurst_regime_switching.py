#!/usr/bin/env python3
"""
===============================================================================
STRATEGY 13: HURST EXPONENT & MULTI-FRACTAL REGIME SWITCHING (HE-MFRS)
===============================================================================
Institutional Quant Model based on Fractal Market Hypothesis (FMH)
Asset: XAUUSD CFD & EURUSD (2020 - 2025, 72 Calendar Months)
Timeframe: M15 (Resampled from M1)

Core Quantitative Hypothesis:
- Financial markets alternate between three distinct mathematical states:
  1. Persistent Trending (Hurst Exponent H > 0.55): Strong directional memory.
     -> Strategy executes Momentum Trend Breakouts.
  2. Anti-Persistent Mean-Reverting (Hurst Exponent H < 0.45): Reversal memory.
     -> Strategy executes Boundary Fading (Mean-Reversion).
  3. Random Walk / Brownian Noise (0.45 <= H <= 0.55): Independent increments.
     -> Strategy stays completely FLAT (filters out 100% of choppy whipsaws).
- Target: Maximizing Monthly Consistency Ratio (MCR) by never trading when H indicates pure noise!
===============================================================================
"""

import os
import sys
import time
import json
import argparse
import numpy as np
import pandas as pd

def compute_atr(highs: np.ndarray, lows: np.ndarray, closes: np.ndarray, period: int = 14) -> np.ndarray:
    n = len(closes)
    tr = np.zeros(n, dtype=np.float64)
    tr[0] = highs[0] - lows[0]
    for i in range(1, n):
        hl = highs[i] - lows[i]
        hc = abs(highs[i] - closes[i - 1])
        lc = abs(lows[i] - closes[i - 1])
        tr[i] = max(hl, max(hc, lc))
    atr = np.zeros(n, dtype=np.float64)
    atr[period - 1] = np.mean(tr[:period])
    alpha = 1.0 / period
    for i in range(period, n):
        atr[i] = (tr[i] * alpha) + (atr[i - 1] * (1.0 - alpha))
    return atr

def compute_rolling_hurst(series: np.ndarray, window: int = 100) -> np.ndarray:
    """
    Computes fast rolling Hurst Exponent via simplified Rescaled Range (R/S) approximation.
    """
    n = len(series)
    hurst = np.full(n, 0.50, dtype=np.float64)
    
    # Precalculate log prices
    log_p = np.log(np.maximum(series, 1e-4))
    
    # Sub-lags for R/S
    lags = [10, 25, 50]
    log_lags = np.log(lags)
    
    for i in range(window, n):
        chunk = log_p[i - window:i]
        rs_vals = []
        
        for lag in lags:
            # Segment into sub-chunks of length lag
            num_sub = window // lag
            rs_sub = []
            for s in range(num_sub):
                sub = chunk[s * lag:(s + 1) * lag]
                m = np.mean(sub)
                dev = sub - m
                cum_dev = np.cumsum(dev)
                r = np.max(cum_dev) - np.min(cum_dev)
                s_std = np.std(sub)
                if s_std > 1e-8:
                    rs_sub.append(r / s_std)
            if len(rs_sub) > 0:
                rs_vals.append(np.mean(rs_sub))
            else:
                rs_vals.append(1.0)
                
        # Fit log(RS) = H * log(lag) + C
        log_rs = np.log(np.maximum(rs_vals, 1e-4))
        # Simple linear regression slope
        cov = np.cov(log_lags, log_rs)[0, 1]
        var = np.var(log_lags)
        h = cov / var if var > 1e-8 else 0.50
        # Clip to valid theoretical bounds [0.05, 0.95]
        hurst[i] = np.clip(h, 0.05, 0.95)
        
    return hurst

def simulate_hurst_strategy(
    opens: np.ndarray,
    highs: np.ndarray,
    lows: np.ndarray,
    closes: np.ndarray,
    atr14: np.ndarray,
    hurst: np.ndarray,
    dates: pd.DatetimeIndex,
    h_trend_thresh: float,      # 0.55, 0.60
    h_rev_thresh: float,        # 0.40, 0.45
    trend_tp_mult: float,       # 3.0, 4.0
    sl_atr_mult: float,         # 2.0, 2.5
    spread: float = 0.25,
    commission_per_unit: float = 0.06,
    unit_size: float = 10.0,
    warmup: int = 150
):
    n = len(closes)
    trades = []

    # 20 SMA & StdDev for Reversion mode
    sma20 = pd.Series(closes).rolling(20).mean().values
    std20 = pd.Series(closes).rolling(20).std().values
    upper_bb = sma20 + 2.0 * std20
    lower_bb = sma20 - 2.0 * std20

    pos = 0 # 0: flat, 1: long, -1: short
    entry_p = 0.0
    sl_p = 0.0
    tp_p = 0.0
    entry_i = 0
    mode = ""

    for i in range(warmup, n - 1):
        c_atr = atr14[i]
        h_val = hurst[i]

        # 1. Manage Exits
        if pos == 1:
            exit_triggered = False
            exit_p = 0.0
            if lows[i] <= sl_p:
                exit_p = sl_p if opens[i] >= sl_p else opens[i]
                exit_triggered = True
            elif mode == "TREND" and highs[i] >= tp_p:
                exit_p = tp_p if opens[i] <= tp_p else opens[i]
                exit_triggered = True
            elif mode == "REVERSION" and highs[i] >= sma20[i]:
                exit_p = sma20[i] if opens[i] <= sma20[i] else opens[i]
                exit_triggered = True

            if exit_triggered:
                pnl = (exit_p - entry_p) * unit_size - (spread + commission_per_unit) * unit_size
                trades.append({
                    "pnl": pnl, "entry_bar": entry_i, "exit_bar": i,
                    "date": dates[i], "mode": mode, "type": "BUY"
                })
                pos = 0

        elif pos == -1:
            exit_triggered = False
            exit_p = 0.0
            if highs[i] >= sl_p:
                exit_p = sl_p if opens[i] <= sl_p else opens[i]
                exit_triggered = True
            elif mode == "TREND" and lows[i] <= tp_p:
                exit_p = tp_p if opens[i] >= tp_p else opens[i]
                exit_triggered = True
            elif mode == "REVERSION" and lows[i] <= sma20[i]:
                exit_p = sma20[i] if opens[i] >= sma20[i] else opens[i]
                exit_triggered = True

            if exit_triggered:
                pnl = (entry_p - exit_p) * unit_size - (spread + commission_per_unit) * unit_size
                trades.append({
                    "pnl": pnl, "entry_bar": entry_i, "exit_bar": i,
                    "date": dates[i], "mode": mode, "type": "SELL"
                })
                pos = 0

        # 2. Check Entries
        if pos == 0 and c_atr > 0.0:
            # ---------------------------------------------------------
            # REGIME 1: PERSISTENT TRENDING (H > h_trend_thresh)
            # ---------------------------------------------------------
            if h_val >= h_trend_thresh:
                # 10-bar breakout
                h10 = np.max(highs[i - 10:i])
                l10 = np.min(lows[i - 10:i])

                if closes[i] > h10:
                    pos = 1
                    entry_p = opens[i + 1] + (spread * 0.5)
                    sl_dist = sl_atr_mult * c_atr
                    sl_p = entry_p - sl_dist
                    tp_p = entry_p + (sl_dist * trend_tp_mult)
                    entry_i = i + 1
                    mode = "TREND"
                    continue
                elif closes[i] < l10:
                    pos = -1
                    entry_p = opens[i + 1] - (spread * 0.5)
                    sl_dist = sl_atr_mult * c_atr
                    sl_p = entry_p + sl_dist
                    tp_p = entry_p - (sl_dist * trend_tp_mult)
                    entry_i = i + 1
                    mode = "TREND"
                    continue

            # ---------------------------------------------------------
            # REGIME 2: ANTI-PERSISTENT MEAN REVERSION (H < h_rev_thresh)
            # ---------------------------------------------------------
            elif h_val <= h_rev_thresh:
                if lows[i] < lower_bb[i] and closes[i] > lower_bb[i]:
                    pos = 1
                    entry_p = opens[i + 1] + (spread * 0.5)
                    sl_p = entry_p - (sl_atr_mult * c_atr)
                    entry_i = i + 1
                    mode = "REVERSION"
                    continue
                elif highs[i] > upper_bb[i] and closes[i] < upper_bb[i]:
                    pos = -1
                    entry_p = opens[i + 1] - (spread * 0.5)
                    sl_p = entry_p + (sl_atr_mult * c_atr)
                    entry_i = i + 1
                    mode = "REVERSION"
                    continue

            # ---------------------------------------------------------
            # REGIME 3: BROWNIAN NOISE (h_rev_thresh < H < h_trend_thresh)
            # -> STAY 100% FLAT (Do not trade!)
            # ---------------------------------------------------------

    return trades

def evaluate_monthly_consistency(trades: list) -> dict:
    if len(trades) < 20:
        return {
            "total_trades": len(trades), "net_profit": 0.0, "pf": 0.0,
            "win_rate": 0.0, "max_dd": 0.0, "mcr": 0.0,
            "total_months": 0, "pos_months": 0, "neg_months": 0
        }

    df_t = pd.DataFrame(trades)
    df_t["year_month"] = pd.to_datetime(df_t["date"]).dt.to_period("M")

    pnls = df_t["pnl"].values
    wins = pnls[pnls > 0]
    losses = pnls[pnls < 0]
    gp = float(np.sum(wins)) if len(wins) > 0 else 0.0
    gl = float(abs(np.sum(losses))) if len(losses) > 0 else 0.0
    net = float(np.sum(pnls))
    pf = (gp / gl) if gl > 0 else 99.0
    wr = (len(wins) / len(pnls)) * 100.0

    eq = 10000.0 + np.cumsum(pnls)
    peaks = np.maximum.accumulate(eq)
    max_dd = float(np.max(peaks - eq)) if len(eq) > 0 else 0.0

    monthly_pnl = df_t.groupby("year_month")["pnl"].sum()
    total_months = len(monthly_pnl)
    pos_months = int(np.sum(monthly_pnl > 0))
    neg_months = int(np.sum(monthly_pnl <= 0))
    mcr = (pos_months / total_months * 100.0) if total_months > 0 else 0.0

    return {
        "total_trades": len(trades),
        "net_profit": round(net, 2),
        "pf": round(pf, 3),
        "win_rate": round(wr, 2),
        "max_dd": round(max_dd, 2),
        "mcr": round(mcr, 2),
        "total_months": total_months,
        "pos_months": pos_months,
        "neg_months": neg_months
    }

def main():
    parser = argparse.ArgumentParser(description="Sweep Strategy 13: Hurst Exponent & Multi-Fractal Regime Switching")
    parser.add_argument("--data", type=str, default="/mnt/sdcard/Download/EA/XAUUSD_M1.csv.gz", help="Path to M1 data")
    parser.add_argument("--out_dir", type=str, default="/root/CFD-Trading-ML/projects/quant_strategy_discovery/results", help="Results dir")
    args = parser.parse_args()

    os.makedirs(args.out_dir, exist_ok=True)

    print(f"[*] Loading M1 data from {args.data}...")
    t0 = time.time()
    df_raw = pd.read_csv(
        args.data,
        usecols=["datetime", "open", "high", "low", "close", "tick_volume"],
        dtype={"open": np.float32, "high": np.float32, "low": np.float32, "close": np.float32, "tick_volume": np.int32}
    )
    df_raw["datetime"] = pd.to_datetime(df_raw["datetime"])
    df_raw.set_index("datetime", inplace=True)
    df_raw.sort_index(inplace=True)

    print(f"[*] Resampling to M15 timeframe...")
    df_m15 = df_raw.resample("15min").agg({
        "open": "first", "high": "max", "low": "min", "close": "last", "tick_volume": "sum"
    }).dropna()
    print(f"[+] Resampled M15 bars: {len(df_m15):,} bars.")

    opens = df_m15["open"].values.astype(np.float64)
    highs = df_m15["high"].values.astype(np.float64)
    lows = df_m15["low"].values.astype(np.float64)
    closes = df_m15["close"].values.astype(np.float64)
    dates = df_m15.index

    print("[*] Precomputing ATR(14) and Rolling Hurst Exponent (window=100)...")
    atr14 = compute_atr(highs, lows, closes, 14)
    t_h = time.time()
    hurst = compute_rolling_hurst(closes, window=100)
    print(f"[+] Hurst Exponent computed in {time.time()-t_h:.2f}s. Mean H: {np.mean(hurst):.3f}")

    # Parameter grid for mass sweep
    h_trend_threshs = [0.55, 0.58, 0.62]
    h_rev_threshs = [0.42, 0.45, 0.48]
    trend_tp_mults = [2.5, 3.0, 4.0]
    sl_atr_mults = [1.5, 2.0, 2.5]

    # Total combinations = 3 * 3 * 3 * 3 = 81 sets
    total_combs = len(h_trend_threshs) * len(h_rev_threshs) * len(trend_tp_mults) * len(sl_atr_mults)
    print(f"[*] Sweeping {total_combs} Hurst regime combinations across 72 calendar months...")

    results = []
    c_idx = 0
    t_start = time.time()

    for htt in h_trend_threshs:
        for hrt in h_rev_threshs:
            for tpm in trend_tp_mults:
                for sam in sl_atr_mults:
                    c_idx += 1
                    trades = simulate_hurst_strategy(
                        opens, highs, lows, closes, atr14, hurst, dates,
                        h_trend_thresh=htt, h_rev_thresh=hrt,
                        trend_tp_mult=tpm, sl_atr_mult=sam
                    )
                    metrics = evaluate_monthly_consistency(trades)
                    metrics.update({
                        "h_trend_thresh": htt,
                        "h_rev_thresh": hrt,
                        "trend_tp_mult": tpm,
                        "sl_atr_mult": sam
                    })
                    results.append(metrics)

                    if c_idx % 20 == 0 or c_idx == total_combs:
                        print(f"[{c_idx}/{total_combs}] Completed ({c_idx/total_combs*100:.1f}%) | Elapsed: {time.time()-t_start:.1f}s")

    df_res = pd.DataFrame(results)
    csv_path = os.path.join(args.out_dir, "strategy_13_hurst_regime_sweep_results.csv")
    df_res.to_csv(csv_path, index=False)
    print(f"[+] Full sweep results saved to: {csv_path}")

    # Find champion: Prioritizing High MCR and Net Profit
    viable = df_res[(df_res["total_trades"] >= 200) & (df_res["pf"] >= 1.05)]
    if len(viable) > 0:
        champ = viable.sort_values(by=["mcr", "net_profit"], ascending=[False, False]).iloc[0]
    else:
        champ = df_res.sort_values(by=["net_profit"], ascending=[False]).iloc[0]

    champ_dict = champ.to_dict()
    json_path = os.path.join(args.out_dir, "strategy_13_hurst_regime_champion.json")
    with open(json_path, "w") as f:
        json.dump(champ_dict, f, indent=2)
    print(f"[+] Champion JSON saved to: {json_path}")

    print("\n" + "="*70)
    print("🏆 CHAMPION PARAMETER SET (STRATEGY 13: HURST REGIME SWITCHING)")
    print("="*70)
    for k, v in champ_dict.items():
        print(f"  {k}: {v}")
    print("="*70)

if __name__ == "__main__":
    main()
