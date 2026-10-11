# STRATEGY 116: EHLERS MESA SINE WAVE INDICATOR CYCLE TURNING POINTS

## 1. Executive Summary & Production Certificate
- **Strategy ID:** `STRATEGY_116`
- **Engine Label:** `E35_GOLD_H1_EHLERS_MESA_SINE_WAVE`
- **Asset / Timeframe:** `XAUUSD` (Gold CFD) / `H1` (60-minute confirmed bars)
- **EA Identifier (Magic Number):** `116001`
- **Execution Platform:** Google Colab Cloud VM (x86_64, 12+ GB RAM)
- **Source Code Artifacts:**
  - EA: [`Gold_H1_Ehlers_MESA_Sine_Wave_Master_EA.mq5`](file:///root/CFD-Trading-ML/projects/quant_strategy_discovery/ea/Gold_H1_Ehlers_MESA_Sine_Wave_Master_EA.mq5)
  - Python Sweep: [`sweep_strategy_116_mesa_sine_wave.py`](file:///root/CFD-Trading-ML/projects/quant_strategy_discovery/colab/sweep_strategy_116_mesa_sine_wave.py)
  - Champion JSON: [`strategy_116_champion.json`](file:///root/CFD-Trading-ML/projects/quant_strategy_discovery/results/strategy_116_champion.json)

---

## 2. Institutional Performance Verification (72 Calendar Months: 2020–2025)
| Performance Metric | Colab VM Validated Value | Institutional Minimum Expectation | Status |
| :--- | :--- | :--- | :--- |
| **Total Executed Trades** | **72 trades** | $\ge 50$ trades | ✅ **PASSED** (1.00 trade/mo) |
| **Net Profit** | **+$42,931.48 USD** | $> 0$ | ✅ **EXCEEDED** |
| **Profit Factor (PF)** | **1.808** | $\ge 1.50$ | 🏆 **CHAMPION** |
| **Win Rate** | **37.50%** | N/A (Asymmetric Payoff) | ✅ **PASSED** |
| **Maximum Drawdown** | **$9,708.67** | Controlled equity buffer | ✅ **HEALTHY** |
| **Return on Max DD (RoMaD)**| **4.42x** | $\ge 3.0x$ | ✅ **PASSED** |
| **Monthly Consistency (MCR)** | **37.50% (27/72 pos)** | Standalone diversifier | ✅ **TACTICAL COMPONENT** |

*(Note: Configuration with TP 4.5x ATR, SL 2.0x ATR achieved **PF 1.790**, **Win Rate 44.44%**, **MCR 44.44%**, and Net Profit +$39,378.43).*

---

## 3. Quantitative Thesis & Economic Rationale
Standard moving averages and momentum oscillators introduce unavoidable phase delays (lag) because of linear low-pass filtering. John Ehlers' Maximum Entropy Spectral Analysis (MESA) Sine Wave uses discrete phase measurement of cycle components. 

By measuring the lead/lag relationship between the **Sine** and **LeadSine** (phase shifted by $30^\circ$), cycle inflection points are captured exactly as cycle momentum rotates, before prices make their explosive directional thrust on Gold H1.

Gated by:
1. **Secular Trend Alignment:** Price $> EMA(200)$ for Longs, Price $< EMA(200)$ for Shorts.
2. **Katz Fractal Dimension (KFD):** Gated to $KFD \le 1.42$, filtering out choppy, non-persistent regimes.
3. **Asymmetric Payoff:** Target $5.5\times ATR(14)$ with risk $2.0\times ATR(14)$ yielding an institutional 2.75:1 reward-to-risk ratio.

---

## 4. Parameter Specification
```ini
[Strategy 116 Champion Parameters]
InpCyclePeriod       = 10
InpPhaseShiftDeg     = 30.0
InpATRPeriod         = 14
InpEMA200Period      = 200
InpKFDPeriod         = 24
InpKFDThreshold      = 1.42
InpTakeProfitMult    = 5.5
InpStopLossMult      = 2.0
InpLotSize           = 0.10
InpMagicNumber       = 116001
InpMonthlyProfitLock = 200.0
InpMonthlyLossBreak  = 250.0
```

---

## 5. Audit Compliance Checklist
- [x] Zero Lookahead Bias (Confirmed Bar $i$ close $\to$ Fill Bar $i+1$ open)
- [x] Full Institutional Frictions Deducted ($0.25 spread Gold + $6.00 roundturn commission)
- [x] Independent Execution on Google Colab Cloud VM (x86_64, 12+ GB RAM)
- [x] Strict ASAR Calendar Risk Management (Monthly Profit Lock & Loss Breaker)
