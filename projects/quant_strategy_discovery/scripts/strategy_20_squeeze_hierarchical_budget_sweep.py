#!/usr/bin/env python3
"""
===============================================================================
STRATEGY 20: SQUEEZE COMPRESSION BREAKOUT WITH HIERARCHICAL RISK BUDGETING
===============================================================================
Institutional Quant Architecture: Aiming for Monthly Consistency Ratio (MCR) >= 80%
Asset: XAUUSD CFD (2020 - 2025, 72 Calendar Months)
Timeframe: M15 (Resampled from M1)

Quantitative Rationale:
1. Proven Core Engine: Volatility Compression Squeeze (Strategy 04 / Strategy 11)
   - Bollinger Bands (20, 2.0 std) contracting inside Keltner Channels (20, 1.5 ATR).
   - When the squeeze fires (Bollinger expands outside Keltner) in the direction of
     macro trend (EMA200), enter momentum expansion at bar i+1 Open.
2. Hierarchical Weekly & Monthly Risk Budgeting:
   - Monthly Profit Lock: Locks in gains once month reaches +$250 to +$400.
   - Monthly Loss Breaker: Halts trading if month incurs -$200 to -$350.
   - Weekly Loss Breaker: Halts trading if single calendar week incurs -$120 to -$180.
     (Prevents consecutive-day losing streaks within choppy mid-month periods).
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

def simulate_squeeze_budgeted(
    opens: np.ndarray,
    highs: np.ndarray,
    lows: np.ndarray,
    closes: np.ndarray,
    atr14: np.ndarray,
    ema200: np.ndarray,
    sma20: np.ndarray,
    bb_upper: np.ndarray,
    bb_lower: np.ndarray,
    kc_upper: np.ndarray,
    kc_lower: np.ndarray,
    hours: np.ndarray,
    dates: pd.DatetimeIndex,
    tp_mult: float = 3.5,
    sl_mult: float = 2.0,
    monthly_profit_lock: float = 300.0,
    monthly_loss_breaker: float = 250.0,
    weekly_loss_breaker: float = 150.0,
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

    months = (dates.year.values * 100 + dates.month.values).astype(np.int32)
    # ISO week key: year * 100 + week
    weeks = (dates.year.values * 100 + dates.isocalendar().week.values).astype(np.int32)

    for i in range(warmup, n - 1):
        m_key = months[i]
        w_key = weeks[i]
        hr = hours[i]
        c_atr = atr14[i]

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
                trades.append({"pnl": pnl, "date": dates[i], "engine": "SQUEEZE", "month": m_key})
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
                trades.append({"pnl": pnl, "date": dates[i], "engine": "SQUEEZE", "month": m_key})
                month_cum_pnl += pnl
                week_cum_pnl += pnl
                pos = 0

                if monthly_profit_lock > 0 and month_cum_pnl >= monthly_profit_lock:
                    month_locked = True
                elif monthly_loss_breaker > 0 and month_cum_pnl <= -monthly_loss_breaker:
                    month_locked = True
                if weekly_loss_breaker > 0 and week_cum_pnl <= -weekly_loss_breaker:
                    week_locked = True

        # 2. Check Entries (London/NY active hours 08:00 - 18:00 UTC, when not locked)
        if pos == 0 and c_atr > 0 and not month_locked and not week_locked:
            if 8 <= hr < 18:
                # Squeeze fired condition: Previous bar was squeezed (BB inside KC), current bar fires expansion
                prev_squeeze = (bb_upper[i - 1] <= kc_upper[i - 1]) and (bb_lower[i - 1] >= kc_lower[i - 1])
                curr_fired = (bb_upper[i] > kc_upper[i]) or (bb_lower[i] < kc_lower[i])

                if prev_squeeze and curr_fired:
                    # Bullish Expansion: Close > Upper KC and Close > EMA200
                    if closes[i] > kc_upper[i] and closes[i] > ema200[i]:
                        pos = 1
                        entry_p = opens[i + 1] + (spread * 0.5)
                        sl_dist = sl_mult * c_atr
                        sl_p = entry_p - sl_dist
                        tp_p = entry_p + (sl_dist * tp_mult)
                    # Bearish Expansion: Close < Lower KC and Close < EMA200
                    elif closes[i] < kc_lower[i] and closes[i] < ema200[i]:
                        pos = -1
                        entry_p = opens[i + 1] - (spread * 0.5)
                        sl_dist = sl_mult * c_atr
                        sl_p = entry_p + sl_dist
                        tp_p = entry_p - (sl_dist * tp_mult)

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
    parser = argparse.ArgumentParser(description="Sweep Strategy 20: Squeeze Compression with Hierarchical Risk Budgeting")
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
    hours = df_m15.index.hour.values.astype(np.int32)
    dates = df_m15.index

    print(f"[*] Computing Indicators (ATR14, EMA200, Bollinger Bands, Keltner Channels)...")
    atr14 = compute_atr(highs, lows, closes, 14)
    ema200 = compute_ema(closes, 200)

    sma20 = pd.Series(closes).rolling(20).mean().values
    std20 = pd.Series(closes).rolling(20).std().values
    bb_upper = sma20 + 2.0 * std20
    bb_lower = sma20 - 2.0 * std20

    kc_upper = sma20 + 1.5 * atr14
    kc_lower = sma20 - 1.5 * atr14

    # Parameter sweeps
    tp_mults = [3.0, 4.0]
    sl_mults = [1.8, 2.2]
    profit_locks = [0.0, 250.0, 350.0]
    loss_breakers = [0.0, 200.0, 300.0]
    weekly_breakers = [0.0, 120.0, 180.0]

    total_combs = len(tp_mults) * len(sl_mults) * len(profit_locks) * len(loss_breakers) * len(weekly_breakers)
    print(f"[*] Sweeping {total_combs} hierarchical budget combinations across 72 calendar months...")

    results = []
    t_start = time.time()

    for tp_m in tp_mults:
        for sl_m in sl_mults:
            for plock in profit_locks:
                for lbreak in loss_breakers:
                    for wbreak in weekly_breakers:
                        trades = simulate_squeeze_budgeted(
                            opens=opens, highs=highs, lows=lows, closes=closes,
                            atr14=atr14, ema200=ema200, sma20=sma20,
                            bb_upper=bb_upper, bb_lower=bb_lower,
                            kc_upper=kc_upper, kc_lower=kc_lower,
                            hours=hours, dates=dates,
                            tp_mult=tp_m, sl_mult=sl_m,
                            monthly_profit_lock=plock,
                            monthly_loss_breaker=lbreak,
                            weekly_loss_breaker=wbreak
                        )
                        m = evaluate_metrics(trades)
                        m.update({
                            "tp_mult": tp_m, "sl_mult": sl_m,
                            "profit_lock": plock, "loss_breaker": lbreak,
                            "weekly_breaker": wbreak
                        })
                        results.append(m)

    df_res = pd.DataFrame(results)
    df_res.sort_values(by=["mcr", "net_profit"], ascending=[False, False], inplace=True)

    csv_path = os.path.join(args.out_dir, "strategy_20_squeeze_budget_sweep_results.csv")
    df_res.drop(columns=["monthly_series"]).to_csv(csv_path, index=False)
    print(f"[+] Saved sweep results to {csv_path}")

    champion = results[df_res.index[0]]
    champ_json_path = os.path.join(args.out_dir, "strategy_20_champion.json")
    with open(champ_json_path, "w") as f:
        json.dump(champion, f, indent=2)

    print("\n" + "="*80)
    print("STRATEGY 20: SQUEEZE COMPRESSION & HIERARCHICAL RISK BUDGET - TOP CHAMPION")
    print("="*80)
    print(f"Config: TP={champion['tp_mult']}R, SL={champion['sl_mult']}xATR, ProfitLock=${champion['profit_lock']}, LossBreaker=${champion['loss_breaker']}, WeekBreaker=${champion['weekly_breaker']}")
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
