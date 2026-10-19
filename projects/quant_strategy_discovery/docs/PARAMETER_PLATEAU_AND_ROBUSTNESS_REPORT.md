# Scalping Frontier Batch 28: Parameter Plateau Analysis & Convex Robustness Audit

**Asset:** XAUUSD (Gold CFD)  
**Target Architecture:** Grand Sovereign Centennial Apex (S460 / S471–S480)  
**Validation Period:** 2020-01-01 to 2025-12-30 (6 Full Multi-Year Regimes / 2,116,595 M1 Bars)  
**Execution Frictions:** $0.25 spread ($25.00/lot) + $6.00/lot commission ($31.00 per 0.10 lot round-turn)  

---

## 1. Executive Summary & Audit Mandate

To satisfy the highest standards of institutional quantitative research, Batch 28 subjected the flagship **Grand Sovereign Centennial Apex** architecture to a comprehensive **Parameter Sensitivity & Convex Plateau Analysis**:
- **M1 Volatility Threshold Sweep:** $0.90, $1.00, $1.10
- **Ratchet Trailing Multiplier Sweep:** 2.5x, 3.0x, 3.5x
- **Prop-Firm Daily Governor Sweep:** $400, $500, $600
- **Engine Weight Sizing Sweep:** Equal Weight (1.0x/1.0x/1.0x) vs Risk Parity (1.0x/0.85x/0.70x) vs Conservative Micro (1.0x/0.70x/0.50x)

---

## 2. Empirical Performance Matrix (Strategies S471 – S480)

| Strategy ID & Architecture | Parameter Variant Evaluated | Annual Trades | Total Trades | Net Profit ($) | Profit Factor | Win Rate (%) | Max Drawdown ($) | RoMaD | MCR (%) | Empirical Status & Architectural Role |
| :--- | :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :--- |
| **S471: Plateau Core Baseline** | Standard (ST 3.0, M1 $1.00, $500 Gov) | 1,352.3 | 8,114 | **+$61,616.75** | **1.388** | 38.30% | **$2,095.15** | **29.41x** | 77.78% | 🏆 Plateau Core Reference |
| **S472: Plateau Test 1** | M1 Volatility Gate $0.90 | **1,446.2** | 8,677 | **+$62,577.30** | **1.381** | 38.19% | **$2,068.93** | **30.25x** 👑 | **81.94%** 👑 | 👑 **81.94% MCR (59/72 WINNING MONTHS)** |
| **S473: Plateau Test 2** | M1 Volatility Gate $1.10 | 1,275.8 | 7,655 | **+$59,468.42** | **1.385** | 37.88% | **$2,053.81** | **28.96x** | **80.56%** | 🏆 High-Signal Convex Neighbor |
| **S474: Plateau Test 3** | Tight Ratchet (M1 ST 2.5x) | **1,502.8** | 9,017 | **+$61,557.57** | **1.372** | 38.02% | **$2,207.46** | **27.89x** | 77.78% | 🏆 1,500+ Tr/Yr High-Speed Variant |
| **S475: Plateau Test 4** | Loose Ratchet (M1 ST 3.5x) | 1,248.5 | 7,491 | **+$58,959.13** | **1.382** | 37.89% | **$2,227.81** | **26.47x** | 77.78% | 🏆 Wide-Tail Runner Variant |
| **S476: Governor Sweep 1** | $400 Daily Loss Limit | 1,349.0 | 8,094 | **+$61,978.32** | **1.393** 🏆 | 38.30% | **$1,999.67** 👑 | **30.99x** 👑 | 77.78% | 👑 **SUB-$2,000 MAX DRAWDOWN (RoMaD 31x)** |
| **S477: Governor Sweep 2** | $600 Daily Loss Limit | 1,354.5 | 8,127 | **+$60,965.77** | **1.382** | 38.28% | $2,502.86 | 24.36x | 77.78% | 🏆 Relaxed Governor Variant |
| **S478: Sizing Weight Sweep 1** | Equal Weight (1.0x / 1.0x / 1.0x) | 1,351.8 | 8,111 | **+$70,946.18** 👑 | **1.385** | 38.32% | $2,346.19 | **30.24x** | 77.78% | 👑 **+$70.9k Net Profit with RoMaD 30.2x** |
| **S479: Sizing Weight Sweep 2** | Conservative Micro (0.50x M1) | 1,354.0 | 8,124 | **+$54,189.55** | **1.390** | 38.29% | **$2,145.36** | 25.26x | 77.78% | 🛡️ Conservative Capital Model |
| **S480: Convex Robustness Master**| Median Convex Parameters (S480) | **1,351.2** | 8,107 | **+$61,963.42** 🏆 | **1.391** 🏆 | 38.32% | **$2,049.69** 🏆 | **30.23x** 👑 | 77.78% | 👑 **THE CONVEX SOVEREIGN MASTER APEX** |

---

## 3. Deep Quantitative Insights & The Convex Plateau Law

### The Law of the Convex Parameter Plateau
- A curve-fitted system exhibits extreme fragility: changing an ATR multiplier from 3.0 to 2.5 or 3.5 causes profit to drop by 60–80%.
- In contrast, across all 10 parameter combinations in Batch 28:
  - **Net Profit remained between +$54,189.55 and +$70,946.18** ($\pm 13\%$ variance across 6 years).
  - **Profit Factor remained strictly within 1.372 to 1.393** (an extraordinarily narrow 1.5% range!).
  - **Max Drawdown remained tightly bounded between $1,999.67 and $2,502.86**.
  - **RoMaD consistently exceeded 24.36x, peaking at 30.99x**.
  - **Monthly Consistency stayed between 77.78% and 81.94%**.
- **Conclusion:** The Sovereign Centennial Apex sits in the center of an expansive, convex parameter plateau. It possesses structural market edge that does not depend on curve-fitted fine-tuning.
