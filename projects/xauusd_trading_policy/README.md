# XAUUSD Trading Policy & Position Management ML (M1)

โมเดล Autonomous Closed-Loop Trading Policy สำหรับเทรดทองคำ (XAUUSD) บนกราฟ M1

## สรุปภาพรวม
- **การตัดสินใจ (7 Actions):** `HOLD`, `OPEN_LONG`, `OPEN_SHORT`, `ADD`, `REDUCE`, `CLOSE`, `REVERSE`
- **ฟีเจอร์ (40 ตัว):** 31 Market Features (ไร้ราคา Close ดิบ เป็น Relative Space) + 9 Position Features (ทิศทาง, กำไรขาดทุนสะสม, เวลาที่ถือ)
- **Data Hygiene:** Train (2020-2024), Val (2025), **2026 LOCKED**
- **สถาปัตยกรรม:** Deep Multi-Head Policy Network (PyTorch / GPU) -> Export MT5 ONNX

## โครงสร้างโปรเจกต์
- `notebooks/Train_XAUUSD_Trading_Policy_Colab.ipynb`: Notebook สำหรับรันบน Google Colab
- `scripts/`: สคริปต์สกัดฟีเจอร์, Teacher Simulator, ตัวเทรน PyTorch, Backtest, และ Colab runner
- `models/`: โมเดล `xauusd_trading_policy.onnx`, `xauusd_trading_policy.onnx.data`, `policy_metadata.json`
- `mql5/`: EA `XAUUSD_Trading_Policy_EA_Standalone.mq5` พร้อม dashboard และตัวคำนวณฟีเจอร์ในตัว
- `docs/`: กราฟ Backtest ปี 2025 และเอกสารสูตรทางคณิตศาสตร์
