#!/usr/bin/env python3
"""
===============================================================================
STRATEGY 87: GOLD H1 DONALD DORSEY'S MASS INDEX VOLATILITY REVERSAL BULGE (MASS-VRB-KFD)
===============================================================================
Hypothesis & Market Edge:
1. Donald Dorsey's Mass Index (1992):
   - Designed to identify trend reversals and volatility expansion by measuring
     the narrowing and widening of high-low price range without directional distortion.
   - Mathematical Formulation:
     High-Low Range: HL[i] = High[i] - Low[i]
     Single EMA: EMA1[i] = EMA(HL, p1)
     Double EMA: EMA2[i] = EMA(EMA1, p1)
     EMA Ratio: Ratio[i] = EMA1[i] / EMA2[i]
     Mass Index: MI[i] = Sum(Ratio, p2)
   - Baseline equilibrium around 25.0 (when EMA1 == EMA2).
2. Signal Mechanics & Trigger Variations:
   - 'dorsey_reversal_bulge': Classic Donald Dorsey Reversal Bulge:
     MI rises above bulge_high (e.g. 26.5/27.0) indicating volatility climax,
     then drops below bulge_low (e.g. 26.0/26.5). Dorsey's counter-trend hypothesis:
     if price < EMA50 -> BUY (exhaustion rebound); if price > EMA50 -> SELL.
   - 'dorsey_continuation_bulge': Modern commodity trend continuation:
     When the bulge resolves (drops below bulge_low), the consolidation ends and
     macro trend resumes: if price > EMA50 -> BUY; if price < EMA50 -> SELL.
   - 'mass_expansion_ignition': Early volatility explosion trigger:
     MI crosses above threshold (e.g. 25.5, 26.0, 26.5):
     if price > EMA50 -> BUY; if price < EMA50 -> SELL.
   - 'mass_compression_turn': Compression exhaustion inflection:
     MI drops below compression threshold (e.g. 24.2, 24.5, 24.8) and turns up:
     if price > EMA50 -> BUY; if price < EMA50 -> SELL.
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

def compute_mass_index(highs: np.ndarray, lows: np.ndarray, ema_period: int = 9, sum_period: int = 25) -> np.ndarray:
    n = len(highs)
    hl = highs - lows
    ema1 = compute_ema(hl, ema_period)
    ema2 = compute_ema(ema1, ema_period)
    ratio = np.ones(n, dtype=np.float64)
    valid_mask = ema2 > 1e-6
    ratio[valid_mask] = ema1[valid_mask] / ema2[valid_mask]

    csum = np.cumsum(np.insert(ratio, 0, 0))
    mi = np.full(n, float(sum_period), dtype=np.float64)
    if sum_period <= n:
        mi[sum_period - 1:] = csum[sum_period:] - csum[:-sum_period]
    return mi

def compute_recent_bulge(mi: np.ndarray, threshold: float, window: int = 12) -> np.ndarray:
    """Precompute rolling window max flag for high Mass Index bulge efficiently."""
    n = len(mi)
    mask = (mi >= threshold).astype(np.float64)
    csum = np.cumsum(np.insert(mask, 0, 0))
    res = np.zeros(n, dtype=bool)
    if window <= n:
        roll_sum = csum[window:] - csum[:-window]
        res[window - 1:] = roll_sum > 0
    return res

def simulate_mass_index_strategy(
    opens: np.ndarray,
    highs: np.ndarray,
    lows: np.ndarray,
    closes: np.ndarray,
    atr14: np.ndarray,
    ema50: np.ndarray,
    ema200: np.ndarray,
    kfd: np.ndarray,
    mi: np.ndarray,
    recent_bulge: np.ndarray,
    months: np.ndarray,
    dates: pd.DatetimeIndex,
    trigger_family: str = "dorsey_reversal_bulge",
    trigger_param1: float = 27.0,
    trigger_param2: float = 26.5,
    trend_filter: str = "ema50",
    use_kfd: bool = True,
    kfd_thresh: float = 1.40,
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

            mi_now = mi[i]
            mi_prev = mi[i - 1]
            mi_prev2 = mi[i - 2]

            if trigger_family == "dorsey_reversal_bulge":
                bulge_drop = recent_bulge[i] and (mi_prev >= trigger_param2) and (mi_now < trigger_param2)
                if bulge_drop:
                    if trend_dn:
                        long_sig = True
                    elif trend_up:
                        short_sig = True

            elif trigger_family == "dorsey_continuation_bulge":
                bulge_drop = recent_bulge[i] and (mi_prev >= trigger_param2) and (mi_now < trigger_param2)
                if bulge_drop:
                    if trend_up:
                        long_sig = True
                    elif trend_dn:
                        short_sig = True

            elif trigger_family == "mass_expansion_ignition":
                crossed_up = (mi_prev < trigger_param1) and (mi_now >= trigger_param1)
                if crossed_up:
                    if trend_up:
                        long_sig = True
                    elif trend_dn:
                        short_sig = True

            elif trigger_family == "mass_compression_turn":
                inflected = (mi_prev <= trigger_param1) and (mi_now > mi_prev) and (mi_prev <= mi_prev2)
                if inflected:
                    if trend_up:
                        long_sig = True
                    elif trend_dn:
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
    parser = argparse.ArgumentParser(description="Sweep Strategy 87: Gold H1 Mass Index Volatility Reversal & Expansion")
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

    ema_periods = [7, 9, 12]
    sum_periods = [25] # classic Dorsey 25-period window

    print("[*] Pre-computing Mass Index series across parameters...", flush=True)
    mi_cache = {}
    for p1 in ema_periods:
        for p2 in sum_periods:
            mi_cache[(p1, p2)] = compute_mass_index(highs, lows, ema_period=p1, sum_period=p2)

    # Pre-compute bulge caches
    bulge_cache = {}
    for p1 in ema_periods:
        for p2 in sum_periods:
            mi_arr = mi_cache[(p1, p2)]
            for b_high in [26.0, 26.5, 27.0]:
                bulge_cache[(p1, p2, b_high)] = compute_recent_bulge(mi_arr, b_high, window=12)

    dummy_bulge = np.zeros(len(closes), dtype=bool)

    trigger_configs = [
        # Classic Dorsey Reversal Bulge (exhaustion rebound)
        ("dorsey_reversal_bulge", 27.0, 26.5),
        ("dorsey_reversal_bulge", 26.5, 26.0),
        ("dorsey_reversal_bulge", 27.0, 26.0),
        # Trend Continuation Bulge (volatility resolution into trend resumption)
        ("dorsey_continuation_bulge", 27.0, 26.5),
        ("dorsey_continuation_bulge", 26.5, 26.0),
        ("dorsey_continuation_bulge", 27.0, 26.0),
        # Mass Expansion Ignition (early volatility breakout)
        ("mass_expansion_ignition", 25.5, 0.0),
        ("mass_expansion_ignition", 26.0, 0.0),
        ("mass_expansion_ignition", 26.5, 0.0),
        # Mass Compression Turn (range contraction exhaustion)
        ("mass_compression_turn", 24.2, 0.0),
        ("mass_compression_turn", 24.5, 0.0),
        ("mass_compression_turn", 24.8, 0.0),
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
        len(ema_periods) * len(sum_periods) * len(trigger_configs) *
        len(trend_filters) * len(kfd_options) * len(tp_mults) * len(sl_mults) * len(profit_locks)
    )
    print(f"[*] Total sweep configurations to evaluate: {total_combos}", flush=True)

    results = []
    best_candidate = None
    best_score = -999999.0

    count = 0
    t_sweep_start = time.time()

    for p1 in ema_periods:
        for p2 in sum_periods:
            mi_arr = mi_cache[(p1, p2)]
            for (trg_fam, p_trg1, p_trg2) in trigger_configs:
                if "bulge" in trg_fam:
                    b_arr = bulge_cache.get((p1, p2, p_trg1), dummy_bulge)
                else:
                    b_arr = dummy_bulge

                for trd in trend_filters:
                    for (use_kfd, kfd_thresh) in kfd_options:
                        for tp_m in tp_mults:
                            for sl_m in sl_mults:
                                for p_lock in profit_locks:
                                    count += 1
                                    trades = simulate_mass_index_strategy(
                                        opens=opens, highs=highs, lows=lows, closes=closes,
                                        atr14=atr14, ema50=ema50, ema200=ema200, kfd=kfd24,
                                        mi=mi_arr,
                                        recent_bulge=b_arr,
                                        months=months, dates=dates,
                                        trigger_family=trg_fam,
                                        trigger_param1=p_trg1,
                                        trigger_param2=p_trg2,
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
                                        "ema_period": p1,
                                        "sum_period": p2,
                                        "trigger_family": trg_fam,
                                        "trigger_param1": p_trg1,
                                        "trigger_param2": p_trg2,
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
                                            f"[{count}/{total_combos}] New Best: MI({p1},{p2}) | Trg={trg_fam}({p_trg1},{p_trg2}) | "
                                            f"Trd={trd} | KFD={use_kfd} | TP={tp_m} | SL={sl_m} | Lock={p_lock} -> "
                                            f"Trades={met['total_trades']}, Net=${met['net_profit']:.2f}, "
                                            f"PF={met['pf']:.3f}, DD=${met['max_dd']:.2f}, RoMaD={met['romad']:.2f}x, MCR={met['mcr']:.1f}%",
                                            flush=True
                                        )

    t_sweep_end = time.time()
    print(f"[*] Sweep completed in {t_sweep_end - t_sweep_start:.2f} seconds.", flush=True)

    df_results = pd.DataFrame(results)
    out_csv = os.path.join(args.out_dir, "strategy_87_mass_index_sweep_results.csv")
    df_results.to_csv(out_csv, index=False)
    print(f"[+] Saved all {len(df_results)} sweep results to {out_csv}", flush=True)

    out_json = os.path.join(args.out_dir, "strategy_87_champion.json")
    with open(out_json, "w") as f:
        json.dump({
            "strategy_id": "STRATEGY_87",
            "strategy_name": "Gold H1 Donald Dorsey Mass Index Volatility Reversal & Expansion (MASS-VRB-KFD)",
            "champion": best_candidate,
            "runtime_seconds": round(t_sweep_end - t_start, 2)
        }, f, indent=2)
    print(f"[+] Saved champion candidate to {out_json}", flush=True)

    print("\n" + "=" * 80, flush=True)
    print("STRATEGY 87 CHAMPION CANDIDATE AUDIT", flush=True)
    print("=" * 80, flush=True)
    if best_candidate:
        for k, v in best_candidate.items():
            print(f"  {k}: {v}", flush=True)
    else:
        print("  No viable candidate passed thresholds (total_trades >= 60, PF >= 1.40)", flush=True)
    print("=" * 80, flush=True)

if __name__ == "__main__":
    main()
