#!/usr/bin/env python3
"""
===============================================================================
STRATEGY 89: GOLD H1 IGOR LIVSHIN'S BALANCE OF POWER (BOP-IBV-KFD)
===============================================================================
Hypothesis & Market Edge:
1. Igor Livshin's Balance of Power (2001):
   - Measures market strength by assessing the ability of buyers and sellers
     to push price to extreme levels relative to the candle range.
   - Raw bar formulation:
     BOP_raw[i] = (Close[i] - Open[i]) / (High[i] - Low[i])  if High[i] > Low[i] else 0.0
   - Smoothed over lookback window p using SMA or EMA:
     BOP[i] = MA(BOP_raw, p)
   - Evaluates internal auction dominance (-1.0 to +1.0) independent of price level.
2. Signal Mechanics & Trigger Variations:
   - 'bop_zero_cross': BOP crosses 0.0 level in macro trend direction.
   - 'bop_extreme_inflection': Bullish reversion when BOP dips below -thresh and turns up;
     Bearish reversion when BOP rises above +thresh and turns down.
   - 'bop_thrust_expansion': Buyer dominance expansion (BOP crosses above +thresh);
     Seller dominance expansion (BOP crosses below -thresh).
   - 'bop_continuation_turn': BOP pulls back and turns back in trend direction while on correct side of 0.
3. Institutional Filters:
   - Trend Filter: EMA200, EMA50, or None.
   - Anti-Chaos Gate: Katz Fractal Dimension (KFD <= 1.35 or 1.40).
   - Asymmetric R:R Take Profit (3.5R to 6.0R) with ATR-based Stop Loss.
4. Validation Standard:
   - 72 Calendar Months (2020-01-01 to 2025-12-30).
   - Realistic CFD Frictions: $0.25 spread ($25/lot) + $6.00 commission ($3.10 / 0.10 lot).
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

def compute_sma(series: np.ndarray, period: int) -> np.ndarray:
    n = len(series)
    sma = np.zeros(n, dtype=np.float64)
    if period <= n:
        csum = np.cumsum(np.insert(series, 0, 0))
        sma[period - 1:] = (csum[period:] - csum[:-period]) / period
        sma[:period - 1] = series[:period - 1]
    return sma

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

def compute_bop(opens: np.ndarray, highs: np.ndarray, lows: np.ndarray, closes: np.ndarray, period: int = 14, smooth_type: str = "sma") -> np.ndarray:
    n = len(closes)
    hl = highs - lows
    co = closes - opens
    raw_bop = np.zeros(n, dtype=np.float64)
    valid = hl > 1e-4
    raw_bop[valid] = co[valid] / hl[valid]
    raw_bop = np.clip(raw_bop, -1.0, 1.0)

    if smooth_type == "ema":
        return compute_ema(raw_bop, period)
    else:
        return compute_sma(raw_bop, period)

def simulate_bop_strategy(
    opens: np.ndarray,
    highs: np.ndarray,
    lows: np.ndarray,
    closes: np.ndarray,
    atr14: np.ndarray,
    ema50: np.ndarray,
    ema200: np.ndarray,
    kfd: np.ndarray,
    bop: np.ndarray,
    months: np.ndarray,
    dates: pd.DatetimeIndex,
    trigger_mode: str = "bop_zero_cross",
    trigger_thresh: float = 0.20,
    trend_filter: str = "ema50",
    use_kfd: bool = True,
    kfd_thresh: float = 1.35,
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

            b_now = bop[i]
            b_prev = bop[i - 1]
            b_prev2 = bop[i - 2]

            if trigger_mode == "bop_zero_cross":
                # Zero line cross
                if (b_prev <= 0.0) and (b_now > 0.0) and trend_up:
                    long_sig = True
                elif (b_prev >= 0.0) and (b_now < 0.0) and trend_dn:
                    short_sig = True

            elif trigger_mode == "bop_extreme_inflection":
                # Extreme bounce
                if (b_prev <= -trigger_thresh) and (b_now > b_prev) and trend_up:
                    long_sig = True
                elif (b_prev >= trigger_thresh) and (b_now < b_prev) and trend_dn:
                    short_sig = True

            elif trigger_mode == "bop_thrust_expansion":
                # Breakout thrust
                if (b_prev < trigger_thresh) and (b_now >= trigger_thresh) and trend_up:
                    long_sig = True
                elif (b_prev > -trigger_thresh) and (b_now <= -trigger_thresh) and trend_dn:
                    short_sig = True

            elif trigger_mode == "bop_continuation_turn":
                # Inflection on active side
                if (b_prev > 0.0) and (b_now > b_prev) and (b_prev <= b_prev2) and trend_up:
                    long_sig = True
                elif (b_prev < 0.0) and (b_now < b_prev) and (b_prev >= b_prev2) and trend_dn:
                    short_sig = True

            if long_sig and kfd_ok:
                pos = 1
                entry_i = i + 1
                entry_p = opens[i + 1]
                sl_p = entry_p - (sl_mult * c_atr)
                tp_p = entry_p + (tp_mult * c_atr)

            elif short_sig and kfd_ok:
                pos = -1
                entry_i = i + 1
                entry_p = opens[i + 1]
                sl_p = entry_p + (sl_mult * c_atr)
                tp_p = entry_p - (tp_mult * c_atr)

    return trades

def evaluate_metrics(trades):
    if not trades:
        return {
            "total_trades": 0, "net_profit": 0.0, "pf": 0.0, "win_rate": 0.0,
            "max_dd": 0.0, "romad": 0.0, "mcr": 0.0, "pos_months": 0, "total_months": 72
        }

    df = pd.DataFrame(trades)
    total_trades = len(df)
    net_profit = df["pnl"].sum()

    wins = df[df["pnl"] > 0]["pnl"].sum()
    losses = abs(df[df["pnl"] < 0]["pnl"].sum())

    pf = (wins / losses) if losses > 0 else (99.0 if wins > 0 else 0.0)
    win_rate = (len(df[df["pnl"] > 0]) / total_trades) * 100.0

    df["cum"] = df["pnl"].cumsum()
    df["peak"] = df["cum"].cummax()
    df["dd"] = df["peak"] - df["cum"]
    max_dd = df["dd"].max() if len(df) > 0 else 0.0

    romad = (net_profit / max_dd) if max_dd > 0 else 0.0

    monthly = df.groupby("month")["pnl"].sum()
    pos_months = int((monthly > 0).sum())
    total_months = 72
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
    parser = argparse.ArgumentParser(description="Sweep Strategy 89: Gold H1 Balance of Power (BOP)")
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

    periods = [10, 14, 20, 24]
    smooth_types = ["sma", "ema"]

    print("[*] Pre-computing BOP series across parameters...", flush=True)
    bop_cache = {}
    for p in periods:
        for st in smooth_types:
            bop_cache[(p, st)] = compute_bop(opens, highs, lows, closes, period=p, smooth_type=st)

    trigger_configs = [
        ("bop_zero_cross", 0.0),
        ("bop_extreme_inflection", 0.25),
        ("bop_extreme_inflection", 0.30),
        ("bop_extreme_inflection", 0.35),
        ("bop_thrust_expansion", 0.15),
        ("bop_thrust_expansion", 0.20),
        ("bop_thrust_expansion", 0.25),
        ("bop_continuation_turn", 0.0),
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
        len(periods) * len(smooth_types) * len(trigger_configs) *
        len(trend_filters) * len(kfd_options) * len(tp_mults) * len(sl_mults) * len(profit_locks)
    )
    print(f"[*] Total sweep configurations to evaluate: {total_combos}", flush=True)

    results = []
    best_candidate = None
    best_score = -999999.0

    count = 0
    t_sweep_start = time.time()

    for p in periods:
        for st in smooth_types:
            b_arr = bop_cache[(p, st)]
            for (trg_m, trg_th) in trigger_configs:
                for trd in trend_filters:
                    for (use_kfd, kfd_thresh) in kfd_options:
                        for tp_m in tp_mults:
                            for sl_m in sl_mults:
                                for p_lock in profit_locks:
                                    count += 1
                                    trades = simulate_bop_strategy(
                                        opens=opens, highs=highs, lows=lows, closes=closes,
                                        atr14=atr14, ema50=ema50, ema200=ema200, kfd=kfd24,
                                        bop=b_arr,
                                        months=months, dates=dates,
                                        trigger_mode=trg_m,
                                        trigger_thresh=trg_th,
                                        trend_filter=trd,
                                        use_kfd=use_kfd, kfd_thresh=kfd_thresh,
                                        tp_mult=tp_m, sl_mult=sl_m,
                                        monthly_profit_lock=p_lock, monthly_loss_breaker=250.0
                                    )
                                    met = evaluate_metrics(trades)

                                    if met["total_trades"] >= 60 and met["max_dd"] > 0:
                                        score = (met["net_profit"] * met["pf"] * (met["mcr"] / 100.0)) / (met["max_dd"] ** 0.5)
                                    else:
                                        score = -1000.0

                                    row = {
                                        "period": p,
                                        "smooth_type": st,
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
                                            f"[{count}/{total_combos}] New Best: BOP({p},{st}) | Trg={trg_m}({trg_th}) | "
                                            f"Trd={trd} | KFD={use_kfd} | TP={tp_m} | SL={sl_m} | Lock={p_lock} -> "
                                            f"Trades={met['total_trades']}, Net=${met['net_profit']:.2f}, "
                                            f"PF={met['pf']:.3f}, DD=${met['max_dd']:.2f}, RoMaD={met['romad']:.2f}x, MCR={met['mcr']:.1f}%",
                                            flush=True
                                        )

    t_sweep_end = time.time()
    print(f"[*] Sweep completed in {t_sweep_end - t_sweep_start:.2f} seconds.", flush=True)

    df_results = pd.DataFrame(results)
    out_csv = os.path.join(args.out_dir, "strategy_89_bop_sweep_results.csv")
    df_results.to_csv(out_csv, index=False)
    print(f"[+] Saved all {len(df_results)} sweep results to {out_csv}", flush=True)

    out_json = os.path.join(args.out_dir, "strategy_89_champion.json")
    with open(out_json, "w") as f:
        json.dump({
            "strategy_id": "STRATEGY_89",
            "strategy_name": "Gold H1 Igor Livshin Balance of Power (BOP-IBV-KFD)",
            "champion": best_candidate,
            "runtime_seconds": round(t_sweep_end - t_start, 2)
        }, f, indent=2)
    print(f"[+] Saved champion candidate to {out_json}", flush=True)

    print("\n" + "=" * 80, flush=True)
    print("STRATEGY 89 CHAMPION CANDIDATE AUDIT", flush=True)
    print("=" * 80, flush=True)
    if best_candidate:
        for k, v in best_candidate.items():
            print(f"  {k}: {v}", flush=True)
    else:
        print("  No viable candidate passed thresholds (total_trades >= 60, PF >= 1.40)", flush=True)
    print("=" * 80, flush=True)

if __name__ == "__main__":
    main()
