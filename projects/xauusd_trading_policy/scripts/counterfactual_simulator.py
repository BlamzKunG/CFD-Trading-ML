"""
=============================================================================
XAUUSD Trading Policy: Counterfactual Teacher Simulator
=============================================================================
Purpose:
- Generates optimal dynamic policy labels without lookahead bias during runtime.
- For each historical timestamp t, simulates prospective outcomes across multiple
  counterfactual position states (Flat, Long Profit, Long Loss, Short Profit, Short Loss).
- Evaluates prospective actions with realistic transaction friction (spread + commission)
  and risk penalties (drawdown penalization).
- Assigns optimal action a*, optimal risk size s*, and optimal dynamic SL/TP targets.
=============================================================================
"""

import numpy as np
import pandas as pd
from typing import Tuple, Dict, List

# Action Definitions
ACTION_HOLD = 0         # No action / Hold current state
ACTION_OPEN_LONG = 1    # Open Long (Flat -> Long)
ACTION_OPEN_SHORT = 2   # Open Short (Flat -> Short)
ACTION_ADD = 3          # Scale into winning position
ACTION_REDUCE = 4       # Scale out / cut risk
ACTION_CLOSE = 5        # Close position completely
ACTION_REVERSE = 6      # Flip position to opposite direction

ACTION_NAMES = {
    ACTION_HOLD: "HOLD",
    ACTION_OPEN_LONG: "OPEN_LONG",
    ACTION_OPEN_SHORT: "OPEN_SHORT",
    ACTION_ADD: "ADD",
    ACTION_REDUCE: "REDUCE",
    ACTION_CLOSE: "CLOSE",
    ACTION_REVERSE: "REVERSE"
}

# Synthetic Counterfactual Position States to sample per timestamp
# Format: (pos_dir, pos_size_frac, unrealized_pnl_atr, time_in_pos_norm, dist_to_sl_atr, dist_to_tp_atr, max_dd_atr, bars_since_act)
SAMPLE_POSITION_STATES = [
    # 0. FLAT
    (0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 1.0),
    # 1. LONG in Profit (+1.2 ATR)
    (1.0, 0.5, 1.2, 0.35, 1.5, 2.5, 0.2, 0.2),
    # 2. LONG in Loss (-0.9 ATR)
    (1.0, 0.5, -0.9, 0.45, 0.8, 3.0, 1.1, 0.3),
    # 3. SHORT in Profit (+1.2 ATR)
    (-1.0, 0.5, 1.2, 0.35, 1.5, 2.5, 0.2, 0.2),
    # 4. SHORT in Loss (-0.9 ATR)
    (-1.0, 0.5, -0.9, 0.45, 0.8, 3.0, 1.1, 0.3),
]


def generate_counterfactual_rollouts(
    close_prices: np.ndarray,
    high_prices: np.ndarray,
    low_prices: np.ndarray,
    atr_values: np.ndarray,
    horizon: int = 60,
    friction_atr: float = 0.15,
    drawdown_penalty: float = 0.8
) -> Dict[str, np.ndarray]:
    """
    Simulates forward price trajectory over `horizon` bars (e.g. 60 M1 bars = 1 hour).
    Computes forward excursion, forward terminal return, and max adverse/favorable excursions.
    Vectorized for rapid execution.
    """
    n = len(close_prices)
    valid_len = n - horizon
    
    forward_ret_long = np.zeros(valid_len, dtype=np.float32)
    forward_ret_short = np.zeros(valid_len, dtype=np.float32)
    max_fav_long = np.zeros(valid_len, dtype=np.float32)
    max_adv_long = np.zeros(valid_len, dtype=np.float32)
    max_fav_short = np.zeros(valid_len, dtype=np.float32)
    max_adv_short = np.zeros(valid_len, dtype=np.float32)

    # Stride matrix for rolling window forward calculation
    # For large datasets, compute in sliding chunks to keep memory usage manageable
    chunk_size = 50000
    for start in range(0, valid_len, chunk_size):
        end = min(start + chunk_size, valid_len)
        chunk_c0 = close_prices[start:end]
        chunk_atr = np.maximum(np.nan_to_num(atr_values[start:end], nan=1.0), 1e-4)

        # Build forward matrix [chunk_len, horizon]
        sub_highs = np.lib.stride_tricks.sliding_window_view(high_prices[start:end + horizon], horizon)[:end - start]
        sub_lows = np.lib.stride_tricks.sliding_window_view(low_prices[start:end + horizon], horizon)[:end - start]
        sub_c_end = close_prices[start + horizon:end + horizon]

        # Terminal return
        fwd_ret = np.nan_to_num((sub_c_end - chunk_c0) / chunk_atr, nan=0.0)
        forward_ret_long[start:end] = fwd_ret
        forward_ret_short[start:end] = -fwd_ret

        # Max Favorable / Adverse Excursions (ATR units)
        max_h = np.max(sub_highs, axis=1)
        min_l = np.min(sub_lows, axis=1)

        max_fav_long[start:end] = np.nan_to_num((max_h - chunk_c0) / chunk_atr, nan=0.0)
        max_adv_long[start:end] = np.nan_to_num((chunk_c0 - min_l) / chunk_atr, nan=0.0)

        max_fav_short[start:end] = np.nan_to_num((chunk_c0 - min_l) / chunk_atr, nan=0.0)
        max_adv_short[start:end] = np.nan_to_num((max_h - chunk_c0) / chunk_atr, nan=0.0)

    return {
        "valid_len": valid_len,
        "fwd_ret_long": forward_ret_long,
        "fwd_ret_short": forward_ret_short,
        "max_fav_long": max_fav_long,
        "max_adv_long": max_adv_long,
        "max_fav_short": max_fav_short,
        "max_adv_short": max_adv_short
    }


def evaluate_counterfactual_actions(
    rollouts: Dict[str, np.ndarray],
    pos_state: Tuple[float, float, float, float, float, float, float, float],
    friction_atr: float = 0.15,
    drawdown_penalty: float = 0.7,
    min_edge_threshold: float = 0.3
) -> Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """
    Evaluates actions for a given position state:
    Returns:
    - best_action (int array): Optimal action [0..6]
    - target_size (float array): Optimal risk fraction [0.1..1.0]
    - target_sl (float array): Optimal Stop Loss distance in ATR
    - target_tp (float array): Optimal Take Profit distance in ATR
    """
    pos_dir, pos_size, unrl_pnl, time_in_pos, dist_sl, dist_tp, max_dd, bars_act = pos_state
    valid_len = rollouts["valid_len"]

    fwd_long = rollouts["fwd_ret_long"]
    fwd_short = rollouts["fwd_ret_short"]
    madv_long = rollouts["max_adv_long"]
    madv_short = rollouts["max_adv_short"]
    mfav_long = rollouts["max_fav_long"]
    mfav_short = rollouts["max_fav_short"]

    # Utilities for candidate actions
    # Utility = Expected Return - Drawdown Penalty - Transaction Friction
    u_hold = np.zeros(valid_len, dtype=np.float32)
    u_open_long = np.full(valid_len, -999.0, dtype=np.float32)
    u_open_short = np.full(valid_len, -999.0, dtype=np.float32)
    u_add = np.full(valid_len, -999.0, dtype=np.float32)
    u_reduce = np.full(valid_len, -999.0, dtype=np.float32)
    u_close = np.full(valid_len, -999.0, dtype=np.float32)
    u_reverse = np.full(valid_len, -999.0, dtype=np.float32)

    if pos_dir == 0.0:
        # FLAT STATE:
        # HOLD: utility = 0.0
        u_hold = np.zeros(valid_len, dtype=np.float32)
        # OPEN_LONG
        u_open_long = fwd_long - (drawdown_penalty * madv_long) - friction_atr
        # OPEN_SHORT
        u_open_short = fwd_short - (drawdown_penalty * madv_short) - friction_atr

        # Stack utilities: [HOLD, OPEN_LONG, OPEN_SHORT]
        utilities = np.stack([u_hold, u_open_long, u_open_short], axis=1)
        action_map = np.array([ACTION_HOLD, ACTION_OPEN_LONG, ACTION_OPEN_SHORT])
        raw_best = np.argmax(utilities, axis=1)
        best_action = action_map[raw_best]

        # Require a minimum positive edge over HOLD to open a trade (filters noise)
        max_u = np.max(utilities[:, 1:], axis=1)
        best_action = np.where(max_u < min_edge_threshold, ACTION_HOLD, best_action)

    elif pos_dir > 0.0:
        # LONG POSITION:
        # HOLD: forward continuation from current position
        u_hold = fwd_long - (drawdown_penalty * madv_long)
        # REDUCE: take partial profit / cut risk in half (drawdown risk on remaining half is significantly reduced)
        u_reduce = 0.5 * (unrl_pnl - friction_atr) + 0.5 * fwd_long - (drawdown_penalty * 0.35 * madv_long)
        # ADD: scale in if momentum is exceptionally strong
        u_add = (1.5 * fwd_long) - (drawdown_penalty * 1.5 * madv_long) - friction_atr
        # REVERSE: close long and open short
        u_reverse = (unrl_pnl - friction_atr) + (fwd_short - drawdown_penalty * madv_short - friction_atr)

        # Stack candidate utilities
        utilities = np.stack([u_hold, u_add, u_reduce, u_close, u_reverse], axis=1)
        action_map = np.array([ACTION_HOLD, ACTION_ADD, ACTION_REDUCE, ACTION_CLOSE, ACTION_REVERSE])
        best_action = action_map[np.argmax(utilities, axis=1)]

    else:
        # SHORT POSITION:
        # HOLD
        u_hold = fwd_short - (drawdown_penalty * madv_short)
        # CLOSE
        u_close = np.full(valid_len, unrl_pnl - friction_atr, dtype=np.float32)
        # REDUCE: take partial profit / cut risk in half
        u_reduce = 0.5 * (unrl_pnl - friction_atr) + 0.5 * fwd_short - (drawdown_penalty * 0.35 * madv_short)
        # ADD
        u_add = (1.5 * fwd_short) - (drawdown_penalty * 1.5 * madv_short) - friction_atr
        # REVERSE
        u_reverse = (unrl_pnl - friction_atr) + (fwd_long - drawdown_penalty * madv_long - friction_atr)

        utilities = np.stack([u_hold, u_add, u_reduce, u_close, u_reverse], axis=1)
        action_map = np.array([ACTION_HOLD, ACTION_ADD, ACTION_REDUCE, ACTION_CLOSE, ACTION_REVERSE])
        best_action = action_map[np.argmax(utilities, axis=1)]

    # Compute optimal continuous target size based on expected reward/risk ratio [0.2 .. 1.0]
    is_long_fav = (best_action == ACTION_OPEN_LONG) | ((pos_dir > 0) & (best_action != ACTION_CLOSE))
    fav = np.where(is_long_fav, mfav_long, mfav_short)
    adv = np.where(is_long_fav, madv_long, madv_short)
    rr_ratio = fav / (adv + 0.5)
    target_size = np.clip(0.2 + 0.25 * rr_ratio, 0.1, 1.0).astype(np.float32)

    # Compute optimal Stop Loss distance in ATR units (bounded [1.0, 3.5] ATR)
    target_sl = np.clip(adv * 1.25 + 0.5, 1.0, 3.5).astype(np.float32)

    # Compute optimal Take Profit distance in ATR units (bounded [1.5, 6.0] ATR)
    target_tp = np.clip(fav * 0.9, 1.5, 6.0).astype(np.float32)

    return best_action, target_size, target_sl, target_tp


def build_augmented_training_dataset(
    market_features: pd.DataFrame,
    close_prices: np.ndarray,
    high_prices: np.ndarray,
    low_prices: np.ndarray,
    atr_values: np.ndarray,
    horizon: int = 60,
    subsample_step: int = 5,
    states_to_sample: List[Tuple] = None
) -> Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """
    Constructs the full augmented training dataset:
    Inputs: [Market Features (31) + Position State Features (9)] = 40 Features
    Targets:
    1. Action (class integer 0..6)
    2. Size (float [0.1..1.0])
    3. Target SL (float in ATR units)
    4. Target TP (float in ATR units)
    """
    if states_to_sample is None:
        states_to_sample = SAMPLE_POSITION_STATES

    print(f"[Counterfactual Simulator] Computing forward rollouts (Horizon={horizon} bars)...")
    rollouts = generate_counterfactual_rollouts(
        close_prices=close_prices,
        high_prices=high_prices,
        low_prices=low_prices,
        atr_values=atr_values,
        horizon=horizon
    )
    valid_len = rollouts["valid_len"]

    # Indices to subsample (to prevent high auto-correlation and keep dataset size efficient)
    sample_indices = np.arange(0, valid_len, subsample_step)
    n_samples = len(sample_indices)

    market_feat_matrix = market_features.iloc[sample_indices].to_numpy(dtype=np.float32)

    all_features = []
    all_actions = []
    all_sizes = []
    all_sls = []
    all_tps = []

    print(f"[Counterfactual Simulator] Generating counterfactual pairs for {len(states_to_sample)} position states...")
    for p_idx, pos_state in enumerate(states_to_sample):
        act, size, sl, tp = evaluate_counterfactual_actions(rollouts, pos_state)

        # Slice to subsampled indices
        act_sub = act[sample_indices]
        size_sub = size[sample_indices]
        sl_sub = sl[sample_indices]
        tp_sub = tp[sample_indices]

        # Construct position feature block for this state: shape [n_samples, 9]
        # (pos_dir, pos_size_frac, entry_dist_atr, unrealized_pnl_atr, time_in_pos_norm, dist_to_sl_atr, dist_to_tp_atr, max_dd_atr, bars_since_act)
        pos_block = np.zeros((n_samples, 9), dtype=np.float32)
        pos_block[:, 0] = pos_state[0]  # pos_dir
        pos_block[:, 1] = pos_state[1]  # pos_size_frac
        pos_block[:, 2] = pos_state[2]  # entry_dist_atr (approx equal to unrl_pnl for unit lot)
        pos_block[:, 3] = pos_state[2]  # unrealized_pnl_atr
        pos_block[:, 4] = pos_state[3]  # time_in_pos_norm
        pos_block[:, 5] = pos_state[4]  # dist_to_sl_atr
        pos_block[:, 6] = pos_state[5]  # dist_to_tp_atr
        pos_block[:, 7] = pos_state[6]  # max_drawdown_atr
        pos_block[:, 8] = pos_state[7]  # bars_since_action_norm

        # Concatenate: [Market Feats (31) + Pos Feats (9)] = 40 Feats
        combined_feats = np.hstack([market_feat_matrix, pos_block])

        all_features.append(combined_feats)
        all_actions.append(act_sub)
        all_sizes.append(size_sub)
        all_sls.append(sl_sub)
        all_tps.append(tp_sub)

    X = np.vstack(all_features)
    y_action = np.concatenate(all_actions)
    y_size = np.concatenate(all_sizes)
    y_sl = np.concatenate(all_sls)
    y_tp = np.concatenate(all_tps)

    # Ensure absolute numerical cleanliness (no NaNs or Infs)
    X = np.nan_to_num(X, nan=0.0, posinf=10.0, neginf=-10.0).astype(np.float32)
    y_size = np.nan_to_num(y_size, nan=0.5, posinf=1.0, neginf=0.1).astype(np.float32)
    y_sl = np.nan_to_num(y_sl, nan=2.0, posinf=3.5, neginf=1.0).astype(np.float32)
    y_tp = np.nan_to_num(y_tp, nan=3.0, posinf=6.0, neginf=1.5).astype(np.float32)

    print(f"[Counterfactual Simulator] Done! Generated {len(X):,} augmented training instances.")
    unique_acts, counts = np.unique(y_action, return_counts=True)
    for u, c in zip(unique_acts, counts):
        print(f"  - Action {u} ({ACTION_NAMES.get(u, 'UNKNOWN')}): {c:,} ({c/len(y_action)*100:.1f}%)")

    return X, y_action, y_size, y_sl, y_tp
