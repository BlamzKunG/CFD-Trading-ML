# 🔬 Research Report: Principles of Robust Machine Learning in Quantitative CFD Trading

> **Author:** BlamzKunG Research  
> **Topic:** "การ Train โมเดลที่ดีสำหรับ Financial & Quant Trading ควรเป็นอย่างไร"  
> **Scope:** CFD Market (XAUUSD, FX, Indices, Crypto) | M1 Timeframe | Multi-Model Architecture Suite

---

## 1. ปัญหาพื้นฐานของ Financial Machine Learning (Why Traditional ML Fails in Trading)

การนำ Machine Learning มาใช้ในตลาดการเงินมีความแตกต่างจากการทำ ML บนรูปภาพหรือข้อความ (CV/NLP) อย่างสิ้นเชิง เนื่องจากลักษณะเฉพาะของข้อมูลตลาดการเงิน 4 ประการ:

```
┌────────────────────────────────────────────────────────────────────────┐
│             4 ความท้าทายหลักของ Financial Time-Series ML               │
├────────────────────────────────┬───────────────────────────────────────┤
│ 1. Low Signal-to-Noise Ratio   │ สัญญาณแท้จริงมีน้อยมาก ตลาดเต็มไปด้วย  │
│    (SNR ต่ำมาก)                │ Noise และ Random Walk                 │
├────────────────────────────────┼───────────────────────────────────────┤
│ 2. Non-Stationarity            │ การกระจายตัว (Mean, Variance) เปลี่ยน  │
│    (สภาวะตลาดเปลี่ยนตลอดเวลา)  │ แปลงข้าม Regime (ปัญหา 1,500 vs 5,000)│
├────────────────────────────────┼───────────────────────────────────────┤
│ 3. Non-I.I.D & Auto-correlation│ ข้อมูลแต่ละแท่งไม่เป็นอิสระต่อกัน     │
│    (ข้อมูลมีความเกี่ยวเนื่อง)  │ การสุ่ม Shuffle ข้อมูลทำให้ Overfit   │
├────────────────────────────────┼───────────────────────────────────────┤
│ 4. Transaction Friction        │ การทำนายถูกทางแต่เทรดถี่เกินไป จะแพ้   │
│    (ต้นทุนค่าสเปรดและคอมมิชชัน)│ ค่า Spread, Slippage, และ Fee ในที่สุด │
└────────────────────────────────┴───────────────────────────────────────┘
```

---

## 2. เสาหลัก 6 ประการของ "การ Train โมเดลที่ดี" (The 6 Pillars of Sound Quant ML)

### เสาหลักที่ 1: Data Hygiene & การขจัด Information Leakage (Lookahead Bias)
- **Point-in-Time Integrity:** ฟีเจอร์ทุกตัว ณ เวลา $t$ ต้องสร้างจากข้อมูลที่มีอยู่ถึงเวลา $t$ เท่านั้น ห้ามใช้ค่า Rolling ที่มองไปข้างหน้า (`shift(-k)`)
- **Purging & Embargoing:** เมื่อสร้าง Label ที่มองไปข้างหน้า $H$ แท่ง (เช่น Horizon 60 แท่ง) แท่งเทียนที่อยู่ในช่วง $t$ ถึง $t+H$ จะมีข้อมูลที่เหลื่อมซ้อนกัน (Overlap) ต้องตัดข้อมูลช่วงรอยต่อระหว่าง Train และ Validation ออก เพื่อป้องกันไม่ให้ข้อมูลจากอนาคตซึมเข้าสู่ Train set
- **Strict Blind Testing:** ข้อมูลปีล่าสุด (ปี 2026) ต้องถูก **LOCKED ห้ามแตะเด็ดขาด** ทั้งในขั้นตอน Normalization, Feature Selection, และ Hyperparameter Tuning เพื่อให้เป็น Out-of-Sample ที่แท้จริง

### เสาหลักที่ 2: Stationarity vs Memory (การแก้ปัญหาสเกลราคาดิบ)
- ราคาปิดดิบ ($P_t$) เป็น non-stationary ($I(1)$) หากใส่ $P_t = 1,500$ ในปี 2020 และ $P_t = 4,300$ ในปี 2025 โมเดลจะไม่สามารถเชื่อมโยงแบบแผนตลาดได้
- **วิธีแก้:** แปลงทุกฟีเจอร์ให้อยู่ใน **Relative & Scale-Free Space**:
  1. Multi-Horizon Log Returns: $r_k = \ln(P_t / P_{t-k})$
  2. Volatility Normalization: $\Delta P / \text{ATR}_{14}$
  3. Microstructure Ratios: $\text{Body}/\text{ATR}$, Wicks / Range, Close Location $[0, 1]$
  4. Local Distribution Z-Scores: $(P_t - \mu) / \sigma$

### เสาหลักที่ 3: Objective Function ที่สอดคล้องกับพอร์ตจริง (Utility Alignment)
- การวัดแค่ **Accuracy** หรือ **Cross-Entropy Loss** ไม่ได้การันตีว่าระบบจะทำกำไร เพราะ:
  - โมเดลที่ทายถูก 80% แต่ไม้ที่แพ้ขาดทุนหนัก (Fat-Tail Risk) ก็ทำให้พอร์ตแตกได้
  - โมเดลที่เทรดถูกทิศ แต่เปิด-ปิดออเดอร์ทุก 2 แท่ง จะถูก Spread และ Fee กัดกินจนหมดตัว
- **วิธีแก้:**
  - ใช้ **Focal Loss** หรือ **Cost-Sensitive Loss Matrix** เพื่อเพิ่มน้ำหนักให้กับการตัดสินใจในจังหวะสำคัญ
  - ลงโทษการเปิดออเดอร์พร่ำเพรื่อ (Turnover Penalty) และลงโทษความเสี่ยงลากติดลบ (Max Adverse Excursion Penalty)

### เสาหลักที่ 4: Action Gating & Turnover Control (แก้ปัญหา Overtrading)
- จากการทดลองพบว่า หากให้โมเดลทำนาย `argmax(logits)` ในทุกๆ แท่ง M1 โมเดลจะสลับ Action ถี่เกินไป (Overtrading) และขาดทุนค่า Spread สะสม
- **วิธีแก้:**
  1. **Confidence Threshold:** กำหนดเกณฑ์ความมั่นใจขั้นต่ำ เช่น $P(\text{Action}) > \theta$ (เช่น 0.40) หากไม่ถึงให้คงสถานะ `HOLD`
  2. **Action Masking:** ป้องกัน Action ที่ผิดหลักตรรกะ เช่น ขณะพอร์ตว่าง ห้ามสั่ง `ADD`, `REDUCE`, หรือ `CLOSE`
  3. **Cooldown Window:** กำหนดระยะเวลาถือครองขั้นต่ำ (Minimum Holding Period) ก่อนเปลี่ยนคำสั่ง

### เสาหลักที่ 5: การแบ่งสัดส่วนและถ่วงน้ำหนักคลาส (Class Imbalance Management)
- ในสภาวะตลาดปกติ แท่งเทียนส่วนใหญ่เป็น Side-way หรือ Noise ทำให้คลาส `HOLD` หรือ `NO_ACTION` มีสัดส่วนสูงกว่าจุดเข้าซื้อขายจริง
- **วิธีแก้:**
  - คำนวณ Class Weights แบบไดนามิก: $w_c = \frac{N}{K \cdot N_c}$
  - กำหนด Cap ของน้ำหนัก (เช่น $\min=0.1, \max=10.0$) เพื่อป้องกัน Gradient ระเบิดในคลาสที่มีตัวอย่างน้อย

### เสาหลักที่ 6: การประเมินผลแบบบูรณาการ (Joint ML & Trading Metrics)
- ไม่ตัดสินโมเดลจากค่า Loss หรือ Accuracy เพียงอย่างเดียว แต่ต้องใช้ Metric คู่ขนาน:
  - **ML Metrics:** Precision on Conviction Trades, Expected Calibration Error (ECE), F1-Macro
  - **Trading Metrics:** Net Profit, Profit Factor ($PF > 1.5$), Win Rate, Max Drawdown % ($MDD < 15\%$), Sharpe Ratio, และ Average Trade Expectancy

---

## 3. แผนพัฒนา 10 โมเดลที่แตกต่างกันทั้ง Algorithm, Tool และระเบียบวิธี

เพื่อให้ได้โมเดลที่มีความหลากหลายทั้งด้านสมมติฐาน (Inductive Bias) และเครื่องมือ เราจัดแบ่งออกเป็น 10 โมเดลใน 3 กลุ่มหลัก:

```
                                  10 QUANT ML MODELS
                                          │
         ┌────────────────────────────────┼────────────────────────────────┐
         ▼                                ▼                                ▼
  [Family A: Tabular GBDT]       [Family B: Deep Neural Nets]     [Family C: Quant Hybrid & RL]
  1. LightGBM (Focal Weight)     4. Deep Multi-Head ResMLP        8. Two-Stage Meta-Labeling
  2. CatBoost (Ordered Boost)    5. Temporal ConvNet (TCN 1D)     9. Asymmetric Cost-Sensitive Net
  3. XGBoost (Regularized Greedy) 6. GRU with Temporal Attention   10. PPO Reinforcement Learning
                                 7. Patch Time-Series Transformer
```

### รายละเอียดของแต่ละโมเดล:

| # | โมเดล | Algorithm / สถาปัตยกรรม | เครื่องมือ / Tool | จุดเด่นเฉพาะตัว (Unique Advantage) |
|---|---|---|---|---|
| **M1** | **LightGBM Policy** | Histogram-based GBDT (Leaf-wise) | `lightgbm` | เทรนเร็วมาก จัดการฟังก์ชันไม่เชิงเส้นได้ดี แยกดู Feature Importance ได้ชัดเจน |
| **M2** | **CatBoost Policy** | Ordered Boosting with Symmetric Trees | `catboost` | ป้องกัน Target Leakage ได้ดีเยี่ยม โครงสร้างต้นไม้สมมาตรช่วยลด Overfitting |
| **M3** | **XGBoost Depth-Constrained** | Depth-wise GBDT with L1/L2 Regularization | `xgboost` | ควบคุมความลึกจำกัด (Max Depth 4) บังคับให้เรียนรู้เฉพาะ Rule ที่กว้างและปลอดภัย |
| **M4** | **Deep Multi-Head ResMLP** | Residual MLP with LayerNorm & GELU | `PyTorch` (GPU) | มี Shared Backbone ร่วม และแยก 3 หัวขับเคลื่อน: Action (7 คลาส), Size, และ SL/TP |
| **M5** | **Temporal ConvNet (TCN)** | Dilated Causal 1D Convolution | `PyTorch` (GPU) | มี Receptive Field กว้าง 60 แท่ง สกัดโครงสร้างคลื่นราคาแบบ Multi-Scale โดยไม่เห็นอนาคต |
| **M6** | **Attention-Gated GRU** | Bidirectional GRU + Self-Attention | `PyTorch` (GPU) | มี Memory State จำสภาวะตลาดและความผันผวนย้อนหลัง พร้อมถ่วงน้ำหนักแท่งสำคัญ |
| **M7** | **Patch Temporal Transformer** | Multi-Head Self-Attention over Time | `PyTorch` (GPU) | คำนวณความสัมพันธ์คู่ขนานระหว่างแท่งเทียนใน Lookback Window เพื่อจับ Breakout Pattern |
| **M8** | **Two-Stage Meta-Labeling** | Primary Trend Filter + Secondary Meta-Classifier | `Scikit-Learn` + `LGBM` | ขั้นแรกคัดกรองทิศทาง ขั้นที่สองคำนวณโอกาสที่ออเดอร์จะรอดพ้น Spread และชนะ TP |
| **M9** | **Asymmetric Cost-Sensitive Net** | Deep Net with Custom Penalty Loss Matrix | `PyTorch` (GPU) | ออกแบบ Loss Function ลงโทษการเปิดไม้ผิดทางและเทรดบ่อยเป็นพิเศษเพื่อลด Churn |
| **M10**| **PPO Deep RL Agent** | Proximal Policy Optimization (Actor-Critic) | `Stable-Baselines3` | เรียนรู้จาก Reward ของ Equity พอร์ตจริงที่หักลบ Drawdown และค่าธรรมเนียม |
