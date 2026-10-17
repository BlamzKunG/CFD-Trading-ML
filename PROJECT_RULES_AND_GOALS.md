# Project Constitution: Scalping Rule-Based CFD Quantitative Research & Logic Template Discovery (V6.0)

**Repository:** `CFD-Trading-ML`  
**Scope:** High-Frequency & Scalping Quantitative Strategy Discovery with Multi-Timeframe Matrix (M1, M5, M15) on Google Colab  
**Primary Asset:** `XAUUSD` (Gold)  
**Trade Volume Expectation:** ~300+ Trades/Year (ยืดหยุ่นได้ 250–800+ Trades/ปี เน้น Active Turnover ไม่ปล่อยให้เงินทุนแช่นิ่ง)  
**Execution Mode:** Continuous Non-Stop Autonomous Execution Loop (ทำงานเรื่อยๆ ห้ามหยุดพักเด็ดขาด)  
**Last Updated:** 2026-10-17  

---

## 1. วิสัยทัศน์และเป้าหมายหลักของโปรเจกต์ (Core Vision & Mandate)

1. **มุ่งเน้นสาย Scalping & High-Turnover Edge (Scalping Research Mandate):**
   * เปลี่ยนทิศทางจากระบบ Safe / Swing สู่การวิจัยระบบ **Scalping** เพื่อจับจังหวะทำกำไรรายวันจากความผันผวนของราคาทองคำ
   * ออกแบบตรรกะให้เก็บกำไรสั้น กระชับ คุมความเสี่ยงแน่นหนา และมีจำนวนไม้เทรดสม่ำเสมอ
2. **สถาปัตยกรรมทดสอบแบบ Multi-Timeframe Matrix (Colab Parallelism):**
   * **กฎเหล็ก Multi-TF:** ทุก 1 สมมติฐาน/กลยุทธ์ที่คิดค้นขึ้น **ต้องไม่ทดสอบแค่ Timeframe เดียว** แต่ต้องส่งไปทดสอบขนานกันบน **`M1`, `M5`, และ `M15`** พร้อมกันบน Google Colab เพื่อพิสูจน์ Cross-Timeframe Robustness
3. **ส่งมอบตรรกะที่แน่นอน ไม่สะเปะสะปะ (Deterministic Logic Templates for EAs):**
   * ทุกกลยุทธ์ที่ผ่านเกณฑ์จะต้องถูกจัดทำเป็น **"แม่แบบตรรกะที่สมบูรณ์ 100%"** สำหรับสร้าง EA
   * ต้องระบุชัดเจนทั้ง: Trigger, Filter, Stop Loss, Take Profit และโค้ด MQL5 สำเร็จรูปที่นำไปใช้ได้ทันที
4. **ความหลากหลายของตรรกะอย่างกว้างขวาง (Unlimited Strategy Scope):**
   * กระจายการค้นคว้าครอบคลุมทุก Archetype ของสาย Scalping:
     - Session Open & Liquidity Sweeps (London/NY Open, Asia Sweep, Judas Swings)
     - Momentum & Volatility Breakout (Keltner/BB Squeeze, Volume Expansion)
     - Fast Pullback & Continuation (EMA Ribbon, Supertrend Micro)
     - Mean Reversion & Overbought/Oversold (RSI Extremes, Institutional VWAP Deviations)
     - Order Flow & Microstructure Imbalance (FVG Retest, Candle Body/Range Spikes)
5. **โฟกัสสินทรัพย์ XAUUSD เป็นหลัก:**
   * โฟกัสทองคำ `XAUUSD` เป็นสนามทดสอบหลักตัวเดียวก่อน เนื่องจาก ATR กว้าง อัตราส่วน Friction ต่อผลตอบแทนต่ำที่สุด ชนะค่าสเปรดและคอมมิชชั่นได้ดีที่สุด

---

## 2. กฎเหล็กความถูกต้องทางคณิตศาสตร์และการประเมินผล (Quantitative Rigor)

1. **Strict Causality (ห้าม Lookahead เด็ดขาด):**
   * สัญญาณที่คอนเฟิร์มเมื่อปิดแท่ง $i$ ต้องเข้าออเดอร์ที่ราคาเปิดแท่งถัดไป $i+1$ เท่านั้น
   * การตรวจสอบ Stop Loss และ Take Profit ระหว่างแท่งต้องใช้หลักการ Worst-Case Check เสมอ
2. **ต้นทุนการเทรดสถาบันสมจริง (Realistic Institutional Friction):**
   * ทองคำ (XAUUSD): Spread $\ge \$0.25$ ($25.00/Lot) + Commission $\$6.00$/Lot + Slippage Buffer
   * ขนาดสัญญามาตรฐานในการเปรียบเทียบ: 0.10 Lot
   * การ Scalp ต้องมี Take Profit เพียงพอที่จะครอบคลุมต้นทุน Friction รวม $0.31 ได้อย่างมั่นคง
3. **การทดสอบความทนทาน (Stress Testing):**
   * ทดสอบสเปรด 2 เท่า ($0.50) เพื่อพิสูจน์ความทนทานต่อสเปรดถ่าง
   * ตรวจสอบผลตอบแทนแยกรายปี (2020–2025) และรายเดือน (72 เดือน)
   * Monte Carlo Permutation 1,000 รอบเพื่อหา Drawdown ที่ 95% และ 99% CI
4. **การประเมินผลลัพธ์ (Performance Expectations):**
   * คาดหวังการเทรด: ~300+ trades/ปี
   * Profit Factor เป้าหมาย: $\ge 1.50$
   * Monthly Consistency Ratio (MCR) เป้าหมาย: $\ge 70\% - 90\%$

---

## 3. สถาปัตยกรรมการประมวลผลและการป้องกันฮาร์ดแวร์ (Hardware & Colab Protocol)

1. **ห้ามรันการคำนวณหนักบนเครื่องมือถือเด็ดขาด:** ใช้เครื่องโทรศัพท์เป็น Client Controller, Code Generator, Documentation และ Local Backup เท่านั้น
2. **Google Colab Cloud Execution:** การทำ Parameter Sweeps ขนาดใหญ่, Multi-Timeframe Sweeps (M1, M5, M15) และ Batch Run ต้องสั่งผ่าน Google Colab CLI (`colab`) เสมอ
3. **Dedicated Parquet Cache & Resource Safety:** ใช้ไฟล์ Parquet ที่จัดเตรียมไว้ รันคำสั่งด้วย `nice -n 19`, คุม Single-thread และเรียก `gc.collect()` เสมอ

---

### 4. วงจรการทำงานต่อเนื่องแบบไม่หยุดพัก (Autonomous Continuous Loop)

1. **Non-Stop Autonomous Mandate:** ระบบ/Agent ต้องทำงานต่อเนื่องแบบอัตโนมัติ ห้ามหยุดพักหรือรอคำสั่งจากผู้ใช้ระหว่างรอบ
2. **Pre-Report Task Launch & Anti-Suspension Watchdog:** ก่อนจบเทิร์นหรือส่งรายงาน Milestone ต้องสั่งรัน Background Task ของกลยุทธ์ถัดไปไว้เสมอ (ห้ามปล่อยให้ระบบว่าง 0 tasks) หากต้องเตรียมงานให้ตั้ง Watchdog Timer (`schedule`) 120 วินาทีเพื่อปลุกขึ้นมาทำงานต่อทันที
3. **Task Lifecycle Hygiene:** เมื่อ Task ใดทำงานเสร็จ (`DONE`/`EXITED`) ต้องรีบ Kill เพื่อคืนหน่วยความจำทันที

---

## 5. การสำรองข้อมูลคู่ขนาน (Dual-Storage Redundancy)

1. **GitHub Repository:** Commit & Push สู่ `origin/main` ด้วยตัวตน `BlamzKunG` เสมอ
2. **Local Storage:** สำเนาไฟล์และ Artifacts ทั้งหมดลง `/mnt/sdcard/Download/EA/quant_strategy_discovery/` เสมอ
