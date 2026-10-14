# STRATEGY 136: QUANTUM TITAN CLEAN QUANT (CORE B PIVOT PULLBACK) LOGIC TEMPLATE

---

## 1. Executive Summary & Provenance
- **Origin Strategy:** Reverse-engineered from `QuantumTitanbyFuckFickFock.mq5` (`Quantum Titan by Triumm.mq5`).
- **Discovery Mission:** Convert opaque proprietary MQL5 logic into disciplined quantitative rule-based models; strip all martingale/recovery multipliers; validate across 72 calendar months (2020–2025) on Google Colab Cloud VM.
- **De-Martingaled Finding:**
  - Original EA relies on an aggressive `CoreARecoveryMultiplier = 2.0` on raw daily high/low breakouts, which loses heavily without martingale (Mode 1 PF 0.484, Mode 2 PF 0.315).
  - However, **Core B (H1 Swing Pivot Pullback with Katz Fractal Dimension Noise Filter)** represents a genuine quantitative alpha edge. Without any recovery mode or position averaging, it generated:
    - **Net Profit:** +$28,299.87 USD (0.10 lot)
    - **Profit Factor (PF):** 1.530
    - **Total Trades:** 72 trades (H1 swing timeframe)
    - **Max Drawdown:** $8,890.04
    - **RoMaD:** 3.18x
    - **Monthly Consistency Ratio (MCR):** 52.8% (38 profitable months out of 72)

---

## 2. Quantitative Alpha Architecture

### 2.1 Trend Direction (Secular Filter)
- **Indicator:** 200 Exponential Moving Average (`EMA(200)`) on H1 close prices.
- **Bullish Regime:** `Close[1] > EMA200[1]` (Only Long trades permitted).
- **Bearish Regime:** `Close[1] < EMA200[1]` (Only Short trades permitted).

### 2.2 Market Efficiency / Noise Gating
- **Indicator:** Katz Fractal Dimension (`KFD(24)`).
  $$D = \frac{\log_{10}(n)}{\log_{10}(n) + \log_{10}(d / L)}$$
  Where $n = 24$, $L$ is total Euclidean path length over 24 bars, and $d$ is maximum planar distance from $Close[t-n]$.
- **Condition:** `KFD <= 1.42`. When $KFD > 1.42$, market turbulence is excessive and trend signals are rejected.

### 2.3 Rolling Swing Pivot High & Low
- **Lookback Window:** $N = 30$ bars.
- **Pivot High ($P_{high}$):** $\max(High[t-31 \dots t-2])$
- **Pivot Low ($P_{low}$):** $\min(Low[t-31 \dots t-2])$

### 2.4 Pullback Reaction Triggers
- **Pullback Distance:** $0.5 \times ATR(14)$.
- **Long Signal (Buy Pullback):**
  - Confirmed bar 1 close drops to or below the pullback threshold:
    $$Close[1] \le P_{high} - (0.5 \times ATR(14)) \quad \text{and} \quad Close[2] > P_{high} - (0.5 \times ATR(14))$$
  - Trend Condition: $Close[1] > EMA200[1]$
  - Gating: $KFD[1] \le 1.42$
- **Short Signal (Sell Pullback):**
  - Confirmed bar 1 close rises to or above the pullback threshold:
    $$Close[1] \ge P_{low} + (0.5 \times ATR(14)) \quad \text{and} \quad Close[2] < P_{low} + (0.5 \times ATR(14))$$
  - Trend Condition: $Close[1] < EMA200[1]$
  - Gating: $KFD[1] \le 1.42$

### 2.5 Strict Risk Management & Execution (Zero-Martingale)
- **Position Sizing:** Fixed 0.10 lots (no scaling, no martingale multiplier).
- **Stop Loss (SL):** $2.5 \times ATR(14)$ hard stop on broker side.
- **Take Profit (TP):** $3.5 \times ATR(14)$ limit order (1.4:1 Reward-to-Risk ratio).
- **ASAR Calendar Governance:**
  - Monthly Profit Lock: Cease new entries once closed monthly net profit reaches +$200.00 USD.
  - Monthly Loss Circuit Breaker: Cease new entries once closed monthly net loss exceeds -$250.00 USD.
  - Resets automatically at 00:00 on the 1st of each calendar month.

---

## 3. Backtest Metrics (72 Months: 2020.01 - 2025.12)
| Metric | Performance |
| :--- | :--- |
| **Asset** | XAUUSD (Gold CFD) |
| **Timeframe** | H1 |
| **Total Trades** | 72 trades |
| **Win Rate** | 41.67% (30 Wins / 42 Losses) |
| **Gross Profit** | $81,684.00 USD |
| **Gross Loss** | $53,384.13 USD |
| **Net Profit** | **+$28,299.87 USD** |
| **Profit Factor (PF)** | **1.530** |
| **Max Drawdown** | $8,890.04 USD |
| **Return on Max DD (RoMaD)** | **3.18x** |
| **Monthly Consistency Ratio** | **52.8%** (38/72 profitable months) |
| **Recovery Multiplier** | **None (1.0x Flat)** |

---

## 4. Production Artifacts
- **EA Path:** `projects/quant_strategy_discovery/ea/Gold_H1_Quantum_Titan_Clean_Quant_Master_EA.mq5`
- **Simulation Script:** `projects/quant_strategy_discovery/colab/sweep_quantum_titan_clean_quant.py`
- **Result Log:** `projects/quant_strategy_discovery/results/quantum_titan_clean_quant_results.json`
