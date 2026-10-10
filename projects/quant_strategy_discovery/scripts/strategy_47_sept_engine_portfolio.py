#!/usr/bin/env python3
"""
===============================================================================
STRATEGY 47: SEPT-ENGINE SUPREME INSTITUTIONAL COMPOSITE (SE-SSIC)
===============================================================================
Assets & Engines:
  - Engine 1: Gold H1 KAMA Dynamic Efficiency (S36, Single PF 2.715)
  - Engine 2: Gold H1 HMA-CMO Velocity (S38, Single PF 2.375, DD $866)
  - Engine 3: Gold H1 Vortex Velocity Breakout (S35, Single PF 2.232)
  - Engine 4: Gold M15 Asian Range Breakout Expansion (S42, Single PF 1.817)
  - Engine 5: Gold M15 Fractal Expansion SVE (S30, Single PF 1.352)
  - Engine 6: EURUSD H1 Macro Momentum DEC (S31, Single PF 1.214)
  - Engine 7: Gold H1 Supertrend Dynamic Trailing (S45, Single PF 1.444)

Horizon: 2020-01-01 to 2025-12-30 (72 Calendar Months)
Objective: Cross $55k+ Net Profit, Maintain Portfolio PF >= 1.95+, Target MCR >= 70%+.
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
from strategy_42_asian_breakout_expansion_sweep import simulate_asian_breakout_expansion
from strategy_45_gold_h1_supertrend_trailing_sweep import simulate_supertrend_trailing, compute_supertrend

def main():
    parser = argparse.ArgumentParser(description="Evaluate Strategy 47: Sept-Engine Portfolio")
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

    g_h1_opens = df_gold_h1["open"].values.astype(np.float64)
    g_h1_highs = df_gold_h1["high"].values.astype(np.float64)
    g_h1_lows = df_gold_h1["low"].values.astype(np.float64)
    g_h1_closes = df_gold_h1["close"].values.astype(np.float64)
    g_h1_dates = df_gold_h1.index
    g_h1_months = (g_h1_dates.year.values * 100 + g_h1_dates.month.values).astype(np.int32)

    atr14_gh1 = atr_kama(g_h1_highs, g_h1_lows, g_h1_closes, 14)
    atr10_gh1 = atr_kama(g_h1_highs, g_h1_lows, g_h1_closes, 10)
    ema50_gh1 = ema_kama(g_h1_closes, 50)
    ema200_gh1 = ema_kama(g_h1_closes, 200)
    kfd24_gh1 = kfd_kama(g_h1_closes, atr14_gh1, 24)

    # --- ENGINE 1: Gold H1 KAMA (PF 2.715) ---
    print("[*] Simulating Engine 1: Gold H1 KAMA...")
    kama10, er10, slope10 = compute_kama(g_h1_closes, n_period=10)
    trades_e1 = simulate_kama_strategy(
        opens=g_h1_opens, highs=g_h1_highs, lows=g_h1_lows, closes=g_h1_closes,
        atr14=atr14_gh1, ema200=ema200_gh1, kfd=kfd24_gh1,
        kama=kama10, er=er10, slope=slope10, months=g_h1_months, dates=g_h1_dates,
        er_threshold=0.45, kfd_thresh=1.35, use_kfd=True,
        monthly_profit_lock=250.0, monthly_loss_breaker=250.0,
        defensive_thresh=120.0, defensive_lot_mult=0.25,
        trend_tp_mult=4.0, trend_sl_mult=2.0
    )

    # --- ENGINE 2: Gold H1 HMA-CMO (PF 2.375) ---
    print("[*] Simulating Engine 2: Gold H1 HMA-CMO...")
    hma16_gh1 = compute_hma(g_h1_closes, period=16)
    cmo14_gh1 = compute_cmo(g_h1_closes, period=14)
    trades_e2 = simulate_hma_cmo_strategy(
        opens=g_h1_opens, highs=g_h1_highs, lows=g_h1_lows, closes=g_h1_closes,
        atr14=atr14_gh1, ema200=ema200_gh1, kfd=kfd24_gh1,
        hma=hma16_gh1, cmo=cmo14_gh1, months=g_h1_months, dates=g_h1_dates,
        use_channel=True, cmo_threshold=20.0, use_kfd=True, kfd_thresh=1.35,
        monthly_profit_lock=200.0, monthly_loss_breaker=250.0,
        defensive_thresh=120.0, defensive_lot_mult=0.25,
        trend_tp_mult=4.0, trend_sl_mult=2.5
    )

    # --- ENGINE 3: Gold H1 Vortex (PF 2.232) ---
    print("[*] Simulating Engine 3: Gold H1 Vortex...")
    vip14_gh1, vin14_gh1 = compute_vortex_indicator(g_h1_highs, g_h1_lows, g_h1_closes, period=14)
    trades_e3 = simulate_vortex_strategy(
        opens=g_h1_opens, highs=g_h1_highs, lows=g_h1_lows, closes=g_h1_closes,
        atr14=atr14_gh1, ema200=ema200_gh1, kfd=kfd24_gh1,
        vip=vip14_gh1, vin=vin14_gh1, months=g_h1_months, dates=g_h1_dates,
        vortex_diff_thresh=0.20, use_kfd=True, kfd_thresh=1.35,
        monthly_profit_lock=250.0, monthly_loss_breaker=250.0,
        defensive_thresh=120.0, defensive_lot_mult=0.25,
        trend_tp_mult=4.0, trend_sl_mult=2.0
    )

    # --- ENGINE 4: Gold M15 Asian Breakout Expansion (PF 1.817) ---
    print("[*] Simulating Engine 4: Gold M15 Asian Breakout Expansion...")
    trades_e4 = simulate_asian_breakout_expansion(
        df_m15=df_gold_m15,
        buffer_atr_mult=0.4,
        sl_mult=1.5,
        tp_mult=3.5,
        monthly_profit_lock=250.0,
        monthly_loss_breaker=250.0,
        defensive_thresh=120.0,
        defensive_lot_mult=0.25
    )

    # --- ENGINE 5: Gold M15 SVE Fractal (PF 1.352) ---
    print("[*] Simulating Engine 5: Gold M15 SVE Fractal...")
    trades_e5 = simulate_mfe_sve(
        df_m15=df_gold_m15,
        profit_lock=250.0,
        loss_breaker=250.0,
        defensive_thresh=120.0,
        defensive_mult=0.25
    )

    # --- ENGINE 6: EURUSD H1 Macro Momentum DEC (PF 1.214) ---
    print("[*] Simulating Engine 6: EURUSD H1 DEC...")
    e_h1_opens = df_eur_h1["open"].values.astype(np.float64)
    e_h1_highs = df_eur_h1["high"].values.astype(np.float64)
    e_h1_lows = df_eur_h1["low"].values.astype(np.float64)
    e_h1_closes = df_eur_h1["close"].values.astype(np.float64)
    e_h1_dates = df_eur_h1.index
    e_h1_months = (e_h1_dates.year.values * 100 + e_h1_dates.month.values).astype(np.int32)
    atr14_eh1 = atr_eur(e_h1_highs, e_h1_lows, e_h1_closes, 14)
    ema21_eh1 = ema_eur(e_h1_closes, 21)
    ema55_eh1 = ema_eur(e_h1_closes, 55)
    ema200_eh1 = ema_eur(e_h1_closes, 200)

    trades_e6 = simulate_eur_h1(
        opens=e_h1_opens, highs=e_h1_highs, lows=e_h1_lows, closes=e_h1_closes,
        atr14=atr14_eh1, ema21=ema21_eh1, ema55=ema55_eh1, ema200=ema200_eh1,
        months=e_h1_months, dates=e_h1_dates,
        tp_mult=2.5, sl_mult=1.5,
        monthly_profit_lock=150.0, monthly_loss_breaker=150.0,
        defensive_thresh=80.0, defensive_lot_mult=0.25
    )

    # --- ENGINE 7: Gold H1 Supertrend Trailing (PF 1.444) ---
    print("[*] Simulating Engine 7: Gold H1 Supertrend Trailing...")
    st_val, trend_val, fub, flb = compute_supertrend(g_h1_highs, g_h1_lows, g_h1_closes, atr10_gh1, multiplier=4.0)
    trades_e7 = simulate_supertrend_trailing(
        opens=g_h1_opens, highs=g_h1_highs, lows=g_h1_lows, closes=g_h1_closes,
        final_ub=fub, final_lb=flb, trend=trend_val, ema200=ema200_gh1,
        kfd=kfd24_gh1, months=g_h1_months, dates=g_h1_dates,
        use_kfd=False, kfd_thresh=1.40,
        monthly_profit_lock=250.0, monthly_loss_breaker=250.0,
        defensive_thresh=120.0, defensive_lot_mult=0.25
    )

    # Assign engine labels
    for t in trades_e1: t["engine"] = "E1_KAMA_H1"
    for t in trades_e2: t["engine"] = "E2_HMA_H1"
    for t in trades_e3: t["engine"] = "E3_VORTEX_H1"
    for t in trades_e4: t["engine"] = "E4_ASIAN_M15"
    for t in trades_e5: t["engine"] = "E5_SVE_M15"
    for t in trades_e6: t["engine"] = "E6_EUR_H1"
    for t in trades_e7: t["engine"] = "E7_SUPERTREND_H1"

    all_trades = sorted(trades_e1 + trades_e2 + trades_e3 + trades_e4 + trades_e5 + trades_e6 + trades_e7, key=lambda x: x["date"])

    def evaluate_composite(trades, label="SEPT-ENGINE COMPOSITE"):
        df_tr = pd.DataFrame(trades)
        pnls = df_tr["pnl"].values
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
        romad = float(net_profit / max_dd) if max_dd > 0 else 0.0

        df_tr["month"] = df_tr["month"].astype(int)
        monthly = df_tr.groupby("month")["pnl"].sum().to_dict()

        all_months = []
        for y in range(2020, 2026):
            for m in range(1, 13):
                all_months.append(y * 100 + m)

        m_series = {m: round(monthly.get(m, 0.0), 2) for m in all_months}
        pos_m = sum(1 for m in all_months if m_series[m] > 0.0)
        neg_m = sum(1 for m in all_months if m_series[m] < 0.0)
        zero_m = sum(1 for m in all_months if m_series[m] == 0.0)
        mcr = float(round(pos_m / len(all_months) * 100.0, 2))

        return {
            "label": label,
            "total_trades": len(trades),
            "net_profit": round(net_profit, 2),
            "pf": round(pf, 3),
            "win_rate": round(win_rate, 2),
            "max_dd": round(max_dd, 2),
            "romad": round(romad, 2),
            "mcr": mcr,
            "pos_months": pos_m,
            "neg_months": neg_m,
            "zero_months": zero_m,
            "total_months": len(all_months)
        }

    m_all = evaluate_composite(all_trades, "SEPT-ENGINE SUPREME INSTITUTIONAL COMPOSITE (SE-SSIC)")
    m_e1 = evaluate_composite(trades_e1, "E1: Gold H1 KAMA Efficiency")
    m_e2 = evaluate_composite(trades_e2, "E2: Gold H1 HMA-CMO Velocity")
    m_e3 = evaluate_composite(trades_e3, "E3: Gold H1 Vortex Velocity")
    m_e4 = evaluate_composite(trades_e4, "E4: Gold M15 Asian Breakout")
    m_e5 = evaluate_composite(trades_e5, "E5: Gold M15 SVE Fractal")
    m_e6 = evaluate_composite(trades_e6, "E6: EURUSD H1 DEC Momentum")
    m_e7 = evaluate_composite(trades_e7, "E7: Gold H1 Supertrend Trailing")

    print("\n" + "=" * 90)
    print("STRATEGY 47: SEPT-ENGINE SUPREME INSTITUTIONAL COMPOSITE (SE-SSIC) AUDIT")
    print("=" * 90)
    print(f"{'Engine / Ensemble':<45} | {'Trades':<7} | {'Net Profit':<12} | {'PF':<6} | {'Max DD':<9} | {'RoMaD':<6} | {'MCR'}")
    print("-" * 90)
    for m in [m_e1, m_e2, m_e3, m_e4, m_e5, m_e6, m_e7]:
        print(f"{m['label']:<45} | {m['total_trades']:<7} | ${m['net_profit']:<11,.2f} | {m['pf']:<6.3f} | ${m['max_dd']:<8,.2f} | {m['romad']:<6.2f} | {m['mcr']:.1f}% ({m['pos_months']}/72)")
    print("=" * 90)
    print(f"{m_all['label']:<45} | {m_all['total_trades']:<7} | ${m_all['net_profit']:<11,.2f} | {m_all['pf']:<6.3f} | ${m_all['max_dd']:<8,.2f} | {m_all['romad']:<6.2f} | {m_all['mcr']:.1f}% ({m_all['pos_months']}/72)")
    print("=" * 90)

    # Save champion JSON
    champ = {
        "strategy_id": "STRATEGY_47",
        "strategy_name": "Sept-Engine Supreme Institutional Composite (SE-SSIC)",
        "engines": [m_e1, m_e2, m_e3, m_e4, m_e5, m_e6, m_e7],
        "portfolio_metrics": m_all,
        "runtime_seconds": round(time.time() - t_start, 2)
    }

    out_json = os.path.join(args.out_dir, "strategy_47_champion.json")
    with open(out_json, "w") as f:
        json.dump(champ, f, indent=2)
    print(f"[+] Saved Strategy 47 results to {out_json}")

if __name__ == "__main__":
    main()
