# 🧠 CFD Quant Trading & Machine Learning Research Hub

[![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/BlamzKunG/XAUUSD-Trading-Policy-ML/blob/main/notebooks/Train_XAUUSD_Trading_Policy_Colab.ipynb)
![License](https://img.shields.io/badge/License-MIT-blue.svg)
![Market](https://img.shields.io/badge/Market-CFD%20Quant%20Trading-purple.svg)
![Assets](https://img.shields.io/badge/Assets-Multi--Asset%20(Gold%20%7C%20FX%20%7C%20Indices%20%7C%20Crypto)-gold.svg)
![Runtime](https://img.shields.io/badge/Engines-PyTorch%20%7C%20LightGBM%20%7C%20ONNX%20%7C%20MT5-green.svg)

---

## 🎯 วิสัยทัศน์และเป้าหมายของ Repository (Repository Purpose)

Repository นี้เป็น **ศูนย์วิจัยและพัฒนาโมเดล Machine Learning สำหรับ Quantitative Trading ในตลาด CFD (Contracts for Difference)** โดยเฉพาะ 

คลังโค้ดนี้ถูกออกแบบให้เป็น **Modular Framework** ที่ **ไม่จำกัดเฉพาะสินทรัพย์ใดสินทรัพย์หนึ่ง และไม่จำกัดประเภทของโจทย์ ML**:

- 🌐 **Multi-Asset CFD Support:** รองรับสินทรัพย์หลากหลาย ไม่ว่าจะเป็น Commodities (**XAUUSD**, XAGUSD, USOIL), Forex (**EURUSD**, GBPUSD, USDJPY), Equity Indices (**US30**, NAS100, SPX500), หรือ Crypto CFDs (**BTCUSD**, ETHUSD)
- 🧪 **Multi-Task ML Paradigms:** 
  - **Policy & Decision Networks:** โมเดล Trading Policy สำหรับตัดสินใจเข้าออเดอร์ บริหารพอร์ต และจัดการคำสั่งแบบ Closed-Loop
  - **Market Regime & Volatility Modeling:** โมเดลจำแนกสภาวะตลาด คาดการณ์ Volatility และตรวจจับการเบรกเอาต์
  - **Excursion & Probability Estimators:** โมเดลประเมินโอกาสแตะระดับเป้าหมายหรือความเสี่ยง Drawdown
  - **Dynamic Position & Risk Sizing:** โมเดลปรับขนาด Lot และวางระยะ Stop Loss / Take Profit ตามความผันผวน
- ⚡ **Production-Grade Execution:** เชื่อมต่อการเทรนบน Cloud GPU (Google Colab / Colab CLI) สู่การรันจริงบน **MetaTrader 5 (MT5)** แบบ Low-Latency ผ่าน **ONNX Runtime**

---

## 🏛️ สถาปัตยกรรมแกนกลางของระบบ (Core Quant Framework)

```
                            Raw CFD Tick / M1 Bar Stream
                                         │
                                         ▼
                     Stationary Feature Engineering (Scale-Free)
                     - Multi-Horizon Log Returns: ln(Pt / Pt-k)
                     - Volatility Normalization: ΔP / ATR
                     - Microstructure: Body, Wicks, Range / ATR
                     - Local Distribution: Rolling Z-Scores, Pct Rank
                                         │
                     ┌───────────────────┴───────────────────┐
                     ▼                                       ▼
             Market State Vector                    Position State Vector
            [31 Scale-Free Feats]                   [9 Relative State Feats]
                     │                                       │
                     └───────────────────┬───────────────────┘
                                         ▼
                                State Input Tensor (40D)
                                         │
                                         ▼
                   Deep Multi-Head Policy Model / ML Backbone
                                         │
                    ┌────────────────────┼────────────────────┐
                    ▼                    ▼                    ▼
              ACTION HEAD            SIZE HEAD           ORDER HEAD
              Discrete Acts       Risk Fraction       Dynamic Distances
            (HOLD, BUY, SELL,      [0.1 .. 1.0]       (SL & TP in ATR)
            ADD, REDUCE, CLOSE,
                  REVERSE)
                    │                    │                    │
                    └────────────────────┼────────────────────┘
                                         ▼
                        Closed-Loop Simulation / MetaTrader 5 EA
                                         │
                                         ▼
                             Next Bar Position State
                                         │
                                         └──────► Feedback Loop
```

---

## 🚀 โครงการที่กำลังพัฒนาและใช้งานใน Hub (Active Projects)

### 📌 Project 1 (Flagship): XAUUSD Autonomous Trading Policy & Position Management
โมเดล Machine Learning แบบ **Autonomous Closed-Loop Trading Policy** สำหรับเทรดทองคำ (XAUUSD) บนไทม์เฟรม M1 โดยโมเดลรับบทบาทเป็นผู้จัดการพอร์ตเต็มรูปแบบ

- **แก้ปัญหา Price Scale ($1,500 vs $5,000):** ตัดขาดจากการใช้ราคา Close ดิบ ทุกอย่างถูกแปลงเป็น Relative Stationary Space
- **Closed-Loop State-Action Framework:** นำ Market Features (31 ตัว) มารวมกับ Position Features (9 ตัว) ทำให้โมเดล "รู้ว่าตอนนี้ถือไม้ฝั่งไหน กำไร/ขาดทุนเท่าไร และควรจัดการต่ออย่างไร"
- **Counterfactual Teacher Simulator:** จำลองการเทรดล่วงหน้า 60 แท่งในทุกสถานะสมมุติ (Flat, Long กำไร/ขาดทุน, Short กำไร/ขาดทุน) หักลบ Spread, Slippage, Commission และลงโทษ Drawdown เพื่อสร้าง Action Targets
- **7 Discrete Actions:** `HOLD` (0), `OPEN_LONG` (1), `OPEN_SHORT` (2), `ADD` (3), `REDUCE` (4), `CLOSE` (5), `REVERSE` (6)
- **Data Hygiene:** Train (2020–2024), Validation (2025), **2026 LOCKED** (ห้ามแตะระหว่างเทรน)
- **MT5 Standalone EA:** มี EA ภาษา MQL5 ตัวเต็มที่คำนวณ 31 Features ในตัว และโหลดโมเดล ONNX มาประมวลผลบนกราฟจริงแบบ Real-time

---

## 🛠️ แผนงานขยายผลสู่สินทรัพย์และโมเดลอื่น (Roadmap for Other CFDs)

| Asset Class | สินทรัพย์เป้าหมาย | ประเภทโมเดล (ML Architecture) | วัตถุประสงค์ (Target Objective) |
|---|---|---|---|
| **Precious Metals** | XAUUSD, XAGUSD | Deep Multi-Head Policy Network | บริหาร Position แบบไดนามิก (เปิด/สเกลอิน/ลดความเสี่ยง/กลับทิศ) |
| **Major Forex** | EURUSD, GBPUSD, USDJPY | Temporal Convolutional Network (TCN) | คาดการณ์ทิศทางและ Volatility Regime ข้ามช่วงข่าวสำคัญ |
| **Stock Indices** | US30, NAS100, SPX500 | Multi-Horizon LightGBM Ensemble | ตรวจจับ Momentum Exhaustion และ Mean Reversion รอบเปิดตลาด US |
| **Energy** | USOIL, UKOIL | Transformer / Self-Attention Policy | สกัดแนวโน้มระยะสั้นที่ได้รับอิทธิพลจาก Breakout ของช่วงราคา |
| **Crypto CFDs** | BTCUSD, ETHUSD | Deep Reinforcement Learning (PPO/SAC) | วาง Trailing SL/TP และ Rebalancing อัตโนมัติตลอด 24/7 |

---

## 💻 วิธีการเทรนโมเดล (Training Workflows)

### ช่องทางที่ 1: รันบน Google Colab ด้วยปุ่มคลิกเดียว (1-Click Browser)
[![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/BlamzKunG/XAUUSD-Trading-Policy-ML/blob/main/notebooks/Train_XAUUSD_Trading_Policy_Colab.ipynb)

1. คลิกที่ปุ่ม **"Open In Colab"** ด้านบน
2. เลือก Runtime เป็น **T4 GPU** (`Runtime` -> `Change runtime type` -> `T4 GPU`)
3. อัปโหลดไฟล์ CSV ข้อมูล หรือ Mount ผ่าน Google Drive
4. กด **`Ctrl + F9` (Run all)** เพื่อรันตั้งแต่ต้นจนจบ: สกัดฟีเจอร์ $\to$ สร้าง Labels $\to$ เทรน PyTorch GPU $\to$ ทำ Backtest $\to$ Export เป็น MT5 ONNX

### ช่องทางที่ 2: รันผ่าน Google Colab CLI (Automated Terminal CLI)
สำหรับผู้ใช้งานสาย Automation ที่ตั้งค่า `colab` CLI ไว้แล้ว:
```bash
# 1. สร้าง Session บน Colab พร้อม T4 GPU
colab new -s quant-train --gpu T4

# 2. อัปโหลดโค้ดและชุดข้อมูล
colab upload -s quant-train /path/to/data.csv.gz /content/data.csv.gz

# 3. สั่งเทรนผ่าน Background Runner
colab exec -s quant-train --timeout 3600 -f scripts/run_colab_training.py

# 4. สั่งปิด Session เมื่อเสร็จสิ้นเพื่อประหยัดโควต้า
colab stop -s quant-train
```

---

## 📈 วิธีการนำโมเดลไปใช้งานบน MetaTrader 5 (MT5 ONNX Deployment)

1. **คัดลอกไฟล์โมเดล ONNX:**
   นำไฟล์ในโฟลเดอร์ `models/` ไปวางที่โฟลเดอร์ข้อมูลของ MT5:
   ```
   [MT5 Data Folder]/MQL5/Files/
   ├── xauusd_trading_policy.onnx
   ├── xauusd_trading_policy.onnx.data
   └── policy_metadata.json
   ```
2. **ติดตั้ง Expert Advisor:**
   นำไฟล์ EA จาก `mql5/Experts/` ไปวางที่:
   ```
   [MT5 Data Folder]/MQL5/Experts/
   └── XAUUSD_Trading_Policy_EA_Standalone.mq5
   ```
3. **คอมไพล์ใน MetaEditor:**
   เปิด MetaEditor 5 ดับเบิ้ลคลิกไฟล์ EA แล้วกด **Compile (F7)** โค้ดเป็น Standalone 100% ปราศจากปัญหา Include ภายนอก
4. **เปิดการทำงานบนกราฟ:**
   เปิดกราฟสินทรัพย์ที่ต้องการ (เช่น XAUUSD M1) ลาก EA ลงบนกราฟ และติ๊กเลือก **"Allow Algo Trading"**

---

## 📁 โครงสร้างโปรเจกต์ (Repository Directory Layout)

```
├── README.md                                          <- เอกสารภาพรวมของ Quant Trading ML Hub
├── requirements.txt                                   <- รายการ Python dependencies (PyTorch, ONNX, LightGBM ฯลฯ)
├── notebooks/
│   └── Train_XAUUSD_Trading_Policy_Colab.ipynb        <- Colab Notebook สำหรับเทรนและทดสอบโมเดล
├── scripts/
│   ├── features_policy.py                             <- Pipeline สกัดฟีเจอร์ไร้สเกลราคา (31 Market + 9 Position)
│   ├── counterfactual_simulator.py                    <- Counterfactual Teacher Simulator สำหรับสร้าง Action Labels
│   ├── train_policy_suite.py                          <- สคริปต์เทรน PyTorch Multi-Head Policy & ONNX Exporter
│   ├── backtest_policy_evaluator.py                   <- Closed-Loop Event-Driven Backtester
│   └── run_colab_training.py                          <- End-to-End Runner สำหรับสั่งงานผ่าน Colab CLI
├── models/
│   ├── xauusd_trading_policy.onnx                     <- โมเดลโครงข่ายประสาทเทียม ONNX พร้อมใช้งานบน MT5
│   ├── xauusd_trading_policy.onnx.data                <- พารามิเตอร์ Weights & Biases ของโมเดล
│   └── policy_metadata.json                           <- สรุปฟีเจอร์ Mean/Std และ Configuration ทั้งหมด
├── mql5/
│   ├── Include/
│   │   └── XAUUSD_Policy_Agent.mqh                    <- คลาส MQL5 สกัดฟีเจอร์และรัน OnnxRun ในตัว
│   └── Experts/
│       └── XAUUSD_Trading_Policy_EA_Standalone.mq5    <- Standalone MT5 Expert Advisor พร้อม On-Chart Dashboard
└── docs/
    ├── ARCHITECTURE.md                                <- เอกสารการคำนวณทางคณิตศาสตร์และโครงสร้าง State-Action
    └── equity_curve_2025.png                          <- ภาพกราฟผลการทดสอบ Closed-Loop Backtest ปี 2025
```

---

## ⚖️ License
MIT License. Developed & Maintained by **BlamzKunG**.
