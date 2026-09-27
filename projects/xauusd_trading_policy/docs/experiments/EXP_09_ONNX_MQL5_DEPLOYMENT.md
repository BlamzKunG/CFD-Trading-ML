# 🔬 Experiment Report: EXP-09-ONNX-MQL5-DEPLOYMENT

**Research Focus:** Production ONNX Neural Engine Export, Latency Benchmarking & MQL5 Integration
**Target Platform:** MetaTrader 5 Build 6063+ (Native ONNX Runtime Execution)
**Production Strategy:** Dual-Sleeve Asymmetric Portfolio Policy (Sleeve A Major + Sleeve B Micro)

## 1. Engine Specifications & Export Artifacts

- **ONNX Model:** [`xauusd_dual_sleeve_champion.onnx`](file:///root/CFD-Trading-ML/projects/xauusd_trading_policy/models/xauusd_dual_sleeve_champion.onnx) (25,066 bytes, Opset 13)
- **Production Configuration:** [`xauusd_production_config.json`](file:///root/CFD-Trading-ML/projects/xauusd_trading_policy/models/xauusd_production_config.json)
- **MetaTrader 5 Expert Advisor:** [`XAUUSD_DualSleeve_Production.mq5`](file:///root/CFD-Trading-ML/projects/xauusd_trading_policy/mql5/Experts/XAUUSD_DualSleeve_Production.mq5)

## 2. Real-Time Inference Latency Benchmarks

Benchmarked across 10,000 continuous M1 bar inference requests on CPU:

| Performance Metric | Measured Value | Production Requirement | Status |
| :--- | :---: | :---: | :---: |
| **Mean Inference Latency** | **30.17 µs (0.030 ms)** | < 2,000 µs (2.0 ms) | ✅ PASS |
| **Median Latency** | **25.60 µs (0.026 ms)** | < 1,000 µs (1.0 ms) | ✅ PASS |
| **P95 Latency** | **45.25 µs (0.045 ms)** | < 5,000 µs (5.0 ms) | ✅ PASS |
| **P99 Latency** | **73.29 µs (0.073 ms)** | < 10,000 µs (10.0 ms) | ✅ PASS |
| **Engine Throughput** | **30,939 bars/sec** | > 1,000 bars/sec | ✅ PASS |
| **Max Numerical Error (vs PyTorch)** | **1.221895e-06** | < 1.00e-04 | ✅ PASS |

## 3. Dual-Sleeve Production Architecture Summary

The deployed system executes two asymmetric risk sleeves:
1. **Sleeve A (Trend Sniper Sleeve):**
   - Condition: `|dist_ema200_atr| <= 0.5` AND `atr_ratio >= 0.85`
   - Sizing: Heavy allocation (0.18 to 0.28 lot)
   - Expectancy: **Profit Factor 2.25**, Win Rate **54.3%**, Drawdown **6.7%**
2. **Sleeve B (Opportunistic Breakout Sleeve):**
   - Condition: Meta-Confidence >= 0.52 without full trend alignment
   - Sizing: Micro allocation (0.03 lot fixed)
   - Function: Harvests residual positive expectancy while strictly containing noise friction

## 4. Overall Master Research Milestone Summary

Across 9 sequential autonomous experiments, the quantitative research loop achieved:
- **Fee Drag Eradication:** Slashed churn from 40,000+ trades to 427 high-conviction trades.
- **Net Profit Growth:** Scaled from -$180,000 losses (raw supervised) to **+$5,283.33 (+52.8% return)** under full realistic friction.
- **Institutional Risk Profile:** Elevated Profit Factor from < 0.60 to **1.68 – 2.25** and contained Max Drawdown below 13.2%.
- **Full Deployment Readiness:** Zero-dependency native ONNX model with sub-millisecond execution.
