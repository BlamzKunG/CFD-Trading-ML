# 📡 XAUUSD Probabilistic Market Sensor: Research & Architecture Guide

> **Core Philosophy:**
> *"สร้าง AI เป็น Market Sensor สำหรับวัด Room-to-Run ของราคาทองคำ โดยโมเดลไม่ต้องบอกว่า Buy หรือ Sell แต่ตอบว่าจากสภาพตลาดตอนนี้ ในอีก $H$ แท่งข้างหน้า ราคาจะมีโอกาสแตะระยะ $D$ มากน้อยเพียงใด"*

---

## 1. นิยามปัญหาและสถาปัตยกรรมเป้าหมาย (Problem Formulation)

ระบบแปลงปัญหาจากการพยากรณ์ราคาดิบ (Raw Price Regression) มาเป็นการคำนวณ **ความน่าจะเป็นของการแตะระยะทาง (Excursion Reach Probability)** บน **Probability Surface Matrix ขนาด 30 ช่อง**:

* **2 ทิศทางการเคลื่อนที่:** ฝั่งขึ้น (`UP`) และ ฝั่งลง (`DOWN`)
* **5 ระดับระยะทาง (ATR Multiples - Scale-Invariant):**
  * $D \in \{0.5, 1.0, 1.5, 2.0, 2.5\} \times \text{ATR}_{14}$
* **3 กรอบเวลาล่วงหน้า (Horizons):**
  * $H \in \{30, 60, 90\}$ แท่งเทียน (M1)
* **รวมทั้งหมด:** $2 \times 5 \times 3 = \mathbf{30 \text{ Binary Targets}}$

### สูตรคำนวณเป้าหมาย (Binary Target Formulation):
$$Y_{\text{up}}(D, H)_t = \begin{cases} 1 & \text{ถ้า } \max(\text{High}_{t+1 : t+H}) \ge \text{Close}_t + (D \times \text{ATR}_{14, t}) \\ 0 & \text{ถ้าไม่ถึง} \end{cases}$$

$$Y_{\text{down}}(D, H)_t = \begin{cases} 1 & \text{ถ้า } \min(\text{Low}_{t+1 : t+H}) \le \text{Close}_t - (D \times \text{ATR}_{14, t}) \\ 0 & \text{ถ้าไม่ถึง} \end{cases}$$

---

## 2. การควบคุมความสะอาดของข้อมูล (Strict Data Hygiene & Anti-Leakage)

เพื่อป้องกัน **Label Overlap** และ **Look-ahead Bias** ข้อมูล 6 ปีเต็ม (2,116,595 แท่ง M1) ถูกแบ่งตามลำดับเวลาและคั่นด้วย **Purge Gap**:

```text
2020.01.02 ──────────────────── 2023.12.31
                 TRAIN SET
                     │
             [ 90-Bar Purge Gap ]
                     │
2024.01.01 ──────────────────── 2024.12.31
              VALIDATION SET
                     │
             [ 90-Bar Purge Gap ]
                     │
2025.01.01 ──────────────────── 2025.12.30
            DEVELOPMENT CHECK SET
                     │
             [ 90-Bar Purge Gap ]
                     │
2026.01.01 ──────────────────── 🔒 LOCKED
         BLIND OUT-OF-SAMPLE TEST
```

* **Purge Gap (90 แท่ง):** ถูกตัดทิ้งออกจากท้ายของแต่ละช่วงเวลา เพื่อไม่ให้เป้าหมาย $H=90$ แท่งเทียนของช่วงเวลาก่อนหน้า เหลื่อมเข้าไปแตะข้อมูลของช่วงเวลาถัดไป
* **🔒 2026 Blind Out-of-Sample:** **ห้ามแตะต้องเด็ดขาด** ระหว่างกระบวนการ Feature Engineering, Tuning หรือ Train เพื่อใช้ทดสอบประสิทธิภาพจริงเพียงครั้งเดียวในตอนสุดท้าย

---

## 3. ชุด Features วัดสภาวะตลาด (22 Stationary Features)

ห้ามไม่ให้โมเดลเห็นราคาดิบ (เช่น Close = 2,750) เพื่อให้ระบบใช้ได้กับทุกยุคราคาโดยไร้ปัญหา Non-stationarity:
1. **Multi-Horizon Log Returns:** $\ln(\text{Close}_t / \text{Close}_{t-k})$ สำหรับ $k \in \{1, 3, 5, 15, 30, 60\}$
2. **Normalized EMA Distances:** $(\text{Close}_t - \text{EMA}_k) / \text{ATR}_{14}$ สำหรับ $k \in \{20, 50, 200\}$
3. **Volatility Metrics:**
   * Relative Volatility: $\text{ATR}_{14} / \text{Close}_t$
   * Volatility Ratio: $\text{ATR}_{14} / \text{ATR}_{50}$ (ตรวจจับภาวะบีบตัว Compression vs ขยายตัว Expansion)
4. **Candlestick Microstructure:**
   * Bar Range: $(\text{High}_t - \text{Low}_t) / \text{ATR}_{14}$
   * Real Body: $(\text{Close}_t - \text{Open}_t) / \text{ATR}_{14}$
   * Upper Wick: $(\text{High}_t - \max(\text{Open}_t, \text{Close}_t)) / \text{ATR}_{14}$
   * Lower Wick: $(\min(\text{Open}_t, \text{Close}_t) - \text{Low}_t) / \text{ATR}_{14}$
5. **Momentum:** $\text{RSI}_{14} / 100$ (สเกล $0.0 - 1.0$)
6. **Volume Ratios:** $\text{Volume}_t / \text{SMA}(\text{Volume})_{20}$ และ $\text{Volume}_t / \text{SMA}(\text{Volume})_{100}$
7. **Cyclic Time Features:** $\sin/\cos$ ของชั่วโมงในวัน (24h) และวันในสัปดาห์ (Day of Week)

---

## 4. แผนงานการทดลอง (3-Stage Experimental Suite)

### 🥇 Stage 1: Fast Tabular Baseline
* **LightGBM (30 Independent Classifiers):** สร้างโมเดลแยกกัน 30 ตัว ตัวละ 1 เป้าหมาย (`target_up_0.5_30`, ..., `target_down_2.5_90`)
* **XGBoost & CatBoost:** รันบนฟีเจอร์และ Split เดียวกัน เพื่อเปรียบเทียบความสามารถในการจับ Non-linear Interaction
* **HistGradientBoosting & ExtraTrees:** ใช้เป็น Sanity Benchmark

### 🥈 Stage 2: Modeling Strategy Comparison
* **Independent Models vs Conditional Model:**
  * **Independent:** $P(Y_i \mid \text{state})$ เรียนรู้ 30 โมเดลแยกกัน
  * **Conditional Unified Model:** เรียนรู้ฟังก์ชันเดียว:
    $$P(\text{reach} \mid \text{state}, \text{direction}, \text{distance}, \text{horizon})$$
  * ช่วยให้สามารถ Query ระยะใดๆ ก็ได้ในอนาคตโดยไม่ต้องเทรนโมเดลใหม่ทั้งชุด

### 🥉 Stage 3: Deep Sequence / Neural Models
* **Multi-Head MLP:** โมเดล PyTorch รับ Input 22 ฟีเจอร์ ผ่าน Shared Backbone แล้วแยกออกเป็น 30 Heads (Sigmoid Output)
* **1D-CNN / Temporal Convolutional Network (TCN):** รับ Sequence ล่าสุด 128 แท่งเพื่อจับ Micro-structure, Compression และ Impulse โดยตรง

---

## 5. มาตรวัดประสิทธิภาพเชิงความน่าจะเป็น (Probabilistic Metrics)

เราไม่ใช้ Accuracy ทั่วไปในการตัดสิน แต่ใช้:
1. **Log Loss (Cross-Entropy):** ตรวจสอบคุณภาพการคาดการณ์เชิงความน่าจะเป็น
2. **Brier Score:** วัด Mean Squared Error ระหว่าง Probability กับผลลัพธ์จริง
3. **Calibration Curve (Reliability Diagram):** ตรวจสอบว่าเหตุการณ์ที่โมเดลบอกว่า $70\%$ เกิดขึ้นจริงประมาณ $70\%$ หรือไม่
4. **ROC-AUC & PR-AUC:** ตรวจสอบความสามารถในการแยกแยะชั้นข้อมูล
5. **Structural Monotonicity Violations (% การละเมิดทางกายภาพ):**
   * **Distance Monotonicity:** $P(D=0.5) \ge P(D=1.0) \ge P(D=1.5) \ge P(D=2.0) \ge P(D=2.5)$
   * **Horizon Monotonicity:** $P(H=30) \le P(H=60) \le P(H=90)$
   * ตรวจสอบว่าโมเดลเข้าใจธรรมชาติของพื้นที่และความน่าจะเป็นได้สมบูรณ์เพียงใด

---

## 6. การทำงานร่วมกับ MetaTrader 5 EA

โมเดลทั้งหมดถูกแปลงเป็น **ONNX Tensor [1, 22] $\to$ [1, 30]**:
* ใน MT5 EA เรียกใช้ผ่าน [`XAUUSD_Sensor.mqh`](file:///root/XAUUSD-ML-Excursion-EA/mql5/Include/XAUUSD_Sensor.mqh)
* แสดงผล Probability Surface แบบสดบนหน้าจอกราฟ
* บันทึกค่าทั้ง 30 ช่องลงไฟล์ `.csv` ใน `MQL5\Files\` ทุกแท่งเทียน M1 เพื่อใช้ตรวจสอบกับ Actual Event ของปี 2026 อย่างโปร่งใส 100%
