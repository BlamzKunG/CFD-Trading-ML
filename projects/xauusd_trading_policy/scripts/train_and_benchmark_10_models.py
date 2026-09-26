"""
=============================================================================
10 Quant ML Trading Policy Models: Unified Training, ONNX Export & Benchmark
=============================================================================
Orchestrates end-to-end training and closed-loop backtesting for 10 distinct
machine learning paradigms on XAUUSD M1 CFD data:
1.  M1_LightGBM          (Histogram GBDT, Leaf-wise growth, Balanced)
2.  M2_CatBoost          (Ordered Boosting, Oblivious Symmetric Trees)
3.  M3_XGBoost           (Depth-Constrained Regularized GBDT)
4.  M4_ResMLP            (Deep Residual Multi-Head MLP)
5.  M5_TCN               (Temporal ConvNet with Causal Dilated Convolutions)
6.  M6_GRU_Attention     (GRU with Temporal Attention Mechanism)
7.  M7_PatchTransformer  (Self-Attention Time-Series Transformer)
8.  M8_MetaLabeling      (Two-Stage Direction Filter + Bet Sizing Meta-Model)
9.  M9_CostSensitive     (Asymmetric Turnover-Penalized Policy Net)
10. M10_ActorCritic_RL   (Deep Reinforcement Learning Policy + Value Net)

Strict Quant ML Principles Applied:
- Scale-Invariant Normalized Inputs (0 raw prices)
- Strict Chronological Train/Val split (2020-2024 train, 2025 val, 2026 locked)
- Dynamic 9-feature Position State feedback in closed loop
- Friction-aware transaction costs ($0.20 spread, $0.10 slippage, $6.0/lot comm)
- Confidence thresholds and action masking to prevent turnover churn
=============================================================================
"""

import os
import sys
import json
import time
import argparse
from typing import Dict, Any, List, Tuple, Optional

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

# Dynamic path resolution
script_dir = os.path.dirname(os.path.abspath(__file__))
project_dir = os.path.dirname(script_dir)
root_repo_dir = os.path.dirname(os.path.dirname(project_dir))
for p in [root_repo_dir, project_dir, script_dir]:
    if p not in sys.path:
        sys.path.insert(0, p)

# Imports from project modules
from scripts.features_policy import (
    extract_market_state_features,
    MARKET_FEATURE_NAMES,
    POSITION_FEATURE_NAMES
)
from scripts.counterfactual_simulator import (
    build_augmented_training_dataset,
    ACTION_NAMES
)
from scripts.models_architecture import (
    LightGBMPolicy,
    CatBoostPolicy,
    XGBoostPolicy,
    TwoStageMetaLabelingPolicy,
    TORCH_AVAILABLE,
    LGB_AVAILABLE,
    CATBOOST_AVAILABLE,
    XGB_AVAILABLE
)

if TORCH_AVAILABLE:
    import torch
    import torch.nn as nn
    import torch.optim as optim
    from torch.utils.data import TensorDataset, DataLoader
    from scripts.models_architecture import (
        ResMLPPolicy,
        TCNPolicy,
        GRUAttentionPolicy,
        PatchTransformerPolicy,
        CostSensitivePolicyNet,
        CostSensitiveLoss,
        ActorCriticPolicyNet
    )

from scripts.hyperparameter_tuning import (
    TUNED_HYPERPARAMETERS,
    get_tuned_hyperparameters
)
from scripts.backtest_policy_evaluator import run_closed_loop_backtest


ALL_MODELS = [
    "M1_LightGBM",
    "M2_CatBoost",
    "M3_XGBoost",
    "M4_ResMLP",
    "M5_TCN",
    "M6_GRU_Attention",
    "M7_PatchTransformer",
    "M8_MetaLabeling",
    "M9_CostSensitive",
    "M10_ActorCritic_RL"
]


def find_dataset_file(custom_path: Optional[str] = None) -> str:
    """Locates the M1 dataset file across common paths."""
    candidates = [
        custom_path,
        "/content/XAUUSD_M1.csv.gz",
        "/content/xauusd_m1.csv",
        "/storage/emulated/0/Download/EA/XAUUSD_M1.csv.gz",
        "/storage/emulated/0/Download/EA/XAUUSD.iux_M1_20200102_to_20251230.csv",
        os.path.join(project_dir, "data", "XAUUSD_M1.csv.gz"),
        os.path.join(project_dir, "data", "xauusd_m1.csv")
    ]
    for c in candidates:
        if c and os.path.exists(c):
            return c
    raise FileNotFoundError(
        f"Could not find M1 dataset. Searched candidates: {[c for c in candidates if c]}"
    )


def load_and_preprocess_data(csv_path: str):
    """Loads, cleans, and splits dataset into 2020-2024 train and 2025 val."""
    print(f"\n[DataLoader] Loading dataset from: {csv_path}")
    t0 = time.time()
    
    if csv_path.endswith(".gz"):
        df = pd.read_csv(csv_path, compression="gzip")
    else:
        df = pd.read_csv(csv_path)
    print(f"[DataLoader] Read {len(df):,} rows in {time.time() - t0:.2f}s")

    # Rename columns to standard lower case
    df.columns = [c.strip().lower() for c in df.columns]

    # Timestamp parsing
    if 'datetime' in df.columns:
        df['dt'] = pd.to_datetime(df['datetime'])
    elif 'timestamp' in df.columns:
        df['dt'] = pd.to_datetime(df['timestamp'], unit='s')
    elif 'time' in df.columns:
        df['dt'] = pd.to_datetime(df['time'])
    else:
        df['dt'] = pd.to_datetime(df.index)

    df.sort_values('dt', inplace=True)
    df.reset_index(drop=True, inplace=True)

    # Chronological Split (Strict No-Leakage)
    # Train: 2020.01.01 to 2024.12.31
    # Val: 2025.01.01 to 2025.12.31
    # 2026: LOCKED
    train_mask = (df['dt'] >= '2020-01-01') & (df['dt'] < '2025-01-01')
    val_mask = (df['dt'] >= '2025-01-01') & (df['dt'] < '2026-01-01')

    df_train = df[train_mask].copy().reset_index(drop=True)
    df_val = df[val_mask].copy().reset_index(drop=True)

    print(f"[DataLoader] Train Set (2020-2024): {len(df_train):,} bars ({df_train['dt'].min()} to {df_train['dt'].max()})")
    print(f"[DataLoader] Val Set   (2025):      {len(df_val):,} bars ({df_val['dt'].min()} to {df_val['dt'].max()})")
    print(f"[DataLoader] 2026 Out-of-Sample:    LOCKED & UNTOUCHED")

    return df_train, df_val


def prepare_market_features(df_train: pd.DataFrame, df_val: pd.DataFrame, warmup: int = 200):
    """Computes 31 scale-invariant stationary market features."""
    print("\n[Features] Extracting 31 scale-invariant market state features...")
    feat_train, atr_train, close_train = extract_market_state_features(df_train)
    feat_val, atr_val, close_val = extract_market_state_features(df_val)

    # Drop warmup bars
    feat_train = feat_train.iloc[warmup:].fillna(0.0).reset_index(drop=True)
    df_train = df_train.iloc[warmup:].reset_index(drop=True)
    atr_train = atr_train.iloc[warmup:].reset_index(drop=True)
    close_train = close_train.iloc[warmup:].reset_index(drop=True)

    feat_val = feat_val.iloc[warmup:].fillna(0.0).reset_index(drop=True)
    df_val = df_val.iloc[warmup:].reset_index(drop=True)
    atr_val = atr_val.iloc[warmup:].reset_index(drop=True)
    close_val = close_val.iloc[warmup:].reset_index(drop=True)

    return (feat_train, atr_train, close_train, df_train), (feat_val, atr_val, close_val, df_val)


# =====================================================================
# PYTORCH MODEL TRAINING ENGINE
# =====================================================================

def train_pytorch_variant(
    model: "nn.Module",
    model_name: str,
    X_train: np.ndarray,
    y_act_train: np.ndarray,
    y_sz_train: np.ndarray,
    y_sl_train: np.ndarray,
    y_tp_train: np.ndarray,
    hparams: Dict[str, Any],
    device: str
) -> "nn.Module":
    """Trains a PyTorch Policy variant using its tuned hyperparameters."""
    epochs = hparams.get("epochs", 25)
    batch_size = hparams.get("batch_size", 1024)
    lr = hparams.get("lr", 8e-4)
    weight_decay = hparams.get("weight_decay", 1e-4)

    y_order_train = np.stack([y_sl_train, y_tp_train], axis=1)
    dataset = TensorDataset(
        torch.tensor(X_train, dtype=torch.float32),
        torch.tensor(y_act_train, dtype=torch.long),
        torch.tensor(y_sz_train, dtype=torch.float32).unsqueeze(1),
        torch.tensor(y_order_train, dtype=torch.float32)
    )
    loader = DataLoader(dataset, batch_size=batch_size, shuffle=True, pin_memory=(device == "cuda"))

    # Compute balanced class weights
    classes, counts = np.unique(y_act_train, return_counts=True)
    raw_w = len(y_act_train) / (len(classes) * counts.astype(np.float32))
    raw_w = np.clip(raw_w, 0.1, 10.0)
    w_arr = np.ones(7, dtype=np.float32)
    for c, w in zip(classes, raw_w):
        w_arr[int(c)] = float(w)
    class_weights = torch.from_numpy(w_arr).to(device)

    # Setup loss functions
    if model_name == "M9_CostSensitive":
        criterion_action = CostSensitiveLoss(turnover_penalty_weight=hparams.get("turnover_penalty_weight", 3.5))
    else:
        criterion_action = nn.CrossEntropyLoss(weight=class_weights)

    criterion_size = nn.MSELoss()
    criterion_order = nn.SmoothL1Loss()
    optimizer = optim.AdamW(model.parameters(), lr=lr, weight_decay=weight_decay)
    scheduler = optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=epochs)

    is_actor_critic = (model_name == "M10_ActorCritic_RL")
    entropy_coef = hparams.get("entropy_coef", 0.01)

    print(f"[{model_name}] Training for {epochs} epochs on {device.upper()} (Batch={batch_size}, LR={lr})...")
    t_start = time.time()

    for epoch in range(1, epochs + 1):
        model.train()
        total_loss, act_correct, total_samples = 0.0, 0, 0

        for bx, ba, bsz, bord in loader:
            bx, ba, bsz, bord = bx.to(device), ba.to(device), bsz.to(device), bord.to(device)
            optimizer.zero_grad()

            if is_actor_critic:
                logits, value, pred_sz, pred_ord = model(bx)
                # Actor CrossEntropy + Critic MSE on size/value baseline
                probs = torch.softmax(logits, dim=-1)
                log_probs = torch.log_softmax(logits, dim=-1)
                entropy = -(probs * log_probs).sum(dim=-1).mean()

                loss_act = criterion_action(logits, ba) - (entropy_coef * entropy)
                loss_val = criterion_size(value, bsz)
                loss_sz = criterion_size(pred_sz, bsz)
                loss_ord = criterion_order(pred_ord, bord)
                loss = loss_act + (0.5 * loss_val) + (0.5 * loss_sz) + (0.3 * loss_ord)
            else:
                logits, pred_sz, pred_ord = model(bx)
                loss_act = criterion_action(logits, ba)
                loss_sz = criterion_size(pred_sz, bsz)
                loss_ord = criterion_order(pred_ord, bord)
                loss = loss_act + (0.5 * loss_sz) + (0.3 * loss_ord)

            loss.backward()
            nn.utils.clip_grad_norm_(model.parameters(), max_norm=1.0)
            optimizer.step()

            total_loss += loss.item() * len(bx)
            act_correct += (logits.argmax(dim=-1) == ba).sum().item()
            total_samples += len(bx)

        scheduler.step()
        if epoch % 5 == 0 or epoch == epochs:
            print(f"[{model_name}] Epoch {epoch:02d}/{epochs:02d} | Loss: {total_loss/total_samples:.4f} | Action Acc: {act_correct/total_samples*100:.1f}%")

    print(f"[{model_name}] Training finished in {time.time() - t_start:.1f}s")
    return model


# =====================================================================
# ONNX EXPORTER FOR METATRADER 5 BUILD 6063+
# =====================================================================

def export_pytorch_to_onnx(
    model: "nn.Module",
    model_name: str,
    output_dir: str,
    input_dim: int = 40,
    opset_version: int = 13
) -> str:
    """Exports PyTorch Policy model to MT5-compatible ONNX."""
    is_ac = (model_name == "M10_ActorCritic_RL")

    class MT5PolicyWrapper(nn.Module):
        def __init__(self, core: nn.Module, is_actor_critic: bool):
            super().__init__()
            self.core = core
            self.is_ac = is_actor_critic
            self.softmax = nn.Softmax(dim=-1)

        def forward(self, x: torch.Tensor):
            if self.is_ac:
                logits, _, size, order = self.core(x)
            else:
                logits, size, order = self.core(x)
            probs = self.softmax(logits)
            return probs, size, order

    wrapper = MT5PolicyWrapper(model.cpu(), is_actor_critic=is_ac).eval()
    dummy_input = torch.zeros(1, input_dim, dtype=torch.float32)

    os.makedirs(output_dir, exist_ok=True)
    onnx_file = os.path.join(output_dir, f"{model_name.lower()}_policy.onnx")

    try:
        torch.onnx.export(
            wrapper,
            dummy_input,
            onnx_file,
            export_params=True,
            opset_version=opset_version,
            do_constant_folding=True,
            input_names=["input_features"],
            output_names=["action_probs", "position_size", "order_params"],
            dynamic_axes={
                "input_features": {0: "batch_size"},
                "action_probs": {0: "batch_size"},
                "position_size": {0: "batch_size"},
                "order_params": {0: "batch_size"}
            }
        )
    except Exception as e:
        print(f"[{model_name}] Standard ONNX export error ({e}), retrying with dynamo=False fallback...")
        torch.onnx.export(
            wrapper,
            dummy_input,
            onnx_file,
            export_params=True,
            opset_version=opset_version,
            do_constant_folding=True,
            dynamo=False,
            input_names=["input_features"],
            output_names=["action_probs", "position_size", "order_params"],
            dynamic_axes={
                "input_features": {0: "batch_size"},
                "action_probs": {0: "batch_size"},
                "position_size": {0: "batch_size"},
                "order_params": {0: "batch_size"}
            }
        )
    print(f"[{model_name}] Successfully exported ONNX model to: {onnx_file}")
    return onnx_file


# =====================================================================
# INFERENCE PREDICTORS FOR CLOSED-LOOP EVALUATION
# =====================================================================

def make_pytorch_eval_predictor(model: "nn.Module", model_name: str, device: str, threshold: float = 0.35):
    """Creates a standardized callable for the closed-loop backtest evaluator."""
    model.eval()
    is_ac = (model_name == "M10_ActorCritic_RL")

    def predictor(state_1x40: np.ndarray) -> Tuple[int, float, float, float]:
        with torch.no_grad():
            t_in = torch.tensor(state_1x40, dtype=torch.float32, device=device)
            if is_ac:
                logits, _, sz_tensor, ord_tensor = model(t_in)
            else:
                logits, sz_tensor, ord_tensor = model(t_in)

            probs = torch.softmax(logits, dim=-1).cpu().numpy()[0]
            best_a = int(np.argmax(probs))
            if probs[best_a] < threshold:
                best_a = 0  # Default to HOLD on low confidence

            sz = float(np.clip(sz_tensor.cpu().numpy()[0, 0], 0.1, 1.0))
            sl = float(np.clip(ord_tensor.cpu().numpy()[0, 0], 1.0, 4.0))
            tp = float(np.clip(ord_tensor.cpu().numpy()[0, 1], 1.5, 7.0))
        return best_a, sz, sl, tp

    return predictor


def make_tabular_eval_predictor(model, threshold: float = 0.35):
    """Wraps GBDT / Meta-Labeling models for evaluation."""
    def predictor(state_1x40: np.ndarray) -> Tuple[int, float, float, float]:
        return model.predict_step(state_1x40, threshold=threshold)
    return predictor


# =====================================================================
# MAIN RUNNER
# =====================================================================

def main():
    parser = argparse.ArgumentParser(description="Train and benchmark 10 Quant ML Trading Policy Models.")
    parser.add_argument("--data-path", type=str, default=None, help="Path to M1 dataset CSV or CSV.GZ")
    parser.add_argument("--models", type=str, default="all", help="Comma-separated models or 'all'")
    parser.add_argument("--output-dir", type=str, default=None, help="Directory to save models and logs")
    parser.add_argument("--subsample-step", type=int, default=4, help="Subsample step for counterfactual simulator")
    parser.add_argument("--horizon", type=int, default=60, help="Forward horizon bars for counterfactual evaluation")
    args = parser.parse_args()

    print("=" * 80)
    print(" 🚀 10 QUANT ML TRADING POLICY MODELS: TRAINING & BENCHMARK SUITE")
    print("=" * 80)

    # 1. Device Setup
    device = "cuda" if (TORCH_AVAILABLE and torch.cuda.is_available()) else "cpu"
    print(f"[Hardware] PyTorch Available: {TORCH_AVAILABLE} | Device: {device.upper()}")
    if device == "cuda":
        print(f"[Hardware] GPU Model: {torch.cuda.get_device_name(0)}")

    # 2. Select Models to Train
    if args.models.lower() == "all":
        selected_models = ALL_MODELS
    else:
        selected_models = [m.strip() for m in args.models.split(",") if m.strip()]
    print(f"[Run Configuration] Models to train ({len(selected_models)}): {selected_models}")

    # 3. Locate & Load Dataset
    csv_file = find_dataset_file(args.data_path)
    df_train, df_val = load_and_preprocess_data(csv_file)

    # 4. Feature Extraction
    (feat_train, atr_train, close_train, df_train_clean), (feat_val, atr_val, close_val, df_val_clean) = prepare_market_features(df_train, df_val)

    # 5. Generate Counterfactual Training Dataset
    print(f"\n[Counterfactual Simulator] Generating augmented dataset (Horizon={args.horizon}, Step={args.subsample_step})...")
    t0_cf = time.time()
    X_train, y_act_train, y_sz_train, y_sl_train, y_tp_train = build_augmented_training_dataset(
        market_features=feat_train,
        close_prices=close_train.to_numpy(),
        high_prices=df_train_clean['high'].to_numpy(),
        low_prices=df_train_clean['low'].to_numpy(),
        atr_values=atr_train.to_numpy(),
        horizon=args.horizon,
        subsample_step=args.subsample_step
    )
    print(f"[Counterfactual Simulator] Completed in {time.time() - t0_cf:.1f}s. Total instances: {len(X_train):,}")

    # Setup directories
    out_dir = args.output_dir or os.path.join(project_dir, "models", "suite")
    docs_dir = os.path.join(project_dir, "docs")
    os.makedirs(out_dir, exist_ok=True)
    os.makedirs(docs_dir, exist_ok=True)

    # Save feature normalization metadata
    meta_path = os.path.join(out_dir, "feature_metadata.json")
    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump({
            "num_features": 40,
            "market_features": MARKET_FEATURE_NAMES,
            "position_features": POSITION_FEATURE_NAMES,
            "means": np.mean(X_train, axis=0).tolist(),
            "stds": np.std(X_train, axis=0).tolist(),
            "action_names": {int(k): v for k, v in ACTION_NAMES.items()}
        }, f, indent=2)
    print(f"[Metadata] Feature stats saved to: {meta_path}")

    # Results dictionary
    benchmark_results: Dict[str, Dict[str, Any]] = {}
    equity_curves: Dict[str, np.ndarray] = {}

    # Pre-build fixed flat state feature matrix for fast-path 2025 out-of-sample backtesting
    mf_val_arr = feat_val.to_numpy(dtype=np.float32)
    pos_flat_block = np.zeros((len(mf_val_arr), 9), dtype=np.float32)
    pos_flat_block[:, 8] = 1.0  # p_act_norm = 1.0
    X_flat_val = np.hstack([mf_val_arr, pos_flat_block]).astype(np.float32)


    # =================================================================
    # TRAINING & EVALUATION LOOP ACROSS MODELS
    # =================================================================
    for idx, model_id in enumerate(selected_models, 1):
        print("\n" + "=" * 80)
        print(f" [{idx}/{len(selected_models)}] PROCESSING MODEL: {model_id}")
        print("=" * 80)

        hparams = get_tuned_hyperparameters(model_id)
        trained_model = None
        eval_predictor = None

        t_train_start = time.time()

        try:
            # ---------------------------------------------------------
            # Model 1: LightGBM
            # ---------------------------------------------------------
            if model_id == "M1_LightGBM":
                if not LGB_AVAILABLE:
                    print("Skipping M1_LightGBM (LightGBM not installed)")
                    continue
                trained_model = LightGBMPolicy(
                    num_leaves=hparams.get("num_leaves", 45),
                    learning_rate=hparams.get("learning_rate", 0.04),
                    n_estimators=hparams.get("n_estimators", 250),
                    min_child_samples=hparams.get("min_child_samples", 80)
                )
                trained_model.fit(X_train, y_act_train, y_sz_train, y_sl_train, y_tp_train)
                eval_predictor = make_tabular_eval_predictor(trained_model, threshold=0.35)

            # ---------------------------------------------------------
            # Model 2: CatBoost
            # ---------------------------------------------------------
            elif model_id == "M2_CatBoost":
                if not CATBOOST_AVAILABLE:
                    print("Skipping M2_CatBoost (CatBoost not installed)")
                    continue
                trained_model = CatBoostPolicy(
                    depth=hparams.get("depth", 5),
                    learning_rate=hparams.get("learning_rate", 0.05),
                    iterations=hparams.get("iterations", 300),
                    l2_leaf_reg=hparams.get("l2_leaf_reg", 6.0)
                )
                trained_model.fit(X_train, y_act_train, y_sz_train, y_sl_train, y_tp_train)
                eval_predictor = make_tabular_eval_predictor(trained_model, threshold=0.35)

            # ---------------------------------------------------------
            # Model 3: XGBoost
            # ---------------------------------------------------------
            elif model_id == "M3_XGBoost":
                if not XGB_AVAILABLE:
                    print("Skipping M3_XGBoost (XGBoost not installed)")
                    continue
                trained_model = XGBoostPolicy(
                    max_depth=hparams.get("max_depth", 4),
                    learning_rate=hparams.get("learning_rate", 0.04),
                    n_estimators=hparams.get("n_estimators", 220),
                    reg_alpha=hparams.get("reg_alpha", 1.5),
                    reg_lambda=hparams.get("reg_lambda", 4.0)
                )
                trained_model.fit(X_train, y_act_train, y_sz_train, y_sl_train, y_tp_train)
                eval_predictor = make_tabular_eval_predictor(trained_model, threshold=0.35)

            # ---------------------------------------------------------
            # Model 4: ResMLP
            # ---------------------------------------------------------
            elif model_id == "M4_ResMLP":
                if not TORCH_AVAILABLE:
                    print("Skipping M4_ResMLP (PyTorch not installed)")
                    continue
                raw_net = ResMLPPolicy(
                    input_dim=40,
                    hidden_dim=hparams.get("hidden_dim", 128),
                    dropout=hparams.get("dropout", 0.20)
                ).to(device)
                trained_model = train_pytorch_variant(
                    raw_net, model_id, X_train, y_act_train, y_sz_train, y_sl_train, y_tp_train, hparams, device
                )
                export_pytorch_to_onnx(trained_model, model_id, out_dir)
                eval_predictor = make_pytorch_eval_predictor(trained_model, model_id, device, threshold=0.35)

            # ---------------------------------------------------------
            # Model 5: TCN
            # ---------------------------------------------------------
            elif model_id == "M5_TCN":
                if not TORCH_AVAILABLE:
                    print("Skipping M5_TCN (PyTorch not installed)")
                    continue
                raw_net = TCNPolicy(
                    num_inputs=40,
                    num_channels=hparams.get("num_channels", [64, 64, 128]),
                    kernel_size=hparams.get("kernel_size", 3),
                    dropout=hparams.get("dropout", 0.20)
                ).to(device)
                trained_model = train_pytorch_variant(
                    raw_net, model_id, X_train, y_act_train, y_sz_train, y_sl_train, y_tp_train, hparams, device
                )
                export_pytorch_to_onnx(trained_model, model_id, out_dir)
                eval_predictor = make_pytorch_eval_predictor(trained_model, model_id, device, threshold=0.35)

            # ---------------------------------------------------------
            # Model 6: GRU + Temporal Attention
            # ---------------------------------------------------------
            elif model_id == "M6_GRU_Attention":
                if not TORCH_AVAILABLE:
                    print("Skipping M6_GRU_Attention (PyTorch not installed)")
                    continue
                raw_net = GRUAttentionPolicy(
                    input_dim=40,
                    hidden_dim=hparams.get("hidden_dim", 64),
                    num_layers=hparams.get("num_layers", 2),
                    dropout=hparams.get("dropout", 0.20)
                ).to(device)
                trained_model = train_pytorch_variant(
                    raw_net, model_id, X_train, y_act_train, y_sz_train, y_sl_train, y_tp_train, hparams, device
                )
                export_pytorch_to_onnx(trained_model, model_id, out_dir)
                eval_predictor = make_pytorch_eval_predictor(trained_model, model_id, device, threshold=0.35)

            # ---------------------------------------------------------
            # Model 7: PatchTransformer
            # ---------------------------------------------------------
            elif model_id == "M7_PatchTransformer":
                if not TORCH_AVAILABLE:
                    print("Skipping M7_PatchTransformer (PyTorch not installed)")
                    continue
                raw_net = PatchTransformerPolicy(
                    input_dim=40,
                    d_model=hparams.get("d_model", 64),
                    nhead=hparams.get("nhead", 4),
                    num_layers=hparams.get("num_layers", 2),
                    dropout=hparams.get("dropout", 0.20)
                ).to(device)
                trained_model = train_pytorch_variant(
                    raw_net, model_id, X_train, y_act_train, y_sz_train, y_sl_train, y_tp_train, hparams, device
                )
                export_pytorch_to_onnx(trained_model, model_id, out_dir)
                eval_predictor = make_pytorch_eval_predictor(trained_model, model_id, device, threshold=0.35)

            # ---------------------------------------------------------
            # Model 8: Two-Stage Meta-Labeling
            # ---------------------------------------------------------
            elif model_id == "M8_MetaLabeling":
                trained_model = TwoStageMetaLabelingPolicy()
                trained_model.fit(X_train, y_act_train)
                eval_predictor = make_tabular_eval_predictor(trained_model, threshold=0.35)

            # ---------------------------------------------------------
            # Model 9: Cost-Sensitive Policy Net
            # ---------------------------------------------------------
            elif model_id == "M9_CostSensitive":
                if not TORCH_AVAILABLE:
                    print("Skipping M9_CostSensitive (PyTorch not installed)")
                    continue
                raw_net = CostSensitivePolicyNet(
                    input_dim=40,
                    hidden_dim=hparams.get("hidden_dim", 128)
                ).to(device)
                trained_model = train_pytorch_variant(
                    raw_net, model_id, X_train, y_act_train, y_sz_train, y_sl_train, y_tp_train, hparams, device
                )
                export_pytorch_to_onnx(trained_model, model_id, out_dir)
                eval_predictor = make_pytorch_eval_predictor(trained_model, model_id, device, threshold=0.35)

            # ---------------------------------------------------------
            # Model 10: Actor-Critic RL
            # ---------------------------------------------------------
            elif model_id == "M10_ActorCritic_RL":
                if not TORCH_AVAILABLE:
                    print("Skipping M10_ActorCritic_RL (PyTorch not installed)")
                    continue
                raw_net = ActorCriticPolicyNet(
                    state_dim=40,
                    hidden_dim=hparams.get("hidden_dim", 128)
                ).to(device)
                trained_model = train_pytorch_variant(
                    raw_net, model_id, X_train, y_act_train, y_sz_train, y_sl_train, y_tp_train, hparams, device
                )
                export_pytorch_to_onnx(trained_model, model_id, out_dir)
                eval_predictor = make_pytorch_eval_predictor(trained_model, model_id, device, threshold=0.35)

            train_time = time.time() - t_train_start

            # ---------------------------------------------------------
            # CLOSED-LOOP BACKTEST EVALUATION ON 2025 OUT-OF-SAMPLE DATA
            # ---------------------------------------------------------
            print(f"\n[{model_id}] Vectorized precomputing flat decisions on 2025 data...", end="", flush=True)
            t_eval_start = time.time()

            if model_id in ["M1_LightGBM", "M2_CatBoost", "M3_XGBoost"]:
                probs = trained_model.clf.predict_proba(X_flat_val)
                best_a = np.argmax(probs, axis=1)
                max_p = np.max(probs, axis=1)
                best_a[max_p < 0.35] = 0
                flat_sz = np.clip(trained_model.reg_size.predict(X_flat_val), 0.1, 1.0)
                flat_sl = np.clip(trained_model.reg_sl.predict(X_flat_val), 1.0, 4.0)
                flat_tp = np.clip(trained_model.reg_tp.predict(X_flat_val), 1.5, 7.0)
                precomputed_flat = (best_a, flat_sz, flat_sl, flat_tp)
            elif model_id == "M8_MetaLabeling":
                prim_preds = trained_model.primary_model.predict(X_flat_val)
                prim_probs = trained_model.primary_model.predict_proba(X_flat_val)
                meta_X = np.hstack([X_flat_val, prim_probs])
                meta_probs = trained_model.meta_model.predict_proba(meta_X)[:, 1]
                final_a = prim_preds.copy()
                final_a[(meta_probs < 0.55) & (final_a != 0)] = 0
                flat_sz = np.clip(meta_probs, 0.2, 1.0)
                flat_sl = np.full(len(X_flat_val), 2.0, dtype=np.float32)
                flat_tp = np.full(len(X_flat_val), 3.5, dtype=np.float32)
                precomputed_flat = (final_a, flat_sz, flat_sl, flat_tp)
            else:
                trained_model.eval()
                all_a, all_sz, all_sl, all_tp = [], [], [], []
                is_ac = (model_id == "M10_ActorCritic_RL")
                with torch.no_grad():
                    for bi in range(0, len(X_flat_val), 8192):
                        bx = torch.tensor(X_flat_val[bi:bi+8192], dtype=torch.float32, device=device)
                        if is_ac:
                            logits, _, sz_t, ord_t = trained_model(bx)
                        else:
                            logits, sz_t, ord_t = trained_model(bx)
                        probs = torch.softmax(logits, dim=-1)
                        max_p, best_a = torch.max(probs, dim=-1)
                        best_a = torch.where(max_p < 0.35, torch.zeros_like(best_a), best_a)
                        all_a.append(best_a.cpu().numpy())
                        all_sz.append(np.clip(sz_t.cpu().numpy()[:, 0], 0.1, 1.0))
                        all_sl.append(np.clip(ord_t.cpu().numpy()[:, 0], 1.0, 4.0))
                        all_tp.append(np.clip(ord_t.cpu().numpy()[:, 1], 1.5, 7.0))
                precomputed_flat = (
                    np.concatenate(all_a),
                    np.concatenate(all_sz),
                    np.concatenate(all_sl),
                    np.concatenate(all_tp)
                )

            print(f" done! Running Closed-Loop Simulation ({len(df_val_clean):,} bars)...", flush=True)

            res = run_closed_loop_backtest(
                df=df_val_clean,
                market_features=feat_val,
                atr_series=atr_val,
                policy_predictor=eval_predictor,
                initial_balance=10000.0,
                lot_base=0.1,
                spread_points=2.0,
                slippage_points=1.0,
                commission_per_lot=6.0,
                precomputed_flat=precomputed_flat
            )
            eval_time = time.time() - t_eval_start

            # Compute Annualized Sharpe Ratio on Equity Curve
            eq = res["equity_curve"]
            equity_curves[model_id] = eq
            rets = np.diff(eq) / eq[:-1]
            if len(rets) > 0 and np.std(rets) > 1e-8:
                sharpe = float(np.mean(rets) / np.std(rets) * np.sqrt(350000))
            else:
                sharpe = 0.0

            benchmark_results[model_id] = {
                "algorithm": model_id.split("_", 1)[1],
                "net_profit": float(res["net_profit"]),
                "return_pct": float(res["return_pct"]),
                "profit_factor": float(res["profit_factor"]),
                "win_rate": float(res["win_rate"]),
                "max_drawdown_pct": float(res["max_drawdown_pct"]),
                "total_trades": int(res["total_trades"]),
                "avg_trade_pnl": float(res["avg_trade_pnl"]),
                "sharpe_ratio": float(sharpe),
                "train_time_sec": float(round(train_time, 1)),
                "eval_time_sec": float(round(eval_time, 1))
            }

            print(f"[{model_id}] 2025 Results -> Net Profit: ${res['net_profit']:,.2f} ({res['return_pct']:.1f}%) | PF: {res['profit_factor']:.2f} | WR: {res['win_rate']:.1f}% | DD: {res['max_drawdown_pct']:.1f}% | Trades: {res['total_trades']:,} | Sharpe: {sharpe:.2f}")

        except Exception as e:
            print(f"❌ Error training/evaluating {model_id}: {e}")
            import traceback
            traceback.print_exc()

    # =================================================================
    # SAVE BENCHMARK COMPARISON & PLOTS
    # =================================================================
    if benchmark_results:
        # Save JSON
        json_path = os.path.join(out_dir, "benchmark_10_models.json")
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(benchmark_results, f, indent=2)
        print(f"\n[Benchmark] Results JSON saved to: {json_path}")

        # Generate Markdown Table
        df_bench = pd.DataFrame.from_dict(benchmark_results, orient="index")
        df_bench.sort_values(by="profit_factor", ascending=False, inplace=True)

        md_path = os.path.join(docs_dir, "BENCHMARK_10_MODELS.md")
        with open(md_path, "w", encoding="utf-8") as f:
            f.write("# 🏆 10 Quant ML Trading Policy Models: 2025 Out-of-Sample Benchmark\n\n")
            f.write("Strictly evaluated on out-of-sample 2025 M1 data (350,807 bars) with realistic transaction friction ($0.20 spread, $0.10 slippage, $6.0/lot comm).\n\n")
            f.write("| Model ID | Paradigm / Algorithm | Net Profit ($) | Return (%) | Profit Factor | Win Rate (%) | Max DD (%) | Trades | Sharpe | Train Time (s) |\n")
            f.write("| :--- | :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |\n")
            for m_id, row in df_bench.iterrows():
                f.write(f"| **{m_id}** | {row['algorithm']} | ${row['net_profit']:,.2f} | {row['return_pct']:.1f}% | **{row['profit_factor']:.2f}** | {row['win_rate']:.1f}% | {row['max_drawdown_pct']:.1f}% | {int(row['total_trades']):,} | {row['sharpe_ratio']:.2f} | {row['train_time_sec']:.1f}s |\n")
            f.write("\n\n*Note: 2026 data remains strictly locked and untouched.*\n")
        print(f"[Benchmark] Markdown table saved to: {md_path}")

        # Plot Comparative Equity Curves
        plot_path = os.path.join(docs_dir, "equity_curves_10_models.png")
        plt.figure(figsize=(14, 8))
        colors = plt.cm.tab10(np.linspace(0, 1, len(equity_curves)))
        for (m_id, eq_curve), col in zip(equity_curves.items(), colors):
            plt.plot(eq_curve, label=f"{m_id} (PF: {benchmark_results[m_id]['profit_factor']:.2f})", color=col, linewidth=1.2)
        plt.title("2025 Out-of-Sample Closed-Loop Equity Curves: 10 Quant ML Models (XAUUSD M1)", fontsize=14, fontweight="bold")
        plt.xlabel("M1 Timesteps (Bars)", fontsize=12)
        plt.ylabel("Account Equity ($)", fontsize=12)
        plt.grid(True, alpha=0.3)
        plt.legend(loc="upper left")
        plt.tight_layout()
        plt.savefig(plot_path, dpi=300)
        print(f"[Benchmark] Comparison plot saved to: {plot_path}")

    print("\n🎉 ALL TRAINING, BENCHMARKING, AND EXPORTS COMPLETED!")


if __name__ == "__main__":
    main()
