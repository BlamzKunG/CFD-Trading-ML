#!/usr/bin/env python3
"""
===============================================================================
STRATEGY 64: GOLD H1 DEMARKER DYNAMIC EXHAUSTION & FRACTAL CONTINUATION (DEM-KFD)
===============================================================================
Hypothesis & Market Edge:
1. Tom DeMark's DeMarker Indicator (DeM):
   - Formulated by Thomas DeMark to quantify directional exhaustion without price lag.
   - DeMax_i = max(High_i - High_{i-1}, 0)
   - DeMin_i = max(Low_{i-1} - Low_i, 0)
   - DeM_i = SMA(DeMax, period) / (SMA(DeMax, period) + SMA(DeMin, period))
   - Strictly bounded in [0.0, 1.0].
2. Exhaustion Pullback Re-Entry Logic:
   - In secular bull trend (Close > EMA200): When DeM dips <= 0.30 (or 0.35) and crosses back above,
     selling exhaustion has ended, triggering a high-expectancy trend continuation LONG.
   - In secular bear trend (Close < EMA200): When DeM rallies >= 0.70 (or 0.65) and crosses back below,
     counter-trend buying exhaustion has ended, triggering a trend continuation SHORT.
3. Katz Fractal Dimension Gate (KFD):
   - Filters out choppy/random walk market regimes (KFD <= 1.40 or 1.45).
4. ASAR Monthly Risk Governance & Frictions:
   - Spread: $0.25 ($25.00/lot), Commission: $6.00/lot ($3.10 total / 0.10 lot).
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

def compute_demarker(highs: np.ndarray, lows: np.ndarray, period: int = 14) -> np.ndarray:
    """
    Computes Tom DeMark's DeMarker Indicator:
    DeMax = max(High_i - High_{i-1}, 0)
    DeMin = max(Low_{i-1} - Low_i, 0)
    DeM = SMA(DeMax, period) / (SMA(DeMax, period) + SMA(DeMin, period))
    """
    n = len(highs)
    demax = np.zeros(n, dtype=np.float64)
    demin = np.zeros(n, dtype=np.float64)
    for i in range(1, n):
        diff_h = highs[i] - highs[i - 1]
        demax[i] = diff_h if diff_h > 0 else 0.0
        diff_l = lows[i - 1] - lows[i]
        demin[i] = diff_l if diff_l > 0 else 0.0

    s_demax = pd.Series(demax).rolling(period).mean().values
    s_demin = pd.Series(demin).rolling(period).mean().values

    denom = s_demax + s_demin
    dem = np.where(denom > 1e-8, s_demax / denom, 0.5)
    return np.nan_to_num(dem, nan=0.5)

def simulate_demarker_strategy(
    opens: np.ndarray,
    highs: np.ndarray,
    lows: np.ndarray,
    closes: np.ndarray,
    atr14: np.ndarray,
    ema200: np.ndarray,
    kfd: np.ndarray,
    dem: np.ndarray,
    months: np.ndarray,
    dates: pd.DatetimeIndex,
    oversold: float = 0.30,
    overbought: float = 0.70,
    use_kfd: bool = True,
    kfd_thresh: float = 1.45,
    use_ema200: bool = True,
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
    spread_cost = spread * lot_size * 100.0 # 0.10 lot Gold = 10 oz -> $2.50
    fixed_friction = spread_cost + comm_cost # $3.10 total roundturn

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
                hit_tp = False; hit_sl = True # Conservative assumption

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

        # Check entry signals if flat
        if pos == 0 and not locked_m:
            c_atr = atr14[i]
            if c_atr < 0.5: continue

            kfd_ok = (kfd[i] <= kfd_thresh) if use_kfd else True
            ema_long_ok = (closes[i] > ema200[i]) if use_ema200 else True
            ema_short_ok = (closes[i] < ema200[i]) if use_ema200 else True

            # DeMarker Exhaustion Turnaround Triggers
            # Bullish: DeM was oversold (<= oversold) on previous bar and crosses back up (> oversold) on current bar
            dem_bull_turn = (dem[i] > oversold) and (dem[i - 1] <= oversold)
            # Bearish: DeM was overbought (>= overbought) on previous bar and crosses back down (< overbought) on current bar
            dem_bear_turn = (dem[i] < overbought) and (dem[i - 1] >= overbought)

            if dem_bull_turn and ema_long_ok and kfd_ok:
                pos = 1
                entry_i = i + 1
                entry_p = opens[i + 1]
                sl_p = entry_p - sl_mult * c_atr
                tp_p = entry_p + tp_mult * c_atr
            elif dem_bear_turn and ema_short_ok and kfd_ok:
                pos = -1
                entry_i = i + 1
                entry_p = opens[i + 1]
                sl_p = entry_p + sl_mult * c_atr
                tp_p = entry_p - tp_mult * c_atr

    return trades

def evaluate_metrics(trades, total_months=72):
    if not trades:
        return {
            "total_trades": 0, "net_profit": 0.0, "pf": 0.0,
            "win_rate": 0.0, "max_dd": 0.0, "romad": 0.0, "mcr": 0.0,
            "trades_per_year": 0.0
        }
    df = pd.DataFrame(trades)
    pnls = df["pnl"].values
    net_p = float(np.sum(pnls))
    wins = pnls[pnls > 0]
    losses = pnls[pnls < 0]
    gw = float(np.sum(wins)) if len(wins) > 0 else 0.0
    gl = float(abs(np.sum(losses))) if len(losses) > 0 else 1e-4
    pf = float(gw / gl)
    wr = float(len(wins) / len(pnls) * 100.0)

    equity = np.cumsum(pnls)
    peak = np.maximum.accumulate(equity)
    dd = peak - equity
    max_dd = float(np.max(dd)) if len(dd) > 0 else 1e-4
    if max_dd < 1.0: max_dd = 1.0
    romad = float(net_p / max_dd)

    m_pnl = df.groupby("month")["pnl"].sum()
    pos_m = int((m_pnl > 0).sum())
    mcr = float(pos_m / total_months * 100.0)

    return {
        "total_trades": len(trades),
        "trades_per_year": round(len(trades) / (total_months / 12.0), 1),
        "net_profit": round(net_p, 2),
        "pf": round(pf, 3),
        "win_rate": round(wr, 2),
        "max_dd": round(max_dd, 2),
        "romad": round(romad, 2),
        "mcr": round(mcr, 2),
        "pos_months": pos_m,
        "total_months": total_months
    }

def main():
    parser = argparse.ArgumentParser(description="Sweep Strategy 64: Gold H1 DeMarker Exhaustion")
    parser.add_argument("--gold_data", type=str, default="/mnt/sdcard/Download/EA/XAUUSD_M1.csv.gz")
    parser.add_argument("--out_dir", type=str, default="projects/quant_strategy_discovery/results")
    args = parser.parse_args()
    os.makedirs(args.out_dir, exist_ok=True)

    t0 = time.time()
    print("[*] Loading Gold raw M1 data...")
    df = pd.read_csv(args.gold_data, usecols=["datetime", "open", "high", "low", "close"])
    df["datetime"] = pd.to_datetime(df["datetime"])
    df.set_index("datetime", inplace=True)
    df.sort_index(inplace=True)

    print("[*] Resampling to H1...")
    df_h1 = df.resample("1h").agg({
        "open": "first", "high": "max", "low": "min", "close": "last"
    }).dropna()

    opens = df_h1["open"].values.astype(np.float64)
    highs = df_h1["high"].values.astype(np.float64)
    lows = df_h1["low"].values.astype(np.float64)
    closes = df_h1["close"].values.astype(np.float64)
    dates = df_h1.index
    months = (dates.year.values * 100 + dates.month.values).astype(np.int32)

    print("[*] Precomputing ATR14, EMA200, and Standard Katz Fractal Dimension...")
    atr14 = compute_atr(highs, lows, closes, 14)
    ema200 = compute_ema(closes, 200)
    kfd24 = compute_katz_fractal_dimension(closes, atr14, 24)

    dem_periods = [9, 14, 21, 28]
    dem_dict = {}
    for p in dem_periods:
        print(f"[*] Precomputing DeMarker for period={p}...")
        dem_dict[p] = compute_demarker(highs, lows, period=p)

    threshold_configs = [
        (0.25, 0.75), # Extreme exhaustion
        (0.30, 0.70), # Classic DeMark standard
        (0.35, 0.65)  # Responsive exhaustion
    ]
    tp_mults = [3.5, 4.0, 4.5, 5.0]
    sl_mults = [1.5, 2.0, 2.5]
    kfd_threshs = [1.35, 1.40, 1.45, 999.0]
    monthly_budget_configs = [
        (0.0, 0.0),       # Unrestricted
        (200.0, 250.0),   # ASAR Conservative
        (250.0, 250.0),   # ASAR Standard
        (300.0, 300.0)    # ASAR Balanced
    ]

    print("[*] Running parameter grid sweep on Strategy 64 (DeMarker Exhaustion)...")
    results = []

    for p in dem_periods:
        dem_series = dem_dict[p]
        for (os_lvl, ob_lvl) in threshold_configs:
            for tp in tp_mults:
                for sl_m in sl_mults:
                    for kfd_t in kfd_threshs:
                        use_kfd = (kfd_t < 100.0)
                        for plock, lbreak in monthly_budget_configs:
                            trades = simulate_demarker_strategy(
                                opens=opens, highs=highs, lows=lows, closes=closes,
                                atr14=atr14, ema200=ema200, kfd=kfd24, dem=dem_series,
                                months=months, dates=dates,
                                oversold=os_lvl, overbought=ob_lvl,
                                use_kfd=use_kfd, kfd_thresh=kfd_t,
                                use_ema200=True,
                                tp_mult=tp, sl_mult=sl_m,
                                monthly_profit_lock=plock, monthly_loss_breaker=lbreak
                            )
                            m = evaluate_metrics(trades)
                            cfg = {
                                "dem_period": p,
                                "oversold": os_lvl,
                                "overbought": ob_lvl,
                                "tp_mult": tp,
                                "sl_mult": sl_m,
                                "kfd_thresh": kfd_t if use_kfd else None,
                                "monthly_profit_lock": plock,
                                "monthly_loss_breaker": lbreak,
                                "use_kfd": use_kfd
                            }
                            results.append({**cfg, **m})

    df_res = pd.DataFrame(results)
    out_csv = os.path.join(args.out_dir, "strategy_64_demarker_sweep_results.csv")
    df_res.to_csv(out_csv, index=False)
    print(f"[+] Saved {len(df_res)} sweep configurations to {out_csv}")

    df_candidates = df_res[(df_res["total_trades"] >= 60) & (df_res["net_profit"] > 0)].copy()
    if not df_candidates.empty:
        df_candidates.sort_values(by=["pf", "net_profit"], ascending=[False, False], inplace=True)
        top5 = df_candidates.head(5)
        print("\n" + "=" * 95)
        print("TOP 5 PERFORMING CONFIGURATIONS - STRATEGY 64: GOLD H1 DEMARKER EXHAUSTION")
        print("=" * 95)
        print(top5[["dem_period", "oversold", "overbought", "tp_mult", "sl_mult", "kfd_thresh", "total_trades", "trades_per_year", "net_profit", "pf", "max_dd", "romad", "mcr"]].to_string(index=False))
        print("=" * 95)

        champ = top5.iloc[0].to_dict()
        champ_file = os.path.join(args.out_dir, "strategy_64_champion.json")
        with open(champ_file, "w") as f:
            json.dump({
                "strategy_id": "STRATEGY_64",
                "strategy_name": "Gold H1 DeMarker Dynamic Exhaustion & Fractal Continuation (DEM-KFD)",
                "champion_metrics": champ,
                "runtime_seconds": round(time.time() - t0, 2)
            }, f, indent=2)
        print(f"[+] Saved champion configuration to {champ_file}")
    else:
        print("[-] No configurations satisfied minimum trade count and profitability criteria.")

    print(f"[*] Total sweep elapsed time: {time.time() - t0:.2f} seconds.")

if __name__ == "__main__":
    main()
