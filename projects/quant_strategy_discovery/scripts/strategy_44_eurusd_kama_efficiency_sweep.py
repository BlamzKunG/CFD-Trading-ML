#!/usr/bin/env python3
"""
===============================================================================
STRATEGY 44: EURUSD H1 KAMA DYNAMIC EFFICIENCY & FRACTAL MACRO TREND (EUR-KAMA)
===============================================================================
Asset: EURUSD CFD (2020 - 2025, 72 Calendar Months)
Timeframe: H1 (Resampled from raw M1 high-resolution data)

Quantitative Rationale & Target Objective (User Mandate: PF >= 1.50+ on FX):
1. Solving Forex Noise with Efficiency Ratio:
   - On EURUSD H1, chop produces repeated false breakouts.
   - Kaufman's Efficiency Ratio (ER = |Net Change| / Sum(|Changes|)) flattens 
     KAMA during low-conviction consolidation, eliminating whipsaws.
2. Directional Slope & Macro Alignment:
   - Long: Close > EMA200 AND Close > KAMA AND KAMA Slope > 0 AND ER >= ER_thresh.
   - Short: Close < EMA200 AND Close < KAMA AND KAMA Slope < 0 AND ER >= ER_thresh.
3. Realistic CFD FX Costs:
   - Spread: 0.5 pip ($0.00005 per unit = $5.00/lot).
   - Commission: $6.00/lot ($0.00006 per unit).
4. Autonomous Scaled Adaptive Risk (ASAR for FX):
   - Monthly profit lock at +$120 - +$180.
   - Monthly loss breaker at -$150.
   - Defensive lot sizing at -$80 drawdown.
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

def compute_katz_fractal_dimension(closes: np.ndarray, atr14: np.ndarray, window: int = 24) -> np.ndarray:
    n = len(closes)
    kfd = np.ones(n, dtype=np.float64) * 1.5
    diffs = np.abs(np.diff(closes, prepend=closes[0]))
    rolling_L = pd.Series(diffs).rolling(window).sum().values
    s_closes = pd.Series(closes)
    rolling_min = s_closes.rolling(window).min().values
    rolling_max = s_closes.rolling(window).max().values
    rolling_d = np.maximum(rolling_max - rolling_min, 1e-5)

    for i in range(window, n):
        c_atr = max(atr14[i], 0.0005)
        L_norm = max(rolling_L[i] / c_atr, 1.01)
        d_norm = max(rolling_d[i] / c_atr, 1.01)
        val = np.log10(L_norm) / np.log10(d_norm)
        kfd[i] = np.clip(val, 1.0, 2.0)
    return kfd

def compute_kama(closes: np.ndarray, n_period: int = 10, fast_span: int = 2, slow_span: int = 30):
    n = len(closes)
    kama = np.zeros(n, dtype=np.float64)
    er = np.zeros(n, dtype=np.float64)

    fast_sc = 2.0 / (fast_span + 1.0)
    slow_sc = 2.0 / (slow_span + 1.0)

    kama[n_period - 1] = closes[n_period - 1]

    diffs = np.abs(np.diff(closes, prepend=closes[0]))
    rolling_volatility = pd.Series(diffs).rolling(n_period).sum().values

    for i in range(n_period, n):
        change = abs(closes[i] - closes[i - n_period])
        volatility = rolling_volatility[i]
        c_er = (change / volatility) if volatility > 1e-6 else 0.0
        er[i] = np.clip(c_er, 0.0, 1.0)

        sc = (c_er * (fast_sc - slow_sc) + slow_sc) ** 2
        kama[i] = kama[i - 1] + sc * (closes[i] - kama[i - 1])

    kama_slope = np.zeros(n, dtype=np.float64)
    kama_slope[1:] = kama[1:] - kama[:-1]

    return kama, er, kama_slope

def simulate_eurusd_kama(
    opens: np.ndarray,
    highs: np.ndarray,
    lows: np.ndarray,
    closes: np.ndarray,
    atr14: np.ndarray,
    ema200: np.ndarray,
    kfd: np.ndarray,
    kama: np.ndarray,
    er: np.ndarray,
    kama_slope: np.ndarray,
    months: np.ndarray,
    dates: pd.DatetimeIndex,
    er_threshold: float = 0.35,
    use_kfd: bool = True,
    kfd_thresh: float = 1.35,
    monthly_profit_lock: float = 150.0,
    monthly_loss_breaker: float = 200.0,
    defensive_thresh: float = 80.0,
    defensive_lot_mult: float = 0.30,
    trend_tp_mult: float = 4.0,
    trend_sl_mult: float = 2.5,
    spread: float = 0.00005,
    commission_per_unit: float = 0.00006,
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

    for i in range(warmup, n - 1):
        m_key = months[i]
        c_atr = atr14[i]

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
            elif highs[i] >= tp_p:
                exit_p = tp_p if opens[i] <= tp_p else opens[i]
                exit_triggered = True

            if exit_triggered:
                pnl = (exit_p - entry_p) * curr_unit_size - (spread + commission_per_unit) * curr_unit_size
                trades.append({"pnl": pnl, "date": dates[i], "engine": "EUR_H1_KAMA", "month": m_key})
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
            if highs[i] <= sl_p:
                exit_p = sl_p if opens[i] >= sl_p else opens[i]
                exit_triggered = True
            elif lows[i] <= tp_p:
                exit_p = tp_p if opens[i] >= tp_p else opens[i]
                exit_triggered = True

            if exit_triggered:
                pnl = (entry_p - exit_p) * curr_unit_size - (spread + commission_per_unit) * curr_unit_size
                trades.append({"pnl": pnl, "date": dates[i], "engine": "EUR_H1_KAMA", "month": m_key})
                month_cum_pnl += pnl
                pos = 0

                if monthly_profit_lock > 0 and month_cum_pnl >= monthly_profit_lock:
                    month_locked = True
                elif monthly_loss_breaker > 0 and month_cum_pnl <= -monthly_loss_breaker:
                    month_locked = True
                elif defensive_thresh > 0 and month_cum_pnl <= -defensive_thresh:
                    curr_unit_size = base_unit_size * defensive_lot_mult

        # 2. Entries
        if pos == 0 and c_atr > 0 and not month_locked:
            kfd_ok = (not use_kfd) or (kfd[i] <= kfd_thresh)
            er_ok = er[i] >= er_threshold

            if kfd_ok and er_ok:
                long_trend = (closes[i] > ema200[i]) and (closes[i] > kama[i]) and (kama_slope[i] > 0)
                short_trend = (closes[i] < ema200[i]) and (closes[i] < kama[i]) and (kama_slope[i] < 0)

                # Pure KAMA inflection cross
                long_sig = long_trend and (closes[i - 1] <= kama[i - 1] or kama_slope[i - 1] <= 0)
                short_sig = short_trend and (closes[i - 1] >= kama[i - 1] or kama_slope[i - 1] >= 0)

                if long_sig:
                    pos = 1
                    entry_p = opens[i + 1] + (spread * 0.5)
                    sl_dist = trend_sl_mult * c_atr
                    sl_p = entry_p - sl_dist
                    tp_p = entry_p + (sl_dist * trend_tp_mult)
                elif short_sig:
                    pos = -1
                    entry_p = opens[i + 1] - (spread * 0.5)
                    sl_dist = trend_sl_mult * c_atr
                    sl_p = entry_p + sl_dist
                    tp_p = entry_p - (sl_dist * trend_tp_mult)

    return trades

def evaluate_metrics(trades: list) -> dict:
    if len(trades) < 20:
        return {
            "total_trades": len(trades), "net_profit": -9999.0, "pf": 0.0,
            "win_rate": 0.0, "max_dd": 9999.0, "mcr": 0.0, "pos_months": 0, "total_months": 72
        }

    pnls = np.array([t["pnl"] for t in trades])
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
    max_dd = float(np.max(dd)) if len(dd) > 0 else 0.0

    df_tr = pd.DataFrame(trades)
    df_tr["month"] = df_tr["month"].astype(int)
    monthly = df_tr.groupby("month")["pnl"].sum().to_dict()

    all_months = []
    for y in range(2020, 2026):
        for m in range(1, 13):
            all_months.append(y * 100 + m)

    m_series = {m: round(monthly.get(m, 0.0), 2) for m in all_months}
    pos_m = sum(1 for m in all_months if m_series[m] > 0.0)
    mcr = float(round(pos_m / len(all_months) * 100.0, 2))

    return {
        "total_trades": len(trades),
        "net_profit": round(net_profit, 2),
        "pf": round(pf, 3),
        "win_rate": round(win_rate, 2),
        "max_dd": round(max_dd, 2),
        "mcr": mcr,
        "pos_months": pos_m,
        "total_months": len(all_months),
        "monthly_series": m_series
    }

def main():
    parser = argparse.ArgumentParser(description="Sweep Strategy 44: EURUSD H1 KAMA Efficiency")
    parser.add_argument("--data", type=str, default="/mnt/sdcard/Download/EA/EURUSD_M1.csv.gz")
    parser.add_argument("--out_dir", type=str, default="projects/quant_strategy_discovery/results")
    args = parser.parse_args()

    os.makedirs(args.out_dir, exist_ok=True)

    print(f"[*] Loading EURUSD M1 data from {args.data}...")
    df_raw = pd.read_csv(
        args.data,
        usecols=["datetime", "open", "high", "low", "close"],
        dtype={"open": np.float32, "high": np.float32, "low": np.float32, "close": np.float32}
    )
    df_raw["datetime"] = pd.to_datetime(df_raw["datetime"])
    df_raw.set_index("datetime", inplace=True)
    df_raw.sort_index(inplace=True)

    print(f"[*] Resampling to H1 timeframe...")
    df_h1 = df_raw.resample("1h").agg({
        "open": "first", "high": "max", "low": "min", "close": "last"
    }).dropna()
    print(f"[+] Loaded {len(df_h1):,} EURUSD H1 bars (2020 - 2025).")

    opens = df_h1["open"].values.astype(np.float64)
    highs = df_h1["high"].values.astype(np.float64)
    lows = df_h1["low"].values.astype(np.float64)
    closes = df_h1["close"].values.astype(np.float64)
    dates = df_h1.index
    months = (dates.year.values * 100 + dates.month.values).astype(np.int32)

    print("[*] Pre-computing baseline indicators...")
    atr14 = compute_atr(highs, lows, closes, 14)
    ema200 = compute_ema(closes, 200)
    kfd24 = compute_katz_fractal_dimension(closes, atr14, 24)

    # Pre-compute KAMA for multiple periods
    kama_periods = [10, 14, 20]
    kama_cache = {}
    for kp in kama_periods:
        print(f"[*] Pre-computing KAMA (period={kp})...")
        kama_cache[kp] = compute_kama(closes, n_period=kp)

    # Sweep parameters
    er_thresholds = [0.25, 0.35, 0.45]
    kfd_options = [(True, 1.35), (True, 1.40), (False, 1.40)]
    profit_locks = [120.0, 150.0, 180.0]
    trend_tps = [3.5, 4.0, 4.5]
    trend_sls = [2.0, 2.5]
    def_threshs = [80.0]
    def_mults = [0.30]

    total_combs = (
        len(kama_periods) * len(er_thresholds) * len(kfd_options) *
        len(profit_locks) * len(trend_tps) * len(trend_sls) * len(def_threshs) * len(def_mults)
    )
    print(f"[*] Calibrating Strategy 44: EURUSD H1 KAMA across {total_combs} combinations...")

    results = []
    t_start = time.time()

    for kp in kama_periods:
        k_val, er_val, slope_val = kama_cache[kp]
        for er_th in er_thresholds:
            for use_kfd, kfd_th in kfd_options:
                for plock in profit_locks:
                    for tp_m in trend_tps:
                        for sl_m in trend_sls:
                            for dthresh in def_threshs:
                                for dmult in def_mults:
                                    trades = simulate_eurusd_kama(
                                        opens=opens, highs=highs, lows=lows, closes=closes,
                                        atr14=atr14, ema200=ema200, kfd=kfd24,
                                        kama=k_val, er=er_val, kama_slope=slope_val,
                                        months=months, dates=dates,
                                        er_threshold=er_th,
                                        use_kfd=use_kfd, kfd_thresh=kfd_th,
                                        monthly_profit_lock=plock,
                                        monthly_loss_breaker=200.0,
                                        defensive_thresh=dthresh,
                                        defensive_lot_mult=dmult,
                                        trend_tp_mult=tp_m,
                                        trend_sl_mult=sl_m
                                    )
                                    m = evaluate_metrics(trades)
                                    if m["total_trades"] >= 40:
                                        m.update({
                                            "kama_period": kp,
                                            "er_threshold": er_th,
                                            "use_kfd": use_kfd,
                                            "kfd_thresh": kfd_th,
                                            "profit_lock": plock,
                                            "trend_tp": tp_m,
                                            "trend_sl": sl_m,
                                            "def_thresh": dthresh,
                                            "def_mult": dmult
                                        })
                                        results.append(m)

    df_res = pd.DataFrame(results)
    if len(df_res) == 0:
        print("[!] No combinations met minimum trade requirements.")
        return

    df_res.sort_values(by=["pf", "net_profit", "mcr"], ascending=[False, False, False], inplace=True)

    csv_path = os.path.join(args.out_dir, "strategy_44_eurusd_kama_sweep_results.csv")
    df_res.drop(columns=["monthly_series"]).to_csv(csv_path, index=False)
    print(f"[+] Saved Strategy 44 sweep results to {csv_path}")

    top_champ = results[df_res.index[0]]
    champ_json_path = os.path.join(args.out_dir, "strategy_44_champion.json")
    with open(champ_json_path, "w") as f:
        json.dump(top_champ, f, indent=2)

    print("\n" + "="*80)
    print("STRATEGY 44: EURUSD H1 KAMA EFFICIENCY CHAMPION RESULTS")
    print("="*80)
    print(f"Top Configuration (PF Target >= 1.50+ on FX):")
    print(f"  - KAMA Period: {top_champ['kama_period']}")
    print(f"  - ER Threshold: {top_champ['er_threshold']}")
    print(f"  - KFD Filter: {top_champ['use_kfd']} (Threshold: {top_champ['kfd_thresh']})")
    print(f"  - Monthly Profit Lock: ${top_champ['profit_lock']}")
    print(f"  - Target R:R / SL: {top_champ['trend_tp']}R / {top_champ['trend_sl']}x ATR")
    print("-" * 80)
    print(f"Performance Metrics Across 72 Calendar Months (2020 - 2025):")
    print(f"  - Total Trades: {top_champ['total_trades']}")
    print(f"  - Net Profit: ${top_champ['net_profit']:,.2f}")
    print(f"  - Profit Factor (PF): {top_champ['pf']}  <-- TARGET KPI")
    print(f"  - Win Rate: {top_champ['win_rate']}%")
    print(f"  - Max Drawdown: ${top_champ['max_dd']:,.2f}")
    print(f"  - Monthly Consistency Ratio (MCR): {top_champ['mcr']}% ({top_champ['pos_months']}/{top_champ['total_months']} profitable months)")
    print(f"Sweep Execution Time: {time.time() - t_start:.2f}s")
    print("="*80)

    print("\nTop 5 Distinct Configurations:")
    top5 = df_res.head(5)[["kama_period", "er_threshold", "use_kfd", "trend_tp", "trend_sl", "pf", "net_profit", "win_rate", "max_dd", "mcr", "total_trades"]]
    print(top5.to_string(index=False))

if __name__ == "__main__":
    main()
