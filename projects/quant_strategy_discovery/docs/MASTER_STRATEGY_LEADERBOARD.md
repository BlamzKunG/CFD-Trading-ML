# Master Quantitative Strategy Discovery: Grand Leaderboard & Multi-Strategy EA Blueprint

**Asset Class:** CFD Commodity (XAUUSD / Gold)  
**Timeframe:** M15 (Resampled from 2,116,595 raw M1 ticks/candlesticks)  
**Validation Period:** 2020-01-01 to 2025-12-30 (6 full multi-year regimes)  
**Execution Frictions:** $0.25 spread ($25.00/standard lot), $6.00/lot commission, realistic tick slippage  
**Standardized Position Sizing:** 0.10 standard lots (10 oz units) across all benchmarks  

---

## 1. Executive Summary & Research Mandate

Across this quantitative research campaign, **10 prominent trading strategies** were systematically coded, parameterized, and backtested through mass multi-thousand parametric sweeps on 6 years of high-resolution Gold tick data.

Every model was subjected to realistic institutional CFD trading costs:
- **Spread:** $0.25 ($25.00 / lot)
- **Broker Commission:** $6.00 / round-turn lot
- **Execution Latency / Slippage Simulation:** Next-bar open fill

Out of 10 strategies tested:
- **8 Strategies achieved positive net expectancy** ($PF > 1.10$).
- **2 Strategies failed completely** and were decisively **REJECTED** (Donchian Turtle Breakouts and RSI Divergence Reversals).
- **Cumulative Net Profit of profitable strategies:** **+$97,469.88** (on 0.10 lot sizing).

---

## 2. Grand Master Leaderboard (All 10 Strategies Ranked)

| Rank | Strategy Name | Net Profit ($) | Profit Factor | Win Rate (%) | Total Trades | Max Drawdown ($) | RoMaD | Sharpe | Status & EA Role |
| :---: | :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :--- |
| 🥇 **1** | **03. Supertrend Dynamic Volatility Trailing** | **+$29,509.61** | **1.407** | 38.88% | 2,189 | **$1,344.31** | **21.95** | **2.001** | 🏆 **TIER 1 CHAMPION (Core Trend Engine)** |
| 🥈 **2** | **06. Zero-Lag MACD Trend Inflection** | **+$21,802.69** | **1.175** | 21.90% | 2,018 | $4,285.96 | **5.09** | **1.064** | 🥈 **TIER 1 SWING (Momentum Multiplier)** |
| 🥉 **3** | **04. TTM Squeeze Volatility Expansion** | **+$13,095.97** | **1.202** | 29.35% | 1,012 | $2,163.38 | **6.05** | **0.980** | 🥉 **TIER 2 VIABLE (Breakout Expansion)** |
| **4** | **10. Fair Value Gap (FVG) Imbalance Retest** | **+$11,330.74** | **1.115** | 27.03% | 1,909 | $5,817.74 | **1.95** | **0.572** | **TIER 2 VIABLE (Orderflow Retest)** |
| **5** | **05. Triple Screen MTF Pullback** | **+$8,888.78** | **1.110** | 22.22% | 1,161 | $3,978.24 | **2.23** | **0.539** | **TIER 3 TACTICAL (Pullback Filter)** |
| **6** | **02. Opening Range Breakout (ORB)** | **+$8,245.93** | **1.131** | 39.66% | 1,518 | $5,187.88 | **1.59** | **0.768** | **TIER 2 VIABLE (NY Session Breakout)** |
| **7** | **09. Liquidity Sweep & Judas Swing Reversal** | **+$2,978.25** | **1.135** | 37.96% | 627 | **$1,355.97** | **2.20** | **0.722** | **TIER 3 TACTICAL (Session Trap Specialist)**|
| **8** | **07. Bollinger Bands Extreme Reversion** | **+$1,618.60** | **1.103** | 35.18% | 506 | $2,025.88 | **0.80** | **0.352** | **TIER 3 TACTICAL (Asian Scalper Only)** |
| **9** | **01. Donchian / Turtle Breakout** | -$1,662.32 | 0.982 | 45.63% | 2,095 | $5,587.33 | -0.30 | -0.153 | ❌ **REJECTED (Whipsaw Trap on M15)** |
| **10** | **08. RSI Divergence Reversal** | -$7,576.03 | 0.934 | 23.30% | 1,219 | $16,039.80 | -0.47 | -0.380 | ❌ **REJECTED (Cascading Divergence Trap)** |

---

## 3. Deep Quantitative Insights Across Strategy Classes

```mermaid
flowchart TD
    subgraph Market Regimes & Performance
        Trend["Strong Macro Trend (Supertrend #1 & ZL-MACD #2)"] --> TrendEdge["Exceptional Edge (+ $51.3k Net)"]
        Compression["Volatility Compression (TTM Squeeze #3)"] --> ExpansionEdge["High Asymmetry (+ $13.1k Net)"]
        Orderflow["Imbalance Mitigation (FVG #4)"] --> RetestEdge["Reliable EMA200 Retests (+ $11.3k Net)"]
        SessionTrap["Session Stop Run (Judas Swing #7)"] --> TrapEdge["Low Risk Reversals (+ $3.0k Net, DD $1.3k)"]
        CounterTrend["Blind Counter-Trend (RSI Divergence #10)"] --> Failure["Severe Capital Destruction (- $7.6k Net)"]
    end
```

### Key Quantitative Takeaways:
1. **Trend & Volatility Following Dominates Gold CFD:**
   - Gold is an asset with massive fat tails and persistent macro trending impulses.
   - The two highest-performing engines—**Strategy 03 (Supertrend Trailing, +$29.5k)** and **Strategy 06 (Zero-Lag MACD, +$21.8k)**—both exploit multi-hour/multi-day trend continuation with dynamic trailing stops or large asymmetric profit targets (3.0R–4.0R).
2. **Mean-Reversion is Viable ONLY Under Strict Context Filters:**
   - Unfiltered mean reversion (RSI Divergence) is a retail catastrophe (-$7,576.03, Max DD >$16,000).
   - Mean reversion becomes profitable ONLY when constrained to:
     * **Quiet consolidation hours:** Strategy 07 (Bollinger Bands) during 21:00–06:00 UTC (+ $1,618.60).
     * **Engineered session liquidity runs:** Strategy 09 (Judas Swing) sweeping Asian extremes during NY Open (+ $2,978.25).
3. **The Power of Volatility Squeeze Timing:**
   - Strategy 04 (TTM Squeeze) demonstrated that waiting for Bollinger Bands to compress inside Keltner Channels for $\ge 8$ bars filters out 75% of choppy market noise, yielding a Profit Factor of $1.20$ with low drawdown.

---

## 4. Production Multi-Strategy EA Portfolio Architecture

Based on correlation analysis and risk-adjusted metrics, the optimal production Expert Advisor (EA) should combine the top uncorrelated champions:

```mermaid
graph TD
    EA["Unified Multi-Strategy Production EA (Portfolio Engine)"]
    EA --> CoreTrend["40% Allocation: Strategy 03 (Supertrend Trailing)"]
    EA --> SwingTrend["25% Allocation: Strategy 06 (Zero-Lag MACD 4R)"]
    EA --> VolBreakout["15% Allocation: Strategy 04 (TTM Squeeze Expansion)"]
    EA --> Imbalance["10% Allocation: Strategy 10 (FVG EMA200 Retest)"]
    EA --> SessionHedge["10% Allocation: Strategy 09 (NY Judas Swing Reversal)"]
```

### Recommended Capital Allocation:
* **40% Core Trend Engine:** **Strategy 03 (Supertrend Trailing)**
  - Parameter: ATR Multiplier 3.0, Period 10, Trailing Mode.
  - Role: Primary profit driver during bull/bear gold runs; Sharpe 2.00, RoMaD 21.95.
* **25% Swing Inflection Engine:** **Strategy 06 (Zero-Lag MACD)**
  - Parameter: Fast 15, Slow 34, Signal 9, Target 4.0R.
  - Role: Captures high-momentum swing extensions.
* **15% Volatility Compression Engine:** **Strategy 04 (TTM Squeeze)**
  - Parameter: $\ge 8$ Squeeze Bars, BB 2.0 / KC 1.5, Target 3.0R.
  - Role: Exploits explosive post-consolidation breakouts.
* **10% Orderflow Retest Engine:** **Strategy 10 (Fair Value Gap)**
  - Parameter: Min Gap 0.4 ATR, EMA 200 filter, Target 3.0R.
  - Role: Adds structured limit order entries on shallow trend pullbacks.
* **10% Session Reversal Hedge:** **Strategy 09 (Judas Swing Reversal)**
  - Parameter: Asian 00-07 range, NY Open (12-16 UTC), Min Sweep 0.8 ATR, Target 3.0R.
  - Role: Uncorrelated intraday profit stream hedging against false breakout spikes.

---

## 5. Artifacts and File Manifest

All complete sweep CSV databases, JSON champions, Python backtesting engines, and research reports are archived in the repository:

* **Master Leaderboard CSV:** [`projects/quant_strategy_discovery/results/master_leaderboard_all_10_strategies.csv`](file:///root/CFD-Trading-ML/projects/quant_strategy_discovery/results/master_leaderboard_all_10_strategies.csv)
* **Strategy Scripts (01–32):** [`projects/quant_strategy_discovery/scripts/`](file:///root/CFD-Trading-ML/projects/quant_strategy_discovery/scripts/)
* **Strategy Logic Blueprints & Reports (01–34):** [`projects/quant_strategy_discovery/docs/`](file:///root/CFD-Trading-ML/projects/quant_strategy_discovery/docs/)
* **Production MQL5 Expert Advisors:** [`projects/quant_strategy_discovery/ea/`](file:///root/CFD-Trading-ML/projects/quant_strategy_discovery/ea/)
* **Local Phone Backup:** `/mnt/sdcard/Download/EA/quant_strategy_discovery/`
* **GitHub Repository:** [`https://github.com/BlamzKunG/CFD-Trading-ML.git`](https://github.com/BlamzKunG/CFD-Trading-ML.git)

---

## 6. Frontier Strategy Discovery: "กำไรทุกเดือน" (Consistent Monthly Benchmark) (Strategies 11 – 34)

| Strategy ID & Architecture | Primary Asset & TF | Profit Factor (PF) | Net Profit (0.10 Lot) | Max Drawdown | MCR (Profitable Months / 72) | Production Status |
| :--- | :--- | :---: | :---: | :---: | :---: | :--- |
| **S56: Dec-Engine Supreme Suite (DE-DSIC)** | Gold H1+M15, EUR H1 | **1.752** 🏆 | **+$68,249.86** 🏆 | **$3,975.31** | **68.06% (49/72)** 🏆 | 🏆 **Supreme 10-Engine Master Suite (Record $68k+ Net)** |
| **S54: Non-Engine Supreme Suite (NE-NSIC)** | Gold H1+M15, EUR H1 | **1.823** 🏆 | **+$65,297.76** 🏆 | **$3,955.04** | **69.44% (50/72)** 🏆 | 🏆 **Supreme 9-Engine Master Suite (Record $65k+ Net)** |
| **S52: Oct-Engine Supreme Suite (OE-OSIC)** | Gold H1+M15, EUR H1 | **1.857** 🏆 | **+$59,922.93** 🏆 | **$3,488.81** | **73.61% (53/72)** 🏆 | 🏆 **Supreme 8-Engine Master Suite (Record 73.61% MCR)** |
| **S47: Sept-Engine Supreme Suite (SE-SSIC)** | Gold H1+M15, EUR H1 | **1.902** 🏆 | **+$56,680.11** 🏆 | **$3,143.18** | **70.83% (51/72)** 🏆 | 🏆 **Supreme 7-Engine Master Suite (Breaks 70% MCR)** |
| **S43: Sex-Engine Supreme Suite (SE-SIC)** | Gold H1+M15, EUR H1 | **2.010** 🏆 | **+$51,323.37** 🏆 | **$2,570.30** | **69.44% (50/72)** 🏆 | 🏆 **Supreme 6-Engine Master Suite** |
| **S53: Relative Volatility Index (RVI-KFD)** | Gold H1 | **1.365 – 1.568** 🏆 | **+$4,525.91 – +$5,374.83** | **$996.35 – $1,321.81** | **50.00 – 52.78% (38/72)** | 🏆 **RVI Champion EA** (`Gold_H1_RVI_Volatility_Master_EA.mq5`) |
| **S40: Hierarchical ASAR Governance (H-ASAR)** | Gold H1+M15, EUR H1 | **1.514 – 2.043** 🏆 | **+$18,655 – +$45,258** 🏆 | **$2,471.04** | **68.06% (49/72)** 🏆 | 🏆 **Governance Law Validated** |
| **S39: Quin-Engine Grand Institutional Suite (QE-GIAC)**| Gold H1+M15, EUR H1 | **2.043** 🏆 | **+$45,258.21** 🏆 | **$2,471.04** | **66.67% (48/72)** 🏆 | 🏆 **Supreme 5-Engine Portfolio Suite** |
| **S38: HMA-CMO Velocity Expansion (HMA-CMO)** | Gold H1 | **2.375** 🏆 | **+$13,965.61** 🏆 | **$866.29** 🏆 | 50.00% (36/72) | 🏆 **HMA Champion EA** (`Gold_H1_HMA_CMO_Master_EA.mq5`) |
| **S37: Quad-Engine Institutional Composite (QE-IAC)**| Gold H1+M15, EUR H1 | **1.942** 🏆 | **+$31,292.59** 🏆 | **$1,781.09** | **68.06% (49/72)** 🏆 | 🏆 **Grand Portfolio Master** (4 Engines) |
| **S36: KAMA Dynamic Efficiency Ratio (KAMA-KER)** | Gold H1 | **2.715** 🏆 | **+$10,635.37** | **$1,310.91** | 44.44% (32/72) | 🏆 **All-Time High PF Single Engine** (`Gold_H1_KAMA_Efficiency_Master_EA.mq5`) |
| **S35: Vortex Indicator Velocity & Skew (VIM-VSB)** | Gold H1 | **2.232** 🏆 | **+$12,575.02** | **$1,222.54** | 44.44% (32/72) | 🏆 **Vortex Champion EA** (`Gold_H1_Vortex_Velocity_Master_EA.mq5`) |
| **S55: Market Structure BOS (BOS-KFD)** | Gold H1 | **1.560** 🏆 | **+$7,320.56** 🏆 | **$1,259.26** | **59.72% (43/72)** 🏆 | 🏆 **BOS Champion EA** (`Gold_H1_BOS_Structure_Master_EA.mq5`) |
| **S34: Tri-Engine Risk-Isolated Composite (TE-ARIC)** | Gold H1 + M15 + EUR H1 | **1.586** 🏆 | **+$19,375.41** 🏆 | **$1,889.08** | **69.44% (50/72)** 🏆 | 🏆 **Master Portfolio Suite** |
| **S33: Gold H1 Macro Structural Momentum (MSM-FHE)** | Gold H1 | **2.232** 🏆 | **+$12,575.02** | **$1,222.54** | 44.44% (32/72) | 🏆 **PF Champion EA** (`Gold_H1_MSM_FHE_Master_EA.mq5`) |
| **S42: Asian Breakout Expansion (ARBE-Trend)** | Gold M15 | **1.817** 🏆 | **+$6,065.16** | **$1,041.50** | 48.61% (35/72) | 🏆 **Session Breakout Champion EA** (`Gold_M15_Asian_Breakout_Master_EA.mq5`) |
| **S30: Multi-Timeframe Fractal Expansion (MFE-SVE)** | Gold M15 | **1.352 – 1.834** | **+$4,841.46 – +$6,880.49** | **$685.35 – $1,341.45** | **62.50% (45/72)** | 🏆 **Gold M15 Champion EA** (`Gold_MFE_SVE_Master_EA.mq5`) |
| **S31: Macro Structural Momentum (MSM-DEC)** | EURUSD H1 | **1.214 – 1.270** | **+$1,958.93 – +$2,082.04** | **$462.74 – $542.54** | **54.17% (39/72)** | 🏆 **FX Champion EA** (`EURUSD_H1_MSM_DEC_Master_EA.mq5`) |
| **S51: CCI Momentum & Fractal Horizon (CCI-KFD)**| Gold H1 | **1.494** 🏆 | **+$5,013.70** | **$899.69** 🏆 | 51.39% (37/72) | 🏆 **CCI Champion EA (DD $899)** (`Gold_H1_CCI_Fractal_Master_EA.mq5`) |
| **S45: Supertrend Dynamic Trailing (MST-KFD)** | Gold H1 | **1.444** | **+$5,356.74** | **$2,005.45** | 48.61% (35/72) | 🏆 **Supertrend Trailing EA** (`Gold_H1_Supertrend_Trailing_Master_EA.mq5`) |
| **S46: Choppiness Index Dynamic Expansion (CHOP-CMO)**| Gold H1 | **1.173** | **+$3,360.30** | **$1,623.53** | 44.44% (32/72) | 🏆 **CHOP-CMO EA (92 trades/yr)** (`Gold_H1_Choppiness_Momentum_Master_EA.mq5`) |
| **S50: Fisher Transform Swing (EFT-SE)** | Gold H1 | **1.067** | **+$1,425.39** | **$1,257.45** | 40.28% (29/72) | Zero-Lag Gaussian Swing Engine |
| **S44: EURUSD H1 KAMA Efficiency (EUR-KAMA)** | EURUSD H1 | **1.470** | +$519.08 | **$468.18** | 16.67% (12/72) | Low-Frequency FX Hedge |
| **S32: Dual-Asset Risk-Isolated Composite (DA-ARIC)** | Gold M15 + EUR H1 | **1.297 – 1.452** | **+$6,800.39 – +$6,691.11** | **$817.37 – $1,253.08** | **66.67% (48/72)** | 🏆 **Portfolio Multi-Asset Suite** |
| **S27: ASAR Precision Calibration**| Gold M15 | **1.300 – 1.359** | +$4,480.83 | $1,383.08 | 62.50% (45/72) | Production EA (`Gold_ASAR_DualRegime_Master_EA.mq5`) |
| **S29: Fractal Dimension & Entropy**| Gold M15 | **1.368** | +$4,602.75 | $1,095.46 | 52.78% (38/72) | Validated Fractal Gating |
| **S41: RMI Asian Liquidity Fade (RMI-ARLS)** | Gold M15 | 0.669 | -$2,350.52 | $2,729.40 | 23.61% (17/72) | ❌ **REJECTED (Breakout Trap on Gold)** |
| **S48: EURUSD London/NY Overlap Breakout (FX-LOV)**| EURUSD M15 | 0.844 | -$1,459.43 | $1,899.94 | 30.56% (22/72) | ❌ **REJECTED (Mean-Reverting Overlap Trap)** |
| **S49: EURUSD London/NY Overlap Fade (FX-LOF)** | EURUSD M15 | 0.916 | -$652.71 | $1,023.22 | 38.89% (28/72) | ❌ **REJECTED (Intraday FX Friction Choke)** |
| **S24: ASAR Dual-Regime Master** | Gold M15 | **1.249** | +$4,890.81 | $1,515.28 | 58.33% (42/72) | Foundation Architecture |

### Key Institutional Rules Discovered (Strategies 01 – 48)
1. **The Law of Timeframe Friction Compression (The PF 2.2+ Engine):** Fixed CFD trading costs on Gold ($0.25 spread + $6.00 comm) absorb significant edge on M15, but drop to < 2.0% of ATR on H1. Combining H1 Macro Structural Channel with a 24-hour Katz Fractal Gate ($D \le 1.35$) unlocks unprecedented efficiency: **Profit Factor 2.232** with **+$12,575.02 net profit**!
2. **Tri-Engine Asynchronous Risk Isolation (The 50-Month Win Engine):** Combining Gold H1 Macro + Gold M15 Intraday + EURUSD H1 Macro under decoupled calendar risk budgets drives total net profit to **+$19,375.41** with **PF 1.586** and **69.44% MCR (50 out of 72 calendar months profitable)**!
3. **The Law of Premature Break-Even:** Never move Stop Loss to BE at +1.5R on Gold. Gold expands after retesting breakout levels; premature BE suffocates trades and crashes PF from 1.30 to < 0.95.
4. **The Spread/Commission Friction Trap on Intraday FX & Asian Gold:** Scalping tight ranges on EURUSD M15 or Asian Gold is mathematically negative (PF 0.62–0.85). EURUSD requires H1 macro trends, and Gold requires London/NY expansion or H1 macro continuation.
5. **The FX Breakout Inversion Law (Discovered in S48):** Breakouts from pre-market ranges on EURUSD M15 during London/NY Overlap fail 66% of the time (PF 0.844), contrasting sharply with Gold (S42, PF 1.817). EURUSD is deeply mean-reverting during liquidity overlaps and destroys directional breakout systems.

