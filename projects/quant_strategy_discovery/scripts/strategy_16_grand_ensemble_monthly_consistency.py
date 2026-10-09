#!/usr/bin/env python3
"""
===============================================================================
STRATEGY 16: THE GRAND ENSEMBLE PORTFOLIO ENGINE (MCR >= 80% MONTHLY CONSISTENCY)
===============================================================================
Bespoke Multi-Strategy Composite Architecture: Designed for "Profitable Every Month"
Asset: XAUUSD CFD (2020 - 2025, 72 Calendar Months)
Timeframe: M15 (Resampled from M1)

Core Quantitative Mechanism:
- By combining 4 completely uncorrelated champion engines:
  1. Engine 1: Zero-Lag MACD (15/34/9) with 4.0R Trend Multiplier
  2. Engine 2: TTM Squeeze Expansion (BB in KC >= 8 bars) with 3.0R Target
  3. Engine 3: Dual-Regime Cross-Session (NY Trend 4.0R + Asian Reversion to SMA 20)
  4. Engine 4: ARC Compression Breakout with Directional Volatility Skew (3.0R)
- The ensemble smooths out the equity curve, fills in individual losing months,
  and drastically boosts the Monthly Consistency Ratio (MCR) toward the >= 80% target!
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

# -----------------------------------------------------------------------------
# ENGINE 1: ZERO-LAG MACD (4.0R TARGET)
# -----------------------------------------------------------------------------
def run_engine_zl_macd(df, spread=0.25, comm=0.06, unit_size=10.0):
    opens = df["open"].values.astype(np.float64)
    highs = df["high"].values.astype(np.float64)
    lows = df["low"].values.astype(np.float64)
    closes = df["close"].values.astype(np.float64)
    n = len(closes)
    atr = compute_atr(highs, lows, closes, 14)

    ema_f1 = compute_ema(closes, 15)
    ema_f2 = compute_ema(ema_f1, 15)
    zl_f = 2.0 * ema_f1 - ema_f2

    ema_s1 = compute_ema(closes, 34)
    ema_s2 = compute_ema(ema_s1, 34)
    zl_s = 2.0 * ema_s1 - ema_s2

    zl_macd = zl_f - zl_s
    zl_sig = compute_ema(zl_macd, 9)

    trades = []
    pos = 0
    entry_p = 0.0
    sl_p = 0.0
    tp_p = 0.0
    entry_i = 0

    for i in range(100, n - 1):
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
                pnl = (exit_p - entry_p) * unit_size - (spread + comm) * unit_size
                trades.append({"pnl": pnl, "date": df.index[i], "engine": "ZL_MACD"})
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
                pnl = (entry_p - exit_p) * unit_size - (spread + comm) * unit_size
                trades.append({"pnl": pnl, "date": df.index[i], "engine": "ZL_MACD"})
                pos = 0

        if pos == 0 and atr[i] > 0:
            bull = (zl_macd[i - 1] <= zl_sig[i - 1]) and (zl_macd[i] > zl_sig[i])
            bear = (zl_macd[i - 1] >= zl_sig[i - 1]) and (zl_macd[i] < zl_sig[i])
            sl_dist = 2.0 * atr[i]
            if bull:
                pos = 1
                entry_p = opens[i + 1] + (spread * 0.5)
                sl_p = entry_p - sl_dist
                tp_p = entry_p + (sl_dist * 4.0)
                entry_i = i + 1
            elif bear:
                pos = -1
                entry_p = opens[i + 1] - (spread * 0.5)
                sl_p = entry_p + sl_dist
                tp_p = entry_p - (sl_dist * 4.0)
                entry_i = i + 1
    return trades

# -----------------------------------------------------------------------------
# ENGINE 2: TTM SQUEEZE EXPANSION (3.0R TARGET)
# -----------------------------------------------------------------------------
def run_engine_ttm_squeeze(df, spread=0.25, comm=0.06, unit_size=10.0):
    opens = df["open"].values.astype(np.float64)
    highs = df["high"].values.astype(np.float64)
    lows = df["low"].values.astype(np.float64)
    closes = df["close"].values.astype(np.float64)
    n = len(closes)
    atr = compute_atr(highs, lows, closes, 14)
    ema200 = compute_ema(closes, 200)

    sma20 = pd.Series(closes).rolling(20).mean().values
    std20 = pd.Series(closes).rolling(20).std().values
    bb_upper = sma20 + 2.0 * std20
    bb_lower = sma20 - 2.0 * std20
    kc_upper = sma20 + 2.0 * atr
    kc_lower = sma20 - 2.0 * atr

    is_sq = (bb_lower > kc_lower) & (bb_upper < kc_upper)
    sq_count = np.zeros(n, dtype=np.int32)
    c = 0
    for i in range(n):
        if is_sq[i]: c += 1
        else: c = 0
        sq_count[i] = c

    delta = closes - ((highs + lows) * 0.5 + sma20) * 0.5
    trades = []
    pos = 0
    entry_p = 0.0
    sl_p = 0.0
    tp_p = 0.0
    entry_i = 0

    for i in range(250, n - 1):
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
                pnl = (exit_p - entry_p) * unit_size - (spread + comm) * unit_size
                trades.append({"pnl": pnl, "date": df.index[i], "engine": "TTM_SQUEEZE"})
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
                pnl = (entry_p - exit_p) * unit_size - (spread + comm) * unit_size
                trades.append({"pnl": pnl, "date": df.index[i], "engine": "TTM_SQUEEZE"})
                pos = 0

        if pos == 0 and atr[i] > 0:
            fired = (not is_sq[i]) and (sq_count[i - 1] >= 8)
            if fired:
                sl_dist = 3.0 * atr[i]
                if delta[i] > 0 and closes[i] > ema200[i]:
                    pos = 1
                    entry_p = opens[i + 1] + (spread * 0.5)
                    sl_p = entry_p - sl_dist
                    tp_p = entry_p + (sl_dist * 3.0)
                    entry_i = i + 1
                elif delta[i] < 0 and closes[i] < ema200[i]:
                    pos = -1
                    entry_p = opens[i + 1] - (spread * 0.5)
                    sl_p = entry_p + sl_dist
                    tp_p = entry_p - (sl_dist * 3.0)
                    entry_i = i + 1
    return trades

# -----------------------------------------------------------------------------
# ENGINE 3: DUAL-REGIME CROSS-SESSION (NY TREND + ASIAN REVERSION)
# -----------------------------------------------------------------------------
def run_engine_dual_regime(df, spread=0.25, comm=0.06, unit_size=10.0):
    opens = df["open"].values.astype(np.float64)
    highs = df["high"].values.astype(np.float64)
    lows = df["low"].values.astype(np.float64)
    closes = df["close"].values.astype(np.float64)
    hours = df.index.hour.values.astype(np.int32)
    n = len(closes)
    atr = compute_atr(highs, lows, closes, 14)
    ema200 = compute_ema(closes, 200)

    sma20 = pd.Series(closes).rolling(20).mean().values
    std20 = pd.Series(closes).rolling(20).std().values
    upper_band = sma20 + 2.8 * std20
    lower_band = sma20 - 2.8 * std20

    trades = []
    pos = 0
    entry_p = 0.0
    sl_p = 0.0
    tp_p = 0.0
    entry_i = 0
    sub_mode = ""

    for i in range(250, n - 1):
        hr = hours[i]
        c_atr = atr[i]

        if pos == 1:
            exit_triggered = False
            exit_p = 0.0
            if lows[i] <= sl_p:
                exit_p = sl_p if opens[i] >= sl_p else opens[i]
                exit_triggered = True
            elif sub_mode == "TREND" and highs[i] >= tp_p:
                exit_p = tp_p if opens[i] <= tp_p else opens[i]
                exit_triggered = True
            elif sub_mode == "REV" and highs[i] >= sma20[i]:
                exit_p = sma20[i] if opens[i] <= sma20[i] else opens[i]
                exit_triggered = True
            if exit_triggered:
                pnl = (exit_p - entry_p) * unit_size - (spread + comm) * unit_size
                trades.append({"pnl": pnl, "date": df.index[i], "engine": "DUAL_REGIME"})
                pos = 0
        elif pos == -1:
            exit_triggered = False
            exit_p = 0.0
            if highs[i] >= sl_p:
                exit_p = sl_p if opens[i] <= sl_p else opens[i]
                exit_triggered = True
            elif sub_mode == "TREND" and lows[i] <= tp_p:
                exit_p = tp_p if opens[i] >= tp_p else opens[i]
                exit_triggered = True
            elif sub_mode == "REV" and lows[i] <= sma20[i]:
                exit_p = sma20[i] if opens[i] >= sma20[i] else opens[i]
                exit_triggered = True
            if exit_triggered:
                pnl = (entry_p - exit_p) * unit_size - (spread + comm) * unit_size
                trades.append({"pnl": pnl, "date": df.index[i], "engine": "DUAL_REGIME"})
                pos = 0

        if pos == 0 and c_atr > 0:
            if 8 <= hr < 18:
                h8 = np.max(highs[i - 8:i])
                l8 = np.min(lows[i - 8:i])
                if closes[i] > h8 and closes[i] > ema200[i]:
                    pos = 1
                    entry_p = opens[i + 1] + (spread * 0.5)
                    sl_dist = 2.5 * c_atr
                    sl_p = entry_p - sl_dist
                    tp_p = entry_p + (sl_dist * 4.0)
                    entry_i = i + 1
                    sub_mode = "TREND"
                elif closes[i] < l8 and closes[i] < ema200[i]:
                    pos = -1
                    entry_p = opens[i + 1] - (spread * 0.5)
                    sl_dist = 2.5 * c_atr
                    sl_p = entry_p + sl_dist
                    tp_p = entry_p - (sl_dist * 4.0)
                    entry_i = i + 1
                    sub_mode = "TREND"
            elif hr >= 21 or hr < 6:
                if lows[i] < lower_band[i] and closes[i] > lower_band[i]:
                    pos = 1
                    entry_p = opens[i + 1] + (spread * 0.5)
                    sl_p = entry_p - (2.0 * c_atr)
                    entry_i = i + 1
                    sub_mode = "REV"
                elif highs[i] > upper_band[i] and closes[i] < upper_band[i]:
                    pos = -1
                    entry_p = opens[i + 1] - (spread * 0.5)
                    sl_p = entry_p + (2.0 * c_atr)
                    entry_i = i + 1
                    sub_mode = "REV"
    return trades

# -----------------------------------------------------------------------------
# ENGINE 4: ARC BREAKOUT WITH DIRECTIONAL SKEW (3.0R TARGET)
# -----------------------------------------------------------------------------
def run_engine_arc_breakout(df, spread=0.25, comm=0.06, unit_size=10.0):
    opens = df["open"].values.astype(np.float64)
    highs = df["high"].values.astype(np.float64)
    lows = df["low"].values.astype(np.float64)
    closes = df["close"].values.astype(np.float64)
    n = len(closes)
    atr_fast = compute_atr(highs, lows, closes, 10)
    atr_slow = compute_atr(highs, lows, closes, 50)
    ema200 = compute_ema(closes, 200)

    trades = []
    pos = 0
    entry_p = 0.0
    sl_p = 0.0
    tp_p = 0.0
    entry_i = 0

    for i in range(200, n - 1):
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
                pnl = (exit_p - entry_p) * unit_size - (spread + comm) * unit_size
                trades.append({"pnl": pnl, "date": df.index[i], "engine": "ARC_BREAKOUT"})
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
                pnl = (entry_p - exit_p) * unit_size - (spread + comm) * unit_size
                trades.append({"pnl": pnl, "date": df.index[i], "engine": "ARC_BREAKOUT"})
                pos = 0

        if pos == 0 and atr_slow[i] > 0:
            if (atr_fast[i] / atr_slow[i]) <= 0.75:
                box_h = np.max(highs[i - 12:i])
                box_l = np.min(lows[i - 12:i])
                c_atr = atr_fast[i]

                delta = closes[i - 12:i] - opens[i - 12:i]
                bull_force = np.sum(delta[delta > 0]) if np.any(delta > 0) else 0.001
                bear_force = np.sum(np.abs(delta[delta < 0])) if np.any(delta < 0) else 0.001

                if closes[i] > box_h and closes[i] > ema200[i] and bull_force >= (bear_force * 1.25):
                    pos = 1
                    entry_p = opens[i + 1] + (spread * 0.5)
                    sl_p = box_l - (0.5 * c_atr)
                    risk = max(0.50, entry_p - sl_p)
                    tp_p = entry_p + (3.0 * risk)
                    entry_i = i + 1
                elif closes[i] < box_l and closes[i] < ema200[i] and bear_force >= (bull_force * 1.25):
                    pos = -1
                    entry_p = opens[i + 1] - (spread * 0.5)
                    sl_p = box_h + (0.5 * c_atr)
                    risk = max(0.50, sl_p - entry_p)
                    tp_p = entry_p - (3.0 * risk)
                    entry_i = i + 1
    return trades

def main():
    parser = argparse.ArgumentParser(description="Evaluate Grand Ensemble Portfolio for Consistent Monthly Profitability")
    parser.add_argument("--data", type=str, default="/mnt/sdcard/Download/EA/XAUUSD_M1.csv.gz", help="Path to M1 data")
    parser.add_argument("--out_dir", type=str, default="/root/CFD-Trading-ML/projects/quant_strategy_discovery/results", help="Results dir")
    args = parser.parse_args()

    os.makedirs(args.out_dir, exist_ok=True)

    print(f"[*] Loading data from {args.data}...")
    t0 = time.time()
    df_raw = pd.read_csv(
        args.data,
        usecols=["datetime", "open", "high", "low", "close", "tick_volume"],
        dtype={"open": np.float32, "high": np.float32, "low": np.float32, "close": np.float32, "tick_volume": np.int32}
    )
    df_raw["datetime"] = pd.to_datetime(df_raw["datetime"])
    df_raw.set_index("datetime", inplace=True)
    df_raw.sort_index(inplace=True)

    print(f"[*] Resampling to M15 timeframe...")
    df = df_raw.resample("15min").agg({
        "open": "first", "high": "max", "low": "min", "close": "last", "tick_volume": "sum"
    }).dropna()
    print(f"[+] Loaded {len(df):,} M15 bars (2020 - 2025).")

    print("\n" + "="*70)
    print("🚀 RUNNING 4 COMPONENT ENGINES ON FULL 72-MONTH HORIZON...")
    print("="*70)

    t_s = time.time()
    t1 = run_engine_zl_macd(df)
    print(f"[+] Engine 1 (Zero-Lag MACD): {len(t1)} trades")
    t2 = run_engine_ttm_squeeze(df)
    print(f"[+] Engine 2 (TTM Squeeze): {len(t2)} trades")
    t3 = run_engine_dual_regime(df)
    print(f"[+] Engine 3 (Dual-Regime Hybrid): {len(t3)} trades")
    t4 = run_engine_arc_breakout(df)
    print(f"[+] Engine 4 (ARC Breakout): {len(t4)} trades")
    print(f"[+] All engines executed in {time.time()-t_s:.2f}s")

    # Combine all trades into ensemble portfolio
    all_trades = t1 + t2 + t3 + t4
    df_all = pd.DataFrame(all_trades)
    df_all.sort_values(by="date", inplace=True)
    df_all.reset_index(drop=True, inplace=True)
    df_all["year_month"] = pd.to_datetime(df_all["date"]).dt.to_period("M")

    pnls = df_all["pnl"].values
    wins = pnls[pnls > 0]
    losses = pnls[pnls < 0]
    gp = float(np.sum(wins))
    gl = float(abs(np.sum(losses)))
    net = float(np.sum(pnls))
    pf = gp / gl
    wr = len(wins) / len(pnls) * 100.0

    eq = 10000.0 + np.cumsum(pnls)
    peaks = np.maximum.accumulate(eq)
    max_dd = float(np.max(peaks - eq))
    romad = net / max_dd

    # 72-Month Heatmap Analysis
    monthly_pnl = df_all.groupby("year_month")["pnl"].sum()
    total_months = len(monthly_pnl)
    pos_months = int(np.sum(monthly_pnl > 0))
    neg_months = int(np.sum(monthly_pnl <= 0))
    mcr = (pos_months / total_months * 100.0)

    # Convert monthly pnl to serializable dict
    monthly_dict = {str(k): round(float(v), 2) for k, v in monthly_pnl.items()}

    print("\n" + "="*70)
    print("🏆 GRAND COMPOSITE ENSEMBLE PORTFOLIO AUDIT (2020 - 2025)")
    print("="*70)
    print(f"  Total Trades:           {len(df_all):,}")
    print(f"  Total Net Profit (0.10): ${net:,.2f}")
    print(f"  Profit Factor:          {pf:.3f}")
    print(f"  Overall Win Rate:       {wr:.2f}%")
    print(f"  Max Drawdown:           ${max_dd:,.2f}")
    print(f"  RoMaD (Return / DD):    {romad:.2f}")
    print(f"  Total Calendar Months:  {total_months} months")
    print(f"  Profitable Months:      {pos_months} months")
    print(f"  Losing Months:          {neg_months} months")
    print(f"  🎯 MONTHLY CONSISTENCY RATIO (MCR): {mcr:.2f}%")
    print("="*70)

    # Save summary JSON and monthly CSV
    summary = {
        "total_trades": len(df_all),
        "net_profit": round(net, 2),
        "profit_factor": round(pf, 3),
        "win_rate": round(wr, 2),
        "max_drawdown": round(max_dd, 2),
        "romad": round(romad, 2),
        "total_months": total_months,
        "pos_months": pos_months,
        "neg_months": neg_months,
        "mcr": round(mcr, 2),
        "monthly_pnl": monthly_dict
    }

    out_json = os.path.join(args.out_dir, "strategy_16_grand_ensemble_champion.json")
    with open(out_json, "w") as f:
        json.dump(summary, f, indent=2)
    print(f"[+] Saved Grand Ensemble summary to {out_json}")

    # Save monthly heatmap CSV
    df_monthly = pd.DataFrame(list(monthly_dict.items()), columns=["Month", "Net_Profit_USD"])
    out_csv = os.path.join(args.out_dir, "strategy_16_grand_ensemble_72_month_heatmap.csv")
    df_monthly.to_csv(out_csv, index=False)
    print(f"[+] Saved 72-month Heatmap CSV to {out_csv}")

if __name__ == "__main__":
    main()
