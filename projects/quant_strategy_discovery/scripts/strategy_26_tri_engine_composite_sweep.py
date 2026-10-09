#!/usr/bin/env python3
"""
===============================================================================
STRATEGY 26: TRI-ENGINE INDEPENDENT BUDGET COMPOSITE (TEIBC) - TARGET: MCR >= 80%
===============================================================================
Quantitative CFD Strategy Discovery Engine (The Grand Consistent Portfolio)
Assets: XAUUSD (Gold) + EURUSD CFD (2020 - 2025, 72 Calendar Months)
Timeframe: M15 (Resampled from M1)

Quantitative Formulation:
1. Synthesis of Top Validated Alpha Engines:
   - Engine 1 (Gold ASAR Dual-Regime): Strategy 24 (PF 1.249, DD $1,515).
     * London/NY Trend Breakout (4.0R) + Asian Reversion.
     * Isolated Monthly Lock: +$200, Defensive Downsizing: -$120 (0.3 lot mult).
   - Engine 2 (Gold ARC Breakout): Strategy 11 (PF 1.183).
     * Volatility Compression Ratio (VCR <= 0.70), Directional Skew, Structural Stop.
     * Isolated Monthly Lock: +$150.
   - Engine 3 (EURUSD Asian Liquidity Fade): Strategy 15 (PF 1.016, DD $405).
     * Asian session mean reversion fading sweeps of Asian range.
     * Isolated Monthly Lock: +$100.
2. The Golden Rule of Portfolio Budgeting (Learned from Strategy 21):
   - RISK BUDGETS ARE STRICTLY ASSET & ENGINE ISOLATED!
   - No engine can freeze or contaminate another engine's trading rights.
3. Master Portfolio Metric:
   - Monthly Composite PnL = PnL(Engine 1) + PnL(Engine 2) + PnL(Engine 3).
   - Target: MCR >= 80% - 90% profitable months over 72 calendar months!
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

def run_engine_1_asar(
    opens, highs, lows, closes, atr14, ema200, sma20, upper_band, lower_band,
    h8_arr, l8_arr, months, hours, dates,
    monthly_lock=200.0, loss_breaker=300.0, def_thresh=120.0, def_mult=0.3
):
    """Engine 1: Gold ASAR Dual-Regime (Strategy 24)"""
    n = len(closes)
    trades = []
    pos = 0; entry_p = 0.0; sl_p = 0.0; tp_p = 0.0; sub_mode = ""
    curr_month = None; month_pnl = 0.0; month_locked = False
    base_unit = 10.0; curr_unit = base_unit
    spread = 0.25; comm = 0.06

    for i in range(250, n - 1):
        m_key = months[i]
        hr = hours[i]
        c_atr = atr14[i]

        if m_key != curr_month:
            curr_month = m_key; month_pnl = 0.0; month_locked = False; curr_unit = base_unit

        # Exits
        if pos == 1:
            exit_trig = False; exit_p = 0.0
            if lows[i] <= sl_p:
                exit_p = sl_p if opens[i] >= sl_p else opens[i]
                exit_trig = True
            elif sub_mode == "TREND" and highs[i] >= tp_p:
                exit_p = tp_p if opens[i] <= tp_p else opens[i]
                exit_trig = True
            elif sub_mode == "REV" and highs[i] >= sma20[i]:
                exit_p = sma20[i] if opens[i] <= sma20[i] else opens[i]
                exit_trig = True

            if exit_trig:
                pnl = (exit_p - entry_p) * curr_unit - (spread + comm) * curr_unit
                trades.append({"pnl": pnl, "date": dates[i], "engine": "E1_ASAR", "month": m_key})
                month_pnl += pnl; pos = 0
                if month_pnl >= monthly_lock: month_locked = True
                elif month_pnl <= -loss_breaker: month_locked = True
                elif month_pnl <= -def_thresh: curr_unit = base_unit * def_mult

        elif pos == -1:
            exit_trig = False; exit_p = 0.0
            if highs[i] >= sl_p:
                exit_p = sl_p if opens[i] <= sl_p else opens[i]
                exit_trig = True
            elif sub_mode == "TREND" and lows[i] <= tp_p:
                exit_p = tp_p if opens[i] >= tp_p else opens[i]
                exit_trig = True
            elif sub_mode == "REV" and lows[i] <= sma20[i]:
                exit_p = sma20[i] if opens[i] >= sma20[i] else opens[i]
                exit_trig = True

            if exit_trig:
                pnl = (entry_p - exit_p) * curr_unit - (spread + comm) * curr_unit
                trades.append({"pnl": pnl, "date": dates[i], "engine": "E1_ASAR", "month": m_key})
                month_pnl += pnl; pos = 0
                if month_pnl >= monthly_lock: month_locked = True
                elif month_pnl <= -loss_breaker: month_locked = True
                elif month_pnl <= -def_thresh: curr_unit = base_unit * def_mult

        # Entries
        if pos == 0 and c_atr > 0 and not month_locked:
            if 8 <= hr < 18:
                if closes[i] > h8_arr[i] and closes[i] > ema200[i]:
                    pos = 1; entry_p = opens[i + 1] + (spread * 0.5)
                    sl_d = 2.5 * c_atr; sl_p = entry_p - sl_d; tp_p = entry_p + (sl_d * 4.0)
                    sub_mode = "TREND"
                elif closes[i] < l8_arr[i] and closes[i] < ema200[i]:
                    pos = -1; entry_p = opens[i + 1] - (spread * 0.5)
                    sl_d = 2.5 * c_atr; sl_p = entry_p + sl_d; tp_p = entry_p - (sl_d * 4.0)
                    sub_mode = "TREND"
            elif hr >= 21 or hr < 6:
                if lows[i] < lower_band[i] and closes[i] > lower_band[i]:
                    pos = 1; entry_p = opens[i + 1] + (spread * 0.5)
                    sl_p = entry_p - (2.0 * c_atr); sub_mode = "REV"
                elif highs[i] > upper_band[i] and closes[i] < upper_band[i]:
                    pos = -1; entry_p = opens[i + 1] - (spread * 0.5)
                    sl_p = entry_p + (2.0 * c_atr); sub_mode = "REV"

    return trades

def run_engine_2_arc(
    opens, highs, lows, closes, atr_fast, atr_slow, ema200,
    box_h_arr, box_l_arr, bull_force_arr, bear_force_arr, vcr_arr,
    months, dates, monthly_lock=150.0
):
    """Engine 2: Gold ARC Breakout (Strategy 11)"""
    n = len(closes)
    trades = []
    pos = 0; entry_p = 0.0; sl_p = 0.0; tp_p = 0.0
    curr_month = None; month_pnl = 0.0; month_locked = False
    unit_size = 10.0; spread = 0.25; comm = 0.06

    for i in range(250, n - 1):
        m_key = months[i]
        if m_key != curr_month:
            curr_month = m_key; month_pnl = 0.0; month_locked = False

        # Exits
        if pos == 1:
            exit_trig = False; exit_p = 0.0
            if lows[i] <= sl_p:
                exit_p = sl_p if opens[i] >= sl_p else opens[i]
                exit_trig = True
            elif highs[i] >= tp_p:
                exit_p = tp_p if opens[i] <= tp_p else opens[i]
                exit_trig = True

            if exit_trig:
                pnl = (exit_p - entry_p) * unit_size - (spread + comm) * unit_size
                trades.append({"pnl": pnl, "date": dates[i], "engine": "E2_ARC", "month": m_key})
                month_pnl += pnl; pos = 0
                if month_pnl >= monthly_lock: month_locked = True

        elif pos == -1:
            exit_trig = False; exit_p = 0.0
            if highs[i] >= sl_p:
                exit_p = sl_p if opens[i] <= sl_p else opens[i]
                exit_trig = True
            elif lows[i] <= tp_p:
                exit_p = tp_p if opens[i] >= tp_p else opens[i]
                exit_trig = True

            if exit_trig:
                pnl = (entry_p - exit_p) * unit_size - (spread + comm) * unit_size
                trades.append({"pnl": pnl, "date": dates[i], "engine": "E2_ARC", "month": m_key})
                month_pnl += pnl; pos = 0
                if month_pnl >= monthly_lock: month_locked = True

        # Entries
        if pos == 0 and not month_locked:
            if vcr_arr[i] <= 0.70:
                c_atr = atr_fast[i]
                if closes[i] > box_h_arr[i] and bull_force_arr[i] >= bear_force_arr[i] * 1.25 and closes[i] > ema200[i]:
                    pos = 1; entry_p = opens[i + 1] + (spread * 0.5)
                    sl_p = box_l_arr[i] - (0.2 * c_atr)
                    risk = max(entry_p - sl_p, 0.50); sl_p = entry_p - risk; tp_p = entry_p + (risk * 3.0)
                elif closes[i] < box_l_arr[i] and bear_force_arr[i] >= bull_force_arr[i] * 1.25 and closes[i] < ema200[i]:
                    pos = -1; entry_p = opens[i + 1] - (spread * 0.5)
                    sl_p = box_h_arr[i] + (0.2 * c_atr)
                    risk = max(sl_p - entry_p, 0.50); sl_p = entry_p + risk; tp_p = entry_p - (risk * 3.0)

    return trades

def run_engine_3_eurusd_fade(
    opens, highs, lows, closes, atr14, sma20, upper_band, lower_band,
    months, hours, dates, monthly_lock=100.0
):
    """Engine 3: EURUSD Asian Liquidity Fade (Strategy 15)"""
    n = len(closes)
    trades = []
    pos = 0; entry_p = 0.0; sl_p = 0.0
    curr_month = None; month_pnl = 0.0; month_locked = False
    unit_size = 10000.0  # 0.10 lot
    spread = 0.00008; comm = 0.00006

    for i in range(250, n - 1):
        m_key = months[i]
        hr = hours[i]
        c_atr = atr14[i]

        if m_key != curr_month:
            curr_month = m_key; month_pnl = 0.0; month_locked = False

        # Exits
        if pos == 1:
            exit_trig = False; exit_p = 0.0
            if lows[i] <= sl_p:
                exit_p = sl_p if opens[i] >= sl_p else opens[i]
                exit_trig = True
            elif highs[i] >= sma20[i]:
                exit_p = sma20[i] if opens[i] <= sma20[i] else opens[i]
                exit_trig = True

            if exit_trig:
                pnl = (exit_p - entry_p) * unit_size - (spread + comm) * unit_size
                trades.append({"pnl": pnl, "date": dates[i], "engine": "E3_EUR_FADE", "month": m_key})
                month_pnl += pnl; pos = 0
                if month_pnl >= monthly_lock: month_locked = True

        elif pos == -1:
            exit_trig = False; exit_p = 0.0
            if highs[i] >= sl_p:
                exit_p = sl_p if opens[i] <= sl_p else opens[i]
                exit_trig = True
            elif lows[i] <= sma20[i]:
                exit_p = sma20[i] if opens[i] >= sma20[i] else opens[i]
                exit_trig = True

            if exit_trig:
                pnl = (entry_p - exit_p) * unit_size - (spread + comm) * unit_size
                trades.append({"pnl": pnl, "date": dates[i], "engine": "E3_EUR_FADE", "month": m_key})
                month_pnl += pnl; pos = 0
                if month_pnl >= monthly_lock: month_locked = True

        # Entries (Asian session 21:00 - 06:00 UTC)
        if pos == 0 and c_atr > 0 and not month_locked and (hr >= 21 or hr < 6):
            if lows[i] < lower_band[i] and closes[i] > lower_band[i]:
                pos = 1; entry_p = opens[i + 1] + (spread * 0.5)
                sl_p = entry_p - (1.5 * c_atr)
            elif highs[i] > upper_band[i] and closes[i] < upper_band[i]:
                pos = -1; entry_p = opens[i + 1] - (spread * 0.5)
                sl_p = entry_p + (1.5 * c_atr)

    return trades

def evaluate_portfolio(trades: list) -> dict:
    if len(trades) < 20:
        return {"total_trades": len(trades), "net_profit": 0.0, "pf": 0.0, "mcr": 0.0}

    df_t = pd.DataFrame(trades)
    df_t["year_month"] = pd.to_datetime(df_t["date"]).dt.to_period("M")

    pnls = df_t["pnl"].values
    wins = pnls[pnls > 0]; losses = pnls[pnls < 0]
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
    parser = argparse.ArgumentParser(description="Evaluate Strategy 26: Tri-Engine Independent Budget Composite")
    parser.add_argument("--gold_data", type=str, default="/mnt/sdcard/Download/EA/XAUUSD_M1.csv.gz")
    parser.add_argument("--eur_data", type=str, default="/mnt/sdcard/Download/EA/EURUSD_M1.csv.gz")
    parser.add_argument("--out_dir", type=str, default="/root/CFD-Trading-ML/projects/quant_strategy_discovery/results")
    args = parser.parse_args()

    os.makedirs(args.out_dir, exist_ok=True)

    print("[*] Loading Gold and EURUSD datasets...")
    df_raw_g = pd.read_csv(args.gold_data, usecols=["datetime", "open", "high", "low", "close"])
    df_raw_g["datetime"] = pd.to_datetime(df_raw_g["datetime"])
    df_raw_g.set_index("datetime", inplace=True)
    df_g = df_raw_g.resample("15min").agg({"open":"first","high":"max","low":"min","close":"last"}).dropna()

    df_raw_e = pd.read_csv(args.eur_data, usecols=["datetime", "open", "high", "low", "close"])
    df_raw_e["datetime"] = pd.to_datetime(df_raw_e["datetime"])
    df_raw_e.set_index("datetime", inplace=True)
    df_e = df_raw_e.resample("15min").agg({"open":"first","high":"max","low":"min","close":"last"}).dropna()

    # Precompute Gold Indicators
    g_opens = df_g["open"].values.astype(np.float64)
    g_highs = df_g["high"].values.astype(np.float64)
    g_lows = df_g["low"].values.astype(np.float64)
    g_closes = df_g["close"].values.astype(np.float64)
    g_dates = df_g.index
    g_months = (g_dates.year.values * 100 + g_dates.month.values).astype(np.int32)
    g_hours = g_dates.hour.values.astype(np.int32)

    g_atr14 = compute_atr(g_highs, g_lows, g_closes, 14)
    g_ema200 = compute_ema(g_closes, 200)
    g_sma20 = pd.Series(g_closes).rolling(20).mean().values
    g_std20 = pd.Series(g_closes).rolling(20).std().values
    g_upper = g_sma20 + 2.8 * g_std20
    g_lower = g_sma20 - 2.8 * g_std20
    g_h8 = pd.Series(g_highs).rolling(8).max().shift(1).fillna(999999.0).values
    g_l8 = pd.Series(g_lows).rolling(8).min().shift(1).fillna(0.0).values

    g_atr7 = compute_atr(g_highs, g_lows, g_closes, 7)
    g_atr28 = compute_atr(g_highs, g_lows, g_closes, 28)
    g_vcr = g_atr7 / np.maximum(g_atr28, 1e-6)
    delta = g_closes - g_opens
    g_bull_delta = np.where(delta > 0, delta, 0.0)
    g_bear_delta = np.where(delta < 0, -delta, 0.0)
    g_box_h = pd.Series(g_highs).rolling(8).max().shift(1).fillna(999999.0).values
    g_box_l = pd.Series(g_lows).rolling(8).min().shift(1).fillna(0.0).values
    g_bull_force = pd.Series(g_bull_delta).rolling(8).sum().shift(1).fillna(0.001).values
    g_bear_force = pd.Series(g_bear_delta).rolling(8).sum().shift(1).fillna(0.001).values

    # Precompute EURUSD Indicators
    e_opens = df_e["open"].values.astype(np.float64)
    e_highs = df_e["high"].values.astype(np.float64)
    e_lows = df_e["low"].values.astype(np.float64)
    e_closes = df_e["close"].values.astype(np.float64)
    e_dates = df_e.index
    e_months = (e_dates.year.values * 100 + e_dates.month.values).astype(np.int32)
    e_hours = e_dates.hour.values.astype(np.int32)
    e_atr14 = compute_atr(e_highs, e_lows, e_closes, 14)
    e_sma20 = pd.Series(e_closes).rolling(20).mean().values
    e_std20 = pd.Series(e_closes).rolling(20).std().values
    e_upper = e_sma20 + 2.5 * e_std20
    e_lower = e_sma20 - 2.5 * e_std20

    print("[*] Running Engine 1 (Gold ASAR Dual-Regime)...")
    t1 = run_engine_1_asar(g_opens, g_highs, g_lows, g_closes, g_atr14, g_ema200, g_sma20, g_upper, g_lower, g_h8, g_l8, g_months, g_hours, g_dates)
    m1 = evaluate_portfolio(t1)
    print(f"    E1 Result: Net=${m1['net_profit']:,.2f}, PF={m1['pf']}, MCR={m1['mcr']}%, DD=${m1['max_dd']:,.2f}")

    print("[*] Running Engine 2 (Gold ARC Breakout)...")
    t2 = run_engine_2_arc(g_opens, g_highs, g_lows, g_closes, g_atr7, g_atr28, g_ema200, g_box_h, g_box_l, g_bull_force, g_bear_force, g_vcr, g_months, g_dates)
    m2 = evaluate_portfolio(t2)
    print(f"    E2 Result: Net=${m2['net_profit']:,.2f}, PF={m2['pf']}, MCR={m2['mcr']}%, DD=${m2['max_dd']:,.2f}")

    print("[*] Running Engine 3 (EURUSD Asian Liquidity Fade)...")
    t3 = run_engine_3_eurusd_fade(e_opens, e_highs, e_lows, e_closes, e_atr14, e_sma20, e_upper, e_lower, e_months, e_hours, e_dates)
    m3 = evaluate_portfolio(t3)
    print(f"    E3 Result: Net=${m3['net_profit']:,.2f}, PF={m3['pf']}, MCR={m3['mcr']}%, DD=${m3['max_dd']:,.2f}")

    print("[*] Synthesizing Tri-Engine Composite Portfolio...")
    all_trades = t1 + t2 + t3
    comp_metrics = evaluate_portfolio(all_trades)

    champ_path = os.path.join(args.out_dir, "strategy_26_tri_engine_champion.json")
    with open(champ_path, "w") as f:
        json.dump(comp_metrics, f, indent=2)

    df_monthly = pd.DataFrame(list(comp_metrics["monthly_series"].items()), columns=["month", "pnl"])
    df_monthly.to_csv(os.path.join(args.out_dir, "strategy_26_monthly_heatmap.csv"), index=False)

    print("\n" + "="*80)
    print("STRATEGY 26: TRI-ENGINE INDEPENDENT BUDGET COMPOSITE (TEIBC) - MASTER AUDIT")
    print("="*80)
    print(f"Total Trades: {comp_metrics['total_trades']}")
    print(f"Net Profit: ${comp_metrics['net_profit']:,.2f}")
    print(f"Profit Factor: {comp_metrics['pf']}")
    print(f"Win Rate: {comp_metrics['win_rate']}%")
    print(f"Max Drawdown: ${comp_metrics['max_dd']:,.2f}")
    print(f"Monthly Consistency Ratio (MCR): {comp_metrics['mcr']}% ({comp_metrics['pos_months']} profitable / {comp_metrics['total_months']} total months)")
    print("="*80)

if __name__ == "__main__":
    main()
