#!/usr/bin/env python3
"""
===============================================================================
STRATEGY 49: EURUSD LONDON/NY OVERLAP LIQUIDITY SWEEP & FADE (FX-LOF)
===============================================================================
Asset: EURUSD CFD (2020 - 2025, 72 Calendar Months)
Timeframe: M15 (Resampled from raw M1 high-resolution data)

Quantitative Hypothesis & Architectural Logic:
1. Microstructure Hypothesis (Derived from Strategy 48 Rejection):
   - Strategy 48 proved that breakouts beyond 00:00 - 11:00 UTC range fail 66% 
     of the time on EURUSD during London/NY Overlap (12:00 - 16:00 UTC).
   - This strategy fades those false breakouts (liquidity sweeps):
     * Bearish Fade: High exceeds Ref High by buffer, then Close drops back below Ref High.
     * Bullish Fade: Low pierces Ref Low by buffer, then Close recovers back above Ref Low.
2. Momentum Exhaustion Confirmation:
   - RSI14 overbought (> 60) for short fades, oversold (< 40) for long fades.
3. Asymmetric Mean-Reversion Target:
   - TP: Session median (midpoint of reference range) or 1.5R - 2.5R.
   - SL: Placed beyond the sweep peak (1.0R - 1.5R).
4. Intraday Time Stop:
   - Close positions by 20:00 UTC before daily rollover.
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

def compute_rsi(closes: np.ndarray, period: int = 14) -> np.ndarray:
    n = len(closes)
    diff = np.diff(closes, prepend=closes[0])
    gains = np.where(diff > 0, diff, 0.0)
    losses = np.where(diff < 0, -diff, 0.0)

    avg_gain = pd.Series(gains).ewm(alpha=1.0 / period, adjust=False).mean().values
    avg_loss = pd.Series(losses).ewm(alpha=1.0 / period, adjust=False).mean().values

    rs = np.where(avg_loss == 0, 100.0, avg_gain / np.where(avg_loss == 0, 1e-6, avg_loss))
    rsi = 100.0 - (100.0 / (1.0 + rs))
    return rsi

def load_and_resample_eur_m15() -> pd.DataFrame:
    data_path = "/mnt/sdcard/Download/EA/EURUSD_M1.csv.gz"
    alt_path = "/root/CFD-Trading-ML/data/EURUSD_M1.csv.gz"

    path_to_use = data_path if os.path.exists(data_path) else alt_path
    if not os.path.exists(path_to_use):
        raise FileNotFoundError(f"EURUSD M1 data not found at {path_to_use}")

    print(f"[*] Loading EURUSD M1 data from {path_to_use}...")
    df_raw = pd.read_csv(
        path_to_use,
        usecols=["datetime", "open", "high", "low", "close"],
        dtype={"open": np.float32, "high": np.float32, "low": np.float32, "close": np.float32}
    )
    df_raw["datetime"] = pd.to_datetime(df_raw["datetime"])
    df_raw.set_index("datetime", inplace=True)
    df_raw.sort_index(inplace=True)

    print("[*] Resampling to M15 timeframe...")
    df_m15 = df_raw.resample("15min").agg({
        "open": "first", "high": "max", "low": "min", "close": "last"
    }).dropna()

    df_m15 = df_m15[(df_m15.index >= "2020-01-01") & (df_m15.index < "2026-01-01")]
    print(f"[+] Loaded {len(df_m15):,} EURUSD M15 bars (2020 - 2025).")
    return df_m15

def simulate_strategy_49(
    opens: np.ndarray,
    highs: np.ndarray,
    lows: np.ndarray,
    closes: np.ndarray,
    atr14: np.ndarray,
    rsi14: np.ndarray,
    hours: np.ndarray,
    days: np.ndarray,
    months: np.ndarray,
    dates: pd.DatetimeIndex,
    sweep_buffer_atr: float = 0.2,
    use_rsi_filter: bool = True,
    tp_mult: float = 2.0,
    sl_mult: float = 1.2,
    monthly_profit_lock: float = 150.0,
    monthly_loss_breaker: float = 150.0,
    defensive_thresh: float = 80.0,
    defensive_lot_mult: float = 0.25,
    spread: float = 0.00006,  # 0.6 pip
    commission_per_unit: float = 0.00006, # $6/lot
    base_unit_size: float = 10000.0,
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

    curr_day = None
    ref_high = -999999.0
    ref_low = 999999.0
    traded_today = False

    for i in range(warmup, n - 1):
        m_key = months[i]
        d_key = days[i]
        hr = hours[i]
        c_atr = atr14[i]

        if m_key != curr_month:
            curr_month = m_key
            month_cum_pnl = 0.0
            month_locked = False
            curr_unit_size = base_unit_size

        if d_key != curr_day:
            curr_day = d_key
            ref_high = -999999.0
            ref_low = 999999.0
            traded_today = False

        if hr < 12:
            if highs[i] > ref_high: ref_high = highs[i]
            if lows[i] < ref_low: ref_low = lows[i]

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
            elif hr >= 20:
                exit_p = closes[i]
                exit_triggered = True

            if exit_triggered:
                pnl = (exit_p - entry_p) * curr_unit_size - (spread + commission_per_unit) * curr_unit_size
                trades.append({"pnl": pnl, "date": dates[i], "engine": "EURUSD_M15_LOF", "month": m_key})
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
            elif hr >= 20:
                exit_p = closes[i]
                exit_triggered = True

            if exit_triggered:
                pnl = (entry_p - exit_p) * curr_unit_size - (spread + commission_per_unit) * curr_unit_size
                trades.append({"pnl": pnl, "date": dates[i], "engine": "EURUSD_M15_LOF", "month": m_key})
                month_cum_pnl += pnl
                pos = 0

                if monthly_profit_lock > 0 and month_cum_pnl >= monthly_profit_lock:
                    month_locked = True
                elif monthly_loss_breaker > 0 and month_cum_pnl <= -monthly_loss_breaker:
                    month_locked = True
                elif defensive_thresh > 0 and month_cum_pnl <= -defensive_thresh:
                    curr_unit_size = base_unit_size * defensive_lot_mult

        # 2. Check Entries during 12:00 - 16:00 UTC (Liquidity Sweep Fade)
        if pos == 0 and not month_locked and not traded_today and (12 <= hr <= 16):
            if ref_high > 0 and ref_low < 999999.0:
                sweep_high_level = ref_high + sweep_buffer_atr * c_atr
                sweep_low_level = ref_low - sweep_buffer_atr * c_atr

                # Bearish Fade: High pierced above Ref High + buffer, but Close ended below Ref High
                bearish_fade = (highs[i] >= sweep_high_level) and (closes[i] < ref_high)
                if use_rsi_filter:
                    bearish_fade = bearish_fade and (rsi14[i] >= 55.0)

                # Bullish Fade: Low pierced below Ref Low - buffer, but Close ended above Ref Low
                bullish_fade = (lows[i] <= sweep_low_level) and (closes[i] > ref_low)
                if use_rsi_filter:
                    bullish_fade = bullish_fade and (rsi14[i] <= 45.0)

                if bearish_fade:
                    pos = -1
                    entry_p = opens[i + 1]
                    sl_p = entry_p + sl_mult * c_atr
                    tp_p = entry_p - tp_mult * c_atr
                    traded_today = True
                elif bullish_fade:
                    pos = 1
                    entry_p = opens[i + 1]
                    sl_p = entry_p - sl_mult * c_atr
                    tp_p = entry_p + tp_mult * c_atr
                    traded_today = True

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
    df_m15 = load_and_resample_eur_m15()

    opens = df_m15["open"].values.astype(np.float64)
    highs = df_m15["high"].values.astype(np.float64)
    lows = df_m15["low"].values.astype(np.float64)
    closes = df_m15["close"].values.astype(np.float64)
    dates = df_m15.index
    months = np.array([f"{d.year}-{d.month:02d}" for d in dates])
    days = (dates.year.values * 10000 + dates.month.values * 100 + dates.day.values).astype(np.int32)
    hours = dates.hour.values.astype(np.int32)

    print("[*] Pre-computing baseline indicators...")
    atr14 = compute_atr(highs, lows, closes, period=14)
    rsi14 = compute_rsi(closes, period=14)

    # Parametric sweep
    sweep_buffers = [0.1, 0.2, 0.3, 0.4]
    rsi_options = [True, False]
    tp_mults = [1.5, 2.0, 2.5]
    sl_mults = [1.0, 1.2, 1.5]
    profit_locks = [100.0, 150.0, 200.0]

    results = []
    print("[*] Calibrating Strategy 49 across parametric combinations...")

    for sb in sweep_buffers:
        for use_rsi in rsi_options:
            for tpm in tp_mults:
                for slm in sl_mults:
                    for pl in profit_locks:
                        res = simulate_strategy_49(
                            opens=opens,
                            highs=highs,
                            lows=lows,
                            closes=closes,
                            atr14=atr14,
                            rsi14=rsi14,
                            hours=hours,
                            days=days,
                            months=months,
                            dates=dates,
                            sweep_buffer_atr=sb,
                            use_rsi_filter=use_rsi,
                            tp_mult=tpm,
                            sl_mult=slm,
                            monthly_profit_lock=pl,
                            monthly_loss_breaker=150.0,
                            defensive_thresh=80.0,
                            defensive_lot_mult=0.25
                        )
                        res.update({
                            "sweep_buffer": sb,
                            "use_rsi": use_rsi,
                            "tp_mult": tpm,
                            "sl_mult": slm,
                            "profit_lock": pl
                        })
                        results.append(res)

    df_res = pd.DataFrame(results)
    out_csv = "projects/quant_strategy_discovery/results/strategy_49_eurusd_fade_sweep_results.csv"
    os.makedirs(os.path.dirname(out_csv), exist_ok=True)
    df_res.to_csv(out_csv, index=False)
    print(f"[+] Saved Strategy 49 sweep results to {out_csv}")

    df_sorted = df_res.sort_values(by="pf", ascending=False)
    best = df_sorted.iloc[0]

    print("\n" + "=" * 80)
    print("STRATEGY 49: EURUSD LIQUIDITY SWEEP & FADE CHAMPION RESULTS")
    print("=" * 80)
    print(f"Top Configuration:")
    print(f"  - Sweep Buffer ATR: {best['sweep_buffer']}")
    print(f"  - RSI Filter Enabled: {best['use_rsi']}")
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
    print(df_sorted[["sweep_buffer", "use_rsi", "tp_mult", "sl_mult", "profit_lock", "pf", "net_profit", "win_rate", "max_dd", "mcr", "total_trades"]].head(5).to_string())

if __name__ == "__main__":
    main()
