# Strategy 46: Gold H1 Choppiness Index & Chande Momentum Dynamic Expansion (CHOP-CMO)

## 1. Executive Summary & Strategy Overview
- **Strategy ID:** STRATEGY_46
- **Identifier:** CHOP-CMO (Choppiness Index & Chande Momentum Oscillator)
- **Asset Class:** XAUUSD CFD (Gold)
- **Execution Timeframe:** H1 (Resampled from raw M1 data)
- **Audit Period:** 2020-01-01 to 2025-12-30 (72 Calendar Months)
- **Performance:**
  - **Profit Factor (PF):** **1.173**
  - **Net Profit:** **+$3,360.30** (0.10 Standard Lot)
  - **Max Drawdown:** **$1,623.53**
  - **Total Trades:** 555 trades (~92.5 trades/year, exactly matching the 90–110/yr target frequency)
  - **Win Rate:** 39.64%
  - **Monthly Consistency Ratio (MCR):** 44.44% (32 of 72 profitable months)
  - **RoMaD:** 2.07x

---

## 2. Quantitative Rationale & Theoretical Edge
1. **Entropy Filtration via Choppiness Index (CI):**
   - The Choppiness Index is a modern formulation of fractal dimension designed to quantify whether the market is trending or consolidating.
   - When $CI > 61.8$, Gold is trapped in chaotic Brownian noise and mean-reverting congestion where breakout signals suffer consecutive whipsaws.
   - When $CI < 45.0$, the market transitions into a low-entropy state with high directional persistence.
2. **Chande Momentum Confirmation:**
   - To prevent entering exhaustive trend climaxes, the Chande Momentum Oscillator ($CMO_{14}$) must confirm strong directional velocity ($CMO \ge +20.0$ for longs, $CMO \le -20.0$ for shorts).
3. **High-Frequency Trade Velocity:**
   - Strategy 46 generates 92.5 trades per year, fulfilling the target frequency expectation of ~100 trades/year.
4. **Autonomous Scaled Adaptive Risk (ASAR):**
   - Monthly profit lock at +$300.
   - Circuit breaker at -$250.
   - Defensive sizing (0.025 lot) activated when intra-month drawdown reaches -$120.

---

## 3. Mathematical Entry & Exit Specifications

### A. Technical Indicators
1. **True Range & Choppiness Index ($N=14$):**
   $$TR_t = \max(H_t - L_t, |H_t - C_{t-1}|, |L_t - C_{t-1}|)$$
   $$CI_{14} = 100 \times \frac{\log_{10}\left(\frac{\sum_{i=0}^{13} TR_{t-i}}{\max(H_{t..t-13}) - \min(L_{t..t-13})}\right)}{\log_{10}(14)}$$

2. **Chande Momentum Oscillator ($CMO_{14}$):**
   $$S_u = \sum (\Delta C > 0), \quad S_d = \sum (-\Delta C > 0)$$
   $$CMO_{14} = 100 \times \frac{S_u - S_d}{S_u + S_d}$$

3. **Breakout Channel & Macro EMA:**
   $$High20 = \max_{1 \le k \le 20}(C_{t-k}), \quad Low20 = \min_{1 \le k \le 20}(C_{t-k})$$
   $$Macro = EMA_{200}(C)$$

### B. Signal Confirmation Rules (Bar $i$ Close)
- **Long Signal:**
  1. $CI_{14} \le 45.0$ (Non-choppy trending regime).
  2. $CMO_{14} \ge +20.0$ (Strong upward momentum).
  3. $C_i \ge High20_i$ (20-bar channel breakout).
  4. $C_i > EMA_{200}$.
  5. No existing position open and monthly circuit breaker not tripped.
- **Short Signal:**
  1. $CI_{14} \le 45.0$.
  2. $CMO_{14} \le -20.0$.
  3. $C_i \le Low20_i$.
  4. $C_i < EMA_{200}$.
  5. No existing position open and monthly circuit breaker not tripped.

### C. Execution & Order Fill (Bar $i+1$ Open)
- Strict causal fill at Open of Bar $i+1$.
- CFD friction: $0.25 spread + $6.00/lot commission.

### D. Exit Mechanics
- **Stop Loss:** $2.0 \times ATR_{14}$
- **Take Profit:** $3.5 \times ATR_{14}$
- Asymmetric reward-to-risk: $1.75 : 1$.

---

## 4. Multi-Year Audit Summary (2020–2025)

| Year | Trades | Win Rate (%) | Net Profit ($) | Profit Factor | Max DD ($) |
| :---: | :---: | :---: | :---: | :---: | :---: |
| **2020** | 102 | 40.20% | +$890.40 | 1.21 | $480.20 |
| **2021** | 94 | 38.30% | +$310.15 | 1.08 | $560.10 |
| **2022** | 98 | 41.84% | +$940.60 | 1.24 | $420.50 |
| **2023** | 89 | 39.33% | +$412.30 | 1.10 | $495.30 |
| **2024** | 88 | 42.05% | +$880.50 | 1.25 | $410.80 |
| **2025** | 84 | 35.71% | -$73.65 | 0.98 | $520.40 |
| **Total**| **555** | **39.64%** | **+$3,360.30** | **1.173** | **$1,623.53** |

---

## 5. MQL5 Expert Advisor Blueprint
- EA File: [`Gold_H1_Choppiness_Momentum_Master_EA.mq5`](file:///root/CFD-Trading-ML/projects/quant_strategy_discovery/ea/Gold_H1_Choppiness_Momentum_Master_EA.mq5)
