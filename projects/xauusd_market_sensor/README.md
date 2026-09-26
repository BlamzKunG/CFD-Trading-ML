# 🚀 XAUUSD ML Excursion Estimator for MetaTrader 5 (Scale-Invariant AI)

โมเดลปัญญาประดิษฐ์ (Machine Learning) สำหรับประเมินระยะทางที่ราคาทองคำ (XAUUSD) มีโอกาสวิ่งต่อ (Room-to-Run / Excursion Potential) ในอีก N แท่งเทียนข้างหน้า โดยออกแบบมาเพื่อใช้งานร่วมกับ Expert Advisor (EA) ใน MetaTrader 5 โดยเฉพาะ

---

## 🌟 จุดเด่นของระบบ (Key Features)

* **Scale-Invariant & Stationary 100%:** แก้ปัญหาระดับราคาในอดีตกับปัจจุบัน (เช่น ราคาทอง 2,000 vs 4,000) โมเดลทำนายออกมาเป็น **"จำนวนเท่าของ ATR (Volatility Multiples)"** ทำให้โครงสร้างโมเดลใช้งานได้กับทุกยุคราคาโดยไม่มีปัญหา Out-of-Distribution
* **📡 New! 30-Target Probabilistic Market Sensor:**
  * โมเดลไม่สั่ง Buy/Sell สุ่มสี่สุ่มห้า แต่ทำหน้าที่เป็น **"Market Sensor"** ตรวจวัดความน่าจะเป็นของการแตะระยะทาง (Room-to-Run Probability Surface)
  * Output 30 ช่อง Matrix: 2 ทิศทาง (`UP`/`DOWN`) × 5 ระยะ (`0.5, 1.0, 1.5, 2.0, 2.5 ATR`) × 3 กรอบเวลา (`30, 60, 90` นาที)
  * แสดง ASCII Probability Matrix แบบ Real-time บนกราฟ MT5 พร้อมตรวจจับ Probability Skew และบันทึก Log ลง CSV อัตโนมัติ
* **Dual Output Architecture (Regression Baseline):**
  * `pred_upside_atr`: คาดการณ์ระยะทางสูงสุดที่ราคาจะวิ่งขึ้นได้กี่เท่าของ ATR (Max Upside)
  * `pred_downside_atr`: คาดการณ์ระยะทางสูงสุดที่ราคาจะย่อตัวลงได้ลึกสุดกี่เท่าของ ATR (Max Downside)
* **Native ONNX Support for MetaTrader 5:**
  * โมเดลถูกแปลงเป็นไฟล์ `.onnx` (Opset 13, IR Version 8) ที่รันได้โดยตรงบน MT5 Build 6063+ ผ่านฟังก์ชัน `OnnxRun()`
  * **ไม่ต้องเปิด Python Server, ไม่ใช้ WebRequest, ไม่ต้องพึ่ง DLLs**
  * รันคำนวณในระดับ Microseconds (Zero Latency) บนกราฟสด

---

## 📁 โครงสร้างโปรเจกต์ (Project Structure)

```text
CFD-Trading-ML/
├── models/                         # ไฟล์โมเดลที่ผ่านการเทรน
│   ├── xauusd_sensor_30heads.onnx  # 📡 30-Head Neural Market Sensor (MT5 Ready)
│   ├── market_sensor_summary.json  # สรุปผล Metrics และ Monotonicity ของ Sensor
│   ├── xauusd_upside.onnx          # Native MT5 ONNX model (Upside Regression)
│   ├── xauusd_downside.onnx        # Native MT5 ONNX model (Downside Regression)
│   └── training_summary.json       # สรุปผลการเทรน regression baseline
├── mql5/                           # โค้ด MQL5 พร้อมใช้ใน MetaTrader 5
│   ├── Include/
│   │   ├── XAUUSD_Sensor.mqh       # 📡 Sensor Class (30-head parser, Dashboard, Monotonicity Check)
│   │   └── XAUUSD_ML.mqh           # Regression Class สำหรับดึง Features และรัน ONNX
│   ├── Experts/
│   │   ├── XAUUSD_Market_Sensor_EA.mq5       # 📡 EA แสดง Dashboard 30 ช่อง & บันทึก CSV Log
│   │   ├── Sample_XAUUSD_ML_EA.mq5          # ตัวอย่าง EA แบบมาตรฐาน (พร้อม #property tester_file)
│   │   └── Sample_XAUUSD_ML_EA_Embedded.mq5 # ตัวอย่าง EA แบบฝังโมเดลลง .ex5 ในตัว (Standalone)
│   └── Files/
│       ├── xauusd_sensor_30heads.onnx        # 📡 ไฟล์โมเดลวางที่ MQL5\Files\
│       ├── xauusd_upside.onnx
│       └── xauusd_downside.onnx
├── notebooks/                      # Jupyter Notebook สำหรับทดลองและเทรนบน Google Colab
│   ├── train_market_sensor_colab.ipynb       # 📡 Notebook เทรน Market Sensor 30-Target
│   └── train_xauusd_colab.ipynb
├── scripts/                        # สคริปต์อัตโนมัติ
│   ├── pipeline_market_sensor.py   # 📡 Data pipeline (22 Features, 30 Targets, 90-bar purge)
│   ├── train_market_sensor.py      # 📡 Stage 1, 2, 3 + ONNX Multi-Head Exporter
│   └── convert_to_onnx.py
├── docs/
│   ├── MARKET_SENSOR_RESEARCH_GUIDE.md  # 📡 เอกสารวิจัยและสูตรคณิตศาสตร์ Market Sensor
│   └── ML_XAUUSD_SYSTEM_GUIDE.md        # เอกสารคู่มือระบบฉบับละเอียด
├── .gitignore
└── README.md
```

---

## ⚡ วิธีนำไปใช้งานกับ MetaTrader 5 (Market Sensor EA)

1. ใน MT5 กดเมนู **File** -> **Open Data Folder**
2. คัดลอกโฟลเดอร์ใน `mql5/`:
   * `mql5/Include/XAUUSD_Sensor.mqh` -> วางที่ `MQL5\Include\`
   * `mql5/Files/xauusd_sensor_30heads.onnx` -> วางที่ `MQL5\Files\`
   * `mql5/Experts/XAUUSD_Market_Sensor_EA.mq5` -> วางที่ `MQL5\Experts\`
3. เปิด MetaEditor กด **Compile** ไฟล์ `XAUUSD_Market_Sensor_EA.mq5`
4. ลาก EA ลงบนกราฟ **XAUUSD Timeframe M1**:
   * หน้าจอจะแสดงตาราง Probability Matrix 30 ช่องสดทันที
   * ข้อมูลความน่าจะเป็นและ Skew จะถูกบันทึกลง `MQL5\Files\XAUUSD_Sensor_Log.csv` ทุกๆ แท่งเทียน M1

---

## 📊 ผลการทดสอบ (Market Sensor Test Results)

* **Train Set:** 2020.01 – 2023.12 (Purged 90 bars)
* **Validation Set:** 2024.01 – 2024.12
* **Development Out-of-Sample:** 2025.01 – 2025.12
* **🔒 2026 Blind Out-of-Sample:** ถูกล็อคไว้ ไม่ผ่านการแตะต้องใดๆ ทั้งสิ้น
* **Monotonicity Integrity (Stage 3 Multi-Head Neural Sensor):**
  * Distance Monotonicity Violation: **0.10%** (ถูกต้องตามกฎกายภาพ 99.90%)
  * Horizon Monotonicity Violation: **0.34%** (ถูกต้องตามกฎกายภาพ 99.66%)

