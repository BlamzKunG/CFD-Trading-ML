#!/usr/bin/env python3
"""
===============================================================================
STRATEGY 35: VORTEX INDICATOR VELOCITY & VOLATILITY SKEW BREAKOUT (VIM-VSB)
===============================================================================
Asset: XAUUSD CFD (2020 - 2025, 72 Calendar Months)
Timeframe: H1 (Resampled from M1)

Quantitative Rationale & Target Objective (User Mandate: PF >= 1.50+):
1. Directional Vortex Dynamics:
   - Etienne Botes & Douglas Siepman's Vortex Indicator (VI+ / VI-) measures 
     the absolute cyclical distance between current bar highs/lows and prior bar 
     lows/highs normalized by True Range.
   - Delta VI = VI+ - VI- reflects raw directional vortex flow velocity without 
     the lag of double-exponential moving averages or artificial oscillators.
2. Dual Macro Moving Average Vector:
   - Direction confirmed by EMA50 (intermediate) and EMA200 (macro structural baseline).
3. Fractal Dimension Horizon Gating (KFD):
   - Katz Fractal Dimension (24 hours): D <= 1.35 - 1.40 ensures entry only during 
     low-entropy, high-directional flow regimes.
4. Asymmetric High-Reward Payoff:
   - SL: 2.0x - 2.5x ATR.
   - TP: 3.5R - 4.5R asymmetric target.
5. Autonomous Adaptive Risk Management (ASAR):
   - Monthly profit locking at +$150 - +$250.
   - Defensive lot sizing under drawdown.
   - Hard calendar circuit breaker at -$250.
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
    rolling_d = np.maximum(rolling_max - rolling_min, 1e-4)

    for i in range(window, n):
        c_atr = max(atr14[i], 0.1)
        L_norm = max(rolling_L[i] / c_atr, 1.01)
        d_norm = max(rolling_d[i] / c_atr, 1.01)
        val = np.log10(L_norm) / np.log10(d_norm)
        kfd[i] = np.clip(val, 1.0, 2.0)
    return kfd

def compute_vortex_indicator(highs: np.ndarray, lows: np.ndarray, closes: np.ndarray, period: int = 14):
    n = len(closes)
    vm_plus = np.zeros(n, dtype=np.float64)
    vm_minus = np.zeros(n, dtype=np.float64)
    tr = np.zeros(n, dtype=np.float64)

    tr[0] = highs[0] - lows[0]
    for i in range(1, n):
        vm_plus[i] = abs(highs[i] - lows[i - 1])
        vm_minus[i] = abs(lows[i] - highs[i - 1])
        hl = highs[i] - lows[i]
        hc = abs(highs[i] - closes[i - 1])
        lc = abs(lows[i] - closes[i - 1])
        tr[i] = max(hl, max(hc, lc))

    sum_tr = pd.Series(tr).rolling(period).sum().values
    sum_vm_plus = pd.Series(vm_plus).rolling(period).sum().values
    sum_vm_minus = pd.Series(vm_minus).rolling(period).sum().values

    sum_tr = np.where(sum_tr == 0, 1e-6, sum_tr)
    vi_plus = sum_vm_plus / sum_tr
    vi_minus = sum_vm_minus / sum_tr
    delta_vi = vi_plus - vi_minus

    return vi_plus, vi_minus, delta_vi

def simulate_vortex_strategy(
    opens: np.ndarray,
    highs: np.ndarray,
    lows: np.ndarray,
    closes: np.ndarray,
    atr14: np.ndarray,
    ema50: np.ndarray,
    ema200: np.ndarray,
    h_lookback: np.ndarray,
    l_lookback: np.ndarray,
    kfd: np.ndarray,
    vi_plus: np.ndarray,
    vi_minus: np.ndarray,
    delta_vi: np.ndarray,
    months: np.ndarray,
    dates: pd.DatetimeIndex,
    use_kfd: bool = True,
    kfd_thresh: float = 1.35,
    delta_vi_thresh: float = 0.15,
    entry_mode: str = "breakout_vortex",  # "breakout_vortex" or "pure_vortex"
    monthly_profit_lock: float = 200.0,
    monthly_loss_breaker: float = 250.0,
    defensive_thresh: float = 120.0,
    defensive_lot_mult: float = 0.3,
    trend_tp_mult: float = 4.0,
    trend_sl_mult: float = 2.5,
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

        # 1. Check Exits
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
                trades.append({"pnl": pnl, "date": dates[i], "engine": "GOLD_H1_VORTEX", "month": m_key})
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
                trades.append({"pnl": pnl, "date": dates[i], "engine": "GOLD_H1_VORTEX", "month": m_key})
                month_cum_pnl += pnl
                pos = 0

                if monthly_profit_lock > 0 and month_cum_pnl >= monthly_profit_lock:
                    month_locked = True
                elif monthly_loss_breaker > 0 and month_cum_pnl <= -monthly_loss_breaker:
                    month_locked = True
                elif defensive_thresh > 0 and month_cum_pnl <= -defensive_thresh:
                    curr_unit_size = base_unit_size * defensive_lot_mult

        # 2. Check Entries
        if pos == 0 and c_atr > 0 and not month_locked:
            kfd_ok = (not use_kfd) or (kfd[i] <= kfd_thresh)
            if kfd_ok:
                long_trend = closes[i] > ema200[i] and closes[i] > ema50[i]
                short_trend = closes[i] < ema200[i] and closes[i] < ema50[i]

                if entry_mode == "breakout_vortex":
                    h_val = h_lookback[i]
                    l_val = l_lookback[i]
                    long_sig = (closes[i] > h_val) and (delta_vi[i] >= delta_vi_thresh) and long_trend
                    short_sig = (closes[i] < l_val) and (delta_vi[i] <= -delta_vi_thresh) and short_trend
                elif entry_mode == "pure_vortex":
                    # Vortex Velocity surge
                    long_sig = (delta_vi[i] >= delta_vi_thresh) and (delta_vi[i - 1] < delta_vi_thresh) and long_trend
                    short_sig = (delta_vi[i] <= -delta_vi_thresh) and (delta_vi[i - 1] > -delta_vi_thresh) and short_trend
                else:
                    long_sig = False
                    short_sig = False

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
    parser = argparse.ArgumentParser(description="Sweep Strategy 35: Vortex Velocity & Volatility Skew Breakout")
    parser.add_argument("--data", type=str, default="/mnt/sdcard/Download/EA/XAUUSD_M1.csv.gz")
    parser.add_argument("--out_dir", type=str, default="projects/quant_strategy_discovery/results")
    args = parser.parse_args()

    os.makedirs(args.out_dir, exist_ok=True)

    print(f"[*] Loading Gold M1 data from {args.data}...")
    df_raw = pd.read_csv(
        args.data,
        usecols=["datetime", "open", "high", "low", "close", "tick_volume"],
        dtype={"open": np.float32, "high": np.float32, "low": np.float32, "close": np.float32, "tick_volume": np.int32}
    )
    df_raw["datetime"] = pd.to_datetime(df_raw["datetime"])
    df_raw.set_index("datetime", inplace=True)
    df_raw.sort_index(inplace=True)

    print(f"[*] Resampling to H1 timeframe...")
    df_h1 = df_raw.resample("1h").agg({
        "open": "first", "high": "max", "low": "min", "close": "last", "tick_volume": "sum"
    }).dropna()
    print(f"[+] Loaded {len(df_h1):,} H1 bars (2020 - 2025).")

    opens = df_h1["open"].values.astype(np.float64)
    highs = df_h1["high"].values.astype(np.float64)
    lows = df_h1["low"].values.astype(np.float64)
    closes = df_h1["close"].values.astype(np.float64)
    dates = df_h1.index
    months = (dates.year.values * 100 + dates.month.values).astype(np.int32)

    print("[*] Pre-computing baseline indicators...")
    atr14 = compute_atr(highs, lows, closes, 14)
    ema50 = compute_ema(closes, 50)
    ema200 = compute_ema(closes, 200)
    kfd24 = compute_katz_fractal_dimension(closes, atr14, 24)

    # Pre-compute Vortex Indicators for multiple periods
    vortex_periods = [14, 21]
    vortex_cache = {}
    for vp in vortex_periods:
        print(f"[*] Pre-computing Vortex Indicator (period={vp})...")
        vortex_cache[vp] = compute_vortex_indicator(highs, lows, closes, vp)

    # Pre-compute Channel Lookbacks
    lookbacks = [12, 16, 20]
    lb_dict = {}
    for lb in lookbacks:
        h = pd.Series(highs).rolling(lb).max().shift(1).fillna(999999.0).values
        l = pd.Series(lows).rolling(lb).min().shift(1).fillna(0.0).values
        lb_dict[lb] = (h, l)

    # Sweep parameter grid
    delta_vi_options = [0.05, 0.10, 0.15, 0.20]
    entry_modes = ["breakout_vortex", "pure_vortex"]
    kfd_options = [(True, 1.35), (True, 1.40), (False, 1.40)]
    profit_locks = [200.0, 250.0]
    trend_tps = [3.5, 4.0, 4.5]
    trend_sls = [2.0, 2.5]
    def_threshs = [120.0]
    def_mults = [0.25, 0.30]

    total_combs = (
        len(vortex_periods) * len(lookbacks) * len(delta_vi_options) *
        len(entry_modes) * len(kfd_options) * len(profit_locks) *
        len(trend_tps) * len(trend_sls) * len(def_threshs) * len(def_mults)
    )
    print(f"[*] Calibrating Strategy 35: Vortex Velocity & Skew across {total_combs} combinations...")

    results = []
    t_start = time.time()

    for vp in vortex_periods:
        vi_p, vi_m, d_vi = vortex_cache[vp]
        for em in entry_modes:
            # If pure_vortex, lookback doesn't matter, only test lb=16 once to avoid duplicate runs
            cur_lookbacks = lookbacks if em == "breakout_vortex" else [16]
            for lb in cur_lookbacks:
                h_arr, l_arr = lb_dict[lb]
                for dvi_th in delta_vi_options:
                    for use_kfd, kfd_th in kfd_options:
                        for plock in profit_locks:
                            for tp_m in trend_tps:
                                for sl_m in trend_sls:
                                    for dthresh in def_threshs:
                                        for dmult in def_mults:
                                            trades = simulate_vortex_strategy(
                                                opens=opens, highs=highs, lows=lows, closes=closes,
                                                atr14=atr14, ema50=ema50, ema200=ema200,
                                                h_lookback=h_arr, l_lookback=l_arr,
                                                kfd=kfd24,
                                                vi_plus=vi_p, vi_minus=vi_m, delta_vi=d_vi,
                                                months=months, dates=dates,
                                                use_kfd=use_kfd, kfd_thresh=kfd_th,
                                                delta_vi_thresh=dvi_th,
                                                entry_mode=em,
                                                monthly_profit_lock=plock,
                                                monthly_loss_breaker=250.0,
                                                defensive_thresh=dthresh,
                                                defensive_lot_mult=dmult,
                                                trend_tp_mult=tp_m,
                                                trend_sl_mult=sl_m
                                            )
                                            m = evaluate_metrics(trades)
                                            if m["total_trades"] >= 50:
                                                m.update({
                                                    "vortex_period": vp,
                                                    "entry_mode": em,
                                                    "lookback": lb,
                                                    "delta_vi_thresh": dvi_th,
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

    # Sort primarily by Profit Factor (PF >= 1.50+), then Net Profit and MCR
    df_res.sort_values(by=["pf", "net_profit", "mcr"], ascending=[False, False, False], inplace=True)

    csv_path = os.path.join(args.out_dir, "strategy_35_vortex_sweep_results.csv")
    df_res.drop(columns=["monthly_series"]).to_csv(csv_path, index=False)
    print(f"[+] Saved Strategy 35 sweep results to {csv_path}")

    # Top Champion
    top_champ = results[df_res.index[0]]
    champ_json_path = os.path.join(args.out_dir, "strategy_35_champion.json")
    with open(champ_json_path, "w") as f:
        json.dump(top_champ, f, indent=2)

    print("\n" + "="*80)
    print("STRATEGY 35: VORTEX VELOCITY & SKEW CHAMPION RESULTS")
    print("="*80)
    print(f"Top Configuration (PF Target >= 1.50+):")
    print(f"  - Entry Mode: {top_champ['entry_mode']}")
    print(f"  - Vortex Period: {top_champ['vortex_period']}")
    print(f"  - Delta VI Threshold: {top_champ['delta_vi_thresh']}")
    print(f"  - Lookback: {top_champ['lookback']} hours")
    print(f"  - KFD Filter: {top_champ['use_kfd']} (Threshold: {top_champ['kfd_thresh']})")
    print(f"  - Profit Lock: ${top_champ['profit_lock']}")
    print(f"  - Trend TP / SL: {top_champ['trend_tp']}R / {top_champ['trend_sl']}xATR")
    print(f"  - Defensive Sizing: ${top_champ['def_thresh']} -> {top_champ['def_mult']}x Lot")
    print("-" * 80)
    print(f"Performance Metrics Across 72 Calendar Months (2020 - 2025):")
    print(f"  - Total Trades: {top_champ['total_trades']}")
    print(f"  - Net Profit: ${top_champ['net_profit']:,.2f}")
    print(f"  - Profit Factor (PF): {top_champ['pf']}  <-- MANDATE BENCHMARK")
    print(f"  - Win Rate: {top_champ['win_rate']}%")
    print(f"  - Max Drawdown: ${top_champ['max_dd']:,.2f}")
    print(f"  - Monthly Consistency Ratio (MCR): {top_champ['mcr']}% ({top_champ['pos_months']} profitable / {top_champ['total_months']} total months)")
    print(f"Sweep Execution Time: {time.time() - t_start:.2f}s")
    print("="*80)

    # Also display top 5 configurations to inspect robustness
    print("\nTop 5 Distinct Configurations:")
    top5 = df_res.head(5)[["entry_mode", "vortex_period", "delta_vi_thresh", "lookback", "pf", "net_profit", "win_rate", "max_dd", "mcr", "total_trades"]]
    print(top5.to_string(index=False))

if __name__ == "__main__":
    main()
