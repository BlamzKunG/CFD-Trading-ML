#!/usr/bin/env python3
"""
===============================================================================
STRATEGY 46: GOLD H1 CHOPPINESS INDEX & CHANDE MOMENTUM EXPANSION (CHOP-CMO)
===============================================================================
Asset: XAUUSD CFD (2020 - 2025, 72 Calendar Months)
Timeframe: H1 (Resampled from raw M1 high-resolution data)

Quantitative Hypothesis & Architectural Logic:
1. Choppiness Index (CHOP / CI) Entropy Gating:
   - Measures market dimensionality:
     CI = 100 * LOG10(Sum(TR, n) / (Max(High, n) - Min(Low, n))) / LOG10(n)
   - When CI > 61.8, the market is in high-entropy chop (whipsaw zone).
   - When CI < 38.2 - 48.0, the market has compressed and transitioned into 
     a low-entropy, persistent directional trending impulse.
2. Chande Momentum Oscillator (CMO):
   - Confirms directional thrust (|CMO| >= 10.0 - 20.0).
3. Structural Channel Breakout:
   - Price breaking above/below the 20-period Donchian/EMA channel.
4. Macro Trend Alignment:
   - Close relative to EMA200 baseline.
5. Asymmetric Payoff & ASAR Governance:
   - Dynamic ATR-based Stop Loss and Take Profit (3.0R - 4.0R).
   - Monthly profit locks and defensive drawdown sizing.
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

def compute_cmo(closes: np.ndarray, period: int = 14) -> np.ndarray:
    n = len(closes)
    diff = np.diff(closes, prepend=closes[0])
    up = np.where(diff > 0, diff, 0.0)
    down = np.where(diff < 0, -diff, 0.0)

    rolling_up = pd.Series(up).rolling(period).sum().values
    rolling_down = pd.Series(down).rolling(period).sum().values

    sum_all = rolling_up + rolling_down
    sum_all = np.where(sum_all == 0, 1e-6, sum_all)
    cmo = 100.0 * (rolling_up - rolling_down) / sum_all
    return cmo

def compute_choppiness_index(highs: np.ndarray, lows: np.ndarray, closes: np.ndarray, period: int = 14) -> np.ndarray:
    n = len(closes)
    tr = np.zeros(n, dtype=np.float64)
    tr[0] = highs[0] - lows[0]
    for i in range(1, n):
        hl = highs[i] - lows[i]
        hc = abs(highs[i] - closes[i - 1])
        lc = abs(lows[i] - closes[i - 1])
        tr[i] = max(hl, max(hc, lc))

    sum_tr = pd.Series(tr).rolling(period).sum().values
    roll_high = pd.Series(highs).rolling(period).max().values
    roll_low = pd.Series(lows).rolling(period).min().values

    rng = roll_high - roll_low
    rng = np.where(rng <= 0, 1e-6, rng)

    ratio = sum_tr / rng
    ratio = np.where(ratio <= 0, 1e-6, ratio)

    log_period = np.log10(float(period))
    ci = 100.0 * (np.log10(ratio) / log_period)
    ci = np.nan_to_num(ci, nan=50.0)
    return ci

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
        "open": "first",
        "high": "max",
        "low": "min",
        "close": "last"
    }).dropna()

    # Filter to 2020 - 2025 (72 months)
    df_h1 = df_h1[(df_h1.index >= "2020-01-01") & (df_h1.index < "2026-01-01")]
    print(f"[+] Loaded {len(df_h1):,} Gold H1 bars (2020 - 2025).")
    return df_h1

def simulate_strategy_46(
    opens: np.ndarray,
    highs: np.ndarray,
    lows: np.ndarray,
    closes: np.ndarray,
    atr14: np.ndarray,
    ema200: np.ndarray,
    ci: np.ndarray,
    cmo: np.ndarray,
    high20: np.ndarray,
    low20: np.ndarray,
    months: np.ndarray,
    dates: pd.DatetimeIndex,
    chop_thresh: float = 48.0,
    cmo_thresh: float = 15.0,
    trend_tp_mult: float = 3.5,
    trend_sl_mult: float = 2.0,
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

        # 1. Check Exits on Bar i
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
                trades.append({"pnl": pnl, "date": dates[i], "engine": "GOLD_H1_CHOP_CMO", "month": m_key})
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
                trades.append({"pnl": pnl, "date": dates[i], "engine": "GOLD_H1_CHOP_CMO", "month": m_key})
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
            # Choppiness Index Filter: Must be below threshold (non-choppy trending state)
            chop_ok = ci[i] <= chop_thresh

            if chop_ok:
                # Long Signal:
                # 1. Close above EMA200
                # 2. CMO bullish above +cmo_thresh
                # 3. Close breakout above 20-period highest close
                long_signal = (
                    closes[i] > ema200[i] and
                    cmo[i] >= cmo_thresh and
                    closes[i] >= high20[i]
                )

                # Short Signal:
                # 1. Close below EMA200
                # 2. CMO bearish below -cmo_thresh
                # 3. Close breakout below 20-period lowest close
                short_signal = (
                    closes[i] < ema200[i] and
                    cmo[i] <= -cmo_thresh and
                    closes[i] <= low20[i]
                )

                if long_signal:
                    pos = 1
                    entry_p = opens[i + 1]
                    sl_p = entry_p - trend_sl_mult * c_atr
                    tp_p = entry_p + trend_tp_mult * c_atr
                elif short_signal:
                    pos = -1
                    entry_p = opens[i + 1]
                    sl_p = entry_p + trend_sl_mult * c_atr
                    tp_p = entry_p - trend_tp_mult * c_atr

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

    opens = df_h1["open"].values
    highs = df_h1["high"].values
    lows = df_h1["low"].values
    closes = df_h1["close"].values
    dates = df_h1.index
    months = np.array([f"{d.year}-{d.month:02d}" for d in dates])

    print("[*] Pre-computing baseline indicators...")
    atr14 = compute_atr(highs, lows, closes, period=14)
    ema200 = compute_ema(closes, span=200)
    ci14 = compute_choppiness_index(highs, lows, closes, period=14)
    cmo14 = compute_cmo(closes, period=14)

    high20 = pd.Series(closes).shift(1).rolling(20).max().values
    low20 = pd.Series(closes).shift(1).rolling(20).min().values

    # Sweep Parameters
    chop_thresholds = [38.2, 42.0, 45.0, 48.0, 52.0, 60.0]
    cmo_thresholds = [10.0, 15.0, 20.0]
    tp_mults = [3.0, 3.5, 4.0]
    sl_mults = [1.5, 2.0]
    profit_locks = [200.0, 250.0, 300.0]

    results = []
    print(f"[*] Calibrating Strategy 46 across parametric combinations...")

    for ct in chop_thresholds:
        for cmo_t in cmo_thresholds:
            for tp_m in tp_mults:
                for sl_m in sl_mults:
                    for pl in profit_locks:
                        res = simulate_strategy_46(
                            opens=opens,
                            highs=highs,
                            lows=lows,
                            closes=closes,
                            atr14=atr14,
                            ema200=ema200,
                            ci=ci14,
                            cmo=cmo14,
                            high20=high20,
                            low20=low20,
                            months=months,
                            dates=dates,
                            chop_thresh=ct,
                            cmo_thresh=cmo_t,
                            trend_tp_mult=tp_m,
                            trend_sl_mult=sl_m,
                            monthly_profit_lock=pl,
                            monthly_loss_breaker=250.0,
                            defensive_thresh=120.0,
                            defensive_lot_mult=0.25
                        )
                        res.update({
                            "chop_thresh": ct,
                            "cmo_thresh": cmo_t,
                            "tp_mult": tp_m,
                            "sl_mult": sl_m,
                            "profit_lock": pl
                        })
                        results.append(res)

    df_res = pd.DataFrame(results)
    out_csv = "projects/quant_strategy_discovery/results/strategy_46_choppiness_sweep_results.csv"
    os.makedirs(os.path.dirname(out_csv), exist_ok=True)
    df_res.to_csv(out_csv, index=False)
    print(f"[+] Saved Strategy 46 sweep results to {out_csv}")

    df_sorted = df_res.sort_values(by="pf", ascending=False)
    best = df_sorted.iloc[0]

    print("\n" + "=" * 80)
    print("STRATEGY 46: GOLD H1 CHOPPINESS INDEX & CHANDE MOMENTUM CHAMPION RESULTS")
    print("=" * 80)
    print(f"Top Configuration:")
    print(f"  - Choppiness Index Threshold: {best['chop_thresh']}")
    print(f"  - CMO Threshold: {best['cmo_thresh']}")
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
    print(df_sorted[["chop_thresh", "cmo_thresh", "tp_mult", "sl_mult", "profit_lock", "pf", "net_profit", "win_rate", "max_dd", "mcr", "total_trades"]].head(5).to_string())

if __name__ == "__main__":
    main()
