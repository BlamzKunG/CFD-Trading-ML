# 📈 CFD Machine Learning Projects Collection

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

คลังรวมโปรเจกต์ Machine Learning สำหรับการเทรด CFD (Quant Trading) รวบรวมงานทดลอง, สคริปต์สกัดฟีเจอร์, โมเดล ONNX สำเร็จรูป และ EA สำหรับ MetaTrader 5 โดยแบ่งออกเป็นแต่ละโปรเจกต์อย่างเป็นระเบียบ

---

## 📁 รายการโปรเจกต์ในคลัง (Projects Collection)

### 1. [XAUUSD Trading Policy & Position Management](projects/xauusd_trading_policy/)
โมเดล Closed-Loop Trading Policy สำหรับตัดสินใจเปิด/ปิด และจัดการออเดอร์ทองคำ (XAUUSD M1)
- **แนวคิด:** โมเดลไม่เพียงแค่บอกสัญญาณ Buy/Sell แต่ทำหน้าที่เป็น Policy Agent ตัดสินใจเลือกระหว่าง `HOLD`, `OPEN_LONG`, `OPEN_SHORT`, `ADD` (สเกลอิน), `REDUCE` (ลดเสี่ยง 50%), `CLOSE`, `REVERSE` พร้อมปรับ Lot Size และ SL/TP แบบไดนามิก
- **ฟีเจอร์:** ใช้ 31 Market Features (ไร้ราคา Close ดิบ แปลงเป็น Relative Space เช่น Log Returns, ATR Ratio, Candlestick Structure, Z-Scores) + 9 Position Features (รวม 40 ฟีเจอร์)
- **Data Hygiene:** Train 2020–2024 | Validation 2025 | **2026 LOCKED**
- **ไฟล์สำคัญ:**
  - โน้ตบุ๊ก Colab: [`projects/xauusd_trading_policy/notebooks/Train_XAUUSD_Trading_Policy_Colab.ipynb`](projects/xauusd_trading_policy/notebooks/Train_XAUUSD_Trading_Policy_Colab.ipynb)
  - โมเดล ONNX: [`projects/xauusd_trading_policy/models/xauusd_trading_policy.onnx`](projects/xauusd_trading_policy/models/xauusd_trading_policy.onnx)
  - EA บน MT5: [`projects/xauusd_trading_policy/mql5/Experts/XAUUSD_Trading_Policy_EA_Standalone.mq5`](projects/xauusd_trading_policy/mql5/Experts/XAUUSD_Trading_Policy_EA_Standalone.mq5)

---

### 2. [XAUUSD Market Sensor & Room-to-Run Excursion](projects/xauusd_market_sensor/)
โมเดล Machine Learning วัดสภาวะตลาด (Market Sensor) ประเมิน Room-to-Run และความน่าจะเป็นในการแตะระยะเป้าหมายของทองคำ (XAUUSD M1)
- **แนวคิด:** โมเดลไม่ได้ชี้นำว่าต้อง Buy หรือ Sell แต่ตอบคำถามว่า "จากสภาพตลาดตอนนี้ ราคามีโอกาสแตะระยะเป้าหมาย D ขึ้นหรือลง ในอีก H แท่งข้างหน้ามากแค่ไหน?"
- **สถาปัตยกรรม:** Multi-Head LightGBM Classifier (30 Heads: 2 ทิศทาง $\times$ 5 ระยะ ATR $\times$ 3 Horizons 30/60/90 แท่ง)
- **ไฟล์สำคัญ:**
  - โน้ตบุ๊ก Colab: [`projects/xauusd_market_sensor/notebooks/train_market_sensor_colab.ipynb`](projects/xauusd_market_sensor/notebooks/train_market_sensor_colab.ipynb)
  - โมเดล ONNX: [`projects/xauusd_market_sensor/models/xauusd_sensor_30heads.onnx`](projects/xauusd_market_sensor/models/xauusd_sensor_30heads.onnx)
  - EA บน MT5: [`projects/xauusd_market_sensor/mql5/Experts/XAUUSD_Market_Sensor_EA_Standalone.mq5`](projects/xauusd_market_sensor/mql5/Experts/XAUUSD_Market_Sensor_EA_Standalone.mq5)

---

## 🗂️ โครงสร้างของ Repository

```
├── LICENSE                                    <- MIT License
├── README.md                                  <- เอกสารสรุปภาพรวมของคลังโปรเจกต์
├── requirements.txt                           <- Python dependencies
└── projects/
    ├── xauusd_trading_policy/                 <- โปรเจกต์ 1: Autonomous Trading Policy
    │   ├── notebooks/                         <- Colab Notebook
    │   ├── scripts/                           <- Feature, Simulator, Trainer, Backtester
    │   ├── models/                            <- โมเดล ONNX + Metadata
    │   ├── mql5/                              <- Standalone EA + Include
    │   └── docs/                              <- ผล Backtest และสูตรคำนวณ
    │
    └── xauusd_market_sensor/                  <- โปรเจกต์ 2: Market Sensor Excursion
        ├── notebooks/                         <- Colab Notebooks
        ├── scripts/                           <- Pipeline, LightGBM Trainer, ONNX Converter
        ├── models/                            <- 30-Head ONNX Models + Summaries
        ├── mql5/                              <- Dashboard EA + Standalone EA
        └── docs/                              <- คู่มือการวิจัยและคู่มือระบบ
```

---

## ⚡ โน้ตการใช้งานคร่าวๆ (Quick Reference)

### การนำโมเดลไปใช้งานบน MetaTrader 5
1. เลือกโปรเจกต์ที่ต้องการใช้งาน
2. คัดลอกไฟล์โมเดล `.onnx` (และ `.data` ถ้ามี) จากโฟลเดอร์ `models/` ไปวางที่ `MQL5/Files/`
3. คัดลอกไฟล์ EA จากโฟลเดอร์ `mql5/Experts/` ไปวางที่ `MQL5/Experts/`
4. เปิด MetaEditor กด **Compile (F7)** แล้วลาก EA ลงบนกราฟ XAUUSD M1 ได้ทันที

---

## ⚖️ License
โปรเจกต์ทั้งหมดในคลังนี้อยู่ภายใต้สัญญาอนุญาต [MIT License](LICENSE)
