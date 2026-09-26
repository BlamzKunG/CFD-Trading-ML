"""
=============================================================================
Full End-to-End Colab GPU Training Runner
=============================================================================
Runs directly on Google Colab with Tesla T4 GPU:
1. Loads M1 CSV dataset
2. Strict train/val split (2020-2024 train, 2025 val, 2026 LOCKED)
3. Computes 31 scale-invariant market features
4. Generates augmented counterfactual state-action pairs
5. Trains PyTorch Deep Multi-Head Policy Network on GPU
6. Exports ONNX model for MetaTrader 5 (Opset 13, IR 8)
7. Runs closed-loop event-driven backtesting on 2025 data
8. Saves performance metrics and pushes to GitHub
=============================================================================
"""

import os
import sys
import json
import time
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import torch

# Add repository and project to path
root_repo_dir = "/content/XAUUSD-Trading-Policy-ML"
repo_dir = os.path.join(root_repo_dir, "projects", "xauusd_trading_policy")
for p in [root_repo_dir, repo_dir]:
    if p not in sys.path:
        sys.path.insert(0, p)

import importlib
import scripts.features_policy as fp
import scripts.counterfactual_simulator as cs
import scripts.train_policy_suite as tps
import scripts.backtest_policy_evaluator as bpe

importlib.reload(fp)
importlib.reload(cs)
importlib.reload(tps)
importlib.reload(bpe)

from scripts.features_policy import extract_market_state_features, MARKET_FEATURE_NAMES, POSITION_FEATURE_NAMES
from scripts.counterfactual_simulator import build_augmented_training_dataset, ACTION_NAMES
from scripts.train_policy_suite import train_pytorch_policy, export_model_to_onnx, save_policy_metadata
from scripts.backtest_policy_evaluator import run_closed_loop_backtest

def main():
    print("=" * 70)
    print("🚀 STARTING XAUUSD TRADING POLICY TRAINING ON GOOGLE COLAB GPU")
    print("=" * 70)
    device = "cuda" if torch.cuda.is_available() else "cpu"
    print(f"[Hardware] PyTorch {torch.__version__} | Device: {device.upper()}")
    if device == "cuda":
        print(f"[Hardware] GPU: {torch.cuda.get_device_name(0)}")

    csv_path = "/content/xauusd_m1.csv"
    if not os.path.exists(csv_path):
        raise FileNotFoundError(f"Dataset not found at {csv_path}")

    # 1. Load Data
    t0 = time.time()
    print(f"\n[Step 1/6] Loading M1 dataset from {csv_path}...")
    df_raw = pd.read_csv(csv_path)
    print(f"Loaded {len(df_raw):,} bars in {time.time() - t0:.1f}s")

    # Datetime parse & sort
    if 'datetime' in df_raw.columns:
        df_raw['dt'] = pd.to_datetime(df_raw['datetime'])
    elif 'timestamp' in df_raw.columns:
        df_raw['dt'] = pd.to_datetime(df_raw['timestamp'], unit='s')
    else:
        df_raw['dt'] = pd.to_datetime(df_raw.index)

    df_raw.sort_values('dt', inplace=True)
    df_raw.reset_index(drop=True, inplace=True)

    # Strict Data Hygiene
    # Train: 2020.01.01 to 2024.12.31
    # Validation: 2025.01.01 to 2025.12.31
    # 2026: STRICTLY LOCKED
    train_mask = (df_raw['dt'] >= '2020-01-01') & (df_raw['dt'] < '2025-01-01')
    val_mask = (df_raw['dt'] >= '2025-01-01') & (df_raw['dt'] < '2026-01-01')

    df_train = df_raw[train_mask].copy().reset_index(drop=True)
    df_val = df_raw[val_mask].copy().reset_index(drop=True)

    print(f"Train Set (2020-2024): {len(df_train):,} bars ({df_train['dt'].min()} -> {df_train['dt'].max()})")
    print(f"Validation Set (2025):  {len(df_val):,} bars ({df_val['dt'].min()} -> {df_val['dt'].max()})")
    print("🔒 2026 Data Status: STRICTLY LOCKED & UNTOUCHED")

    # 2. Feature Extraction
    print("\n[Step 2/6] Extracting 31 scale-invariant stationary market features...")
    feat_train, atr_train, close_train = extract_market_state_features(df_train)
    feat_val, atr_val, close_val = extract_market_state_features(df_val)

    warmup = 200
    feat_train = feat_train.iloc[warmup:].fillna(0.0).reset_index(drop=True)
    df_train = df_train.iloc[warmup:].reset_index(drop=True)
    atr_train = atr_train.iloc[warmup:].reset_index(drop=True)
    close_train = close_train.iloc[warmup:].reset_index(drop=True)

    feat_val = feat_val.iloc[warmup:].fillna(0.0).reset_index(drop=True)
    df_val = df_val.iloc[warmup:].reset_index(drop=True)
    atr_val = atr_val.iloc[warmup:].reset_index(drop=True)
    close_val = close_val.iloc[warmup:].reset_index(drop=True)

    print(f"Train Market Features: {feat_train.shape} | Val Market Features: {feat_val.shape}")

    # 3. Counterfactual Teacher Simulation
    print("\n[Step 3/6] Running Counterfactual Teacher Simulator (Horizon=60, Step=4)...")
    t_cf = time.time()
    X_train, y_act_train, y_sz_train, y_sl_train, y_tp_train = build_augmented_training_dataset(
        market_features=feat_train,
        close_prices=close_train.to_numpy(),
        high_prices=df_train['high'].to_numpy(),
        low_prices=df_train['low'].to_numpy(),
        atr_values=atr_train.to_numpy(),
        horizon=60,
        subsample_step=4
    )
    print(f"Generated {len(X_train):,} training instances with 40 features in {time.time() - t_cf:.1f}s")

    # 4. Train Deep Multi-Head Policy Model
    print("\n[Step 4/6] Training PyTorch Multi-Head Policy Network on GPU...")
    model = train_pytorch_policy(
        X_train=X_train,
        y_action_train=y_act_train,
        y_size_train=y_sz_train,
        y_sl_train=y_sl_train,
        y_tp_train=y_tp_train,
        epochs=30,
        batch_size=1024,
        lr=1e-3,
        device=device
    )

    # 5. Export to ONNX
    print("\n[Step 5/6] Exporting Model to ONNX (Opset 13, IR 8) for MT5...")
    onnx_path = os.path.join(repo_dir, "models", "xauusd_trading_policy.onnx")
    export_model_to_onnx(model, onnx_path, input_dim=40, opset_version=13)

    # Save Metadata
    metadata_path = os.path.join(repo_dir, "models", "policy_metadata.json")
    save_policy_metadata(
        output_path=metadata_path,
        feature_names=MARKET_FEATURE_NAMES + POSITION_FEATURE_NAMES,
        action_names=ACTION_NAMES,
        mean_stats=np.mean(X_train, axis=0),
        std_stats=np.std(X_train, axis=0)
    )

    # 6. Closed-Loop Backtesting on 2025 Out-of-Sample Data
    print("\n[Step 6/6] Executing Closed-Loop Backtest on 2025 Out-of-Sample Data...")
    model.eval()
    dev = next(model.parameters()).device

    def policy_predictor(state_1x40: np.ndarray):
        with torch.no_grad():
            t_in = torch.tensor(state_1x40, dtype=torch.float32, device=dev)
            logits, size, order = model(t_in)
            act_id = int(torch.argmax(logits, dim=-1).item())
            sz = float(size.item())
            sl_atr = float(order[0, 0].item())
            tp_atr = float(order[0, 1].item())
        return act_id, sz, sl_atr, tp_atr

    results = run_closed_loop_backtest(
        df=df_val,
        market_features=feat_val,
        atr_series=atr_val,
        policy_predictor=policy_predictor,
        initial_balance=10000.0,
        lot_base=0.1,
        spread_points=2.0
    )

    print("\n" + "=" * 50)
    print("📊 2025 OUT-OF-SAMPLE CLOSED-LOOP RESULTS")
    print("=" * 50)
    print(f"Initial Balance:   ${results['initial_balance']:,.2f}")
    print(f"Final Equity:      ${results['final_equity']:,.2f}")
    print(f"Net Profit:        ${results['net_profit']:,.2f} ({results['return_pct']:.2f}%)")
    print(f"Profit Factor:     {results['profit_factor']:.2f}")
    print(f"Win Rate:          {results['win_rate']:.2f}%")
    print(f"Max Drawdown:      {results['max_drawdown_pct']:.2f}%")
    print(f"Total Trades:      {results['total_trades']:,}")
    print(f"Avg Trade PnL:     ${results['avg_trade_pnl']:.2f}")
    print("=" * 50)

    # Save Equity Curve Plot
    plot_path = os.path.join(repo_dir, "docs", "equity_curve_2025.png")
    os.makedirs(os.path.dirname(plot_path), exist_ok=True)
    plt.figure(figsize=(14, 6))
    plt.plot(results['equity_curve'], label='Trading Policy Equity ($)', color='#10b981', linewidth=1.5)
    plt.title('2025 Out-of-Sample Closed-Loop Backtest (XAUUSD M1)', fontsize=14, fontweight='bold')
    plt.xlabel('Time (M1 Bars)', fontsize=12)
    plt.ylabel('Account Equity ($)', fontsize=12)
    plt.grid(True, alpha=0.3)
    plt.legend()
    plt.tight_layout()
    plt.savefig(plot_path, dpi=300)
    print(f"[Plot] Saved equity curve to {plot_path}")

    # Push to GitHub
    print("\n[GitHub] Committing and pushing trained models to repository...")
    os.system(f"cd {root_repo_dir} && git config user.name 'BlamzKunG' && git config user.email 'blamzkung@users.noreply.github.com'")
    gh_token = os.environ.get("GITHUB_TOKEN", "")
    if gh_token:
        os.system(f"cd {root_repo_dir} && git remote set-url origin https://BlamzKunG:{gh_token}@github.com/BlamzKunG/XAUUSD-Trading-Policy-ML.git")
    os.system(f"cd {root_repo_dir} && git add projects/xauusd_trading_policy/models/ projects/xauusd_trading_policy/docs/ && git commit -m 'feat(model): add trained ONNX policy model and 2025 backtest results [skip ci]'")
    push_out = os.popen(f"cd {root_repo_dir} && git push origin main").read()
    print(f"[GitHub Push] {push_out}")

    print("\n🎉 ALL TRAINING, EVALUATION, AND EXPORT TASKS COMPLETED SUCCESSFULLY!")

if __name__ == "__main__":
    main()
