# Rule-Based CFD Quantitative Research Report: Strategy 21 (Multi-Asset Cross-Regime Ensemble with Shared Risk Budgeting)

**Asset Classes:** CFD Commodity (XAUUSD / Gold) + Major FX (EURUSD)  
**Timeframe:** M15 (Resampled from M1)  
**Historical Horizon:** 2020-01-01 to 2025-12-30 (72 Calendar Months)  
**Standardized Lot Size:** 0.10 lots  
**Execution Frictions:** Gold ($0.25 spread + $6 commission), EURUSD (0.8 pip spread + $6 commission)  
**Status:** ❌ **REJECTED (Circuit Breaker Cross-Contamination Phenomenon, PF 0.893)**  

---

## 1. Executive Summary & Core Concept

Strategy 21 investigated combining **Gold Trend Breakouts (London/NY)** with **EURUSD Asian Mean Reversion** under a unified portfolio risk budgeting architecture (Shared Monthly Profit Lock $+\$250$ to $+\$500$, Shared Weekly Breaker $-\$100$ to $-\$150$, and Summer Seasonality De-risking).

---

## 2. 72-Month Empirical Results & Parameter Sweep

Across 81 multi-asset combinations tested simultaneously across 72 calendar months:

| Metric | Top Multi-Asset Candidate | Gold-Only Baseline (Strategy 17) |
| :--- | :---: | :---: |
| **Net Profit (0.10 Lot)** | **-$3,595.56** | **+$4,492.46** |
| **Profit Factor (PF)** | **0.893** | **1.120** |
| **Win Rate (%)** | 39.78% | 38.50% |
| **Max Drawdown ($)** | $7,006.71 | **$3,516.71** |
| **Total Trades** | 1,302 | 1,140 |
| **Monthly Consistency (MCR)** | **41.67% (30 of 72 months)** | **66.67% (48 of 72 months)** |

---

## 3. Quantitative Autopsy: Why Shared Multi-Asset Circuit Breakers Fail

1. **The Circuit Breaker Cross-Contamination Effect:**
   - When EURUSD experienced normal minor mean-reversion pullbacks during the Asian session (e.g. -$60 to -$100), it hit the shared weekly circuit breaker ($-\$120$).
   - This prematurely halted the ENTIRE portfolio right before the London/NY session started.
   - As a consequence, Gold was locked out and prevented from entering high-expectancy trend breakout moves during London and New York.
   - The lower-expectancy asset systematically cannibalized the opportunities of the higher-expectancy asset.
2. **Volatility Dimension Mismatch:**
   - Gold volatility is denominated in full dollar moves ($1.00 = 100 pips), whereas EURUSD moves in decimal fractions of a pip. A shared cash circuit breaker without dynamic volatility parity scaling acts asymmetrically against the portfolio.

---

## 4. Key Takeaways & Institutional Mandate
- **Rule of Asset Risk Isolation:** Risk budgets, profit locks, and circuit breakers must be evaluated on an **ASSET-ISOLATED** basis, never pooled across heterogeneous asset classes.
- This finding establishes the direct pivot back to **Strategy 22: Adaptive Range Compression (ARC) Breakout with Asset-Isolated Hierarchical Risk Budgeting**.
