# XAUUSD Trading Policy Architecture & Mathematical Specification

## 1. Scale-Invariance & Stationarity Formulation

Standard algorithmic indicators and ML models suffer catastrophic domain shifts when tested across large price regimes (e.g. XAUUSD moving from $1,500/oz in 2020 to >$4,300/oz in 2025).

To guarantee strict mathematical stationarity, all 40 features entering the model are unitless or normalized:

### 1.1 Multi-Horizon Continuous Log Returns

$$r_k(t) = \ln\left(\frac{P_t}{P_{t-k}}\right), \quad k \in \{1, 3, 5, 15, 30, 60\}$$

### 1.2 Volatility-Normalized Price Deltas

$$\Delta_{\mathrm{norm}, k}(t) = \frac{P_t - P_{t-k}}{\mathrm{ATR}_{14}(t)}$$

### 1.3 Candlestick Microstructure

- **Normalized Body**:
  $$\frac{\mathrm{Close}_t - \mathrm{Open}_t}{\mathrm{ATR}_{14}(t)}$$

- **Normalized Bar Range**:
  $$\frac{\mathrm{High}_t - \mathrm{Low}_t}{\mathrm{ATR}_{14}(t)}$$

- **Wick Ratios**:
  $$\mathrm{UpperWickRatio} = \frac{\mathrm{High}_t - \max(\mathrm{Open}_t, \mathrm{Close}_t)}{\mathrm{High}_t - \mathrm{Low}_t}$$
  $$\mathrm{LowerWickRatio} = \frac{\min(\mathrm{Open}_t, \mathrm{Close}_t) - \mathrm{Low}_t}{\mathrm{High}_t - \mathrm{Low}_t}$$

- **Close Location**:
  $$\frac{\mathrm{Close}_t - \mathrm{Low}_t}{\mathrm{High}_t - \mathrm{Low}_t} \in [0, 1]$$

### 1.4 Local Price Distribution

$$Z_{20}(t) = \frac{P_t - \mu_{20}(t)}{\sigma_{20}(t)}, \quad Z_{100}(t) = \frac{P_t - \mu_{100}(t)}{\sigma_{100}(t)}$$

$$\mathrm{Rank}_{60}(t) = \frac{P_t - \min_{60}(P)}{\max_{60}(P) - \min_{60}(P) + \epsilon} \in [0, 1]$$

---

## 2. Closed-Loop Position State Representation

The agent receives its current position context as part of the state vector:

$$\mathbf{S}_t = \left[ \mathbf{S}_{\mathrm{market}, t} \in \mathbb{R}^{31} \parallel \mathbf{S}_{\mathrm{pos}, t} \in \mathbb{R}^{9} \right] \in \mathbb{R}^{40}$$

Where $\mathbf{S}_{\mathrm{pos}, t}$ consists of:

1. `pos_dir`: $\{-1.0, 0.0, +1.0\}$
2. `pos_size_frac`: Lot fraction relative to maximum allowable exposure $[0, 1]$
3. `entry_dist_atr`: $\frac{P_t - P_{\mathrm{entry}}}{\mathrm{ATR}_{14}(t)}$
4. `unrealized_pnl_atr`: $\text{pos}\textunderscore\text{dir} \times \frac{P_t - P_{\mathrm{entry}}}{\mathrm{ATR}_{14}(t)}$
5. `time_in_pos_norm`: $\min\left(1.0, \frac{\text{bars}\textunderscore\text{in}\textunderscore\text{pos}}{120}\right)$
6. `dist_to_sl_atr`: $\frac{\vert{}P_t - P_{\mathrm{SL}}\vert{}}{\mathrm{ATR}_{14}(t)}$
7. `dist_to_tp_atr`: $\frac{\vert{}P_t - P_{\mathrm{TP}}\vert{}}{\mathrm{ATR}_{14}(t)}$
8. `max_drawdown_atr`: Maximum adverse excursion observed during the trade
9. `bars_since_action_norm`: $\min\left(1.0, \frac{\text{bars}\textunderscore\text{since}\textunderscore\text{action}}{60}\right)$

---

## 3. Counterfactual Teacher Optimization

For each timestamp $t$ and horizon $H=60$, the teacher evaluates prospective rollouts:

$$U(a) = \mathrm{Terminal\ PnL}(a) - \lambda \cdot \mathrm{Max\ Adverse\ Excursion}(a) - \mathrm{Friction}$$

Where:
- $\lambda = 0.7$ (risk-aversion coefficient)
- $\mathrm{Friction} = 0.15 \ \mathrm{ATR}$ (spread, slippage, commission)

The optimal decision is selected via:

$$a^*(t) = \arg\max_{a \in \mathcal{A}(\mathbf{S}_{\mathrm{pos}})} U(a)$$

This formulates policy learning as supervised distillation of counterfactual optimal play.
