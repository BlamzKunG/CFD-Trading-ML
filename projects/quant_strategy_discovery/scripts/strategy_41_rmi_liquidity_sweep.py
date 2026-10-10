#!/usr/bin/env python3
"""
===============================================================================
STRATEGY 41: RELATIVE MOMENTUM INDEX & ASIAN RANGE LIQUIDITY SWEEP (RMI-ARLS)
===============================================================================
Asset: XAUUSD CFD (2020 - 2025, 72 Calendar Months)
Timeframe: M15 (Resampled from M1)

Quantitative Rationale & Target Objective (User Mandate: PF >= 1.50+):
1. Counter-Cyclical Range Harvesting:
   - Solves the quiet consolidation / summer doldrums where H1 trend models pause.
   - Focuses on Asian session range accumulation (00:00 - 07:00 UTC) and London/NY sweeps.
2. Roger Altman's Relative Momentum Index (RMI):
   - Calculates momentum changes over multi-bar intervals (M = 3-5 bars) over period N:
     RMI = 100 * EMA(Up_M, N) / ( EMA(Up_M, N) + EMA(Down_M, N) )
   - Eliminates 1-bar noise spikes while accurately flagging structural exhaustion.
3. Liquidity Sweep Trigger:
   - Price sweeps Asian High by >= 0.5 - 1.0 ATR, rejected with RMI >= 75 -> Short fade.
   - Price sweeps Asian Low by >= 0.5 - 1.0 ATR, rejected with RMI <= 25 -> Long fade.
4. Asymmetric Payoff:
   - SL: 1.5x - 2.0x ATR.
   - TP: 2.5R - 3.5R back toward session median.
5. Autonomous Scaled Adaptive Risk (ASAR):
   - Monthly profit lock at +$150 - +$200.
   - Monthly breaker at -$200.
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

def compute_rmi(closes: np.ndarray, period: int = 14, momentum: int = 4) -> np.ndarray:
    n = len(closes)
    rmi = np.ones(n, dtype=np.float64) * 50.0

    diff = np.zeros(n, dtype=np.float64)
    for i in range(momentum, n):
        diff[i] = closes[i] - closes[i - momentum]

    up = np.where(diff > 0, diff, 0.0)
    down = np.where(diff < 0, -diff, 0.0)

    # Wilder-style EMA
    alpha = 1.0 / period
    up_ema = np.zeros(n, dtype=np.float64)
    down_ema = np.zeros(n, dtype=np.float64)

    start = momentum + period
    if start < n:
        up_ema[start - 1] = np.mean(up[momentum:start])
        down_ema[start - 1] = np.mean(down[momentum:start])

        for i in range(start, n):
            up_ema[i] = (up[i] * alpha) + (up_ema[i - 1] * (1.0 - alpha))
            down_ema[i] = (down[i] * alpha) + (down_ema[i - 1] * (1.0 - alpha))
            denom = up_ema[i] + down_ema[i]
            if denom > 1e-6:
                rmi[i] = 100.0 * up_ema[i] / denom
            else:
                rmi[i] = 50.0

    return rmi

def simulate_rmi_liquidity_sweep(
    opens: np.ndarray,
    highs: np.ndarray,
    lows: np.ndarray,
    closes: np.ndarray,
    atr14: np.ndarray,
    rmi: np.ndarray,
    hours: np.ndarray,
    days: np.ndarray,
    months: np.ndarray,
    dates: pd.DatetimeIndex,
    asian_end_hour: int = 7,
    sweep_start_hour: int = 8,
    sweep_end_hour: int = 16,
    sweep_atr_mult: float = 0.6,
    rmi_ob: float = 75.0,
    rmi_os: float = 25.0,
    monthly_profit_lock: float = 150.0,
    monthly_loss_breaker: float = 200.0,
    defensive_thresh: float = 100.0,
    defensive_lot_mult: float = 0.25,
    trend_tp_mult: float = 3.0,
    trend_sl_mult: float = 1.8,
    spread: float = 0.25,
    commission_per_unit: float = 0.06,
    base_unit_size: float = 10.0,
    warmup: int = 250
):
    n = len(closes)
    trades = []

    pos = 0
    entry_p = 0.0
    sl_p = 0.0
    tp_p = 0.0
    curr_unit_size = base_unit_size

    curr_month = None
    month_cum_pnl = 0.0
    month_locked = False

    curr_day = None
    asian_high = -1.0
    asian_low = 999999.0

    for i in range(warmup, n - 1):
        m_key = months[i]
        d_key = days[i]
        hr = hours[i]
        c_atr = atr14[i]

        if m_key != curr_month:
            curr_month = m_key
            month_cum_pnl = 0.0
            month_locked = False
            curr_unit_size = base_unit_size

        if d_key != curr_day:
            curr_day = d_key
            asian_high = -1.0
            asian_low = 999999.0

        # Build Asian range (00:00 to asian_end_hour UTC)
        if hr < asian_end_hour:
            if highs[i] > asian_high: asian_high = highs[i]
            if lows[i] < asian_low: asian_low = lows[i]

        # 1. Exits
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
                pnl = (exit_p - entry_p) * curr_unit_size - (spread + commission_per_unit) * curr_unit_size
                trades.append({"pnl": pnl, "date": dates[i], "engine": "GOLD_M15_RMI_SWEEP", "month": m_key})
                month_cum_pnl += pnl
                pos = 0

                if monthly_profit_lock > 0 and month_cum_pnl >= monthly_profit_lock:
                    month_locked = True
                elif monthly_loss_breaker > 0 and month_cum_pnl <= -monthly_loss_breaker:
                    month_locked = True
                elif defensive_thresh > 0 and month_cum_pnl <= -defensive_thresh:
                    curr_unit_size = base_unit_size * defensive_lot_mult

        elif pos == -1:
            exit_triggered = False
            exit_p = 0.0
            if highs[i] <= sl_p:
                exit_p = sl_p if opens[i] <= sl_p else opens[i]
                exit_triggered = True
            elif lows[i] <= tp_p:
                exit_p = tp_p if opens[i] >= tp_p else opens[i]
                exit_triggered = True

            if exit_triggered:
                pnl = (entry_p - exit_p) * curr_unit_size - (spread + commission_per_unit) * curr_unit_size
                trades.append({"pnl": pnl, "date": dates[i], "engine": "GOLD_M15_RMI_SWEEP", "month": m_key})
                month_cum_pnl += pnl
                pos = 0

                if monthly_profit_lock > 0 and month_cum_pnl >= monthly_profit_lock:
                    month_locked = True
                elif monthly_loss_breaker > 0 and month_cum_pnl <= -monthly_loss_breaker:
                    month_locked = True
                elif defensive_thresh > 0 and month_cum_pnl <= -defensive_thresh:
                    curr_unit_size = base_unit_size * defensive_lot_mult

        # 2. Entries (During London / Early NY liquidity window: sweep_start_hour to sweep_end_hour)
        if pos == 0 and c_atr > 0 and not month_locked:
            if sweep_start_hour <= hr <= sweep_end_hour and asian_high > 0 and asian_low < 900000.0:
                # Bearish sweep of Asian High: High penetrated above Asian High + sweep_dist, Close rejects back inside
                sweep_dist = sweep_atr_mult * c_atr
                short_sweep = (highs[i] >= asian_high + sweep_dist) and (closes[i] < asian_high) and (rmi[i] >= rmi_ob)

                # Bullish sweep of Asian Low: Low penetrated below Asian Low - sweep_dist, Close rejects back inside
                long_sweep = (lows[i] <= asian_low - sweep_dist) and (closes[i] > asian_low) and (rmi[i] <= rmi_os)

                if long_sweep:
                    pos = 1
                    entry_p = opens[i + 1] + (spread * 0.5)
                    sl_dist = trend_sl_mult * c_atr
                    sl_p = entry_p - sl_dist
                    tp_p = entry_p + (sl_dist * trend_tp_mult)
                elif short_sweep:
                    pos = -1
                    entry_p = opens[i + 1] - (spread * 0.5)
                    sl_dist = trend_sl_mult * c_atr
                    sl_p = entry_p + sl_dist
                    tp_p = entry_p - (sl_dist * trend_tp_mult)

    return trades

def evaluate_metrics(trades: list) -> dict:
    if len(trades) < 20:
        return {
            "total_trades": len(trades), "net_profit": -9999.0, "pf": 0.0,
            "win_rate": 0.0, "max_dd": 9999.0, "mcr": 0.0, "pos_months": 0, "total_months": 72
        }

    pnls = np.array([t["pnl"] for t in trades])
    net_profit = float(np.sum(pnls))
    wins = pnls[pnls > 0]
    losses = pnls[pnls < 0]
    gross_win = float(np.sum(wins)) if len(wins) > 0 else 0.0
    gross_loss = float(abs(np.sum(losses))) if len(losses) > 0 else 1e-4
    pf = float(gross_win / gross_loss)
    win_rate = float(len(wins) / len(pnls) * 100.0)

    equity = np.cumsum(pnls)
    peak = np.maximum.accumulate(equity)
    dd = peak - equity
    max_dd = float(np.max(dd)) if len(dd) > 0 else 0.0

    df_tr = pd.DataFrame(trades)
    df_tr["month"] = df_tr["month"].astype(int)
    monthly = df_tr.groupby("month")["pnl"].sum().to_dict()

    all_months = []
    for y in range(2020, 2026):
        for m in range(1, 13):
            all_months.append(y * 100 + m)

    m_series = {m: round(monthly.get(m, 0.0), 2) for m in all_months}
    pos_m = sum(1 for m in all_months if m_series[m] > 0.0)
    mcr = float(round(pos_m / len(all_months) * 100.0, 2))

    return {
        "total_trades": len(trades),
        "net_profit": round(net_profit, 2),
        "pf": round(pf, 3),
        "win_rate": round(win_rate, 2),
        "max_dd": round(max_dd, 2),
        "mcr": mcr,
        "pos_months": pos_m,
        "total_months": len(all_months),
        "monthly_series": m_series
    }

def main():
    parser = argparse.ArgumentParser(description="Sweep Strategy 41: RMI Asian Liquidity Sweep")
    parser.add_argument("--data", type=str, default="/mnt/sdcard/Download/EA/XAUUSD_M1.csv.gz")
    parser.add_argument("--out_dir", type=str, default="projects/quant_strategy_discovery/results")
    args = parser.parse_args()

    os.makedirs(args.out_dir, exist_ok=True)

    print(f"[*] Loading Gold M1 data from {args.data}...")
    df_raw = pd.read_csv(
        args.data,
        usecols=["datetime", "open", "high", "low", "close"],
        dtype={"open": np.float32, "high": np.float32, "low": np.float32, "close": np.float32}
    )
    df_raw["datetime"] = pd.to_datetime(df_raw["datetime"])
    df_raw.set_index("datetime", inplace=True)
    df_raw.sort_index(inplace=True)

    print(f"[*] Resampling to M15 timeframe...")
    df_m15 = df_raw.resample("15min").agg({
        "open": "first", "high": "max", "low": "min", "close": "last"
    }).dropna()
    print(f"[+] Loaded {len(df_m15):,} M15 bars (2020 - 2025).")

    opens = df_m15["open"].values.astype(np.float64)
    highs = df_m15["high"].values.astype(np.float64)
    lows = df_m15["low"].values.astype(np.float64)
    closes = df_m15["close"].values.astype(np.float64)
    dates = df_m15.index
    months = (dates.year.values * 100 + dates.month.values).astype(np.int32)
    days = (dates.year.values * 10000 + dates.month.values * 100 + dates.day.values).astype(np.int32)
    hours = dates.hour.values.astype(np.int32)

    print("[*] Pre-computing baseline indicators...")
    atr14 = compute_atr(highs, lows, closes, 14)

    # Pre-compute RMI with different momentum spans
    rmi_cache = {}
    for mom in [3, 4, 5]:
        print(f"[*] Pre-computing RMI (period=14, momentum={mom})...")
        rmi_cache[mom] = compute_rmi(closes, period=14, momentum=mom)

    # Sweep parameters
    mom_spans = [3, 4, 5]
    sweep_mults = [0.4, 0.6, 0.8]
    ob_os_pairs = [(70.0, 30.0), (75.0, 25.0)]
    profit_locks = [150.0, 200.0]
    trend_tps = [2.5, 3.0, 3.5]
    trend_sls = [1.5, 1.8]

    total_combs = len(mom_spans) * len(sweep_mults) * len(ob_os_pairs) * len(profit_locks) * len(trend_tps) * len(trend_sls)
    print(f"[*] Calibrating Strategy 41: RMI Sweep across {total_combs} combinations...")

    results = []
    t_start = time.time()

    for mom in mom_spans:
        c_rmi = rmi_cache[mom]
        for sm in sweep_mults:
            for ob, os_val in ob_os_pairs:
                for plock in profit_locks:
                    for tp_m in trend_tps:
                        for sl_m in trend_sls:
                            trades = simulate_rmi_liquidity_sweep(
                                opens=opens, highs=highs, lows=lows, closes=closes,
                                atr14=atr14, rmi=c_rmi, hours=hours, days=days,
                                months=months, dates=dates,
                                asian_end_hour=7, sweep_start_hour=8, sweep_end_hour=16,
                                sweep_atr_mult=sm, rmi_ob=ob, rmi_os=os_val,
                                monthly_profit_lock=plock,
                                monthly_loss_breaker=200.0,
                                defensive_thresh=100.0, defensive_lot_mult=0.25,
                                trend_tp_mult=tp_m, trend_sl_mult=sl_m
                            )
                            m = evaluate_metrics(trades)
                            if m["total_trades"] >= 30:
                                m.update({
                                    "momentum": mom, "sweep_mult": sm, "rmi_ob": ob, "rmi_os": os_val,
                                    "profit_lock": plock, "trend_tp": tp_m, "trend_sl": sl_m
                                })
                                results.append(m)

    df_res = pd.DataFrame(results)
    if len(df_res) == 0:
        print("[!] No combinations met minimum trade requirements.")
        return

    df_res.sort_values(by=["pf", "net_profit", "mcr"], ascending=[False, False, False], inplace=True)

    csv_path = os.path.join(args.out_dir, "strategy_41_rmi_sweep_results.csv")
    df_res.drop(columns=["monthly_series"]).to_csv(csv_path, index=False)
    print(f"[+] Saved Strategy 41 sweep results to {csv_path}")

    top_champ = results[df_res.index[0]]
    champ_json_path = os.path.join(args.out_dir, "strategy_41_champion.json")
    with open(champ_json_path, "w") as f:
        json.dump(top_champ, f, indent=2)

    print("\n" + "="*80)
    print("STRATEGY 41: RMI ASIAN LIQUIDITY SWEEP CHAMPION RESULTS")
    print("="*80)
    print(f"Top Configuration (PF Target >= 1.50+):")
    print(f"  - RMI Momentum Span: {top_champ['momentum']} bars (OB: {top_champ['rmi_ob']} / OS: {top_champ['rmi_os']})")
    print(f"  - Sweep Distance Multiplier: {top_champ['sweep_mult']}x ATR")
    print(f"  - Monthly Profit Lock: ${top_champ['profit_lock']}")
    print(f"  - Target R:R / SL: {top_champ['trend_tp']}R / {top_champ['trend_sl']}x ATR")
    print("-" * 80)
    print(f"Performance Metrics Across 72 Calendar Months (2020 - 2025):")
    print(f"  - Total Trades: {top_champ['total_trades']}")
    print(f"  - Net Profit: ${top_champ['net_profit']:,.2f}")
    print(f"  - Profit Factor (PF): {top_champ['pf']}")
    print(f"  - Win Rate: {top_champ['win_rate']}%")
    print(f"  - Max Drawdown: ${top_champ['max_dd']:,.2f}")
    print(f"  - Monthly Consistency Ratio (MCR): {top_champ['mcr']}% ({top_champ['pos_months']}/{top_champ['total_months']} profitable months)")
    print(f"Sweep Execution Time: {time.time() - t_start:.2f}s")
    print("="*80)

    print("\nTop 5 Distinct Configurations:")
    top5 = df_res.head(5)[["momentum", "sweep_mult", "rmi_ob", "trend_tp", "trend_sl", "pf", "net_profit", "win_rate", "max_dd", "mcr", "total_trades"]]
    print(top5.to_string(index=False))

if __name__ == "__main__":
    main()
