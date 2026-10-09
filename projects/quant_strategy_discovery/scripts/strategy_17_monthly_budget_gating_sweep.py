#!/usr/bin/env python3
"""
===============================================================================
STRATEGY 17: MONTHLY RISK BUDGETING & CIRCUIT BREAKER ENGINE (MCR >= 80% TARGET)
===============================================================================
Institutional Risk Architecture: Engineered to Achieve "กำไรทุกเดือน" (>= 80% MCR)
Asset: XAUUSD CFD (2020 - 2025, 72 Calendar Months)
Timeframe: M15 (Resampled from M1)

Core Quantitative Hypothesis:
- A great strategy still has 30-40% losing months if it trades unconstrained because
  profitable months often give back gains in the final week, and quiet months suffer
  from death-by-a-thousand-cuts chop.
- Institutional Monthly Budgeting Architecture:
  1. Monthly Profit Lock: Once a calendar month accumulates >= target_lock (e.g. +$300 to +$600),
     trading is locked / lot size drops by 80% to preserve the winning month.
  2. Monthly Max Loss Circuit Breaker: If cumulative loss within the calendar month hits
     max_loss_thresh (e.g. -$200 to -$400), trading is paused until the 1st of next month.
  3. Core Trading Engine: Dual-Regime Cross-Session (NY Trend 4.0R + Asian Reversion).
- Mass Parametric Sweep:
  - Sweeps profit lock targets, loss circuit breakers, and volatility thresholds.
  - Objective: Isolate parameter sets achieving Monthly Consistency Ratio (MCR) >= 80% - 90%!
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

def simulate_budgeted_dual_regime(
    opens: np.ndarray,
    highs: np.ndarray,
    lows: np.ndarray,
    closes: np.ndarray,
    atr14: np.ndarray,
    ema200: np.ndarray,
    hours: np.ndarray,
    dates: pd.DatetimeIndex,
    monthly_profit_lock: float,   # 0 (no lock), 300, 500, 800 USD
    monthly_loss_breaker: float,  # 0 (no breaker), 200, 300, 400 USD
    trend_tp_mult: float = 4.0,
    trend_sl_mult: float = 2.5,
    rev_std_mult: float = 2.8,
    rev_sl_atr: float = 2.0,
    spread: float = 0.25,
    commission_per_unit: float = 0.06,
    unit_size: float = 10.0,
    warmup: int = 250
):
    n = len(closes)
    trades = []
    
    sma20 = pd.Series(closes).rolling(20).mean().values
    std20 = pd.Series(closes).rolling(20).std().values
    upper_band = sma20 + rev_std_mult * std20
    lower_band = sma20 - rev_std_mult * std20

    pos = 0
    entry_p = 0.0
    sl_p = 0.0
    tp_p = 0.0
    entry_i = 0
    sub_mode = ""

    curr_month = None
    month_cum_pnl = 0.0
    month_locked = False

    for i in range(warmup, n - 1):
        dt = dates[i]
        m_key = (dt.year, dt.month)
        hr = hours[i]
        c_atr = atr14[i]

        # Reset budget at start of each new calendar month
        if m_key != curr_month:
            curr_month = m_key
            month_cum_pnl = 0.0
            month_locked = False

        # 1. Manage Exits
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
                pnl = (exit_p - entry_p) * unit_size - (spread + commission_per_unit) * unit_size
                trades.append({"pnl": pnl, "date": dt, "engine": sub_mode, "month": m_key})
                month_cum_pnl += pnl
                pos = 0

                # Check Monthly Circuit Breakers
                if monthly_profit_lock > 0 and month_cum_pnl >= monthly_profit_lock:
                    month_locked = True
                elif monthly_loss_breaker > 0 and month_cum_pnl <= -monthly_loss_breaker:
                    month_locked = True

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
                pnl = (entry_p - exit_p) * unit_size - (spread + commission_per_unit) * unit_size
                trades.append({"pnl": pnl, "date": dt, "engine": sub_mode, "month": m_key})
                month_cum_pnl += pnl
                pos = 0

                if monthly_profit_lock > 0 and month_cum_pnl >= monthly_profit_lock:
                    month_locked = True
                elif monthly_loss_breaker > 0 and month_cum_pnl <= -monthly_loss_breaker:
                    month_locked = True

        # 2. Check Entries (Only if month is not locked)
        if pos == 0 and c_atr > 0 and not month_locked:
            # Engine A: London / NY Trend Breakout (08:00 - 18:00 UTC)
            if 8 <= hr < 18:
                h8 = np.max(highs[i - 8:i])
                l8 = np.min(lows[i - 8:i])
                if closes[i] > h8 and closes[i] > ema200[i]:
                    pos = 1
                    entry_p = opens[i + 1] + (spread * 0.5)
                    sl_dist = trend_sl_mult * c_atr
                    sl_p = entry_p - sl_dist
                    tp_p = entry_p + (sl_dist * trend_tp_mult)
                    entry_i = i + 1
                    sub_mode = "TREND"
                elif closes[i] < l8 and closes[i] < ema200[i]:
                    pos = -1
                    entry_p = opens[i + 1] - (spread * 0.5)
                    sl_dist = trend_sl_mult * c_atr
                    sl_p = entry_p + sl_dist
                    tp_p = entry_p - (sl_dist * trend_tp_mult)
                    entry_i = i + 1
                    sub_mode = "TREND"

            # Engine B: Asian Mean Reversion (21:00 - 06:00 UTC)
            elif hr >= 21 or hr < 6:
                if lows[i] < lower_band[i] and closes[i] > lower_band[i]:
                    pos = 1
                    entry_p = opens[i + 1] + (spread * 0.5)
                    sl_p = entry_p - (rev_sl_atr * c_atr)
                    entry_i = i + 1
                    sub_mode = "REV"
                elif highs[i] > upper_band[i] and closes[i] < upper_band[i]:
                    pos = -1
                    entry_p = opens[i + 1] - (spread * 0.5)
                    sl_p = entry_p + (rev_sl_atr * c_atr)
                    entry_i = i + 1
                    sub_mode = "REV"

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

    eq = 10000.0 + np.cumsum(pnls)
    peaks = np.maximum.accumulate(eq)
    max_dd = float(np.max(peaks - eq)) if len(eq) > 0 else 0.0

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
    parser = argparse.ArgumentParser(description="Sweep Strategy 17: Monthly Risk Budgeting & Circuit Breakers")
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

    print(f"[*] Resampling to M15 timeframe...")
    df_m15 = df_raw.resample("15min").agg({
        "open": "first", "high": "max", "low": "min", "close": "last", "tick_volume": "sum"
    }).dropna()
    print(f"[+] Loaded {len(df_m15):,} M15 bars (2020 - 2025).")

    opens = df_m15["open"].values.astype(np.float64)
    highs = df_m15["high"].values.astype(np.float64)
    lows = df_m15["low"].values.astype(np.float64)
    closes = df_m15["close"].values.astype(np.float64)
    hours = df_m15.index.hour.values.astype(np.int32)
    dates = df_m15.index

    atr14 = compute_atr(highs, lows, closes, 14)
    ema200 = compute_ema(closes, 200)

    # Budget parameters to sweep
    profit_locks = [0.0, 300.0, 500.0, 800.0]     # USD target to lock month
    loss_breakers = [0.0, 200.0, 300.0, 400.0]    # USD max loss to halt month

    total_combs = len(profit_locks) * len(loss_breakers)
    print(f"[*] Sweeping {total_combs} monthly budget gating combinations across 72 calendar months...")

    results = []
    c_idx = 0
    t_start = time.time()

    for pl in profit_locks:
        for lb in loss_breakers:
            c_idx += 1
            trades = simulate_budgeted_dual_regime(
                opens, highs, lows, closes, atr14, ema200, hours, dates,
                monthly_profit_lock=pl, monthly_loss_breaker=lb
            )
            metrics = evaluate_monthly_consistency(trades)
            metrics.update({
                "monthly_profit_lock": pl,
                "monthly_loss_breaker": lb
            })
            results.append(metrics)

            if c_idx % 4 == 0 or c_idx == total_combs:
                print(f"[{c_idx}/{total_combs}] Completed ({c_idx/total_combs*100:.1f}%) | Elapsed: {time.time()-t_start:.1f}s")

    df_res = pd.DataFrame(results)
    csv_path = os.path.join(args.out_dir, "strategy_17_monthly_budget_sweep_results.csv")
    df_res.to_csv(csv_path, index=False)
    print(f"[+] Saved full results to {csv_path}")

    # Prioritize Highest MCR (Monthly Consistency Ratio) and Net Profit
    champ = df_res.sort_values(by=["mcr", "net_profit"], ascending=[False, False]).iloc[0]
    champ_dict = champ.to_dict()

    json_path = os.path.join(args.out_dir, "strategy_17_monthly_budget_champion.json")
    with open(json_path, "w") as f:
        json.dump(champ_dict, f, indent=2)
    print(f"[+] Champion JSON saved to {json_path}")

    print("\n" + "="*70)
    print("🏆 CHAMPION MONTHLY BUDGET CONFIGURATION (STRATEGY 17)")
    print("="*70)
    for k, v in champ_dict.items():
        print(f"  {k}: {v}")
    print("="*70)

if __name__ == "__main__":
    main()
