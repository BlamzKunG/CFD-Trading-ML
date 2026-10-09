#!/usr/bin/env python3
"""
===============================================================================
STRATEGY 22: ADAPTIVE RANGE COMPRESSION (ARC) WITH HIERARCHICAL RISK BUDGETING
===============================================================================
Institutional Quant Architecture: High-Performance Vectorized Backtest
Asset: XAUUSD CFD (2020 - 2025, 72 Calendar Months)
Timeframe: M15 (Resampled from M1)

Quantitative Rationale:
1. Core Alpha Engine: Adaptive Range Compression (Strategy 11 - Top PF 1.183 Champion)
   - Volatility Compression Ratio: VCR = ATR(7) / ATR(28) <= 0.70.
   - Microstructure Compression Box: 8 to 12 bars lookback.
   - Directional Force Skew: Measures directional aggressive volume inside the box.
   - Macro Directional Filter: EMA 200 on M15.
   - Structural Stop Loss: Placed directly behind the compression box boundary.
2. Hierarchical Risk Budgeting Overlay:
   - Monthly Profit Lock: Locks in month gains once profit reaches +$250 to +$350.
   - Monthly Loss Breaker: Halts trading for the calendar month if loss hits -$200 to -$300.
   - Weekly Loss Breaker: Halts trading until next Monday if week hits -$100 to -$150.
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

def simulate_arc_budgeted_fast(
    opens: np.ndarray,
    highs: np.ndarray,
    lows: np.ndarray,
    closes: np.ndarray,
    atr_fast: np.ndarray,
    ema200: np.ndarray,
    box_h_arr: np.ndarray,
    box_l_arr: np.ndarray,
    bull_force_arr: np.ndarray,
    bear_force_arr: np.ndarray,
    vcr_arr: np.ndarray,
    months: np.ndarray,
    weeks: np.ndarray,
    dates: pd.DatetimeIndex,
    vcr_thresh: float = 0.70,
    skew_mult: float = 1.25,
    sl_buffer_atr: float = 0.2,
    tp_rr_mult: float = 3.0,
    monthly_profit_lock: float = 300.0,
    monthly_loss_breaker: float = 250.0,
    weekly_loss_breaker: float = 120.0,
    spread: float = 0.25,
    commission_per_unit: float = 0.06,
    unit_size: float = 10.0,
    warmup: int = 250
):
    n = len(closes)
    trades = []

    pos = 0
    entry_p = 0.0
    sl_p = 0.0
    tp_p = 0.0

    curr_month = None
    curr_week = None
    month_cum_pnl = 0.0
    week_cum_pnl = 0.0
    month_locked = False
    week_locked = False

    for i in range(warmup, n - 1):
        m_key = months[i]
        w_key = weeks[i]

        # Reset month budget
        if m_key != curr_month:
            curr_month = m_key
            month_cum_pnl = 0.0
            month_locked = False

        # Reset week budget
        if w_key != curr_week:
            curr_week = w_key
            week_cum_pnl = 0.0
            week_locked = False

        # 1. Manage Exits
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
                pnl = (exit_p - entry_p) * unit_size - (spread + commission_per_unit) * unit_size
                trades.append({"pnl": pnl, "date": dates[i], "engine": "ARC", "month": m_key})
                month_cum_pnl += pnl
                week_cum_pnl += pnl
                pos = 0

                if monthly_profit_lock > 0 and month_cum_pnl >= monthly_profit_lock:
                    month_locked = True
                elif monthly_loss_breaker > 0 and month_cum_pnl <= -monthly_loss_breaker:
                    month_locked = True
                if weekly_loss_breaker > 0 and week_cum_pnl <= -weekly_loss_breaker:
                    week_locked = True

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
                trades.append({"pnl": pnl, "date": dates[i], "engine": "ARC", "month": m_key})
                month_cum_pnl += pnl
                week_cum_pnl += pnl
                pos = 0

                if monthly_profit_lock > 0 and month_cum_pnl >= monthly_profit_lock:
                    month_locked = True
                elif monthly_loss_breaker > 0 and month_cum_pnl <= -monthly_loss_breaker:
                    month_locked = True
                if weekly_loss_breaker > 0 and week_cum_pnl <= -weekly_loss_breaker:
                    week_locked = True

        # 2. Check Entries on Breakout (Fast O(1) Precomputed Arrays)
        if pos == 0 and not month_locked and not week_locked:
            if vcr_arr[i] <= vcr_thresh:
                box_h = box_h_arr[i]
                box_l = box_l_arr[i]
                c_atr = atr_fast[i]
                bull_force = bull_force_arr[i]
                bear_force = bear_force_arr[i]

                bull_break = (closes[i] > box_h)
                bear_break = (closes[i] < box_l)

                if bull_break:
                    skew_ok = (bull_force >= bear_force * skew_mult)
                    trend_ok = (closes[i] > ema200[i])
                    if skew_ok and trend_ok:
                        pos = 1
                        entry_p = opens[i + 1] + (spread * 0.5)
                        sl_p = box_l - (sl_buffer_atr * c_atr)
                        risk = max(entry_p - sl_p, 0.50)
                        sl_p = entry_p - risk
                        tp_p = entry_p + (risk * tp_rr_mult)

                elif bear_break:
                    skew_ok = (bear_force >= bull_force * skew_mult)
                    trend_ok = (closes[i] < ema200[i])
                    if skew_ok and trend_ok:
                        pos = -1
                        entry_p = opens[i + 1] - (spread * 0.5)
                        sl_p = box_h + (sl_buffer_atr * c_atr)
                        risk = max(sl_p - entry_p, 0.50)
                        sl_p = entry_p + risk
                        tp_p = entry_p - (risk * tp_rr_mult)

    return trades

def evaluate_metrics(trades: list) -> dict:
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
    peak = np.maximum.accumulate(eq)
    dd = peak - eq
    max_dd = float(np.max(dd))

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
        "neg_months": neg_months,
        "monthly_series": {str(k): round(float(v), 2) for k, v in monthly_pnl.items()}
    }

def main():
    parser = argparse.ArgumentParser(description="Sweep Strategy 22: ARC Breakout with Hierarchical Risk Budgeting")
    parser.add_argument("--data", type=str, default="/mnt/sdcard/Download/EA/XAUUSD_M1.csv.gz", help="Path to M1 data")
    parser.add_argument("--out_dir", type=str, default="/root/CFD-Trading-ML/projects/quant_strategy_discovery/results", help="Results dir")
    args = parser.parse_args()

    os.makedirs(args.out_dir, exist_ok=True)

    print(f"[*] Loading M1 data from {args.data}...")
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
    dates = df_m15.index

    months = (dates.year.values * 100 + dates.month.values).astype(np.int32)
    weeks = (dates.year.values * 100 + dates.isocalendar().week.values).astype(np.int32)

    print(f"[*] Computing Indicators (ATR7, ATR28, EMA200)...")
    atr_fast = compute_atr(highs, lows, closes, 7)
    atr_slow = compute_atr(highs, lows, closes, 28)
    ema200 = compute_ema(closes, 200)
    vcr_arr = atr_fast / np.maximum(atr_slow, 1e-6)

    delta = closes - opens
    bull_delta = np.where(delta > 0, delta, 0.0)
    bear_delta = np.where(delta < 0, -delta, 0.0)

    # Grid parameter sweep
    box_lookbacks = [8, 12]
    tp_mults = [2.5, 3.5]
    profit_locks = [0.0, 250.0, 350.0]
    loss_breakers = [0.0, 200.0, 300.0]
    weekly_breakers = [0.0, 100.0, 150.0]

    total_combs = len(box_lookbacks) * len(tp_mults) * len(profit_locks) * len(loss_breakers) * len(weekly_breakers)
    print(f"[*] Sweeping {total_combs} ARC budget combinations across 72 calendar months...")

    results = []
    t_start = time.time()

    for box_lb in box_lookbacks:
        # Precompute box boundaries and forces for this lookback
        box_h_arr = pd.Series(highs).rolling(box_lb).max().shift(1).fillna(999999.0).values
        box_l_arr = pd.Series(lows).rolling(box_lb).min().shift(1).fillna(0.0).values
        bull_force_arr = pd.Series(bull_delta).rolling(box_lb).sum().shift(1).fillna(0.001).values
        bear_force_arr = pd.Series(bear_delta).rolling(box_lb).sum().shift(1).fillna(0.001).values

        for tp_m in tp_mults:
            for plock in profit_locks:
                for lbreak in loss_breakers:
                    for wbreak in weekly_breakers:
                        trades = simulate_arc_budgeted_fast(
                            opens=opens, highs=highs, lows=lows, closes=closes,
                            atr_fast=atr_fast, ema200=ema200,
                            box_h_arr=box_h_arr, box_l_arr=box_l_arr,
                            bull_force_arr=bull_force_arr, bear_force_arr=bear_force_arr,
                            vcr_arr=vcr_arr, months=months, weeks=weeks,
                            dates=dates, tp_rr_mult=tp_m,
                            monthly_profit_lock=plock, monthly_loss_breaker=lbreak,
                            weekly_loss_breaker=wbreak
                        )
                        m = evaluate_metrics(trades)
                        m.update({
                            "box_lookback": box_lb, "tp_rr": tp_m,
                            "profit_lock": plock, "loss_breaker": lbreak,
                            "weekly_breaker": wbreak
                        })
                        results.append(m)

    df_res = pd.DataFrame(results)
    df_res.sort_values(by=["mcr", "net_profit"], ascending=[False, False], inplace=True)

    csv_path = os.path.join(args.out_dir, "strategy_22_arc_budget_sweep_results.csv")
    df_res.drop(columns=["monthly_series"]).to_csv(csv_path, index=False)
    print(f"[+] Saved sweep results to {csv_path}")

    champion = results[df_res.index[0]]
    champ_json_path = os.path.join(args.out_dir, "strategy_22_champion.json")
    with open(champ_json_path, "w") as f:
        json.dump(champion, f, indent=2)

    print("\n" + "="*80)
    print("STRATEGY 22: ARC BREAKOUT & HIERARCHICAL RISK BUDGET - TOP CHAMPION")
    print("="*80)
    print(f"Config: BoxLookback={champion['box_lookback']}, TP={champion['tp_rr']}R, ProfitLock=${champion['profit_lock']}, LossBreaker=${champion['loss_breaker']}, WeekBreaker=${champion['weekly_breaker']}")
    print(f"Trades: {champion['total_trades']}")
    print(f"Net Profit: ${champion['net_profit']:,.2f}")
    print(f"Profit Factor: {champion['pf']}")
    print(f"Win Rate: {champion['win_rate']}%")
    print(f"Max Drawdown: ${champion['max_dd']:,.2f}")
    print(f"Monthly Consistency Ratio (MCR): {champion['mcr']}% ({champion['pos_months']} profitable / {champion['total_months']} total months)")
    print(f"Elapsed Time: {time.time() - t_start:.2f}s")
    print("="*80)

if __name__ == "__main__":
    main()
