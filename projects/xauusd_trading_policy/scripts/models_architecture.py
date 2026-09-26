"""
=============================================================================
10 Diverse Machine Learning Model Architectures for CFD Quant Trading
=============================================================================
Includes:
- Family A (Tabular GBDT):
    1. LightGBMPolicy (Histogram GBDT, Leaf-wise, Balanced)
    2. CatBoostPolicy (Ordered Boosting, Oblivious Symmetric Trees)
    3. XGBoostPolicy (Depth-Constrained Regularized GBDT)
- Family B (Deep Sequence & Spatial Neural Networks):
    4. ResMLPPolicy (Deep Residual Multi-Head MLP)
    5. TCNPolicy (Temporal Convolutional Network with Causal Dilated Convolutions)
    6. GRUAttentionPolicy (Gated Recurrent Unit with Temporal Self-Attention)
    7. PatchTransformerPolicy (Multi-Head Self-Attention Time-Series Transformer)
- Family C (Specialized Quant Hybrids & RL):
    8. MetaLabelingPolicy (Two-Stage Marcos López de Prado Architecture)
    9. CostSensitivePolicyNet (Asymmetric Turnover-Penalized Loss Network)
   10. ActorCriticPolicyNet (Deep Reinforcement Learning Policy & Value Net)
=============================================================================
"""

import math
import warnings
warnings.filterwarnings('ignore')

import numpy as np
from typing import Dict, Any, Tuple, List, Optional

# Conditional Imports for PyTorch and Tabular Libraries
try:
    import torch
    import torch.nn as nn
    import torch.nn.functional as F
    TORCH_AVAILABLE = True
except ImportError:
    TORCH_AVAILABLE = False

try:
    import lightgbm as lgb
    LGB_AVAILABLE = True
except ImportError:
    LGB_AVAILABLE = False

try:
    import catboost as cb
    CATBOOST_AVAILABLE = True
except ImportError:
    CATBOOST_AVAILABLE = False

try:
    import xgboost as xgb
    XGB_AVAILABLE = True
except ImportError:
    XGB_AVAILABLE = False

from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression


# =====================================================================
# FAMILY A: TABULAR GRADIENT BOOSTED DECISION TREES
# =====================================================================

class LightGBMPolicy:
    """Model 1: LightGBM Policy (Histogram-based GBDT, Leaf-wise split)"""
    def __init__(self, num_leaves: int = 63, learning_rate: float = 0.05, n_estimators: int = 250, min_child_samples: int = 50):
        self.params = {
            'objective': 'multiclass',
            'num_class': 7,
            'num_leaves': num_leaves,
            'learning_rate': learning_rate,
            'n_estimators': n_estimators,
            'min_child_samples': min_child_samples,
            'class_weight': 'balanced',
            'n_jobs': -1,
            'random_state': 42,
            'verbose': -1
        }
        self.clf = lgb.LGBMClassifier(**self.params) if LGB_AVAILABLE else None
        self.reg_size = lgb.LGBMRegressor(n_estimators=100, learning_rate=0.08, num_leaves=31, n_jobs=-1, random_state=42, verbose=-1) if LGB_AVAILABLE else None
        self.reg_sl = lgb.LGBMRegressor(n_estimators=100, learning_rate=0.08, num_leaves=31, n_jobs=-1, random_state=42, verbose=-1) if LGB_AVAILABLE else None
        self.reg_tp = lgb.LGBMRegressor(n_estimators=100, learning_rate=0.08, num_leaves=31, n_jobs=-1, random_state=42, verbose=-1) if LGB_AVAILABLE else None

    def fit(self, X: np.ndarray, y_act: np.ndarray, y_sz: np.ndarray, y_sl: np.ndarray, y_tp: np.ndarray):
        print("[M1 LightGBM] Fitting 7-class Action Classifier...")
        self.clf.fit(X, y_act)
        print("[M1 LightGBM] Fitting Size, SL, TP Regressors...")
        self.reg_size.fit(X, y_sz)
        self.reg_sl.fit(X, y_sl)
        self.reg_tp.fit(X, y_tp)
        return self

    def predict_step(self, x_1x40: np.ndarray, threshold: float = 0.35) -> Tuple[int, float, float, float]:
        probs = self.clf.predict_proba(x_1x40)[0]
        best_a = int(np.argmax(probs))
        if probs[best_a] < threshold:
            best_a = 0  # Default to HOLD on low confidence
        sz = float(np.clip(self.reg_size.predict(x_1x40)[0], 0.1, 1.0))
        sl = float(np.clip(self.reg_sl.predict(x_1x40)[0], 1.0, 4.0))
        tp = float(np.clip(self.reg_tp.predict(x_1x40)[0], 1.5, 7.0))
        return best_a, sz, sl, tp


class CatBoostPolicy:
    """Model 2: CatBoost Policy (Ordered Boosting, Oblivious Symmetric Trees)"""
    def __init__(self, depth: int = 6, learning_rate: float = 0.06, iterations: int = 300, l2_leaf_reg: float = 5.0):
        self.clf = cb.CatBoostClassifier(
            iterations=iterations,
            depth=depth,
            learning_rate=learning_rate,
            l2_leaf_reg=l2_leaf_reg,
            loss_function='MultiClass',
            auto_class_weights='Balanced',
            verbose=0,
            random_seed=42
        ) if CATBOOST_AVAILABLE else None
        self.reg_size = cb.CatBoostRegressor(iterations=150, depth=5, learning_rate=0.08, verbose=0, random_seed=42) if CATBOOST_AVAILABLE else None
        self.reg_sl = cb.CatBoostRegressor(iterations=150, depth=5, learning_rate=0.08, verbose=0, random_seed=42) if CATBOOST_AVAILABLE else None
        self.reg_tp = cb.CatBoostRegressor(iterations=150, depth=5, learning_rate=0.08, verbose=0, random_seed=42) if CATBOOST_AVAILABLE else None

    def fit(self, X: np.ndarray, y_act: np.ndarray, y_sz: np.ndarray, y_sl: np.ndarray, y_tp: np.ndarray):
        print("[M2 CatBoost] Fitting Ordered Boosting Policy...")
        self.clf.fit(X, y_act)
        self.reg_size.fit(X, y_sz)
        self.reg_sl.fit(X, y_sl)
        self.reg_tp.fit(X, y_tp)
        return self

    def predict_step(self, x_1x40: np.ndarray, threshold: float = 0.35) -> Tuple[int, float, float, float]:
        probs = self.clf.predict_proba(x_1x40)[0]
        best_a = int(np.argmax(probs))
        if probs[best_a] < threshold:
            best_a = 0
        sz = float(np.clip(self.reg_size.predict(x_1x40)[0], 0.1, 1.0))
        sl = float(np.clip(self.reg_sl.predict(x_1x40)[0], 1.0, 4.0))
        tp = float(np.clip(self.reg_tp.predict(x_1x40)[0], 1.5, 7.0))
        return best_a, sz, sl, tp


class XGBoostPolicy:
    """Model 3: XGBoost Depth-Constrained Policy (Regularized Depth-wise GBDT)"""
    def __init__(self, max_depth: int = 4, learning_rate: float = 0.05, n_estimators: int = 200, reg_alpha: float = 1.0, reg_lambda: float = 3.0):
        self.clf = xgb.XGBClassifier(
            max_depth=max_depth,
            learning_rate=learning_rate,
            n_estimators=n_estimators,
            reg_alpha=reg_alpha,
            reg_lambda=reg_lambda,
            subsample=0.8,
            colsample_bytree=0.8,
            objective='multi:softprob',
            num_class=7,
            n_jobs=-1,
            random_state=42
        ) if XGB_AVAILABLE else None
        self.reg_size = xgb.XGBRegressor(max_depth=4, n_estimators=100, learning_rate=0.08, n_jobs=-1, random_state=42) if XGB_AVAILABLE else None
        self.reg_sl = xgb.XGBRegressor(max_depth=4, n_estimators=100, learning_rate=0.08, n_jobs=-1, random_state=42) if XGB_AVAILABLE else None
        self.reg_tp = xgb.XGBRegressor(max_depth=4, n_estimators=100, learning_rate=0.08, n_jobs=-1, random_state=42) if XGB_AVAILABLE else None

    def fit(self, X: np.ndarray, y_act: np.ndarray, y_sz: np.ndarray, y_sl: np.ndarray, y_tp: np.ndarray):
        print("[M3 XGBoost] Fitting Depth-Constrained Policy...")
        self.clf.fit(X, y_act)
        self.reg_size.fit(X, y_sz)
        self.reg_sl.fit(X, y_sl)
        self.reg_tp.fit(X, y_tp)
        return self

    def predict_step(self, x_1x40: np.ndarray, threshold: float = 0.35) -> Tuple[int, float, float, float]:
        probs = self.clf.predict_proba(x_1x40)[0]
        best_a = int(np.argmax(probs))
        if probs[best_a] < threshold:
            best_a = 0
        sz = float(np.clip(self.reg_size.predict(x_1x40)[0], 0.1, 1.0))
        sl = float(np.clip(self.reg_sl.predict(x_1x40)[0], 1.0, 4.0))
        tp = float(np.clip(self.reg_tp.predict(x_1x40)[0], 1.5, 7.0))
        return best_a, sz, sl, tp


# =====================================================================
# FAMILY B: DEEP NEURAL NETWORKS (PYTORCH)
# =====================================================================

if TORCH_AVAILABLE:

    class ResMLPPolicy(nn.Module):
        """Model 4: Deep Multi-Head Residual MLP"""
        def __init__(self, input_dim: int = 40, hidden_dim: int = 128, dropout: float = 0.15):
            super().__init__()
            self.input_layer = nn.Sequential(
                nn.Linear(input_dim, hidden_dim),
                nn.LayerNorm(hidden_dim),
                nn.GELU(),
                nn.Dropout(dropout)
            )
            self.res_block1 = nn.Sequential(
                nn.Linear(hidden_dim, hidden_dim),
                nn.LayerNorm(hidden_dim),
                nn.GELU(),
                nn.Dropout(dropout)
            )
            self.res_block2 = nn.Sequential(
                nn.Linear(hidden_dim, hidden_dim),
                nn.LayerNorm(hidden_dim),
                nn.GELU(),
                nn.Dropout(dropout)
            )
            # Multi-Head Decoders
            self.action_head = nn.Sequential(nn.Linear(hidden_dim, 64), nn.GELU(), nn.Linear(64, 7))
            self.size_head = nn.Sequential(nn.Linear(hidden_dim, 32), nn.GELU(), nn.Linear(32, 1), nn.Sigmoid())
            self.order_head = nn.Sequential(nn.Linear(hidden_dim, 32), nn.GELU(), nn.Linear(32, 2), nn.Softplus())

        def forward(self, x: torch.Tensor) -> Tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
            h = self.input_layer(x)
            h = self.res_block1(h) + h
            h = self.res_block2(h) + h
            return self.action_head(h), self.size_head(h), self.order_head(h)


    class Chomp1d(nn.Module):
        """Removes trailing padding to ensure causality (no future leakage)"""
        def __init__(self, chomp_size: int):
            super().__init__()
            self.chomp_size = chomp_size

        def forward(self, x: torch.Tensor) -> torch.Tensor:
            return x[:, :, :-self.chomp_size].contiguous()


    class TemporalConvBlock(nn.Module):
        def __init__(self, in_channels: int, out_channels: int, kernel_size: int, dilation: int, dropout: float = 0.15):
            super().__init__()
            padding = (kernel_size - 1) * dilation
            self.conv1 = nn.Conv1d(in_channels, out_channels, kernel_size, padding=padding, dilation=dilation)
            self.chomp1 = Chomp1d(padding)
            self.norm1 = nn.BatchNorm1d(out_channels)
            self.relu1 = nn.GELU()
            self.drop1 = nn.Dropout(dropout)

            self.conv2 = nn.Conv1d(out_channels, out_channels, kernel_size, padding=padding, dilation=dilation)
            self.chomp2 = Chomp1d(padding)
            self.norm2 = nn.BatchNorm1d(out_channels)
            self.relu2 = nn.GELU()
            self.drop2 = nn.Dropout(dropout)

            self.downsample = nn.Conv1d(in_channels, out_channels, 1) if in_channels != out_channels else None

        def forward(self, x: torch.Tensor) -> torch.Tensor:
            res = x if self.downsample is None else self.downsample(x)
            out = self.drop1(self.relu1(self.norm1(self.chomp1(self.conv1(x)))))
            out = self.drop2(self.relu2(self.norm2(self.chomp2(self.conv2(out)))))
            return F.gelu(out + res)


    class TCNPolicy(nn.Module):
        """Model 5: Temporal Convolutional Network (Causal Dilated 1D-CNN)"""
        def __init__(self, num_inputs: int = 40, num_channels: List[int] = [64, 64, 128], kernel_size: int = 3, dropout: float = 0.15):
            super().__init__()
            layers = []
            for i in range(len(num_channels)):
                in_ch = num_inputs if i == 0 else num_channels[i - 1]
                out_ch = num_channels[i]
                dilation = 2 ** i
                layers.append(TemporalConvBlock(in_ch, out_ch, kernel_size, dilation, dropout))
            self.network = nn.Sequential(*layers)
            
            last_ch = num_channels[-1]
            self.action_head = nn.Sequential(nn.Linear(last_ch, 64), nn.GELU(), nn.Linear(64, 7))
            self.size_head = nn.Sequential(nn.Linear(last_ch, 32), nn.GELU(), nn.Linear(32, 1), nn.Sigmoid())
            self.order_head = nn.Sequential(nn.Linear(last_ch, 32), nn.GELU(), nn.Linear(32, 2), nn.Softplus())

        def forward(self, x: torch.Tensor) -> Tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
            # Input x: [Batch, Features] -> treat as single temporal step or reshape
            if x.dim() == 2:
                x = x.unsqueeze(-1)  # [Batch, Features, 1]
            y = self.network(x)[:, :, -1]  # Extract latest causal timestamp
            return self.action_head(y), self.size_head(y), self.order_head(y)


    class GRUAttentionPolicy(nn.Module):
        """Model 6: Gated Recurrent Unit with Temporal Self-Attention"""
        def __init__(self, input_dim: int = 40, hidden_dim: int = 64, num_layers: int = 2, dropout: float = 0.15):
            super().__init__()
            self.gru = nn.GRU(input_dim, hidden_dim, num_layers=num_layers, batch_first=True, dropout=dropout)
            self.attn_dense = nn.Linear(hidden_dim, 32)
            self.attn_vec = nn.Linear(32, 1, bias=False)
            
            self.action_head = nn.Sequential(nn.Linear(hidden_dim, 64), nn.GELU(), nn.Linear(64, 7))
            self.size_head = nn.Sequential(nn.Linear(hidden_dim, 32), nn.GELU(), nn.Linear(32, 1), nn.Sigmoid())
            self.order_head = nn.Sequential(nn.Linear(hidden_dim, 32), nn.GELU(), nn.Linear(32, 2), nn.Softplus())

        def forward(self, x: torch.Tensor) -> Tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
            if x.dim() == 2:
                x = x.unsqueeze(1)  # [Batch, SeqLen=1, Features]
            gru_out, _ = self.gru(x)  # [Batch, SeqLen, Hidden]
            
            # Temporal Attention
            u = torch.tanh(self.attn_dense(gru_out))
            scores = self.attn_vec(u)
            weights = F.softmax(scores, dim=1)
            context = torch.sum(weights * gru_out, dim=1)  # [Batch, Hidden]
            
            return self.action_head(context), self.size_head(context), self.order_head(context)


    class PatchTransformerPolicy(nn.Module):
        """Model 7: Patch Time-Series Transformer Policy"""
        def __init__(self, input_dim: int = 40, d_model: int = 64, nhead: int = 4, num_layers: int = 2, dropout: float = 0.15):
            super().__init__()
            self.proj = nn.Linear(input_dim, d_model)
            encoder_layer = nn.TransformerEncoderLayer(d_model=d_model, nhead=nhead, dim_feedforward=128, dropout=dropout, batch_first=True)
            self.transformer = nn.TransformerEncoder(encoder_layer, num_layers=num_layers)
            
            self.action_head = nn.Sequential(nn.Linear(d_model, 64), nn.GELU(), nn.Linear(64, 7))
            self.size_head = nn.Sequential(nn.Linear(d_model, 32), nn.GELU(), nn.Linear(32, 1), nn.Sigmoid())
            self.order_head = nn.Sequential(nn.Linear(d_model, 32), nn.GELU(), nn.Linear(32, 2), nn.Softplus())

        def forward(self, x: torch.Tensor) -> Tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
            if x.dim() == 2:
                x = x.unsqueeze(1)
            emb = self.proj(x)
            out = self.transformer(emb)[:, -1, :]
            return self.action_head(out), self.size_head(out), self.order_head(out)


# =====================================================================
# FAMILY C: QUANT HYBRIDS, SPECIALIZED LOSS, AND RL
# =====================================================================

class TwoStageMetaLabelingPolicy:
    """Model 8: Two-Stage Meta-Labeling (Marcos López de Prado Architecture)"""
    def __init__(self):
        # Stage 1: Primary Model (Proposes Direction Buy/Sell/Hold)
        self.primary_model = RandomForestClassifier(n_estimators=100, max_depth=5, random_state=42, n_jobs=-1)
        # Stage 2: Meta-Model (Predicts Probability of Success / Overcoming Friction)
        self.meta_model = LogisticRegression(C=1.0, max_iter=500, random_state=42)

    def fit(self, X: np.ndarray, y_act: np.ndarray):
        print("[M8 Meta-Labeling] Training Primary Direction Model...")
        self.primary_model.fit(X, y_act)
        
        # Meta-label: 1 if primary model was correct, 0 otherwise
        primary_preds = self.primary_model.predict(X)
        meta_y = (primary_preds == y_act).astype(int)
        
        print("[M8 Meta-Labeling] Training Secondary Meta-Model (Bet Sizing Probability)...")
        # Meta features: Market features + Primary model probability distribution
        primary_probs = self.primary_model.predict_proba(X)
        meta_X = np.hstack([X, primary_probs])
        self.meta_model.fit(meta_X, meta_y)
        return self

    def predict_step(self, x_1x40: np.ndarray, meta_threshold: float = 0.55) -> Tuple[int, float, float, float]:
        prim_act = int(self.primary_model.predict(x_1x40)[0])
        prim_probs = self.primary_model.predict_proba(x_1x40)
        meta_feat = np.hstack([x_1x40, prim_probs])
        p_success = float(self.meta_model.predict_proba(meta_feat)[0, 1])
        
        if p_success < meta_threshold and prim_act != 0:
            final_act = 0  # Cancel trade if meta-model assesses high friction risk
            size_frac = 0.0
        else:
            final_act = prim_act
            size_frac = float(np.clip(p_success, 0.2, 1.0))
            
        sl_atr = 2.0
        tp_atr = 3.5
        return final_act, size_frac, sl_atr, tp_atr


if TORCH_AVAILABLE:

    class CostSensitiveLoss(nn.Module):
        """Asymmetric Cost-Sensitive Loss penalizing false entries heavily"""
        def __init__(self, turnover_penalty_weight: float = 3.0):
            super().__init__()
            self.turnover_penalty_weight = turnover_penalty_weight
            self.ce = nn.CrossEntropyLoss(reduction='none')

        def forward(self, logits: torch.Tensor, targets: torch.Tensor) -> torch.Tensor:
            base_loss = self.ce(logits, targets)
            preds = logits.argmax(dim=-1)
            # If target was HOLD (0) but model predicted an ENTRY (1, 2, 3, 6), heavily penalize turnover
            unnecessary_trade_mask = (targets == 0) & (preds != 0)
            cost_multiplier = torch.where(unnecessary_trade_mask, self.turnover_penalty_weight, 1.0)
            return (base_loss * cost_multiplier).mean()


    class CostSensitivePolicyNet(nn.Module):
        """Model 9: Asymmetric Cost-Sensitive Network"""
        def __init__(self, input_dim: int = 40, hidden_dim: int = 128):
            super().__init__()
            self.net = nn.Sequential(
                nn.Linear(input_dim, hidden_dim),
                nn.LayerNorm(hidden_dim),
                nn.SiLU(),
                nn.Linear(hidden_dim, hidden_dim),
                nn.LayerNorm(hidden_dim),
                nn.SiLU()
            )
            self.action_head = nn.Linear(hidden_dim, 7)
            self.size_head = nn.Sequential(nn.Linear(hidden_dim, 1), nn.Sigmoid())
            self.order_head = nn.Sequential(nn.Linear(hidden_dim, 2), nn.Softplus())

        def forward(self, x: torch.Tensor) -> Tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
            h = self.net(x)
            return self.action_head(h), self.size_head(h), self.order_head(h)


    class ActorCriticPolicyNet(nn.Module):
        """Model 10: Deep Reinforcement Learning Actor-Critic Network (PPO formulation)"""
        def __init__(self, state_dim: int = 40, hidden_dim: int = 128):
            super().__init__()
            self.actor = nn.Sequential(
                nn.Linear(state_dim, hidden_dim),
                nn.LayerNorm(hidden_dim),
                nn.Tanh(),
                nn.Linear(hidden_dim, hidden_dim),
                nn.Tanh(),
                nn.Linear(hidden_dim, 7)
            )
            self.critic = nn.Sequential(
                nn.Linear(state_dim, hidden_dim),
                nn.LayerNorm(hidden_dim),
                nn.Tanh(),
                nn.Linear(hidden_dim, hidden_dim),
                nn.Tanh(),
                nn.Linear(hidden_dim, 1)  # Value function V(s)
            )
            self.size_head = nn.Sequential(nn.Linear(hidden_dim, 1), nn.Sigmoid())
            self.order_head = nn.Sequential(nn.Linear(hidden_dim, 2), nn.Softplus())

        def forward(self, x: torch.Tensor) -> Tuple[torch.Tensor, torch.Tensor, torch.Tensor, torch.Tensor]:
            h_actor = self.actor[:-1](x)
            action_logits = self.actor[-1](h_actor)
            value = self.critic(x)
            size = self.size_head(h_actor)
            order = self.order_head(h_actor)
            return action_logits, value, size, order
