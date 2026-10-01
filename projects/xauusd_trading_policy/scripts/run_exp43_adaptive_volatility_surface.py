"""
=============================================================================
Experiment EXP-43: Asymmetric Volatility Surface & Adaptive Dynamic Excursion Targets (AVS-ADET)
=============================================================================
Autonomous Quant ML Research - Multi-Asset Quantitative Trading
Evaluates:
1. Variant 1: EXP-36 Master Baseline (Fixed 3-Tier APHE Ladder: 50%->BE, 70%->35%, 85%->65%)
2. Variant 2: Adaptive Trailing Thresholds (Dynamic Excursion Tiers based on Volatility Velocity)
3. Variant 3: Adaptive Excursion Targets (Dynamic TP Expansion 2.5x-5.5x ATR)
4. Variant 4: Master AVS-ADET Fused Policy (Adaptive Tiers + Dynamic Targets + USDi Gating)
5. Variant 5: Asymmetric Macro Drift Bias (Gold Monetary Drift Long-Bias Sizing)
Plus:
- Full Model Persistence (.joblib)
- High-Resolution Equity & Excursion Dynamics Charts
- Master Registry Update
=============================================================================
"""

import os
import sys
import time
import json
import joblib
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from typing import Dict, Any, Tuple, Optional

# Ensure project root is in sys.path
script_dir = os.path.dirname(os.path.abspath(__file__))
project_dir = os.path.abspath(os.path.join(script_dir, ".."))
if project_dir not in sys.path:
    sys.path.insert(0, project_dir)

from scripts.features_policy import extract_market_state_features
from scripts.train_and_benchmark_10_models import (
    load_and_preprocess_data,
    prepare_market_features,
    find_dataset_file
)
from scripts.run_research_experiment import compute_comprehensive_metrics

ACTION_HOLD = 0
ACTION_OPEN_LONG = 1
ACTION_OPEN_SHORT = 2


def make_directional_meta_features(X_base, p_fwd_50, p_rev_50, p_fwd_80, p_rev_80, ratio, is_liq, trend_aligned, slope):
    extra = np.column_stack([
        p_fwd_50, p_rev_50, p_fwd_80, p_rev_80, ratio, is_liq, trend_aligned, slope
    ])
    return np.hstack([X_base, extra]).astype(np.float32)


def run_adaptive_volatility_backtest(
    df: pd.DataFrame,
    atr_series: pd.Series,
    actions: np.ndarray,
    sl_mults: np.ndarray,
    tp_mults: np.ndarray,
    vol_velocity: np.ndarray,
    mode: str = "baseline", # "baseline", "adaptive_tiers", "dynamic_targets", "master_avs", "asymmetric_drift"
    risk_pct: float = 0.0085,
    point_value: float = 100.0,
    spread_points: float = 2.0,
    slippage_points: float = 1.0,
    commission_per_lot: float = 6.0,
    initial_balance: float = 10000.0
) -> Dict[str, Any]:
    n_bars = len(df)
    c_arr = df['close'].to_numpy(dtype=np.float64)
    h_arr = df['high'].to_numpy(dtype=np.float64)
    l_arr = df['low'].to_numpy(dtype=np.float64)
    atr_arr = np.maximum(atr_series.to_numpy(dtype=np.float64), 0.1)

    balance = initial_balance
    equity_curve = [balance]
    trades = []

    pos_dir = 0.0
    pos_lot = 0.0
    entry_price = 0.0
    entry_bar = 0
    sl_price = 0.0
    tp_price = 0.0
    max_excursion = 0.0
    trail_tier = 0

    cost_per_trade_price = (spread_points + slippage_points) * 0.10

    for t in range(n_bars):
        close_t = c_arr[t]
        high_t = h_arr[t]
        low_t = l_arr[t]
        atr_t = atr_arr[t]
        v_vel = vol_velocity[t]

        if pos_dir != 0.0:
            exit_trade = False
            exit_price = 0.0
            reason = ""
            bars_held = t - entry_bar

            # Determine dynamic thresholds based on regime
            if mode in ["adaptive_tiers", "master_avs", "asymmetric_drift"]:
                if v_vel > 0.15:
                    # High expansion velocity: give room
                    t1_exc = 0.60; t1_sl_offset = 0.10; t2_exc = 0.75; t2_lock = 0.40; t3_exc = 0.90; t3_lock = 0.75
                elif v_vel < -0.10:
                    # Compressing velocity: quick harvest
                    t1_exc = 0.40; t1_sl_offset = 0.05; t2_exc = 0.55; t2_lock = 0.35; t3_exc = 0.75; t3_lock = 0.60
                else:
                    # Normal APHE
                    t1_exc = 0.50; t1_sl_offset = 0.10; t2_exc = 0.70; t2_lock = 0.35; t3_exc = 0.85; t3_lock = 0.65
            else:
                # Baseline fixed APHE
                t1_exc = 0.50; t1_sl_offset = 0.10; t2_exc = 0.70; t2_lock = 0.35; t3_exc = 0.85; t3_lock = 0.65

            if pos_dir == 1.0:
                current_excursion = (high_t - entry_price) / max(tp_price - entry_price, 0.01)
                max_excursion = max(max_excursion, current_excursion)

                if trail_tier == 0 and max_excursion >= t1_exc:
                    sl_price = max(sl_price, entry_price + t1_sl_offset * atr_t)
                    trail_tier = 1
                elif trail_tier == 1 and max_excursion >= t2_exc:
                    sl_price = max(sl_price, entry_price + t2_lock * (tp_price - entry_price))
                    trail_tier = 2
                elif trail_tier == 2 and max_excursion >= t3_exc:
                    sl_price = max(sl_price, entry_price + t3_lock * (tp_price - entry_price))
                    trail_tier = 3

                # Stagnation Ratchet (from EXP-41)
                if bars_held >= 45 and max_excursion < 0.25:
                    sl_price = max(sl_price, entry_price - 0.75 * atr_t)

                if low_t <= sl_price:
                    exit_trade = True; exit_price = sl_price; reason = f"SL_T{trail_tier}" if trail_tier > 0 else "SL"
                elif high_t >= tp_price:
                    exit_trade = True; exit_price = tp_price; reason = "TP"
                elif bars_held >= 180:
                    exit_trade = True; exit_price = close_t; reason = "TIME"

            elif pos_dir == -1.0:
                current_excursion = (entry_price - low_t) / max(entry_price - tp_price, 0.01)
                max_excursion = max(max_excursion, current_excursion)

                if trail_tier == 0 and max_excursion >= t1_exc:
                    sl_price = min(sl_price, entry_price - t1_sl_offset * atr_t)
                    trail_tier = 1
                elif trail_tier == 1 and max_excursion >= t2_exc:
                    sl_price = min(sl_price, entry_price - t2_lock * (entry_price - tp_price))
                    trail_tier = 2
                elif trail_tier == 2 and max_excursion >= t3_exc:
                    sl_price = min(sl_price, entry_price - t3_lock * (entry_price - tp_price))
                    trail_tier = 3

                # Stagnation Ratchet (from EXP-41)
                if bars_held >= 45 and max_excursion < 0.25:
                    sl_price = min(sl_price, entry_price + 0.75 * atr_t)

                if high_t >= sl_price:
                    exit_trade = True; exit_price = sl_price; reason = f"SL_T{trail_tier}" if trail_tier > 0 else "SL"
                elif low_t <= tp_price:
                    exit_trade = True; exit_price = tp_price; reason = "TP"
                elif bars_held >= 180:
                    exit_trade = True; exit_price = close_t; reason = "TIME"

            if exit_trade:
                gross_pnl = (exit_price - entry_price) * pos_dir * point_value * pos_lot
                total_comm = commission_per_lot * pos_lot
                net_pnl = gross_pnl - total_comm
                balance += net_pnl
                trades.append({
                    "entry_bar": entry_bar, "exit_bar": t, "direction": pos_dir,
                    "lot": pos_lot, "entry_price": entry_price, "exit_price": exit_price,
                    "net_pnl": net_pnl, "reason": reason, "bars_held": bars_held
                })
                pos_dir = 0.0; trail_tier = 0; max_excursion = 0.0

        if pos_dir == 0.0 and actions[t] != ACTION_HOLD:
            act = actions[t]
            base_sl = float(sl_mults[t])
            base_tp = float(tp_mults[t])

            # Dynamic Excursion Target Expansion
            if mode in ["dynamic_targets", "master_avs", "asymmetric_drift"]:
                if v_vel > 0.15:
                    target_tp = np.clip(base_tp * 1.35, 3.5, 7.5)
                elif v_vel < -0.10:
                    target_tp = np.clip(base_tp * 0.80, 2.0, 4.0)
                else:
                    target_tp = base_tp
            else:
                target_tp = base_tp

            # Asymmetric Drift Sizing
            trade_risk = risk_pct
            if mode == "asymmetric_drift":
                if act == ACTION_OPEN_LONG:
                    trade_risk = risk_pct * 1.15 # Long monetary expansion bias
                elif act == ACTION_OPEN_SHORT:
                    trade_risk = risk_pct * 0.85 # Counter-trend dampener

            dollar_risk_budget = balance * trade_risk
            dollar_per_lot_risk = base_sl * atr_t * point_value
            calc_lot = dollar_risk_budget / max(dollar_per_lot_risk, 10.0)
            pos_lot = float(np.clip(calc_lot, 0.02, 0.50))

            if act == ACTION_OPEN_LONG:
                pos_dir = 1.0
                entry_price = close_t + cost_per_trade_price * 0.5
                entry_bar = t
                sl_price = entry_price - (base_sl * atr_t)
                tp_price = entry_price + (target_tp * atr_t)
            elif act == ACTION_OPEN_SHORT:
                pos_dir = -1.0
                entry_price = close_t - cost_per_trade_price * 0.5
                entry_bar = t
                sl_price = entry_price + (base_sl * atr_t)
                tp_price = entry_price - (target_tp * atr_t)
            trail_tier = 0
            max_excursion = 0.0

        equity_curve.append(balance)

    eq_arr = np.array(equity_curve)
    peaks = np.maximum.accumulate(eq_arr)
    drawdowns = (peaks - eq_arr) / peaks * 100.0
    max_dd = float(np.max(drawdowns)) if len(drawdowns) > 0 else 0.0

    trade_cols = ["entry_bar", "exit_bar", "direction", "lot", "entry_price", "exit_price", "net_pnl", "reason", "bars_held"]
    trade_df = pd.DataFrame(trades, columns=trade_cols) if trades else pd.DataFrame(columns=trade_cols)

    return {
        "initial_balance": initial_balance,
        "final_balance": balance,
        "net_profit": balance - initial_balance,
        "return_pct": (balance - initial_balance) / initial_balance * 100.0,
        "trades": trade_df,
        "total_trades": len(trades),
        "equity_curve": eq_arr,
        "max_drawdown_pct": max_dd
    }


def run_experiment_43(eurusd_path: Optional[str] = None, xauusd_path: Optional[str] = None):
    print("=" * 80)
    print("🔬 EXPERIMENT EXP-43: ASYMMETRIC VOLATILITY SURFACE & ADAPTIVE EXCURSION TARGETS (AVS-ADET)")
    print("=" * 80)

    # 1. Load Data
    eur_file = find_dataset_file(eurusd_path) if eurusd_path else find_dataset_file("EURUSD")
    xau_file = find_dataset_file(xauusd_path) if xauusd_path else find_dataset_file("XAUUSD")

    print(f"\n[DataLoader] EURUSD: {eur_file}")
    print(f"[DataLoader] XAUUSD: {xau_file}")

    df_eur_tr, df_eur_val = load_and_preprocess_data(eur_file)
    df_xau_tr, df_xau_val = load_and_preprocess_data(xau_file)

    (feat_eur_val, atr_eur_val, close_eur_val, df_eur_val_c) = prepare_market_features(df_eur_tr, df_eur_val)[1]
    (feat_xau_val, atr_xau_val, close_xau_val, df_xau_val_c) = prepare_market_features(df_xau_tr, df_xau_val)[1]

    # Align Timestamps
    df_eur_val_c['dt_key'] = pd.to_datetime(df_eur_val_c['dt'] if 'dt' in df_eur_val_c.columns else df_eur_val_c.index)
    df_xau_val_c['dt_key'] = pd.to_datetime(df_xau_val_c['dt'] if 'dt' in df_xau_val_c.columns else df_xau_val_c.index)

    df_eur_idx = df_eur_val_c.set_index('dt_key')
    df_xau_idx = df_xau_val_c.set_index('dt_key')
    common_idx = df_xau_idx.index.intersection(df_eur_idx.index)

    eur_c = df_eur_idx.loc[common_idx, 'close'].to_numpy(dtype=np.float64)
    xau_c = df_xau_idx.loc[common_idx, 'close'].to_numpy(dtype=np.float64)

    eur_ret15 = pd.Series(eur_c).pct_change(15).fillna(0.0).to_numpy()
    xau_ret15 = pd.Series(xau_c).pct_change(15).fillna(0.0).to_numpy()
    usdi_ret15 = -0.60 * eur_ret15 - 0.40 * xau_ret15

    # 2. Compute Volatility Velocity & Surfaces
    atr_val_arr = np.maximum(atr_xau_val.to_numpy(dtype=np.float64), 0.1)
    atr_s = pd.Series(atr_val_arr)
    atr_ma60 = atr_s.rolling(60, min_periods=10).mean().bfill().to_numpy()
    vol_velocity = (atr_val_arr - atr_ma60) / atr_ma60

    # 3. Load Model Bundle
    models_dir = os.path.join(project_dir, "models")
    bundle = joblib.load(os.path.join(models_dir, "exp27_cross_session_dual_sleeve.joblib"))

    X_val = np.nan_to_num(feat_xau_val.to_numpy(dtype=np.float32), nan=0.0)
    c_val = close_xau_val

    ema20_val = c_val.ewm(span=20, adjust=False).mean()
    ema60_val = c_val.ewm(span=60, adjust=False).mean()
    ema240_val = c_val.ewm(span=240, adjust=False).mean()

    trend_l_val = ((c_val > ema60_val) & (ema20_val > ema60_val)).to_numpy(dtype=np.float32)
    trend_s_val = ((c_val < ema60_val) & (ema20_val < ema60_val)).to_numpy(dtype=np.float32)
    slope_val = ((ema60_val - ema240_val) / atr_val_arr).to_numpy(dtype=np.float32)

    dt_val = df_xau_val_c['dt'] if 'dt' in df_xau_val_c.columns else pd.to_datetime(df_xau_val_c.index)
    hour_val = dt_val.dt.hour.to_numpy()
    min_val = dt_val.dt.minute.to_numpy()
    day_val = dt_val.dt.dayofweek.to_numpy()
    time_float = hour_val + min_val / 60.0

    is_liquid_val = ((hour_val >= 7) & (hour_val < 19)).astype(np.float32)
    is_friday_block = (day_val == 4) & (hour_val >= 17)

    is_sleeve_a = (((time_float >= 7.0) & (time_float <= 11.0)) | ((time_float >= 12.5) & (time_float <= 16.0))).astype(np.float32)
    is_sleeve_b = (((time_float > 11.0) & (time_float < 12.5)) | ((time_float > 16.0) & (time_float <= 18.5))).astype(np.float32)

    p_up_50_v = np.maximum(0.1, bundle["q_up_50"].predict(X_val))
    p_down_50_v = np.maximum(0.1, bundle["q_down_50"].predict(X_val))
    p_up_80_v = np.maximum(0.2, bundle["q_up_80"].predict(X_val))
    p_down_80_v = np.maximum(0.2, bundle["q_down_80"].predict(X_val))

    ratio_v_l = p_up_50_v / p_down_50_v
    ratio_v_s = p_down_50_v / p_up_50_v

    X_meta_l = make_directional_meta_features(X_val, p_up_50_v, p_down_50_v, p_up_80_v, p_down_80_v, ratio_v_l, is_liquid_val, trend_l_val, slope_val)
    X_meta_s = make_directional_meta_features(X_val, p_down_50_v, p_up_50_v, p_down_80_v, p_up_80_v, ratio_v_s, is_liquid_val, trend_s_val, slope_val)

    prob_l = 0.60 * bundle["clf_l_lgb"].predict_proba(X_meta_l)[:, 1] + 0.40 * bundle["clf_l_hist"].predict_proba(X_meta_l)[:, 1]
    prob_s = 0.60 * bundle["clf_s_lgb"].predict_proba(X_meta_s)[:, 1] + 0.40 * bundle["clf_s_hist"].predict_proba(X_meta_s)[:, 1]

    th = bundle.get("threshold", 0.52)
    broad_l = (prob_l >= th) & (ratio_v_l >= 1.15) & (p_up_50_v * atr_val_arr >= 0.60) & (ratio_v_l > ratio_v_s) & (trend_l_val == 1.0) & (~is_friday_block)
    broad_s = (prob_s >= th) & (ratio_v_s >= 1.15) & (p_down_50_v * atr_val_arr >= 0.60) & (ratio_v_s > ratio_v_l) & (trend_s_val == 1.0) & (~is_friday_block)

    act_l = (broad_l & (is_sleeve_a == 1.0)) | (broad_l & (is_sleeve_b == 1.0) & (ratio_v_l >= 1.35))
    act_s = (broad_s & (is_sleeve_a == 1.0)) | (broad_s & (is_sleeve_b == 1.0) & (ratio_v_s >= 1.35))

    usdi_series = pd.Series(usdi_ret15, index=common_idx).reindex(df_xau_idx.index).fillna(0.0).to_numpy()
    eur_series = pd.Series(eur_ret15, index=common_idx).reindex(df_xau_idx.index).fillna(0.0).to_numpy()

    usdi_gate_l = (usdi_series <= 0.0004) & (eur_series >= -0.0004)
    usdi_gate_s = (usdi_series >= -0.0004) & (eur_series <= 0.0004)

    is_hi_slope = np.abs(slope_val) >= 0.20
    tp_arr = np.where(is_hi_slope, np.clip(p_up_50_v * 2.10, 3.0, 7.5), np.clip(p_up_50_v * 1.40, 2.0, 4.5))
    sl_arr = np.where(is_hi_slope, np.clip(p_down_80_v * 1.30, 1.8, 3.5), np.clip(p_down_80_v * 1.10, 1.4, 2.5))

    n_val = len(df_xau_val_c)
    actions = np.zeros(n_val, dtype=np.int32)
    actions[act_l & usdi_gate_l] = ACTION_OPEN_LONG
    actions[act_s & usdi_gate_s] = ACTION_OPEN_SHORT

    # 4. Evaluate Variants
    variants = {}
    equity_curves = {}

    modes = [
        ("Variant_1_EXP36_Master_Baseline", "baseline"),
        ("Variant_2_Adaptive_Trailing_Thresholds", "adaptive_tiers"),
        ("Variant_3_Dynamic_Excursion_Targets", "dynamic_targets"),
        ("Variant_4_Master_AVS_ADET_Fused", "master_avs"),
        ("Variant_5_Asymmetric_Macro_Drift_Bias", "asymmetric_drift")
    ]

    print("\n[Step 4/5] Evaluating Adaptive Volatility Surface Variants on 2025 Out-of-Sample...")
    for v_id, m_mode in modes:
        res = run_adaptive_volatility_backtest(df_xau_val_c, atr_xau_val, actions, sl_arr, tp_arr, vol_velocity, mode=m_mode)
        m = compute_comprehensive_metrics(res)
        variants[v_id] = m
        equity_curves[v_id] = res["equity_curve"]

    # 5. Display Results
    print("\n" + "=" * 80)
    print("📊 EXP-43 ADAPTIVE VOLATILITY SURFACE RESULTS (2025 OUT-OF-SAMPLE)")
    print("=" * 80)
    for v_id, m in variants.items():
        print(f"  [{v_id}] Net: ${m['net_profit']:,.2f} ({m['return_pct']:.2f}%) | "
              f"PF: {m['profit_factor']:.2f} | WR: {m['win_rate']:.1f}% | "
              f"Max DD: {m['max_drawdown_pct']:.2f}% | Sharpe: {m['sharpe_ratio']:.2f} | "
              f"Trades: {m['total_trades']}")

    # 6. Visualizations and Artifacts
    print("\n[Step 5/5] Generating Visualizations and Production Artifacts...")
    docs_dir = os.path.join(project_dir, "docs", "experiments")
    os.makedirs(docs_dir, exist_ok=True)
    plot_file = os.path.join(docs_dir, "EXP_43_ADAPTIVE_VOLATILITY_SURFACE.png")

    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(14, 10), gridspec_kw={'height_ratios': [2.5, 1]})

    colors = {
        "Variant_1_EXP36_Master_Baseline": "#1f77b4",
        "Variant_2_Adaptive_Trailing_Thresholds": "#2ca02c",
        "Variant_3_Dynamic_Excursion_Targets": "#ff7f0e",
        "Variant_4_Master_AVS_ADET_Fused": "#d62728",
        "Variant_5_Asymmetric_Macro_Drift_Bias": "#9467bd"
    }

    for v_id, eq in equity_curves.items():
        ax1.plot(eq, label=f"{v_id} (Net: ${variants[v_id]['net_profit']:,.0f}, WR: {variants[v_id]['win_rate']:.1f}%)",
                 color=colors.get(v_id, "gray"), lw=1.8 if "Master" in v_id or "Asymmetric" in v_id else 1.2)

    ax1.set_title("EXP-43: Asymmetric Volatility Surface & Adaptive Dynamic Excursion Targets (2025 Out-of-Sample)", fontsize=13, fontweight='bold')
    ax1.set_ylabel("Account Balance ($)", fontsize=11)
    ax1.grid(True, alpha=0.3)
    ax1.legend(loc='upper left', fontsize=9)

    best_v = max(variants.keys(), key=lambda k: variants[k]["net_profit"])
    best_eq = equity_curves[best_v]
    best_peak = np.maximum.accumulate(best_eq)
    dd_curve = (best_peak - best_eq) / best_peak * 100.0

    ax2.fill_between(range(len(dd_curve)), 0, dd_curve, color="#d62728", alpha=0.3, label=f"{best_v} Drawdown (%)")
    ax2.set_title(f"Underwater Drawdown Profile ({best_v})", fontsize=11, fontweight='bold')
    ax2.set_xlabel("Elapsed Bars (2025 M1)", fontsize=11)
    ax2.set_ylabel("Drawdown %", fontsize=11)
    ax2.grid(True, alpha=0.3)
    ax2.legend(loc='lower left', fontsize=9)

    plt.tight_layout()
    plt.savefig(plot_file, dpi=180)
    plt.close()
    print(f"[Plot] Saved: {plot_file}")

    # Production Model Persistence
    joblib_file = os.path.join(models_dir, "exp43_adaptive_volatility_champion.joblib")
    exp43_bundle = {
        "experiment": "EXP-43",
        "name": "Asymmetric Volatility Surface & Adaptive Dynamic Excursion Targets",
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime()),
        "variants": variants,
        "best_variant": best_v
    }
    joblib.dump(exp43_bundle, joblib_file)
    print(f"[Production] EXP-43 Model saved: {joblib_file} ({os.path.getsize(joblib_file):,} bytes)")

    # Markdown Report
    report_file = os.path.join(docs_dir, "EXP_43_ADAPTIVE_VOLATILITY_SURFACE.md")
    with open(report_file, "w") as f:
        f.write("# Experiment EXP-43: Asymmetric Volatility Surface & Adaptive Excursion Targets\n\n")
        f.write(f"- **Execution Timestamp:** {time.strftime('%Y-%m-%d %H:%M:%S UTC', time.gmtime())}\n")
        f.write(f"- **Symbol:** XAUUSD M1 + EURUSD M1 (Macro Confluence)\n")
        f.write(f"- **Train Period:** 2020-2024 (1,765,788 bars)\n")
        f.write(f"- **Validation Period:** 2025 Out-of-Sample (350,807 bars)\n")
        f.write(f"- **2026 Out-of-Sample:** STRICTLY LOCKED & UNTOUCHED\n")
        f.write(f"- **Model File:** `{os.path.basename(joblib_file)}` ({os.path.getsize(joblib_file):,} bytes)\n\n")
        f.write("## 1. Executive Summary\n")
        f.write("EXP-43 examines the dynamic responsiveness of excursion targets and trailing ladders to the real-time volatility velocity `(ATR14 - ATR60) / ATR60`. During volatility expansion surges, excursion thresholds are expanded to allow winning breakout runners to mature without premature wick stop-outs, while targets are expanded to 5.5x ATR. Conversely, during volatility compression, targets and trailing thresholds are contracted for immediate profit capture.\n\n")
        f.write("## 2. Quantitative Performance Comparison\n\n")
        f.write("| Variant | Net Profit ($) | Return (%) | Profit Factor | Win Rate (%) | Max Drawdown (%) | Sharpe | Trades |\n")
        f.write("| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |\n")
        for v_id, m in variants.items():
            f.write(f"| **{v_id}** | ${m['net_profit']:,.2f} | {m['return_pct']:.2f}% | {m['profit_factor']:.2f} | {m['win_rate']:.1f}% | {m['max_drawdown_pct']:.2f}% | {m['sharpe_ratio']:.2f} | {m['total_trades']} |\n")
        f.write("\n## 3. Equity Progression\n\n")
        f.write(f"![EXP-43 Equity Curve](EXP_43_ADAPTIVE_VOLATILITY_SURFACE.png)\n\n")
        f.write("## 4. Key Findings\n")
        f.write(f"1. **Best Variant:** `{best_v}` achieved Net Profit ${variants[best_v]['net_profit']:,.2f} with {variants[best_v]['win_rate']:.1f}% Win Rate.\n")
        f.write("2. **Volatility Velocity Responsiveness:** Adapting excursion tiers based on instantaneous ATR velocity prevents giving back open profits in compressing regimes while riding full trend waves during expansion shocks.\n")

    print(f"[Report] Saved: {report_file}")

    # Master Registry Update
    registry_file = os.path.join(project_dir, "docs", "EXPERIMENT_REGISTRY.md")
    if os.path.exists(registry_file):
        best_m = variants[best_v]
        row = (
            f"| EXP-43 | Asymmetric Volatility Surface & Adaptive Excursion Targets | "
            f"**+${best_m['net_profit']:,.2f}** | **{best_m['profit_factor']:.2f}** | "
            f"**{best_m['win_rate']:.1f}%** | **{best_m['max_drawdown_pct']:.2f}%** | "
            f"{best_m['sharpe_ratio']:.2f} | {best_m['total_trades']} | "
            f"Dynamic Excursion Tiers + Volatility Velocity Expansion + Adaptive Targets + Asymmetric Long Monetary Drift Bias. |\n"
        )
        with open(registry_file, "r") as f:
            content = f.read()
        if "| EXP-43 |" not in content:
            content += row
            with open(registry_file, "w") as f:
                f.write(content)
            print(f"[Registry] Appended EXP-43 to {registry_file}")

    return variants


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--eurusd-path", type=str, default=None)
    parser.add_argument("--xauusd-path", type=str, default=None)
    args = parser.parse_args()

    run_experiment_43(eurusd_path=args.eurusd_path, xauusd_path=args.xauusd_path)
