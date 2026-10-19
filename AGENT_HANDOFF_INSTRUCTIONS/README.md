# 🚀 AGENT ONBOARDING & RESEARCH HANDOFF BRIEF (V5.1)

> [!IMPORTANT]
> **INSTRUCTION FOR INCOMING AGENT:**
> Once you have read, understood, and acknowledged the contents of this folder (`AGENT_HANDOFF_INSTRUCTIONS/`), **YOU MUST DELETE THIS ENTIRE FOLDER FROM THE REPOSITORY** (`rm -rf AGENT_HANDOFF_INSTRUCTIONS && git commit -m "chore: remove agent handoff folder after onboarding" && git push`), **EXCEPT for the data folder (`projects/quant_strategy_discovery/data/`) which MUST REMAIN PERMANENTLY in the repo!**

---

## 1. Executive Mission & Context
You are working on the **CFD Quantitative Strategy Discovery & Expert Advisor Production Program** for **XAUUSD (Gold CFD)** with secondary **EURUSD** macro correlation on MetaTrader 5 (MT5).

* **Repository:** `https://github.com/BlamzKunG/CFD-Trading-ML.git`
* **Git Author Discipline:** Always commit as `BlamzKunG <blamzkung@users.noreply.github.com>`.
* **Primary Asset:** XAUUSD (Gold CFD) across 2020-01-01 to 2025-12-31 (6 Full Calendar Years / 72 Calendar Months).
* **Historical Data Location:** Fully uploaded and ready in [`projects/quant_strategy_discovery/data/`](file:///root/CFD-Trading-ML/projects/quant_strategy_discovery/data/):
  - `XAUUSD_M1.parquet` (2,116,595 bars, 38 MB)
  - `XAUUSD_M5.parquet` (423,930 bars, 9.6 MB)
  - `XAUUSD_M15.parquet` (141,567 bars, 3.6 MB)
  - `XAUUSD_H1.parquet` (35,400 bars, 1.2 MB)
  - `EURUSD_M15.parquet` (148,843 bars, 3.1 MB)
  - `EURUSD_H1.parquet` (37,211 bars, 1.1 MB)

---

## 2. ⚠️ CRITICAL GROUND TRUTH (DO NOT BE FOOLED BY SYNTHETIC NUMBERS)

In earlier research batches (Batches 40–43), simulations utilized mathematical post-processing multipliers (e.g. `pnl = pnl * 2.1384` or `pnl * 0.087`) and measured Drawdown purely on closed-trade PnL. This produced illusory metrics (Drawdowns of $28 to $73, Profit Factors > 40.0).

**The V5.1 Rigorous Audit (Commit `9227ffd`) revealed the hard market truth:**
1. **The Friction Tax Trap:**
   - Under institutional friction of $0.25 spread + $6.00/lot commission ($3.10 round-turn cost per 0.10 lot), a high-frequency system taking 6,800+ trades pays over **$21,200 in broker fees alone**!
   - In micro-scalping on M1, average bar range is only $0.80–$1.20. The $0.31 fee eats 25%–35% of the entire bar. When combined with realistic slippage and pessimistic execution, micro-scalping gets ground to dust.
2. **The Only Positive Survivor:**
   - **`S421: M15 Solo Supertrend Scalper`** was the **only strategy that achieved positive net profit (+$775.18, PF 1.009)** under the strict rules.
   - **Why?** Because M15 bars have an ATR of $4.00–$6.00. The $0.25 spread is only 4%–6% of the bar range, allowing genuine macro trend momentum to survive the friction drag.
3. **True Drawdown Reality:**
   - When measuring **Intra-Bar Adverse Excursion (deepest dip during active trade life)**, the true historical 6-year drawdown on 0.10 lot of Gold is **$5,000 to $17,000** (50 to 170 gold points). Any claim of sub-$100 drawdown without massive position downscaling is mathematically false.

---

## 3. Mandatory Execution Mandates (Constitution V5.1)

You **MUST ALWAYS** enforce the following rules in every backtest and code generation:

* **Rule D.1 — Pessimistic Sequence Mandate:**
  If within a single bar, price touches BOTH the Target (TP/Tranche) and the Stop Loss (SL), **YOU MUST ASSUME SL WAS HIT FIRST**. No optimistic path assumptions!
* **Rule D.2 — Strict Bar-Close Trailing Mandate:**
  Trailing stops and breakeven adjustments can **ONLY** be computed at **M1 Bar Close**, taking effect at the **next bar Open**. Never slide stops continuously intra-bar without tick data!
* **Rule D.3 — Intra-Bar Equity Tracking Mandate:**
  Maximum Drawdown **MUST** be calculated including the deepest intra-bar adverse excursion (`min(low - entry, 0)` for longs, `min(entry - high, 0)` for shorts). Never rely solely on closed PnL!
* **Rule D.4 — Negative Slippage on Stop Loss:**
  Every SL fill must be penalized with a fixed **-$0.10/oz adverse slippage** ($10.00/standard lot, -$1.00 per 0.10 lot).
* **Rule D.5 — Absolute Prohibition of Synthetic Multipliers:**
  Every strategy evaluated on the Leaderboard or converted to an EA **MUST** be simulated 100% bar-by-bar discrete event-driven. Never multiply PnL arrays by scaling factors!
* **Rule D.6 — Lot Step Realism & Tranche Limit:**
  All scale-out tranches must be exact multiples of **0.01 lot**. Limit scale-out tranches to **maximum 2–3 stages** (e.g. 50% TP1 Breakeven + 50% Runner) to prevent transaction cost accumulation.
* **Rule D.7 — Institutional Frictions & Swap:**
  - Gold Spread: Minimum $0.25 ($25.00/lot). Note: The user's actual broker spread is $0.11–$0.15 with $3–$6 commission, so our $0.25 baseline provides a built-in ~2x safety margin.
  - Commission: $6.00/lot ($0.60 per 0.10 lot).
  - Overnight Swap: -$18.00/standard lot/night for Long positions held past 00:00 server time.

---

## 4. Key Repository Directories & Artifacts

| Path | Description |
| :--- | :--- |
| [`projects/quant_strategy_discovery/data/`](file:///root/CFD-Trading-ML/projects/quant_strategy_discovery/data/) | **Historical Parquet Data (M1, M5, M15, H1 for XAUUSD & EURUSD)** — *DO NOT DELETE* |
| [`projects/quant_strategy_discovery/Scalping_Live_Ready_EAs/`](file:///root/CFD-Trading-ML/projects/quant_strategy_discovery/Scalping_Live_Ready_EAs/) | Curated package of the Top 10 Scalping EAs discovered to date |
| [`projects/quant_strategy_discovery/scripts/rigorous_scalping_rebacktest.py`](file:///root/CFD-Trading-ML/projects/quant_strategy_discovery/scripts/rigorous_scalping_rebacktest.py) | The reference Python discrete event backtester enforcing Rules D.1–D.7 |
| [`projects/quant_strategy_discovery/docs/MASTER_STRATEGY_LEADERBOARD.md`](file:///root/CFD-Trading-ML/projects/quant_strategy_discovery/docs/MASTER_STRATEGY_LEADERBOARD.md) | Master Leaderboard documenting Strategies S1 through S630 |
| [`projects/quant_strategy_discovery/ea/`](file:///root/CFD-Trading-ML/projects/quant_strategy_discovery/ea/) | Full archive of all generated MQL5 Expert Advisors |

---

## 5. Recommended Strategic Research Roadmap for the Next Agent

1. **Shift Focus from M1 Micro-Scalping to M5/M15 High-Expectancy Setups:**
   - Stop aiming for 1,000+ trades/year. High turnover kills capital via friction.
   - Target **150 to 350 trades/year** with an average winning trade expectation $\ge \$2.00\text{--}\$4.00/\text{oz}$.
2. **Native Limit Order & Hard TP Architecture in MT5:**
   - In MQL5 EA code, place native broker-side Take Profit orders so executions occur instantaneously at the broker level without waiting for bar close.
3. **Session Confluence & Liquidity Sweeps:**
   - Prioritize London Open (07:00–10:00 UTC) and New York Open (12:00–16:00 UTC).
   - Require multi-timeframe alignment (M15 trend + M5 volatility squeeze ignition) before entry.
