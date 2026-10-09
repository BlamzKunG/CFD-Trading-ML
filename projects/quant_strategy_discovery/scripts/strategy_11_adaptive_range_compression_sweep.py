#!/usr/bin/env python3
"""
===============================================================================
STRATEGY 11: ADAPTIVE RANGE COMPRESSION (ARC) BREAKOUT & DIRECTIONAL SKEW
===============================================================================
Bespoke In-House Quantitative Strategy Logic Template
Asset: XAUUSD CFD & EURUSD (Multi-Asset Capable)
Period: 2020 - 2025 (Full 72-Month Historical Validation)
Timeframe: M15 (Resampled from M1)

Core Quantitative Mechanisms:
1. Microstructure Volatility Compression Ratio (VCR):
   - Short ATR(10) / Long ATR(50) < compression_ratio (e.g. 0.65 to 0.75)
   - Indicates severe coiled potential energy before institutional breakout
2. Directional Volatility Skew (DVS):
   - Computes asymmetric body momentum during compression:
     Sum(Close - Open | Green bars) vs Sum(Open - Close | Red bars)
   - Filters out false breakout direction by aligning with order accumulation
3. Compression Range Breakout Trigger:
   - Bar i Closes strictly outside the highest high or lowest low of the compression box
4. Strict Causal Execution:
   - Order executed strictly at Bar i+1 Open
5. Risk Management:
   - SL: Opposite boundary of compression box + buffer
   - TP: Asymmetric Risk-Reward (2.0R, 3.0R, 4.0R)
6. 72-Month Consistency Heatmap Analysis:
   - Evaluates monthly win rate across all 72 individual calendar months (2020 - 2025)
   - Benchmark: Target Monthly Consistency Ratio (MCR) >= 80%
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

def simulate_arc_breakout(
    opens: np.ndarray,
    highs: np.ndarray,
    lows: np.ndarray,
    closes: np.ndarray,
    atr_fast: np.ndarray,
    atr_slow: np.ndarray,
    dates: pd.DatetimeIndex,
    box_lookback: int,          # 8, 12, 16 bars
    vcr_thresh: float,          # 0.65, 0.75
    skew_mult: float,           # 1.0 (no skew filter), 1.25 (skew required)
    use_ema_filter: bool,       # True / False (EMA 200)
    ema200: np.ndarray,
    sl_buffer_atr: float,       # 0.2, 0.5
    tp_rr_mult: float,          # 2.0, 3.0, 4.0
    spread: float = 0.25,
    commission_per_unit: float = 0.06,
    unit_size: float = 10.0,
    warmup: int = 200
):
    n = len(closes)
    trades = []
    pos = 0
    entry_p = 0.0
    sl_p = 0.0
    tp_p = 0.0
    entry_i = 0

    for i in range(warmup, n - 1):
        # 1. Manage Exits (Strict worst-case order: check SL first, then TP)
        if pos == 1:
            exit_triggered = False
            exit_p = 0.0
            if lows[i] <= sl_p:
                exit_p = sl_p if opens[i] >= sl_p else opens[i] # Gap slippage
                exit_triggered = True
            elif highs[i] >= tp_p:
                exit_p = tp_p if opens[i] <= tp_p else opens[i]
                exit_triggered = True

            if exit_triggered:
                pnl = (exit_p - entry_p) * unit_size - (spread + commission_per_unit) * unit_size
                trades.append({
                    "pnl": pnl, "entry_bar": entry_i, "exit_bar": i,
                    "date": dates[i], "type": "BUY"
                })
                pos = 0

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
                pnl = (entry_p - exit_p) * unit_size - (spread + commission_per_unit) * unit_size
                trades.append({
                    "pnl": pnl, "entry_bar": entry_i, "exit_bar": i,
                    "date": dates[i], "type": "SELL"
                })
                pos = 0

        # 2. Check Entries on Breakout
        if pos == 0 and atr_slow[i] > 0.0:
            vcr = atr_fast[i] / atr_slow[i]
            if vcr <= vcr_thresh:
                # Compression box boundaries (previous box_lookback bars, excluding current bar)
                box_h = np.max(highs[i - box_lookback:i])
                box_l = np.min(lows[i - box_lookback:i])
                c_atr = atr_fast[i]

                # Directional Volatility Skew
                delta = closes[i - box_lookback:i] - opens[i - box_lookback:i]
                bull_force = np.sum(delta[delta > 0]) if np.any(delta > 0) else 0.001
                bear_force = np.sum(np.abs(delta[delta < 0])) if np.any(delta < 0) else 0.001

                bull_break = (closes[i] > box_h)
                bear_break = (closes[i] < box_l)

                if bull_break:
                    skew_ok = (bull_force >= bear_force * skew_mult)
                    trend_ok = (closes[i] > ema200[i]) if use_ema_filter else True

                    if skew_ok and trend_ok:
                        pos = 1
                        entry_p = opens[i + 1] + (spread * 0.5)
                        sl_p = box_l - (sl_buffer_atr * c_atr)
                        risk = entry_p - sl_p
                        if risk < 0.50:
                            risk = 0.50
                            sl_p = entry_p - risk
                        tp_p = entry_p + (risk * tp_rr_mult)
                        entry_i = i + 1
                        continue

                elif bear_break:
                    skew_ok = (bear_force >= bull_force * skew_mult)
                    trend_ok = (closes[i] < ema200[i]) if use_ema_filter else True

                    if skew_ok and trend_ok:
                        pos = -1
                        entry_p = opens[i + 1] - (spread * 0.5)
                        sl_p = box_h + (sl_buffer_atr * c_atr)
                        risk = sl_p - entry_p
                        if risk < 0.50:
                            risk = 0.50
                            sl_p = entry_p + risk
                        tp_p = entry_p - (risk * tp_rr_mult)
                        entry_i = i + 1
                        continue

    return trades

def evaluate_monthly_consistency(trades: list) -> dict:
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

    # Drawdown
    eq = 10000.0 + np.cumsum(pnls)
    peaks = np.maximum.accumulate(eq)
    max_dd = float(np.max(peaks - eq)) if len(eq) > 0 else 0.0

    # Monthly breakdown
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
        "neg_months": neg_months
    }

def main():
    parser = argparse.ArgumentParser(description="Sweep Strategy 11: ARC Breakout & Monthly Consistency")
    parser.add_argument("--data", type=str, default="/mnt/sdcard/Download/EA/XAUUSD_M1.csv.gz", help="Path to M1 data")
    parser.add_argument("--out_dir", type=str, default="/root/CFD-Trading-ML/projects/quant_strategy_discovery/results", help="Results dir")
    args = parser.parse_args()

    os.makedirs(args.out_dir, exist_ok=True)

    print(f"[*] Loading M1 data from {args.data}...")
    t0 = time.time()
    df_raw = pd.read_csv(
        args.data,
        usecols=["datetime", "open", "high", "low", "close", "tick_volume"],
        dtype={"open": np.float32, "high": np.float32, "low": np.float32, "close": np.float32, "tick_volume": np.int32}
    )
    df_raw["datetime"] = pd.to_datetime(df_raw["datetime"])
    df_raw.set_index("datetime", inplace=True)
    df_raw.sort_index(inplace=True)
    print(f"[+] Loaded {len(df_raw):,} M1 bars in {time.time() - t0:.2f}s.")

    print(f"[*] Resampling to M15 timeframe...")
    df_m15 = df_raw.resample("15min").agg({
        "open": "first", "high": "max", "low": "min", "close": "last", "tick_volume": "sum"
    }).dropna()
    print(f"[+] Resampled M15 bars: {len(df_m15):,} bars.")

    opens = df_m15["open"].values.astype(np.float64)
    highs = df_m15["high"].values.astype(np.float64)
    lows = df_m15["low"].values.astype(np.float64)
    closes = df_m15["close"].values.astype(np.float64)
    dates = df_m15.index

    print("[*] Precomputing indicators (ATR fast/slow, EMA 200)...")
    atr_fast = compute_atr(highs, lows, closes, 10)
    atr_slow = compute_atr(highs, lows, closes, 50)
    ema200 = compute_ema(closes, 200)

    # Parameter grid for mass sweep
    box_lookbacks = [8, 12, 16]
    vcr_threshs = [0.65, 0.70, 0.75]
    skew_mults = [1.0, 1.25]
    ema_filters = [True, False]
    sl_buffers = [0.2, 0.5]
    tp_rr_mults = [2.0, 3.0, 4.0]

    # Total combinations = 3 * 3 * 2 * 2 * 2 * 3 = 216 combinations
    total_combs = len(box_lookbacks) * len(vcr_threshs) * len(skew_mults) * len(ema_filters) * len(sl_buffers) * len(tp_rr_mults)
    print(f"[*] Sweeping {total_combs} parameter combinations across 72-month historical data...")

    results = []
    c_idx = 0
    t_start = time.time()

    for bl in box_lookbacks:
        for vt in vcr_threshs:
            for sm in skew_mults:
                for ef in ema_filters:
                    for slb in sl_buffers:
                        for tpr in tp_rr_mults:
                            c_idx += 1
                            trades = simulate_arc_breakout(
                                opens, highs, lows, closes, atr_fast, atr_slow, dates,
                                box_lookback=bl, vcr_thresh=vt, skew_mult=sm,
                                use_ema_filter=ef, ema200=ema200,
                                sl_buffer_atr=slb, tp_rr_mult=tpr
                            )
                            metrics = evaluate_monthly_consistency(trades)
                            metrics.update({
                                "box_lookback": bl,
                                "vcr_thresh": vt,
                                "skew_mult": sm,
                                "use_ema_filter": ef,
                                "sl_buffer_atr": slb,
                                "tp_rr_mult": tpr
                            })
                            results.append(metrics)

                            if c_idx % 50 == 0 or c_idx == total_combs:
                                print(f"[{c_idx}/{total_combs}] Completed ({c_idx/total_combs*100:.1f}%) | Elapsed: {time.time()-t_start:.1f}s")

    df_res = pd.DataFrame(results)
    csv_path = os.path.join(args.out_dir, "strategy_11_arc_breakout_sweep_results.csv")
    df_res.to_csv(csv_path, index=False)
    print(f"[+] Full sweep results saved to: {csv_path}")

    # Find champion: Prioritizing High MCR (Monthly Consistency Ratio >= 70%) & High Net Profit
    viable = df_res[(df_res["total_trades"] >= 200) & (df_res["pf"] >= 1.05)]
    if len(viable) > 0:
        champ = viable.sort_values(by=["mcr", "net_profit"], ascending=[False, False]).iloc[0]
    else:
        champ = df_res.sort_values(by=["net_profit"], ascending=[False]).iloc[0]

    champ_dict = champ.to_dict()
    json_path = os.path.join(args.out_dir, "strategy_11_arc_breakout_champion.json")
    with open(json_path, "w") as f:
        json.dump(champ_dict, f, indent=2)
    print(f"[+] Champion JSON saved to: {json_path}")

    print("\n" + "="*70)
    print("🏆 CHAMPION PARAMETER SET (STRATEGY 11: ARC BREAKOUT)")
    print("="*70)
    for k, v in champ_dict.items():
        print(f"  {k}: {v}")
    print("="*70)

if __name__ == "__main__":
    main()
