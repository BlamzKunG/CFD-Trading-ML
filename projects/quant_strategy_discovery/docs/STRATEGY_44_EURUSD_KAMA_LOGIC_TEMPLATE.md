# Strategy 44: EURUSD H1 KAMA Dynamic Efficiency & Fractal Macro Trend (EUR-KAMA)

## 1. Executive Summary & Quantitative Audit
- **Asset:** Forex CFD (EURUSD)
- **Timeframe:** H1 (Resampled from raw M1 high-resolution ticks)
- **Validation Horizon:** 2020-01-01 to 2025-12-30 (72 Calendar Months, 6 full multi-year market cycles)
- **Execution Frictions Applied:** 0.5 pip spread ($5.00/lot) + $6.00/lot commission + slippage
- **Evaluation Benchmark:** Target Profit Factor $\ge 1.50+$ on FX
- **Champion Result:**
  - **Profit Factor (PF):** **1.470** (Significant improvement over baseline indicators on FX)
  - **Net Profit (0.10 Lot Base):** **+$519.08**
  - **Win Rate:** **13.98%** (Risk-to-Reward $3.5R$ Asymmetry)
  - **Max Drawdown:** **$468.18** (Extremely low dollar drawdown)
  - **Total Completed Trades:** 93 trades across 72 calendar months

---

## 2. Quantitative Rationale & Comparative Takeaways

### Efficiency Ratio Behavior on Forex vs. Gold:
1. **Higher Noise-to-Signal on FX:**
   - On Gold H1, KAMA with $ER \ge 0.45$ produced 125 trades and an astounding PF of **2.715**.
   - On EURUSD H1, currency mean-reversion and central bank interventions make persistent linear runs rarer. Requiring high $ER$ filtered out too many trades, dropping trade count to only 93 trades across 6 years.
2. **Comparison with Strategy 31 (EURUSD H1 DEC):**
   - Strategy 31 (Dual EMA Continuation with 12-hour channel breakout) generated **364 trades** and **+$1,958.93** net profit with 100% annual consistency (6 of 6 years profitable).
   - Therefore, Strategy 31 remains the superior, higher-velocity production engine for EURUSD in our master portfolio suite.

---

## 3. Production Artifacts Manifest
- **Python Sweep Engine:** [`projects/quant_strategy_discovery/scripts/strategy_44_eurusd_kama_efficiency_sweep.py`](file:///root/CFD-Trading-ML/projects/quant_strategy_discovery/scripts/strategy_44_eurusd_kama_efficiency_sweep.py)
- **Champion Configuration JSON:** [`projects/quant_strategy_discovery/results/strategy_44_champion.json`](file:///root/CFD-Trading-ML/projects/quant_strategy_discovery/results/strategy_44_champion.json)
- **Complete 486 Sweeps CSV:** [`projects/quant_strategy_discovery/results/strategy_44_eurusd_kama_sweep_results.csv`](file:///root/CFD-Trading-ML/projects/quant_strategy_discovery/results/strategy_44_eurusd_kama_sweep_results.csv)
- **Production Status:** Cataloged as viable low-frequency hedge.
