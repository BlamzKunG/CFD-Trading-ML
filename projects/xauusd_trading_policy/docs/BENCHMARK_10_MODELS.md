# 🏆 10 Quant ML Trading Policy Models: 2025 Out-of-Sample Benchmark

Strictly evaluated on out-of-sample 2025 M1 data (350,807 bars) with realistic transaction friction ($0.20 spread, $0.10 slippage, $6.0/lot comm).

| Model ID | Paradigm / Algorithm | Net Profit ($) | Return (%) | Profit Factor | Win Rate (%) | Max DD (%) | Trades | Sharpe | Train Time (s) |
| :--- | :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **M10_ActorCritic_RL** | ActorCritic_RL | $29,528.54 | 295.1% | **1.10** | 39.1% | 103.8% | 48,425 | 0.12 | 390.6s |
| **M3_XGBoost** | XGBoost | $-31,027.07 | -309.9% | **0.84** | 35.0% | 316.7% | 10,381 | -1.07 | 95.0s |
| **M5_TCN** | TCN | $-90,836.84 | -908.3% | **0.63** | 42.6% | 909.8% | 44,211 | 1.09 | 272.7s |
| **M1_LightGBM** | LightGBM | $-92,487.40 | -924.8% | **0.61** | 39.2% | 930.9% | 39,277 | -1.82 | 90.0s |
| **M7_PatchTransformer** | PatchTransformer | $-92,039.05 | -920.3% | **0.60** | 43.2% | 921.0% | 42,900 | 0.85 | 263.5s |
| **M2_CatBoost** | CatBoost | $-107,594.84 | -1075.9% | **0.58** | 44.9% | 1077.8% | 39,727 | 1.69 | 120.0s |
| **M4_ResMLP** | ResMLP | $-134,452.07 | -1344.5% | **0.57** | 41.1% | 1344.3% | 54,266 | 1.84 | 197.5s |
| **M6_GRU_Attention** | GRU_Attention | $-176,257.04 | -1762.6% | **0.55** | 39.1% | 1762.7% | 59,492 | 1.09 | 202.5s |
| **M9_CostSensitive** | CostSensitive | $-99,247.51 | -992.5% | **0.42** | 37.6% | 991.9% | 18,008 | 1.04 | 355.7s |


*Note: 2026 data remains strictly locked and untouched.*
