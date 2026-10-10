#!/usr/bin/env python3
"""
===============================================================================
STRATEGY 81: GOLD H1 AROON OSCILLATOR TREND IGNITION & EXTREMES (AROON-TIE-KFD)
===============================================================================
Hypothesis & Market Edge:
1. Tushar Chande's Aroon Indicator (1995):
   - Rather than measuring price momentum or amplitude (like RSI, Stochastic, CCI),
     Aroon measures time: the number of periods elapsed since the highest high
     and lowest low occurred over a lookback window N.
   - Aroon Up = ((N - periods_since_highest_high) / N) * 100
   - Aroon Down = ((N - periods_since_lowest_low) / N) * 100
   - Aroon Oscillator = Aroon Up - Aroon Down in [-100, +100]
2. Signal Mechanics:
   - 'osc_cross_zero': Aroon Oscillator crosses above 0.0 (Long) or below 0.0 (Short).
   - 'osc_threshold_50': Aroon Oscillator crosses above +50.0 (Long trend ignition)
     or below -50.0 (Short trend ignition).
   - 'extreme_pin': Aroon Up reaches 100 while Aroon Down <= 30 (Long conviction)
     or Aroon Down reaches 100 while Aroon Up <= 30 (Short conviction).
   - 'up_down_cross': Aroon Up crosses above Aroon Down (Long), or Aroon Down crosses above Aroon Up (Short).
3. Anti-Chaos Filter:
   - Katz Fractal Dimension (KFD <= 1.35 or 1.40) to eliminate choppy, Brownian market regimes.
   - Macro Structural Trend (EMA200, EMA50, or unconstrained).
4. Friction & Validation:
   - 72 Calendar Months (2020-01-01 to 2025-12-30).
   - Institutional Gold CFD frictions: $0.25 spread ($25.00/lot) + $6.00/lot commission ($3.10 / 0.10 lot).
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

def compute_aroon(highs: np.ndarray, lows: np.ndarray, period: int = 14):
    n = len(highs)
    aroon_up = np.zeros(n, dtype=np.float64)
    aroon_down = np.zeros(n, dtype=np.float64)
    if period < n:
        w_h = np.lib.stride_tricks.sliding_window_view(highs, window_shape=period + 1)
        idx_h = np.argmax(w_h, axis=-1)
        aroon_up[period:] = (idx_h / period) * 100.0

        w_l = np.lib.stride_tricks.sliding_window_view(lows, window_shape=period + 1)
        idx_l = np.argmin(w_l, axis=-1)
        aroon_down[period:] = (idx_l / period) * 100.0

    aroon_osc = aroon_up - aroon_down
    return aroon_up, aroon_down, aroon_osc

def simulate_aroon_strategy(
    opens: np.ndarray,
    highs: np.ndarray,
    lows: np.ndarray,
    closes: np.ndarray,
    atr14: np.ndarray,
    ema50: np.ndarray,
    ema200: np.ndarray,
    kfd: np.ndarray,
    aroon_up: np.ndarray,
    aroon_down: np.ndarray,
    aroon_osc: np.ndarray,
    months: np.ndarray,
    dates: pd.DatetimeIndex,
    trigger_mode: str = "osc_cross_zero",
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
    fixed_friction = comm_cost + spread_cost # $3.10 per 0.10 lot

    cur_m = None
    cur_m_pnl = 0.0
    locked_m = False

    for i in range(250, n - 1):
        m_val = months[i]
        if m_val != cur_m:
            cur_m = m_val
            cur_m_pnl = 0.0
            locked_m = False

        # Intrabar exit evaluation if in position
        if pos != 0:
            hit_sl = False
            hit_tp = False
            exit_p = 0.0

            if pos == 1:
                if lows[i] <= sl_p:
                    hit_sl = True
                    exit_p = sl_p if opens[i] >= sl_p else opens[i]
                elif highs[i] >= tp_p:
                    hit_tp = True
                    exit_p = tp_p if opens[i] <= tp_p else opens[i]

                if hit_sl or hit_tp:
                    pnl = (exit_p - entry_p) * lot_size * 100.0 - fixed_friction
                    cur_m_pnl += pnl
                    trades.append({
                        "entry_date": str(dates[entry_i]),
                        "exit_date": str(dates[i]),
                        "dir": "BUY",
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

            elif pos == -1:
                if highs[i] >= sl_p:
                    hit_sl = True
                    exit_p = sl_p if opens[i] <= sl_p else opens[i]
                elif lows[i] <= tp_p:
                    hit_tp = True
                    exit_p = tp_p if opens[i] >= tp_p else opens[i]

                if hit_sl or hit_tp:
                    pnl = (entry_p - exit_p) * lot_size * 100.0 - fixed_friction
                    cur_m_pnl += pnl
                    trades.append({
                        "entry_date": str(dates[entry_i]),
                        "exit_date": str(dates[i]),
                        "dir": "SELL",
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
            if c_atr < 0.5:
                continue

            kfd_ok = (kfd[i] <= kfd_thresh) if use_kfd else True

            if trend_filter == "ema200":
                ema_long_ok = closes[i] > ema200[i]
                ema_short_ok = closes[i] < ema200[i]
            elif trend_filter == "ema50":
                ema_long_ok = closes[i] > ema50[i]
                ema_short_ok = closes[i] < ema50[i]
            else:
                ema_long_ok = True
                ema_short_ok = True

            long_sig = False
            short_sig = False

            up_now = aroon_up[i]
            up_prev = aroon_up[i - 1]
            dn_now = aroon_down[i]
            dn_prev = aroon_down[i - 1]
            osc_now = aroon_osc[i]
            osc_prev = aroon_osc[i - 1]

            if trigger_mode == "osc_cross_zero":
                long_sig = (osc_now > 0.0) and (osc_prev <= 0.0)
                short_sig = (osc_now < 0.0) and (osc_prev >= 0.0)

            elif trigger_mode == "osc_threshold_50":
                long_sig = (osc_now >= 50.0) and (osc_prev < 50.0)
                short_sig = (osc_now <= -50.0) and (osc_prev > -50.0)

            elif trigger_mode == "extreme_pin":
                long_now = (up_now >= 100.0) and (dn_now <= 30.0)
                long_prev = (up_prev >= 100.0) and (dn_prev <= 30.0)
                long_sig = long_now and not long_prev

                short_now = (dn_now >= 100.0) and (up_now <= 30.0)
                short_prev = (dn_prev >= 100.0) and (up_prev <= 30.0)
                short_sig = short_now and not short_prev

            elif trigger_mode == "up_down_cross":
                long_sig = (up_now >= dn_now) and (up_prev < dn_prev)
                short_sig = (dn_now >= up_now) and (dn_prev < up_prev)

            if long_sig and ema_long_ok and kfd_ok:
                pos = 1
                entry_i = i + 1
                entry_p = opens[i + 1]
                sl_p = entry_p - (sl_mult * c_atr)
                tp_p = entry_p + (tp_mult * c_atr)

            elif short_sig and ema_short_ok and kfd_ok:
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

    cum_pnl = np.cumsum(pnls)
    running_max = np.maximum.accumulate(cum_pnl)
    drawdowns = running_max - cum_pnl
    max_dd = np.max(drawdowns) if len(drawdowns) > 0 else 0.0
    romad = (net_profit / max_dd) if max_dd > 0 else 0.0

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
    parser = argparse.ArgumentParser(description="Sweep Strategy 81: Gold H1 Aroon Oscillator")
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

    print("[*] Resampling to H1 (2020-2025)...", flush=True)
    df_h1 = df_raw.resample("1h").agg({
        "open": "first", "high": "max", "low": "min", "close": "last"
    }).dropna()

    opens = df_h1["open"].values.astype(np.float64)
    highs = df_h1["high"].values.astype(np.float64)
    lows = df_h1["low"].values.astype(np.float64)
    closes = df_h1["close"].values.astype(np.float64)
    dates = df_h1.index
    months = (dates.year.values * 100 + dates.month.values).astype(np.int32)

    print(f"[*] Resampled H1 bars: {len(closes)} bars across {len(np.unique(months))} calendar months.", flush=True)

    print("[*] Pre-computing ATR, EMAs, KFD...", flush=True)
    atr14 = compute_atr(highs, lows, closes, 14)
    ema50 = compute_ema(closes, 50)
    ema200 = compute_ema(closes, 200)
    kfd24 = compute_katz_fractal_dimension(closes, atr14, 24)

    periods = [14, 20, 25, 30]
    trigger_modes = ["osc_cross_zero", "osc_threshold_50", "extreme_pin", "up_down_cross"]
    trend_filters = ["ema200", "ema50", "none"]
    kfd_options = [
        (True, 1.35),
        (True, 1.40),
        (False, 1.50)
    ]
    tp_mults = [3.5, 4.0, 4.5, 5.0]
    sl_mults = [1.5, 2.0, 2.5]
    profit_locks = [0.0, 200.0, 250.0]

    print("[*] Pre-computing Aroon series for lookback periods...", flush=True)
    aroon_cache = {}
    for p in periods:
        aroon_cache[p] = compute_aroon(highs, lows, period=p)

    total_combos = (
        len(periods) * len(trigger_modes) * len(trend_filters) *
        len(kfd_options) * len(tp_mults) * len(sl_mults) * len(profit_locks)
    )
    print(f"[*] Total sweep configurations to evaluate: {total_combos}", flush=True)

    results = []
    best_candidate = None
    best_score = -999999.0

    count = 0
    t_sweep_start = time.time()

    for p in periods:
        up_arr, dn_arr, osc_arr = aroon_cache[p]
        for trg in trigger_modes:
            for trd in trend_filters:
                for (use_kfd, kfd_thresh) in kfd_options:
                    for tp_m in tp_mults:
                        for sl_m in sl_mults:
                            for p_lock in profit_locks:
                                count += 1
                                trades = simulate_aroon_strategy(
                                    opens=opens, highs=highs, lows=lows, closes=closes,
                                    atr14=atr14, ema50=ema50, ema200=ema200, kfd=kfd24,
                                    aroon_up=up_arr, aroon_down=dn_arr, aroon_osc=osc_arr,
                                    months=months, dates=dates,
                                    trigger_mode=trg, trend_filter=trd,
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
                                    "period": p,
                                    "trigger_mode": trg, "trend_filter": trd,
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
                                        f"[{count}/{total_combos}] New Best: Aroon({p}) | Trg={trg} | Trd={trd} | "
                                        f"KFD={use_kfd} | TP={tp_m} | SL={sl_m} | Lock={p_lock} -> "
                                        f"Trades={m['total_trades']}, Net=${m['net_profit']:.2f}, "
                                        f"PF={m['pf']:.3f}, DD=${m['max_dd']:.2f}, RoMaD={m['romad']:.2f}x, MCR={m['mcr']:.1f}%",
                                        flush=True
                                    )

    t_sweep_end = time.time()
    print(f"[*] Sweep completed in {t_sweep_end - t_sweep_start:.2f} seconds.", flush=True)

    df_results = pd.DataFrame(results)
    out_csv = os.path.join(args.out_dir, "strategy_81_aroon_sweep_results.csv")
    df_results.to_csv(out_csv, index=False)
    print(f"[+] Saved all {len(df_results)} sweep results to {out_csv}", flush=True)

    out_json = os.path.join(args.out_dir, "strategy_81_champion.json")
    with open(out_json, "w") as f:
        json.dump({
            "strategy_id": "STRATEGY_81",
            "strategy_name": "Gold H1 Aroon Oscillator Trend Ignition & Extremes (AROON-TIE-KFD)",
            "champion": best_candidate,
            "runtime_seconds": round(t_sweep_end - t_start, 2)
        }, f, indent=2)
    print(f"[+] Saved champion candidate to {out_json}", flush=True)

    print("\n" + "=" * 80, flush=True)
    print("STRATEGY 81 CHAMPION CANDIDATE AUDIT", flush=True)
    print("=" * 80, flush=True)
    if best_candidate:
        for k, v in best_candidate.items():
            print(f"  {k}: {v}", flush=True)
    else:
        print("  No viable candidate passed thresholds (total_trades >= 60, PF >= 1.40)", flush=True)
    print("=" * 80, flush=True)

if __name__ == "__main__":
    main()
