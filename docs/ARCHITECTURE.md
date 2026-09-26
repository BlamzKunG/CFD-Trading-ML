# XAUUSD Trading Policy Architecture & Mathematical Specification

## 1. Scale-Invariance & Stationarity Formulation

Standard algorithmic indicators and ML models suffer catastrophic domain shifts when tested across large price regimes (e.g. XAUUSD moving from $1,500/oz in 2020 to >$4,300/oz in 2025).

To guarantee strict mathematical stationarity, all 40 features entering the model are unitless or normalized:

### 1.1 Multi-Horizon Continuous Log Returns
$$r_k(t) = \ln\left(\frac{P_t}{P_{t-k}}\right), \quad k \in \{1, 3, 5, 15, 30, 60\}$$

### 1.2 Volatility-Normalized Price Deltas
$$\Delta_{\text{norm}, k}(t) = \frac{P_t - P_{t-k}}{\text{ATR}_{14}(t)}$$

### 1.3 Candlestick Microstructure
- **Normalized Body**: $\frac{\text{Close}_t - \text{Open}_t}{\text{ATR}_{14}(t)}$
- **Normalized Bar Range**: $\frac{\text{High}_t - \text{Low}_t}{\text{ATR}_{14}(t)}$
- **Wick Ratios**:
  $$\text{UpperWickRatio} = \frac{\text{High}_t - \max(\text{Open}_t, \text{Close}_t)}{\text{High}_t - \text{Low}_t}$$
  $$\text{LowerWickRatio} = \frac{\min(\text{Open}_t, \text{Close}_t) - \text{Low}_t}{\text{High}_t - \text{Low}_t}$$
- **Close Location**: $\frac{\text{Close}_t - \text{Low}_t}{\text{High}_t - \text{Low}_t} \in [0, 1]$

### 1.4 Local Price Distribution
$$Z_{20}(t) = \frac{P_t - \mu_{20}(t)}{\sigma_{20}(t)}, \quad Z_{100}(t) = \frac{P_t - \mu_{100}(t)}{\sigma_{100}(t)}$$
$$\text{Rank}_{60}(t) = \frac{P_t - \min_{60}(P)}{\max_{60}(P) - \min_{60}(P) + \epsilon} \in [0, 1]$$

---

## 2. Closed-Loop Position State Representation

The agent receives its current position context as part of the state vector:
$$\mathbf{S}_t = \left[ \mathbf{S}_{\text{market}, t} \in \mathbb{R}^{31} \;\|\; \mathbf{S}_{\text{pos}, t} \in \mathbb{R}^{9} \right] \in \mathbb{R}^{40}$$

Where $\mathbf{S}_{\text{pos}, t}$ consists of:
1. `pos_dir`: $\{-1.0, 0.0, +1.0\}$
2. `pos_size_frac`: Lot fraction relative to maximum allowable exposure $[0, 1]$
3. `entry_dist_atr`: $\frac{P_t - P_{\text{entry}}}{\text{ATR}_{14}(t)}$
4. `unrealized_pnl_atr`: $\text{pos\_dir} \times \frac{P_t - P_{\text{entry}}}{\text{ATR}_{14}(t)}$
5. `time_in_pos_norm`: $\min\left(1.0, \frac{\text{bars\_in\_pos}}{120}\right)$
6. `dist_to_sl_atr`: $\frac{|P_t - P_{\text{SL}}|}{\text{ATR}_{14}(t)}$
7. `dist_to_tp_atr`: $\frac{|P_t - P_{\text{TP}}|}{\text{ATR}_{14}(t)}$
8. `max_drawdown_atr`: Maximum adverse excursion observed during the trade
9. `bars_since_action_norm`: $\min\left(1.0, \frac{\text{bars\_since\_action}}{60}\right)$

---

## 3. Counterfactual Teacher Optimization

For each timestamp $t$ and horizon $H=60$, the teacher evaluates prospective rollouts:
$$U(a) = \text{Terminal PnL}(a) - \lambda \cdot \text{Max Adverse Excursion}(a) - \text{Friction}$$
Where:
- $\lambda = 0.7$ (risk-aversion coefficient)
- $\text{Friction} = 0.15 \text{ ATR}$ (spread, slippage, commission)

The optimal decision is selected via:
$$a^*(t) = \arg\max_{a \in \mathcal{A}(\mathbf{S}_{\text{pos}})} U(a)$$

This formulates policy learning as supervised distillation of counterfactual optimal play.
