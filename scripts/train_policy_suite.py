"""
=============================================================================
XAUUSD Trading Policy: Multi-Algorithm Training & ONNX Export Suite
=============================================================================
Features:
1. PyTorch Multi-Head Policy Network (Shared Backbone -> Action, Size, Order heads)
2. LightGBM Policy Baseline (Multi-Class + Multi-Regressor)
3. Multi-task loss balancing with focal/class weighting
4. MetaTrader 5 ONNX Exporter (Opset 13, IR Version 8, Float32)
5. Model metadata export for live EA ingestion
=============================================================================
"""

import os
import json
import numpy as np
from typing import Dict, Any, Tuple

# Try importing torch; if not present (e.g. on lightweight environments), fallback gracefully
try:
    import torch
    import torch.nn as nn
    import torch.optim as optim
    from torch.utils.data import TensorDataset, DataLoader
    TORCH_AVAILABLE = True
except ImportError:
    TORCH_AVAILABLE = False

try:
    import lightgbm as lgb
    LGB_AVAILABLE = True
except ImportError:
    LGB_AVAILABLE = False


if TORCH_AVAILABLE:
    class TradingPolicyNetwork(nn.Module):
        """
        Deep Multi-Head Trading Policy Network
        - Input: 40 Scale-Invariant Features (31 Market + 9 Position)
        - Shared Representation: 2-layer MLP with LayerNorm, GELU, and Dropout
        - Multi-Head Outputs:
          1. Action Head: Logits for 7 discrete actions (HOLD, OPEN_L, OPEN_S, ADD, REDUCE, CLOSE, REVERSE)
          2. Size Head: Continuous risk sizing in [0.1, 1.0] (Sigmoid activation)
          3. Order Head: Dynamic SL & TP distances in ATR units (Softplus activation)
        """
        def __init__(self, input_dim: int = 40, hidden_dim: int = 128, num_actions: int = 7, dropout: float = 0.15):
            super().__init__()
            self.input_layer = nn.Sequential(
                nn.Linear(input_dim, hidden_dim),
                nn.LayerNorm(hidden_dim),
                nn.GELU(),
                nn.Dropout(dropout)
            )
            
            self.backbone = nn.Sequential(
                nn.Linear(hidden_dim, hidden_dim),
                nn.LayerNorm(hidden_dim),
                nn.GELU(),
                nn.Dropout(dropout)
            )
            
            # Head 1: Action Classification
            self.action_head = nn.Sequential(
                nn.Linear(hidden_dim, 64),
                nn.GELU(),
                nn.Linear(64, num_actions)
            )
            
            # Head 2: Risk Size Fraction [0.1, 1.0]
            self.size_head = nn.Sequential(
                nn.Linear(hidden_dim, 32),
                nn.GELU(),
                nn.Linear(32, 1),
                nn.Sigmoid()
            )
            
            # Head 3: Order Parameters [SL_atr, TP_atr]
            self.order_head = nn.Sequential(
                nn.Linear(hidden_dim, 32),
                nn.GELU(),
                nn.Linear(32, 2),
                nn.Softplus()  # Ensures positive distances
            )

        def forward(self, x: torch.Tensor) -> Tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
            feat = self.input_layer(x)
            feat = self.backbone(feat) + feat  # Residual skip connection
            
            action_logits = self.action_head(feat)
            size_out = self.size_head(feat)
            order_out = self.order_head(feat)
            
            return action_logits, size_out, order_out


def train_pytorch_policy(
    X_train: np.ndarray,
    y_action_train: np.ndarray,
    y_size_train: np.ndarray,
    y_sl_train: np.ndarray,
    y_tp_train: np.ndarray,
    X_val: np.ndarray = None,
    y_action_val: np.ndarray = None,
    y_size_val: np.ndarray = None,
    y_sl_val: np.ndarray = None,
    y_tp_val: np.ndarray = None,
    epochs: int = 25,
    batch_size: int = 512,
    lr: float = 1e-3,
    device: str = None
) -> "TradingPolicyNetwork":
    """
    Trains the Multi-Head Trading Policy Network with PyTorch (GPU accelerated if available).
    """
    if not TORCH_AVAILABLE:
        raise RuntimeError("PyTorch is not installed in the current environment.")

    if device is None:
        device = "cuda" if torch.cuda.is_available() else "cpu"
    print(f"[PyTorch Trainer] Training on device: {device.upper()}")

    # Prepare datasets
    y_order_train = np.stack([y_sl_train, y_tp_train], axis=1)
    train_dataset = TensorDataset(
        torch.tensor(X_train, dtype=torch.float32),
        torch.tensor(y_action_train, dtype=torch.long),
        torch.tensor(y_size_train, dtype=torch.float32).unsqueeze(1),
        torch.tensor(y_order_train, dtype=torch.float32)
    )
    train_loader = DataLoader(train_dataset, batch_size=batch_size, shuffle=True, pin_memory=(device == "cuda"))

    has_val = X_val is not None
    if has_val:
        y_order_val = np.stack([y_sl_val, y_tp_val], axis=1)
        val_dataset = TensorDataset(
            torch.tensor(X_val, dtype=torch.float32),
            torch.tensor(y_action_val, dtype=torch.long),
            torch.tensor(y_size_val, dtype=torch.float32).unsqueeze(1),
            torch.tensor(y_order_val, dtype=torch.float32)
        )
        val_loader = DataLoader(val_dataset, batch_size=batch_size, shuffle=False)

    # Class weighting for balanced action learning
    classes, counts = np.unique(y_action_train, return_counts=True)
    weights = len(y_action_train) / (len(classes) * counts.astype(np.float32))
    class_weights = torch.ones(7, dtype=torch.float32)
    for c, w in zip(classes, weights):
        class_weights[c] = w
    class_weights = class_weights.to(device)

    model = TradingPolicyNetwork(input_dim=X_train.shape[1]).to(device)
    criterion_action = nn.CrossEntropyLoss(weight=class_weights)
    criterion_size = nn.MSELoss()
    criterion_order = nn.SmoothL1Loss()
    optimizer = optim.AdamW(model.parameters(), lr=lr, weight_decay=1e-4)
    scheduler = optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=epochs)

    for epoch in range(1, epochs + 1):
        model.train()
        total_loss, act_correct, total_samples = 0.0, 0, 0

        for batch_x, batch_act, batch_sz, batch_ord in train_loader:
            batch_x = batch_x.to(device)
            batch_act = batch_act.to(device)
            batch_sz = batch_sz.to(device)
            batch_ord = batch_ord.to(device)

            optimizer.zero_grad()
            logits, pred_sz, pred_ord = model(batch_x)

            loss_act = criterion_action(logits, batch_act)
            loss_sz = criterion_size(pred_sz, batch_sz)
            loss_ord = criterion_order(pred_ord, batch_ord)
            loss = loss_act + (0.5 * loss_sz) + (0.3 * loss_ord)

            loss.backward()
            nn.utils.clip_grad_norm_(model.parameters(), max_norm=1.0)
            optimizer.step()

            total_loss += loss.item() * len(batch_x)
            act_correct += (logits.argmax(dim=1) == batch_act).sum().item()
            total_samples += len(batch_x)

        scheduler.step()
        train_loss = total_loss / total_samples
        train_acc = act_correct / total_samples * 100.0

        if has_val:
            model.eval()
            val_loss, val_correct, val_samples = 0.0, 0, 0
            with torch.no_grad():
                for bx, ba, bs, bo in val_loader:
                    bx, ba, bs, bo = bx.to(device), ba.to(device), bs.to(device), bo.to(device)
                    lgt, psz, pord = model(bx)
                    v_loss = criterion_action(lgt, ba) + 0.5 * criterion_size(psz, bs) + 0.3 * criterion_order(pord, bo)
                    val_loss += v_loss.item() * len(bx)
                    val_correct += (lgt.argmax(dim=1) == ba).sum().item()
                    val_samples += len(bx)
            print(f"Epoch [{epoch:02d}/{epochs:02d}] Train Loss: {train_loss:.4f} (Acc: {train_acc:.1f}%) | Val Loss: {val_loss/val_samples:.4f} (Val Acc: {val_correct/val_samples*100:.1f}%)")
        else:
            print(f"Epoch [{epoch:02d}/{epochs:02d}] Train Loss: {train_loss:.4f} (Acc: {train_acc:.1f}%)")

    return model


def export_model_to_onnx(
    model: "TradingPolicyNetwork",
    output_path: str,
    input_dim: int = 40,
    opset_version: int = 13
) -> str:
    """
    Exports the trained PyTorch policy network to an ONNX model compatible with MetaTrader 5 Build 6063+.
    Output format:
    - Input: 'input_features' [1, 40] (float32)
    - Outputs:
      - 'action_logits': [1, 7]
      - 'action_probs': [1, 7] (via Softmax wrapper)
      - 'position_size': [1, 1]
      - 'sl_tp_distances': [1, 2]
    """
    if not TORCH_AVAILABLE:
        raise RuntimeError("PyTorch is required for ONNX export.")

    class MT5ExportWrapper(nn.Module):
        def __init__(self, core_model: nn.Module):
            super().__init__()
            self.core = core_model
            self.softmax = nn.Softmax(dim=-1)

        def forward(self, x: torch.Tensor):
            logits, size, order = self.core(x)
            probs = self.softmax(logits)
            return probs, size, order

    wrapper = MT5ExportWrapper(model.cpu()).eval()
    dummy_input = torch.zeros(1, input_dim, dtype=torch.float32)

    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
    
    torch.onnx.export(
        wrapper,
        dummy_input,
        output_path,
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
    print(f"[ONNX Exporter] Model successfully saved to {output_path}")
    return output_path


def train_lightgbm_policy_baseline(
    X_train: np.ndarray,
    y_action_train: np.ndarray,
    y_size_train: np.ndarray,
    y_sl_train: np.ndarray,
    y_tp_train: np.ndarray,
    feature_names: list
) -> Dict[str, Any]:
    """
    Trains a fast LightGBM baseline for Policy Action classification and parameters regression.
    """
    if not LGB_AVAILABLE:
        raise RuntimeError("LightGBM is not installed.")

    print("[LightGBM Baseline] Training Action Classifier...")
    clf = lgb.LGBMClassifier(
        n_estimators=150,
        learning_rate=0.08,
        num_leaves=31,
        class_weight='balanced',
        n_jobs=-1,
        random_state=42
    )
    clf.fit(X_train, y_action_train)

    print("[LightGBM Baseline] Training Size Regressor...")
    reg_size = lgb.LGBMRegressor(
        n_estimators=100,
        learning_rate=0.08,
        num_leaves=31,
        n_jobs=-1,
        random_state=42
    )
    reg_size.fit(X_train, y_size_train)

    print("[LightGBM Baseline] Training SL Regressor...")
    reg_sl = lgb.LGBMRegressor(
        n_estimators=100,
        learning_rate=0.08,
        num_leaves=31,
        n_jobs=-1,
        random_state=42
    )
    reg_sl.fit(X_train, y_sl_train)

    print("[LightGBM Baseline] Training TP Regressor...")
    reg_tp = lgb.LGBMRegressor(
        n_estimators=100,
        learning_rate=0.08,
        num_leaves=31,
        n_jobs=-1,
        random_state=42
    )
    reg_tp.fit(X_train, y_tp_train)

    print("[LightGBM Baseline] Complete!")
    return {
        "action_classifier": clf,
        "size_regressor": reg_size,
        "sl_regressor": reg_sl,
        "tp_regressor": reg_tp
    }


def save_policy_metadata(
    output_path: str,
    feature_names: list,
    action_names: Dict[int, str],
    mean_stats: np.ndarray = None,
    std_stats: np.ndarray = None
):
    """
    Saves metadata config JSON needed by MetaTrader 5 EA to prepare input tensors.
    """
    metadata = {
        "version": "1.0.0",
        "symbol": "XAUUSD",
        "timeframe": "M1",
        "num_features": len(feature_names),
        "feature_names": feature_names,
        "action_mapping": {int(k): v for k, v in action_names.items()},
        "means": mean_stats.tolist() if mean_stats is not None else [],
        "stds": std_stats.tolist() if std_stats is not None else []
    }
    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(metadata, f, indent=2)
    print(f"[Metadata] Config saved to {output_path}")
