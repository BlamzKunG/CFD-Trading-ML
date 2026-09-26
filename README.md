# 🚀 XAUUSD Autonomous Trading Policy & Position Management ML

[![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/BlamzKunG/XAUUSD-Trading-Policy-ML/blob/main/notebooks/Train_XAUUSD_Trading_Policy_Colab.ipynb)
![License](https://img.shields.io/badge/License-MIT-blue.svg)
![Target](https://img.shields.io/badge/Asset-XAUUSD%20(Gold)-gold.svg)
![Timeframe](https://img.shields.io/badge/Timeframe-M1-orange.svg)
![Runtime](https://img.shields.io/badge/Engine-PyTorch%20%7C%20ONNX%20%7C%20MetaTrader%205-green.svg)

---

## 📖 สรุปภาพรวมและปรัชญาของระบบ (Core Philosophy)

โมเดล ML ในโปรเจกต์นี้ **ไม่ใช่** ตัวทำนาย Buy/Sell สัญญาณเดี่ยว และ **ไม่มีการใช้ Room-to-Run หรือ Raw Price** แต่เป็น **"Autonomous Trading Policy Agent"** ที่ตัดสินใจและบริหาร Position ของตัวเองตลอดอายุของ Trade:

```
                      Raw M1 OHLC
                           │
                           ▼
          Stationary Feature Transformation (Scale-Free)
                           │
                ┌──────────┴──────────┐
                │                     │
           Market State          Position State
           (31 features)         (9 features)
                │                     │
                └──────────┬──────────┘
                           ▼
                Deep Multi-Head Policy Model
                           │
              ┌────────────┼─────────────┐
              ▼            ▼             ▼
           ACTION      RISK SIZE     ORDER PARAMS
         (7 Classes)  ([0.1..1.0])   (Dynamic SL/TP)
              │            │             │
              └────────────┴─────────────┘
                           ▼
               Closed-Loop Execution Engine
                           │
                           ▼
                  Updated Position State
                           │
                           └──────► Loop to Next M1 Bar
```

---

## 🌟 จุดเด่นสำคัญ (Key Innovations)

### 1. แก้ปัญหา 1,500 vs 5,000 Price Scale อย่างเด็ดขาด (Zero Raw Price Inputs)
- โมเดลไม่เห็นราคา Close ดิบ (เช่น Close = 1518 หรือ Close = 4339) เพราะราคาที่ต่างกัน 3 เท่าทำให้โมเดล Tabular หรือ Deep Net เสียความหมาย
- ทุก Feature ถูกแปลงให้อยู่ใน **Relative, Stationary Space**:
  - **Multi-Horizon Log Returns**: $r_k = \ln(P_t / P_{t-k})$ ($k \in [1, 3, 5, 15, 30, 60]$)
  - **Volatility Normalization**: $\Delta P / \text{ATR}_{14}$
  - **Candlestick Microstructure**: $\text{Body}/\text{ATR}$, $\text{Range}/\text{ATR}$, Upper/Lower Wick ratios, Relative Close location in bar $[0, 1]$
  - **Local Price Distribution**: Rolling Z-scores (20 & 100 bars), Percentile rank (60 bars)
  - **Cyclic Time**: Sine/Cosine transforms ของชั่วโมงและวันในสัปดาห์

### 2. Closed-Loop State-Action Framework (40 Input Features)
- **Market State (31 Features)**: วัดสภาวะตลาด โมเมนตัม ความผันผวน และโครงสร้างแท่งเทียน
- **Position State (9 Features)**:
  - ทิศทางปัจจุบัน: `pos_dir` (-1 Short, 0 Flat, +1 Long)
  - สัดส่วนความเสี่ยง: `pos_size_frac`
  - ระยะห่างจากจุดเข้า: `entry_dist_atr`
  - กำไร/ขาดทุนทางบัญชี: `unrealized_pnl_atr`
  - ระยะเวลาที่ถือสถานะ: `time_in_pos_norm`
  - ระยะห่างถึง SL และ TP: `dist_to_sl_atr`, `dist_to_tp_atr`
  - Max Drawdown ที่เคยเจอ: `max_drawdown_atr`
  - ระยะเวลาตั้งแต่การกระทำล่าสุด: `bars_since_action_norm`

### 3. Counterfactual Teacher Simulator (Dynamic Action Labeling)
- ป้องกัน Lookahead Bias และปัญหาระบบหลับ
- จำลองผลลัพธ์ล่วงหน้าในทุก Timestamp สำหรับสถานะสมมุติ (Flat, Long กำไร, Long ขาดทุน, Short กำไร, Short ขาดทุน)
- คำนวณ Utility ที่หักลบ Spread, Slippage, Commission และลงโทษ Drawdown
- คัดเลือก Action ที่ให้ Utility สูงสุดเป็น Target label $a^*$ สำหรับการเทรน

### 4. กฎเหล็ก Data Hygiene (2026 LOCKED)
- **Train Set**: 2020.01.02 – 2024.12.31 (5 ปีเต็ม)
- **Validation Set**: 2025.01.01 – 2025.12.30 (Out-of-sample สำหรับจูนโมเดล)
- **Blind Test**: **2026 ถูกล็อคห้ามแตะเด็ดขาด (LOCKED)** เพื่อใช้ทดสอบความสามารถจริงในอนาคต

---

## 🎯 Action Space (7 Discrete Actions)

| Action ID | Action Name | ความหมาย |
|---|---|---|
| `0` | **HOLD** | ไม่เปิดสถานะเพิ่ม / ถือสถานะเดิมต่อไป |
| `1` | **OPEN_LONG** | เปิดสถานะ Buy เมื่อพอร์ตว่าง |
| `2` | **OPEN_SHORT** | เปิดสถานะ Sell เมื่อพอร์ตว่าง |
| `3` | **ADD** | Scale-in เพิ่มไม้เมื่อแนวโน้มวิ่งแรงในทิศทางที่ถูกต้อง |
| `4` | **REDUCE** | Scale-out ลดความเสี่ยงหรือล็อคกำไรบางส่วน (50%) เมื่อเริ่มชะลอตัว |
| `5` | **CLOSE** | ปิดสถานะทันทีเมื่อสภาวะตลาดเปลี่ยนทิศ |
| `6` | **REVERSE** | ปิดสถานะเดิมและสลับทิศทางทันที |

---

## 🚀 วิธีการเทรนบน Google Colab (Step-by-Step Guide)

คลิกที่ปุ่มด้านล่างเพื่อเปิด Notebook บน Google Colab ได้ทันที:

[![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/BlamzKunG/XAUUSD-Trading-Policy-ML/blob/main/notebooks/Train_XAUUSD_Trading_Policy_Colab.ipynb)

### ขั้นตอนการรันบน Google Colab:
1. **เปิด Notebook**: กดปุ่ม **"Open In Colab"** ด้านบน
2. **เปิด GPU Runtime**:
   - ไปที่เมนู `Runtime` -> `Change runtime type` -> เลือก **T4 GPU** -> กด `Save`
3. **โหลด Dataset**:
   - นำไฟล์ `XAUUSD.iux_M1_20200102_to_20251230.csv` อัปโหลดใส่ใน Google Drive หรืออัปโหลดผ่าน Widget ในเซลล์ที่ 3
4. **รันเซลล์ทั้งหมด (Run All)**:
   - กด `Runtime` -> `Run all` (Ctrl + F9)
   - โมเดลจะทำการสกัด 31 Market Features
   - ทำ Counterfactual Simulation เพื่อสร้างชุดข้อมูล 40 Features
   - เทรน Multi-Head Neural Network ด้วย PyTorch (GPU)
   - รัน Closed-Loop Backtest บนข้อมูลปี 2025 Out-of-Sample และพล็อตกราฟ Equity Curve
   - Export โมเดลออกมาเป็น `models/xauusd_trading_policy.onnx` (Opset 13, IR 8)
   - Commit & Push กลับเข้าสู่ GitHub ให้อัตโนมัติ!

---

## 🖥️ วิธีการติดตั้งบน MetaTrader 5 (MT5 EA Setup)

1. **ดาวน์โหลดไฟล์ EA**:
   - คัดลอก `mql5/Experts/XAUUSD_Trading_Policy_EA_Standalone.mq5` ไปวางในโฟลเดอร์ `MQL5/Experts/` ของ MT5
2. **คัดลอกโมเดล ONNX**:
   - นำไฟล์โมเดล `models/xauusd_trading_policy.onnx` ไปวางในโฟลเดอร์ `MQL5/Files/`
3. **คอมไพล์ใน MetaEditor**:
   - เปิด MetaEditor 5 -> ดับเบิ้ลคลิกไฟล์ `XAUUSD_Trading_Policy_EA_Standalone.mq5` -> กด `Compile` (F7)
   - โค้ดถูกออกแบบให้ Standalone 100% ปราศจากปัญหา Include ภายนอก
4. **Attach เข้ากับกราฟ**:
   - เปิดกราฟ **XAUUSD บน Timeframe M1**
   - ลาก EA ลงบนกราฟ ติ๊กเลือก `"Allow Algo Trading"`
   - ระบบจะเริ่มคำนวณ 31 Market Features แบบ Real-time และสั่งการเทรดอัตโนมัติ

---

## 📁 โครงสร้างโปรเจกต์ (Project Tree)

```
XAUUSD-Trading-Policy-ML/
├── README.md                                          <- รายละเอียดโปรเจกต์และวิธีใช้งาน
├── requirements.txt                                   <- Python dependencies
├── notebooks/
│   └── Train_XAUUSD_Trading_Policy_Colab.ipynb        <- Jupyter Notebook สำหรับเทรนบน Colab
├── scripts/
│   ├── features_policy.py                             <- Scale-Invariant Feature Pipeline (31 Market + 9 Pos)
│   ├── counterfactual_simulator.py                    <- Counterfactual Teacher Simulator
│   ├── train_policy_suite.py                          <- Multi-Head PyTorch & LightGBM Trainer & ONNX Exporter
│   └── backtest_policy_evaluator.py                   <- Closed-Loop Event-Driven Backtester
├── models/
│   ├── xauusd_trading_policy.onnx                     <- ONNX Model สำหรับ MT5 Build 6063+
│   └── policy_metadata.json                           <- Model Configuration & Normalization Stats
├── mql5/
│   ├── Include/
│   │   └── XAUUSD_Policy_Agent.mqh                    <- Policy Agent Include Class
│   └── Experts/
│       └── XAUUSD_Trading_Policy_EA_Standalone.mq5    <- Standalone MT5 Expert Advisor
└── docs/
    └── ARCHITECTURE.md                                <- เอกสารวิเคราะห์เชิงลึกของระบบ
```

---

## ⚖️ License
MIT License. Developed by **BlamzKunG**.
