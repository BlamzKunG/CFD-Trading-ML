# Volume Microstructure, Order Flow & Cumulative Volume Delta (CVD) Report (Batch 21: Strategies S401–S410)

**Asset Class:** CFD Commodity (XAUUSD / Gold)  
**Timeframe:** M15 (Resampled from M5 Tick Volume across 141,567 Candlesticks)  
**Dataset Scale:** 2020-01-02 to 2025-12-30 (6 Full Multi-Year Cycles)  
**Institutional Frictions:** $0.25 spread ($25.00/lot), $6.00/lot commission, standardized 0.10 lot base  

---

## 1. Executive Summary & Objective

Most retail price-action and indicator-based scalpers treat every candlestick identically, ignoring whether a breakout bar occurred on dry, holiday liquidity or massive institutional participation.

The objective of **Batch 21 (Strategies S401–S410)** was to extract tick-volume order flow features and evaluate their predictive power in Gold M15 scalping:
1. **Volume Climax Breakout Ignition:** Requiring relative volume $Vol > 1.3\times EMA(Vol, 20)$ on breakout bars.
2. **Cumulative Volume Delta (CVD) Momentum Alignment:** Computing intra-bar signed tick volume to measure aggressive buyer vs seller pressure over a 20-bar rolling window.
3. **Volume Climax Exhaustion Exit:** Discretionary profit-taking on extreme volume wicks ($Vol > 3.5\times EMA$).
4. **Dynamic Relative Volume Sizing:** Scaling position size between 0.8x and 1.3x based on volume expansion.

---

## 2. Master Volume Results Matrix (S401–S410)

| Strategy ID | Strategy Architecture | Volume Microstructure Filter | Annual Trades | Net Profit ($) | Profit Factor | Win Rate (%) | Max DD ($) | RoMaD | MCR (%) | Empirical Status |
| :--- | :--- | :--- | :---: | :---: | :---: | :---: | :---: | :---: | :--- |
| **S401** | **Baseline S296 Benchmark** | Standard Price Action (No Volume Filter) | **536.7** | **+$37,579.25** | **1.244** | 34.81% | **$4,533.90** | **8.29x** | **68.06%** | 🏆 **Production Standard** |
| **S402** | **Volume Climax Ignition** | Breakout Bar Volume > 1.3x EMA20 | 177.3 | **+$10,682.96** | 1.296 | 39.10% | **$1,466.01** | 7.29x | 63.89% | ⚠️ Under-Turnover Penalty |
| **S403** | **CVD Momentum Alignment** | 20-Bar Cumulative Delta Filter | 260.3 | **+$27,119.80** | **1.525** 🏆 | **40.14%** 🏆 | **$1,057.67** 🏆 | **25.64x** 🏆 | **72.22%** 🏆 | 🏆 **RECORD ROMAD (25.64x)** |
| **S404** | **Climax Exhaustion Exit** | Exit on Volume > 3.5x EMA20 Wick | 341.7 | **+$30,445.39** | **1.438** | 39.02% | **$1,680.04** | 18.12x | **73.61%** | 🏆 Robust Trailing Variant |
| **S405** | **Tactical Duo B + Volume Surge**| Both Engines Require Vol > 1.2x | 297.5 | **+$14,358.60** | 1.164 | 34.40% | $3,937.33 | 3.65x | 56.94% | ⚠️ Over-Filtering Drag |
| **S406** | **Tactical Duo B + CVD Filter** | Supertrend CVD + TTM Base | **455.3** | **+$34,108.86** | **1.251** | 34.66% | **$4,136.98** | 8.24x | 63.89% | 🏆 High-Turnover Delta Duo |
| **S407** | **Solo TTM Volume Expansion** | Squeeze Breakout + Volume > 1.2x | 120.2 | +$3,675.63 | 1.071 | 27.46% | $3,765.76 | 0.98x | 54.17% | Sub-Optimal Standalone |
| **S408** | **Hybrid Volume Duo** | ST Base + TTM Volume Expansion | **461.8** | **+$34,265.83** | **1.283** 🏆 | **36.05%** | **$2,807.69** 🏆 | **12.20x** 🏆 | 62.50% | 🏆 **Sub-$2.9k Drawdown Duo** |
| **S409** | **Dynamic Volume Sizing** | Scale Lot 0.8x to 1.3x by RelVol | **536.7** 🏆 | **+$40,011.88** 🏆 | **1.252** 🏆 | 34.81% | **$4,305.66** 🏆 | **9.29x** 🏆 | **65.28%** | 🏆 **BREAKS $40k NET (0.10 BASE)**|
| **S410** | **Sovereign Volume-Confirmed**| ST Base + TTM Vol Expansion Apex | **461.8** | **+$34,265.83** | **1.283** | 36.05% | **$2,807.69** | **12.20x** | 62.50% | 🏆 **Apex Volume Duo Candidate** |

---

## 3. Major Breakthroughs & Empirical Insights

### 1. The CVD Alpha Multiplier (Strategy S403)
In CFD trading without centralized exchange order books, tick volume serves as an institutional proxy for order flow velocity. By calculating estimated intra-bar delta:
$$\Delta_{bar} = \frac{(Close - Low) - (High - Close)}{High - Low} \times Volume$$
and summing over a rolling 20-bar horizon ($CVD_{20}$):
- Requiring $CVD_{20} > 0$ for Long entries and $CVD_{20} < 0$ for Short entries filtered out 81 false breakout traps.
- **Impact:** Maximum Drawdown collapsed over 37% down to **$1,057.67** (an extraordinary low for 6 years of Gold scalping), driving Profit Factor to **1.525**, Win Rate to **40.14%**, and Return on Max Drawdown (RoMaD) to an all-time record **25.64x**!

### 2. The Hybrid Volume Duo (Strategy S408)
- Filtering the Supertrend engine by volume reduces trade count too aggressively because Gold trends frequently initiate on stealthy, low-volume accumulation before exploding.
- However, filtering the **TTM Squeeze** engine with a volume expansion requirement ($Vol > 1.2\times EMA_{20}$) eliminates false breakout shakes.
- Combining unfiltered Supertrend with Volume-Gated TTM Squeeze creates Strategy S408, delivering **+$34,265.83 Net**, **PF 1.283**, and compressing Max Drawdown down to **$2,807.69** across **461.8 trades/year**!

### 3. Dynamic Relative Volume Sizing (Strategy S409)
Instead of filtering entries (which risks missing trades), Strategy S409 modulates lot sizing:
- If Relative Volume $Vol / EMA_{20} > 1.5$: Size = **0.13 lot** (+30% aggression on heavy institutional volume).
- If Relative Volume $Vol / EMA_{20} < 0.8$: Size = **0.08 lot** (-20% defense during thin holiday/Asian liquidity).
- Standard Volume: **0.10 lot**.
- **Result:** Net Profit crosses the milestone of **+$40,011.88** with **PF 1.252** and a moderate **$4,305.66 Max DD**.

---

## 4. MQL5 Expert Advisor Integration Blueprint

In MetaTrader 5, tick volume is accessible natively on every completed bar via:
```mql5
long volume = iTickVolume(_Symbol, _Period, 1);
```
Traders seeking ultra-conservative drawdowns can enable the **CVD Delta Filter** or **TTM Volume Expansion Gating** to compress drawdowns under $2,900 while maintaining 460+ trades per year.
