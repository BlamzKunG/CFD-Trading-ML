"""
=============================================================================
Hyperparameter Tuning & Configurations for 10 Quant ML Models
=============================================================================
Defines empirically validated, robust hyperparameter presets designed to
prevent financial overfitting, control turnover, and maximize risk-adjusted return.
=============================================================================
"""

from typing import Dict, Any

TUNED_HYPERPARAMETERS: Dict[str, Dict[str, Any]] = {
    # -------------------------------------------------------------
    # Family A: Tabular Gradient Boosting
    # -------------------------------------------------------------
    "M1_LightGBM": {
        "num_leaves": 45,             # Constrained to prevent memorizing noise
        "learning_rate": 0.04,        # Conservative learning rate
        "n_estimators": 250,          # Sufficient iterations with shrinkage
        "min_child_samples": 80,      # Higher leaf size for generalizable split rules
        "subsample": 0.8,
        "colsample_bytree": 0.8,
        "class_weight": "balanced"
    },
    "M2_CatBoost": {
        "depth": 5,                   # Oblivious symmetric trees with shallow depth
        "learning_rate": 0.05,
        "iterations": 300,
        "l2_leaf_reg": 6.0,           # Strong L2 regularization on leaf weights
        "auto_class_weights": "Balanced"
    },
    "M3_XGBoost": {
        "max_depth": 4,               # Strict depth constraint
        "learning_rate": 0.04,
        "n_estimators": 220,
        "reg_alpha": 1.5,             # L1 Lasso sparsity constraint
        "reg_lambda": 4.0,            # L2 Ridge penalty
        "subsample": 0.75,
        "colsample_bytree": 0.75
    },

    # -------------------------------------------------------------
    # Family B: Deep Neural Networks (PyTorch)
    # -------------------------------------------------------------
    "M4_ResMLP": {
        "hidden_dim": 128,
        "dropout": 0.20,              # Higher dropout for market generalization
        "lr": 8e-4,
        "weight_decay": 2e-4,
        "epochs": 8,
        "batch_size": 1024
    },
    "M5_TCN": {
        "num_channels": [64, 64, 128],
        "kernel_size": 3,
        "dropout": 0.20,
        "lr": 7e-4,
        "weight_decay": 1e-4,
        "epochs": 8,
        "batch_size": 1024
    },
    "M6_GRU_Attention": {
        "hidden_dim": 64,
        "num_layers": 2,
        "dropout": 0.20,
        "lr": 8e-4,
        "weight_decay": 1e-4,
        "epochs": 8,
        "batch_size": 1024
    },
    "M7_PatchTransformer": {
        "d_model": 64,
        "nhead": 4,
        "num_layers": 2,
        "dropout": 0.20,
        "lr": 6e-4,
        "weight_decay": 2e-4,
        "epochs": 8,
        "batch_size": 1024
    },

    # -------------------------------------------------------------
    # Family C: Specialized Quant Hybrids & RL
    # -------------------------------------------------------------
    "M8_MetaLabeling": {
        "primary_n_estimators": 120,
        "primary_max_depth": 5,
        "meta_C": 0.8,
        "meta_threshold": 0.55        # Minimum confidence before taking trade
    },
    "M9_CostSensitive": {
        "hidden_dim": 128,
        "turnover_penalty_weight": 3.5, # Strong penalty against unnecessary trades
        "lr": 8e-4,
        "epochs": 8,
        "batch_size": 1024
    },
    "M10_ActorCritic_RL": {
        "hidden_dim": 128,
        "actor_lr": 3e-4,
        "critic_lr": 1e-3,
        "gamma": 0.99,
        "entropy_coef": 0.01,
        "epochs": 8,
        "batch_size": 1024
    }
}

def get_tuned_hyperparameters(model_id: str) -> Dict[str, Any]:
    """Retrieves tuned hyperparameters for a given model identifier."""
    if model_id not in TUNED_HYPERPARAMETERS:
        raise ValueError(f"Unknown model_id '{model_id}'. Available: {list(TUNED_HYPERPARAMETERS.keys())}")
    return TUNED_HYPERPARAMETERS[model_id].copy()
