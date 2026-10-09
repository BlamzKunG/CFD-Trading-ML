# Project Constitution: Rule-Based CFD Quantitative Research & EA Logic Template Discovery

**Repository:** `CFD-Trading-ML`  
**Scope:** Rule-Based CFD Quantitative Strategy Discovery & Parameter Sweeping System  
**Last Updated:** 2026-10-09  

---

## 1. วิสัยทัศน์และเป้าหมายหลักของโปรเจกต์ (Core Vision & Objectives)

1. **ไม่มุ่งเน้นการสร้าง EA แบบปิด (Black-box One-off EAs):**
   * เป้าหมายของโปรเจกต์นี้ไม่ใช่การเขียน EA สำเร็จรูปขึ้นมาตัวเดียวแล้วจบ
   * เรากำลังสร้าง **"Rule-Based CFD Trading Logic Template Library"** — คลังแม่แบบตรรกะการเข้า/ออกออเดอร์เชิงปริมาณสำหรับสร้าง EA หลากหลายรูปแบบ
2. **การค้นหากลยุทธ์ที่ดีที่สุดผ่าน Mass Parameter Sweeping:**
   * ทุกตรรกะจะต้องถูกทดสอบแบบครอบคลุม **หลายร้อยถึงหลายพันชุดพารามิเตอร์** และ **หลายพันรูปแบบตลาด** พร้อมกัน
   * เป้าหมายคือการหา **"Wide Profitable Plateau"** (โซนพารามิเตอร์ที่มีเสถียรภาพสูง ไม่ใช่จุด Peak เดี่ยวๆ ที่เกิดจาก Overfitting)
3. **ขยายผลให้ครอบคลุมตาม Data ทั้งหมดที่มีในระบบ:**
   * ปัจจุบันรองรับ:
     - `XAUUSD_M1.csv.gz` (Gold CFD: 2.11 ล้านแท่ง, ปี 2020–2025)
     - `EURUSD_M1.csv.gz` (Forex Major: ปี 2020–2025)
   * รองรับการขยายผลไปยังสินทรัพย์และ Timeframe อื่นๆ อย่างต่อเนื่อง

---

## 2. กฎเหล็กเชิงปริมาณและความถูกต้องของข้อมูล (Quantitative Integrity Rules)

1. **Strict Causality & Anti-Lookahead Policy (ห้าม Lookahead เด็ดขาด):**
   * สัญญาณที่คอนเฟิร์มเมื่อปิดแท่ง $i$ (Candle Close $i$) จะต้องเข้าออเดอร์ที่ราคาเปิดของแท่งถัดไป $i+1$ (Open $i+1$) เท่านั้น
   * ห้ามใช้ข้อมูล High, Low หรือ Close ของแท่งปัจจุบันก่อนที่แท่งจะปิดสมบูรณ์
   * การชน Stop Loss หรือ Take Profit ระหว่างแท่ง ต้องใช้หลักการอนุรักษ์นิยม (Conservative Worst-Case Check)
2. **ต้นทุนการเทรดสมจริง (Mandatory Realistic Frictions):**
   * **ทองคำ (XAUUSD):** Spread อย่างน้อย $0.25 ($25.00/Lot) + Commission $6.00/Round-Turn Lot + Slippage
   * **Forex (EURUSD):** Spread 0.3–0.6 pips + Commission $6.00/Lot
   * ขนาดสัญญามาตรฐานในการเปรียบเทียบ: 0.10 Standard Lots (10 oz Gold)
3. **การทดสอบความทนทาน (Mandatory Stress Testing Protocol):**
   * **Friction Stress Test:** ทดสอบสเปรด 2 เท่า ($0.50) และ 3 เท่า ($0.75) เพื่อพิสูจน์ว่ากลยุทธ์ยังรอดในสภาวะสเปรดถ่าง
   * **Annual Consistency:** ต้องแสดงผลแยกรายปี (2020–2025) เพื่อดูความสม่ำเสมอ
   * **Monte Carlo Permutation:** สุ่มลำดับไม้เทรด 1,000 รอบเพื่อหาค่า Drawdown ที่ 95% และ 99% Confidence Interval

---

## 3. กฎการทำงานอัตโนมัติและการบริหาร Task (Autonomous Workflow & Task Management)

1. **ทำงานต่อเนื่องแบบอิสระ (Continuous Autonomous Execution):**
   * AI จะต้องทำงานอย่างต่อเนื่องตามแผนงานวิจัยที่วางไว้ โดยไม่หยุดชะงักและไม่ถามคำถามจุกจิกโดยไม่จำเป็น
2. **จังหวะเวลาการรายงานผล (Reporting Cadence):**
   * ส่งรายงานสรุปผลที่มีโครงสร้างชัดเจน **ทุกๆ 30 นาที** หรือ **เมื่อเสร็จสิ้นแต่ละกลยุทธ์/Milestone ใหญ่**
3. **การประหยัด Token และประสิทธิภาพของระบบ (Token & Resource Efficiency):**
   * เมื่อรันการคำนวณขนาดใหญ่ ให้ส่งไปทำงานเป็น Background Process
   * **ห้ามวนลูป ManageTask หรือเช็คสถานะซ้ำๆ** ให้หยุดรอการแจ้งเตือนเสร็จสิ้นจากระบบอัตโนมัติ
4. **กฎการบริหารจัดการ Task หลังรายงาน (Task Management Lifecycle):**
   * เมื่อส่งรายงานแต่ละรอบเรียบร้อยแล้ว ให้ทำการตรวจสอบ Background Tasks
   * **หากมี Task ใดที่ทำงานเสร็จแล้ว (`DONE` หรือ `EXITED`) ให้สั่ง Kill/Clean up ทันที** เพื่อคืนทรัพยากรระบบ
   * **หากมี Task ใดที่กำลังประมวลผลตามเป้าหมายปกติอยู่ ให้ปล่อยให้ทำงานต่อไปโดยไม่รบกวน**

---

## 4. กฎการสำรองข้อมูลคู่ขนาน (Dual-Storage Zero Data Loss Protocol)

ทุกครั้งที่การทดลองหรือเอกสารวิจัยเสร็จสิ้นในแต่ละรอบ ต้องทำการสำรองข้อมูลลง 2 แหล่งเสมอ:
1. **GitHub Repository:**
   ```bash
   git add projects/quant_strategy_discovery/
   git commit -m "feat(quant): <รายละเอียดความคืบหน้า>"
   git push origin main
   ```
2. **โทรศัพท์มือถือ (Local Mobile Storage):**
   * สำเนาไฟล์โค้ด, ผลลัพธ์ CSV, Champion JSON และรายงาน Markdown ทั้งหมดลงที่:
     `/mnt/sdcard/Download/EA/quant_strategy_discovery/`

---

## 5. แผนที่กลยุทธ์ที่ค้นพบแล้ว (Catalog of Discovered Strategies)

| รหัส | ชื่อกลยุทธ์ | สถิติเด่น | สถานะ |
| :---: | :--- | :---: | :---: |
| **01** | Donchian / Turtle Breakout | Net -$1.6k, PF 0.98 | ❌ Rejected (Whipsaw บน M15) |
| **02** | Opening Range Breakout (NY ORB) | Net +$8.2k, PF 1.13 | ✅ Accepted (Breakout) |
| **03** | Supertrend Pro Trailing | Net +$3.4k, PF 1.04 (Strict) | ✅ Accepted (Trailing Core) |
| **04** | TTM Squeeze Volatility Expansion | Net +$7.2k, PF 1.085, DD $4.7k | 🏆 Top Champion (Squeeze 8 bars, 3R) |
| **05** | Triple Screen MTF Pullback | Net +$8.9k, PF 1.11 | ✅ Accepted (Pullback Filter) |
| **06** | Zero-Lag MACD Trend Inflection | Net +$8.6k, PF 1.064, กำไร 5/6 ปี | 🏆 Top Champion (ZL 15/34/9, 4R) |
| **07** | Bollinger Asian Reversion | Net +$1.6k, PF 1.10 | ✅ Accepted (Asian Scalper Only) |
| **08** | RSI Divergence Reversal | Net -$7.6k, PF 0.93, DD $16k | ❌ Rejected (Cascading Trap) |
| **09** | Liquidity Sweep & Judas Swing | Net +$3.0k, PF 1.135, DD $1.3k | ✅ Accepted (NY Session Reversal) |
| **10** | Fair Value Gap (FVG) Retest | Net +$11.3k, PF 1.115 | ✅ Accepted (EMA200 Orderflow) |
