#!/usr/bin/env python3
"""
===============================================================================
STRATEGY 40: HIERARCHICAL ASAR GOVERNANCE & MCR CONSISTENCY ENHANCER (H-ASAR)
===============================================================================
Assets & Engines:
  5-Engine Master Suite (KAMA H1, HMA-CMO H1, Vortex H1, MFE-SVE M15, DEC H1)
  Each engine retains its proven individual ASAR shields.
  A Portfolio Master ASAR Governor sits above all engines.

Horizon: 2020-01-01 to 2025-12-30 (72 Calendar Months)
Objective: Boost MCR >= 70% - 80%+ while preserving Profit Factor >= 1.80 - 2.00+
===============================================================================
"""

import os
import sys
import time
import json
import argparse
import numpy as np
import pandas as pd

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from strategy_36_kama_efficiency_sweep import simulate_kama_strategy, compute_atr as atr_kama, compute_ema as ema_kama, compute_katz_fractal_dimension as kfd_kama, compute_kama
from strategy_38_hma_cmo_velocity_sweep import simulate_hma_cmo_strategy, compute_hma, compute_cmo
from strategy_35_vortex_momentum_sweep import simulate_vortex_strategy, compute_vortex_indicator
from strategy_31_eurusd_h1_macro_momentum_sweep import simulate_eur_h1, compute_atr as atr_eur, compute_ema as ema_eur
from strategy_30_mfe_sve_champion_sweep import simulate_mfe_sve

def simulate_portfolio_governance(all_trades_raw: list, p_profit_lock: float, p_loss_breaker: float, p_def_thresh: float, p_def_mult: float):
    sorted_trades = sorted(all_trades_raw, key=lambda x: x["date"])

    trades_out = []
    curr_month = None
    month_cum_pnl = 0.0
    month_locked = False

    for t in sorted_trades:
        m_key = t["month"]
        if m_key != curr_month:
            curr_month = m_key
            month_cum_pnl = 0.0
            month_locked = False

        if month_locked:
            continue

        raw_pnl = t["pnl"]

        # Check portfolio defensive sizing
        curr_mult = 1.0
        if p_def_thresh > 0 and month_cum_pnl <= -p_def_thresh:
            curr_mult = p_def_mult

        adj_pnl = raw_pnl * curr_mult
        trades_out.append({
            "pnl": adj_pnl,
            "date": t["date"],
            "engine": t["engine"],
            "month": m_key
        })
        month_cum_pnl += adj_pnl

        # Check portfolio locks
        if p_profit_lock > 0 and month_cum_pnl >= p_profit_lock:
            month_locked = True
        elif p_loss_breaker > 0 and month_cum_pnl <= -p_loss_breaker:
            month_locked = True

    return trades_out

def evaluate_metrics(trades: list) -> dict:
    if len(trades) < 50:
        return {
            "total_trades": len(trades), "net_profit": -9999.0, "pf": 0.0,
            "win_rate": 0.0, "max_dd": 9999.0, "romad": 0.0, "mcr": 0.0, "pos_months": 0, "total_months": 72
        }

    pnls = np.array([t["pnl"] for t in trades])
    net_profit = float(np.sum(pnls))
    wins = pnls[pnls > 0]
    losses = pnls[pnls < 0]
    gross_win = float(np.sum(wins))
    gross_loss = float(abs(np.sum(losses))) if len(losses) > 0 else 1e-4
    pf = float(gross_win / gross_loss)
    win_rate = float(len(wins) / len(pnls) * 100.0)

    equity = np.cumsum(pnls)
    peak = np.maximum.accumulate(equity)
    dd = peak - equity
    max_dd = float(np.max(dd)) if len(dd) > 0 else 1.0
    romad = float(net_profit / max_dd)

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
        "romad": round(romad, 2),
        "mcr": mcr,
        "pos_months": pos_m,
        "total_months": len(all_months),
        "monthly_series": m_series
    }

def main():
    parser = argparse.ArgumentParser(description="Sweep Strategy 40: Hierarchical ASAR Governance")
    parser.add_argument("--gold_data", type=str, default="/mnt/sdcard/Download/EA/XAUUSD_M1.csv.gz")
    parser.add_argument("--eur_data", type=str, default="/mnt/sdcard/Download/EA/EURUSD_M1.csv.gz")
    parser.add_argument("--out_dir", type=str, default="projects/quant_strategy_discovery/results")
    args = parser.parse_args()

    os.makedirs(args.out_dir, exist_ok=True)
    t_start = time.time()

    print("[*] Generating Strategy 39 proven shielded engine trade streams...")
    df_gold = pd.read_csv(args.gold_data, usecols=["datetime", "open", "high", "low", "close"])
    df_gold["datetime"] = pd.to_datetime(df_gold["datetime"])
    df_gold.set_index("datetime", inplace=True)
    df_gold.sort_index(inplace=True)

    df_gold_h1 = df_gold.resample("1h").agg({"open": "first", "high": "max", "low": "min", "close": "last"}).dropna()
    df_gold_m15 = df_gold.resample("15min").agg({"open": "first", "high": "max", "low": "min", "close": "last"}).dropna()

    df_eur = pd.read_csv(args.eur_data, usecols=["datetime", "open", "high", "low", "close"])
    df_eur["datetime"] = pd.to_datetime(df_eur["datetime"])
    df_eur.set_index("datetime", inplace=True)
    df_eur.sort_index(inplace=True)
    df_eur_h1 = df_eur.resample("1h").agg({"open": "first", "high": "max", "low": "min", "close": "last"}).dropna()

    g_h1_opens = df_gold_h1["open"].values.astype(np.float64)
    g_h1_highs = df_gold_h1["high"].values.astype(np.float64)
    g_h1_lows = df_gold_h1["low"].values.astype(np.float64)
    g_h1_closes = df_gold_h1["close"].values.astype(np.float64)
    g_h1_dates = df_gold_h1.index
    g_h1_months = (g_h1_dates.year.values * 100 + g_h1_dates.month.values).astype(np.int32)

    atr14_gh1 = atr_kama(g_h1_highs, g_h1_lows, g_h1_closes, 14)
    ema50_gh1 = ema_kama(g_h1_closes, 50)
    ema200_gh1 = ema_kama(g_h1_closes, 200)
    kfd24_gh1 = kfd_kama(g_h1_closes, atr14_gh1, 24)

    # 1. KAMA H1 (Retains individual ASAR: Lock $250, Breaker $250, Def $120 -> 0.25x)
    kama10, er10, slope10 = compute_kama(g_h1_closes, n_period=10)
    trades_e1 = simulate_kama_strategy(
        opens=g_h1_opens, highs=g_h1_highs, lows=g_h1_lows, closes=g_h1_closes,
        atr14=atr14_gh1, ema200=ema200_gh1, kfd=kfd24_gh1,
        kama=kama10, er=er10, kama_slope=slope10,
        h_lookback=g_h1_highs, l_lookback=g_h1_lows,
        months=g_h1_months, dates=g_h1_dates,
        use_channel=False, er_threshold=0.45,
        use_kfd=False, kfd_thresh=1.40,
        monthly_profit_lock=250.0, monthly_loss_breaker=250.0,
        defensive_thresh=120.0, defensive_lot_mult=0.25,
        trend_tp_mult=4.5, trend_sl_mult=2.0
    )
    for t in trades_e1: t["engine"] = "E1_KAMA"

    # 2. HMA-CMO H1 (Individual ASAR: Lock $200, Breaker $250, Def $120 -> 0.25x)
    hma24 = compute_hma(g_h1_closes, period=24)
    cmo10 = compute_cmo(g_h1_closes, period=10)
    h_lb12 = pd.Series(g_h1_highs).rolling(12).max().shift(1).fillna(999999.0).values
    l_lb12 = pd.Series(g_h1_lows).rolling(12).min().shift(1).fillna(0.0).values
    trades_e2 = simulate_hma_cmo_strategy(
        opens=g_h1_opens, highs=g_h1_highs, lows=g_h1_lows, closes=g_h1_closes,
        atr14=atr14_gh1, ema200=ema200_gh1, kfd=kfd24_gh1,
        hma=hma24, cmo=cmo10,
        h_lookback=h_lb12, l_lookback=l_lb12,
        months=g_h1_months, dates=g_h1_dates,
        use_channel=True, cmo_threshold=25.0,
        use_kfd=True, kfd_thresh=1.40,
        monthly_profit_lock=200.0, monthly_loss_breaker=250.0,
        defensive_thresh=120.0, defensive_lot_mult=0.25,
        trend_tp_mult=4.5, trend_sl_mult=2.5
    )
    for t in trades_e2: t["engine"] = "E2_HMA_CMO"

    # 3. Vortex H1 (Individual ASAR: Lock $200, Breaker $250, Def $120 -> 0.25x)
    vi_p14, vi_m14, d_vi14 = compute_vortex_indicator(g_h1_highs, g_h1_lows, g_h1_closes, 14)
    h_lb16 = pd.Series(g_h1_highs).rolling(16).max().shift(1).fillna(999999.0).values
    l_lb16 = pd.Series(g_h1_lows).rolling(16).min().shift(1).fillna(0.0).values
    trades_e3 = simulate_vortex_strategy(
        opens=g_h1_opens, highs=g_h1_highs, lows=g_h1_lows, closes=g_h1_closes,
        atr14=atr14_gh1, ema50=ema50_gh1, ema200=ema200_gh1,
        h_lookback=h_lb16, l_lookback=l_lb16,
        kfd=kfd24_gh1, vi_plus=vi_p14, vi_minus=vi_m14, delta_vi=d_vi14,
        months=g_h1_months, dates=g_h1_dates,
        use_kfd=True, kfd_thresh=1.35, delta_vi_thresh=0.05,
        entry_mode="breakout_vortex",
        monthly_profit_lock=200.0, monthly_loss_breaker=250.0,
        defensive_thresh=120.0, defensive_lot_mult=0.25,
        trend_tp_mult=4.0, trend_sl_mult=2.5
    )
    for t in trades_e3: t["engine"] = "E3_VORTEX"

    # 4. Gold M15 MFE-SVE (Individual ASAR: Lock $200, Breaker $250, Def $120 -> 0.30x)
    g_m15_opens = df_gold_m15["open"].values.astype(np.float64)
    g_m15_highs = df_gold_m15["high"].values.astype(np.float64)
    g_m15_lows = df_gold_m15["low"].values.astype(np.float64)
    g_m15_closes = df_gold_m15["close"].values.astype(np.float64)
    g_m15_dates = df_gold_m15.index
    g_m15_months = (g_m15_dates.year.values * 100 + g_m15_dates.month.values).astype(np.int32)
    g_m15_hours = g_m15_dates.hour.values.astype(np.int32)

    atr14_gm15 = atr_kama(g_m15_highs, g_m15_lows, g_m15_closes, 14)
    ema50_gm15 = ema_kama(g_m15_closes, 50)
    ema200_gm15 = ema_kama(g_m15_closes, 200)
    kfd32_gm15 = kfd_kama(g_m15_closes, atr14_gm15, 32)
    h_lb16_m15 = pd.Series(g_m15_highs).rolling(16).max().shift(1).fillna(999999.0).values
    l_lb16_m15 = pd.Series(g_m15_lows).rolling(16).min().shift(1).fillna(0.0).values
    vr14_gm15 = pd.Series(atr14_gm15).rolling(14).mean().values
    vr14_gm15 = np.where(vr14_gm15 <= 0, 1e-4, atr14_gm15 / vr14_gm15)

    trades_e4 = simulate_mfe_sve(
        opens=g_m15_opens, highs=g_m15_highs, lows=g_m15_lows, closes=g_m15_closes,
        atr14=atr14_gm15, ema50=ema50_gm15, ema200=ema200_gm15,
        h_lookback=h_lb16_m15, l_lookback=l_lb16_m15,
        kfd=kfd32_gm15, vr_ratio=vr14_gm15,
        months=g_m15_months, hours=g_m15_hours, dates=g_m15_dates,
        use_kfd=True, kfd_thresh=1.40,
        use_vr=False, vr_thresh=1.20,
        use_ema50_filter=True,
        start_hour=8, end_hour=18,
        monthly_profit_lock=200.0, monthly_loss_breaker=250.0,
        defensive_thresh=120.0, defensive_lot_mult=0.30
    )
    for t in trades_e4: t["engine"] = "E4_M15_SVE"

    # 5. EURUSD H1 DEC (Individual ASAR: Lock $120, Breaker $150, Def $80 -> 0.30x)
    eur_opens = df_eur_h1["open"].values.astype(np.float64)
    eur_highs = df_eur_h1["high"].values.astype(np.float64)
    eur_lows = df_eur_h1["low"].values.astype(np.float64)
    eur_closes = df_eur_h1["close"].values.astype(np.float64)
    eur_dates = df_eur_h1.index
    eur_months = (eur_dates.year.values * 100 + eur_dates.month.values).astype(np.int32)

    atr14_eur = atr_eur(eur_highs, eur_lows, eur_closes, 14)
    ema50_eur = ema_eur(eur_closes, 50)
    ema200_eur = ema_eur(eur_closes, 200)
    h_lb12_eur = pd.Series(eur_highs).rolling(12).max().shift(1).fillna(999999.0).values
    l_lb12_eur = pd.Series(eur_lows).rolling(12).min().shift(1).fillna(0.0).values

    trades_e5 = simulate_eur_h1(
        opens=eur_opens, highs=eur_highs, lows=eur_lows, closes=eur_closes,
        atr14=atr14_eur, ema50=ema50_eur, ema200=ema200_eur,
        h_lookback=h_lb12_eur, l_lookback=l_lb12_eur,
        months=eur_months, dates=eur_dates,
        monthly_profit_lock=120.0, monthly_loss_breaker=150.0,
        defensive_thresh=80.0, defensive_lot_mult=0.30,
        trend_tp_mult=4.0, trend_sl_mult=2.5
    )
    for t in trades_e5: t["engine"] = "E5_EUR_DEC"

    raw_shielded_trades = trades_e1 + trades_e2 + trades_e3 + trades_e4 + trades_e5
    print(f"[+] Total individually shielded trades: {len(raw_shielded_trades):,}")

    # Now sweep Hierarchical Portfolio Governance sitting ON TOP of the individually shielded engines
    p_profit_locks = [0.0, 400.0, 500.0, 600.0, 750.0, 1000.0, 1500.0]
    p_loss_breakers = [0.0, 300.0, 400.0, 500.0, 600.0]
    p_def_threshs = [0.0, 200.0, 300.0]
    p_def_mults = [0.25, 0.50]

    total_combs = len(p_profit_locks) * len(p_loss_breakers) * len(p_def_threshs) * len(p_def_mults)
    print(f"[*] Sweeping Strategy 40 Hierarchical ASAR across {total_combs} combinations...")

    results = []
    for plock in p_profit_locks:
        for pbreak in p_loss_breakers:
            for pdef_th in p_def_threshs:
                for pdef_m in p_def_mults:
                    trades_gov = simulate_portfolio_governance(
                        raw_shielded_trades,
                        p_profit_lock=plock,
                        p_loss_breaker=pbreak,
                        p_def_thresh=pdef_th,
                        p_def_mult=pdef_m
                    )
                    m = evaluate_metrics(trades_gov)
                    m.update({
                        "portfolio_profit_lock": plock,
                        "portfolio_loss_breaker": pbreak,
                        "portfolio_def_thresh": pdef_th,
                        "portfolio_def_mult": pdef_m
                    })
                    results.append(m)

    df_res = pd.DataFrame(results)
    # Sort by MCR, then PF, then Net Profit
    df_res.sort_values(by=["mcr", "pf", "net_profit"], ascending=[False, False, False], inplace=True)

    csv_path = os.path.join(args.out_dir, "strategy_40_hierarchical_asar_results.csv")
    df_res.drop(columns=["monthly_series"]).to_csv(csv_path, index=False)
    print(f"[+] Saved Strategy 40 sweep results to {csv_path}")

    top_champ = results[df_res.index[0]]
    champ_json_path = os.path.join(args.out_dir, "strategy_40_champion.json")
    with open(champ_json_path, "w") as f:
        json.dump(top_champ, f, indent=2)

    print("\n" + "="*80)
    print("STRATEGY 40: HIERARCHICAL ASAR (H-ASAR) CHAMPION RESULTS")
    print("="*80)
    print(f"Top Configuration:")
    print(f"  - Portfolio Monthly Profit Lock: ${top_champ['portfolio_profit_lock']}")
    print(f"  - Portfolio Monthly Loss Breaker: ${top_champ['portfolio_loss_breaker']}")
    print(f"  - Portfolio Defensive Threshold: ${top_champ['portfolio_def_thresh']} -> {top_champ['portfolio_def_mult']}x Lot")
    print("-" * 80)
    print(f"Performance Metrics Across 72 Calendar Months (2020 - 2025):")
    print(f"  - Total Trades: {top_champ['total_trades']}")
    print(f"  - Net Profit: ${top_champ['net_profit']:,.2f}")
    print(f"  - Profit Factor (PF): {top_champ['pf']}  <-- MANDATE BENCHMARK (>= 1.50+)")
    print(f"  - Win Rate: {top_champ['win_rate']}%")
    print(f"  - Max Drawdown: ${top_champ['max_dd']:,.2f}")
    print(f"  - Return on Max DD (RoMaD): {top_champ['romad']}x")
    print(f"  - Monthly Consistency Ratio (MCR): {top_champ['mcr']}% ({top_champ['pos_months']}/{top_champ['total_months']} profitable months)")
    print(f"Sweep Execution Time: {time.time() - t_start:.2f}s")
    print("="*80)

    print("\nTop 10 Distinct Configurations by MCR:")
    top10 = df_res.head(10)[["portfolio_profit_lock", "portfolio_loss_breaker", "portfolio_def_thresh", "mcr", "pos_months", "pf", "net_profit", "max_dd", "romad"]]
    print(top10.to_string(index=False))

if __name__ == "__main__":
    main()
