#!/usr/bin/env python3
"""
===============================================================================
STRATEGY 51: GOLD H1 COMMODITY CHANNEL INDEX & FRACTAL EXPANSION (CCI-KFD)
===============================================================================
Asset: XAUUSD CFD (2020 - 2025, 72 Calendar Months)
Timeframe: H1 (Resampled from raw M1 high-resolution data)

Quantitative Hypothesis & Architectural Logic:
1. Commodity-Specific Statistical Momentum (Donald Lambert CCI):
   - Gold is a physical commodity prone to cyclical momentum surges.
   - CCI measures deviation from statistical mean:
     CCI = (TypicalPrice - SMA(TP, n)) / (0.015 * MeanDeviation(TP, n))
   - A cross above +100 / +120 confirms institutional momentum breakout.
   - A cross below -100 / -120 confirms institutional selloff impulse.
2. Katz Fractal Horizon Gate (KFD):
   - Only take CCI breakout entries when Katz Fractal Dimension D <= 1.35 - 1.40 
     (filtering out noisy sideways chop).
3. Macro Trend Alignment:
   - Close relative to EMA200 baseline.
4. Asymmetric Payoff & ASAR Governance:
   - 3.5R to 4.5R Take Profit with 1.5R to 2.0R Stop Loss.
   - Monthly profit locks ($200 - $300) and loss breakers ($250).
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

def compute_ema(series: np.ndarray, span: int) -> np.ndarray:
    n = len(series)
    ema = np.zeros(n, dtype=np.float64)
    alpha = 2.0 / (span + 1.0)
    ema[0] = series[0]
    for i in range(1, n):
        ema[i] = (series[i] * alpha) + (ema[i - 1] * (1.0 - alpha))
    return ema

def compute_cci(highs: np.ndarray, lows: np.ndarray, closes: np.ndarray, period: int = 20) -> np.ndarray:
    tp = (highs + lows + closes) / 3.0
    s_tp = pd.Series(tp)
    sma_tp = s_tp.rolling(period).mean().values
    
    # Mean absolute deviation
    def mad(window):
        return np.mean(np.abs(window - np.mean(window)))
    
    # Fast rolling mean deviation using rolling apply or series
    dev = s_tp.rolling(period).apply(lambda x: np.mean(np.abs(x - np.mean(x))), raw=True).values
    dev = np.where(dev <= 0, 1e-6, dev)
    
    cci = (tp - sma_tp) / (0.015 * dev)
    cci = np.nan_to_num(cci, nan=0.0)
    return cci

def compute_katz_fractal_dimension(closes: np.ndarray, atr14: np.ndarray, window: int = 24) -> np.ndarray:
    n = len(closes)
    kfd = np.full(n, 1.5, dtype=np.float64)
    s_c = pd.Series(closes)
    
    roll_max = s_c.rolling(window).max().values
    roll_min = s_c.rolling(window).min().values
    d = roll_max - roll_min
    
    diffs = np.abs(np.diff(closes, prepend=closes[0]))
    l_sum = pd.Series(diffs).rolling(window).sum().values
    
    log_w = np.log10(float(window))
    for i in range(window, n):
        if l_sum[i] > 0 and d[i] > 0:
            a = l_sum[i] / float(window)
            ratio = d[i] / l_sum[i]
            if ratio > 0:
                kfd[i] = np.log10(float(window)) / (np.log10(float(window)) + np.log10(ratio))
                kfd[i] = max(1.0, min(kfd[i], 2.0))
    return np.nan_to_num(kfd, nan=1.5)

def load_and_resample_gold_h1() -> pd.DataFrame:
    data_path = "/mnt/sdcard/Download/EA/XAUUSD_M1.csv.gz"
    alt_path = "/root/CFD-Trading-ML/data/XAUUSD_M1.csv.gz"

    path_to_use = data_path if os.path.exists(data_path) else alt_path
    if not os.path.exists(path_to_use):
        raise FileNotFoundError(f"Gold M1 data not found at {path_to_use}")

    print(f"[*] Loading Gold M1 data from {path_to_use}...")
    df_raw = pd.read_csv(
        path_to_use,
        usecols=["datetime", "open", "high", "low", "close"],
        dtype={"open": np.float32, "high": np.float32, "low": np.float32, "close": np.float32}
    )
    df_raw["datetime"] = pd.to_datetime(df_raw["datetime"])
    df_raw.set_index("datetime", inplace=True)
    df_raw.sort_index(inplace=True)

    print("[*] Resampling to H1 timeframe...")
    df_h1 = df_raw.resample("1h").agg({
        "open": "first", "high": "max", "low": "min", "close": "last"
    }).dropna()

    df_h1 = df_h1[(df_h1.index >= "2020-01-01") & (df_h1.index < "2026-01-01")]
    print(f"[+] Loaded {len(df_h1):,} Gold H1 bars (2020 - 2025).")
    return df_h1

def simulate_strategy_51(
    opens: np.ndarray,
    highs: np.ndarray,
    lows: np.ndarray,
    closes: np.ndarray,
    atr14: np.ndarray,
    ema200: np.ndarray,
    cci: np.ndarray,
    kfd: np.ndarray,
    months: np.ndarray,
    dates: pd.DatetimeIndex,
    cci_threshold: float = 100.0,
    use_kfd: bool = True,
    kfd_thresh: float = 1.35,
    tp_mult: float = 4.0,
    sl_mult: float = 2.0,
    monthly_profit_lock: float = 250.0,
    monthly_loss_breaker: float = 250.0,
    defensive_thresh: float = 120.0,
    defensive_lot_mult: float = 0.25,
    spread: float = 0.25,
    commission_per_unit: float = 0.06,
    base_unit_size: float = 10.0,
    warmup: int = 250
):
    n = len(closes)
    trades = []

    pos = 0
    entry_p = 0.0
    sl_p = 0.0
    tp_p = 0.0
    curr_unit_size = base_unit_size

    curr_month = None
    month_cum_pnl = 0.0
    month_locked = False

    for i in range(warmup, n - 1):
        m_key = months[i]
        c_atr = atr14[i]

        if m_key != curr_month:
            curr_month = m_key
            month_cum_pnl = 0.0
            month_locked = False
            curr_unit_size = base_unit_size

        # 1. Manage Exits
        if pos == 1:
            exit_triggered = False
            exit_p = 0.0
            if lows[i] <= sl_p:
                exit_p = sl_p if opens[i] >= sl_p else opens[i]
                exit_triggered = True
            elif highs[i] >= tp_p:
                exit_p = tp_p if opens[i] <= tp_p else opens[i]
                exit_triggered = True

            if exit_triggered:
                pnl = (exit_p - entry_p) * curr_unit_size - (spread + commission_per_unit) * curr_unit_size
                trades.append({"pnl": pnl, "date": dates[i], "engine": "GOLD_H1_CCI", "month": m_key})
                month_cum_pnl += pnl
                pos = 0

                if monthly_profit_lock > 0 and month_cum_pnl >= monthly_profit_lock:
                    month_locked = True
                elif monthly_loss_breaker > 0 and month_cum_pnl <= -monthly_loss_breaker:
                    month_locked = True
                elif defensive_thresh > 0 and month_cum_pnl <= -defensive_thresh:
                    curr_unit_size = base_unit_size * defensive_lot_mult

        elif pos == -1:
            exit_triggered = False
            exit_p = 0.0
            if highs[i] >= sl_p:
                exit_p = sl_p if opens[i] <= sl_p else opens[i]
                exit_triggered = True
            elif lows[i] <= tp_p:
                exit_p = tp_p if opens[i] >= tp_p else opens[i]
                exit_triggered = True

            if exit_triggered:
                pnl = (entry_p - exit_p) * curr_unit_size - (spread + commission_per_unit) * curr_unit_size
                trades.append({"pnl": pnl, "date": dates[i], "engine": "GOLD_H1_CCI", "month": m_key})
                month_cum_pnl += pnl
                pos = 0

                if monthly_profit_lock > 0 and month_cum_pnl >= monthly_profit_lock:
                    month_locked = True
                elif monthly_loss_breaker > 0 and month_cum_pnl <= -monthly_loss_breaker:
                    month_locked = True
                elif defensive_thresh > 0 and month_cum_pnl <= -defensive_thresh:
                    curr_unit_size = base_unit_size * defensive_lot_mult

        # 2. Check Entries for Bar i+1 Open
        if pos == 0 and not month_locked:
            kfd_ok = (not use_kfd) or (kfd[i] <= kfd_thresh)
            
            # Bullish cross above +cci_threshold
            bull_cross = (cci[i] >= cci_threshold) and (cci[i - 1] < cci_threshold) and (closes[i] > ema200[i]) and kfd_ok
            # Bearish cross below -cci_threshold
            bear_cross = (cci[i] <= -cci_threshold) and (cci[i - 1] > -cci_threshold) and (closes[i] < ema200[i]) and kfd_ok

            if bull_cross:
                pos = 1
                entry_p = opens[i + 1]
                sl_p = entry_p - sl_mult * c_atr
                tp_p = entry_p + tp_mult * c_atr
            elif bear_cross:
                pos = -1
                entry_p = opens[i + 1]
                sl_p = entry_p + sl_mult * c_atr
                tp_p = entry_p - tp_mult * c_atr

    if len(trades) == 0:
        return {
            "total_trades": 0, "net_profit": 0.0, "pf": 0.0, "win_rate": 0.0,
            "max_dd": 0.0, "mcr": 0.0, "pos_months": 0, "total_months": 72
        }

    df_tr = pd.DataFrame(trades)
    net_profit = df_tr["pnl"].sum()
    gross_win = df_tr[df_tr["pnl"] > 0]["pnl"].sum()
    gross_loss = abs(df_tr[df_tr["pnl"] < 0]["pnl"].sum())
    pf = (gross_win / gross_loss) if gross_loss > 0 else (99.0 if gross_win > 0 else 0.0)
    win_rate = (len(df_tr[df_tr["pnl"] > 0]) / len(df_tr)) * 100.0

    cum = df_tr["pnl"].cumsum()
    peak = cum.cummax()
    max_dd = (peak - cum).max()

    m_pnl = df_tr.groupby("month")["pnl"].sum()
    pos_m = (m_pnl > 0).sum()
    mcr = (pos_m / 72.0) * 100.0

    return {
        "total_trades": len(df_tr),
        "net_profit": round(float(net_profit), 2),
        "pf": round(float(pf), 3),
        "win_rate": round(float(win_rate), 2),
        "max_dd": round(float(max_dd), 2),
        "mcr": round(float(mcr), 2),
        "pos_months": int(pos_m),
        "total_months": 72
    }

def main():
    t0 = time.time()
    df_h1 = load_and_resample_gold_h1()

    opens = df_h1["open"].values.astype(np.float64)
    highs = df_h1["high"].values.astype(np.float64)
    lows = df_h1["low"].values.astype(np.float64)
    closes = df_h1["close"].values.astype(np.float64)
    dates = df_h1.index
    months = np.array([f"{d.year}-{d.month:02d}" for d in dates])

    print("[*] Pre-computing baseline indicators...")
    atr14 = compute_atr(highs, lows, closes, period=14)
    ema200 = compute_ema(closes, span=200)
    kfd24 = compute_katz_fractal_dimension(closes, atr14, window=24)
    cci20 = compute_cci(highs, lows, closes, period=20)

    # Parametric sweep
    cci_thresholds = [80.0, 100.0, 120.0, 150.0]
    kfd_options = [(True, 1.35), (True, 1.40), (False, 1.40)]
    tp_mults = [3.0, 3.5, 4.0, 4.5]
    sl_mults = [1.5, 2.0]
    profit_locks = [200.0, 250.0, 300.0]

    results = []
    print("[*] Calibrating Strategy 51 across parametric combinations...")

    for ct in cci_thresholds:
        for use_kfd, kfd_th in kfd_options:
            for tpm in tp_mults:
                for slm in sl_mults:
                    for pl in profit_locks:
                        res = simulate_strategy_51(
                            opens=opens,
                            highs=highs,
                            lows=lows,
                            closes=closes,
                            atr14=atr14,
                            ema200=ema200,
                            cci=cci20,
                            kfd=kfd24,
                            months=months,
                            dates=dates,
                            cci_threshold=ct,
                            use_kfd=use_kfd,
                            kfd_thresh=kfd_th,
                            tp_mult=tpm,
                            sl_mult=slm,
                            monthly_profit_lock=pl,
                            monthly_loss_breaker=250.0,
                            defensive_thresh=120.0,
                            defensive_lot_mult=0.25
                        )
                        res.update({
                            "cci_threshold": ct,
                            "use_kfd": use_kfd,
                            "kfd_thresh": kfd_th,
                            "tp_mult": tpm,
                            "sl_mult": slm,
                            "profit_lock": pl
                        })
                        results.append(res)

    df_res = pd.DataFrame(results)
    out_csv = "projects/quant_strategy_discovery/results/strategy_51_cci_momentum_sweep_results.csv"
    os.makedirs(os.path.dirname(out_csv), exist_ok=True)
    df_res.to_csv(out_csv, index=False)
    print(f"[+] Saved Strategy 51 sweep results to {out_csv}")

    df_sorted = df_res.sort_values(by="pf", ascending=False)
    best = df_sorted.iloc[0]

    print("\n" + "=" * 80)
    print("STRATEGY 51: GOLD H1 CCI MOMENTUM & FRACTAL EXPANSION CHAMPION RESULTS")
    print("=" * 80)
    print(f"Top Configuration:")
    print(f"  - CCI Threshold: {best['cci_threshold']}")
    print(f"  - KFD Filter Enabled: {best['use_kfd']} (Threshold: {best['kfd_thresh']})")
    print(f"  - TP Multiplier: {best['tp_mult']}R | SL Multiplier: {best['sl_mult']}R")
    print(f"  - Monthly Profit Lock: ${best['profit_lock']}")
    print("-" * 80)
    print("Performance Metrics Across 72 Calendar Months (2020 - 2025):")
    print(f"  - Total Trades: {int(best['total_trades'])}")
    print(f"  - Net Profit: ${best['net_profit']:,.2f}")
    print(f"  - Profit Factor (PF): {best['pf']:.3f}")
    print(f"  - Win Rate: {best['win_rate']:.2f}%")
    print(f"  - Max Drawdown: ${best['max_dd']:,.2f}")
    print(f"  - Monthly Consistency Ratio (MCR): {best['mcr']:.2f}% ({int(best['pos_months'])}/72 profitable months)")
    print(f"Sweep Execution Time: {time.time() - t0:.2f}s")
    print("=" * 80)

    print("\nTop 5 Distinct Configurations:")
    print(df_sorted[["cci_threshold", "use_kfd", "kfd_thresh", "tp_mult", "sl_mult", "profit_lock", "pf", "net_profit", "win_rate", "max_dd", "mcr", "total_trades"]].head(5).to_string())

if __name__ == "__main__":
    main()
