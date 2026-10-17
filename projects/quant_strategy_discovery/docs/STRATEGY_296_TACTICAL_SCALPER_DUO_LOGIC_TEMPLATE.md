# STRATEGY 296: TACTICAL SCALPER DUO B (M15 LOGIC TEMPLATE & MQL5 BLUEPRINT)

**Strategy ID:** `STRATEGY_296`  
**Strategy Name:** Tactical Scalper Duo B (Supertrend Trailing Ratchet + TTM Squeeze Volatility Breakout)  
**Target Asset:** `XAUUSD` (Gold CFD)  
**Timeframe:** `M15`  
**Execution Frictions:** Spread = $0.25 ($25.00/standard lot), Commission = $6.00/lot ($0.60 per 0.10 lot)  
**Standard Lot Size:** 0.10 Lot ($10 / point)  
**Backtest Period:** 2020-01-02 to 2025-12-30 (6 Full Multi-Year Regimes)  

---

## 1. Executive Summary & Quantitative Thesis

Strategy 296 เป็นการรวมพลังของ 2 กลยุทธ์ชั้นยอดบน M15 ที่ได้รับการพิสูจน์แล้วว่าสามารถเอาชนะค่าเสียดทานของโบรกเกอร์ (Spread $0.25 + Commission $6.00/lot) ได้อย่างสมบูรณ์แบบ:
1. **Sub-Engine 1 (Supertrend Dynamic Volatility Ratchet - Magic 296001):**
   - หน้าที่: เป็นกระดูกสันหลังทำกำไรคำโต (Trend Capture Engine) โดยปล่อยให้ออเดอร์วิ่งไปตามแนวโน้มใหญ่ และใช้ Monotonic Ratchet Trailing Stop ล็อคกำไรตามความผันผวน ($3.0 \times ATR_{14}$)
   - สถิติเดี่ยว: 341.7 Trades/Year, Profit Factor 1.440, Net Profit +$30,590.19, Max DD $1,680.04, MCR 75.00%
2. **Sub-Engine 2 (TTM Squeeze Volatility Breakout - Magic 296002):**
   - หน้าที่: ดักจับการระเบิดตัวของราคาหลังจากเกิดการบีบอัดตัวของความผันผวนอย่างรุนแรง (Volatility Compression Breakout) โดยกรองให้ Bollinger Bands (20, 2.0) บีบตัวอยู่ภายใน Keltner Channel (20, 2.0) ติดต่อกันอย่างน้อย 8 แท่งเทียน ก่อนจะระเบิดตัวตามแนวโน้ม EMA 200
   - สถิติเดี่ยว: 195.0 Trades/Year, Profit Factor 1.083, Net Profit +$6,989.06, Max DD $4,779.26

### ผลลัพธ์จากการทดสอบ 6 ปีเต็ม (2020–2025):
* **ความถี่ในการเทรดรวม:** **536.7 Trades ต่อปี** (รวม 3,220 trades ตลอด 6 ปี — เฉลี่ย ~2.1 Trades ต่อวันเทรด บรรลุเป้าหมาย Scalping 300+ อย่างงดงาม)
* **กำไรสุทธิรวม (Net Profit):** **+$37,579.25** (คำนวณบน Lot 0.10 หลังหัก Spread และค่าคอมมิชชั่นครบถ้วน)
* **Profit Factor (PF):** **1.244** (สูงกว่าเกณฑ์ Scalping ทั่วไปอย่างมีนัยสำคัญ)
* **Win Rate:** **34.81%**
* **Maximum Drawdown:** **$4,533.90**
* **Return on Max Drawdown (RoMaD):** **8.29x**
* **Monthly Consistency Ratio (MCR):** **68.06%** (49 จาก 72 เดือนมีกำไรสุทธิเป็นบวก)

---

## 2. สูตรคณิตศาสตร์และเงื่อนไขการเทรดที่แน่นอน (Deterministic Logic)

### 2.1 ตัวกรองทิศทางแนวโน้มใหญ่ (Macro Trend Filter)
* คำนวณเส้น Exponential Moving Average 200 แท่งบน M15:
  $$EMA_{200}[t] = \alpha \cdot Close[t] + (1 - \alpha) \cdot EMA_{200}[t-1], \quad \alpha = \frac{2}{200 + 1}$$
* **Bullish Regime:** $Close[t] > EMA_{200}[t]$
* **Bearish Regime:** $Close[t] < EMA_{200}[t]$

---

### 2.2 ตรรกะของ Sub-Engine 1: Supertrend Trailing Ratchet (Magic: 296001)
* **Median Price:** $M[t] = \frac{High[t] + Low[t]}{2}$
* **Supertrend Bands:**
  $$U[t] = M[t] + 3.0 \times ATR_{14}[t]$$
  $$L[t] = M[t] - 3.0 \times ATR_{14}[t]$$
* **Ratchet Trailing:**
  $$\text{LowerBand}[t] = \max(L[t], \text{LowerBand}[t-1]) \quad \text{if } Close[t-1] > \text{LowerBand}[t-1]$$
  $$\text{UpperBand}[t] = \min(U[t], \text{UpperBand}[t-1]) \quad \text{if } Close[t-1] < \text{UpperBand}[t-1]$$
* **Entry Trigger:**
  * **Buy Order:** เมื่อ Trend พลิกจาก Bearish (-1) เป็น Bullish (+1) และ $Close[t] > EMA_{200}[t]$
  * **Sell Order:** เมื่อ Trend พลิกจาก Bullish (+1) เป็น Bearish (-1) และ $Close[t] < EMA_{200}[t]$
* **Exit Logic:**
  * ฝั่ง Buy: ปิดเมื่อ $Low[t] \le \text{LowerBand}[t]$ หรือเกิด Trend Flip เป็น Bearish
  * ฝั่ง Sell: ปิดเมื่อ $High[t] \ge \text{UpperBand}[t]$ หรือเกิด Trend Flip เป็น Bullish

---

### 2.3 ตรรกะของ Sub-Engine 2: TTM Squeeze Volatility Breakout (Magic: 296002)
* **Bollinger Bands (20, 2.0):**
  $$BB_{Mid}[t] = SMA_{20}(Close)[t]$$
  $$BB_{Upper}[t] = BB_{Mid}[t] + 2.0 \times \sigma_{20}[t]$$
  $$BB_{Lower}[t] = BB_{Mid}[t] - 2.0 \times \sigma_{20}[t]$$
* **Keltner Channel (20, 2.0):**
  $$KC_{Upper}[t] = BB_{Mid}[t] + 2.0 \times ATR_{14}[t]$$
  $$KC_{Lower}[t] = BB_{Mid}[t] - 2.0 \times ATR_{14}[t]$$
* **Squeeze State Definition:**
  $$\text{SqueezeActive}[t] = (BB_{Upper}[t] \le KC_{Upper}[t]) \land (BB_{Lower}[t] \ge KC_{Lower}[t])$$
* **Entry Trigger:**
  * เกิดการบีบอัดตัว $\text{SqueezeActive} == \text{True}$ ต่อเนื่องกัน $\ge 8$ แท่งเทียน
  * และในแท่งปัจจุบัน เกิดการดีดตัวหลุด Squeeze ($\text{SqueezeActive} == \text{False}$)
  * **Buy Order:** หาก $Close[t] > BB_{Mid}[t]$ และ $Close[t] > EMA_{200}[t]$
    - Stop Loss = $Ask - (3.0 \times ATR_{14}[t])$
    - Take Profit = $Ask + (3.0 \times \text{SL Distance}) = Ask + (9.0 \times ATR_{14}[t])$
  * **Sell Order:** หาก $Close[t] < BB_{Mid}[t]$ และ $Close[t] < EMA_{200}[t]$
    - Stop Loss = $Bid + (3.0 \times ATR_{14}[t])$
    - Take Profit = $Bid - (3.0 \times \text{SL Distance}) = Bid - (9.0 \times ATR_{14}[t])$

---

## 3. MQL5 Expert Advisor Implementation File

ไฟล์ Expert Advisor ที่พร้อมใช้งานจริงในโปรดักชันถูกบันทึกไว้ที่:
- [`projects/quant_strategy_discovery/ea/Gold_M15_Tactical_Duo_Squeeze_Scalper_Master_EA.mq5`](file:///root/CFD-Trading-ML/projects/quant_strategy_discovery/ea/Gold_M15_Tactical_Duo_Squeeze_Scalper_Master_EA.mq5)
- และสำรองไว้ที่โฟลเดอร์สำหรับโทรศัพท์มือถือ:
  `/mnt/sdcard/Download/EA/quant_strategy_discovery/ea/Gold_M15_Tactical_Duo_Squeeze_Scalper_Master_EA.mq5`
