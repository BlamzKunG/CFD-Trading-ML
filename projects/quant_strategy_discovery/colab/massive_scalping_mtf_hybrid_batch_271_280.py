#!/usr/bin/env python3
"""
===============================================================================
SCALPING FRONTIER BATCH 8: STRATEGIES 271 - 280
MULTI-TIMEFRAME MATRIX HYBRID SCALPERS (M15 MACRO FILTER + M5 MICRO EXECUTION)
===============================================================================
Objective:
Solve the M5 micro-scalping friction challenge by marrying M15 Macro Regime
Filtering (Supertrend / EMA200) with M5 low-risk pullback execution and dynamic
ratchet trailing exits to achieve PF >= 1.20 - 1.50+ with 300 - 600+ trades/year.

Execution Frictions:
- Spread: $0.25 ($25.00 / lot)
- Commission: $6.00 / lot ($0.60 / 0.10 lot)
- Strict Zero Look-Ahead Bias: M15 signals aligned strictly using completed bars.
===============================================================================
"""

import os
import sys
import gc
import time
import json
import numpy as np
import pandas as pd

if os.path.exists("/content/CFD-Trading-ML"):
    REPO_ROOT = "/content/CFD-Trading-ML"
else:
    REPO_ROOT = "/root/CFD-Trading-ML"

DATA_DIR = os.path.join(REPO_ROOT, "projects/quant_strategy_discovery/data")
RESULTS_DIR = os.path.join(REPO_ROOT, "projects/quant_strategy_discovery/results")
os.makedirs(RESULTS_DIR, exist_ok=True)

# -----------------------------------------------------------------------------
# Fast Vectorized Indicator Helpers
# -----------------------------------------------------------------------------
def compute_atr(highs: np.ndarray, lows: np.ndarray, closes: np.ndarray, period: int = 14) -> np.ndarray:
    n = len(closes)
    atr = np.zeros(n, dtype=np.float64)
    tr = np.zeros(n, dtype=np.float64)
    tr[0] = highs[0] - lows[0]
    for i in range(1, n):
        hl = highs[i] - lows[i]
        hc = abs(highs[i] - closes[i - 1])
        lc = abs(lows[i] - closes[i - 1])
        tr[i] = max(hl, max(hc, lc))
    atr[period - 1] = np.mean(tr[:period])
    alpha = 1.0 / period
    for i in range(period, n):
        atr[i] = (tr[i] * alpha) + (atr[i - 1] * (1.0 - alpha))
    return atr

def compute_ema(series: np.ndarray, period: int) -> np.ndarray:
    n = len(series)
    ema = np.zeros(n, dtype=np.float64)
    ema[0] = series[0]
    alpha = 2.0 / (period + 1.0)
    for i in range(1, n):
        ema[i] = (series[i] * alpha) + (ema[i - 1] * (1.0 - alpha))
    return ema

def compute_rsi(closes: np.ndarray, period: int = 5) -> np.ndarray:
    n = len(closes)
    rsi = np.full(n, 50.0, dtype=np.float64)
    diffs = np.diff(closes)
    gains = np.where(diffs > 0, diffs, 0.0)
    losses = np.where(diffs < 0, -diffs, 0.0)
    if len(gains) < period:
        return rsi
    avg_gain = np.mean(gains[:period])
    avg_loss = np.mean(losses[:period])
    for i in range(period, len(diffs)):
        avg_gain = (avg_gain * (period - 1) + gains[i]) / period
        avg_loss = (avg_loss * (period - 1) + losses[i]) / period
        if avg_loss == 0:
            rsi[i + 1] = 100.0
        else:
            rs = avg_gain / avg_loss
            rsi[i + 1] = 100.0 - (100.0 / (1.0 + rs))
    return rsi

def compute_stochastic(highs: np.ndarray, lows: np.ndarray, closes: np.ndarray,
                       k_period: int = 8, d_period: int = 3) -> tuple:
    n = len(closes)
    k = np.full(n, 50.0, dtype=np.float64)
    for i in range(k_period - 1, n):
        h = np.max(highs[i - k_period + 1 : i + 1])
        l = np.min(lows[i - k_period + 1 : i + 1])
        k[i] = ((closes[i] - l) / (h - l) * 100.0) if (h > l) else 50.0
    d = compute_ema(k, d_period)
    return k, d

def compute_supertrend(highs: np.ndarray, lows: np.ndarray, closes: np.ndarray,
                       period: int = 14, multiplier: float = 3.0) -> tuple:
    n = len(closes)
    atr = compute_atr(highs, lows, closes, period)
    upper = (highs + lows) / 2.0 + multiplier * atr
    lower = (highs + lows) / 2.0 - multiplier * atr
    trend = np.ones(n, dtype=np.int32)
    st = np.zeros(n, dtype=np.float64)

    for i in range(period + 1, n):
        if closes[i - 1] > lower[i - 1]:
            lower[i] = max(lower[i], lower[i - 1])
        if closes[i - 1] < upper[i - 1]:
            upper[i] = min(upper[i], upper[i - 1])

        if trend[i - 1] == 1:
            if closes[i] < lower[i]:
                trend[i] = -1
                st[i] = upper[i]
            else:
                trend[i] = 1
                st[i] = lower[i]
        else:
            if closes[i] > upper[i]:
                trend[i] = 1
                st[i] = lower[i]
            else:
                trend[i] = -1
                st[i] = upper[i]
    return trend, st

# -----------------------------------------------------------------------------
# Micro-Execution Scalper Backtest Simulator (Ratchet Trailing & Dynamic Targets)
# -----------------------------------------------------------------------------
def simulate_mtf_scalper(opens, highs, lows, closes, atr,
                         bull_signals, bear_signals,
                         months,
                         exit_mode="ratchet_trailing",
                         trailing_mult=2.5,
                         sl_mult=1.5,
                         tp_mult=3.5,
                         max_hold_bars=36,
                         spread_pts=0.25,
                         comm_dollars=0.60):
    n = len(closes)
    trades = []
    in_pos = False
    pos_type = 0
    entry_price = 0.0
    entry_idx = 0
    stop_price = 0.0
    target_price = 0.0
    extreme_price = 0.0
    point_value = 100.0

    for i in range(100, n - 1):
        if in_pos:
            hit_exit = False
            exit_price = 0.0

            # 1. Update dynamic ratchet trailing stop
            if exit_mode == "ratchet_trailing":
                trail_dist = trailing_mult * atr[i]
                if pos_type == 1:
                    if highs[i] > extreme_price:
                        extreme_price = highs[i]
                        new_stop = extreme_price - trail_dist
                        if new_stop > stop_price:
                            stop_price = new_stop
                    if lows[i] <= stop_price:
                        hit_exit = True
                        exit_price = min(stop_price, opens[i]) - spread_pts
                elif pos_type == -1:
                    if lows[i] < extreme_price:
                        extreme_price = lows[i]
                        new_stop = extreme_price + trail_dist
                        if new_stop < stop_price:
                            stop_price = new_stop
                    if highs[i] >= stop_price:
                        hit_exit = True
                        exit_price = max(stop_price, opens[i])

            elif exit_mode == "fixed_rr":
                if pos_type == 1:
                    if lows[i] <= stop_price:
                        hit_exit = True
                        exit_price = stop_price - spread_pts
                    elif highs[i] >= target_price:
                        hit_exit = True
                        exit_price = target_price - spread_pts
                elif pos_type == -1:
                    if highs[i] >= stop_price:
                        hit_exit = True
                        exit_price = stop_price
                    elif lows[i] <= target_price:
                        hit_exit = True
                        exit_price = target_price

            # Max hold time exit
            if not hit_exit and (i - entry_idx) >= max_hold_bars:
                hit_exit = True
                if pos_type == 1:
                    exit_price = opens[i] - spread_pts
                else:
                    exit_price = opens[i]

            if hit_exit:
                if pos_type == 1:
                    pnl = (exit_price - entry_price) * point_value - comm_dollars
                else:
                    pnl = (entry_price - exit_price) * point_value - comm_dollars
                trades.append({
                    "pnl": pnl,
                    "month": months[entry_idx],
                    "entry_idx": entry_idx,
                    "exit_idx": i
                })
                in_pos = False
                continue

        # Entry logic (Next bar fill at opens[i+1])
        if not in_pos:
            atr_val = atr[i]
            if atr_val < 0.80:  # Minimum volatility filter
                continue

            if bull_signals[i]:
                in_pos = True
                pos_type = 1
                entry_idx = i + 1
                entry_price = opens[i + 1] + spread_pts
                extreme_price = entry_price
                if exit_mode == "ratchet_trailing":
                    stop_price = entry_price - (sl_mult * atr_val)
                else:
                    stop_price = entry_price - (sl_mult * atr_val)
                    target_price = entry_price + (tp_mult * atr_val)

            elif bear_signals[i]:
                in_pos = True
                pos_type = -1
                entry_idx = i + 1
                entry_price = opens[i + 1]
                extreme_price = entry_price
                if exit_mode == "ratchet_trailing":
                    stop_price = entry_price + (sl_mult * atr_val)
                else:
                    stop_price = entry_price + (sl_mult * atr_val)
                    target_price = entry_price - (tp_mult * atr_val)

    if not trades:
        return {
            "total_trades": 0, "annual_trades": 0.0, "net_profit": 0.0, "pf": 0.0,
            "win_rate": 0.0, "max_dd": 0.0, "romad": 0.0, "mcr": 0.0, "trades": []
        }

    pnls = np.array([t["pnl"] for t in trades])
    net_profit = np.sum(pnls)
    gross_win = np.sum(pnls[pnls > 0])
    gross_loss = abs(np.sum(pnls[pnls < 0]))
    pf = (gross_win / gross_loss) if gross_loss > 0 else (99.0 if gross_win > 0 else 0.0)
    win_rate = (len(pnls[pnls > 0]) / len(pnls)) * 100.0

    equity = np.cumsum(pnls)
    peak = np.maximum.accumulate(equity)
    dd = peak - equity
    max_dd = np.max(dd) if len(dd) > 0 else 0.0
    romad = (net_profit / max_dd) if max_dd > 0 else 0.0

    df_t = pd.DataFrame(trades)
    m_pnl = df_t.groupby("month")["pnl"].sum()
    total_months = len(m_pnl)
    win_months = np.sum(m_pnl > 0)
    mcr = (win_months / total_months * 100.0) if total_months > 0 else 0.0
    annual_trades = round(len(trades) / 6.0, 1)

    return {
        "total_trades": len(trades),
        "annual_trades": annual_trades,
        "net_profit": round(float(net_profit), 2),
        "pf": round(float(pf), 3),
        "win_rate": round(float(win_rate), 2),
        "max_dd": round(float(max_dd), 2),
        "romad": round(float(romad), 2),
        "mcr": round(float(mcr), 2),
        "trades": trades
    }

# -----------------------------------------------------------------------------
# Main Execution Pipeline
# -----------------------------------------------------------------------------
def main():
    print("=" * 80)
    print("STARTING SCALPING FRONTIER BATCH 8: STRATEGIES 271 - 280")
    print("MULTI-TIMEFRAME MATRIX HYBRID SCALPERS (M15 MACRO + M5 MICRO)")
    print("=" * 80)
    t0 = time.time()

    # Load high-resolution M5 and M15 datasets
    print("Loading XAUUSD M5 and M15 Parquet datasets...")
    df_m5 = pd.read_parquet(os.path.join(DATA_DIR, "XAUUSD_M5.parquet"))
    df_m15 = pd.read_parquet(os.path.join(DATA_DIR, "XAUUSD_M15.parquet"))

    print(f"M5 Shape: {df_m5.shape}, Range: {df_m5.index[0]} to {df_m5.index[-1]}")
    print(f"M15 Shape: {df_m15.shape}, Range: {df_m15.index[0]} to {df_m15.index[-1]}")

    # Compute M15 Indicators
    print("Computing M15 Macro Indicators (Supertrend & EMA200)...")
    m15_opens = df_m15["open"].values.astype(np.float64)
    m15_highs = df_m15["high"].values.astype(np.float64)
    m15_lows = df_m15["low"].values.astype(np.float64)
    m15_closes = df_m15["close"].values.astype(np.float64)

    m15_trend, m15_st = compute_supertrend(m15_highs, m15_lows, m15_closes, period=14, multiplier=3.0)
    m15_ema200 = compute_ema(m15_closes, 200)

    # Put M15 indicator results into DataFrame and shift by 1 bar to strictly eliminate lookahead bias
    df_m15_signals = pd.DataFrame(index=df_m15.index)
    df_m15_signals["m15_trend"] = pd.Series(m15_trend, index=df_m15.index).shift(1).fillna(0).astype(int)
    df_m15_signals["m15_ema200"] = pd.Series(m15_ema200, index=df_m15.index).shift(1).fillna(0)
    df_m15_signals["m15_close_prev"] = pd.Series(m15_closes, index=df_m15.index).shift(1).fillna(0)

    # Merge M15 macro trend onto M5 index using asof join (strictly backwards in time)
    print("Aligning M15 macro trend onto M5 timeline via zero lookahead backward merge...")
    df_m5_merged = pd.merge_asof(
        df_m5.sort_index(),
        df_m15_signals.sort_index(),
        left_index=True,
        right_index=True,
        direction="backward"
    )

    m5_opens = df_m5_merged["open"].values.astype(np.float64)
    m5_highs = df_m5_merged["high"].values.astype(np.float64)
    m5_lows = df_m5_merged["low"].values.astype(np.float64)
    m5_closes = df_m5_merged["close"].values.astype(np.float64)
    m5_volumes = df_m5_merged["tick_volume"].values.astype(np.float64) if "tick_volume" in df_m5_merged.columns else np.ones(len(m5_closes))

    m15_trend_aligned = df_m5_merged["m15_trend"].values
    m15_ema200_aligned = df_m5_merged["m15_ema200"].values
    m15_close_aligned = df_m5_merged["m15_close_prev"].values

    dates = df_m5_merged.index
    months = np.array([f"{d.year}-{d.month:02d}" for d in dates])
    hours = np.array([d.hour for d in dates])
    n5 = len(m5_closes)

    print("Computing M5 Technical Features...")
    m5_atr14 = compute_atr(m5_highs, m5_lows, m5_closes, 14)
    m5_rsi5 = compute_rsi(m5_closes, 5)
    m5_rsi7 = compute_rsi(m5_closes, 7)
    m5_k, m5_d = compute_stochastic(m5_highs, m5_lows, m5_closes, 8, 3)
    m5_ema9 = compute_ema(m5_closes, 9)
    m5_ema21 = compute_ema(m5_closes, 21)
    m5_ema50 = compute_ema(m5_closes, 50)
    m5_vol_sma20 = compute_ema(m5_volumes, 20)

    # M5 Bollinger Bands
    m5_bb_mid = compute_ema(m5_closes, 20)
    m5_bb_std = pd.Series(m5_closes).rolling(20).std().fillna(1.0).values
    m5_bb_upper = m5_bb_mid + 2.0 * m5_bb_std
    m5_bb_lower = m5_bb_mid - 2.0 * m5_bb_std

    # M5 Supertrend
    m5_trend, m5_st = compute_supertrend(m5_highs, m5_lows, m5_closes, period=14, multiplier=3.0)

    # M5 Fair Value Gap (FVG) detection
    bull_fvg = np.zeros(n5, dtype=bool)
    bear_fvg = np.zeros(n5, dtype=bool)
    for i in range(2, n5):
        if m5_lows[i] > m5_highs[i - 2]:  # Bullish gap
            bull_fvg[i] = True
        elif m5_highs[i] < m5_lows[i - 2]:  # Bearish gap
            bear_fvg[i] = True

    print("\nExecuting Strategy Discovery Sweeps (S271 - S280)...")
    results = []

    # -------------------------------------------------------------------------
    # S271: M15 Supertrend + M5 Fast RSI Dip (Ratchet Trailing Exit)
    # -------------------------------------------------------------------------
    print("Evaluating S271: M15 Supertrend + M5 Fast RSI Dip (Ratchet Trailing)...")
    bull_sigs = np.zeros(n5, dtype=bool)
    bear_sigs = np.zeros(n5, dtype=bool)
    for i in range(1, n5):
        # M15 Trend is Bullish
        if m15_trend_aligned[i] == 1:
            if m5_rsi5[i - 1] < 25 and m5_rsi5[i] >= 25:
                bull_sigs[i] = True
        # M15 Trend is Bearish
        elif m15_trend_aligned[i] == -1:
            if m5_rsi5[i - 1] > 75 and m5_rsi5[i] <= 75:
                bear_sigs[i] = True

    res_271 = simulate_mtf_scalper(m5_opens, m5_highs, m5_lows, m5_closes, m5_atr14,
                                   bull_sigs, bear_sigs, months,
                                   exit_mode="ratchet_trailing", trailing_mult=2.5, sl_mult=1.5)
    res_271["strategy_id"] = "S271"
    res_271["strategy_name"] = "M15 Supertrend + M5 Fast RSI Dip (Ratchet Trailing)"
    res_271["status"] = "CHAMPION" if res_271["pf"] >= 1.20 else ("TACTICAL CANDIDATE" if res_271["net_profit"] > 0 else "REJECTED")
    results.append(res_271)

    # -------------------------------------------------------------------------
    # S272: M15 Supertrend + M5 Fast RSI Dip (Asymmetric 3.5R Target & 1.2R SL)
    # -------------------------------------------------------------------------
    print("Evaluating S272: M15 Supertrend + M5 Fast RSI Dip (Asymmetric 3.5:1.2 RR)...")
    res_272 = simulate_mtf_scalper(m5_opens, m5_highs, m5_lows, m5_closes, m5_atr14,
                                   bull_sigs, bear_sigs, months,
                                   exit_mode="fixed_rr", sl_mult=1.2, tp_mult=3.5, max_hold_bars=24)
    res_272["strategy_id"] = "S272"
    res_272["strategy_name"] = "M15 Supertrend + M5 Fast RSI Dip (Asymmetric 3.5:1.2 RR)"
    res_272["status"] = "CHAMPION" if res_272["pf"] >= 1.20 else ("TACTICAL CANDIDATE" if res_272["net_profit"] > 0 else "REJECTED")
    results.append(res_272)

    # -------------------------------------------------------------------------
    # S273: M15 Supertrend + M5 Stochastic %K Momentum Pop
    # -------------------------------------------------------------------------
    print("Evaluating S273: M15 Supertrend + M5 Stochastic %K Momentum Pop...")
    bull_sigs = np.zeros(n5, dtype=bool)
    bear_sigs = np.zeros(n5, dtype=bool)
    for i in range(1, n5):
        if m15_trend_aligned[i] == 1:
            if m5_k[i - 1] < m5_d[i - 1] and m5_k[i] >= m5_d[i] and m5_k[i] < 30:
                bull_sigs[i] = True
        elif m15_trend_aligned[i] == -1:
            if m5_k[i - 1] > m5_d[i - 1] and m5_k[i] <= m5_d[i] and m5_k[i] > 70:
                bear_sigs[i] = True

    res_273 = simulate_mtf_scalper(m5_opens, m5_highs, m5_lows, m5_closes, m5_atr14,
                                   bull_sigs, bear_sigs, months,
                                   exit_mode="ratchet_trailing", trailing_mult=2.5, sl_mult=1.5)
    res_273["strategy_id"] = "S273"
    res_273["strategy_name"] = "M15 Supertrend + M5 Stochastic %K Pop (Ratchet Trailing)"
    res_273["status"] = "CHAMPION" if res_273["pf"] >= 1.20 else ("TACTICAL CANDIDATE" if res_273["net_profit"] > 0 else "REJECTED")
    results.append(res_273)

    # -------------------------------------------------------------------------
    # S274: M15 Supertrend + M5 Bollinger Lower Band Dip Bounce
    # -------------------------------------------------------------------------
    print("Evaluating S274: M15 Supertrend + M5 Bollinger Bands Lower Bounce...")
    bull_sigs = np.zeros(n5, dtype=bool)
    bear_sigs = np.zeros(n5, dtype=bool)
    for i in range(1, n5):
        if m15_trend_aligned[i] == 1:
            if m5_lows[i] <= m5_bb_lower[i] and m5_closes[i] > m5_opens[i]:
                bull_sigs[i] = True
        elif m15_trend_aligned[i] == -1:
            if m5_highs[i] >= m5_bb_upper[i] and m5_closes[i] < m5_opens[i]:
                bear_sigs[i] = True

    res_274 = simulate_mtf_scalper(m5_opens, m5_highs, m5_lows, m5_closes, m5_atr14,
                                   bull_sigs, bear_sigs, months,
                                   exit_mode="ratchet_trailing", trailing_mult=2.5, sl_mult=1.5)
    res_274["strategy_id"] = "S274"
    res_274["strategy_name"] = "M15 Supertrend + M5 BB Dip Bounce (Ratchet Trailing)"
    res_274["status"] = "CHAMPION" if res_274["pf"] >= 1.20 else ("TACTICAL CANDIDATE" if res_274["net_profit"] > 0 else "REJECTED")
    results.append(res_274)

    # -------------------------------------------------------------------------
    # S275: M15 Supertrend + M5 Fair Value Gap Retest
    # -------------------------------------------------------------------------
    print("Evaluating S275: M15 Supertrend + M5 Fair Value Gap Retest...")
    bull_sigs = np.zeros(n5, dtype=bool)
    bear_sigs = np.zeros(n5, dtype=bool)
    for i in range(5, n5):
        if m15_trend_aligned[i] == 1:
            if np.any(bull_fvg[i - 4 : i]) and m5_lows[i] <= m5_closes[i - 2] and m5_closes[i] > m5_opens[i]:
                bull_sigs[i] = True
        elif m15_trend_aligned[i] == -1:
            if np.any(bear_fvg[i - 4 : i]) and m5_highs[i] >= m5_closes[i - 2] and m5_closes[i] < m5_opens[i]:
                bear_sigs[i] = True

    res_275 = simulate_mtf_scalper(m5_opens, m5_highs, m5_lows, m5_closes, m5_atr14,
                                   bull_sigs, bear_sigs, months,
                                   exit_mode="ratchet_trailing", trailing_mult=2.5, sl_mult=1.5)
    res_275["strategy_id"] = "S275"
    res_275["strategy_name"] = "M15 Supertrend + M5 FVG Retest (Ratchet Trailing)"
    res_275["status"] = "CHAMPION" if res_275["pf"] >= 1.20 else ("TACTICAL CANDIDATE" if res_275["net_profit"] > 0 else "REJECTED")
    results.append(res_275)

    # -------------------------------------------------------------------------
    # S276: M15 Supertrend + M5 Volume Force Expansion
    # -------------------------------------------------------------------------
    print("Evaluating S276: M15 Supertrend + M5 Volume Force Expansion...")
    bull_sigs = np.zeros(n5, dtype=bool)
    bear_sigs = np.zeros(n5, dtype=bool)
    for i in range(1, n5):
        if m15_trend_aligned[i] == 1:
            if m5_volumes[i] >= 1.5 * m5_vol_sma20[i] and (m5_closes[i] - m5_opens[i]) > 0.4 * m5_atr14[i]:
                bull_sigs[i] = True
        elif m15_trend_aligned[i] == -1:
            if m5_volumes[i] >= 1.5 * m5_vol_sma20[i] and (m5_opens[i] - m5_closes[i]) > 0.4 * m5_atr14[i]:
                bear_sigs[i] = True

    res_276 = simulate_mtf_scalper(m5_opens, m5_highs, m5_lows, m5_closes, m5_atr14,
                                   bull_sigs, bear_sigs, months,
                                   exit_mode="ratchet_trailing", trailing_mult=2.5, sl_mult=1.5)
    res_276["strategy_id"] = "S276"
    res_276["strategy_name"] = "M15 Supertrend + M5 Volume Force (Ratchet Trailing)"
    res_276["status"] = "CHAMPION" if res_276["pf"] >= 1.20 else ("TACTICAL CANDIDATE" if res_276["net_profit"] > 0 else "REJECTED")
    results.append(res_276)

    # -------------------------------------------------------------------------
    # S277: M15 Supertrend + M5 EMA Ribbon Fast Cross (EMA 9 > EMA 21)
    # -------------------------------------------------------------------------
    print("Evaluating S277: M15 Supertrend + M5 EMA Fast Ribbon Cross...")
    bull_sigs = np.zeros(n5, dtype=bool)
    bear_sigs = np.zeros(n5, dtype=bool)
    for i in range(1, n5):
        if m15_trend_aligned[i] == 1:
            if m5_ema9[i - 1] <= m5_ema21[i - 1] and m5_ema9[i] > m5_ema21[i]:
                bull_sigs[i] = True
        elif m15_trend_aligned[i] == -1:
            if m5_ema9[i - 1] >= m5_ema21[i - 1] and m5_ema9[i] < m5_ema21[i]:
                bear_sigs[i] = True

    res_277 = simulate_mtf_scalper(m5_opens, m5_highs, m5_lows, m5_closes, m5_atr14,
                                   bull_sigs, bear_sigs, months,
                                   exit_mode="ratchet_trailing", trailing_mult=2.5, sl_mult=1.5)
    res_277["strategy_id"] = "S277"
    res_277["strategy_name"] = "M15 Supertrend + M5 EMA 9/21 Cross (Ratchet Trailing)"
    res_277["status"] = "CHAMPION" if res_277["pf"] >= 1.20 else ("TACTICAL CANDIDATE" if res_277["net_profit"] > 0 else "REJECTED")
    results.append(res_277)

    # -------------------------------------------------------------------------
    # S278: M15 Supertrend + M5 Supertrend Ratchet (Dual-Timeframe Trend)
    # -------------------------------------------------------------------------
    print("Evaluating S278: M15 Supertrend + M5 Supertrend Ratchet...")
    bull_sigs = np.zeros(n5, dtype=bool)
    bear_sigs = np.zeros(n5, dtype=bool)
    for i in range(1, n5):
        if m15_trend_aligned[i] == 1 and m5_trend[i - 1] == -1 and m5_trend[i] == 1:
            bull_sigs[i] = True
        elif m15_trend_aligned[i] == -1 and m5_trend[i - 1] == 1 and m5_trend[i] == -1:
            bear_sigs[i] = True

    res_278 = simulate_mtf_scalper(m5_opens, m5_highs, m5_lows, m5_closes, m5_atr14,
                                   bull_sigs, bear_sigs, months,
                                   exit_mode="ratchet_trailing", trailing_mult=3.0, sl_mult=1.5)
    res_278["strategy_id"] = "S278"
    res_278["strategy_name"] = "M15 Supertrend + M5 Supertrend Ratchet Scalper"
    res_278["status"] = "CHAMPION" if res_278["pf"] >= 1.20 else ("TACTICAL CANDIDATE" if res_278["net_profit"] > 0 else "REJECTED")
    results.append(res_278)

    # -------------------------------------------------------------------------
    # S279: Multi-TF Tactical Duo: M15 Supertrend Core (S261) + S271 M5 Fast RSI
    # -------------------------------------------------------------------------
    print("Evaluating S279: Multi-TF Tactical Duo Ensemble...")
    trades_271 = res_271["trades"]
    # Run M15 Supertrend Core on M15 bars
    m15_dates = df_m15.index
    m15_months = np.array([f"{d.year}-{d.month:02d}" for d in m15_dates])
    m15_atr = compute_atr(m15_highs, m15_lows, m15_closes, 14)
    bull_m15 = np.zeros(len(m15_closes), dtype=bool)
    bear_m15 = np.zeros(len(m15_closes), dtype=bool)
    for i in range(1, len(m15_closes)):
        if m15_trend[i - 1] == -1 and m15_trend[i] == 1:
            bull_m15[i] = True
        elif m15_trend[i - 1] == 1 and m15_trend[i] == -1:
            bear_m15[i] = True

    res_m15_core = simulate_mtf_scalper(m15_opens, m15_highs, m15_lows, m15_closes, m15_atr,
                                        bull_m15, bear_m15, m15_months,
                                        exit_mode="ratchet_trailing", trailing_mult=3.0, sl_mult=1.5)

    combined_trades_279 = trades_271 + res_m15_core["trades"]
    if combined_trades_279:
        pnls = np.array([t["pnl"] for t in combined_trades_279])
        net_profit = np.sum(pnls)
        gross_win = np.sum(pnls[pnls > 0])
        gross_loss = abs(np.sum(pnls[pnls < 0]))
        pf = (gross_win / gross_loss) if gross_loss > 0 else 0.0
        win_rate = (len(pnls[pnls > 0]) / len(pnls)) * 100.0
        equity = np.cumsum(pnls)
        peak = np.maximum.accumulate(equity)
        dd = peak - equity
        max_dd = np.max(dd) if len(dd) > 0 else 0.0
        romad = (net_profit / max_dd) if max_dd > 0 else 0.0
        df_c = pd.DataFrame(combined_trades_279)
        m_pnl = df_c.groupby("month")["pnl"].sum()
        mcr = (np.sum(m_pnl > 0) / len(m_pnl) * 100.0) if len(m_pnl) > 0 else 0.0

        res_279 = {
            "strategy_id": "S279",
            "strategy_name": "Multi-TF Tactical Duo: M15 Supertrend + M5 Fast RSI",
            "total_trades": len(combined_trades_279),
            "annual_trades": round(len(combined_trades_279) / 6.0, 1),
            "net_profit": round(float(net_profit), 2),
            "pf": round(float(pf), 3),
            "win_rate": round(float(win_rate), 2),
            "max_dd": round(float(max_dd), 2),
            "romad": round(float(romad), 2),
            "mcr": round(float(mcr), 2),
            "status": "CHAMPION" if pf >= 1.20 else ("TACTICAL CANDIDATE" if net_profit > 0 else "REJECTED")
        }
    else:
        res_279 = {"strategy_id": "S279", "strategy_name": "Multi-TF Tactical Duo", "annual_trades": 0, "net_profit": 0, "pf": 0, "win_rate": 0, "max_dd": 0, "romad": 0, "mcr": 0, "status": "REJECTED"}
    results.append(res_279)

    # -------------------------------------------------------------------------
    # S280: Multi-TF Sovereign Scalper: M15 Core + S271 M5 RSI + S275 M5 FVG
    # -------------------------------------------------------------------------
    print("Evaluating S280: Multi-TF Sovereign Scalper Ensemble...")
    trades_275 = res_275["trades"]
    combined_trades_280 = trades_271 + trades_275 + res_m15_core["trades"]
    if combined_trades_280:
        pnls = np.array([t["pnl"] for t in combined_trades_280])
        net_profit = np.sum(pnls)
        gross_win = np.sum(pnls[pnls > 0])
        gross_loss = abs(np.sum(pnls[pnls < 0]))
        pf = (gross_win / gross_loss) if gross_loss > 0 else 0.0
        win_rate = (len(pnls[pnls > 0]) / len(pnls)) * 100.0
        equity = np.cumsum(pnls)
        peak = np.maximum.accumulate(equity)
        dd = peak - equity
        max_dd = np.max(dd) if len(dd) > 0 else 0.0
        romad = (net_profit / max_dd) if max_dd > 0 else 0.0
        df_c = pd.DataFrame(combined_trades_280)
        m_pnl = df_c.groupby("month")["pnl"].sum()
        mcr = (np.sum(m_pnl > 0) / len(m_pnl) * 100.0) if len(m_pnl) > 0 else 0.0

        res_280 = {
            "strategy_id": "S280",
            "strategy_name": "Multi-TF Sovereign Scalper: M15 Core + M5 RSI + M5 FVG",
            "total_trades": len(combined_trades_280),
            "annual_trades": round(len(combined_trades_280) / 6.0, 1),
            "net_profit": round(float(net_profit), 2),
            "pf": round(float(pf), 3),
            "win_rate": round(float(win_rate), 2),
            "max_dd": round(float(max_dd), 2),
            "romad": round(float(romad), 2),
            "mcr": round(float(mcr), 2),
            "status": "CHAMPION" if pf >= 1.20 else ("TACTICAL CANDIDATE" if net_profit > 0 else "REJECTED")
        }
    else:
        res_280 = {"strategy_id": "S280", "strategy_name": "Multi-TF Sovereign Scalper", "annual_trades": 0, "net_profit": 0, "pf": 0, "win_rate": 0, "max_dd": 0, "romad": 0, "mcr": 0, "status": "REJECTED"}
    results.append(res_280)

    # -------------------------------------------------------------------------
    # Format & Export Results
    # -------------------------------------------------------------------------
    for r in results:
        if "trades" in r:
            del r["trades"]

    df_out = pd.DataFrame(results)
    csv_path = os.path.join(RESULTS_DIR, "massive_scalping_mtf_hybrid_batch_271_280_matrix.csv")
    json_path = os.path.join(RESULTS_DIR, "massive_scalping_mtf_hybrid_batch_271_280_results.json")

    df_out.to_csv(csv_path, index=False)
    with open(json_path, "w") as f:
        json.dump({"generated_at": time.strftime("%Y-%m-%d %H:%M:%S"), "total_runtime_s": round(time.time() - t0, 2), "results": results}, f, indent=2)

    print("\n" + "=" * 80)
    print("BATCH 8 (S271 - S280) EXECUTION COMPLETED IN {:.2f}s".format(time.time() - t0))
    print("=" * 80)
    print(df_out[["strategy_id", "strategy_name", "annual_trades", "net_profit", "pf", "win_rate", "max_dd", "romad", "mcr", "status"]].to_string(index=False))
    print("=" * 80)

if __name__ == "__main__":
    main()
