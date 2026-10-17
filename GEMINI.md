# CFD Trading ML & Quantitative Discovery: Project Constitution & Execution Rules (V6.0)

> **Mandate:** High-Frequency & Scalping Rule-Based CFD Quantitative Research, Multi-Timeframe Matrix (M1, M5, M15) on Google Colab, and Continuous Non-Stop Autonomous Execution Engine (Target: Consistent Monthly Profitability, ~300+ Trades/Year on XAUUSD).

---

## 1. Project Mission & Core Philosophy
1. **Scalping Focus on XAUUSD:** Research dedicated to robust intraday and high-turnover scalping strategies on Gold (`XAUUSD`), where ATR-to-friction ratio is most advantageous.
2. **Multi-Timeframe Simultaneous Testing:** Every single strategy hypothesis must be tested and evaluated across **`M1`, `M5`, and `M15` simultaneously** via Google Colab parallel batch execution.
3. **Deterministic Logic Templates for EAs:** Every discovered strategy must be delivered with 100% exact mathematical entry triggers, directional filters, SL formulas, TP formulas, and ready-to-run MQL5 code blocks.
4. **Volume Expectation:** Target trade frequency is expected at **~300+ trades/year** (flexible 250–800+ trades/year).
5. **Broad Strategy Diversity:** Full exploration across Session Sweeps, Momentum Breakouts, Squeeze Ignition, Fast Pullbacks, Mean Reversion, and Order Flow / FVG Imbalance.

---

## 2. Standard Operating Procedures (SOP)
1. **Strict Causality:** Signals confirmed at bar $i$ close execute ONLY at bar $i+1$ open. Conservative intra-bar collision checks.
2. **Institutional Frictions:** Gold spread $\ge \$0.25$, commission $\ge \$6.00$/lot. Standardized comparison sizing: 0.10 lots.
3. **Multi-Year Robustness:** 72-month heatmaps (2020–2025), target MCR $\ge 70\% - 90\%$, 2x spread stress tests, and 1,000-run Monte Carlo permutations.

---

### 4. วงจรการทำงานต่อเนื่องแบบไม่หยุดพัก (Autonomous Continuous Loop)

1. **Non-Stop Autonomous Mandate:** ระบบ/Agent ต้องทำงานต่อเนื่องแบบอัตโนมัติ ห้ามหยุดพักหรือรอคำสั่งจากผู้ใช้ระหว่างรอบ
2. **Pre-Report Task Launch & Anti-Suspension Watchdog:** ก่อนจบเทิร์นหรือส่งรายงาน Milestone ต้องสั่งรัน Background Task ของกลยุทธ์ถัดไปไว้เสมอ (ห้ามปล่อยให้ระบบว่าง 0 tasks) หากต้องเตรียมงานให้ตั้ง Watchdog Timer (`schedule`) 120 วินาทีเพื่อปลุกขึ้นมาทำงานต่อทันที
3. **Task Lifecycle Hygiene:** เมื่อ Task ใดทำงานเสร็จ (`DONE`/`EXITED`) ต้องรีบ Kill เพื่อคืนหน่วยความจำทันที

---

## 5. Mandatory Dual-Backup Protocol
Sync to both GitHub (`origin/main`) and Phone (`/mnt/sdcard/Download/EA/quant_strategy_discovery/`) on every completed strategy.
