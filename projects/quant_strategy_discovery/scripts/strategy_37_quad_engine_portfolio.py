#!/usr/bin/env python3
"""
===============================================================================
STRATEGY 37: QUAD-ENGINE INSTITUTIONAL ALPHA COMPOSITE (QE-IAC)
===============================================================================
Assets: 
  - Engine 1: Gold H1 KAMA Dynamic Efficiency (S36, Single PF 2.715)
  - Engine 2: Gold H1 Vortex Velocity Breakout (S35, Single PF 2.232)
  - Engine 3: Gold M15 Fractal Expansion SVE (S30, Single PF 1.352)
  - Engine 4: EURUSD H1 Macro Structural Momentum (S31, Single PF 1.214)

Horizon: 2020-01-01 to 2025-12-30 (72 Calendar Months)
===============================================================================
"""

import os
import sys
import time
import json
import argparse
import numpy as np
import pandas as pd

# Add script directory to sys.path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from strategy_36_kama_efficiency_sweep import simulate_kama_strategy, compute_atr as atr_kama, compute_ema as ema_kama, compute_katz_fractal_dimension as kfd_kama, compute_kama
from strategy_35_vortex_momentum_sweep import simulate_vortex_strategy, compute_vortex_indicator
from strategy_31_eurusd_h1_macro_momentum_sweep import simulate_eur_h1, compute_atr as atr_eur, compute_ema as ema_eur
from strategy_30_mfe_sve_champion_sweep import simulate_mfe_sve

def main():
    parser = argparse.ArgumentParser(description="Evaluate Strategy 37: Quad-Engine Portfolio")
    parser.add_argument("--gold_data", type=str, default="/mnt/sdcard/Download/EA/XAUUSD_M1.csv.gz")
    parser.add_argument("--eur_data", type=str, default="/mnt/sdcard/Download/EA/EURUSD_M1.csv.gz")
    parser.add_argument("--out_dir", type=str, default="projects/quant_strategy_discovery/results")
    args = parser.parse_args()

    os.makedirs(args.out_dir, exist_ok=True)
    t_start = time.time()

    print("[*] Loading Gold raw M1...")
    df_gold = pd.read_csv(args.gold_data, usecols=["datetime", "open", "high", "low", "close"])
    df_gold["datetime"] = pd.to_datetime(df_gold["datetime"])
    df_gold.set_index("datetime", inplace=True)
    df_gold.sort_index(inplace=True)

    print("[*] Resampling Gold H1 & M15...")
    df_gold_h1 = df_gold.resample("1h").agg({"open": "first", "high": "max", "low": "min", "close": "last"}).dropna()
    df_gold_m15 = df_gold.resample("15min").agg({"open": "first", "high": "max", "low": "min", "close": "last"}).dropna()

    print("[*] Loading EURUSD raw M1...")
    df_eur = pd.read_csv(args.eur_data, usecols=["datetime", "open", "high", "low", "close"])
    df_eur["datetime"] = pd.to_datetime(df_eur["datetime"])
    df_eur.set_index("datetime", inplace=True)
    df_eur.sort_index(inplace=True)
    df_eur_h1 = df_eur.resample("1h").agg({"open": "first", "high": "max", "low": "min", "close": "last"}).dropna()

    # --- ENGINE 1: Gold H1 KAMA (PF 2.715) ---
    print("[*] Simulating Engine 1: Gold H1 KAMA...")
    g_h1_opens = df_gold_h1["open"].values.astype(np.float64)
    g_h1_highs = df_gold_h1["high"].values.astype(np.float64)
    g_h1_lows = df_gold_h1["low"].values.astype(np.float64)
    g_h1_closes = df_gold_h1["close"].values.astype(np.float64)
    g_h1_dates = df_gold_h1.index
    g_h1_months = (g_h1_dates.year.values * 100 + g_h1_dates.month.values).astype(np.int32)

    atr14_gh1 = atr_kama(g_h1_highs, g_h1_lows, g_h1_closes, 14)
    ema200_gh1 = ema_kama(g_h1_closes, 200)
    kfd24_gh1 = kfd_kama(g_h1_closes, atr14_gh1, 24)
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
    for t in trades_e1: t["engine"] = "E1_GOLD_H1_KAMA"
    print(f"  [+] Engine 1 generated {len(trades_e1)} trades.")

    # --- ENGINE 2: Gold H1 Vortex Velocity (PF 2.232) ---
    print("[*] Simulating Engine 2: Gold H1 Vortex Velocity...")
    ema50_gh1 = ema_kama(g_h1_closes, 50)
    vi_p14, vi_m14, d_vi14 = compute_vortex_indicator(g_h1_highs, g_h1_lows, g_h1_closes, 14)
    h_lb16 = pd.Series(g_h1_highs).rolling(16).max().shift(1).fillna(999999.0).values
    l_lb16 = pd.Series(g_h1_lows).rolling(16).min().shift(1).fillna(0.0).values

    trades_e2 = simulate_vortex_strategy(
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
    for t in trades_e2: t["engine"] = "E2_GOLD_H1_VORTEX"
    print(f"  [+] Engine 2 generated {len(trades_e2)} trades.")

    # --- ENGINE 3: Gold M15 MFE-SVE (PF 1.352, Net +$4,841) ---
    print("[*] Simulating Engine 3: Gold M15 MFE-SVE...")
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

    trades_e3 = simulate_mfe_sve(
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
    for t in trades_e3: t["engine"] = "E3_GOLD_M15_SVE"
    print(f"  [+] Engine 3 generated {len(trades_e3)} trades.")

    # --- ENGINE 4: EURUSD H1 DEC (PF 1.214, Net +$1,958) ---
    print("[*] Simulating Engine 4: EURUSD H1 Macro Momentum...")
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

    trades_e4 = simulate_eur_h1(
        opens=eur_opens, highs=eur_highs, lows=eur_lows, closes=eur_closes,
        atr14=atr14_eur, ema50=ema50_eur, ema200=ema200_eur,
        h_lookback=h_lb12_eur, l_lookback=l_lb12_eur,
        months=eur_months, dates=eur_dates,
        monthly_profit_lock=120.0, monthly_loss_breaker=150.0,
        defensive_thresh=80.0, defensive_lot_mult=0.30,
        trend_tp_mult=4.0, trend_sl_mult=2.5
    )
    for t in trades_e4: t["engine"] = "E4_EURUSD_H1_DEC"
    print(f"  [+] Engine 4 generated {len(trades_e4)} trades.")

    # Combine all trades chronologically
    all_trades = trades_e1 + trades_e2 + trades_e3 + trades_e4
    all_trades.sort(key=lambda x: x["date"])

    pnls = np.array([t["pnl"] for t in all_trades])
    net_profit = float(np.sum(pnls))
    wins = pnls[pnls > 0]
    losses = pnls[pnls < 0]
    gross_win = float(np.sum(wins))
    gross_loss = float(abs(np.sum(losses)))
    pf = float(gross_win / gross_loss)
    win_rate = float(len(wins) / len(pnls) * 100.0)

    equity = np.cumsum(pnls)
    peak = np.maximum.accumulate(equity)
    dd = peak - equity
    max_dd = float(np.max(dd))
    romad = float(net_profit / max_dd)

    df_comb = pd.DataFrame(all_trades)
    df_comb["month"] = df_comb["month"].astype(int)
    monthly_pnl = df_comb.groupby("month")["pnl"].sum().to_dict()

    all_months = []
    for y in range(2020, 2026):
        for m in range(1, 13):
            all_months.append(y * 100 + m)

    monthly_summary = {m: round(monthly_pnl.get(m, 0.0), 2) for m in all_months}
    pos_months = sum(1 for m in all_months if monthly_summary[m] > 0.0)
    mcr = float(round(pos_months / len(all_months) * 100.0, 2))

    df_comb["year"] = pd.to_datetime(df_comb["date"]).dt.year
    annual = df_comb.groupby("year")["pnl"].sum().to_dict()

    champion = {
        "strategy": "Strategy 37: Quad-Engine Institutional Alpha Composite (QE-IAC)",
        "total_trades": len(all_trades),
        "net_profit": round(net_profit, 2),
        "pf": round(pf, 3),
        "win_rate": round(win_rate, 2),
        "max_dd": round(max_dd, 2),
        "romad": round(romad, 2),
        "mcr": mcr,
        "pos_months": pos_months,
        "total_months": len(all_months),
        "annual_pnl": {y: round(annual.get(y, 0.0), 2) for y in range(2020, 2026)},
        "engine_trades": {
            "E1_GOLD_H1_KAMA": len(trades_e1),
            "E2_GOLD_H1_VORTEX": len(trades_e2),
            "E3_GOLD_M15_SVE": len(trades_e3),
            "E4_EURUSD_H1_DEC": len(trades_e4)
        },
        "monthly_summary": monthly_summary
    }

    champ_path = os.path.join(args.out_dir, "strategy_37_champion.json")
    with open(champ_path, "w") as f:
        json.dump(champion, f, indent=2)

    print("\n" + "="*80)
    print("STRATEGY 37: QUAD-ENGINE INSTITUTIONAL ALPHA COMPOSITE (QE-IAC) RESULTS")
    print("="*80)
    print(f"Total Portfolio Trades: {champion['total_trades']}")
    print(f"Combined Net Profit: ${champion['net_profit']:,.2f}")
    print(f"Portfolio Profit Factor (PF): {champion['pf']}  <-- MANDATE (PF >= 1.50+)")
    print(f"Win Rate: {champion['win_rate']}%")
    print(f"Max Drawdown: ${champion['max_dd']:,.2f}")
    print(f"Return on Max DD (RoMaD): {champion['romad']}x")
    print(f"Monthly Consistency Ratio (MCR): {champion['mcr']}% ({champion['pos_months']}/72 months profitable)")
    print("-" * 80)
    print("Annual Performance Breakdown (2020 - 2025):")
    for y in sorted(champion['annual_pnl'].keys()):
        print(f"  {y}: ${champion['annual_pnl'][y]:+,.2f}")
    print("-" * 80)
    print("Engine Trade Counts:")
    for eng, count in champion['engine_trades'].items():
        print(f"  {eng}: {count} trades")
    print(f"Execution Time: {time.time() - t_start:.2f}s")
    print("="*80)

if __name__ == "__main__":
    main()
