# CFD Trading ML & Quantitative Discovery: Project Constitution & Execution Rules (V2.0)

> **Mandate:** Advanced Rule-Based CFD Quantitative Research, Deterministic Strategy Logic Template Discovery, and Automated Backtesting Engine (Target: Consistent Monthly Profitability).

---

## 1. Project Mission & Core Philosophy
1. **Deterministic Logic Templates for EAs:** Every discovered strategy must be delivered with 100% exact mathematical entry triggers, directional filters, SL formulas, TP formulas, and ready-to-run MQL5 code blocks.
2. **Mass Parametric Sweeping:** Every strategy must be evaluated across hundreds to thousands of parameter combinations simultaneously to isolate wide, robust plateaus.
3. **Monthly Consistency Standard ("กำไรทุกเดือน"):**
   - Must evaluate 72-month profitability heatmaps (2020–2025).
   - Monthly Consistency Ratio (MCR) target: $\ge 80\% - 90\%$ profitable months.
4. **Unlimited Strategy Scope:**
   - In-house bespoke proprietary quantitative algorithms.
   - Institutional quant papers and web research.
   - Hybrid cross-regime ensemble systems.
5. **Multi-Asset Coverage:** Test across all available historical data (XAUUSD, EURUSD, and future datasets).

---

## 2. Standard Operating Procedures (SOP)
1. **Strict Causality:** Signals confirmed at bar $i$ close execute ONLY at bar $i+1$ open. Conservative intra-bar collision checks.
2. **Institutional Frictions:** Gold spread $\ge \$0.25$, commission $\ge \$6.00$/lot. Forex spread $\ge 0.5$ pips, commission $\ge \$6.00$/lot.
3. **Standardized Comparison Sizing:** 0.10 lots across all models.

---

## 3. Autonomous Execution & Communication Rules
1. **Continuous Autonomy:** Work steadily through the research backlog without stopping.
2. **Token Efficiency:** No repetitive polling loops. Run sweeps asynchronously in the background.
3. **Reporting Cadence:** Report every 30 minutes OR upon finishing each strategy/major milestone.
4. **Task Management Lifecycle:** Check tasks after reporting — kill finished tasks (`DONE`/`EXITED`), let running tasks proceed undisturbed.

---

## 4. Mandatory Dual-Backup Protocol
Sync to both GitHub (`origin/main`) and Phone (`/mnt/sdcard/Download/EA/quant_strategy_discovery/`) on every completed strategy.
