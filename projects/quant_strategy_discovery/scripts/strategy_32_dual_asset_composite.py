#!/usr/bin/env python3
"""
===============================================================================
STRATEGY 32: DUAL-ASSET ASYNCHRONOUS RISK-ISOLATED COMPOSITE (DA-ARIC)
===============================================================================
Portfolio Quant Architecture: Sourced from Institutional Risk Parity & 
Asset Isolation Theorems.
Assets: XAUUSD CFD (M15) + EURUSD CFD (H1)
Time Period: 2020 - 2025 (72 Calendar Months)

Quantitative Rationale:
1. Solving the Cross-Contamination Flaw:
   - Prior multi-asset tests (Strategy 21 & 26) failed because heterogeneous assets 
     shared a single circuit breaker, allowing EURUSD chops to freeze Gold.
   - Strategy 32 implements Strict Risk Isolation: Gold M15 and EURUSD H1 run on 
     independent calendar risk budgets and decoupled execution loops.
2. Cross-Asset Regime Decorrelation:
   - Gold exploits intraday liquidity expansion during London/NY sessions (M15).
   - EURUSD exploits macro monetary divergences on H1.
3. Target Benchmark:
   - Evaluate whether portfolio monthly diversification cancels out single-asset 
     losing months, driving Monthly Consistency Ratio (MCR) towards >= 75% - 85%.
===============================================================================
"""

import os
import sys
import time
import json
import argparse
import numpy as np
import pandas as pd
sys.path.insert(0, '/root/CFD-Trading-ML')

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

def run_gold_m15_trades(df_m15: pd.DataFrame, profit_lock=150.0, trend_tp=4.0, trend_sl=2.5, def_thresh=100.0, def_mult=0.3):
    opens = df_m15["open"].values.astype(np.float64)
    highs = df_m15["high"].values.astype(np.float64)
    lows = df_m15["low"].values.astype(np.float64)
    closes = df_m15["close"].values.astype(np.float64)
    hours = df_m15.index.hour.values.astype(np.int32)
    dates = df_m15.index
    months = (dates.year.values * 100 + dates.month.values).astype(np.int32)

    atr14 = compute_atr(highs, lows, closes, 14)
    ema50 = compute_ema(closes, 50)
    ema200 = compute_ema(closes, 200)
    h8_arr = pd.Series(highs).rolling(8).max().shift(1).fillna(999999.0).values
    l8_arr = pd.Series(lows).rolling(8).min().shift(1).fillna(0.0).values

    n = len(closes)
    trades = []
    pos = 0
    entry_p = 0.0
    sl_p = 0.0
    tp_p = 0.0
    spread = 0.25
    comm = 0.06
    base_unit = 10.0
    curr_unit = base_unit

    curr_month = None
    month_cum = 0.0
    month_locked = False

    for i in range(250, n - 1):
        m_key = months[i]
        hr = hours[i]
        c_atr = atr14[i]

        if m_key != curr_month:
            curr_month = m_key
            month_cum = 0.0
            month_locked = False
            curr_unit = base_unit

        if pos == 1:
            exit_trig = False
            exit_p = 0.0
            if lows[i] <= sl_p:
                exit_p = sl_p if opens[i] >= sl_p else opens[i]
                exit_trig = True
            elif highs[i] >= tp_p:
                exit_p = tp_p if opens[i] <= tp_p else opens[i]
                exit_trig = True
            if exit_trig:
                pnl = (exit_p - entry_p) * curr_unit - (spread + comm) * curr_unit
                trades.append({"asset": "GOLD", "pnl": pnl, "date": dates[i], "month": m_key})
                month_cum += pnl
                pos = 0
                if profit_lock > 0 and month_cum >= profit_lock: month_locked = True
                elif month_cum <= -250.0: month_locked = True
                elif def_thresh > 0 and month_cum <= -def_thresh: curr_unit = base_unit * def_mult

        elif pos == -1:
            exit_trig = False
            exit_p = 0.0
            if highs[i] >= sl_p:
                exit_p = sl_p if opens[i] <= sl_p else opens[i]
                exit_trig = True
            elif lows[i] <= tp_p:
                exit_p = tp_p if opens[i] >= tp_p else opens[i]
                exit_trig = True
            if exit_trig:
                pnl = (entry_p - exit_p) * curr_unit - (spread + comm) * curr_unit
                trades.append({"asset": "GOLD", "pnl": pnl, "date": dates[i], "month": m_key})
                month_cum += pnl
                pos = 0
                if profit_lock > 0 and month_cum >= profit_lock: month_locked = True
                elif month_cum <= -250.0: month_locked = True
                elif def_thresh > 0 and month_cum <= -def_thresh: curr_unit = base_unit * def_mult

        if pos == 0 and c_atr > 0 and not month_locked:
            if 8 <= hr < 18:
                if closes[i] > h8_arr[i] and closes[i] > ema200[i] and closes[i] > ema50[i]:
                    pos = 1
                    entry_p = opens[i + 1] + (spread * 0.5)
                    sl_dist = trend_sl * c_atr
                    sl_p = entry_p - sl_dist
                    tp_p = entry_p + (sl_dist * trend_tp)
                elif closes[i] < l8_arr[i] and closes[i] < ema200[i] and closes[i] < ema50[i]:
                    pos = -1
                    entry_p = opens[i + 1] - (spread * 0.5)
                    sl_dist = trend_sl * c_atr
                    sl_p = entry_p + sl_dist
                    tp_p = entry_p - (sl_dist * trend_tp)

    return trades

def run_eur_h1_trades(df_h1: pd.DataFrame, lb=12, profit_lock=120.0, trend_tp=4.0, trend_sl=1.8, def_thresh=80.0, def_mult=0.3):
    opens = df_h1["open"].values.astype(np.float64)
    highs = df_h1["high"].values.astype(np.float64)
    lows = df_h1["low"].values.astype(np.float64)
    closes = df_h1["close"].values.astype(np.float64)
    dates = df_h1.index
    months = (dates.year.values * 100 + dates.month.values).astype(np.int32)

    atr14 = compute_atr(highs, lows, closes, 14)
    ema50 = compute_ema(closes, 50)
    ema200 = compute_ema(closes, 200)
    h_arr = pd.Series(highs).rolling(lb).max().shift(1).fillna(999999.0).values
    l_arr = pd.Series(lows).rolling(lb).min().shift(1).fillna(0.0).values

    n = len(closes)
    trades = []
    pos = 0
    entry_p = 0.0
    sl_p = 0.0
    tp_p = 0.0
    spread = 0.00005
    comm = 0.00006
    base_unit = 10000.0
    curr_unit = base_unit

    curr_month = None
    month_cum = 0.0
    month_locked = False

    for i in range(250, n - 1):
        m_key = months[i]
        c_atr = atr14[i]

        if m_key != curr_month:
            curr_month = m_key
            month_cum = 0.0
            month_locked = False
            curr_unit = base_unit

        if pos == 1:
            exit_trig = False
            exit_p = 0.0
            if lows[i] <= sl_p:
                exit_p = sl_p if opens[i] >= sl_p else opens[i]
                exit_trig = True
            elif highs[i] >= tp_p:
                exit_p = tp_p if opens[i] <= tp_p else opens[i]
                exit_trig = True
            if exit_trig:
                pnl = (exit_p - entry_p) * curr_unit - (spread + comm) * curr_unit
                trades.append({"asset": "EURUSD", "pnl": pnl, "date": dates[i], "month": m_key})
                month_cum += pnl
                pos = 0
                if profit_lock > 0 and month_cum >= profit_lock: month_locked = True
                elif month_cum <= -200.0: month_locked = True
                elif def_thresh > 0 and month_cum <= -def_thresh: curr_unit = base_unit * def_mult

        elif pos == -1:
            exit_trig = False
            exit_p = 0.0
            if highs[i] >= sl_p:
                exit_p = sl_p if opens[i] <= sl_p else opens[i]
                exit_trig = True
            elif lows[i] <= tp_p:
                exit_p = tp_p if opens[i] >= tp_p else opens[i]
                exit_trig = True
            if exit_trig:
                pnl = (entry_p - exit_p) * curr_unit - (spread + comm) * curr_unit
                trades.append({"asset": "EURUSD", "pnl": pnl, "date": dates[i], "month": m_key})
                month_cum += pnl
                pos = 0
                if profit_lock > 0 and month_cum >= profit_lock: month_locked = True
                elif month_cum <= -200.0: month_locked = True
                elif def_thresh > 0 and month_cum <= -def_thresh: curr_unit = base_unit * def_mult

        if pos == 0 and c_atr > 0 and not month_locked:
            if closes[i] > h_arr[i] and closes[i] > ema200[i] and closes[i] > ema50[i]:
                pos = 1
                entry_p = opens[i + 1] + (spread * 0.5)
                sl_dist = trend_sl * c_atr
                sl_p = entry_p - sl_dist
                tp_p = entry_p + (sl_dist * trend_tp)
            elif closes[i] < l_arr[i] and closes[i] < ema200[i] and closes[i] < ema50[i]:
                pos = -1
                entry_p = opens[i + 1] - (spread * 0.5)
                sl_dist = trend_sl * c_atr
                sl_p = entry_p + sl_dist
                tp_p = entry_p - (sl_dist * trend_tp)

    return trades

def evaluate_portfolio(trades_gold: list, trades_eur: list) -> dict:
    all_trades = trades_gold + trades_eur
    df_all = pd.DataFrame(all_trades)
    df_all["date"] = pd.to_datetime(df_all["date"])
    df_all.sort_values(by="date", inplace=True)
    df_all["year_month"] = df_all["date"].dt.to_period("M").astype(str)

    m_pnl = df_all.groupby("year_month")["pnl"].sum()
    monthly_dict = {k: round(float(v), 2) for k, v in m_pnl.to_dict().items()}

    total_months = 72
    pos_months = int((m_pnl > 0).sum())
    neg_months = total_months - pos_months
    mcr = round((pos_months / total_months) * 100.0, 2)

    net_profit = round(float(df_all["pnl"].sum()), 2)
    gross_win = float(df_all[df_all["pnl"] > 0]["pnl"].sum())
    gross_loss = float(abs(df_all[df_all["pnl"] < 0]["pnl"].sum()))
    pf = round(gross_win / max(gross_loss, 1e-4), 3)

    win_rate = round((df_all["pnl"] > 0).mean() * 100.0, 2)

    cum_pnl = df_all["pnl"].cumsum()
    peak = cum_pnl.cummax()
    max_dd = round(float((peak - cum_pnl).max()), 2)

    df_gold = pd.DataFrame(trades_gold)
    df_eur = pd.DataFrame(trades_eur)

    return {
        "total_trades": len(all_trades),
        "gold_trades": len(df_gold),
        "eur_trades": len(df_eur),
        "gold_net": round(float(df_gold["pnl"].sum()), 2),
        "eur_net": round(float(df_eur["pnl"].sum()), 2),
        "net_profit": net_profit,
        "pf": pf,
        "win_rate": win_rate,
        "max_dd": max_dd,
        "mcr": mcr,
        "total_months": total_months,
        "pos_months": pos_months,
        "neg_months": neg_months,
        "monthly_series": monthly_dict
    }

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--gold_data", type=str, default="/mnt/sdcard/Download/EA/XAUUSD_M1.csv.gz")
    parser.add_argument("--eur_data", type=str, default="/mnt/sdcard/Download/EA/EURUSD_M1.csv.gz")
    parser.add_argument("--out_dir", type=str, default="/root/CFD-Trading-ML/projects/quant_strategy_discovery/results")
    args = parser.parse_args()

    os.makedirs(args.out_dir, exist_ok=True)

    print("[*] Loading Gold M1 data...")
    df_gold_raw = pd.read_csv(args.gold_data, usecols=["datetime", "open", "high", "low", "close", "tick_volume"],
                              dtype={"open": np.float32, "high": np.float32, "low": np.float32, "close": np.float32, "tick_volume": np.int32})
    df_gold_raw["datetime"] = pd.to_datetime(df_gold_raw["datetime"])
    df_gold_raw.set_index("datetime", inplace=True)
    df_gold_raw.sort_index(inplace=True)
    df_gold_m15 = df_gold_raw.resample("15min").agg({"open": "first", "high": "max", "low": "min", "close": "last", "tick_volume": "sum"}).dropna()

    print("[*] Loading EURUSD M1 data...")
    df_eur_raw = pd.read_csv(args.eur_data, usecols=["datetime", "open", "high", "low", "close", "tick_volume"],
                             dtype={"open": np.float32, "high": np.float32, "low": np.float32, "close": np.float32, "tick_volume": np.int32})
    df_eur_raw["datetime"] = pd.to_datetime(df_eur_raw["datetime"])
    df_eur_raw.set_index("datetime", inplace=True)
    df_eur_raw.sort_index(inplace=True)
    df_eur_h1 = df_eur_raw.resample("1h").agg({"open": "first", "high": "max", "low": "min", "close": "last", "tick_volume": "sum"}).dropna()

    print("[*] Simulating Strategy 32: DA-ARIC Composite across 72 Calendar Months...")
    t_start = time.time()

    print("\n[*] Evaluating Strategy 32 Variant A (High Consistency Composite)...")
    trades_gold_a = run_gold_m15_trades(df_gold_m15, profit_lock=150.0, trend_tp=4.0, trend_sl=2.5, def_thresh=100.0, def_mult=0.3)
    trades_eur = run_eur_h1_trades(df_eur_h1, lb=12, profit_lock=120.0, trend_tp=4.0, trend_sl=1.8, def_thresh=80.0, def_mult=0.3)
    port_a = evaluate_portfolio(trades_gold_a, trades_eur)

    # Variant B: Sniper Composite (KFD 1.40, VR 1.15 on Gold)
    print("[*] Evaluating Strategy 32 Variant B (Ultra-Sniper Composite)...")
    opens_g = df_gold_m15["open"].values.astype(np.float64)
    highs_g = df_gold_m15["high"].values.astype(np.float64)
    lows_g = df_gold_m15["low"].values.astype(np.float64)
    closes_g = df_gold_m15["close"].values.astype(np.float64)
    hours_g = df_gold_m15.index.hour.values.astype(np.int32)
    dates_g = df_gold_m15.index
    months_g = (dates_g.year.values * 100 + dates_g.month.values).astype(np.int32)

    atr14_g = compute_atr(highs_g, lows_g, closes_g, 14)
    atr7_g = compute_atr(highs_g, lows_g, closes_g, 7)
    atr28_g = compute_atr(highs_g, lows_g, closes_g, 28)
    vr_ratio_g = atr7_g / np.maximum(atr28_g, 1e-4)
    ema50_g = compute_ema(closes_g, 50)
    ema200_g = compute_ema(closes_g, 200)
    h8_g = pd.Series(highs_g).rolling(8).max().shift(1).fillna(999999.0).values
    l8_g = pd.Series(lows_g).rolling(8).min().shift(1).fillna(0.0).values

    # KFD
    diffs_g = np.abs(np.diff(closes_g, prepend=closes_g[0]))
    rolling_L_g = pd.Series(diffs_g).rolling(32).sum().values
    rolling_min_g = pd.Series(closes_g).rolling(32).min().values
    rolling_max_g = pd.Series(closes_g).rolling(32).max().values
    rolling_d_g = np.maximum(rolling_max_g - rolling_min_g, 1e-4)
    kfd_g = np.ones(len(closes_g), dtype=np.float64) * 1.5
    for i in range(32, len(closes_g)):
        c_atr = max(atr14_g[i], 0.1)
        L_norm = max(rolling_L_g[i] / c_atr, 1.01)
        d_norm = max(rolling_d_g[i] / c_atr, 1.01)
        kfd_g[i] = np.clip(np.log10(L_norm) / np.log10(d_norm), 1.0, 2.0)

    from projects.quant_strategy_discovery.scripts.strategy_30_mfe_sve_champion_sweep import simulate_mfe_sve
    trades_gold_b = simulate_mfe_sve(
        opens=opens_g, highs=highs_g, lows=lows_g, closes=closes_g,
        atr14=atr14_g, ema50=ema50_g, ema200=ema200_g,
        h_lookback=h8_g, l_lookback=l8_g,
        kfd=kfd_g, vr_ratio=vr_ratio_g,
        months=months_g, hours=hours_g, dates=dates_g,
        use_kfd=True, kfd_thresh=1.40,
        use_vr=True, vr_thresh=1.15,
        use_ema50_filter=False,
        monthly_profit_lock=150.0,
        trend_tp_mult=4.5, trend_sl_mult=2.0,
        defensive_thresh=120.0, defensive_lot_mult=0.25
    )
    for t in trades_gold_b: t["asset"] = "GOLD_SNIPER"
    port_b = evaluate_portfolio(trades_gold_b, trades_eur)

    # Save champion JSON
    champ_json_path = os.path.join(args.out_dir, "strategy_32_champion.json")
    with open(champ_json_path, "w") as f:
        json.dump({
            "variant_a_consistency": port_a,
            "variant_b_sniper": port_b
        }, f, indent=2)

    print("\n" + "="*80)
    print("STRATEGY 32: DUAL-ASSET ASYNCHRONOUS RISK-ISOLATED COMPOSITE (DA-ARIC)")
    print("="*80)
    print("VARIANT A: HIGH-CONSISTENCY COMPOSITE (Gold MFE-SVE + EURUSD H1)")
    print(f"  - Total Trades: {port_a['total_trades']} (Gold: {port_a['gold_trades']}, EUR: {port_a['eur_trades']})")
    print(f"  - Portfolio Net Profit: ${port_a['net_profit']:,.2f} (Gold: ${port_a['gold_net']:,.2f}, EUR: ${port_a['eur_net']:,.2f})")
    print(f"  - Profit Factor (PF): {port_a['pf']}")
    print(f"  - Max Drawdown: ${port_a['max_dd']:,.2f}")
    print(f"  - Monthly Consistency Ratio (MCR): {port_a['mcr']}% ({port_a['pos_months']}/{port_a['total_months']} profitable months)")
    print("-" * 80)
    print("VARIANT B: ULTRA-SNIPER COMPOSITE (Gold KFD Sniper + EURUSD H1)")
    print(f"  - Total Trades: {port_b['total_trades']} (Gold: {port_b['gold_trades']}, EUR: {port_b['eur_trades']})")
    print(f"  - Portfolio Net Profit: ${port_b['net_profit']:,.2f} (Gold: ${port_b['gold_net']:,.2f}, EUR: ${port_b['eur_net']:,.2f})")
    print(f"  - Profit Factor (PF): {port_b['pf']}")
    print(f"  - Max Drawdown: ${port_b['max_dd']:,.2f}")
    print(f"  - Monthly Consistency Ratio (MCR): {port_b['mcr']}% ({port_b['pos_months']}/{port_b['total_months']} profitable months)")
    print(f"Elapsed Time: {time.time() - t_start:.2f}s")
    print("="*80)

if __name__ == "__main__":
    main()
