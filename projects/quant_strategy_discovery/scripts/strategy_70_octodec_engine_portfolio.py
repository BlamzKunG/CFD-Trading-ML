#!/usr/bin/env python3
"""
===============================================================================
STRATEGY 70: OCTODEC-ENGINE SUPREME INSTITUTIONAL COMPOSITE (OE-STIC)
===============================================================================
Assets & Engines (18 Asynchronous Strategy Units):
  - Engine 1:  Gold H1 KAMA Dynamic Efficiency (S36, Single PF 2.715)
  - Engine 2:  Gold H1 HMA-CMO Velocity (S38, Single PF 2.375, DD $866)
  - Engine 3:  Gold H1 Vortex Velocity Breakout (S35, Single PF 2.232)
  - Engine 4:  Gold M15 Asian Range Breakout Expansion (S42, Single PF 1.817)
  - Engine 5:  Gold M15 Fractal Expansion SVE (S30, Single PF 1.589)
  - Engine 6:  EURUSD H1 Macro Momentum DEC (S31, Single PF 1.315)
  - Engine 7:  Gold H1 Supertrend Dynamic Trailing (S45, Single PF 1.444)
  - Engine 8:  Gold H1 CCI Momentum & Fractal Expansion (S51, Single PF 1.151, DD $1,330)
  - Engine 9:  Gold H1 Relative Volatility Index Expansion (S53, Single PF 1.568, DD $996)
  - Engine 10: Gold H1 Market Structure Break of Structure (S55, Single PF 1.560, DD $1,259)
  - Engine 11: Gold H1 Elder's Force Index Dynamic Volume Breakout (S58, Single PF 1.476, MCR 62.5%)
  - Engine 12: Gold H1 Williams %R Momentum & Volatility Pullback (S59, Single PF 1.496)
  - Engine 13: Gold H1 McGinley Dynamic Adaptive Trend (S61, Single PF 1.641, DD $920, MCR 68.1%)
  - Engine 14: Gold H1 Schaff Trend Cycle Momentum & Fractal (S62, Single PF 1.573, DD $1,277)
  - Engine 15: Gold H1 DeMarker Dynamic Exhaustion (S64, Single PF 1.451, Win 51.1%)
  - Engine 16: Gold H1 Chande Kroll Stop Volatility Breakout (S65, Single PF 1.337, DD $866-$2.7k)
  - Engine 17: Gold H1 Linear Regression Slope & R² (S67, Single PF 2.095, Net +$9.0k, DD $993)
  - Engine 18: Gold H1 Coppock Curve Momentum Inflection (S69, Single PF 1.450, Net +$7.0k, Win 50.0%)

Horizon: 2020-01-01 to 2025-12-30 (72 Calendar Months)
Objective: Historic 18-Engine Grand Institutional Milestone: Shatter $112,000+ Net Profit Barrier,
           Cross 3,400 Total Executed Trades, Maintain Portfolio PF >= 1.63+, RoMaD >= 20.0x.
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
from strategy_51_gold_h1_cci_momentum_sweep import compute_cci
from strategy_53_gold_h1_rvi_volatility_sweep import compute_rvi
from strategy_55_gold_h1_bos_structure_sweep import simulate_bos_strategy, compute_confirmed_swing_levels
from strategy_58_gold_h1_elder_force_index_sweep import simulate_efi_strategy, compute_elder_force_index, compute_katz_fractal_dimension as kfd_standard
from strategy_59_gold_h1_williams_r_pullback_sweep import simulate_wpr_strategy, compute_williams_r
from strategy_61_gold_h1_mcginley_dynamic_sweep import simulate_mgd_strategy, compute_mcginley_dynamic
from strategy_62_gold_h1_schaff_trend_cycle_sweep import simulate_stc_strategy, compute_schaff_trend_cycle
from strategy_64_gold_h1_demarker_exhaustion_sweep import simulate_demarker_strategy, compute_demarker
from strategy_65_gold_h1_chande_kroll_stop_sweep import simulate_cks_strategy, compute_chande_kroll_stop
from strategy_67_gold_h1_linear_regression_slope_sweep import simulate_lrs_strategy, compute_linear_regression_metrics
from strategy_69_gold_h1_coppock_curve_sweep import simulate_ccmi_strategy, compute_coppock_curve

def main():
    parser = argparse.ArgumentParser(description="Evaluate Strategy 70: Octodec-Engine Portfolio")
    parser.add_argument("--gold_data", type=str, default="/mnt/sdcard/Download/EA/XAUUSD_M1.csv.gz")
    parser.add_argument("--eur_data", type=str, default="/mnt/sdcard/Download/EA/EURUSD_M1.csv.gz")
    parser.add_argument("--out_dir", type=str, default="projects/quant_strategy_discovery/results")
    args = parser.parse_args()

    os.makedirs(args.out_dir, exist_ok=True)
    t_start = time.time()

    print("[*] Loading Gold raw M1 data with tick_volume...")
    df_gold = pd.read_csv(args.gold_data, usecols=["datetime", "open", "high", "low", "close", "tick_volume"])
    df_gold["datetime"] = pd.to_datetime(df_gold["datetime"])
    df_gold.set_index("datetime", inplace=True)
    df_gold.sort_index(inplace=True)

    print("[*] Resampling Gold H1 & M15...")
    df_gold_h1 = df_gold.resample("1h").agg({
        "open": "first", "high": "max", "low": "min", "close": "last", "tick_volume": "sum"
    }).dropna()
    df_gold_m15 = df_gold.resample("15min").agg({
        "open": "first", "high": "max", "low": "min", "close": "last"
    }).dropna()

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
    g_h1_vols = df_gold_h1["tick_volume"].values.astype(np.float64)
    g_h1_dates = df_gold_h1.index
    g_h1_months = (g_h1_dates.year.values * 100 + g_h1_dates.month.values).astype(np.int32)

    atr14_gh1 = atr_kama(g_h1_highs, g_h1_lows, g_h1_closes, 14)
    atr10_gh1 = atr_kama(g_h1_highs, g_h1_lows, g_h1_closes, 10)
    ema50_gh1 = ema_kama(g_h1_closes, 50)
    ema200_gh1 = ema_kama(g_h1_closes, 200)
    kfd24_gh1 = kfd_kama(g_h1_closes, atr14_gh1, 24)
    kfd24_std = kfd_standard(g_h1_closes, atr14_gh1, 24)

    # --- ENGINE 1: Gold H1 KAMA (PF 2.715) ---
    print("[*] Simulating Engine 1: Gold H1 KAMA...")
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

    # --- ENGINE 2: Gold H1 HMA-CMO Velocity (PF 2.375) ---
    print("[*] Simulating Engine 2: Gold H1 HMA-CMO...")
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
    for t in trades_e2: t["engine"] = "E2_GOLD_H1_HMA_CMO"

    # --- ENGINE 3: Gold H1 Vortex Velocity (PF 1.704) ---
    print("[*] Simulating Engine 3: Gold H1 Vortex Velocity...")
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
        trend_tp_mult=4.0, trend_sl_mult=2.0
    )
    for t in trades_e3: t["engine"] = "E3_GOLD_H1_VORTEX"

    # --- Gold M15 Setup ---
    g_m15_opens = df_gold_m15["open"].values.astype(np.float64)
    g_m15_highs = df_gold_m15["high"].values.astype(np.float64)
    g_m15_lows = df_gold_m15["low"].values.astype(np.float64)
    g_m15_closes = df_gold_m15["close"].values.astype(np.float64)
    g_m15_dates = df_gold_m15.index
    g_m15_months = (g_m15_dates.year.values * 100 + g_m15_dates.month.values).astype(np.int32)
    g_m15_hours = g_m15_dates.hour.values.astype(np.int32)
    g_m15_days = (g_m15_dates.year.values * 10000 + g_m15_dates.month.values * 100 + g_m15_dates.day.values).astype(np.int32)

    atr14_gm15 = atr_kama(g_m15_highs, g_m15_lows, g_m15_closes, 14)
    ema50_gm15 = ema_kama(g_m15_closes, 50)
    ema200_gm15 = ema_kama(g_m15_closes, 200)
    kfd32_gm15 = kfd_kama(g_m15_closes, atr14_gm15, 32)

    # --- ENGINE 4: Gold M15 Asian Breakout (PF 1.817) ---
    print("[*] Simulating Engine 4: Gold M15 Asian Breakout...")
    trades_e4 = simulate_asian_breakout_expansion(
        opens=g_m15_opens, highs=g_m15_highs, lows=g_m15_lows, closes=g_m15_closes,
        atr14=atr14_gm15, ema50=ema50_gm15, ema200=ema200_gm15, kfd=kfd32_gm15,
        hours=g_m15_hours, days=g_m15_days, months=g_m15_months, dates=g_m15_dates,
        asian_end_hour=7, exec_start_hour=8, exec_end_hour=16,
        breakout_atr_buffer=0.4,
        use_kfd=True, kfd_thresh=1.40,
        monthly_profit_lock=200.0, monthly_loss_breaker=250.0,
        defensive_thresh=120.0, defensive_lot_mult=0.25,
        trend_tp_mult=4.5, trend_sl_mult=2.2
    )
    for t in trades_e4: t["engine"] = "E4_GOLD_M15_ARBE"

    # --- ENGINE 5: Gold M15 SVE Fractal (PF 1.589) ---
    print("[*] Simulating Engine 5: Gold M15 SVE Fractal...")
    h_lb16_m15 = pd.Series(g_m15_highs).rolling(16).max().shift(1).fillna(999999.0).values
    l_lb16_m15 = pd.Series(g_m15_lows).rolling(16).min().shift(1).fillna(0.0).values
    vr14_gm15 = pd.Series(atr14_gm15).rolling(14).mean().values
    vr14_gm15 = np.where(vr14_gm15 <= 0, 1e-4, atr14_gm15 / vr14_gm15)
    trades_e5 = simulate_mfe_sve(
        opens=g_m15_opens, highs=g_m15_highs, lows=g_m15_lows, closes=g_m15_closes,
        atr14=atr14_gm15, ema50=ema50_gm15, ema200=ema200_gm15,
        h_lookback=h_lb16_m15, l_lookback=l_lb16_m15,
        kfd=kfd32_gm15, vr=vr14_gm15,
        months=g_m15_months, dates=g_m15_dates,
        kfd_thresh=1.35, vr_thresh=1.2,
        monthly_profit_lock=200.0, monthly_loss_breaker=250.0,
        defensive_thresh=120.0, defensive_lot_mult=0.25,
        trend_tp_mult=4.5, trend_sl_mult=2.0
    )
    for t in trades_e5: t["engine"] = "E5_GOLD_M15_SVE"

    # --- EURUSD H1 Setup ---
    e_h1_opens = df_eur_h1["open"].values.astype(np.float64)
    e_h1_highs = df_eur_h1["high"].values.astype(np.float64)
    e_h1_lows = df_eur_h1["low"].values.astype(np.float64)
    e_h1_closes = df_eur_h1["close"].values.astype(np.float64)
    e_h1_dates = df_eur_h1.index
    e_h1_months = (e_h1_dates.year.values * 100 + e_h1_dates.month.values).astype(np.int32)

    atr14_eh1 = atr_eur(e_h1_highs, e_h1_lows, e_h1_closes, 14)
    ema20_eh1 = ema_eur(e_h1_closes, 20)
    ema50_eh1 = ema_eur(e_h1_closes, 50)
    ema200_eh1 = ema_eur(e_h1_closes, 200)
    kfd24_eh1 = kfd_kama(e_h1_closes, atr14_eh1, 24)

    # --- ENGINE 6: EURUSD H1 DEC (PF 1.315) ---
    print("[*] Simulating Engine 6: EURUSD H1 DEC...")
    trades_e6 = simulate_eur_h1(
        opens=e_h1_opens, highs=e_h1_highs, lows=e_h1_lows, closes=e_h1_closes,
        atr14=atr14_eh1, ema20=ema20_eh1, ema50=ema50_eh1, ema200=ema200_eh1, kfd=kfd24_eh1,
        months=e_h1_months, dates=e_h1_dates,
        kfd_thresh=1.35, tp_mult=4.0, sl_mult=2.0,
        monthly_profit_lock=150.0, monthly_loss_breaker=150.0,
        defensive_thresh=80.0, defensive_lot_mult=0.25
    )
    for t in trades_e6: t["engine"] = "E6_EUR_H1_DEC"

    # --- ENGINE 7: Gold H1 Supertrend Trailing (PF 1.444) ---
    print("[*] Simulating Engine 7: Gold H1 Supertrend Trailing...")
    st_dir, st_val = compute_supertrend(g_h1_highs, g_h1_lows, g_h1_closes, period=10, multiplier=3.0)
    trades_e7 = simulate_supertrend_trailing(
        opens=g_h1_opens, highs=g_h1_highs, lows=g_h1_lows, closes=g_h1_closes,
        atr14=atr14_gh1, ema200=ema200_gh1, kfd=kfd24_gh1,
        st_direction=st_dir, st_value=st_val,
        months=g_h1_months, dates=g_h1_dates,
        use_kfd=True, kfd_thresh=1.40,
        monthly_profit_lock=250.0, monthly_loss_breaker=250.0,
        defensive_thresh=120.0, defensive_lot_mult=0.25,
        tp_mult=4.5, sl_mult=2.5, trailing_activation_r=2.0
    )
    for t in trades_e7: t["engine"] = "E7_GOLD_H1_MST"

    # --- ENGINE 8: Gold H1 CCI Momentum & Fractal (PF 1.151) ---
    print("[*] Simulating Engine 8: Gold H1 CCI Momentum...")
    cci20 = compute_cci(g_h1_highs, g_h1_lows, g_h1_closes, period=20)
    trades_e8 = []
    pos8 = 0; ent_p8 = 0.0; sl_p8 = 0.0; tp_p8 = 0.0; ent_i8 = 0
    cur_m8 = g_h1_months[0]; m_pnl8 = 0.0; lock8 = False
    for i in range(50, len(g_h1_closes) - 1):
        if g_h1_months[i] != cur_m8:
            cur_m8 = g_h1_months[i]; m_pnl8 = 0.0; lock8 = False
        if pos8 != 0:
            h = g_h1_highs[i]; l = g_h1_lows[i]; hit_tp = False; hit_sl = False
            if pos8 == 1:
                if l <= sl_p8: hit_sl = True
                elif h >= tp_p8: hit_tp = True
            elif pos8 == -1:
                if h >= sl_p8: hit_sl = True
                elif l <= tp_p8: hit_tp = True
            if hit_sl and hit_tp: hit_tp = False; hit_sl = True
            if hit_sl or hit_tp:
                exit_p = tp_p8 if hit_tp else sl_p8
                pnl = ((exit_p - ent_p8) if pos8 == 1 else (ent_p8 - exit_p)) * 10.0 - 3.10
                m_pnl8 += pnl
                trades_e8.append({"pnl": round(pnl, 2), "date": g_h1_dates[i], "engine": "E8_GOLD_H1_CCI", "month": cur_m8})
                pos8 = 0
                if m_pnl8 >= 200.0 or m_pnl8 <= -250.0: lock8 = True
        if pos8 == 0 and not lock8:
            atr = atr14_gh1[i]
            if atr < 0.5: continue
            if kfd24_gh1[i] <= 1.40:
                if cci20[i] > 100.0 and cci20[i-1] <= 100.0 and g_h1_closes[i] > ema200_gh1[i]:
                    pos8 = 1; ent_i8 = i + 1; ent_p8 = g_h1_opens[i+1]
                    sl_p8 = ent_p8 - 2.0 * atr; tp_p8 = ent_p8 + 4.5 * atr
                elif cci20[i] < -100.0 and cci20[i-1] >= -100.0 and g_h1_closes[i] < ema200_gh1[i]:
                    pos8 = -1; ent_i8 = i + 1; ent_p8 = g_h1_opens[i+1]
                    sl_p8 = ent_p8 + 2.0 * atr; tp_p8 = ent_p8 - 4.5 * atr

    # --- ENGINE 9: Gold H1 RVI Volatility (PF 1.568) ---
    print("[*] Simulating Engine 9: Gold H1 RVI Volatility...")
    rvi14, sig14 = compute_rvi(g_h1_opens, g_h1_highs, g_h1_lows, g_h1_closes, period=14)
    trades_e9 = []
    pos9 = 0; ent_p9 = 0.0; sl_p9 = 0.0; tp_p9 = 0.0; ent_i9 = 0
    cur_m9 = g_h1_months[0]; m_pnl9 = 0.0; lock9 = False
    for i in range(50, len(g_h1_closes) - 1):
        if g_h1_months[i] != cur_m9:
            cur_m9 = g_h1_months[i]; m_pnl9 = 0.0; lock9 = False
        if pos9 != 0:
            h = g_h1_highs[i]; l = g_h1_lows[i]; hit_tp = False; hit_sl = False
            if pos9 == 1:
                if l <= sl_p9: hit_sl = True
                elif h >= tp_p9: hit_tp = True
            elif pos9 == -1:
                if h >= sl_p9: hit_sl = True
                elif l <= tp_p9: hit_tp = True
            if hit_sl and hit_tp: hit_tp = False; hit_sl = True
            if hit_sl or hit_tp:
                exit_p = tp_p9 if hit_tp else sl_p9
                pnl = ((exit_p - ent_p9) if pos9 == 1 else (ent_p9 - exit_p)) * 10.0 - 3.10
                m_pnl9 += pnl
                trades_e9.append({"pnl": round(pnl, 2), "date": g_h1_dates[i], "engine": "E9_GOLD_H1_RVI", "month": cur_m9})
                pos9 = 0
                if m_pnl9 >= 200.0 or m_pnl9 <= -250.0: lock9 = True
        if pos9 == 0 and not lock9:
            atr = atr14_gh1[i]
            if atr < 0.5: continue
            if kfd24_gh1[i] <= 1.40:
                if rvi14[i] > sig14[i] and rvi14[i-1] <= sig14[i-1] and g_h1_closes[i] > ema200_gh1[i]:
                    pos9 = 1; ent_i9 = i + 1; ent_p9 = g_h1_opens[i+1]
                    sl_p8 = ent_p9 - 2.0 * atr; tp_p9 = ent_p9 + 4.5 * atr
                elif rvi14[i] < sig14[i] and rvi14[i-1] >= sig14[i-1] and g_h1_closes[i] < ema200_gh1[i]:
                    pos9 = -1; ent_i9 = i + 1; ent_p9 = g_h1_opens[i+1]
                    sl_p9 = ent_p9 + 2.0 * atr; tp_p9 = ent_p9 - 4.5 * atr

    # --- ENGINE 10: Gold H1 Market Structure BOS (PF 1.560) ---
    print("[*] Simulating Engine 10: Gold H1 Market Structure BOS...")
    swing_highs, swing_lows = compute_confirmed_swing_levels(g_h1_highs, g_h1_lows, swing_left=5, swing_right=2)
    raw_trades_e10 = simulate_bos_strategy(
        opens=g_h1_opens, highs=g_h1_highs, lows=g_h1_lows, closes=g_h1_closes,
        atr14=atr14_gh1, ema200=ema200_gh1, kfd=kfd24_std,
        swing_highs=swing_highs, swing_lows=swing_lows,
        months=g_h1_months, dates=g_h1_dates,
        use_kfd=True, kfd_thresh=1.40,
        monthly_profit_lock=250.0, monthly_loss_breaker=250.0,
        defensive_thresh=120.0, defensive_lot_mult=0.25,
        tp_mult=4.5, sl_mult=2.0
    )
    trades_e10 = []
    for t in raw_trades_e10:
        trades_e10.append({
            "pnl": t["pnl"],
            "date": pd.to_datetime(t["exit_date"]),
            "engine": "E10_GOLD_H1_BOS",
            "month": t["month"]
        })

    # --- ENGINE 11: Gold H1 Elder's Force Index (PF 1.476) ---
    print("[*] Simulating Engine 11: Gold H1 Elder Force Index...")
    efi13 = compute_elder_force_index(g_h1_closes, g_h1_vols, period=13)
    raw_trades_e11 = simulate_efi_strategy(
        opens=g_h1_opens, highs=g_h1_highs, lows=g_h1_lows, closes=g_h1_closes,
        atr14=atr14_gh1, ema200=ema200_gh1, kfd=kfd24_std,
        efi=efi13, months=g_h1_months, dates=g_h1_dates,
        use_kfd=True, kfd_thresh=1.40,
        monthly_profit_lock=200.0, monthly_loss_breaker=250.0,
        defensive_thresh=120.0, defensive_lot_mult=0.25,
        tp_mult=4.0, sl_mult=2.0
    )
    trades_e11 = []
    for t in raw_trades_e11:
        trades_e11.append({
            "pnl": t["pnl"],
            "date": pd.to_datetime(t["exit_date"]),
            "engine": "E11_GOLD_H1_EFI",
            "month": t["month"]
        })

    # --- ENGINE 12: Gold H1 Williams %R Pullback (PF 1.496) ---
    print("[*] Simulating Engine 12: Gold H1 Williams %R Pullback...")
    wpr14 = compute_williams_r(g_h1_highs, g_h1_lows, g_h1_closes, period=14)
    raw_trades_e12 = simulate_wpr_strategy(
        opens=g_h1_opens, highs=g_h1_highs, lows=g_h1_lows, closes=g_h1_closes,
        atr14=atr14_gh1, ema50=ema50_gh1, ema200=ema200_gh1, kfd=kfd24_std,
        wpr=wpr14, months=g_h1_months, dates=g_h1_dates,
        use_kfd=True, kfd_thresh=1.35,
        trend_filter="ema50",
        ob_level=-20.0, os_level=-80.0,
        tp_mult=4.0, sl_mult=2.0,
        monthly_profit_lock=200.0, monthly_loss_breaker=250.0
    )
    trades_e12 = []
    for t in raw_trades_e12:
        trades_e12.append({
            "pnl": t["pnl"],
            "date": pd.to_datetime(t["exit_date"]),
            "engine": "E12_GOLD_H1_WPR",
            "month": t["month"]
        })

    # --- ENGINE 13: Gold H1 McGinley Dynamic Adaptive Trend (PF 1.641) ---
    print("[*] Simulating Engine 13: Gold H1 McGinley Dynamic...")
    mgd14 = compute_mcginley_dynamic(g_h1_closes, period=14, k=0.6)
    raw_trades_e13 = simulate_mgd_strategy(
        opens=g_h1_opens, highs=g_h1_highs, lows=g_h1_lows, closes=g_h1_closes,
        atr14=atr14_gh1, ema200=ema200_gh1, kfd=kfd24_std,
        mgd=mgd14, months=g_h1_months, dates=g_h1_dates,
        use_kfd=True, kfd_thresh=1.40,
        tp_mult=4.5, sl_mult=2.5,
        monthly_profit_lock=250.0, monthly_loss_breaker=250.0
    )
    trades_e13 = []
    for t in raw_trades_e13:
        trades_e13.append({
            "pnl": t["pnl"],
            "date": pd.to_datetime(t["exit_date"]),
            "engine": "E13_GOLD_H1_MGD",
            "month": t["month"]
        })

    # --- ENGINE 14: Gold H1 Schaff Trend Cycle Momentum (PF 1.573) ---
    print("[*] Simulating Engine 14: Gold H1 Schaff Trend Cycle...")
    stc_line = compute_schaff_trend_cycle(g_h1_closes, fast_len=23, slow_len=50, cycle_len=10, smooth=3)
    raw_trades_e14 = simulate_stc_strategy(
        opens=g_h1_opens, highs=g_h1_highs, lows=g_h1_lows, closes=g_h1_closes,
        atr14=atr14_gh1, ema200=ema200_gh1, kfd=kfd24_std,
        stc=stc_line, months=g_h1_months, dates=g_h1_dates,
        use_kfd=True, kfd_thresh=1.40,
        tp_mult=4.0, sl_mult=2.5,
        monthly_profit_lock=250.0, monthly_loss_breaker=250.0
    )
    trades_e14 = []
    for t in raw_trades_e14:
        trades_e14.append({
            "pnl": t["pnl"],
            "date": pd.to_datetime(t["exit_date"]),
            "engine": "E14_GOLD_H1_STC",
            "month": t["month"]
        })

    # --- ENGINE 15: Gold H1 DeMarker Dynamic Exhaustion (PF 1.451) ---
    print("[*] Simulating Engine 15: Gold H1 DeMarker Exhaustion...")
    dem14 = compute_demarker(g_h1_highs, g_h1_lows, period=14)
    raw_trades_e15 = simulate_demarker_strategy(
        opens=g_h1_opens, highs=g_h1_highs, lows=g_h1_lows, closes=g_h1_closes,
        atr14=atr14_gh1, ema50=ema50_gh1, ema200=ema200_gh1, kfd=kfd24_std,
        demarker=dem14, months=g_h1_months, dates=g_h1_dates,
        trend_filter="none",
        use_kfd=True, kfd_thresh=1.40,
        ob_thresh=0.70, os_thresh=0.30,
        tp_mult=4.5, sl_mult=2.0,
        monthly_profit_lock=0.0, monthly_loss_breaker=0.0
    )
    trades_e15 = []
    for t in raw_trades_e15:
        trades_e15.append({
            "pnl": t["pnl"],
            "date": pd.to_datetime(t["exit_date"]),
            "engine": "E15_GOLD_H1_DEM",
            "month": t["month"]
        })

    # --- ENGINE 16: Gold H1 Chande Kroll Stop Volatility Breakout (S65) ---
    print("[*] Simulating Engine 16: Gold H1 Chande Kroll Stop...")
    cks_sl14, cks_ss14 = compute_chande_kroll_stop(g_h1_highs, g_h1_lows, atr14_gh1, p_period=14, mult=2.5, q_period=20)
    raw_trades_e16 = simulate_cks_strategy(
        opens=g_h1_opens, highs=g_h1_highs, lows=g_h1_lows, closes=g_h1_closes,
        atr14=atr14_gh1, ema200=ema200_gh1, kfd=kfd24_std,
        stop_long=cks_sl14, stop_short=cks_ss14,
        months=g_h1_months, dates=g_h1_dates,
        use_kfd=True, kfd_thresh=1.40,
        use_ema200=True,
        tp_mult=5.0, sl_mult=2.5,
        monthly_profit_lock=200.0, monthly_loss_breaker=250.0
    )
    trades_e16 = []
    for t in raw_trades_e16:
        trades_e16.append({
            "pnl": t["pnl"],
            "date": pd.to_datetime(t["exit_date"]),
            "engine": "E16_GOLD_H1_CKS",
            "month": t["month"]
        })

    # --- ENGINE 17: Gold H1 Linear Regression Slope & R² (S67) ---
    print("[*] Simulating Engine 17: Gold H1 Linear Regression Slope...")
    lrs28, r2_28 = compute_linear_regression_metrics(g_h1_closes, period=28)
    raw_trades_e17 = simulate_lrs_strategy(
        opens=g_h1_opens, highs=g_h1_highs, lows=g_h1_lows, closes=g_h1_closes,
        atr14=atr14_gh1, ema200=ema200_gh1, kfd=kfd24_std,
        slopes=lrs28, r2_vals=r2_28,
        months=g_h1_months, dates=g_h1_dates,
        r2_thresh=0.60,
        use_kfd=True, kfd_thresh=1.35,
        use_ema200=True,
        tp_mult=5.0, sl_mult=2.0,
        monthly_profit_lock=250.0, monthly_loss_breaker=250.0
    )
    trades_e17 = []
    for t in raw_trades_e17:
        trades_e17.append({
            "pnl": t["pnl"],
            "date": pd.to_datetime(t["exit_date"]),
            "engine": "E17_GOLD_H1_LRS",
            "month": t["month"]
        })

    # --- ENGINE 18: Gold H1 Coppock Curve Momentum Inflection (S69) ---
    print("[*] Simulating Engine 18: Gold H1 Coppock Curve Momentum Inflection...")
    c_curve69, s_curve69 = compute_coppock_curve(g_h1_closes, r1=6, r2=12, w_len=8, sig_len=5)
    raw_trades_e18 = simulate_ccmi_strategy(
        opens=g_h1_opens, highs=g_h1_highs, lows=g_h1_lows, closes=g_h1_closes,
        atr14=atr14_gh1, ema50=ema50_gh1, ema200=ema200_gh1, kfd=kfd24_std,
        coppock=c_curve69, signal=s_curve69,
        months=g_h1_months, dates=g_h1_dates,
        trigger_mode="inflection", trend_filter="none",
        use_kfd=True, kfd_thresh=1.40,
        tp_mult=3.5, sl_mult=2.5,
        monthly_profit_lock=200.0, monthly_loss_breaker=250.0
    )
    trades_e18 = []
    for t in raw_trades_e18:
        trades_e18.append({
            "pnl": t["pnl"],
            "date": pd.to_datetime(t["exit_date"]),
            "engine": "E18_GOLD_H1_CCMI",
            "month": t["month"]
        })

    all_trades = sorted(
        trades_e1 + trades_e2 + trades_e3 + trades_e4 + trades_e5 + trades_e6 +
        trades_e7 + trades_e8 + trades_e9 + trades_e10 + trades_e11 + trades_e12 +
        trades_e13 + trades_e14 + trades_e15 + trades_e16 + trades_e17 + trades_e18,
        key=lambda x: x["date"]
    )

    def evaluate_composite(trades, label="OCTODEC-ENGINE COMPOSITE"):
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
        max_dd = float(np.max(dd)) if len(dd) > 0 else 1e-4
        romad = float(net_profit / max_dd)

        m_pnl = df_tr.groupby("month")["pnl"].sum()
        pos_m = int((m_pnl > 0).sum())
        total_m = 72
        mcr = float(pos_m / total_m * 100.0)

        return {
            "label": label,
            "total_trades": len(trades),
            "net_profit": round(net_profit, 2),
            "pf": round(pf, 3),
            "win_rate": round(win_rate, 2),
            "max_dd": round(max_dd, 2),
            "romad": round(romad, 2),
            "mcr": round(mcr, 2),
            "pos_months": pos_m,
            "total_months": total_m
        }

    m_e1 = evaluate_composite(trades_e1, "E1: Gold H1 KAMA Efficiency")
    m_e2 = evaluate_composite(trades_e2, "E2: Gold H1 HMA-CMO Velocity")
    m_e3 = evaluate_composite(trades_e3, "E3: Gold H1 Vortex Velocity")
    m_e4 = evaluate_composite(trades_e4, "E4: Gold M15 Asian Breakout")
    m_e5 = evaluate_composite(trades_e5, "E5: Gold M15 SVE Fractal")
    m_e6 = evaluate_composite(trades_e6, "E6: EURUSD H1 DEC Momentum")
    m_e7 = evaluate_composite(trades_e7, "E7: Gold H1 Supertrend Trailing")
    m_e8 = evaluate_composite(trades_e8, "E8: Gold H1 CCI Momentum")
    m_e9 = evaluate_composite(trades_e9, "E9: Gold H1 RVI Volatility")
    m_e10 = evaluate_composite(trades_e10, "E10: Gold H1 Market Structure BOS")
    m_e11 = evaluate_composite(trades_e11, "E11: Gold H1 Elder Force Index")
    m_e12 = evaluate_composite(trades_e12, "E12: Gold H1 Williams %R Pullback")
    m_e13 = evaluate_composite(trades_e13, "E13: Gold H1 McGinley Dynamic Adaptive Trend")
    m_e14 = evaluate_composite(trades_e14, "E14: Gold H1 Schaff Trend Cycle Momentum")
    m_e15 = evaluate_composite(trades_e15, "E15: Gold H1 DeMarker Dynamic Exhaustion")
    m_e16 = evaluate_composite(trades_e16, "E16: Gold H1 Chande Kroll Stop Volatility Breakout")
    m_e17 = evaluate_composite(trades_e17, "E17: Gold H1 Linear Regression Slope & R²")
    m_e18 = evaluate_composite(trades_e18, "E18: Gold H1 Coppock Curve Momentum Inflection")
    m_portfolio = evaluate_composite(all_trades, "OCTODEC-ENGINE SUPREME INSTITUTIONAL COMPOSITE (OE-STIC)")

    print("\n" + "=" * 95)
    print("STRATEGY 70: OCTODEC-ENGINE SUPREME INSTITUTIONAL COMPOSITE (OE-STIC) AUDIT")
    print("=" * 95)
    print(f"{'Engine / Ensemble':<46} | {'Trades':<7} | {'Net Profit':<12} | {'PF':<6} | {'Max DD':<9} | {'RoMaD':<6} | MCR")
    print("-" * 95)
    for m in [m_e1, m_e2, m_e3, m_e4, m_e5, m_e6, m_e7, m_e8, m_e9, m_e10, m_e11, m_e12, m_e13, m_e14, m_e15, m_e16, m_e17, m_e18]:
        print(f"{m['label']:<46} | {m['total_trades']:<7} | ${m['net_profit']:<11.2f} | {m['pf']:<6.3f} | ${m['max_dd']:<8.2f} | {m['romad']:<6.2f} | {m['mcr']:.1f}% ({m['pos_months']}/{m['total_months']})")
    print("=" * 95)
    print(f"{m_portfolio['label']:<46} | {m_portfolio['total_trades']:<7} | ${m_portfolio['net_profit']:<11.2f} | {m_portfolio['pf']:<6.3f} | ${m_portfolio['max_dd']:<8.2f} | {m_portfolio['romad']:<6.2f} | {m_portfolio['mcr']:.1f}% ({m_portfolio['pos_months']}/{m_portfolio['total_months']})")
    print("=" * 95)

    out_json = os.path.join(args.out_dir, "strategy_70_champion.json")
    with open(out_json, "w") as f:
        json.dump({
            "strategy_id": "STRATEGY_70",
            "strategy_name": "Octodec-Engine Supreme Institutional Composite (OE-STIC)",
            "engines": [m_e1, m_e2, m_e3, m_e4, m_e5, m_e6, m_e7, m_e8, m_e9, m_e10, m_e11, m_e12, m_e13, m_e14, m_e15, m_e16, m_e17, m_e18],
            "portfolio_metrics": m_portfolio,
            "runtime_seconds": round(time.time() - t_start, 2)
        }, f, indent=2)
    print(f"[+] Saved Strategy 70 results to {out_json}")

if __name__ == "__main__":
    main()
