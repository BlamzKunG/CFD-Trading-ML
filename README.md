# 📈 CFD Machine Learning Projects Collection

คลังรวมโปรเจกต์ Machine Learning สำหรับการเทรด CFD (Quant Trading) รวบรวมงานทดลอง, สคริปต์ทำฟีเจอร์, ตัวจำลองกลยุทธ์, โมเดลสำเร็จรูป (ONNX) และ Expert Advisor (MetaTrader 5) จัดเก็บแยกเป็นคอลเลกชันตามแต่ละโปรเจกต์

---

## 📁 โปรเจกต์ในคลัง (Projects Collection)

### 1. XAUUSD Trading Policy & Position Management (M1)
โมเดล ML สำหรับตัดสินใจเปิด/ปิด และจัดการ Position ทองคำ (XAUUSD) บนกราฟ M1 แบบ Autonomous Policy
- **สิ่งที่โมเดลทำ:** ไม่ใช่แค่บอก Buy/Sell ลอยๆ แต่ตัดสินใจเลือกระหว่าง `HOLD`, `OPEN_LONG`, `OPEN_SHORT`, `ADD` (เพิ่มไม้), `REDUCE` (ลดความเสี่ยง 50%), `CLOSE` (ปิดไม้), `REVERSE` (กลับทิศ) พร้อมคำนวณขนาด Lot และระยะ SL/TP ให้ตามความผันผวน
- **ฟีเจอร์ที่ใช้:** 31 Market Features (ไร้ราคา Close ดิบ แปลงเป็นค่าสัมพัทธ์ เช่น Log Returns, ATR Ratio, Candlestick Wicks, Z-Score) + 9 Position Features (สถานะปัจจุบัน กำไร/ขาดทุนสะสม ระยะเวลาที่ถือ) รวม 40 Features
- **Data Hygiene:** ใช้ข้อมูล 2020–2024 สำหรับ Train, ปี 2025 สำหรับ Validation และล็อคข้อมูลปี 2026 ไว้ห้ามแตะ
- **ไฟล์ของโปรเจกต์นี้:**
  - [notebooks/Train_XAUUSD_Trading_Policy_Colab.ipynb](file:///root/XAUUSD-Trading-Policy-ML/notebooks/Train_XAUUSD_Trading_Policy_Colab.ipynb) - โน้ตบุ๊กสำหรับเปิดเทรนบน Google Colab (GPU T4)
  - [scripts/run_colab_training.py](file:///root/XAUUSD-Trading-Policy-ML/scripts/run_colab_training.py) - สคริปต์รันเทรนอัตโนมัติผ่าน Colab CLI
  - [scripts/features_policy.py](file:///root/XAUUSD-Trading-Policy-ML/scripts/features_policy.py) - สคริปต์สกัด 31 Market + 9 Position Features
  - [scripts/counterfactual_simulator.py](file:///root/XAUUSD-Trading-Policy-ML/scripts/counterfactual_simulator.py) - ระบบจำลองเพื่อสร้าง Target Label แบบหักลบค่าธรรมเนียมและสเปรด
  - [scripts/train_policy_suite.py](file:///root/XAUUSD-Trading-Policy-ML/scripts/train_policy_suite.py) - โครงสร้างโมเดล PyTorch Multi-Head และตัวแปลง ONNX
  - [scripts/backtest_policy_evaluator.py](file:///root/XAUUSD-Trading-Policy-ML/scripts/backtest_policy_evaluator.py) - สคริปต์ทำ Closed-Loop Backtest
  - [models/xauusd_trading_policy.onnx](file:///root/XAUUSD-Trading-Policy-ML/models/xauusd_trading_policy.onnx) - โมเดล ONNX ที่เทรนเสร็จแล้ว
  - [models/policy_metadata.json](file:///root/XAUUSD-Trading-Policy-ML/models/policy_metadata.json) - ค่าสถิติ Mean/Std สำหรับ Normalize
  - [mql5/Experts/XAUUSD_Trading_Policy_EA_Standalone.mq5](file:///root/XAUUSD-Trading-Policy-ML/mql5/Experts/XAUUSD_Trading_Policy_EA_Standalone.mq5) - EA บน MT5 สำหรับรันโมเดลจริง (Standalone 100%)

*(โปรเจกต์ ML อื่นๆ เกี่ยวกับ CFD เช่น คู่เงิน Forex, ดัชนีหุ้น หรือโมเดล Regime/Volatility จะถูกเพิ่มเข้ามาแยกเป็นงานๆ ในคลังนี้)*

---

## 🗂️ โครงสร้างโฟลเดอร์ใน Repo

```
├── notebooks/   # รวม Jupyter Notebook สำหรับรันเทรน
├── scripts/     # รวม Python scripts ทั้งหมด (Feature, Trainer, Backtest, CLI Runner)
├── models/      # เก็บโมเดลที่เทรนเสร็จแล้ว (.onnx, metadata)
├── mql5/        # เก็บ EA และ Include Files สำหรับรันบน MetaTrader 5
└── docs/        # เก็บภาพกราฟผลการทดสอบ และเอกสารประกอบ
```

---

## ⚡ โน้ตการใช้งาน (Quick Notes)

### การเทรนโมเดล
- **เทรนบนเบราว์เซอร์:** กดเปิดไฟล์ในโฟลเดอร์ `notebooks/` บน Google Colab เลือก GPU T4 แล้วกด Run All ได้เลย
- **เทรนผ่าน Colab CLI:**
  ```bash
  colab new -s my-session --gpu T4
  colab exec -s my-session --timeout 3600 -f scripts/run_colab_training.py
  colab stop -s my-session
  ```

### การนำโมเดลไปรันใน MetaTrader 5
1. คัดลอกไฟล์ใน `models/` (`.onnx` และ `.onnx.data`) ไปไว้ที่โฟลเดอร์ `MQL5/Files/` ของ MT5
2. คัดลอกไฟล์ใน `mql5/Experts/` ไปไว้ที่โฟลเดอร์ `MQL5/Experts/`
3. เปิด MetaEditor กด **Compile (F7)** แล้วนำ EA ไปลากใส่กราฟ (เช่น XAUUSD M1) เปิด Algo Trading ได้ทันที
