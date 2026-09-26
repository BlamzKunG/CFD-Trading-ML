# 📑 คู่มือระบบ AI/ML สำหรับทำนายระยะการไปต่อของราคา (XAUUSD Room-to-Run Estimator)

เอกสารฉบับนี้อธิบายรายละเอียดเกี่ยวกับสถาปัตยกรรม, อัลกอริทึม, เครื่องมือ, ขั้นตอนการเทรน และการนำโมเดลไปใช้งานร่วมกับ Expert Advisor (EA) ตามความต้องการเฉพาะของระบบ

---

## 1. วัตถุประสงค์และบทบาทของโมเดล (Philosophy & Objectives)

### สิ่งที่โมเดลนี้ "เป็น" และ "หน้าที่หลัก":
* เป็น **ตัวช่วยประเมินระยะทางที่ราคามีโอกาสวิ่งต่อ (Room-to-Run / Excursion Estimator)** ในอีก $N$ แท่งข้างหน้า (เช่น 15 แท่ง)
* ตอบคำถาม 2 ข้ออย่างชัดเจน:
  1. **ถ้าราคาขึ้น:** มันมีโอกาสวิ่งขึ้นไปได้สูงสุดเท่าไหร่ (Maximum Upside Potential)
  2. **ถ้าราคาลง:** มันมีโอกาสวิ่งลงไปได้ลึกสุดเท่าไหร่ (Maximum Downside Potential)

### สิ่งที่โมเดลนี้ "ไม่ได้เป็น":
* ❌ **ไม่ใช่ Logic ออกออเดอร์เดี่ยวๆ:** โมเดลไม่ได้สั่ง Buy หรือ Sell ตรงๆ แต่ทำงานเป็น **Filter และ Dynamic Target** ให้กับระบบ EA เดิมของคุณ
* ❌ **ไม่ใช่ตัวหาแนวรับแนวต้าน:** โมเดลไม่ได้วาดเส้นแนวรับแนวต้านคงที่ แต่คำนวณ "แรงเหวี่ยงและความยืดตัวของราคา" ตามสภาวะตลาดจริงในปัจจุบัน

---

## 2. วิธีแก้ปัญหา "ราคาทอง 4000 ตอนนี้ กับ 2000 เมื่อก่อน" (Scale-Invariance & Stationarity)

### ทำไมการใช้ราคาดิบถึงล้มเหลว?
หากป้อนราคาดิบ (เช่น Close, SMA) หรือให้โมเดลทำนายเป็น "ระยะดอลลาร์ดิบ" (เช่น ราคาจะวิ่ง $20):
* ปี 2020: ทองคำอยู่ที่ $1,500 การขยับ $20 คิดเป็น **1.33%** (แท่งข่าวใหญ่ระดับมหึมา)
* ปี 2025: ทองคำอยู่ที่ $4,000 การขยับ $20 คิดเป็นเพียง **0.50%** (การแกว่งตัวธรรมดาในแท่งสั้นๆ)
* ผลลัพธ์: โมเดลจะสับสนและล้มเหลวทันทีเมื่อเจอกับราคาที่ไม่เคยเห็นในอดีต (Out-of-Distribution Shift)

### ✅ ทางออกทางคณิตศาสตร์ที่เราใช้:
1. **Target Formulation (ทำนายเป็นจำนวนเท่าของ ATR):**
   $$\text{Target\_Upside\_ATR} = \frac{\max(High_{t+1 \dots t+N}) - Close_t}{ATR_t}$$
   $$\text{Target\_Downside\_ATR} = \frac{Close_t - \min(Low_{t+1 \dots t+N})}{ATR_t}$$
   * ค่า ATR จะขยายตัวตามระดับราคาและความผันผวนจริงของตลาดโดยอัตโนมัติ
   * Output ของโมเดลจะบอกเป็น **"จำนวนเท่าของ ATR"** เช่น `+2.4 ATR` หรือ `-0.8 ATR`

2. **22 Features ไร้ราคาดิบ 100% (Stationary Features):**
   * **Multi-Horizon Returns (Log Returns):** $\ln(Close_t / Close_{t-k})$ ($k = 1, 3, 5, 15, 30, 60$)
   * **ระยะห่างจาก Moving Average ต่อ ATR:** $(Close - EMA_{20}) / ATR$, $(Close - EMA_{50}) / ATR$, $(Close - EMA_{200}) / ATR$ (วัดความยืดตัวของเทรนด์)
   * **สัดส่วนแท่งเทียนต่อ ATR:** ขนาดเนื้อเทียน, ไส้บน, ไส้ล่าง เทียบกับ ATR
   * **อัตราส่วนความผันผวน:** $ATR_{14} / Close$ (ความผันผวนสัมพัทธ์) และ $ATR_{14} / ATR_{50}$ (การบีบ/ระเบิดตัวของ Volatility)
   * **Momentum & Volume:** RSI(14) (สเกล 0–1) และสัดส่วน Tick Volume เทียบกับเส้นเฉลี่ย 20 และ 100 แท่ง
   * **Session Cyclic Encoding:** $\sin, \cos$ ของเวลาและวันในสัปดาห์ (London / New York Session)

---

## 3. เครื่องมือและ AI อัลกอริทึมที่เลือกใช้ (Tech Stack & Algorithm)

### ทำไมถึงเลือก LightGBM (Gradient Boosted Decision Trees)?
1. **ประสิทธิภาพสูงสุดบนข้อมูลตาราง (Tabular Financial Data):** ในวงการ Quantitative Finance โมเดลตระกูล Tree-based มักชนะ Deep Learning บนข้อมูล Price Action เพราะไม่เกิด Overfitting จาก Noise ระดับสูง
2. **Speed & Efficiency:** ข้อมูล 2.1 ล้านแถว สามารถเทรนจบได้ในเวลาเพียง **2–5 นาที** บน Google Colab
3. **Loss Function (L1 Regression / MAE):** ใช้ `objective='regression_l1'` ซึ่งทนทานต่อ Outliers และ Flash Spikes ผิดปกติในตลาดทองคำได้ดีกว่า MSE ทั่วไป

### เครื่องมือที่ใช้:
* **Google Colab CLI (colab-cli):** สำหรับควบคุมการสร้าง VM, อัปโหลดโค้ด และสั่งเทรนบน Google Cloud โดยตรงจาก Terminal
* **Python 3.12+ / Pandas / NumPy:** จัดการข้อมูลและคำนวณ Feature Engineering
* **Scikit-Learn & Joblib:** สำหรับประเมินผลและบันทึกโมเดล

---

## 4. กระบวนการเทรนและการตรวจสอบผล (Validation Methodology)

* **Time-Series Split (80% Train, 20% Test):**
  * **Train Set (80% แรก):** ข้อมูลตั้งแต่ปี 2020 ถึงต้นปี 2024 (~1.69 ล้านแท่ง)
  * **Test Set (20% หลัง):** ข้อมูลตั้งแต่ปี 2024 ถึงปลายปี 2025 (~420,000 แท่ง)
  * **ห้าม Shuffle เด็ดขาด:** เพื่อป้องกัน Lookahead Bias และ Data Leakage
* **Early Stopping:** หยุดการเทรนอัตโนมัติหากผลประเมินบนชุดข้อมูลทดสอบไม่ดีขึ้นติดต่อกัน 30 รอบ เพื่อป้องกัน Overfitting

---

## 5. วิธีนำโมเดลไปใช้งานร่วมกับ EA (Production Deployment)

เมื่อโมเดลส่งผลทำนายกลับมา (เช่น `pred_up = 2.3` และ `pred_down = 0.8`):

### โค้ดตัวอย่างใน MQL5:
```mql5
// 1. อ่านค่า ATR14 ปัจจุบันจากกราฟ
double current_atr = iATR(_Symbol, PERIOD_CURRENT, 14, 0);

// 2. แปลงผลทำนายของโมเดลกลับเป็นระดับราคาจริง
double expected_max_high = Close[0] + (pred_up   * current_atr);
double expected_max_low  = Close[0] - (pred_down * current_atr);

// 3. ตัวอย่างการนำไปใช้:
// A. เป็น Filter สัญญาณเทรด:
if (ea_signal == SIGNAL_BUY) {
   if (pred_up < 0.8) {
      // Upside เหลือน้อยเกินไป (< 0.8 ATR) สั่งยกเลิกไม่เข้าออเดอร์
      return; 
   }
}

// B. ตั้งจุด Take Profit อัตโนมัติ (Dynamic TP):
double dynamic_tp = expected_max_high;
```
