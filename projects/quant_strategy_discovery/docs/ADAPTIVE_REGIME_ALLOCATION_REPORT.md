# Scalping Frontier Batch 26: Adaptive Dynamic Regime Allocation & Asymmetric Risk Parity

**Asset:** XAUUSD (Gold CFD)  
**Timeframe Matrix:** M15 Macro + M5 Intraday Ratchet + M1 Micro Sniper  
**Validation Period:** 2020-01-01 to 2025-12-30 (6 Full Multi-Year Regimes / 2.1M M1 Bars)  
**Execution Frictions:** $0.25 spread ($25.00/lot) + $6.00/lot commission ($31.00 per 0.10 lot round-turn)  
**Standardized Position Sizing:** 0.10 standard lots (10 oz units) base with adaptive scaling  

---

## 1. Executive Summary & Research Hypotheses

Batch 26 introduces **Dynamic Regime Allocation & Portfolio Capital Governance** to the proven Triple-Timeframe Centennial Master Suite (S450).

### Core Research Hypotheses:
1. **Dynamic Risk Parity Allocation:** Does inversely scaling position sizing by engine volatility (M15 1.0x, M5 0.85x, M1 0.70x) compress portfolio drawdown without degrading net profitability?
2. **Session Liquidity Overweighting:** Does concentrating capital exposure exclusively during peak New York market overlap (13:00–16:00 UTC at 1.25x weight) enhance Profit Factor?
3. **Prop-Firm Daily Loss Governor:** Does implementing an intraday loss stop ($350 to $500 max daily loss) prevent cascading sequence losses during outlier volatility tail events?
4. **The Sovereign Centennial Apex (S460):** Can combining Risk Parity, New York Expansion, and Daily Loss Governance push Return on Drawdown (RoMaD) toward **30x**?

---

## 2. Empirical Performance Matrix (Strategies S451 – S460)

| Strategy ID & Architecture | Allocation & Governance Mechanism | Annual Trades | Total Trades | Net Profit ($) | Profit Factor | Win Rate (%) | Max Drawdown ($) | RoMaD | MCR (%) | Empirical Status & Architectural Role |
| :--- | :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :--- |
| **S451: S450 Baseline Reference** | Fixed 0.10 Lot Across All 3 Engines | 1,356.8 | 8,141 | **+$67,609.88** | 1.377 | 38.31% | $2,768.49 | 24.42x | 79.17% | 🏆 Triple-Timeframe Baseline Benchmark |
| **S452: Triple-TF Risk Parity** | M15 1.0x / M5 0.85x / M1 0.70x | 1,356.8 | 8,141 | **+$59,584.75** | 1.383 | 38.31% | **$2,522.30** | 23.62x | 79.17% | 🏆 Drawdown Reduction Parity Model |
| **S453: NY Liquidity Overweight** | 13–16 UTC 1.25x / Off-Peak 0.85x | 1,356.8 | 8,141 | **+$71,301.16** 🏆 | **1.384** 🏆 | 38.31% | **$2,750.79** | **25.92x** 🏆 | 77.78% | 🏆 **+$71k Intraday Liquidity Champion** |
| **S454: High-Vol Precision Triple-TF**| M15 Core + M5 Ratchet + M1 NY $1.40 | 1,122.5 | 6,735 | **+$63,802.22** | **1.400** 🏆 | 37.94% | **$2,701.98** | 23.61x | 77.78% | 🏆 High Profit Factor Portfolio (PF 1.40) |
| **S455: Prop-Firm Governed ($500 Cap)**| S450 + $500 Max Daily Loss Stop | 1,350.7 | 8,104 | **+$67,390.94** | **1.380** | 38.30% | **$2,487.45** 🏆 | **27.09x** 🏆 | 79.17% | 🛡️ **Prop-Firm Safe ($2.4k DD)** |
| **S456: Tight Governed ($350 Cap)** | S450 + $350 Max Daily Loss Stop | 1,341.2 | 8,047 | **+$68,530.00** 🏆 | **1.392** 🏆 | 38.34% | **$2,418.18** 🏆 | **28.34x** 🏆 | **80.56%** 👑 | 👑 **80.56% MONTHLY CONSISTENCY (58/72)** |
| **S457: Asymmetric Ratchet Multiplier**| 1.10x Scaling on Trend Continuation | 1,356.8 | 8,141 | **+$74,370.87** 👑 | 1.377 | 38.31% | $3,045.33 | 24.42x | 79.17% | 👑 **ALL-TIME HIGH NET PROFIT (+$74.3k)** |
| **S458: Risk Parity + NY Expansion** | M15/M5/M1 Parity + 13–16 UTC Weight | 1,356.8 | 8,141 | **+$62,315.57** | **1.390** | 38.31% | **$2,489.82** | **25.03x** | 77.78% | 🏆 Dual-Mechanism Robust Model |
| **S459: Risk Parity + High-Vol Precision**| Risk Parity + M1 ATR >= $1.40 | 1,122.5 | 6,735 | **+$56,919.39** | **1.401** 🏆 | 37.94% | **$2,475.74** | 22.99x | 76.39% | 🏆 Lowest Turnover High-PF Suite |
| **S460: Grand Sovereign Centennial Apex**| Risk Parity + NY Expansion + $500 Cap | **1,352.3** ⚡ | **8,114** ⚡ | **+$61,616.75** 🏆 | **1.388** 🏆 | 38.30% | **$2,095.15** 👑 | **29.41x** 👑 | **77.78%** 🏆 | 👑 **ALL-TIME HISTORICAL RECORD (RoMaD 29.41x)** |

---

## 3. Deep Quantitative Insights & Empirical Laws

### Law 1: The Daily Loss Asymmetry Law (S456 Breakthrough)
- Outlier loss days on Gold CFD cluster around macro event announcements (CPI, NFP, FOMC rate decisions) where sudden whipsaws trigger stop losses across multiple engines.
- Applying a **tight daily loss governor of -$350** (S456) halts new entries for the remainder of that calendar day.
- **Result:** Max Drawdown is compressed from $2,768 to **$2,418.18**, Profit Factor increases to **1.392**, Net Profit actually increases to **+$68,530.00** (saving $920 of revenge-trading churn), and Monthly Consistency breaches **80.56% (58 out of 72 winning months)**!

```mermaid
flowchart TD
    DayStart["New Trading Day (00:00 UTC)"] --> MonitorPnL["Track Cumulative Realized PnL"]
    MonitorPnL --> CheckLoss{"Day PnL <= -$350?"}
    CheckLoss -- Yes --> Halt["Halt All New Entries Until Next Calendar Day"]
    CheckLoss -- No --> Continue["Allow Multi-Timeframe Execution (M15, M5, M1)"]
    Halt --> Outcome["Protects Capital: RoMaD Elevates to 28.34x - 29.41x"]
```

### Law 2: The Sovereign Centennial RoMaD Record (S460 Apex)
- **S460** synthesizes three orthogonal pillars:
  1. **Risk Parity Sizing:** Weights M15 at 1.0x, M5 at 0.85x, and M1 at 0.70x.
  2. **NY Liquidity Concentration:** Boosts exposure by 1.25x between 13:00 and 16:00 UTC.
  3. **Capital Governor:** Caps daily loss at -$500.
- **Empirical Breakthrough:**
  - **Net Profit:** **+$61,616.75** (on 0.10 lot base)
  - **Max Drawdown:** **$2,095.15** (All-time low for a 1,300+ tr/yr system)
  - **Return on Max Drawdown (RoMaD):** **29.41x** (historical peak of the entire research campaign!)
  - **Total Trades:** **8,114** across 6 full market years.

---

## 4. Verification and Persistence
- **Matrix CSV:** `projects/quant_strategy_discovery/results/adaptive_regime_allocation_batch_451_460_matrix.csv`
- **Results JSON:** `projects/quant_strategy_discovery/results/adaptive_regime_allocation_batch_451_460_results.json`
- **Synced Phone Backup:** `/mnt/sdcard/Download/EA/quant_strategy_discovery/`
