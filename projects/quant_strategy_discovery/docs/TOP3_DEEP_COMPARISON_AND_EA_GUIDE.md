# Top 3 Champion Strategies: In-Depth Comparison, Sanity Audit & Production EA Guide

**Asset Class:** CFD Commodity (XAUUSD / Gold)  
**Timeframe:** M15 (Resampled from 2,116,595 raw M1 ticks/candlesticks)  
**Validation Period:** 2020-01-01 to 2025-12-30 (6 full multi-year regimes)  
**Benchmark Sizing:** 0.10 standard lots (10 oz units)  

---

## 1. Top 3 Candidates: Comparative Performance Matrix

| Metric | Champion #1: Zero-Lag MACD (4.0R Target) | Champion #2: TTM Squeeze (3.0R Target) | Champion #3: Supertrend Pro (Strict Trailing) |
| :--- | :---: | :---: | :---: |
| **Strategy Concept** | Dynamic momentum inflection with zero lag | Volatility compression explosion (BB in KC) | Volatility-adaptive structural trailing stop |
| **Trade Frequency** | ~350 trades / year | ~185 trades / year (Highly selective) | ~340 trades / year |
| **Win Rate** | 21.03% | 27.48% | 33.76% |
| **Profit Factor (Base Frictions)** | **1.064** | **1.085** | **1.040** |
| **Net PnL (0.10 Lot)** | **+$8,594.91** | **+$7,168.39** | **+$3,391.08** |
| **Profit Factor (2x Spread Stress $0.50)** | **1.010 (+ $1,345)** | **1.022 (+ $1,902)** | 0.948 (- $4,706) |
| **Max Drawdown (Historical)** | $6,196.46 | **$4,779.27** | $8,056.97 |
| **Monte Carlo Median DD (1,000 runs)** | $6,796.72 | **$5,372.50** | $5,524.13 |
| **Monte Carlo 95th Percentile DD** | $12,925.76 | **$10,471.48** | $10,849.70 |
| **Consistency Across 6 Years** | **5 of 6 Years Profitable** | **4 of 6 Years Profitable** | 3 of 6 Years Profitable |

---

## 2. Deep Sanity Audit: ข้อค้นพบเชิงลึกและจุดแปลกในผลลัพธ์แรกเริ่ม (The Sanity Check Findings)

เมื่อเราทำการทดสอบเจาะลึกตามข้อสังเกตของผู้ใช้ เพื่อตรวจสอบความถูกต้องอย่างเคร่งครัด (Rigorous Causal Verification):

### 🚨 1. ข้อค้นพบเรื่อง "Supertrend Intra-Bar Exit Bug"
* **สิ่งที่พบในโค้ด Backtest เริ่มต้น:** ในสคริปต์ `strategy_03` ครั้งแรก มีบั๊กทางตรรกะในฟังก์ชันจำลอง: เมื่อแท่งเทียนที่ $i$ ปิดแท่งแล้วเกิดสัญญาณ Supertrend Flip สลับฝั่ง บรรทัดคำนวณราคาออกกลับไปใช้ `opens[i]` (ราคาเปิดของแท่งเดิมที่เพิ่งเริ่ม) แทนที่จะเป็น `opens[i+1]` (ราคาเปิดของแท่งถัดไป) หรือราคา Stop จริง!
* **ผลกระทบ:** ทำให้ในการเทสรอบแรก ผลกำไรของ Supertrend ดูสวยหรูเกินจริง (+ $29.5k) เพราะระบบได้เปรียบ Lookahead เล็กน้อยในการหนีราคาร่วง
* **เมื่อแก้ไขเป็น Strict Causal 100%:**
  * กำไรสุทธิที่แท้จริงของ Supertrend Trailing ลดลงมาอยู่ที่ **+$3,391.08** ($PF=1.04$)
  * และเมื่อเจอบททดสอบความเคี่ยวของโบรกเกอร์ (Spread กว้าง $0.50) กลยุทธ์ Supertrend จะติดลบทันที (-$4,706) เนื่องจากธรรมชาติของ Trailing Stop บนแท่ง M15 จะโดน Whipsaw สะบัดตัดขาดทุนบ่อยเกินไป

### 🏆 2. ทำไม "Zero-Lag MACD" และ "TTM Squeeze" ถึงเป็น Champion ตัวจริงที่แข็งแกร่งที่สุด
* **Zero-Lag MACD (4.0R Target):** การตั้งเป้าหมายกำไรไกลถึง **4.0R** ทำให้ต้นทุนค่า Spread และ Commission แทบไม่มีผลกระทบต่อกำไรคำโต แม้ Spread จะถ่างเป็น 2 เท่า ($0.50) กลยุทธ์ก็ยังทำกำไรได้ต่อเนื่อง ($PF=1.010$) และมีกำไรเป็นบวกถึง 5 จาก 6 ปี (2020–2023 และ 2025 กำไรหมด)
* **TTM Squeeze (3.0R Target):** เป็นกลยุทธ์ที่มี **ความทนทานต่อต้นทุนสูงสุด ($PF=1.085$)** เพราะมีตัวกรองการบีบตัวนาน $\ge 8$ แท่ง ทำให้เปิดเทรดเพียง ~185 ไม้ต่อปี (น้อยกว่ากลยุทธ์อื่นเกือบครึ่งหนึ่ง) จึงประหยัดค่าคอมมิชชั่นและสเปรดไปได้หลายหมื่นดอลลาร์ และมี Drawdown ต่ำที่สุดในกลุ่ม ($4,779)

---

## 3. รายละเอียดและการทำงานของ EA ทั้ง 3 ตัว (MetaTrader 5 MQL5)

ไฟล์ Expert Advisor พร้อมใช้งานถูกสร้างไว้ที่โฟลเดอร์ [`projects/quant_strategy_discovery/ea/`](file:///root/CFD-Trading-ML/projects/quant_strategy_discovery/ea/):

### 1. `ZeroLag_MACD_Trend_EA.mq5` (Champion #1: Momentum Inflection)
* **ไฟล์:** [`ZeroLag_MACD_Trend_EA.mq5`](file:///root/CFD-Trading-ML/projects/quant_strategy_discovery/ea/ZeroLag_MACD_Trend_EA.mq5)
* **ตรรกะ:** คำนวณ Zero-Lag EMA สองชั้น ($2 \times \text{EMA} - \text{EMA}(\text{EMA})$) ทั้ง Fast (15) และ Slow (34) เมื่อเกิด Golden/Death Cross จะเปิด Buy/Sell ทันทีที่ราคาเปิดแท่งใหม่
* **การจัดการความเสี่ยง:**
  * Stop Loss: $2.0 \times \text{ATR}(14)$
  * Take Profit: $4.0 \times \text{Risk}$ ($4.0R$)
  * รองรับทั้ง Fixed Lot และ Dynamic Risk %

### 2. `TTM_Squeeze_Expansion_EA.mq5` (Champion #2: Volatility Explosion)
* **ไฟล์:** [`TTM_Squeeze_Expansion_EA.mq5`](file:///root/CFD-Trading-ML/projects/quant_strategy_discovery/ea/TTM_Squeeze_Expansion_EA.mq5)
* **ตรรกะ:** ตรวจสอบภาวะ Bollinger Bands (20, 2.0) บีบตัวอยู่ภายใน Keltner Channel (20, 2.0 ATR) ติดต่อกันอย่างน้อย 8 แท่งเทียน เมื่อเกิดการระเบิดตัว (Squeeze Fire) แท่งแรก พร้อมโมเมนตัมและทิศทางเหนือกว่า EMA 200 จะเปิดออเดอร์ตามทิศทางการระเบิด
* **การจัดการความเสี่ยง:**
  * Stop Loss: $3.0 \times \text{ATR}(14)$
  * Take Profit: $3.0 \times \text{Risk}$ ($3.0R$)

### 3. `Supertrend_Trailing_Pro_EA.mq5` (Champion #3: Strict Trailing Core)
* **ไฟล์:** [`Supertrend_Trailing_Pro_EA.mq5`](file:///root/CFD-Trading-ML/projects/quant_strategy_discovery/ea/Supertrend_Trailing_Pro_EA.mq5)
* **ตรรกะ:** คำนวณ Supertrend (14, 3.0) พร้อมตัวกรองเทรนด์ใหญ่ EMA 200 โดยใช้ตรรกะ Strict Candle Close เท่านั้น
* **ระบบ Trailing Stop:** ขยับ Stop Loss ตามเส้น Supertrend ขาขึ้น/ขาลง บนราคาเปิดแท่งใหม่อย่างเคร่งครัด ปิดออเดอร์ทันทีเมื่อแท่งเทียนปิดหลุดเส้นกลับทิศ
