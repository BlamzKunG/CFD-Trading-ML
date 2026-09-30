"""
=============================================================================
Export & Benchmark Champion Models Suite (EXP-24, EXP-26, EXP-27)
=============================================================================
Autonomous Quant ML Research - Mandatory Model Persistence Engine
Trains, saves, documents, and benchmarks the Top 3 Champion Models.
Dependencies: scikit-learn, lightgbm, joblib, pandas, numpy
NO CatBoost dependency -> 100% portable across Colab, Termux, and MT5!
=============================================================================
"""

import os
import sys
import time
import json
import joblib
import numpy as np
import pandas as pd
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
    run_closed_loop_backtest,
    find_dataset_file,
    ACTION_HOLD,
    ACTION_OPEN_LONG,
    ACTION_OPEN_SHORT
)
from scripts.run_research_experiment import compute_comprehensive_metrics

from sklearn.ensemble import HistGradientBoostingRegressor, HistGradientBoostingClassifier
import lightgbm as lgb


def compute_excursions(df_clean, c_ser, atr_ser, H_bars=30):
    h = df_clean['high'].to_numpy(dtype=np.float64)
    l = df_clean['low'].to_numpy(dtype=np.float64)
    c = c_ser.to_numpy(dtype=np.float64)
    atr = np.maximum(np.nan_to_num(atr_ser.to_numpy(dtype=np.float64), nan=0.5), 0.1)

    rev_h = pd.Series(h[::-1])
    rev_l = pd.Series(l[::-1])
    fwd_max_h = np.roll(rev_h.rolling(H_bars, min_periods=1).max().to_numpy()[::-1], -1)
    fwd_min_l = np.roll(rev_l.rolling(H_bars, min_periods=1).min().to_numpy()[::-1], -1)

    up = np.nan_to_num((fwd_max_h - c) / atr, nan=0.0, posinf=10.0, neginf=0.0)
    down = np.nan_to_num((c - fwd_min_l) / atr, nan=0.0, posinf=10.0, neginf=0.0)
    return up, down


def make_directional_meta_features(X_base, p_fwd_50, p_rev_50, p_fwd_80, p_rev_80, ratio, is_liq, trend_aligned, slope):
    extra = np.column_stack([
        p_fwd_50, p_rev_50, p_fwd_80, p_rev_80, ratio, is_liq, trend_aligned, slope
    ])
    return np.hstack([X_base, extra]).astype(np.float32)


def extract_volume_series(df_in, length):
    for col_name in ['tick_volume', 'real_volume', 'volume']:
        if col_name in df_in.columns:
            return df_in[col_name].to_numpy(dtype=np.float64)
    return np.ones(length, dtype=np.float64)


def main(data_path: Optional[str] = None):
    print("=" * 80)
    print("🚀 QUANT ML CHAMPION SUITE: TRAINING, PERSISTING & BENCHMARKING TOP 3 MODELS")
    print("=" * 80)

    # 1. Load Data
    csv_file = find_dataset_file(data_path)
    print(f"\n[DataLoader] Loading dataset from: {csv_file}")
    df_train, df_val = load_and_preprocess_data(csv_file)
    (feat_train, atr_train, close_train, df_train_clean), (feat_val, atr_val, close_val, df_val_clean) = prepare_market_features(df_train, df_val)

    # 2. Features for Train Set
    print("\n[Step 1/5] Extracting training signals & macro trend...")
    c_tr = close_train
    ema20_tr = c_tr.ewm(span=20, adjust=False).mean()
    ema60_tr = c_tr.ewm(span=60, adjust=False).mean()
    ema240_tr = c_tr.ewm(span=240, adjust=False).mean()

    trend_l_tr = ((c_tr > ema60_tr) & (ema20_tr > ema60_tr)).to_numpy(dtype=np.float32)
    trend_s_tr = ((c_tr < ema60_tr) & (ema20_tr < ema60_tr)).to_numpy(dtype=np.float32)
    slope_tr = ((ema60_tr - ema240_tr) / np.maximum(atr_train, 0.1)).fillna(0.0).to_numpy(dtype=np.float32)

    dt_train = df_train_clean['dt'] if 'dt' in df_train_clean.columns else pd.to_datetime(df_train_clean.index)
    hour_tr = dt_train.dt.hour.to_numpy()
    is_liquid_tr = ((hour_tr >= 7) & (hour_tr < 19)).astype(np.float32)

    # Features for Val Set (2025)
    c_val = close_val
    ema20_val = c_val.ewm(span=20, adjust=False).mean()
    ema60_val = c_val.ewm(span=60, adjust=False).mean()
    ema240_val = c_val.ewm(span=240, adjust=False).mean()

    trend_l_val = ((c_val > ema60_val) & (ema20_val > ema60_val)).to_numpy(dtype=np.float32)
    trend_s_val = ((c_val < ema60_val) & (ema20_val < ema60_val)).to_numpy(dtype=np.float32)
    slope_val = ((ema60_val - ema240_val) / np.maximum(atr_val, 0.1)).fillna(0.0).to_numpy(dtype=np.float32)

    # H1 Macro Trend (600 bars = 10h, 1800 bars = 30h)
    ema_h1_fast = c_val.ewm(span=600, adjust=False).mean()
    ema_h1_slow = c_val.ewm(span=1800, adjust=False).mean()
    h1_bullish_val = ((c_val > ema_h1_fast) & (ema_h1_fast > ema_h1_slow)).to_numpy(dtype=np.float32)
    h1_bearish_val = ((c_val < ema_h1_fast) & (ema_h1_fast < ema_h1_slow)).to_numpy(dtype=np.float32)

    # Volume extraction
    vol_val = extract_volume_series(df_val_clean, len(c_val))
    vol_ma20_val = pd.Series(vol_val).rolling(20, min_periods=1).mean().to_numpy()
    vol_ratio_val = vol_val / np.maximum(vol_ma20_val, 1e-4)
    is_vol_active = (vol_ratio_val >= 1.00).astype(np.float32)

    dt_val = df_val_clean['dt'] if 'dt' in df_val_clean.columns else pd.to_datetime(df_val_clean.index)
    hour_val = dt_val.dt.hour.to_numpy()
    minute_val = dt_val.dt.minute.to_numpy()
    day_val = dt_val.dt.dayofweek.to_numpy()

    is_liquid_val = ((hour_val >= 7) & (hour_val < 19)).astype(np.float32)
    is_peak_window_val = ((hour_val >= 8) & (hour_val < 16)).astype(np.float32)

    time_float = hour_val + minute_val / 60.0
    is_dual_open_val = (((time_float >= 7.0) & (time_float <= 11.0)) | ((time_float >= 12.5) & (time_float <= 16.0))).astype(np.float32)
    is_sleeve_a = is_dual_open_val
    is_sleeve_b = (((time_float > 11.0) & (time_float < 12.5)) | ((time_float > 16.0) & (time_float <= 18.5))).astype(np.float32)
    is_friday_block_entry = (day_val == 4) & (hour_val >= 17)

    # 3. Train Quantile Regressors
    print("\n[Step 2/5] Training 4-head Excursion Quantile Regressors (2020-2024)...")
    up_tr_30, down_tr_30 = compute_excursions(df_train_clean, close_train, atr_train, 30)

    step = 6
    sub_idx = np.arange(0, len(df_train_clean) - 60, step)
    X_train_sub = np.nan_to_num(feat_train.iloc[sub_idx].to_numpy(dtype=np.float32), nan=0.0, posinf=0.0, neginf=0.0)
    atr_sub = np.maximum(atr_train.iloc[sub_idx].to_numpy(dtype=np.float64), 0.1)

    q_up_30_50 = HistGradientBoostingRegressor(loss='quantile', quantile=0.50, max_iter=100, max_depth=5, learning_rate=0.08, random_state=42)
    q_down_30_50 = HistGradientBoostingRegressor(loss='quantile', quantile=0.50, max_iter=100, max_depth=5, learning_rate=0.08, random_state=42)
    q_up_30_80 = HistGradientBoostingRegressor(loss='quantile', quantile=0.80, max_iter=100, max_depth=5, learning_rate=0.08, random_state=42)
    q_down_30_80 = HistGradientBoostingRegressor(loss='quantile', quantile=0.80, max_iter=100, max_depth=5, learning_rate=0.08, random_state=42)

    q_up_30_50.fit(X_train_sub, up_tr_30[sub_idx])
    q_down_30_50.fit(X_train_sub, down_tr_30[sub_idx])
    q_up_30_80.fit(X_train_sub, up_tr_30[sub_idx])
    q_down_30_80.fit(X_train_sub, down_tr_30[sub_idx])

    # In-sample candidate filter
    p_up_50_tr = np.maximum(0.1, q_up_30_50.predict(X_train_sub))
    p_down_50_tr = np.maximum(0.1, q_down_30_50.predict(X_train_sub))
    p_up_80_tr = np.maximum(0.2, q_up_30_80.predict(X_train_sub))
    p_down_80_tr = np.maximum(0.2, q_down_30_80.predict(X_train_sub))

    ratio_tr_l = p_up_50_tr / p_down_50_tr
    ratio_tr_s = p_down_50_tr / p_up_50_tr

    dist_ema200_tr = feat_train['dist_ema200'].iloc[sub_idx].to_numpy() if 'dist_ema200' in feat_train.columns else np.zeros(len(sub_idx))
    atr_ratio_tr = feat_train['atr_ratio'].iloc[sub_idx].to_numpy() if 'atr_ratio' in feat_train.columns else np.ones(len(sub_idx))

    cand_tr_l = (ratio_tr_l >= 1.15) & (p_up_50_tr * atr_sub >= 0.60) & (ratio_tr_l > ratio_tr_s) & (dist_ema200_tr >= -0.5) & (atr_ratio_tr >= 0.85)
    cand_tr_s = (ratio_tr_s >= 1.15) & (p_down_50_tr * atr_sub >= 0.60) & (ratio_tr_s > ratio_tr_l) & (dist_ema200_tr <= 0.5) & (atr_ratio_tr >= 0.85)

    y_meta_l = np.where((up_tr_30[sub_idx] >= p_up_50_tr * 1.50) & (down_tr_30[sub_idx] <= p_down_80_tr * 1.25), 1, 0)
    y_meta_s = np.where((down_tr_30[sub_idx] >= p_down_50_tr * 1.50) & (up_tr_30[sub_idx] <= p_up_80_tr * 1.25), 1, 0)

    cand_idx_l = np.where(cand_tr_l)[0]
    cand_idx_s = np.where(cand_tr_s)[0]

    X_meta_l = make_directional_meta_features(
        X_train_sub[cand_idx_l],
        p_up_50_tr[cand_idx_l], p_down_50_tr[cand_idx_l],
        p_up_80_tr[cand_idx_l], p_down_80_tr[cand_idx_l],
        ratio_tr_l[cand_idx_l], is_liquid_tr[sub_idx[cand_idx_l]],
        trend_l_tr[sub_idx[cand_idx_l]], slope_tr[sub_idx[cand_idx_l]]
    )
    y_meta_l_tr = y_meta_l[cand_idx_l]

    X_meta_s = make_directional_meta_features(
        X_train_sub[cand_idx_s],
        p_down_50_tr[cand_idx_s], p_up_50_tr[cand_idx_s],
        p_down_80_tr[cand_idx_s], p_up_80_tr[cand_idx_s],
        ratio_tr_s[cand_idx_s], is_liquid_tr[sub_idx[cand_idx_s]],
        trend_s_tr[sub_idx[cand_idx_s]], slope_tr[sub_idx[cand_idx_s]]
    )
    y_meta_s_tr = y_meta_s[cand_idx_s]

    # 4. Train Dual Directional Meta Classifiers (LightGBM 60% + HistGBDT 40% - No CatBoost!)
    print("\n[Step 3/5] Training Dual Directional Ensembles (LightGBM 60% + HistGBDT 40%)...")
    clf_l_lgb = lgb.LGBMClassifier(n_estimators=120, max_depth=5, learning_rate=0.07, random_state=101, verbose=-1, n_jobs=-1)
    clf_l_lgb.fit(X_meta_l, y_meta_l_tr)

    clf_l_hist = HistGradientBoostingClassifier(max_iter=120, max_depth=5, learning_rate=0.07, l2_regularization=1.5, random_state=101)
    clf_l_hist.fit(X_meta_l, y_meta_l_tr)

    clf_s_lgb = lgb.LGBMClassifier(n_estimators=120, max_depth=5, learning_rate=0.07, random_state=202, verbose=-1, n_jobs=-1)
    clf_s_lgb.fit(X_meta_s, y_meta_s_tr)

    clf_s_hist = HistGradientBoostingClassifier(max_iter=120, max_depth=5, learning_rate=0.07, l2_regularization=1.5, random_state=202)
    clf_s_hist.fit(X_meta_s, y_meta_s_tr)

    # 5. Out-of-Sample Predictions on 2025
    print("\n[Step 4/5] Vectorizing 2025 out-of-sample inferences...")
    X_val_all = np.nan_to_num(feat_val.to_numpy(dtype=np.float32), nan=0.0, posinf=0.0, neginf=0.0)
    atr_val_arr = np.maximum(atr_val.to_numpy(dtype=np.float64), 0.1)

    p_up_50_v = np.maximum(0.1, q_up_30_50.predict(X_val_all))
    p_down_50_v = np.maximum(0.1, q_down_30_50.predict(X_val_all))
    p_up_80_v = np.maximum(0.2, q_up_30_80.predict(X_val_all))
    p_down_80_v = np.maximum(0.2, q_down_30_80.predict(X_val_all))

    ratio_v_l = p_up_50_v / p_down_50_v
    ratio_v_s = p_down_50_v / p_up_50_v

    dist_ema200_v = feat_val['dist_ema200'].to_numpy() if 'dist_ema200' in feat_val.columns else np.zeros(len(X_val_all))
    atr_ratio_v = feat_val['atr_ratio'].to_numpy() if 'atr_ratio' in feat_val.columns else np.ones(len(X_val_all))

    cand_v_l = (ratio_v_l >= 1.15) & (p_up_50_v * atr_val_arr >= 0.60) & (ratio_v_l > ratio_v_s) & (dist_ema200_v >= -0.5) & (atr_ratio_v >= 0.85)
    cand_v_s = (ratio_v_s >= 1.15) & (p_down_50_v * atr_val_arr >= 0.60) & (ratio_v_s > ratio_v_l) & (dist_ema200_v <= 0.5) & (atr_ratio_v >= 0.85)

    X_meta_v_l = make_directional_meta_features(
        X_val_all, p_up_50_v, p_down_50_v, p_up_80_v, p_down_80_v, ratio_v_l, is_liquid_val, trend_l_val, slope_val
    )
    X_meta_v_s = make_directional_meta_features(
        X_val_all, p_down_50_v, p_up_50_v, p_down_80_v, p_up_80_v, ratio_v_s, is_liquid_val, trend_s_val, slope_val
    )

    p_l = 0.60 * clf_l_lgb.predict_proba(X_meta_v_l)[:, 1] + 0.40 * clf_l_hist.predict_proba(X_meta_v_l)[:, 1]
    p_s = 0.60 * clf_s_lgb.predict_proba(X_meta_v_s)[:, 1] + 0.40 * clf_s_hist.predict_proba(X_meta_v_s)[:, 1]

    n_val = len(df_val_clean)
    th = 0.47

    # Base conditions
    broad_l = cand_v_l & (p_l >= th) & (is_liquid_val == 1.0) & (trend_l_val == 1.0) & (h1_bullish_val == 1.0) & (~is_friday_block_entry)
    broad_s = cand_v_s & (p_s >= th) & (is_liquid_val == 1.0) & (trend_s_val == 1.0) & (h1_bearish_val == 1.0) & (~is_friday_block_entry)

    def passive_predictor(state_1x40: np.ndarray) -> Tuple[int, float, float, float]:
        return ACTION_HOLD, 0.0, 2.0, 3.5

    models_dir = os.path.join(project_dir, "models")
    os.makedirs(models_dir, exist_ok=True)

    # =========================================================================
    # MODEL 1: EXP-24 Surgical Ultra-Precision Filter
    # =========================================================================
    print("\n" + "=" * 60)
    print("🥇 EVALUATING & SAVING EXP-24: SURGICAL ULTRA-PRECISION FILTER")
    print("=" * 60)
    act_exp24_l = broad_l & (is_peak_window_val == 1.0) & (is_vol_active == 1.0)
    act_exp24_s = broad_s & (is_peak_window_val == 1.0) & (is_vol_active == 1.0)

    all_actions_24 = np.zeros(n_val, dtype=np.int32)
    all_sizes_24 = np.full(n_val, 0.10, dtype=np.float32)
    all_sl_24 = np.full(n_val, 2.0, dtype=np.float32)
    all_tp_24 = np.full(n_val, 3.5, dtype=np.float32)

    all_actions_24[act_exp24_l] = ACTION_OPEN_LONG
    all_actions_24[act_exp24_s] = ACTION_OPEN_SHORT

    is_tr_24_l = np.abs(slope_val[act_exp24_l]) >= 0.20
    all_tp_24[act_exp24_l] = np.where(is_tr_24_l, np.clip(p_up_50_v[act_exp24_l] * 2.10, 3.0, 7.5), np.clip(p_up_50_v[act_exp24_l] * 1.40, 2.0, 4.5))
    all_sl_24[act_exp24_l] = np.where(is_tr_24_l, np.clip(p_down_80_v[act_exp24_l] * 1.30, 1.8, 3.5), np.clip(p_down_80_v[act_exp24_l] * 1.10, 1.4, 2.5))

    is_tr_24_s = np.abs(slope_val[act_exp24_s]) >= 0.20
    all_tp_24[act_exp24_s] = np.where(is_tr_24_s, np.clip(p_down_50_v[act_exp24_s] * 2.10, 3.0, 7.5), np.clip(p_down_50_v[act_exp24_s] * 1.40, 2.0, 4.5))
    all_sl_24[act_exp24_s] = np.where(is_tr_24_s, np.clip(p_up_80_v[act_exp24_s] * 1.30, 1.8, 3.5), np.clip(p_up_80_v[act_exp24_s] * 1.10, 1.4, 2.5))

    res_24 = run_closed_loop_backtest(
        df=df_val_clean, market_features=feat_val, atr_series=atr_val,
        policy_predictor=passive_predictor, initial_balance=10000.0,
        lot_base=0.1, spread_points=2.0, slippage_points=1.0, commission_per_lot=6.0,
        precomputed_flat=(all_actions_24, all_sizes_24, all_sl_24, all_tp_24)
    )
    m24 = compute_comprehensive_metrics(res_24)
    print(f"  [EXP-24 Result] Net: ${m24['net_profit']:,.2f} | PF: {m24['profit_factor']:.2f} | WR: {m24['win_rate']:.1f}% | DD: {m24['max_drawdown_pct']:.1f}% | Trades: {m24['total_trades']}")

    # Save Model Bundle 24
    bundle_24_path = os.path.join(models_dir, "exp24_surgical_precision.joblib")
    bundle_24 = {
        "model_id": "EXP-24-SURGICAL-PRECISION",
        "clf_l_lgb": clf_l_lgb, "clf_l_hist": clf_l_hist,
        "clf_s_lgb": clf_s_lgb, "clf_s_hist": clf_s_hist,
        "q_up_50": q_up_30_50, "q_down_50": q_down_30_50,
        "q_up_80": q_up_30_80, "q_down_80": q_down_30_80,
        "weights": {"lgb": 0.60, "hist": 0.40},
        "threshold": th,
        "metrics_2025": m24
    }
    joblib.dump(bundle_24, bundle_24_path, compress=3)
    print(f"  [Saved] Bundle persisted to: {bundle_24_path} ({os.path.getsize(bundle_24_path)/1024:.1f} KB)")

    # =========================================================================
    # MODEL 2: EXP-26 Concentrated Dual-Open Breakout
    # =========================================================================
    print("\n" + "=" * 60)
    print("🥈 EVALUATING & SAVING EXP-26: CONCENTRATED DUAL-OPEN BREAKOUT")
    print("=" * 60)
    act_exp26_l = broad_l & (is_dual_open_val == 1.0)
    act_exp26_s = broad_s & (is_dual_open_val == 1.0)

    all_actions_26 = np.zeros(n_val, dtype=np.int32)
    all_sizes_26 = np.full(n_val, 0.08, dtype=np.float32)
    all_sl_26 = np.full(n_val, 2.0, dtype=np.float32)
    all_tp_26 = np.full(n_val, 3.5, dtype=np.float32)

    all_actions_26[act_exp26_l] = ACTION_OPEN_LONG
    all_actions_26[act_exp26_s] = ACTION_OPEN_SHORT

    is_hi_conv_l = np.abs(slope_val[act_exp26_l]) >= 0.30
    all_sizes_26[act_exp26_l] = np.where(is_hi_conv_l, 0.18, 0.08)

    is_hi_conv_s = np.abs(slope_val[act_exp26_s]) >= 0.30
    all_sizes_26[act_exp26_s] = np.where(is_hi_conv_s, 0.18, 0.08)

    is_tr_26_l = np.abs(slope_val[act_exp26_l]) >= 0.20
    all_tp_26[act_exp26_l] = np.where(is_tr_26_l, np.clip(p_up_50_v[act_exp26_l] * 2.10, 3.0, 7.5), np.clip(p_up_50_v[act_exp26_l] * 1.40, 2.0, 4.5))
    all_sl_26[act_exp26_l] = np.where(is_tr_26_l, np.clip(p_down_80_v[act_exp26_l] * 1.30, 1.8, 3.5), np.clip(p_down_80_v[act_exp26_l] * 1.10, 1.4, 2.5))

    is_tr_26_s = np.abs(slope_val[act_exp26_s]) >= 0.20
    all_tp_26[act_exp26_s] = np.where(is_tr_26_s, np.clip(p_down_50_v[act_exp26_s] * 2.10, 3.0, 7.5), np.clip(p_down_50_v[act_exp26_s] * 1.40, 2.0, 4.5))
    all_sl_26[act_exp26_s] = np.where(is_tr_26_s, np.clip(p_up_80_v[act_exp26_s] * 1.30, 1.8, 3.5), np.clip(p_up_80_v[act_exp26_s] * 1.10, 1.4, 2.5))

    res_26 = run_closed_loop_backtest(
        df=df_val_clean, market_features=feat_val, atr_series=atr_val,
        policy_predictor=passive_predictor, initial_balance=10000.0,
        lot_base=0.1, spread_points=2.0, slippage_points=1.0, commission_per_lot=6.0,
        precomputed_flat=(all_actions_26, all_sizes_26, all_sl_26, all_tp_26)
    )
    m26 = compute_comprehensive_metrics(res_26)
    print(f"  [EXP-26 Result] Net: ${m26['net_profit']:,.2f} | PF: {m26['profit_factor']:.2f} | WR: {m26['win_rate']:.1f}% | DD: {m26['max_drawdown_pct']:.1f}% | Trades: {m26['total_trades']}")

    # Save Model Bundle 26
    bundle_26_path = os.path.join(models_dir, "exp26_dual_open_breakout.joblib")
    bundle_26 = {
        "model_id": "EXP-26-DUAL-OPEN-BREAKOUT",
        "clf_l_lgb": clf_l_lgb, "clf_l_hist": clf_l_hist,
        "clf_s_lgb": clf_s_lgb, "clf_s_hist": clf_s_hist,
        "q_up_50": q_up_30_50, "q_down_50": q_down_30_50,
        "q_up_80": q_up_30_80, "q_down_80": q_down_30_80,
        "weights": {"lgb": 0.60, "hist": 0.40},
        "threshold": th,
        "metrics_2025": m26
    }
    joblib.dump(bundle_26, bundle_26_path, compress=3)
    print(f"  [Saved] Bundle persisted to: {bundle_26_path} ({os.path.getsize(bundle_26_path)/1024:.1f} KB)")

    # =========================================================================
    # MODEL 3: EXP-27 Cross-Session Dual-Sleeve
    # =========================================================================
    print("\n" + "=" * 60)
    print("🥉 EVALUATING & SAVING EXP-27: CROSS-SESSION DUAL-SLEEVE")
    print("=" * 60)
    slv_a_l = broad_l & (is_sleeve_a == 1.0)
    slv_a_s = broad_s & (is_sleeve_a == 1.0)
    slv_b_l = broad_l & (is_sleeve_b == 1.0) & (ratio_v_l >= 1.35)
    slv_b_s = broad_s & (is_sleeve_b == 1.0) & (ratio_v_s >= 1.35)

    act_exp27_l = slv_a_l | slv_b_l
    act_exp27_s = slv_a_s | slv_b_s

    all_actions_27 = np.zeros(n_val, dtype=np.int32)
    all_sizes_27 = np.full(n_val, 0.10, dtype=np.float32)
    all_sl_27 = np.full(n_val, 2.0, dtype=np.float32)
    all_tp_27 = np.full(n_val, 3.5, dtype=np.float32)

    all_actions_27[act_exp27_l] = ACTION_OPEN_LONG
    all_actions_27[act_exp27_s] = ACTION_OPEN_SHORT

    all_sizes_27[slv_a_l] = 0.18
    all_sizes_27[slv_a_s] = 0.18
    all_sizes_27[slv_b_l] = 0.06
    all_sizes_27[slv_b_s] = 0.06

    is_tr_27_l = np.abs(slope_val[act_exp27_l]) >= 0.20
    all_tp_27[act_exp27_l] = np.where(is_tr_27_l, np.clip(p_up_50_v[act_exp27_l] * 2.10, 3.0, 7.5), np.clip(p_up_50_v[act_exp27_l] * 1.40, 2.0, 4.5))
    all_sl_27[act_exp27_l] = np.where(is_tr_27_l, np.clip(p_down_80_v[act_exp27_l] * 1.30, 1.8, 3.5), np.clip(p_down_80_v[act_exp27_l] * 1.10, 1.4, 2.5))

    is_tr_27_s = np.abs(slope_val[act_exp27_s]) >= 0.20
    all_tp_27[act_exp27_s] = np.where(is_tr_27_s, np.clip(p_down_50_v[act_exp27_s] * 2.10, 3.0, 7.5), np.clip(p_down_50_v[act_exp27_s] * 1.40, 2.0, 4.5))
    all_sl_27[act_exp27_s] = np.where(is_tr_27_s, np.clip(p_up_80_v[act_exp27_s] * 1.30, 1.8, 3.5), np.clip(p_up_80_v[act_exp27_s] * 1.10, 1.4, 2.5))

    res_27 = run_closed_loop_backtest(
        df=df_val_clean, market_features=feat_val, atr_series=atr_val,
        policy_predictor=passive_predictor, initial_balance=10000.0,
        lot_base=0.1, spread_points=2.0, slippage_points=1.0, commission_per_lot=6.0,
        precomputed_flat=(all_actions_27, all_sizes_27, all_sl_27, all_tp_27)
    )
    m27 = compute_comprehensive_metrics(res_27)
    print(f"  [EXP-27 Result] Net: ${m27['net_profit']:,.2f} | PF: {m27['profit_factor']:.2f} | WR: {m27['win_rate']:.1f}% | DD: {m27['max_drawdown_pct']:.1f}% | Trades: {m27['total_trades']}")

    # Save Model Bundle 27
    bundle_27_path = os.path.join(models_dir, "exp27_cross_session_dual_sleeve.joblib")
    bundle_27 = {
        "model_id": "EXP-27-CROSS-SESSION-DUAL-SLEEVE",
        "clf_l_lgb": clf_l_lgb, "clf_l_hist": clf_l_hist,
        "clf_s_lgb": clf_s_lgb, "clf_s_hist": clf_s_hist,
        "q_up_50": q_up_30_50, "q_down_50": q_down_30_50,
        "q_up_80": q_up_30_80, "q_down_80": q_down_30_80,
        "weights": {"lgb": 0.60, "hist": 0.40},
        "threshold": th,
        "metrics_2025": m27
    }
    joblib.dump(bundle_27, bundle_27_path, compress=3)
    print(f"  [Saved] Bundle persisted to: {bundle_27_path} ({os.path.getsize(bundle_27_path)/1024:.1f} KB)")

    # Save Master Summary Metadata
    meta_summary_path = os.path.join(models_dir, "champion_models_registry.json")
    summary_data = {
        "export_timestamp": time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime()),
        "dataset_train": "2020-2024",
        "dataset_val": "2025 Out-of-Sample",
        "models": {
            "EXP-24": {"name": "Surgical Ultra-Precision", "file": "exp24_surgical_precision.joblib", "metrics": m24},
            "EXP-26": {"name": "Concentrated Dual-Open", "file": "exp26_dual_open_breakout.joblib", "metrics": m26},
            "EXP-27": {"name": "Cross-Session Dual-Sleeve", "file": "exp27_cross_session_dual_sleeve.joblib", "metrics": m27}
        }
    }
    with open(meta_summary_path, "w") as f:
        json.dump(summary_data, f, indent=2)
    print(f"\n[Registry] Master Champion Registry written to: {meta_summary_path}")
    print("\n" + "=" * 80)
    print("🎉 ALL TOP 3 CHAMPION MODELS PERSISTED AND BENCHMARKED SUCCESSFULLY!")
    print("=" * 80)


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-path", type=str, default=None)
    args = parser.parse_args()
    main(args.data_path)
