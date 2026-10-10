# Strategy 40: Hierarchical ASAR Governance & Consistency Law (H-ASAR)

## 1. Executive Summary & Quantitative Thesis
- **Research Question:** Can applying a centralized Portfolio Master Profit Lock ($+$400 to $+$1,500) on top of the 5-Engine Master Suite (Strategy 39) improve the Monthly Consistency Ratio (MCR) to $\ge 80\%$ without degrading Profit Factor?
- **Tested Assets & Portfolio:** 5-Engine Suite (Gold H1 KAMA, Gold H1 HMA-CMO, Gold H1 Vortex, Gold M15 SVE, EURUSD H1 DEC).
- **Validation Horizon:** 2020-01-01 to 2025-12-30 (72 Calendar Months, 6 full multi-year market cycles)
- **Frictions Applied:** $0.25 spread on Gold, 0.5 pip spread on EURUSD, $6.00/lot commission + slippage.

---

## 2. Comparative Findings Across Governance Regimes

| Governance Mode | Portfolio Profit Lock | Portfolio Breaker | Net Profit ($) | Profit Factor (PF) | Max DD ($) | RoMaD | MCR (Profitable Months / 72) |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **Autonomous Decoupled (S39 Baseline)** | **None ($0)** | **None ($0)** | **+$45,258.21** 🏆 | **2.043** 🏆 | **$2,471.04** | **18.32x** 🏆 | **66.67% (48/72)** |
| **Gentle Master Cap** | **+$1,500** | $0 | **+$40,605.00** | **1.955** | $2,471.04 | 16.43x | 66.67% (48/72) |
| **Moderate Master Cap** | **+$1,000** | $0 | **+$33,345.74** | **1.804** | $2,471.04 | 13.49x | 66.67% (48/72) |
| **Tight Master Cap** | **+$400** | $0 | +$18,655.15 | 1.514 | $2,471.04 | 7.55x | **68.06% (49/72)** |

---

## 3. The Core Quantitative Law Discovered

### The Law of Asynchronous Individual Isolation over Centralized Ceiling:
1. **The Fallacy of the Portfolio Profit Cap:**
   - Capping portfolio monthly gains at a low ceiling (e.g. +$400) yielded only **1 additional green month** (49 vs 48 months), but destroyed **58.8% of total net profits** (falling from +$45.2k down to +$18.6k) and collapsed the Profit Factor from **2.043 down to 1.514**.
2. **Fat-Tailed Trend Reality:**
   - Gold and currency macro expansions on H1 follow power-law distributions. Mega-expansion months (like early 2022 and 2024–2025) generate exponential returns that vastly compensate for normal consolidation friction.
   - Imposing a global ceiling suffocates positive skewness.
3. **The True Path to $\ge 80\%$ MCR:**
   - Monthly consistency CANNOT be achieved by choking trending winners.
   - It MUST be achieved by adding **non-correlated counter-cyclical engines** (e.g., Asian Range Scalpers / Liquidity Sweeps) that harvest gains during summer consolidation and range-bound regimes when H1 trend engines remain quiet.

---

## 4. Production Artifacts Manifest
- **Python Audit Engine:** [`projects/quant_strategy_discovery/scripts/strategy_40_hierarchical_asar_sweep.py`](file:///root/CFD-Trading-ML/projects/quant_strategy_discovery/scripts/strategy_40_hierarchical_asar_sweep.py)
- **Champion Configuration JSON:** [`projects/quant_strategy_discovery/results/strategy_40_champion.json`](file:///root/CFD-Trading-ML/projects/quant_strategy_discovery/results/strategy_40_champion.json)
- **Complete 210 Governance Sweeps CSV:** [`projects/quant_strategy_discovery/results/strategy_40_hierarchical_asar_results.csv`](file:///root/CFD-Trading-ML/projects/quant_strategy_discovery/results/strategy_40_hierarchical_asar_results.csv)
