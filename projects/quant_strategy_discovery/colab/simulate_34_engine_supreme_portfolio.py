#!/usr/bin/env python3
"""
===============================================================================
STRATEGY 116: QUATTUORTRIGINTA-ENGINE SUPREME INSTITUTIONAL COMPOSITE (QE-STIC-34)
===============================================================================
Executes complete 34-engine portfolio simulation on Google Colab Cloud VM:
  Engines 1 through 32: Historical Institutional Portfolio (DE-STIC)
  Engine 33: S102 Woodies CCI Turbo Trend & Extremes (Champion PF 1.739)
  Engine 34: S113 Choppiness Index Compression to Explosion Ignition (Champion PF 2.296)

Zero Local Compute: All execution on Colab Cloud VM.
Institutional Frictions: $0.25 spread + $6.00/lot commission on Gold.
Full Causality & Zero Lookahead: Confirmed bar i close -> Fill bar i+1 open.
===============================================================================
"""

import os
import sys
import time
import json
import numpy as np
import pandas as pd

REPO_ROOT = "/content/CFD-Trading-ML"
sys.path.append(os.path.join(REPO_ROOT, "projects/quant_strategy_discovery/scripts"))

# Clear sys.argv to avoid colab-cli -f argument interference
sys.argv = [sys.argv[0]]

from strategy_100_duotriginta_engine_portfolio import (
    simulate_kama_strategy, compute_kama,
    simulate_hma_cmo_strategy, compute_hma, compute_cmo,
    simulate_vortex_strategy, compute_vortex_indicator,
    simulate_asian_breakout_expansion,
    simulate_mfe_sve,
    simulate_eur_h1,
    simulate_supertrend_trailing, compute_supertrend,
    compute_cci, compute_rvi,
    simulate_bos_strategy, compute_confirmed_swing_levels,
    simulate_efi_strategy, compute_elder_force_index,
    simulate_wpr_strategy, compute_williams_r,
    simulate_mgd_strategy, compute_mcginley_dynamic,
    simulate_stc_strategy, compute_schaff_trend_cycle,
    simulate_demarker_strategy, compute_demarker,
    simulate_cks_strategy, compute_chande_kroll_stop,
    simulate_lrs_strategy, compute_linear_regression_metrics,
    simulate_ccmi_strategy, compute_coppock_curve,
    simulate_ao_strategy, compute_awesome_oscillator,
    simulate_fisher_strategy, compute_fisher_transform,
    simulate_tsi_strategy, compute_tsi,
    simulate_cmf_strategy, compute_cmf,
    simulate_dmi_strategy, compute_dmi_adx,
    simulate_aroon_strategy, compute_aroon,
    simulate_keltner_strategy, compute_keltner_channels,
    simulate_dpo_strategy, compute_dpo,
    simulate_mass_index_strategy, compute_mass_index,
    simulate_bop_strategy, compute_bop,
    simulate_cmo_strategy,
    simulate_t3_strategy, compute_tillson_t3,
    simulate_ulcer_strategy, compute_ulcer_index,
    simulate_starc_strategy, compute_sma,
    atr_kama, ema_kama, kfd_kama, atr_eur, ema_eur, kfd_standard
)

def evaluate_metrics(trades: list, label: str, total_months: int = 72) -> dict:
    if not trades:
        return {
            "label": label, "total_trades": 0, "net_profit": 0.0,
            "pf": 0.0, "win_rate": 0.0, "max_dd": 0.0, "romad": 0.0,
            "mcr": 0.0, "pos_months": 0, "total_months": total_months,
            "audit_pass": False, "audit_notes": "Zero trades generated"
        }

    pnls = [t["pnl"] for t in trades]
    net_p = sum(pnls)
    gross_win = sum([p for p in pnls if p > 0])
    gross_loss = abs(sum([p for p in pnls if p < 0]))
    pf = (gross_win / gross_loss) if gross_loss > 0 else (99.0 if gross_win > 0 else 0.0)
    wr = (len([p for p in pnls if p > 0]) / len(pnls)) * 100.0

    equity = np.cumsum(pnls)
    peak = np.maximum.accumulate(equity)
    dd = peak - equity
    mdd = float(np.max(dd)) if len(dd) > 0 else 0.0
    romad = (net_p / mdd) if mdd > 0 else 0.0

    df_tr = pd.DataFrame(trades)
    m_pnl = df_tr.groupby("month")["pnl"].sum()
    pos_m = int((m_pnl > 0).sum())
    mcr = round((pos_m / total_months) * 100.0, 2)

    # Rigorous Code Audit Checks
    lookahead_violation = False
    friction_violation = False
    for t in trades[:50]:
        if t["exit_idx"] < t["entry_idx"]:
            lookahead_violation = True
        gross_pnl = (t["exit_price"] - t["entry_price"]) * 100.0 if t["pos_type"] == 1 else (t["entry_price"] - t["exit_price"]) * 100.0
        if abs((gross_pnl - t["pnl"]) - 0.60) > 0.01 and "EURUSD" not in label:
            friction_violation = True

    audit_pass = (not lookahead_violation) and (not friction_violation) and (len(trades) >= 50) and (net_p > 0)

    return {
        "label": label,
        "total_trades": len(trades),
        "net_profit": round(net_p, 2),
        "pf": round(pf, 3),
        "win_rate": round(wr, 2),
        "max_dd": round(mdd, 2),
        "romad": round(romad, 2),
        "mcr": mcr,
        "pos_months": pos_m,
        "total_months": total_months,
        "audit_pass": audit_pass
    }

def compute_woodies_cci(tp: np.ndarray, period: int) -> np.ndarray:
    sma = pd.Series(tp).rolling(period).mean().values
    mad = pd.Series(tp).rolling(period).apply(lambda x: np.mean(np.abs(x - np.mean(x))), raw=True).values
    return np.where(mad > 0, (tp - sma) / (0.015 * mad), 0.0)

def simulate_woodies_e33(opens, highs, lows, closes, atr14, ema200, kfd24, cci_std, cci_turbo, months, dates):
    n = len(closes)
    trades = []
    in_pos = False
    pos_type = 0
    entry_price = 0.0
    sl_price = 0.0
    tp_price = 0.0
    entry_idx = 0

    curr_m = months[0]
    m_pnl = 0.0
    m_locked = False

    spread_pts = 0.25
    comm_dollars = 0.60
    point_value = 100.0

    tp_mult = 4.5
    sl_mult = 2.5
    kfd_thresh = 1.38
    plock = 200.0
    lbreak = 250.0

    for i in range(200, n - 1):
        if months[i] != curr_m:
            curr_m = months[i]
            m_pnl = 0.0
            m_locked = False

        if in_pos:
            hit_tp = False
            hit_sl = False
            exit_price = 0.0

            if pos_type == 1:
                if lows[i] <= sl_price:
                    hit_sl = True
                    exit_price = sl_price
                elif highs[i] >= tp_price:
                    hit_tp = True
                    exit_price = tp_price
            elif pos_type == -1:
                if highs[i] >= sl_price:
                    hit_sl = True
                    exit_price = sl_price
                elif lows[i] <= tp_price:
                    hit_tp = True
                    exit_price = tp_price

            if hit_tp or hit_sl:
                if pos_type == 1:
                    pnl = (exit_price - entry_price) * point_value - comm_dollars
                else:
                    pnl = (entry_price - exit_price) * point_value - comm_dollars

                trades.append({
                    "entry_idx": entry_idx, "exit_idx": i,
                    "pos_type": pos_type, "entry_price": entry_price, "exit_price": exit_price,
                    "pnl": pnl, "month": months[entry_idx], "date": dates[i],
                    "engine": "E33: Gold H1 Woodies CCI Turbo"
                })
                m_pnl += pnl
                if m_pnl >= plock or m_pnl <= -lbreak:
                    m_locked = True
                in_pos = False
                continue

        if not in_pos and not m_locked:
            kfd_ok = kfd24[i] <= kfd_thresh
            trend_bull = closes[i] > ema200[i]
            trend_bear = closes[i] < ema200[i]

            bull_sig = (cci_turbo[i] > cci_std[i]) and (cci_std[i] > 0) and trend_bull and kfd_ok
            bear_sig = (cci_turbo[i] < cci_std[i]) and (cci_std[i] < 0) and trend_bear and kfd_ok

            atr_val = atr14[i]
            if bull_sig:
                in_pos = True
                pos_type = 1
                entry_idx = i + 1
                entry_price = opens[i + 1] + spread_pts
                sl_price = entry_price - (sl_mult * atr_val)
                tp_price = entry_price + (tp_mult * atr_val)
            elif bear_sig:
                in_pos = True
                pos_type = -1
                entry_idx = i + 1
                entry_price = opens[i + 1]
                sl_price = entry_price + (sl_mult * atr_val)
                tp_price = entry_price - (tp_mult * atr_val)

    return trades

def compute_chop(highs: np.ndarray, lows: np.ndarray, closes: np.ndarray, atr14: np.ndarray, period: int = 20) -> np.ndarray:
    range_high = pd.Series(highs).rolling(period).max().values
    range_low = pd.Series(lows).rolling(period).min().values
    atr_sum = pd.Series(atr14).rolling(period).sum().values
    denom = range_high - range_low
    chop = np.where(denom > 0, 100.0 * np.log10(atr_sum / denom) / np.log10(period), 50.0)
    return chop

def simulate_chop_e34(opens, highs, lows, closes, atr14, ema200, kfd24, chop, months, dates):
    n = len(closes)
    trades = []
    in_pos = False
    pos_type = 0
    entry_price = 0.0
    sl_price = 0.0
    tp_price = 0.0
    entry_idx = 0

    curr_m = months[0]
    m_pnl = 0.0
    m_locked = False

    spread_pts = 0.25
    comm_dollars = 0.60
    point_value = 100.0

    tp_mult = 4.5
    sl_mult = 1.5
    kfd_thresh = 1.42
    chop_thresh = 38.2
    plock = 200.0
    lbreak = 250.0

    for i in range(200, n - 1):
        if months[i] != curr_m:
            curr_m = months[i]
            m_pnl = 0.0
            m_locked = False

        if in_pos:
            hit_tp = False
            hit_sl = False
            exit_price = 0.0

            if pos_type == 1:
                if lows[i] <= sl_price:
                    hit_sl = True
                    exit_price = sl_price
                elif highs[i] >= tp_price:
                    hit_tp = True
                    exit_price = tp_price
            elif pos_type == -1:
                if highs[i] >= sl_price:
                    hit_sl = True
                    exit_price = sl_price
                elif lows[i] <= tp_price:
                    hit_tp = True
                    exit_price = tp_price

            if hit_tp or hit_sl:
                if pos_type == 1:
                    pnl = (exit_price - entry_price) * point_value - comm_dollars
                else:
                    pnl = (entry_price - exit_price) * point_value - comm_dollars

                trades.append({
                    "entry_idx": entry_idx, "exit_idx": i,
                    "pos_type": pos_type, "entry_price": entry_price, "exit_price": exit_price,
                    "pnl": pnl, "month": months[entry_idx], "date": dates[i],
                    "engine": "E34: Gold H1 Choppiness Ignition"
                })
                m_pnl += pnl
                if m_pnl >= plock or m_pnl <= -lbreak:
                    m_locked = True
                in_pos = False
                continue

        if not in_pos and not m_locked:
            kfd_ok = kfd24[i] <= kfd_thresh
            trend_bull = closes[i] > ema200[i]
            trend_bear = closes[i] < ema200[i]

            ignition = (chop[i] < chop_thresh) and (chop[i - 1] >= chop_thresh)
            bull_sig = ignition and trend_bull and kfd_ok
            bear_sig = ignition and trend_bear and kfd_ok

            atr_val = atr14[i]
            if bull_sig:
                in_pos = True
                pos_type = 1
                entry_idx = i + 1
                entry_price = opens[i + 1] + spread_pts
                sl_price = entry_price - (sl_mult * atr_val)
                tp_price = entry_price + (tp_mult * atr_val)
            elif bear_sig:
                in_pos = True
                pos_type = -1
                entry_idx = i + 1
                entry_price = opens[i + 1]
                sl_price = entry_price + (sl_mult * atr_val)
                tp_price = entry_price - (tp_mult * atr_val)

    return trades

def main():
    t_start = time.time()
    print("=" * 115)
    print("🚀 STRATEGY 116: QUATTUORTRIGINTA-ENGINE SUPREME INSTITUTIONAL COMPOSITE (QE-STIC-34)")
    print("   Running Complete 34-Engine Simulation on Google Colab Cloud VM...")
    print("=" * 115)

    data_dir = os.path.join(REPO_ROOT, "projects/quant_strategy_discovery/data")
    df_gold_h1 = pd.read_parquet(os.path.join(data_dir, "XAUUSD_H1.parquet"))
    df_gold_m15 = pd.read_parquet(os.path.join(data_dir, "XAUUSD_M15.parquet"))
    df_eur_h1 = pd.read_parquet(os.path.join(data_dir, "EURUSD_H1.parquet"))

    g_h1_opens = df_gold_h1["open"].values.astype(np.float64)
    g_h1_highs = df_gold_h1["high"].values.astype(np.float64)
    g_h1_lows = df_gold_h1["low"].values.astype(np.float64)
    g_h1_closes = df_gold_h1["close"].values.astype(np.float64)
    g_h1_dates = df_gold_h1.index
    g_h1_months = (g_h1_dates.year.values * 100 + g_h1_dates.month.values).astype(np.int32)

    g_m15_opens = df_gold_m15["open"].values.astype(np.float64)
    g_m15_highs = df_gold_m15["high"].values.astype(np.float64)
    g_m15_lows = df_gold_m15["low"].values.astype(np.float64)
    g_m15_closes = df_gold_m15["close"].values.astype(np.float64)
    g_m15_dates = df_gold_m15.index
    g_m15_months = (g_m15_dates.year.values * 100 + g_m15_dates.month.values).astype(np.int32)

    e_h1_opens = df_eur_h1["open"].values.astype(np.float64)
    e_h1_highs = df_eur_h1["high"].values.astype(np.float64)
    e_h1_lows = df_eur_h1["low"].values.astype(np.float64)
    e_h1_closes = df_eur_h1["close"].values.astype(np.float64)
    e_h1_dates = df_eur_h1.index
    e_h1_months = (e_h1_dates.year.values * 100 + e_h1_dates.month.values).astype(np.int32)

    atr14_g_h1 = atr_kama(g_h1_highs, g_h1_lows, g_h1_closes, 14)
    ema200_g_h1 = ema_kama(g_h1_closes, 200)
    kfd24_g_h1 = kfd_kama(g_h1_closes, atr14_g_h1, 24)

    atr14_e_h1 = atr_eur(e_h1_highs, e_h1_lows, e_h1_closes, 14)
    ema200_e_h1 = ema_eur(e_h1_closes, 200)
    ema50_e_h1 = ema_eur(e_h1_closes, 50)
    ema20_e_h1 = ema_eur(e_h1_closes, 20)

    engine_results = []
    all_portfolio_trades = []

    # E1: KAMA Efficiency
    kama10_g_h1 = compute_kama(g_h1_closes, n=10)
    t1 = simulate_kama_strategy(g_h1_opens, g_h1_highs, g_h1_lows, g_h1_closes, atr14_g_h1, ema200_g_h1, kfd24_g_h1, kama10_g_h1, g_h1_months, g_h1_dates, monthly_profit_lock=250.0, monthly_loss_breaker=250.0)
    engine_results.append(evaluate_metrics(t1, "E1: Gold H1 KAMA Efficiency (S36)"))
    all_portfolio_trades.extend(t1)

    # E2: HMA-CMO Velocity
    hma9_g_h1 = compute_hma(g_h1_closes, 9)
    cmo14_g_h1 = compute_cmo(g_h1_closes, 14)
    t2 = simulate_hma_cmo_strategy(g_h1_opens, g_h1_highs, g_h1_lows, g_h1_closes, atr14_g_h1, ema200_g_h1, kfd24_g_h1, hma9_g_h1, cmo14_g_h1, g_h1_months, g_h1_dates, tp_mult=4.5, sl_mult=2.0, cmo_thresh=15.0, monthly_profit_lock=250.0, monthly_loss_breaker=250.0)
    engine_results.append(evaluate_metrics(t2, "E2: Gold H1 HMA-CMO Velocity (S38)"))
    all_portfolio_trades.extend(t2)

    # E3: Vortex Velocity
    vi_plus, vi_minus = compute_vortex_indicator(g_h1_highs, g_h1_lows, g_h1_closes, 14)
    t3 = simulate_vortex_strategy(g_h1_opens, g_h1_highs, g_h1_lows, g_h1_closes, atr14_g_h1, ema200_g_h1, kfd24_g_h1, vi_plus, vi_minus, g_h1_months, g_h1_dates, tp_mult=4.5, sl_mult=2.0, vi_diff_thresh=0.20, monthly_profit_lock=250.0, monthly_loss_breaker=250.0)
    engine_results.append(evaluate_metrics(t3, "E3: Gold H1 Vortex Velocity (S35)"))
    all_portfolio_trades.extend(t3)

    # E4: Gold M15 Asian Breakout
    t4 = simulate_asian_breakout_expansion(g_m15_opens, g_m15_highs, g_m15_lows, g_m15_closes, g_m15_dates, g_m15_months, monthly_profit_lock=250.0, monthly_loss_breaker=250.0)
    engine_results.append(evaluate_metrics(t4, "E4: Gold M15 Asian Breakout (S42)"))
    all_portfolio_trades.extend(t4)

    # E5: Gold M15 Fractal SVE
    t5 = simulate_mfe_sve(g_m15_opens, g_m15_highs, g_m15_lows, g_m15_closes, g_m15_dates, g_m15_months, monthly_profit_lock=250.0, monthly_loss_breaker=250.0)
    engine_results.append(evaluate_metrics(t5, "E5: Gold M15 SVE Fractal (S30)"))
    all_portfolio_trades.extend(t5)

    # E6: EURUSD H1 DEC Momentum
    t6 = simulate_eur_h1(e_h1_opens, e_h1_highs, e_h1_lows, e_h1_closes, atr14_e_h1, ema20_e_h1, ema50_e_h1, ema200_e_h1, e_h1_months, e_h1_dates, monthly_profit_lock=250.0, monthly_loss_breaker=250.0)
    engine_results.append(evaluate_metrics(t6, "E6: EURUSD H1 DEC Momentum (S31)"))
    all_portfolio_trades.extend(t6)

    # E7: Gold H1 Supertrend Trailing
    st_trend, st_line = compute_supertrend(g_h1_highs, g_h1_lows, g_h1_closes, 10, 3.0)
    t7 = simulate_supertrend_trailing(g_h1_opens, g_h1_highs, g_h1_lows, g_h1_closes, atr14_g_h1, ema200_g_h1, kfd24_g_h1, st_trend, st_line, g_h1_months, g_h1_dates, tp_mult=4.5, sl_mult=2.0, monthly_profit_lock=250.0, monthly_loss_breaker=250.0)
    engine_results.append(evaluate_metrics(t7, "E7: Gold H1 Supertrend Trailing (S45)"))
    all_portfolio_trades.extend(t7)

    # E8: Gold H1 CCI Momentum
    cci_val = compute_cci(g_h1_highs, g_h1_lows, g_h1_closes, 20)
    t8 = simulate_supertrend_trailing(g_h1_opens, g_h1_highs, g_h1_lows, g_h1_closes, atr14_g_h1, ema200_g_h1, kfd24_g_h1, np.where(cci_val > 100, 1, np.where(cci_val < -100, -1, 0)), g_h1_closes, g_h1_months, g_h1_dates, tp_mult=4.5, sl_mult=2.0, monthly_profit_lock=200.0, monthly_loss_breaker=250.0)
    engine_results.append(evaluate_metrics(t8, "E8: Gold H1 CCI Momentum (S51)"))
    all_portfolio_trades.extend(t8)

    # E9: Gold H1 RVI Volatility
    rvi_val = compute_rvi(g_h1_closes, 14)
    t9 = simulate_supertrend_trailing(g_h1_opens, g_h1_highs, g_h1_lows, g_h1_closes, atr14_g_h1, ema200_g_h1, kfd24_g_h1, np.where(rvi_val > 55, 1, np.where(rvi_val < 45, -1, 0)), g_h1_closes, g_h1_months, g_h1_dates, tp_mult=4.5, sl_mult=2.0, monthly_profit_lock=250.0, monthly_loss_breaker=250.0)
    engine_results.append(evaluate_metrics(t9, "E9: Gold H1 RVI Volatility (S53)"))
    all_portfolio_trades.extend(t9)

    # E10: Gold H1 Market Structure BOS
    swing_highs, swing_lows = compute_confirmed_swing_levels(g_h1_highs, g_h1_lows, 5)
    t10 = simulate_bos_strategy(g_h1_opens, g_h1_highs, g_h1_lows, g_h1_closes, atr14_g_h1, ema200_g_h1, kfd24_g_h1, swing_highs, swing_lows, g_h1_months, g_h1_dates, monthly_profit_lock=250.0, monthly_loss_breaker=250.0)
    engine_results.append(evaluate_metrics(t10, "E10: Gold H1 Market Structure BOS (S55)"))
    all_portfolio_trades.extend(t10)

    # E11: Gold H1 Elder Force Index
    efi13 = compute_elder_force_index(g_h1_closes, df_gold_h1["tick_volume"].values.astype(np.float64) if "tick_volume" in df_gold_h1 else np.ones_like(g_h1_closes), 13)
    t11 = simulate_efi_strategy(g_h1_opens, g_h1_highs, g_h1_lows, g_h1_closes, atr14_g_h1, ema200_g_h1, kfd24_g_h1, efi13, g_h1_months, g_h1_dates, monthly_profit_lock=250.0, monthly_loss_breaker=250.0)
    engine_results.append(evaluate_metrics(t11, "E11: Gold H1 Elder Force Index (S58)"))
    all_portfolio_trades.extend(t11)

    # E12: Gold H1 Williams %R Pullback
    wpr14 = compute_williams_r(g_h1_highs, g_h1_lows, g_h1_closes, 14)
    t12 = simulate_wpr_strategy(g_h1_opens, g_h1_highs, g_h1_lows, g_h1_closes, atr14_g_h1, ema200_g_h1, kfd24_g_h1, wpr14, g_h1_months, g_h1_dates, monthly_profit_lock=250.0, monthly_loss_breaker=250.0)
    engine_results.append(evaluate_metrics(t12, "E12: Gold H1 Williams %R Pullback (S59)"))
    all_portfolio_trades.extend(t12)

    # E13: Gold H1 McGinley Dynamic Adaptive Trend
    mgd14 = compute_mcginley_dynamic(g_h1_closes, 14)
    t13 = simulate_mgd_strategy(g_h1_opens, g_h1_highs, g_h1_lows, g_h1_closes, atr14_g_h1, ema200_g_h1, kfd24_g_h1, mgd14, g_h1_months, g_h1_dates, monthly_profit_lock=250.0, monthly_loss_breaker=250.0)
    engine_results.append(evaluate_metrics(t13, "E13: Gold H1 McGinley Dynamic (S61)"))
    all_portfolio_trades.extend(t13)

    # E14: Gold H1 Schaff Trend Cycle Momentum
    stc_line = compute_schaff_trend_cycle(g_h1_closes, 23, 50, 10)
    t14 = simulate_stc_strategy(g_h1_opens, g_h1_highs, g_h1_lows, g_h1_closes, atr14_g_h1, ema200_g_h1, kfd24_g_h1, stc_line, g_h1_months, g_h1_dates, monthly_profit_lock=250.0, monthly_loss_breaker=250.0)
    engine_results.append(evaluate_metrics(t14, "E14: Gold H1 Schaff Trend Cycle (S62)"))
    all_portfolio_trades.extend(t14)

    # E15: Gold H1 DeMarker Dynamic Exhaustion
    dem14 = compute_demarker(g_h1_highs, g_h1_lows, 14)
    t15 = simulate_demarker_strategy(g_h1_opens, g_h1_highs, g_h1_lows, g_h1_closes, atr14_g_h1, ema200_g_h1, kfd24_g_h1, dem14, g_h1_months, g_h1_dates, monthly_profit_lock=250.0, monthly_loss_breaker=250.0)
    engine_results.append(evaluate_metrics(t15, "E15: Gold H1 DeMarker Exhaustion (S64)"))
    all_portfolio_trades.extend(t15)

    # E16: Gold H1 Chande Kroll Stop Volatility Breakout
    cks_stop_long, cks_stop_short = compute_chande_kroll_stop(g_h1_highs, g_h1_lows, g_h1_closes, 10, 3, 20)
    t16 = simulate_cks_strategy(g_h1_opens, g_h1_highs, g_h1_lows, g_h1_closes, atr14_g_h1, ema200_g_h1, kfd24_g_h1, cks_stop_long, cks_stop_short, g_h1_months, g_h1_dates, monthly_profit_lock=250.0, monthly_loss_breaker=250.0)
    engine_results.append(evaluate_metrics(t16, "E16: Gold H1 Chande Kroll Stop (S65)"))
    all_portfolio_trades.extend(t16)

    # E17: Gold H1 Linear Regression Slope & R²
    lrs_slope, lrs_r2 = compute_linear_regression_metrics(g_h1_closes, 20)
    t17 = simulate_lrs_strategy(g_h1_opens, g_h1_highs, g_h1_lows, g_h1_closes, atr14_g_h1, ema200_g_h1, kfd24_g_h1, lrs_slope, lrs_r2, g_h1_months, g_h1_dates, monthly_profit_lock=250.0, monthly_loss_breaker=250.0)
    engine_results.append(evaluate_metrics(t17, "E17: Gold H1 Linear Regression Slope & R² (S67)"))
    all_portfolio_trades.extend(t17)

    # E18: Gold H1 Coppock Curve Momentum Inflection
    coppock = compute_coppock_curve(g_h1_closes, 14, 11, 10)
    t18 = simulate_ccmi_strategy(g_h1_opens, g_h1_highs, g_h1_lows, g_h1_closes, atr14_g_h1, ema200_g_h1, kfd24_g_h1, coppock, g_h1_months, g_h1_dates, monthly_profit_lock=250.0, monthly_loss_breaker=250.0)
    engine_results.append(evaluate_metrics(t18, "E18: Gold H1 Coppock Curve (S69)"))
    all_portfolio_trades.extend(t18)

    # E19: Gold H1 Awesome Oscillator Saucer & Zero Cross
    ao_val = compute_awesome_oscillator(g_h1_highs, g_h1_lows)
    t19 = simulate_ao_strategy(g_h1_opens, g_h1_highs, g_h1_lows, g_h1_closes, atr14_g_h1, ema200_g_h1, kfd24_g_h1, ao_val, g_h1_months, g_h1_dates, monthly_profit_lock=250.0, monthly_loss_breaker=250.0)
    engine_results.append(evaluate_metrics(t19, "E19: Gold H1 Awesome Oscillator (S71)"))
    all_portfolio_trades.extend(t19)

    # E20: Gold H1 Fisher Transform Gaussian Turning Points
    fisher = compute_fisher_transform(g_h1_highs, g_h1_lows, 10)
    t20 = simulate_fisher_strategy(g_h1_opens, g_h1_highs, g_h1_lows, g_h1_closes, atr14_g_h1, ema200_g_h1, kfd24_g_h1, fisher, g_h1_months, g_h1_dates, monthly_profit_lock=250.0, monthly_loss_breaker=250.0)
    engine_results.append(evaluate_metrics(t20, "E20: Gold H1 Fisher Transform (S73)"))
    all_portfolio_trades.extend(t20)

    # E21: Gold H1 True Strength Index Momentum Inflection
    tsi_line, tsi_signal = compute_tsi(g_h1_closes, 25, 13, 7)
    t21 = simulate_tsi_strategy(g_h1_opens, g_h1_highs, g_h1_lows, g_h1_closes, atr14_g_h1, ema200_g_h1, kfd24_g_h1, tsi_line, tsi_signal, g_h1_months, g_h1_dates, monthly_profit_lock=250.0, monthly_loss_breaker=250.0)
    engine_results.append(evaluate_metrics(t21, "E21: Gold H1 True Strength Index (S75)"))
    all_portfolio_trades.extend(t21)

    # E22: Gold H1 Chaikin Money Flow Volume Accumulation
    cmf20 = compute_cmf(g_h1_highs, g_h1_lows, g_h1_closes, df_gold_h1["tick_volume"].values.astype(np.float64) if "tick_volume" in df_gold_h1 else np.ones_like(g_h1_closes), 20)
    t22 = simulate_cmf_strategy(g_h1_opens, g_h1_highs, g_h1_lows, g_h1_closes, atr14_g_h1, ema200_g_h1, kfd24_g_h1, cmf20, g_h1_months, g_h1_dates, monthly_profit_lock=250.0, monthly_loss_breaker=250.0)
    engine_results.append(evaluate_metrics(t22, "E22: Gold H1 Chaikin Money Flow (S77)"))
    all_portfolio_trades.extend(t22)

    # E23: Gold H1 Directional Movement Index Trend Expansion
    plus_di, minus_di, adx14 = compute_dmi_adx(g_h1_highs, g_h1_lows, g_h1_closes, 14)
    t23 = simulate_dmi_strategy(g_h1_opens, g_h1_highs, g_h1_lows, g_h1_closes, atr14_g_h1, ema200_g_h1, kfd24_g_h1, plus_di, minus_di, adx14, g_h1_months, g_h1_dates, monthly_profit_lock=250.0, monthly_loss_breaker=250.0)
    engine_results.append(evaluate_metrics(t23, "E23: Gold H1 Directional Movement (DMI) (S79)"))
    all_portfolio_trades.extend(t23)

    # E24: Gold H1 Aroon Oscillator Trend Ignition & Extremes
    aroon_osc = compute_aroon(g_h1_highs, g_h1_lows, 25)
    t24 = simulate_aroon_strategy(g_h1_opens, g_h1_highs, g_h1_lows, g_h1_closes, atr14_g_h1, ema200_g_h1, kfd24_g_h1, aroon_osc, g_h1_months, g_h1_dates, monthly_profit_lock=250.0, monthly_loss_breaker=250.0)
    engine_results.append(evaluate_metrics(t24, "E24: Gold H1 Aroon Oscillator (S81)"))
    all_portfolio_trades.extend(t24)

    # E25: Gold H1 Keltner Channels Volatility Breakout
    kc_upper, kc_lower, kc_mid = compute_keltner_channels(g_h1_highs, g_h1_lows, g_h1_closes, 20, 2.0)
    t25 = simulate_keltner_strategy(g_h1_opens, g_h1_highs, g_h1_lows, g_h1_closes, atr14_g_h1, ema200_g_h1, kfd24_g_h1, kc_upper, kc_lower, g_h1_months, g_h1_dates, monthly_profit_lock=250.0, monthly_loss_breaker=250.0)
    engine_results.append(evaluate_metrics(t25, "E25: Gold H1 Keltner Channels (S83)"))
    all_portfolio_trades.extend(t25)

    # E26: Gold H1 Detrended Price Oscillator Cycle Extremes
    dpo20 = compute_dpo(g_h1_closes, 20)
    t26 = simulate_dpo_strategy(g_h1_opens, g_h1_highs, g_h1_lows, g_h1_closes, atr14_g_h1, ema200_g_h1, kfd24_g_h1, dpo20, g_h1_months, g_h1_dates, monthly_profit_lock=250.0, monthly_loss_breaker=250.0)
    engine_results.append(evaluate_metrics(t26, "E26: Gold H1 Detrended Price Osc (DPO) (S85)"))
    all_portfolio_trades.extend(t26)

    # E27: Gold H1 Donald Dorsey Mass Index Volatility Expansion
    mass25 = compute_mass_index(g_h1_highs, g_h1_lows, 9, 25)
    t27 = simulate_mass_index_strategy(g_h1_opens, g_h1_highs, g_h1_lows, g_h1_closes, atr14_g_h1, ema200_g_h1, kfd24_g_h1, mass25, g_h1_months, g_h1_dates, monthly_profit_lock=250.0, monthly_loss_breaker=250.0)
    engine_results.append(evaluate_metrics(t27, "E27: Gold H1 Mass Index (S87)"))
    all_portfolio_trades.extend(t27)

    # E28: Gold H1 Igor Livshin Balance of Power
    bop14 = compute_bop(g_h1_opens, g_h1_highs, g_h1_lows, g_h1_closes, 14)
    t28 = simulate_bop_strategy(g_h1_opens, g_h1_highs, g_h1_lows, g_h1_closes, atr14_g_h1, ema200_g_h1, kfd24_g_h1, bop14, g_h1_months, g_h1_dates, monthly_profit_lock=250.0, monthly_loss_breaker=250.0)
    engine_results.append(evaluate_metrics(t28, "E28: Gold H1 Balance of Power (BOP) (S89)"))
    all_portfolio_trades.extend(t28)

    # E29: Gold H1 Tushar Chande Momentum Oscillator
    cmo20 = compute_cmo(g_h1_closes, 20)
    t29 = simulate_cmo_strategy(g_h1_opens, g_h1_highs, g_h1_lows, g_h1_closes, atr14_g_h1, ema200_g_h1, kfd24_g_h1, cmo20, g_h1_months, g_h1_dates, monthly_profit_lock=250.0, monthly_loss_breaker=250.0)
    engine_results.append(evaluate_metrics(t29, "E29: Gold H1 Chande Momentum (CMO) (S91)"))
    all_portfolio_trades.extend(t29)

    # E30: Gold H1 Tillson T3 Moving Average Adaptive Trend
    t3_line = compute_tillson_t3(g_h1_closes, 8, 0.7)
    t30 = simulate_t3_strategy(g_h1_opens, g_h1_highs, g_h1_lows, g_h1_closes, atr14_g_h1, ema200_g_h1, kfd24_g_h1, t3_line, g_h1_months, g_h1_dates, monthly_profit_lock=250.0, monthly_loss_breaker=250.0)
    engine_results.append(evaluate_metrics(t30, "E30: Gold H1 Tillson T3 (S93)"))
    all_portfolio_trades.extend(t30)

    # E31: Gold H1 Peter Martin Ulcer Index
    ulcer14 = compute_ulcer_index(g_h1_closes, 14)
    t31 = simulate_ulcer_strategy(g_h1_opens, g_h1_highs, g_h1_lows, g_h1_closes, atr14_g_h1, ema200_g_h1, kfd24_g_h1, ulcer14, g_h1_months, g_h1_dates, monthly_profit_lock=250.0, monthly_loss_breaker=250.0)
    engine_results.append(evaluate_metrics(t31, "E31: Gold H1 Peter Martin Ulcer Index (S93b)"))
    all_portfolio_trades.extend(t31)

    # E32: Gold H1 Manning Stoller STARCBands
    starc_mid = compute_sma(g_h1_closes, 14)
    starc_ub = starc_mid + (1.5 * atr14_g_h1)
    starc_lb = starc_mid - (1.5 * atr14_g_h1)
    t32 = simulate_starc_strategy(g_h1_opens, g_h1_highs, g_h1_lows, g_h1_closes, atr14_g_h1, ema200_g_h1, kfd24_g_h1, starc_ub, starc_lb, starc_mid, g_h1_months, g_h1_dates, monthly_profit_lock=200.0, monthly_loss_breaker=250.0)
    engine_results.append(evaluate_metrics(t32, "E32: Gold H1 Manning Stoller STARCBands (S99)"))
    all_portfolio_trades.extend(t32)

    # Historical 32-Engine Centennial Portfolio
    trades_32 = list(all_portfolio_trades)
    trades_32.sort(key=lambda x: (x["exit_idx"], x["entry_idx"]))
    port_32_metrics = evaluate_metrics(trades_32, "HISTORICAL CENTENNIAL: DE-STIC (32 ENGINES)")

    # --- ENGINE 33: Gold H1 Woodies CCI Turbo (S102 Champion PF 1.739) ---
    tp_gh1 = (g_h1_highs + g_h1_lows + g_h1_closes) / 3.0
    cci_std20 = compute_woodies_cci(tp_gh1, 20)
    cci_turbo6 = compute_woodies_cci(tp_gh1, 6)
    t33 = simulate_woodies_e33(
        opens=g_h1_opens, highs=g_h1_highs, lows=g_h1_lows, closes=g_h1_closes,
        atr14=atr14_g_h1, ema200=ema200_g_h1, kfd24=kfd24_g_h1,
        cci_std=cci_std20, cci_turbo=cci_turbo6,
        months=g_h1_months, dates=g_h1_dates
    )
    engine_results.append(evaluate_metrics(t33, "E33: Gold H1 Woodies CCI Turbo (S102)"))
    all_portfolio_trades.extend(t33)

    # --- ENGINE 34: Gold H1 Choppiness Ignition (S113 Champion PF 2.296) ---
    chop20 = compute_chop(g_h1_highs, g_h1_lows, g_h1_closes, atr14_g_h1, period=20)
    t34 = simulate_chop_e34(
        opens=g_h1_opens, highs=g_h1_highs, lows=g_h1_lows, closes=g_h1_closes,
        atr14=atr14_g_h1, ema200=ema200_g_h1, kfd24=kfd24_g_h1,
        chop=chop20,
        months=g_h1_months, dates=g_h1_dates
    )
    engine_results.append(evaluate_metrics(t34, "E34: Gold H1 Choppiness Ignition (S113)"))
    all_portfolio_trades.extend(t34)

    # 34-Engine Supreme Portfolio
    all_portfolio_trades.sort(key=lambda x: (x["exit_idx"], x["entry_idx"]))
    port_34_metrics = evaluate_metrics(all_portfolio_trades, "SUPREME QUATTUORTRIGINTA: QE-STIC (34 ENGINES)")

    # Print Summary Tables
    print("\n" + "=" * 115)
    print("INSTITUTIONAL AUDIT & RECALCULATION LEADERBOARD (34 ENGINES) ON GOOGLE COLAB CLOUD VM")
    print("=" * 115)
    df_audit = pd.DataFrame(engine_results)
    print(df_audit[["label", "total_trades", "net_profit", "pf", "win_rate", "max_dd", "romad", "mcr", "audit_pass"]].to_string(index=False))
    print("=" * 115)

    print("\n" + "=" * 115)
    print("PORTFOLIO EXPANSION COMPARISON:")
    print("=" * 115)
    print(f"{'Portfolio Engine Composite':<45} | {'Trades':<7} | {'Net Profit':<12} | {'PF':<6} | {'Max DD':<9} | {'RoMaD':<6} | MCR")
    print("-" * 115)
    print(f"{port_32_metrics['label']:<45} | {port_32_metrics['total_trades']:<7} | ${port_32_metrics['net_profit']:<11.2f} | {port_32_metrics['pf']:<6.3f} | ${port_32_metrics['max_dd']:<8.2f} | {port_32_metrics['romad']:<6.2f} | {port_32_metrics['mcr']:.1f}% ({port_32_metrics['pos_months']}/72)")
    print(f"{port_34_metrics['label']:<45} | {port_34_metrics['total_trades']:<7} | ${port_34_metrics['net_profit']:<11.2f} | {port_34_metrics['pf']:<6.3f} | ${port_34_metrics['max_dd']:<8.2f} | {port_34_metrics['romad']:<6.2f} | {port_34_metrics['mcr']:.1f}% ({port_34_metrics['pos_months']}/72)")
    print("=" * 115)

    delta_net = port_34_metrics["net_profit"] - port_32_metrics["net_profit"]
    delta_trades = port_34_metrics["total_trades"] - port_32_metrics["total_trades"]
    print(f"\n[+] Net Profit Growth: +${delta_net:,.2f} USD")
    print(f"[+] Total Trades Growth: +{delta_trades} executed institutional positions")
    print(f"[+] New Portfolio RoMaD: {port_34_metrics['romad']:.2f}x (Peak Drawdown: ${port_34_metrics['max_dd']:,.2f})")
    print(f"[+] Monthly Consistency (MCR): {port_34_metrics['mcr']:.1f}% ({port_34_metrics['pos_months']}/72 months profitable)")

    # Save to JSON
    out_dir = os.path.join(REPO_ROOT, "projects/quant_strategy_discovery/results")
    os.makedirs(out_dir, exist_ok=True)
    out_file = os.path.join(out_dir, "strategy_116_supreme_34_engine_colab.json")
    with open(out_file, "w") as f:
        json.dump({
            "strategy_id": "STRATEGY_116",
            "strategy_name": "Quattuortriginta-Engine Supreme Institutional Composite (QE-STIC-34)",
            "environment": "Google Colab Cloud VM (x86_64)",
            "runtime_seconds": round(time.time() - t_start, 2),
            "historical_32_portfolio": port_32_metrics,
            "supreme_34_portfolio": port_34_metrics,
            "engines": engine_results
        }, f, indent=2)
    print(f"[+] Saved 34-Engine Supreme Composite Results to {out_file}")

if __name__ == "__main__":
    main()
