#!/usr/bin/env python3
"""
===============================================================================
STRATEGY 91: GOLD H1 TUSHAR CHANDE'S MOMENTUM OSCILLATOR (CMO-MPE-KFD)
===============================================================================
Hypothesis & Market Edge:
1. Tushar Chande's Momentum Oscillator (1994):
   - Measures pure price momentum by taking the difference between positive
     and negative price changes divided by total price movement:
     CMO[i] = 100.0 * (S_u - S_d) / (S_u + S_d)
   - Unlike RSI, CMO does not doubly-smooth prices; it captures unsmoothed
     directional momentum impulses and volume-independent auction thrust.
2. Signal Mechanics & Trigger Variations:
   - 'cmo_zero_cross': Centerline cross in macro trend direction.
   - 'cmo_thrust_expansion': CMO crosses above/below threshold (+20, +30, +40) indicating velocity expansion.
   - 'cmo_extreme_reversion': Extreme bounce: dips below -thresh and crosses back up; surges above +thresh and crosses back down.
   - 'cmo_signal_cross': CMO crosses above/below its EMA signal line.
3. Institutional Filters & Validation:
   - Trend Filter: EMA50, EMA200, or None.
   - Anti-Chaos Gate: Katz Fractal Dimension (KFD <= 1.35, 1.40, or False).
   - Asymmetric R:R (3.5R to 6.0R) with ATR-based Stop Loss.
   - ASAR Risk Protection: Monthly profit lock ($200, $250) & circuit breaker ($250).
   - 72 Calendar Months (2020-01-01 to 2025-12-30).
   - Realistic CFD Frictions: $0.25 spread ($25/lot) + $6.00 comm ($3.10 / 0.10 lot).
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

def compute_katz_fractal_dimension(closes: np.ndarray, period: int = 24) -> np.ndarray:
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

def compute_cmo(closes: np.ndarray, period: int = 14) -> np.ndarray:
    n = len(closes)
    cmo = np.zeros(n, dtype=np.float64)
    diff = np.diff(closes)
    pos = np.maximum(diff, 0.0)
    neg = np.maximum(-diff, 0.0)
    
    pos_pad = np.insert(pos, 0, 0.0)
    neg_pad = np.insert(neg, 0, 0.0)
    
    pos_cs = np.cumsum(np.insert(pos_pad, 0, 0.0))
    neg_cs = np.cumsum(np.insert(neg_pad, 0, 0.0))
    
    for i in range(period, n):
        s_u = pos_cs[i + 1] - pos_cs[i + 1 - period]
        s_d = neg_cs[i + 1] - neg_cs[i + 1 - period]
        tot = s_u + s_d
        if tot > 1e-6:
            cmo[i] = 100.0 * (s_u - s_d) / tot
        else:
            cmo[i] = 0.0
    return cmo

def simulate_cmo_strategy(
    opens: np.ndarray,
    highs: np.ndarray,
    lows: np.ndarray,
    closes: np.ndarray,
    atr14: np.ndarray,
    ema50: np.ndarray,
    ema200: np.ndarray,
    kfd: np.ndarray,
    cmo: np.ndarray,
    cmo_sig: np.ndarray,
    months: np.ndarray,
    dates: pd.DatetimeIndex,
    trigger_mode: str = "cmo_thrust_expansion",
    trigger_thresh: float = 30.0,
    trend_filter: str = "ema50",
    use_kfd: bool = False,
    kfd_thresh: float = 1.35,
    tp_mult: float = 4.0,
    sl_mult: float = 2.0,
    monthly_profit_lock: float = 250.0,
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

    for i in range(50, n - 1):
        m = months[i]
        if m != cur_m:
            cur_m = m
            cur_m_pnl = 0.0
            locked_m = False

        # Manage open position
        if pos != 0:
            hit_sl = False
            hit_tp = False

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
            if not kfd_ok:
                continue

            if trend_filter == "ema200":
                trend_up = closes[i] > ema200[i]
                trend_dn = closes[i] < ema200[i]
            elif trend_filter == "ema50":
                trend_up = closes[i] > ema50[i]
                trend_dn = closes[i] < ema50[i]
            else:
                trend_up = True
                trend_dn = True

            long_sig = False
            short_sig = False

            c_now = cmo[i]
            c_prev = cmo[i - 1]

            if trigger_mode == "cmo_zero_cross":
                if (c_prev <= 0.0) and (c_now > 0.0) and trend_up:
                    long_sig = True
                elif (c_prev >= 0.0) and (c_now < 0.0) and trend_dn:
                    short_sig = True

            elif trigger_mode == "cmo_thrust_expansion":
                if (c_prev < trigger_thresh) and (c_now >= trigger_thresh) and trend_up:
                    long_sig = True
                elif (c_prev > -trigger_thresh) and (c_now <= -trigger_thresh) and trend_dn:
                    short_sig = True

            elif trigger_mode == "cmo_extreme_reversion":
                if (c_prev <= -trigger_thresh) and (c_now > -trigger_thresh) and trend_up:
                    long_sig = True
                elif (c_prev >= trigger_thresh) and (c_now < trigger_thresh) and trend_dn:
                    short_sig = True

            elif trigger_mode == "cmo_signal_cross":
                s_now = cmo_sig[i]
                s_prev = cmo_sig[i - 1]
                if (c_prev <= s_prev) and (c_now > s_now) and trend_up:
                    long_sig = True
                elif (c_prev >= s_prev) and (c_now < s_now) and trend_dn:
                    short_sig = True

            if long_sig:
                pos = 1
                entry_i = i + 1
                entry_p = opens[i + 1]
                sl_p = entry_p - (sl_mult * c_atr)
                tp_p = entry_p + (tp_mult * c_atr)

            elif short_sig:
                pos = -1
                entry_i = i + 1
                entry_p = opens[i + 1]
                sl_p = entry_p + (sl_mult * c_atr)
                tp_p = entry_p - (tp_mult * c_atr)

    return trades

def evaluate_metrics_fast(trades):
    if not trades:
        return {
            "total_trades": 0, "net_profit": 0.0, "pf": 0.0, "win_rate": 0.0,
            "max_dd": 0.0, "romad": 0.0, "mcr": 0.0, "pos_months": 0, "total_months": 72
        }

    total_trades = len(trades)
    pnls = np.array([t["pnl"] for t in trades], dtype=np.float64)
    net_profit = float(np.sum(pnls))
    wins = pnls[pnls > 0]
    losses = pnls[pnls < 0]
    gross_win = float(np.sum(wins)) if len(wins) > 0 else 0.0
    gross_loss = float(abs(np.sum(losses))) if len(losses) > 0 else 0.0

    pf = (gross_win / gross_loss) if gross_loss > 0 else (99.0 if gross_win > 0 else 0.0)
    win_rate = (len(wins) / total_trades) * 100.0

    cum = np.cumsum(pnls)
    peak = np.maximum.accumulate(cum)
    dd = peak - cum
    max_dd = float(np.max(dd)) if len(dd) > 0 else 0.0
    romad = (net_profit / max_dd) if max_dd > 0 else 0.0

    t_months = np.array([t["month"] for t in trades], dtype=np.int32)
    u_months, inv = np.unique(t_months, return_inverse=True)
    m_pnl = np.bincount(inv, weights=pnls)
    pos_months = int(np.sum(m_pnl > 0))
    total_months = 72
    mcr = (pos_months / total_months) * 100.0

    return {
        "total_trades": total_trades,
        "net_profit": round(net_profit, 2),
        "pf": round(pf, 3),
        "win_rate": round(win_rate, 2),
        "max_dd": round(max_dd, 2),
        "romad": round(romad, 2),
        "mcr": round(mcr, 2),
        "pos_months": pos_months,
        "total_months": total_months
    }

def main():
    parser = argparse.ArgumentParser(description="Sweep Strategy 91: Gold H1 Chande Momentum Oscillator (CMO)")
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
    kfd24 = compute_katz_fractal_dimension(closes, 24)

    periods = [9, 14, 20, 25]
    print("[*] Pre-computing CMO series across parameters...", flush=True)
    cmo_cache = {}
    cmo_sig_cache = {}
    for p in periods:
        c_arr = compute_cmo(closes, period=p)
        cmo_cache[p] = c_arr
        cmo_sig_cache[(p, 9)] = compute_ema(c_arr, 9)

    trigger_configs = [
        ("cmo_zero_cross", 0.0),
        ("cmo_thrust_expansion", 20.0),
        ("cmo_thrust_expansion", 30.0),
        ("cmo_thrust_expansion", 40.0),
        ("cmo_extreme_reversion", 40.0),
        ("cmo_extreme_reversion", 50.0),
        ("cmo_signal_cross", 0.0),
    ]

    trend_filters = ["ema200", "ema50", "none"]
    kfd_options = [
        (True, 1.35),
        (True, 1.40),
        (False, 1.50)
    ]
    tp_mults = [3.5, 4.0, 5.0, 6.0]
    sl_mults = [1.5, 2.0, 2.5]
    profit_locks = [0.0, 200.0, 250.0]

    total_combos = (
        len(periods) * len(trigger_configs) *
        len(trend_filters) * len(kfd_options) * len(tp_mults) * len(sl_mults) * len(profit_locks)
    )
    print(f"[*] Total sweep configurations to evaluate: {total_combos}", flush=True)

    results = []
    best_candidate = None
    best_score = -999999.0

    count = 0
    t_sweep_start = time.time()

    for p in periods:
        c_arr = cmo_cache[p]
        c_sig = cmo_sig_cache[(p, 9)]
        for (trg_m, trg_th) in trigger_configs:
            for trd in trend_filters:
                for (use_kfd, kfd_thresh) in kfd_options:
                    for tp_m in tp_mults:
                        for sl_m in sl_mults:
                            for p_lock in profit_locks:
                                count += 1
                                trades = simulate_cmo_strategy(
                                    opens=opens, highs=highs, lows=lows, closes=closes,
                                    atr14=atr14, ema50=ema50, ema200=ema200, kfd=kfd24,
                                    cmo=c_arr, cmo_sig=c_sig,
                                    months=months, dates=dates,
                                    trigger_mode=trg_m,
                                    trigger_thresh=trg_th,
                                    trend_filter=trd,
                                    use_kfd=use_kfd, kfd_thresh=kfd_thresh,
                                    tp_mult=tp_m, sl_mult=sl_m,
                                    monthly_profit_lock=p_lock, monthly_loss_breaker=250.0
                                )
                                met = evaluate_metrics_fast(trades)

                                if met["total_trades"] >= 60 and met["max_dd"] > 0:
                                    score = (met["net_profit"] * met["pf"] * (met["mcr"] / 100.0)) / (met["max_dd"] ** 0.5)
                                else:
                                    score = -1000.0

                                row = {
                                    "period": p,
                                    "trigger_mode": trg_m,
                                    "trigger_thresh": trg_th,
                                    "trend_filter": trd,
                                    "use_kfd": use_kfd,
                                    "kfd_thresh": kfd_thresh,
                                    "tp_mult": tp_m,
                                    "sl_mult": sl_m,
                                    "profit_lock": p_lock,
                                    **met,
                                    "score": round(score, 2)
                                }
                                results.append(row)

                                if score > best_score and met["total_trades"] >= 60 and met["pf"] >= 1.40:
                                    best_score = score
                                    best_candidate = row
                                    print(
                                        f"[{count}/{total_combos}] New Best: CMO({p}) | Trg={trg_m}({trg_th}) | "
                                        f"Trd={trd} | KFD={use_kfd} | TP={tp_m} | SL={sl_m} | Lock={p_lock} -> "
                                        f"Trades={met['total_trades']}, Net=${met['net_profit']:.2f}, "
                                        f"PF={met['pf']:.3f}, DD=${met['max_dd']:.2f}, RoMaD={met['romad']:.2f}x, MCR={met['mcr']:.1f}%",
                                        flush=True
                                    )

    t_sweep_end = time.time()
    print(f"[*] Sweep completed in {t_sweep_end - t_sweep_start:.2f} seconds.", flush=True)

    df_results = pd.DataFrame(results)
    out_csv = os.path.join(args.out_dir, "strategy_91_cmo_sweep_results.csv")
    df_results.to_csv(out_csv, index=False)
    print(f"[+] Saved all {len(df_results)} sweep results to {out_csv}", flush=True)

    out_json = os.path.join(args.out_dir, "strategy_91_champion.json")
    with open(out_json, "w") as f:
        json.dump({
            "strategy_id": "STRATEGY_91",
            "strategy_name": "Gold H1 Tushar Chande Momentum Oscillator (CMO-MPE-KFD)",
            "champion": best_candidate,
            "runtime_seconds": round(t_sweep_end - t_start, 2)
        }, f, indent=2)
    print(f"[+] Saved champion candidate to {out_json}", flush=True)

    print("\n" + "=" * 80, flush=True)
    print("STRATEGY 91 CHAMPION CANDIDATE AUDIT", flush=True)
    print("=" * 80, flush=True)
    if best_candidate:
        for k, v in best_candidate.items():
            print(f"  {k}: {v}", flush=True)
    else:
        print("  No viable candidate passed thresholds (total_trades >= 60, PF >= 1.40)", flush=True)
    print("=" * 80, flush=True)

if __name__ == "__main__":
    main()
