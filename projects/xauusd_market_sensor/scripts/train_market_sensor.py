"""
=============================================================================
XAUUSD Market Sensor: 30-Target Training & Evaluation Suite
=============================================================================
Algorithms:
1. Stage 1: LightGBM 30 Independent Classifiers
2. Stage 2: LightGBM Conditional Model (Unified Distribution Surface)
3. Stage 3: Multi-Head Neural Sensor (30 outputs) & ONNX Exporter (MT5 Ready)
Metrics:
- Log Loss, Brier Score, ROC-AUC, PR-AUC
- Expected Calibration Error (ECE - 10 Bins)
- Distance Monotonicity Violation Rate (%)
- Horizon Monotonicity Violation Rate (%)
=============================================================================
"""

import os
import sys
import json
import time
import shutil
import argparse
import numpy as np
import pandas as pd
import lightgbm as lgb
from sklearn.metrics import log_loss, brier_score_loss, roc_auc_score, average_precision_score
from sklearn.neural_network import MLPClassifier
from scipy.special import expit

import onnx
from onnx import helper, TensorProto
import onnxruntime as ort

from pipeline_market_sensor import (
    DIRECTIONS, DISTANCES, HORIZONS, TARGET_COLUMNS, FEATURE_COLUMNS,
    build_market_sensor_features, build_30_binary_targets, create_purged_splits
)

def evaluate_probabilistic_predictions(y_true: np.ndarray, y_prob: np.ndarray):
    """
    คำนวณ Metrics เชิงความน่าจะเป็นตามมาตรฐาน
    """
    eps = 1e-15
    y_prob_clipped = np.clip(y_prob, eps, 1.0 - eps)
    
    ll = log_loss(y_true, y_prob_clipped)
    brier = brier_score_loss(y_true, y_prob)
    
    try:
        auc = roc_auc_score(y_true, y_prob)
    except Exception:
        auc = 0.5
        
    try:
        pr_auc = average_precision_score(y_true, y_prob)
    except Exception:
        pr_auc = 0.0
        
    # Expected Calibration Error (ECE - 10 Bins)
    bin_edges = np.linspace(0.0, 1.0, 11)
    ece = 0.0
    n_samples = len(y_true)
    
    for i in range(10):
        bin_mask = (y_prob >= bin_edges[i]) & (y_prob < bin_edges[i+1])
        if np.sum(bin_mask) > 0:
            bin_acc = np.mean(y_true[bin_mask])
            bin_conf = np.mean(y_prob[bin_mask])
            ece += (np.sum(bin_mask) / n_samples) * np.abs(bin_acc - bin_conf)
            
    return {
        "log_loss": round(float(ll), 4),
        "brier_score": round(float(brier), 4),
        "roc_auc": round(float(auc), 4),
        "pr_auc": round(float(pr_auc), 4),
        "ece": round(float(ece), 4)
    }

def calculate_monotonicity_violations(prob_dict: dict, n_samples: int):
    """
    ตรวจสอบการละเมิดหลัก Monotonicity:
    1. Distance Monotonicity: P(D_i) >= P(D_{i+1})
    2. Horizon Monotonicity:  P(H_i) <= P(H_{i+1})
    """
    dist_violations = 0
    dist_checks = 0
    
    horizon_violations = 0
    horizon_checks = 0
    
    for d in DIRECTIONS:
        # 1. Check Distance Monotonicity (for each horizon)
        for h in HORIZONS:
            for i in range(len(DISTANCES) - 1):
                d_curr = DISTANCES[i]
                d_next = DISTANCES[i + 1]
                p_curr = prob_dict[f"target_{d}_{d_curr}_{h}"]
                p_next = prob_dict[f"target_{d}_{d_next}_{h}"]
                
                violations = np.sum(p_next > p_curr)
                dist_violations += violations
                dist_checks += n_samples
                
        # 2. Check Horizon Monotonicity (for each distance)
        for dist in DISTANCES:
            for i in range(len(HORIZONS) - 1):
                h_curr = HORIZONS[i]
                h_next = HORIZONS[i + 1]
                p_curr = prob_dict[f"target_{d}_{dist}_{h_curr}"]
                p_next = prob_dict[f"target_{d}_{dist}_{h_next}"]
                
                violations = np.sum(p_curr > p_next)
                horizon_violations += violations
                horizon_checks += n_samples
                
    dist_rate = (dist_violations / max(1, dist_checks)) * 100.0
    horizon_rate = (horizon_violations / max(1, horizon_checks)) * 100.0
    
    return {
        "distance_violation_rate_pct": round(dist_rate, 2),
        "horizon_violation_rate_pct": round(horizon_rate, 2),
        "total_dist_violations": int(dist_violations),
        "total_horizon_violations": int(horizon_violations)
    }

def build_and_export_onnx(weights, biases, output_path):
    """
    สร้าง ONNX Graph ด้วย onnx.helper สำหรับสถาปัตยกรรม Multi-Head Neural Sensor:
    Input [1, 22] -> Dense(64, ReLU) -> Dense(32, ReLU) -> Dense(30, Sigmoid) -> Output [1, 30]
    ตั้งค่า Opset 13 และ IR Version 8 เพื่อรองรับ MetaTrader 5 Build 6063+ โดยสมบูรณ์
    """
    W0, b0 = weights[0].astype(np.float32), biases[0].astype(np.float32)
    W1, b1 = weights[1].astype(np.float32), biases[1].astype(np.float32)
    W2, b2 = weights[2].astype(np.float32), biases[2].astype(np.float32)

    t_W0 = helper.make_tensor('W0', TensorProto.FLOAT, list(W0.shape), W0.flatten())
    t_b0 = helper.make_tensor('b0', TensorProto.FLOAT, list(b0.shape), b0.flatten())
    t_W1 = helper.make_tensor('W1', TensorProto.FLOAT, list(W1.shape), W1.flatten())
    t_b1 = helper.make_tensor('b1', TensorProto.FLOAT, list(b1.shape), b1.flatten())
    t_W2 = helper.make_tensor('W2', TensorProto.FLOAT, list(W2.shape), W2.flatten())
    t_b2 = helper.make_tensor('b2', TensorProto.FLOAT, list(b2.shape), b2.flatten())

    input_tensor = helper.make_tensor_value_info('input_market_state', TensorProto.FLOAT, [1, 22])
    output_tensor = helper.make_tensor_value_info('prob_surface_30', TensorProto.FLOAT, [1, 30])

    nodes = [
        helper.make_node('Gemm', ['input_market_state', 'W0', 'b0'], ['h0']),
        helper.make_node('Relu', ['h0'], ['a0']),
        helper.make_node('Gemm', ['a0', 'W1', 'b1'], ['h1']),
        helper.make_node('Relu', ['h1'], ['a1']),
        helper.make_node('Gemm', ['a1', 'W2', 'b2'], ['logits']),
        helper.make_node('Sigmoid', ['logits'], ['prob_surface_30'])
    ]

    graph = helper.make_graph(
        nodes,
        'xauusd_sensor_30heads',
        [input_tensor],
        [output_tensor],
        initializer=[t_W0, t_b0, t_W1, t_b1, t_W2, t_b2]
    )

    model = helper.make_model(graph, opset_imports=[helper.make_opsetid('', 13)])
    model.ir_version = 8

    onnx.checker.check_model(model)
    onnx.save(model, output_path)

    # ทดสอบรันด้วย ONNX Runtime เพื่อยืนยันความถูกต้อง
    sess = ort.InferenceSession(output_path)
    dummy_input = np.random.randn(1, 22).astype(np.float32)
    ort_out = sess.run(None, {'input_market_state': dummy_input})[0]
    
    assert ort_out.shape == (1, 30), f"Expected shape (1, 30), got {ort_out.shape}"
    assert 0.0 <= ort_out.min() and ort_out.max() <= 1.0, "Output out of probability range [0, 1]"
    print(f"✅ ONNX Model successfully verified! Shape: {ort_out.shape}, Output range: [{ort_out.min():.4f}, {ort_out.max():.4f}]", flush=True)

def main():
    parser = argparse.ArgumentParser(description="Train XAUUSD 30-Target Market Sensor")
    parser.add_argument("--data_path", type=str, default="/storage/emulated/0/Download/EA/XAUUSD.iux_M1_20200102_to_20251230.csv")
    parser.add_argument("--output_dir", type=str, default="/root/CFD-Trading-ML/models")
    parser.add_argument("--mql5_files_dir", type=str, default="/root/CFD-Trading-ML/mql5/Files")
    parser.add_argument("--max_train_samples", type=int, default=60000, help="Max train samples for fast robust training")
    args = parser.parse_args()
    
    os.makedirs(args.output_dir, exist_ok=True)
    os.makedirs(args.mql5_files_dir, exist_ok=True)
    
    print("=" * 70, flush=True)
    print("🚀 XAUUSD MARKET SENSOR: TRAINING 30-TARGET PROBABILITY SURFACE", flush=True)
    print("=" * 70, flush=True)
    print(f"📂 Loading dataset: {args.data_path}", flush=True)
    
    # 1. Load Data (Optimized memory)
    cols = ['datetime', 'open', 'high', 'low', 'close', 'tick_volume']
    dtypes = {'open': 'float32', 'high': 'float32', 'low': 'float32', 'close': 'float32', 'tick_volume': 'float32'}
    df = pd.read_csv(args.data_path, usecols=cols, dtype=dtypes)
    print(f"📊 Loaded {len(df):,} continuous M1 bars.", flush=True)
    
    # 2. Build Features
    print("⚙️ Engineering 22 Scale-Invariant Features...", flush=True)
    features_df, atr14, close = build_market_sensor_features(df)
    
    # 3. Build 30 Targets
    print("🎯 Engineering 30 Binary Targets (2 Dir x 5 Dist x 3 Horizons)...", flush=True)
    targets_df = build_30_binary_targets(df, atr14)
    
    # Drop warm-up & tail NaNs
    valid_mask = ~(features_df.isna().any(axis=1) | targets_df.isna().any(axis=1))
    features_df = features_df[valid_mask]
    targets_df = targets_df[valid_mask]
    df = df[valid_mask]
    
    print(f"✅ Clean dataset: {len(features_df):,} bars.", flush=True)
    
    # 4. Create Purged Splits
    print("✂️ Creating Purged Splits (Train 2020-2023 | Val 2024 | Dev 2025 | 2026 LOCKED)...", flush=True)
    train_idx, val_idx, dev_idx = create_purged_splits(df, max_horizon=90)
    print(f"   Train: {len(train_idx):,} bars (2020-2023)", flush=True)
    print(f"   Val:   {len(val_idx):,} bars (2024)", flush=True)
    print(f"   Dev:   {len(dev_idx):,} bars (2025)", flush=True)
    
    # Uniform Subsample for Training across 2020-2023
    if len(train_idx) > args.max_train_samples:
        step = int(np.ceil(len(train_idx) / args.max_train_samples))
        sampled_train_idx = train_idx[::step]
        print(f"⚡ Subsampled Train Set to {len(sampled_train_idx):,} bars (step={step}) across 2020-2023.", flush=True)
    else:
        sampled_train_idx = train_idx
        
    # Subsample validation & dev for snappy metrics calculation
    val_sample_idx = val_idx[::15] if len(val_idx) > 25000 else val_idx
    dev_sample_idx = dev_idx[::15] if len(dev_idx) > 25000 else dev_idx
    print(f"📊 Evaluation set sizes: Val={len(val_sample_idx):,}, Dev={len(dev_sample_idx):,}", flush=True)
    
    X_train = features_df.loc[sampled_train_idx].values.astype(np.float32)
    X_val = features_df.loc[val_sample_idx].values.astype(np.float32)
    X_dev = features_df.loc[dev_sample_idx].values.astype(np.float32)
    
    # =========================================================================
    # STAGE 1: LightGBM 30 Independent Classifiers
    # =========================================================================
    print("\n" + "=" * 70, flush=True)
    print("🏆 STAGE 1: TRAINING 30 INDEPENDENT LIGHTGBM CLASSIFIERS", flush=True)
    print("=" * 70, flush=True)
    
    lgb_val_preds = {}
    lgb_dev_preds = {}
    stage1_results = {}
    
    t0 = time.time()
    for i, col in enumerate(TARGET_COLUMNS):
        y_train = targets_df.loc[sampled_train_idx, col].values.astype(np.int8)
        y_val = targets_df.loc[val_sample_idx, col].values.astype(np.int8)
        y_dev = targets_df.loc[dev_sample_idx, col].values.astype(np.int8)
        
        clf = lgb.LGBMClassifier(
            n_estimators=40,
            learning_rate=0.08,
            num_leaves=25,
            max_depth=5,
            random_state=42,
            n_jobs=4,
            objective='binary',
            verbosity=-1
        )
        
        clf.fit(X_train, y_train)
        
        p_val = clf.predict_proba(X_val)[:, 1]
        p_dev = clf.predict_proba(X_dev)[:, 1]
        
        lgb_val_preds[col] = p_val
        lgb_dev_preds[col] = p_dev
        
        metrics_val = evaluate_probabilistic_predictions(y_val, p_val)
        metrics_dev = evaluate_probabilistic_predictions(y_dev, p_dev)
        
        stage1_results[col] = {
            "validation_2024": metrics_val,
            "development_2025": metrics_dev
        }
        
        print(f"[{i+1:02d}/30] {col:22s} | Val AUC: {metrics_val['roc_auc']:.3f} | Brier: {metrics_val['brier_score']:.3f} | Dev AUC: {metrics_dev['roc_auc']:.3f}", flush=True)
            
    stage1_time = time.time() - t0
    print(f"⏱️ 30 LightGBM Models trained in {stage1_time:.1f}s.", flush=True)
    
    # Monotonicity Checks for Stage 1
    mono_val_s1 = calculate_monotonicity_violations(lgb_val_preds, len(val_sample_idx))
    mono_dev_s1 = calculate_monotonicity_violations(lgb_dev_preds, len(dev_sample_idx))
    
    print("\n" + "-" * 70, flush=True)
    print("📐 STAGE 1 MONOTONICITY INTEGRITY:", flush=True)
    print(f"   Validation 2024 - Dist Violations: {mono_val_s1['distance_violation_rate_pct']:.2f}% | Horizon Violations: {mono_val_s1['horizon_violation_rate_pct']:.2f}%", flush=True)
    print(f"   Development 2025 - Dist Violations: {mono_dev_s1['distance_violation_rate_pct']:.2f}% | Horizon Violations: {mono_dev_s1['horizon_violation_rate_pct']:.2f}%", flush=True)
    print("-" * 70, flush=True)
    
    # =========================================================================
    # STAGE 2: Conditional LightGBM Model
    # =========================================================================
    print("\n" + "=" * 70, flush=True)
    print("🧠 STAGE 2: TRAINING CONDITIONAL LIGHTGBM MODEL P(reach | state, dir, D, H)", flush=True)
    print("=" * 70, flush=True)
    
    np.random.seed(42)
    sample_queries_n = min(40000, len(sampled_train_idx))
    chosen_idx = np.random.choice(sampled_train_idx, size=sample_queries_n, replace=False)
    
    cond_rows_X = []
    cond_rows_y = []
    for idx in chosen_idx:
        feat_vec = features_df.loc[idx].values
        for _ in range(2):
            d = np.random.choice(DIRECTIONS)
            dist = np.random.choice(DISTANCES)
            h = np.random.choice(HORIZONS)
            
            dir_code = 1.0 if d == 'up' else -1.0
            query_feat = np.append(feat_vec, [dir_code, dist, float(h)])
            label = targets_df.loc[idx, f"target_{d}_{dist}_{h}"]
            
            cond_rows_X.append(query_feat)
            cond_rows_y.append(label)
            
    cond_X = np.array(cond_rows_X, dtype=np.float32)
    cond_y = np.array(cond_rows_y, dtype=np.int8)
    
    cond_clf = lgb.LGBMClassifier(
        n_estimators=50,
        learning_rate=0.08,
        num_leaves=31,
        max_depth=5,
        random_state=42,
        n_jobs=4,
        objective='binary',
        verbosity=-1
    )
    cond_clf.fit(cond_X, cond_y)
    print("✅ Conditional LightGBM Model trained successfully!", flush=True)

    # =========================================================================
    # STAGE 3: Multi-Head Neural Sensor & Export to ONNX [1, 22] -> [1, 30]
    # =========================================================================
    print("\n" + "=" * 70, flush=True)
    print("🌐 STAGE 3: MULTI-HEAD NEURAL SENSOR (30 HEADS) & ONNX EXPORTER", flush=True)
    print("=" * 70, flush=True)
    
    Y_train_all = targets_df.loc[sampled_train_idx, TARGET_COLUMNS].values.astype(np.float32)
    Y_val_all = targets_df.loc[val_sample_idx, TARGET_COLUMNS].values.astype(np.float32)
    Y_dev_all = targets_df.loc[dev_sample_idx, TARGET_COLUMNS].values.astype(np.float32)
    
    print(f"🏋️ Training Multi-Head Neural Sensor on {len(X_train):,} samples (Hidden: 64 -> 32 -> 30)...", flush=True)
    mlp = MLPClassifier(
        hidden_layer_sizes=(64, 32),
        activation='relu',
        solver='adam',
        learning_rate_init=0.003,
        max_iter=15,
        batch_size=2048,
        random_state=42,
        verbose=True
    )
    mlp.fit(X_train, Y_train_all)
    
    # Calculate predictions on Val & Dev
    h0_val = np.maximum(0, X_val @ mlp.coefs_[0] + mlp.intercepts_[0])
    h1_val = np.maximum(0, h0_val @ mlp.coefs_[1] + mlp.intercepts_[1])
    val_probs_matrix = expit(h1_val @ mlp.coefs_[2] + mlp.intercepts_[2])
    
    h0_dev = np.maximum(0, X_dev @ mlp.coefs_[0] + mlp.intercepts_[0])
    h1_dev = np.maximum(0, h0_dev @ mlp.coefs_[1] + mlp.intercepts_[1])
    dev_probs_matrix = expit(h1_dev @ mlp.coefs_[2] + mlp.intercepts_[2])
    
    stage3_val_preds = {col: val_probs_matrix[:, i] for i, col in enumerate(TARGET_COLUMNS)}
    stage3_dev_preds = {col: dev_probs_matrix[:, i] for i, col in enumerate(TARGET_COLUMNS)}
    
    stage3_results = {}
    for i, col in enumerate(TARGET_COLUMNS):
        m_val = evaluate_probabilistic_predictions(Y_val_all[:, i], stage3_val_preds[col])
        m_dev = evaluate_probabilistic_predictions(Y_dev_all[:, i], stage3_dev_preds[col])
        stage3_results[col] = {
            "validation_2024": m_val,
            "development_2025": m_dev
        }
        
    mono_val_s3 = calculate_monotonicity_violations(stage3_val_preds, len(val_sample_idx))
    mono_dev_s3 = calculate_monotonicity_violations(stage3_dev_preds, len(dev_sample_idx))
    
    print("\n" + "-" * 70, flush=True)
    print("📐 STAGE 3 MULTI-HEAD NEURAL SENSOR MONOTONICITY INTEGRITY:", flush=True)
    print(f"   Validation 2024 - Dist Violations: {mono_val_s3['distance_violation_rate_pct']:.2f}% | Horizon Violations: {mono_val_s3['horizon_violation_rate_pct']:.2f}%", flush=True)
    print(f"   Development 2025 - Dist Violations: {mono_dev_s3['distance_violation_rate_pct']:.2f}% | Horizon Violations: {mono_dev_s3['horizon_violation_rate_pct']:.2f}%", flush=True)
    print("-" * 70, flush=True)
    
    # Export to ONNX
    onnx_filename = "xauusd_sensor_30heads.onnx"
    onnx_dest_model = os.path.join(args.output_dir, onnx_filename)
    onnx_dest_mql5 = os.path.join(args.mql5_files_dir, onnx_filename)
    
    print(f"📦 Exporting ONNX Model to {onnx_dest_model}...", flush=True)
    build_and_export_onnx(mlp.coefs_, mlp.intercepts_, onnx_dest_model)
    
    # Copy to MQL5/Files for MT5 immediate deployment
    shutil.copyfile(onnx_dest_model, onnx_dest_mql5)
    print(f"📋 Copied ONNX Model to MQL5 Files directory: {onnx_dest_mql5}", flush=True)
    
    # =========================================================================
    # Save Comprehensive Summary JSON
    # =========================================================================
    summary_path = os.path.join(args.output_dir, "market_sensor_summary.json")
    full_output = {
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "features": FEATURE_COLUMNS,
        "targets": TARGET_COLUMNS,
        "split": {
            "train_years": "2020-2023",
            "val_year": "2024",
            "dev_year": "2025",
            "blind_test_year": "2026 (LOCKED)",
            "purge_gap_bars": 90
        },
        "stage1_independent_lightgbm": {
            "targets_metrics": stage1_results,
            "monotonicity_eval": {
                "validation_2024": mono_val_s1,
                "development_2025": mono_dev_s1
            }
        },
        "stage3_multihead_neural_sensor": {
            "targets_metrics": stage3_results,
            "monotonicity_eval": {
                "validation_2024": mono_val_s3,
                "development_2025": mono_dev_s3
            }
        },
        "onnx_export": {
            "model_file": onnx_filename,
            "input_name": "input_market_state",
            "input_shape": [1, 22],
            "output_name": "prob_surface_30",
            "output_shape": [1, 30],
            "opset_version": 13,
            "ir_version": 8
        }
    }
    
    with open(summary_path, "w") as f:
        json.dump(full_output, f, indent=2)
    print(f"💾 Comprehensive Summary JSON saved to: {summary_path}", flush=True)
    
    print("\n" + "=" * 70, flush=True)
    print("🎉 ALL STAGES AND ONNX EXPORT COMPLETED SUCCESSFULLY!", flush=True)
    print("=" * 70, flush=True)

if __name__ == "__main__":
    main()
