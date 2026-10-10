#!/usr/bin/env python3
"""
===============================================================================
STRATEGY 73: GOLD H1 EHLERS FISHER TRANSFORM GAUSSIAN TURNING POINTS (EFT-GTP-KFD)
===============================================================================
Hypothesis & Market Edge:
1. John Ehlers' Fisher Transform:
   - Financial price series have fat-tailed, non-Gaussian distributions.
   - Standard bounded oscillators clamp near extremities and provide sluggish inflections.
   - Fisher Transform converts normalized prices into an approximate Gaussian normal distribution:
       Price_t = (High_t + Low_t) / 2
       X_t = 0.33 * 2 * ((Price_t - MinL) / (MaxH - MinL) - 0.5) + 0.67 * X_{t-1}
       Fisher_t = 0.5 * ln((1 + X_t) / (1 - X_t)) + 0.5 * Fisher_{t-1}
       Trigger_t = Fisher_{t-1}
   - Extreme values (> +1.5 / < -1.5) indicate statistically improbable price extensions,
     producing decisive turning points with virtually zero phase lag.
2. Signal Triggers:
   - 'cross_extreme': Fisher crossing Trigger line from beyond +/- threshold (e.g. +/-1.5).
   - 'cross_zero': Fisher crossing the zero line.
   - 'cross_all': Standard Fisher crossing Trigger.
   - 'cross_extreme_or_zero': Crossover from extreme territory OR zero waterline cross.
3. Trend & Chaos Filtering:
   - EMA200 / EMA50 structural alignment.
   - Katz Fractal Dimension (KFD <= 1.35 or 1.40) noise gating.
4. Frictions:
   - 72 Calendar Months (2020-01-01 to 2025-12-30).
   - Gold CFD frictions: $0.25 spread ($25.00/lot) + $6.00/lot commission ($3.10 total / 0.10 lot).
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

def compute_fisher_transform(highs: np.ndarray, lows: np.ndarray, period: int = 10):
    n = len(highs)
    med_price = (highs + lows) / 2.0
    x_val = np.zeros(n, dtype=np.float64)
    fisher = np.zeros(n, dtype=np.float64)
    trigger = np.zeros(n, dtype=np.float64)

    for i in range(period, n):
        max_h = np.max(highs[i - period + 1 : i + 1])
        min_l = np.min(lows[i - period + 1 : i + 1])
        diff = max_h - min_l
        if diff < 1e-6:
            diff = 1e-6

        raw_x = 0.33 * 2.0 * ((med_price[i] - min_l) / diff - 0.5) + 0.67 * x_val[i - 1]
        raw_x = max(-0.999, min(0.999, raw_x))
        x_val[i] = raw_x

        fish = 0.5 * np.log((1.0 + raw_x) / (1.0 - raw_x)) + 0.5 * fisher[i - 1]
        fisher[i] = fish
        trigger[i] = fisher[i - 1]

    return fisher, trigger

def simulate_fisher_strategy(
    opens: np.ndarray,
    highs: np.ndarray,
    lows: np.ndarray,
    closes: np.ndarray,
    atr14: np.ndarray,
    ema50: np.ndarray,
    ema200: np.ndarray,
    kfd: np.ndarray,
    fisher: np.ndarray,
    trigger: np.ndarray,
    months: np.ndarray,
    dates: pd.DatetimeIndex,
    trigger_mode: str = "cross_extreme",
    extreme_thresh: float = 1.5,
    trend_filter: str = "ema200",
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

    comm_cost = commission * lot_size
    spread_cost = spread * lot_size * 100.0
    fixed_friction = spread_cost + comm_cost

    cur_m = months[0]
    cur_m_pnl = 0.0
    locked_m = False

    for i in range(50, n - 1):
        bar_m = months[i]
        if bar_m != cur_m:
            cur_m = bar_m
            cur_m_pnl = 0.0
            locked_m = False

        # Manage active position
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
                    "entry_p": round(entry_p, 2),
                    "exit_p": round(exit_p, 2),
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

        # Check entries if flat
        if pos == 0 and not locked_m:
            c_atr = atr14[i]
            if c_atr < 0.5: continue

            kfd_ok = (kfd[i] <= kfd_thresh) if use_kfd else True

            if trend_filter == "ema200":
                ema_long_ok = (closes[i] > ema200[i])
                ema_short_ok = (closes[i] < ema200[i])
            elif trend_filter == "ema50":
                ema_long_ok = (closes[i] > ema50[i])
                ema_short_ok = (closes[i] < ema50[i])
            else:
                ema_long_ok = True
                ema_short_ok = True

            f0 = fisher[i]
            f1 = fisher[i - 1]
            t0 = trigger[i]
            t1 = trigger[i - 1]

            bull_signal = False
            bear_signal = False

            cross_up = (f0 > t0) and (f1 <= t1)
            cross_down = (f0 < t0) and (f1 >= t1)

            if trigger_mode == "cross_extreme":
                bull_signal = cross_up and (f1 <= -extreme_thresh)
                bear_signal = cross_down and (f1 >= extreme_thresh)
            elif trigger_mode == "cross_zero":
                bull_signal = (f0 > 0.0) and (f1 <= 0.0)
                bear_signal = (f0 < 0.0) and (f1 >= 0.0)
            elif trigger_mode == "cross_all":
                bull_signal = cross_up
                bear_signal = cross_down
            elif trigger_mode == "cross_extreme_or_zero":
                extr_bull = cross_up and (f1 <= -extreme_thresh)
                zero_bull = (f0 > 0.0) and (f1 <= 0.0)
                bull_signal = extr_bull or zero_bull

                extr_bear = cross_down and (f1 >= extreme_thresh)
                zero_bear = (f0 < 0.0) and (f1 >= 0.0)
                bear_signal = extr_bear or zero_bear

            bull_trigger = bull_signal and ema_long_ok and kfd_ok
            bear_trigger = bear_signal and ema_short_ok and kfd_ok

            if bull_trigger:
                pos = 1
                entry_i = i + 1
                entry_p = opens[i + 1]
                sl_p = entry_p - (sl_mult * c_atr)
                tp_p = entry_p + (tp_mult * c_atr)
            elif bear_trigger:
                pos = -1
                entry_i = i + 1
                entry_p = opens[i + 1]
                sl_p = entry_p + (sl_mult * c_atr)
                tp_p = entry_p - (tp_mult * c_atr)

    return trades

def evaluate_metrics(trades: list, total_months: int = 72) -> dict:
    if not trades:
        return {
            "total_trades": 0, "net_profit": 0.0, "pf": 0.0,
            "win_rate": 0.0, "max_dd": 0.0, "romad": 0.0,
            "mcr": 0.0, "pos_months": 0, "total_months": total_months
        }

    pnls = np.array([t["pnl"] for t in trades], dtype=np.float64)
    total_trades = len(trades)
    net_profit = np.sum(pnls)

    wins = pnls[pnls > 0]
    losses = pnls[pnls < 0]
    gross_profit = np.sum(wins) if len(wins) > 0 else 0.0
    gross_loss = abs(np.sum(losses)) if len(losses) > 0 else 1e-4
    pf = gross_profit / gross_loss
    win_rate = (len(wins) / total_trades) * 100.0

    # Max Drawdown
    cum_pnl = np.cumsum(pnls)
    running_max = np.maximum.accumulate(cum_pnl)
    drawdowns = running_max - cum_pnl
    max_dd = np.max(drawdowns) if len(drawdowns) > 0 else 0.0
    romad = (net_profit / max_dd) if max_dd > 0 else 0.0

    # Monthly Consistency Ratio (MCR)
    m_dict = {}
    for t in trades:
        m = t["month"]
        m_dict[m] = m_dict.get(m, 0.0) + t["pnl"]

    pos_months = sum(1 for v in m_dict.values() if v > 0)
    mcr = (pos_months / total_months) * 100.0

    return {
        "total_trades": total_trades,
        "net_profit": round(float(net_profit), 2),
        "pf": round(float(pf), 3),
        "win_rate": round(float(win_rate), 2),
        "max_dd": round(float(max_dd), 2),
        "romad": round(float(romad), 2),
        "mcr": round(float(mcr), 2),
        "pos_months": pos_months,
        "total_months": total_months
    }

def main():
    parser = argparse.ArgumentParser(description="Sweep Strategy 73: Gold H1 Fisher Transform")
    parser.add_argument("--gold_data", type=str, default="/mnt/sdcard/Download/EA/XAUUSD_M1.csv.gz")
    parser.add_argument("--out_dir", type=str, default="projects/quant_strategy_discovery/results")
    args = parser.parse_args()

    os.makedirs(args.out_dir, exist_ok=True)
    t_start = time.time()

    print("[*] Loading Gold raw M1 data...", flush=True)
    df_raw = pd.read_csv(args.gold_data, usecols=["datetime", "open", "high", "low", "close"])
    df_raw["datetime"] = pd.to_datetime(df_raw["datetime"])
    df_raw.set_index("datetime", inplace=True)
    df_raw.sort_index(inplace=True)

    print("[*] Resampling to Gold H1...", flush=True)
    df_h1 = df_raw.resample("1h").agg({
        "open": "first", "high": "max", "low": "min", "close": "last"
    }).dropna()

    opens = df_h1["open"].values.astype(np.float64)
    highs = df_h1["high"].values.astype(np.float64)
    lows = df_h1["low"].values.astype(np.float64)
    closes = df_h1["close"].values.astype(np.float64)
    dates = df_h1.index
    months = (dates.year.values * 100 + dates.month.values).astype(np.int32)

    print(f"[*] Resampled H1 bars: {len(closes)} from {dates[0]} to {dates[-1]}", flush=True)

    atr14 = compute_atr(highs, lows, closes, 14)
    ema50 = compute_ema(closes, 50)
    ema200 = compute_ema(closes, 200)
    kfd24 = compute_katz_fractal_dimension(closes, atr14, 24)

    lookback_periods = [8, 10, 12, 14, 16, 20]
    trigger_modes = ["cross_extreme", "cross_zero", "cross_all", "cross_extreme_or_zero"]
    extreme_threshs = [1.5, 2.0]
    trend_filters = ["ema200", "ema50", "none"]
    kfd_options = [
        (True, 1.35),
        (True, 1.40),
        (False, 1.50)
    ]
    tp_mults = [3.5, 4.0, 4.5, 5.0]
    sl_mults = [1.5, 2.0, 2.5]
    profit_locks = [0.0, 200.0, 250.0]

    print("[*] Pre-computing Fisher Transforms...", flush=True)
    fisher_cache = {}
    for p in lookback_periods:
        fisher_cache[p] = compute_fisher_transform(highs, lows, p)

    total_combos = (
        len(lookback_periods) * len(trigger_modes) * len(extreme_threshs) *
        len(trend_filters) * len(kfd_options) * len(tp_mults) * len(sl_mults) * len(profit_locks)
    )
    print(f"[*] Total sweep configurations to evaluate: {total_combos}", flush=True)

    results = []
    best_candidate = None
    best_score = -999999.0

    count = 0
    t_sweep_start = time.time()

    for p in lookback_periods:
        f_arr, t_arr = fisher_cache[p]
        for trg in trigger_modes:
            for ex_t in extreme_threshs:
                for trd in trend_filters:
                    for (use_kfd, kfd_thresh) in kfd_options:
                        for tp_m in tp_mults:
                            for sl_m in sl_mults:
                                for p_lock in profit_locks:
                                    count += 1
                                    trades = simulate_fisher_strategy(
                                        opens=opens, highs=highs, lows=lows, closes=closes,
                                        atr14=atr14, ema50=ema50, ema200=ema200, kfd=kfd24,
                                        fisher=f_arr, trigger=t_arr,
                                        months=months, dates=dates,
                                        trigger_mode=trg, extreme_thresh=ex_t,
                                        trend_filter=trd,
                                        use_kfd=use_kfd, kfd_thresh=kfd_thresh,
                                        tp_mult=tp_m, sl_mult=sl_m,
                                        monthly_profit_lock=p_lock, monthly_loss_breaker=250.0
                                    )
                                    m = evaluate_metrics(trades)

                                    if m["total_trades"] >= 60 and m["max_dd"] > 0:
                                        score = (m["net_profit"] * m["pf"] * (m["mcr"] / 100.0)) / (m["max_dd"] ** 0.5)
                                    else:
                                        score = -1000.0

                                    row = {
                                        "period": p, "trigger_mode": trg, "extreme_thresh": ex_t,
                                        "trend_filter": trd,
                                        "use_kfd": use_kfd, "kfd_thresh": kfd_thresh,
                                        "tp_mult": tp_m, "sl_mult": sl_m,
                                        "profit_lock": p_lock,
                                        **m,
                                        "score": round(score, 2)
                                    }
                                    results.append(row)

                                    if score > best_score and m["total_trades"] >= 60 and m["pf"] >= 1.40:
                                        best_score = score
                                        best_candidate = row
                                        print(
                                            f"[{count}/{total_combos}] New Best: Fisher({p}) | Trg={trg}({ex_t}) | Trd={trd} | "
                                            f"KFD={use_kfd} | TP={tp_m} | SL={sl_m} | Lock={p_lock} -> "
                                            f"Trades={m['total_trades']}, Net=${m['net_profit']:.2f}, "
                                            f"PF={m['pf']:.3f}, DD=${m['max_dd']:.2f}, RoMaD={m['romad']:.2f}x, MCR={m['mcr']:.1f}%",
                                            flush=True
                                        )

    t_sweep_end = time.time()
    print(f"[*] Sweep completed in {t_sweep_end - t_sweep_start:.2f} seconds.", flush=True)

    df_results = pd.DataFrame(results)
    out_csv = os.path.join(args.out_dir, "strategy_73_fisher_sweep_results.csv")
    df_results.to_csv(out_csv, index=False)
    print(f"[+] Saved sweep results to {out_csv}", flush=True)

    top_candidates = df_results.sort_values(by="score", ascending=False).head(20)
    print("\n================ TOP 10 CANDIDATES ================", flush=True)
    print(top_candidates[["period", "trigger_mode", "extreme_thresh", "trend_filter", "tp_mult", "sl_mult", "profit_lock", "total_trades", "net_profit", "pf", "max_dd", "romad", "mcr"]].head(10).to_string(), flush=True)

    if best_candidate is not None:
        champ_file = os.path.join(args.out_dir, "strategy_73_champion.json")
        with open(champ_file, "w") as f:
            json.dump({
                "strategy_id": "STRATEGY_73",
                "strategy_name": "Gold H1 Ehlers Fisher Transform Gaussian Turning Points (EFT-GTP-KFD)",
                "champion": best_candidate,
                "runtime_seconds": round(time.time() - t_start, 2)
            }, f, indent=2)
        print(f"[+] Saved Strategy 73 Champion to {champ_file}", flush=True)
    else:
        print("[!] No candidate satisfied all criteria.", flush=True)

if __name__ == "__main__":
    main()
