# Strategy 99: Gold H1 Manning Stoller's STARCBands (STARC-ATR-KFD) Logic Template
## Linear Volatility Channel Expansion & Asymmetric Breakout Continuation

---

## 1. Executive Summary & Strategic Positioning
- **Strategy ID:** `STRATEGY_99`
- **Asset:** XAUUSD (Gold CFD)
- **Timeframe:** H1
- **Period:** 2020-01-01 to 2025-12-30 (72 Calendar Months)
- **Execution Model:** Next-Bar Open Fill, Institutional spread $0.25 ($2.50/0.10 lot) + commission $6/lot ($0.60/0.10 lot) = $3.10 fixed friction
- **Status:** **VALIDATED — INSTITUTIONAL SINGLE ENGINE** (PF 1.504, Net +$6,265.35, Win Rate 35.63%, Asymmetric 2.75:1 R:R)

### Core Hypothesis
Manning Stoller developed STARCBands (Stoller Average Range Channels) in 1980 as an alternative to Bollinger Bands. Bollinger Bands expand non-linearly during volatile blow-offs due to standard deviation squaring, causing erratic envelope distortions and false reversal triggers.

In contrast, STARCBands maintain strict linear volatility scaling by multiplying the Average True Range (ATR):

$$\text{UpperBand}_t = \text{SMA}_n(t) + \text{multiplier} \times \text{ATR}_m(t)$$
$$\text{LowerBand}_t = \text{SMA}_n(t) - \text{multiplier} \times \text{ATR}_m(t)$$

When price confirms a bar close outside the STARC envelope in the direction of the intermediate trend ($\text{EMA}_{50}$), while the Katz Fractal Dimension indicates low planar entropy ($D \le 1.40$), it confirms an institutional momentum breakout free from non-linear volatility distortion.

---

## 2. Institutional Performance Audit (2020 – 2025, 72 Calendar Months)

| Metric | Champion Config (PF 1.504) | Robust Variant (MCR 63.9%) | Low-DD Variant (DD $892) | Institutional Standard |
| :--- | :---: | :---: | :---: | :---: |
| **Total Trades** | **174** (29.0 / yr) | **228** (38.0 / yr) | **148** (24.7 / yr) | ~100 / year aggregate |
| **Net Profit (0.10 Lot)** | **+$6,265.35** | **+$6,321.54** | **+$5,579.59** | Positive Expectancy |
| **Profit Factor (PF)** | **1.504** 🏆 | **1.444** | **1.469** | $\ge 1.50$ |
| **Win Rate** | **35.63%** | **41.67%** | **37.16%** | High for 2.75:1 R:R |
| **Maximum Drawdown** | **$1,487.80** | **$1,230.05** | **$892.60** 🏆 | Sub-$1,500 baseline |
| **RoMaD** | **4.21x** | **5.14x** | **6.25x** | Return to Drawdown |
| **Monthly Consistency (MCR)**| **56.94% (41/72)** | **63.89% (46/72)** 🏆 | **59.72% (43/72)** | Consistent Cashflow |

---

## 3. Champion Parameter Configuration

| Parameter | Setting | Strategic Rationale |
| :--- | :---: | :--- |
| **SMA Period** | `14` | Baseline 14-period moving average centerline |
| **ATR Period** | `14` | Synchronized 14-hour volatility measurement |
| **Band Multiplier** | `1.5` | Standard Stoller envelope expansion multiplier |
| **Trigger Mode** | `starc_breakout` | Close pierces beyond outer band |
| **Intermediate Trend Gate** | `EMA50` | Aligns trade execution with prevailing intermediate momentum |
| **Anti-Chaos Gate** | `KFD <= 1.40` | Katz Fractal Dimension filter to avoid planar consolidation |
| **Take Profit** | `5.5 * ATR` | Asymmetric 2.75:1 reward-to-risk ratio |
| **Stop Loss** | `2.0 * ATR` | Tight stop avoiding noise stops |
| **Monthly Profit Lock** | `$200.00` | ASAR monthly gain protection |
| **Hard Loss Breaker** | `$250.00` | ASAR monthly capital protection |
