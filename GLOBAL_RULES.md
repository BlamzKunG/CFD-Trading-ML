# GLOBAL RULES: AUTONOMOUS QUANT ML RESEARCH & PRODUCTION TRADING ENGINE

> **Project Mandate & Global Repository Constitution**  
> *Target Assets:* XAUUSD (Gold), EURUSD  
> *Production Standard:* Real-Money Live Trading Viability, MQL5 Parity, Friction-Resistant Execution

---

## 1. Core Mission & Ultimate Objective (The Real-Trading Principle)
1. **Primary Goal:** The primary objective of this program is **NOT** merely training machine learning models, maximizing isolated backtest metrics, curve-fitting parameters, or chasing artificially high Profit Factors with tiny sample sizes.
2. **Ultimate Destination:** The ultimate goal is to discover, design, engineer, validate, and deploy a **robust, production-grade ML algorithmic trading system capable of REAL-MONEY LIVE TRADING**.
3. **Microstructure Grounding:** Every research decision, architecture, feature, target, and risk policy must be evaluated under realistic execution realities: broker spread, commissions, slippage, liquidity voids, and non-stationary regime shifts.
4. **End-to-End System:** Research encompasses the entire pipeline: signal discovery, feature representation, execution simulation, risk budgeting, portfolio allocation, ONNX compilation, and 1:1 parity MQL5 Expert Advisor code.

---

## 2. Realistic Trade Frequency & Sample Size Mandate (The Real-World Volume Law)
1. **The Small-Sample Fallacy:** Systems that produce only 20–30 trades per calendar year (~2 to 3 trades per month on 350,000+ M1 bars) suffer from severe small-sample selection bias, fail statistical significance tests, and leave trading capital idle >99% of the trading year. Such systems are **practically unusable for live trading**.
2. **Target Annual Volume:** Intraday policies evaluated on 1-year historical out-of-sample data (e.g. 2025 M1 data) must target **150 to 500+ high-conviction trades per year (~1 to 3 trades per active trading day)**.
3. **Confluence-Driven Volume Expansion:** Trade volume must **NEVER** be artificially increased by loosening risk filters, lowering probability thresholds into market noise, or taking unconfirmed trades. Instead, volume must be unlocked through **Multi-Level Structural Confluences**:
   - Asia Session High/Low Liquidity Sweeps during London Open.
   - Prior Day High/Low & H1/M15 Key Support/Resistance Rejections.
   - Multi-Bar Liquidity Void / Fair Value Gap (FVG) Retests with volume absorption.
   - Intraday Order Flow Imbalance and Volume Force Spikes ($VFS \ge 1.10$, $VDP$ directional confirmation).

---

## 3. Forward Testing Protocol Boundary
1. **Agent Evaluation Scope:** The autonomous research agent conducts feature engineering, historical in-sample training, temporal walk-forward validation, and realistic out-of-sample backtesting across historical data (e.g., 2020–2025).
2. **User Forward Testing:** Live/forward testing on out-of-sample forward datasets (e.g., 2026 data) is reserved exclusively for the user (*"เรื่อง forward test ไม่ต้องก็ได้เดี๋ยวฉันทำเอง"*). The agent does not execute 2026 forward tests unless explicitly directed by the user.
3. **Deployment Deliverables:** For every verified strategy, the agent delivers ready-to-run artifacts: trained `.joblib` pipelines, quantized `.onnx` inference engines, and plug-and-play `.mq5` Expert Advisors for live forward testing by the user.

---

## 4. Scale-Invariance & Input Price Normalization Mandate
1. **The 4,000 vs 2,000 Problem:** Gold at $4,000 must be interpreted mathematically the same way as Gold at $2,000. **NEVER feed raw absolute prices (e.g. Close = 2750.50, High = 2760.00) directly into ML models.**
2. **Scale-Invariant Representations:** All model inputs must be scale-invariant:
   - Log returns: $\ln(C_t / C_{t-k})$
   - ATR-normalized price distances: $(P_t - \text{MA}_k) / \text{ATR}_k$
   - Percentage volatility bands: $(High - Low) / Close$
   - Rolling z-scores, rolling quantiles, and dimensionless volume momentum ratios.
3. **Diversity of Normalization:** The normalization method is **NOT fixed to a single static formula**. Researchers are encouraged to explore diverse scale-invariant representations (e.g., adaptive ATR scaling, Rolling Robust MAD, MinMax quantiles, fractional differentiation) to discover richer predictive alphas.

---

## 5. Real-Chart Execution & Trade Placement Integrity
1. **Dual Representation Principle:** Even though input features and model predictions operate in normalized, scale-invariant vector spaces, **ALL Trade Execution, Orders, Stop-Loss (SL), Take-Profit (TP), and Trailing Stops MUST BE PLACED ON THE ACTUAL REAL-CHART PRICE**.
2. **Backtest Fidelity:** Every backtest and execution simulator must convert normalized exit parameters (e.g. $2.0 \times \text{ATR}$ or percentage bands) back into actual chart price levels at the time of order placement.
3. **Execution Realistic Costing:** Every trade simulation must incorporate:
   - Gold (XAUUSD): Bid-Ask spread of $0.25–$0.30 per ounce + slippage buffer.
   - FX Pairs: Appropriate spread + broker commission.

---

## 6. Empirical Microstructure Friction Law
1. **Friction Ratio Definition:**
   $$\Phi = \frac{\text{Spread} + \text{Commission}}{\text{ATR}}$$
2. **Microstructure Viability Threshold:** High-turnover micro-strategies are mathematically non-viable when $\Phi > 25\%$.
3. **Asset Specific Roles:**
   - **XAUUSD (Gold M1):** $\Phi \approx 12.5\%$ (Spread $0.25 on ATR $2.00). Ideal primary intraday execution vehicle with vast net alpha capacity.
   - **EURUSD (Euro M1):** $\Phi \approx 70.0\%$ (Spread + Comm 1.4 pips on ATR 2.0 pips). High-frequency M1 execution suffers fatal spread churn. EURUSD serves strictly as an **exogenous macro/regime informational lead** or higher-timeframe swing filter for Gold.

---

## 7. Temporal Integrity & Strict Causality
1. **Zero Look-Ahead Bias:** Strict temporal ordering must be maintained. Future data must never leak into feature calculation, rolling statistics, scaler fits, label generation, or threshold optimization.
2. **Causal Preprocessing:** Scalers, PCA transforms, or normalization parameters must be fit strictly on in-sample training folds and applied causally to validation/test folds.

---

## 8. Strict 1:1 ML-to-MQL5 Parity & Real-Time Inference
1. **Exact Parity Requirement:** For every production trading policy, an identical MQL5 Expert Advisor (`.mq5`) must be generated. Feature calculations, indicators, normalization, thresholds, and trade management in MQL5 must match the Python backtest with 100% mathematical parity.
2. **Sub-50 µs ONNX Inference:** Machine learning models must be exported to ONNX format with verified mean inference latency under **50 µs** per bar on CPU, ensuring zero execution lag during live tick processing in MetaTrader 5.

---

## 9. Artifact Persistence & Triple Redundancy
1. **Persistence Obligation:** Every experiment must save:
   - Scikit-learn / PyTorch / LightGBM pipeline (`.joblib` or `.pt`).
   - Exported and validated ONNX model (`.onnx`).
   - Complete experiment report and performance charts (`projects/xauusd_trading_policy/docs/experiments/`).
   - MQL5 Expert Advisor script (`projects/xauusd_trading_policy/mql5/experts/`).
   - Updated central registry entry in `champion_models_registry.json`.
2. **Triple Redundancy Sync:**
   - Local Git repository (`/root/CFD-Trading-ML/`).
   - Remote GitHub repository (`origin main`).
   - Mobile / Physical storage backup (`/storage/emulated/0/Download/EA/CFD-Trading-ML/`).

---

## 10. Git Commit Identity & Standards
1. **Author Identity:** All git commits must strictly use the project identity:
   ```bash
   git config user.name "BlamzKunG"
   git config user.email "blamzkung@users.noreply.github.com"
   ```
2. **Commit Message Format:** Conventional commits (e.g. `feat(exp71): ...`, `docs: ...`, `fix: ...`).

---

## 11. Autonomous Continuous Execution Mandate ("ห้ามหยุดถ้าไม่สั่งหยุด")
1. **Unconditional Research Loop:** The research agent operates autonomously and continuously across hypotheses, model training, validation, MQL5 generation, and persistence.
2. **No Halting Without Command:** The agent must never stop or idle awaiting user prompts between research stages unless explicitly ordered to pause by the user.

---

## 12. Priority 1 Anti-Stuck Task Protocol
1. **Mandatory Immediate Inspection:** Immediately after any background task, command execution, or training script finishes, the very **FIRST** action performed by the agent must be:
   ```bash
   manage_task list
   ```
2. **Zero Orphaned Tasks:** Any completed, hung, or zombie tasks must be immediately killed using `manage_task kill` before starting any new tool invocation or experiment.
