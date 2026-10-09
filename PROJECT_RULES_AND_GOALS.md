# Project Constitution: Rule-Based CFD Quantitative Research & Logic Template Discovery (V2.0)

**Repository:** `CFD-Trading-ML`  
**Scope:** Advanced Rule-Based CFD Trading Strategy Discovery & Parameter Sweeping Engine  
**Core Target:** Deterministic Strategy Logic Templates with Consistent Monthly Profitability ("กำไรทุกเดือน")  
**Last Updated:** 2026-10-09  

---

## 1. วิสัยทัศน์และเป้าหมายหลักของโปรเจกต์ (Core Vision & Mandate)

1. **ส่งมอบตรรกะที่แน่นอน ไม่สะเปะสะปะ (Deterministic Logic Templates for EAs):**
   * ทุกกลยุทธ์ที่ผ่านเกณฑ์จะต้องถูกจัดทำเป็น **"แม่แบบตรรกะที่สมบูรณ์ 100%"** สำหรับสร้าง EA
   * ต้องระบุชัดเจนทั้ง: สูตรเงื่อนไขการเข้า (Trigger), ตัวกรองทิศทาง (Filter), สูตรคำนวณ Stop Loss, สูตรคำนวณ Take Profit และโค้ด MQL5 สำเร็จรูปที่นำไปใช้ได้ทันทีโดยไม่มีความคลุมเครือ
2. **เป้าหมายผลลัพธ์: "กำไรทุกเดือน" (Consistent Monthly Profitability):**
   * เพิ่มเกณฑ์การประเมินผลแบบ **72-Month Heatmap Analysis (2020–2025)**
   * เป้าหมาย: อัตราส่วนเดือนที่ทำกำไร **Monthly Consistency Ratio (MCR) $\ge 80\% - 90\%$**
   * เส้นกำไร (Equity Curve) ต้องเรียบสม่ำเสมอ ลดความผันผวนของผลตอบแทนรายเดือน
3. **ขอบเขตการคิดค้นที่ไม่จำกัด (Unlimited Strategy Scope):**
   * **เสาหลักที่ 1 (Proprietary In-House):** ตรรกะเชิงปริมาณที่ออกแบบขึ้นมาใหม่เอง (เช่น Asymmetric Volatility Skew, Microstructure Range Compression, Liquidity Vacuums)
   * **เสาหลักที่ 2 (Institutional & Quant Papers):** งานวิจัยและอัลกอริทึมจากสถาบันและเว็บไซต์ Quantitative ชั้นนำ
   * **เสาหลักที่ 3 (Hybrid & Cross-Regime Ensemble):** การผสานกลยุทธ์ที่ทำกำไรต่างสภาวะตลาด (เช่น Trend ในช่วง NY + Mean Reversion ในช่วง Asian)
4. **ความครอบคลุมของสินทรัพย์ (Multi-Asset Expansion):**
   * ปัจจุบันรองรับข้อมูล M1 ความละเอียดสูง:
     - ทองคำ `XAUUSD_M1.csv.gz` (2.11 ล้านแท่ง, 2020–2025)
     - ค่าเงินหลัก `EURUSD_M1.csv.gz` (2020–2025)
   * รองรับการขยายผลไปยังสินทรัพย์และ Timeframe อื่นๆ เพิ่มเติมตามไฟล์ใน DATA โฟลเดอร์

---

## 2. กฎเหล็กความถูกต้องทางคณิตศาสตร์และการประเมินผล (Quantitative Rigor)

1. **Strict Causality (ห้าม Lookahead เด็ดขาด):**
   * สัญญาณที่คอนเฟิร์มเมื่อปิดแท่ง $i$ ต้องเข้าออเดอร์ที่ราคาเปิดแท่งถัดไป $i+1$ เท่านั้น
   * การตรวจสอบ Stop Loss และ Take Profit ระหว่างแท่งต้องใช้หลักการ Worst-Case Check เสมอ
2. **ต้นทุนการเทรดสถาบันสมจริง:**
   * ทองคำ (XAUUSD): Spread $\ge \$0.25$ ($25.00/Lot) + Commission $\$6.00$/Lot + Slippage
   * ค่าเงิน (EURUSD): Spread $\ge 0.5$ pips + Commission $\$6.00$/Lot
   * ขนาดสัญญามาตรฐานในการเปรียบเทียบ: 0.10 Lot
3. **การทดสอบความทนทาน (Stress Testing):**
   * ทดสอบสเปรด 2 เท่า ($0.50) เพื่อพิสูจน์ความทนทานต่อสเปรดถ่าง
   * ตรวจสอบผลตอบแทนแยกรายปี (2020–2025) และรายเดือน (72 เดือน)
   * Monte Carlo Permutation 1,000 รอบเพื่อหา Drawdown ที่ 95% และ 99% CI

---

## 3. ระเบียบปฏิบัติการทำงานอัตโนมัติและการบริหาร Task (Autonomous Workflow)

1. **ทำงานต่อเนื่องแบบไม่หยุดพัก (Continuous Autonomous Execution):**
   * AI จะเดินหน้าทดลองและคิดค้นกลยุทธ์ตามคลังแนวคิดอย่างต่อเนื่องโดยอัตโนมัติ
2. **การประหยัด Token สูงสุด (Maximum Token Efficiency):**
   * รันการคำนวณขนาดใหญ่แบบ Background Process ไม่วนลูปตรวจสอบคำสั่งซ้ำๆ
3. **จังหวะเวลาการรายงาน:**
   * ส่งรายงานสรุปผลทุกๆ 30 นาที หรือเมื่อเสร็จสิ้นแต่ละกลยุทธ์/Milestone
4. **วงจรชีวิตการบริหาร Task (Task Management Lifecycle):**
   * หลังส่งรายงาน ให้ตรวจเช็ค Task: หาก Task ใดจบแล้ว (`DONE`/`EXITED`) ให้สั่ง Kill ทันทีเพื่อคืน RAM
   * หาก Task ใดกำลังคำนวณตามเป้าหมายปกติ ให้ปล่อยให้รันต่อไปอย่างอิสระ
5. **การสำรองข้อมูลคู่ขนาน (Dual-Storage Redundancy):**
   * GitHub Repository: Commit & Push สู่ `origin/main` เสมอ
   * Phone Storage: สำเนาไฟล์ทั้งหมดลง `/mnt/sdcard/Download/EA/quant_strategy_discovery/` เสมอ
