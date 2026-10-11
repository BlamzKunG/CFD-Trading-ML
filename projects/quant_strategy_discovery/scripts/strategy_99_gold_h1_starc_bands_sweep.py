#!/usr/bin/env python3
"""
===============================================================================
STRATEGY 99: GOLD H1 MANNING STOLLER'S STARCBANDS (STARC-ATR-KFD) SWEEP
===============================================================================
Asset: XAUUSD (Gold CFD)
Timeframe: H1
Data Source: Lightweight Parquet Cache (Mobile Hardware Protected, Zero OOM)
Horizon: 2020-01-01 to 2025-12-30 (72 Calendar Months)
Execution Model: Next-Bar Open Fill, $0.25 Spread ($2.50/0.10 lot), $6/lot Comm ($0.60/0.10 lot)
Hypothesis:
  Manning Stoller developed STARCBands (Stoller Average Range Channels) in 1980 to
  establish dynamic volatility envelopes around a moving average using ATR:
    UpperBand = SMA(period) + mult * ATR(atr_period)
    LowerBand = SMA(period) - mult * ATR(atr_period)
  Unlike Bollinger Bands (which use standard deviation and expand erratically during
  extreme moves), STARCBands maintain strict linear volatility proportionality.
  When combined with Katz Fractal Gating (KFD <= 1.40) and Macro Structural Trend (EMA200),
  breakouts from compressed STARC envelopes provide an asymmetric institutional edge on Gold H1.
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
    atr = np.zeros(n, dtype=np.float64)
    tr = np.zeros(n, dtype=np.float64)
    tr[0] = highs[0] - lows[0]
    for i in range(1, n):
        hl = highs[i] - lows[i]
        hc = abs(highs[i] - closes[i - 1])
        lc = abs(lows[i] - closes[i - 1])
        tr[i] = max(hl, max(hc, lc))
    atr[period - 1] = np.mean(tr[:period])
    alpha = 1.0 / period
    for i in range(period, n):
        atr[i] = (tr[i] * alpha) + (atr[i - 1] * (1.0 - alpha))
    return atr

def compute_sma(series: np.ndarray, period: int) -> np.ndarray:
    return pd.Series(series).rolling(period, min_periods=1).mean().values

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

def simulate_starc_strategy(
    opens: np.ndarray,
    highs: np.ndarray,
    lows: np.ndarray,
    closes: np.ndarray,
    atr14: np.ndarray,
    ema50: np.ndarray,
    ema200: np.ndarray,
    kfd: np.ndarray,
    upper_band: np.ndarray,
    lower_band: np.ndarray,
    mid_sma: np.ndarray,
    months: np.ndarray,
    dates: pd.DatetimeIndex,
    trigger_mode: str = "starc_breakout",
    trend_filter: str = "ema200",
    use_kfd: bool = True,
    kfd_thresh: float = 1.40,
    tp_mult: float = 4.5,
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

            c_prev = closes[i - 1]
            c_now = closes[i]
            ub_prev = upper_band[i - 1]
            ub_now = upper_band[i]
            lb_prev = lower_band[i - 1]
            lb_now = lower_band[i]
            mid_now = mid_sma[i]

            if trigger_mode == "starc_breakout":
                # Price pierces outer band
                if (c_prev <= ub_prev) and (c_now > ub_now) and trend_up:
                    long_sig = True
                elif (c_prev >= lb_prev) and (c_now < lb_now) and trend_dn:
                    short_sig = True

            elif trigger_mode == "starc_pullback_bounce":
                # Pullback to middle SMA and bounces outward
                if (lows[i - 1] <= mid_now) and (c_now > mid_now) and (c_now > opens[i]) and trend_up:
                    long_sig = True
                elif (highs[i - 1] >= mid_now) and (c_now < mid_now) and (c_now < opens[i]) and trend_dn:
                    short_sig = True

            elif trigger_mode == "starc_envelope_reversion":
                # Deep overextension hooks inward
                if (highs[i - 1] >= ub_prev) and (c_now < ub_now) and (c_now < opens[i]):
                    short_sig = True
                elif (lows[i - 1] <= lb_prev) and (c_now > lb_now) and (c_now > opens[i]):
                    long_sig = True

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
    parser = argparse.ArgumentParser(description="Sweep Strategy 99: Gold H1 Manning Stoller STARCBands")
    parser.add_argument("--data_dir", type=str, default="projects/quant_strategy_discovery/data")
    parser.add_argument("--out_dir", type=str, default="projects/quant_strategy_discovery/results")
    args = parser.parse_args()

    os.makedirs(args.out_dir, exist_ok=True)
    t_start = time.time()

    print("[*] Loading XAUUSD H1 Lightweight Parquet Cache...", flush=True)
    df_h1 = pd.read_parquet(os.path.join(args.data_dir, "XAUUSD_H1.parquet"))
    opens = df_h1["open"].values.astype(np.float64)
    highs = df_h1["high"].values.astype(np.float64)
    lows = df_h1["low"].values.astype(np.float64)
    closes = df_h1["close"].values.astype(np.float64)
    dates = df_h1.index
    months = (dates.year.values * 100 + dates.month.values).astype(np.int32)

    print(f"[*] Loaded H1 bars: {len(closes)} bars across {len(np.unique(months))} calendar months.", flush=True)

    print("[*] Pre-computing ATR, EMAs, KFD...", flush=True)
    atr14 = compute_atr(highs, lows, closes, 14)
    atr10 = compute_atr(highs, lows, closes, 10)
    ema50 = compute_ema(closes, 50)
    ema200 = compute_ema(closes, 200)
    kfd24 = compute_katz_fractal_dimension(closes, 24)

    sma_periods = [6, 10, 14, 20]
    multipliers = [1.2, 1.5, 1.8, 2.0]
    atr_options = [(14, atr14), (10, atr10)]

    print("[*] Pre-computing STARC Band variations...", flush=True)
    starc_cache = {}
    for sp in sma_periods:
        sma_val = compute_sma(closes, sp)
        for (ap, atr_arr) in atr_options:
            for mult in multipliers:
                ub = sma_val + (mult * atr_arr)
                lb = sma_val - (mult * atr_arr)
                starc_cache[(sp, ap, mult)] = (ub, lb, sma_val)

    trigger_modes = ["starc_breakout", "starc_pullback_bounce"]
    trend_filters = ["ema200", "ema50"]
    kfd_options = [(True, 1.40), (False, 1.50)]
    tp_mults = [3.5, 4.5, 5.5]
    sl_mults = [2.0, 2.5]
    profit_locks = [200.0, 250.0]

    total_combos = (
        len(sma_periods) * len(atr_options) * len(multipliers) *
        len(trigger_modes) * len(trend_filters) * len(kfd_options) *
        len(tp_mults) * len(sl_mults) * len(profit_locks)
    )
    print(f"[*] Total STARC configurations to evaluate: {total_combos}", flush=True)

    results = []
    best_candidate = None
    best_score = -999999.0

    count = 0
    t_sweep_start = time.time()

    for sp in sma_periods:
        for (ap, atr_arr) in atr_options:
            for mult in multipliers:
                ub, lb, mid_sma = starc_cache[(sp, ap, mult)]
                for trg in trigger_modes:
                    for trd in trend_filters:
                        for (use_kfd, kfd_th) in kfd_options:
                            for tp_m in tp_mults:
                                for sl_m in sl_mults:
                                    for p_lock in profit_locks:
                                        count += 1
                                        trades = simulate_starc_strategy(
                                            opens=opens, highs=highs, lows=lows, closes=closes,
                                            atr14=atr14, ema50=ema50, ema200=ema200, kfd=kfd24,
                                            upper_band=ub, lower_band=lb, mid_sma=mid_sma,
                                            months=months, dates=dates,
                                            trigger_mode=trg, trend_filter=trd,
                                            use_kfd=use_kfd, kfd_thresh=kfd_th,
                                            tp_mult=tp_m, sl_mult=sl_m,
                                            monthly_profit_lock=p_lock, monthly_loss_breaker=250.0
                                        )
                                        met = evaluate_metrics_fast(trades)

                                        if met["total_trades"] >= 60 and met["max_dd"] > 0:
                                            score = (met["net_profit"] * met["pf"] * (met["mcr"] / 100.0)) / (met["max_dd"] ** 0.5)
                                        else:
                                            score = -1000.0

                                        row = {
                                            "sma_period": sp,
                                            "atr_period": ap,
                                            "multiplier": mult,
                                            "trigger_mode": trg,
                                            "trend_filter": trd,
                                            "use_kfd": use_kfd,
                                            "kfd_thresh": kfd_th,
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
                                                f"[{count}/{total_combos}] New Best: STARC({sp}, ATR{ap}, x{mult}) | "
                                                f"Trg={trg} | Trd={trd} | KFD={use_kfd} | TP={tp_m} | SL={sl_m} | Lock={p_lock} -> "
                                                f"Trades={met['total_trades']}, Net=${met['net_profit']:.2f}, "
                                                f"PF={met['pf']:.3f}, DD=${met['max_dd']:.2f}, RoMaD={met['romad']:.2f}x, MCR={met['mcr']:.1f}%",
                                                flush=True
                                            )

    t_sweep_end = time.time()
    print(f"[*] Sweep completed in {t_sweep_end - t_sweep_start:.2f} seconds.", flush=True)

    df_results = pd.DataFrame(results)
    out_csv = os.path.join(args.out_dir, "strategy_99_starc_bands_sweep_results.csv")
    df_results.to_csv(out_csv, index=False)
    print(f"[+] Saved all {len(df_results)} sweep results to {out_csv}", flush=True)

    out_json = os.path.join(args.out_dir, "strategy_99_champion.json")
    with open(out_json, "w") as f:
        json.dump({
            "strategy_id": "STRATEGY_99",
            "strategy_name": "Gold H1 Manning Stoller STARCBands (STARC-ATR-KFD)",
            "champion": best_candidate,
            "runtime_seconds": round(t_sweep_end - t_start, 2)
        }, f, indent=2)
    print(f"[+] Saved champion candidate to {out_json}", flush=True)

    print("\n" + "=" * 80, flush=True)
    print("STRATEGY 99 CHAMPION CANDIDATE AUDIT", flush=True)
    print("=" * 80, flush=True)
    if best_candidate:
        for k, v in best_candidate.items():
            print(f"  {k}: {v}", flush=True)
    else:
        print("  No viable candidate passed thresholds (total_trades >= 60, PF >= 1.40)", flush=True)
    print("=" * 80, flush=True)

if __name__ == "__main__":
    main()
