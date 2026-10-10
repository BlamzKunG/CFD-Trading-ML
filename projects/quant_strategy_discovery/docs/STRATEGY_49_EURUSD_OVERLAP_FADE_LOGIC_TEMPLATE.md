# Strategy 49: EURUSD London/NY Overlap Liquidity Sweep & Fade (FX-LOF) — REJECTION AUDIT

## 1. Executive Summary & Strategy Verdict
- **Strategy ID:** STRATEGY_49
- **Identifier:** FX-LOF (London/NY Overlap Liquidity Sweep Fade)
- **Asset Class:** EURUSD CFD (Forex)
- **Execution Timeframe:** M15 (Resampled from raw M1 data)
- **Audit Period:** 2020-01-01 to 2025-12-30 (72 Calendar Months)
- **Status:** ❌ **DECISIVELY REJECTED**
- **Performance:**
  - **Profit Factor (PF):** **0.916** ❌ *(Target: $\ge 1.50$)*
  - **Net Profit:** **-$652.71** (0.10 Lot sizing)
  - **Max Drawdown:** **$1,023.22**
  - **Total Trades:** 1,038 trades
  - **Win Rate:** 39.40%
  - **Monthly Consistency Ratio (MCR):** 38.89% (28 of 72 profitable months)
  - **RoMaD:** -0.64x

---

## 2. Quantitative Rationale & Cross-Comparison with Strategy 48
1. **The Fade Hypothesis vs. The Breakout Hypothesis:**
   - In Strategy 48, EURUSD London/NY Overlap breakout generated **PF 0.844** and **-$1,459.43**.
   - Fading the sweep (Strategy 49) improved Net Profit by +$806.72 and boosted PF to **0.916**.
   - However, even with the structural improvement of fading false breakouts, expectancy remained stubbornly negative.
2. **The Intraday FX Friction Choke Law:**
   - On EURUSD M15, average bar ATR is only 10–14 pips.
   - Standard broker spread (0.6 pip) + commission (0.6 pip) totals 1.2 pips per trade.
   - Over 1,038 trades, frictional drag equals:
     $$1,038 \text{ trades} \times 1.2 \text{ pips} \times \$1.00/\text{pip} = \$1,245.60 \text{ in pure broker fees!}$$
   - Without the $1,245 friction drag, the gross strategy is slightly positive (~+$590), but real-world CFD execution drags the net bottom line into a -$652 loss.
3. **Strategic Conclusion (Constitution V5.0 Section 7):**
   - M15 intraday trading on EURUSD (whether breakout or fade) is mathematically unviable for retail/prop EA execution under standard broker commissions.
   - Forex quantitative alpha must strictly operate on **H1 macro timeframes** (such as Strategy 31 Dual EMA Continuation, where ATR is 40–60 pips and friction drops to < 2.5% of trade excursion).

---

## 3. Parametric Sweep Summary Across 216 Configurations

| Sweep Buffer ATR | RSI Filter | Take Profit | Stop Loss | Profit Lock | Total Trades | Win Rate (%) | Net Profit ($) | Profit Factor | Max DD ($) |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| 0.2 | False | 2.5R | 1.5R | $150 | 1,038 | 39.40% | -$652.71 | 0.916 | $1,023.22 |
| 0.2 | False | 2.5R | 1.5R | $200 | 1,039 | 39.36% | -$666.65 | 0.914 | $1,023.22 |
| 0.2 | False | 2.5R | 1.5R | $100 | 1,015 | 39.41% | -$676.51 | 0.910 | $1,018.86 |
| 0.1 | False | 2.5R | 1.5R | $150 | 1,103 | 39.44% | -$763.88 | 0.908 | $1,041.00 |
| 0.1 | False | 2.5R | 1.5R | $200 | 1,104 | 39.40% | -$777.82 | 0.907 | $1,041.00 |
| 0.3 | True | 2.0R | 1.2R | $150 | 542 | 37.08% | -$790.40 | 0.884 | $1,110.50 |

*Archived permanently in the Negative Knowledge Catalog to prevent repeating intraday FX session fade experiments.*
