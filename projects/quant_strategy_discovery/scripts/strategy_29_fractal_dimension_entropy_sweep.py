#!/usr/bin/env python3
"""
===============================================================================
STRATEGY 29: FRACTAL DIMENSION & ENTROPY-GATED REGIME SWITCHING (FDE-RS)
===============================================================================
Institutional Quant Architecture: Sourced from Fractal Market Analysis (B. Mandelbrot & E. Peters)
Asset: XAUUSD CFD (2020 - 2025, 72 Calendar Months)
Timeframe: M15 (Resampled from M1)

Quantitative Formulation:
1. Katz Fractal Dimension (KFD):
   - Measures curve ruggedness and persistence over a rolling lookback (N = 32 bars = 8 hours):
     Path Length: L = sum(abs(Close_k - Close_{k-1}))
     Planar Distance: d = max(abs(Close_k - Close_0))
     Normalized: D = log10(L / ATR) / (log10(d / ATR) + 1e-6)
   - Regime Classification:
     * D < D_trend (e.g. 1.25 - 1.35): Persistent Trend Regime -> Allow Breakouts.
     * D > D_rev (e.g. 1.55 - 1.65): Anti-Persistent Mean-Reverting Regime -> Allow Fades.
     * D_trend <= D <= D_rev: Chaotic Entropy Noise Zone -> Cash Preservation (NO TRADES).
2. Integrated ASAR Risk Architecture:
   - Monthly Profit Lock: +$150 to +$250.
   - Defensive Downsizing: 70% lot reduction when month drops to -$120.
   - Hard Circuit Breaker: -$250.
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

def compute_katz_fractal_dimension(closes: np.ndarray, atr14: np.ndarray, window: int = 32) -> np.ndarray:
    n = len(closes)
    kfd = np.ones(n, dtype=np.float64) * 1.5  # default neutral
    diffs = np.abs(np.diff(closes, prepend=closes[0]))
    s_diffs = pd.Series(diffs)
    rolling_L = s_diffs.rolling(window).sum().values

    s_closes = pd.Series(closes)
    rolling_min = s_closes.rolling(window).min().values
    rolling_max = s_closes.rolling(window).max().values
    rolling_d = np.maximum(rolling_max - rolling_min, 1e-4)

    for i in range(window, n):
        c_atr = max(atr14[i], 0.1)
        L_norm = max(rolling_L[i] / c_atr, 1.01)
        d_norm = max(rolling_d[i] / c_atr, 1.01)
        # Katz formula: D = log10(n_steps) / (log10(n_steps) + log10(d / L))
        # Or standard D = log10(L) / log10(d)
        val = np.log10(L_norm) / np.log10(d_norm)
        kfd[i] = np.clip(val, 1.0, 2.0)

    return kfd

def simulate_fde_strategy(
    opens: np.ndarray,
    highs: np.ndarray,
    lows: np.ndarray,
    closes: np.ndarray,
    atr14: np.ndarray,
    ema200: np.ndarray,
    sma20: np.ndarray,
    std20: np.ndarray,
    h8_arr: np.ndarray,
    l8_arr: np.ndarray,
    kfd: np.ndarray,
    months: np.ndarray,
    hours: np.ndarray,
    dates: pd.DatetimeIndex,
    d_trend_thresh: float = 1.35,
    d_rev_thresh: float = 1.60,
    monthly_profit_lock: float = 150.0,
    monthly_loss_breaker: float = 250.0,
    defensive_thresh: float = 120.0,
    defensive_lot_mult: float = 0.3,
    trend_tp_mult: float = 4.0,
    trend_sl_mult: float = 2.5,
    rev_std_mult: float = 2.8,
    rev_sl_atr: float = 2.0,
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
    sub_mode = ""
    curr_unit_size = base_unit_size

    curr_month = None
    month_cum_pnl = 0.0
    month_locked = False

    upper_band = sma20 + rev_std_mult * std20
    lower_band = sma20 - rev_std_mult * std20

    for i in range(warmup, n - 1):
        m_key = months[i]
        hr = hours[i]
        c_atr = atr14[i]
        c_kfd = kfd[i]

        if m_key != curr_month:
            curr_month = m_key
            month_cum_pnl = 0.0
            month_locked = False
            curr_unit_size = base_unit_size

        # 1. Exits
        if pos == 1:
            exit_triggered = False
            exit_p = 0.0
            if lows[i] <= sl_p:
                exit_p = sl_p if opens[i] >= sl_p else opens[i]
                exit_triggered = True
            elif sub_mode == "TREND" and highs[i] >= tp_p:
                exit_p = tp_p if opens[i] <= tp_p else opens[i]
                exit_triggered = True
            elif sub_mode == "REV" and highs[i] >= sma20[i]:
                exit_p = sma20[i] if opens[i] <= sma20[i] else opens[i]
                exit_triggered = True

            if exit_triggered:
                pnl = (exit_p - entry_p) * curr_unit_size - (spread + commission_per_unit) * curr_unit_size
                trades.append({"pnl": pnl, "date": dates[i], "engine": sub_mode, "month": m_key})
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
            elif sub_mode == "TREND" and lows[i] <= tp_p:
                exit_p = tp_p if opens[i] >= tp_p else opens[i]
                exit_triggered = True
            elif sub_mode == "REV" and lows[i] <= sma20[i]:
                exit_p = sma20[i] if opens[i] >= sma20[i] else opens[i]
                exit_triggered = True

            if exit_triggered:
                pnl = (entry_p - exit_p) * curr_unit_size - (spread + commission_per_unit) * curr_unit_size
                trades.append({"pnl": pnl, "date": dates[i], "engine": sub_mode, "month": m_key})
                month_cum_pnl += pnl
                pos = 0

                if monthly_profit_lock > 0 and month_cum_pnl >= monthly_profit_lock:
                    month_locked = True
                elif monthly_loss_breaker > 0 and month_cum_pnl <= -monthly_loss_breaker:
                    month_locked = True
                elif defensive_thresh > 0 and month_cum_pnl <= -defensive_thresh:
                    curr_unit_size = base_unit_size * defensive_lot_mult

        # 2. Entries (Gated by Fractal Dimension)
        if pos == 0 and c_atr > 0 and not month_locked:
            # Persistent Trend Regime (D < d_trend_thresh) in active hours
            if (8 <= hr < 18) and (c_kfd <= d_trend_thresh):
                h8 = h8_arr[i]
                l8 = l8_arr[i]
                if closes[i] > h8 and closes[i] > ema200[i]:
                    pos = 1
                    entry_p = opens[i + 1] + (spread * 0.5)
                    sl_dist = trend_sl_mult * c_atr
                    sl_p = entry_p - sl_dist
                    tp_p = entry_p + (sl_dist * trend_tp_mult)
                    sub_mode = "TREND"
                elif closes[i] < l8 and closes[i] < ema200[i]:
                    pos = -1
                    entry_p = opens[i + 1] - (spread * 0.5)
                    sl_dist = trend_sl_mult * c_atr
                    sl_p = entry_p + sl_dist
                    tp_p = entry_p - (sl_dist * trend_tp_mult)
                    sub_mode = "TREND"

            # Anti-Persistent Reversion Regime (D >= d_rev_thresh) in Asian hours
            elif (hr >= 21 or hr < 6) and (c_kfd >= d_rev_thresh):
                if lows[i] < lower_band[i] and closes[i] > lower_band[i]:
                    pos = 1
                    entry_p = opens[i + 1] + (spread * 0.5)
                    sl_p = entry_p - (rev_sl_atr * c_atr)
                    sub_mode = "REV"
                elif highs[i] > upper_band[i] and closes[i] < upper_band[i]:
                    pos = -1
                    entry_p = opens[i + 1] - (spread * 0.5)
                    sl_p = entry_p + (rev_sl_atr * c_atr)
                    sub_mode = "REV"

    return trades

def evaluate_metrics(trades: list) -> dict:
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
    peak = np.maximum.accumulate(eq)
    dd = peak - eq
    max_dd = float(np.max(dd))

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
        "neg_months": neg_months,
        "monthly_series": {str(k): round(float(v), 2) for k, v in monthly_pnl.items()}
    }

def main():
    parser = argparse.ArgumentParser(description="Sweep Strategy 29: Fractal Dimension & Entropy-Gated Switching")
    parser.add_argument("--data", type=str, default="/mnt/sdcard/Download/EA/XAUUSD_M1.csv.gz")
    parser.add_argument("--out_dir", type=str, default="/root/CFD-Trading-ML/projects/quant_strategy_discovery/results")
    args = parser.parse_args()

    os.makedirs(args.out_dir, exist_ok=True)

    print(f"[*] Loading M1 data from {args.data}...")
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
    print(f"[+] Loaded {len(df_m15):,} M15 bars (2020 - 2025).")

    opens = df_m15["open"].values.astype(np.float64)
    highs = df_m15["high"].values.astype(np.float64)
    lows = df_m15["low"].values.astype(np.float64)
    closes = df_m15["close"].values.astype(np.float64)
    hours = df_m15.index.hour.values.astype(np.int32)
    dates = df_m15.index
    months = (dates.year.values * 100 + dates.month.values).astype(np.int32)

    print(f"[*] Computing Indicators (ATR14, EMA200, Bollinger Bands, Katz Fractal Dimension)...")
    atr14 = compute_atr(highs, lows, closes, 14)
    ema200 = compute_ema(closes, 200)
    sma20 = pd.Series(closes).rolling(20).mean().values
    std20 = pd.Series(closes).rolling(20).std().values
    h8_arr = pd.Series(highs).rolling(8).max().shift(1).fillna(999999.0).values
    l8_arr = pd.Series(lows).rolling(8).min().shift(1).fillna(0.0).values

    kfd = compute_katz_fractal_dimension(closes, atr14, window=32)

    # Sweep parameters
    d_trends = [1.30, 1.40, 1.50]
    d_revs = [1.50, 1.60]
    profit_locks = [150.0, 200.0]
    def_mults = [0.2, 0.3]

    total_combs = len(d_trends) * len(d_revs) * len(profit_locks) * len(def_mults)
    print(f"[*] Sweeping {total_combs} Fractal Dimension combinations across 72 calendar months...")

    results = []
    t_start = time.time()

    for dt in d_trends:
        for dr in d_revs:
            if dt >= dr: continue
            for plock in profit_locks:
                for dmult in def_mults:
                    trades = simulate_fde_strategy(
                        opens=opens, highs=highs, lows=lows, closes=closes,
                        atr14=atr14, ema200=ema200, sma20=sma20, std20=std20,
                        h8_arr=h8_arr, l8_arr=l8_arr, kfd=kfd,
                        months=months, hours=hours, dates=dates,
                        d_trend_thresh=dt, d_rev_thresh=dr,
                        monthly_profit_lock=plock, defensive_lot_mult=dmult
                    )
                    m = evaluate_metrics(trades)
                    m.update({
                        "d_trend": dt, "d_rev": dr,
                        "profit_lock": plock, "def_mult": dmult
                    })
                    results.append(m)

    df_res = pd.DataFrame(results)
    df_res.sort_values(by=["mcr", "pf", "net_profit"], ascending=[False, False, False], inplace=True)

    csv_path = os.path.join(args.out_dir, "strategy_29_fractal_dimension_sweep_results.csv")
    df_res.drop(columns=["monthly_series"]).to_csv(csv_path, index=False)
    print(f"[+] Saved sweep results to {csv_path}")

    champion = results[df_res.index[0]]
    champ_json_path = os.path.join(args.out_dir, "strategy_29_champion.json")
    with open(champ_json_path, "w") as f:
        json.dump(champion, f, indent=2)

    print("\n" + "="*80)
    print("STRATEGY 29: FRACTAL DIMENSION & ENTROPY SWITCHING - TOP CHAMPION")
    print("="*80)
    print(f"Config: D_Trend<={champion['d_trend']}, D_Rev>={champion['d_rev']}, ProfitLock=${champion['profit_lock']}, DefMult={champion['def_mult']}")
    print(f"Trades: {champion['total_trades']}")
    print(f"Net Profit: ${champion['net_profit']:,.2f}")
    print(f"Profit Factor: {champion['pf']}")
    print(f"Win Rate: {champion['win_rate']}%")
    print(f"Max Drawdown: ${champion['max_dd']:,.2f}")
    print(f"Monthly Consistency Ratio (MCR): {champion['mcr']}% ({champion['pos_months']} profitable / {champion['total_months']} total months)")
    print(f"Elapsed Time: {time.time() - t_start:.2f}s")
    print("="*80)

if __name__ == "__main__":
    main()
