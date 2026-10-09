# Rule-Based CFD Quantitative Research Report: Strategy 28 (Microstructure Cumulative Volume Delta - CVD Breakout with ASAR)

**Asset Class:** CFD Commodity (XAUUSD / Gold)  
**Timeframe:** M15 (Resampled from M1, 141,567 bars)  
**Historical Horizon:** 2020-01-01 to 2025-12-30 (72 Calendar Months)  
**Base Lot Size:** 0.10 lots  
**Execution Frictions:** $0.25 spread ($25.00/standard lot), $6.00/lot round-turn commission  
**Status:** ⚖️ **VIABLE VARIANT (PF 1.302, Net +$4,299, but Pure Price Action Remains Superior at PF 1.359)**  

---

## 1. Executive Summary & Comparative Breakdown

Strategy 28 tested whether filtering London/NY breakouts with **Cumulative Volume Delta (CVD > SMA(CVD, 8))** improves performance under the ASAR risk architecture.

### Comparative Sweep Results (72 Calendar Months)

| Metric | With CVD Filter (`use_cvd=True`) | Pure Price Action Baseline (`use_cvd=False`) | Impact of CVD Filter |
| :--- | :---: | :---: | :---: |
| **Profit Factor (PF)** | **1.302** | **1.359** | Pure price action is 4.4% more efficient |
| **Net Profit (0.10 Lot)**| **+$4,299.59** | **+$5,003.20** | CVD filters out $703 of net profit |
| **Max Drawdown ($)** | **$1,282.24** | **$1,136.67** | Baseline achieves lower drawdown |
| **Total Trades** | 769 | 743 | Comparable sample size |
| **Monthly Consistency (MCR)**| **58.33% (42 of 72 months)** | **62.50% (45 of 72 months)** | Baseline achieves higher monthly win rate |

---

## 2. Quantitative Microstructure Insight
- Tick-derived Volume Delta on Gold CFD is moderately noisy during rapid market-order cascades.
- Pure price action breakouts ($8$-bar High/Low confirmed with $200$ EMA) capture the exact structural break of liquidity without the latency introduced by tick volume distribution smoothing.
- **Architectural Directive:** Retain pure price action for the London/NY engine in the production Master EA ([`Gold_ASAR_DualRegime_Master_EA.mq5`](file:///root/CFD-Trading-ML/projects/quant_strategy_discovery/ea/Gold_ASAR_DualRegime_Master_EA.mq5)).
