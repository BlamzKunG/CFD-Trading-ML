#!/usr/bin/env python3
"""
===============================================================================
SCALPING ALPHA BATCH 9: STRATEGIES 281 - 290
CRACKING THE 300 - 800 TRADES/YR BARRIER:
VOLATILITY-GATED M5 SESSION SCALPERS & M15 HIGH-FREQUENCY COMPOSITES
===============================================================================
Key Breakthrough Questions:
1. Can M5 scalping achieve positive net expectancy if constrained strictly to:
   - High-liquidity sessions (London/NY: 07:00 - 17:00 UTC)
   - Expanded Volatility Gate (M5 ATR >= $1.80) to neutralize friction?
2. Can M15 high-turnover engines (Donchian Pulse, Fast Supertrend, Momentum Cross)
   be combined into a resilient 400 - 750 trades/year scalping ensemble?

Execution Frictions:
- Spread: $0.25 ($25.00 / lot)
- Commission: $6.00 / lot ($0.60 / 0.10 lot)
- Zero Look-Ahead Bias: Next-bar open execution with full slippage buffer.
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
# Fast Scalping Simulator
# -----------------------------------------------------------------------------
def run_scalper(opens, highs, lows, closes, atr, bull_sigs, bear_sigs, months,
                exit_mode="ratchet_trailing", trailing_mult=3.0, sl_mult=1.5,
                tp_mult=3.5, max_hold=48, min_atr_gate=0.0,
                spread_pts=0.25, comm_dollars=0.60):
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

    for i in range(50, n - 1):
        if in_pos:
            hit_exit = False
            exit_price = 0.0

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

            if not hit_exit and (i - entry_idx) >= max_hold:
                hit_exit = True
                exit_price = (opens[i] - spread_pts) if (pos_type == 1) else opens[i]

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

        if not in_pos:
            if min_atr_gate > 0.0 and atr[i] < min_atr_gate:
                continue

            if bull_sigs[i]:
                in_pos = True
                pos_type = 1
                entry_idx = i + 1
                entry_price = opens[i + 1] + spread_pts
                extreme_price = entry_price
                stop_price = entry_price - (sl_mult * atr[i])
                if exit_mode == "fixed_rr":
                    target_price = entry_price + (tp_mult * atr[i])

            elif bear_sigs[i]:
                in_pos = True
                pos_type = -1
                entry_idx = i + 1
                entry_price = opens[i + 1]
                extreme_price = entry_price
                stop_price = entry_price + (sl_mult * atr[i])
                if exit_mode == "fixed_rr":
                    target_price = entry_price - (tp_mult * atr[i])

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
    print("STARTING SCALPING ALPHA BATCH 9: STRATEGIES 281 - 290")
    print("VOLATILITY-GATED M5 SESSION SCALPERS & M15 HIGH-FREQUENCY COMPOSITES")
    print("=" * 80)
    t0 = time.time()

    # 1. Load M5 and M15 Parquet Data
    print("Loading Parquet data...")
    df_m5 = pd.read_parquet(os.path.join(DATA_DIR, "XAUUSD_M5.parquet"))
    df_m15 = pd.read_parquet(os.path.join(DATA_DIR, "XAUUSD_M15.parquet"))

    m5_opens = df_m5["open"].values.astype(np.float64)
    m5_highs = df_m5["high"].values.astype(np.float64)
    m5_lows = df_m5["low"].values.astype(np.float64)
    m5_closes = df_m5["close"].values.astype(np.float64)
    m5_vols = df_m5["tick_volume"].values.astype(np.float64) if "tick_volume" in df_m5.columns else np.ones(len(m5_closes))
    m5_dates = df_m5.index
    m5_months = np.array([f"{d.year}-{d.month:02d}" for d in m5_dates])
    m5_hours = np.array([d.hour for d in m5_dates])
    n5 = len(m5_closes)

    m15_opens = df_m15["open"].values.astype(np.float64)
    m15_highs = df_m15["high"].values.astype(np.float64)
    m15_lows = df_m15["low"].values.astype(np.float64)
    m15_closes = df_m15["close"].values.astype(np.float64)
    m15_dates = df_m15.index
    m15_months = np.array([f"{d.year}-{d.month:02d}" for d in m15_dates])
    n15 = len(m15_closes)

    # Technical Indicators on M5
    print("Computing M5 indicators...")
    m5_atr14 = compute_atr(m5_highs, m5_lows, m5_closes, 14)
    m5_rsi5 = compute_rsi(m5_closes, 5)
    m5_trend, m5_st = compute_supertrend(m5_highs, m5_lows, m5_closes, 14, 3.0)
    m5_vol_sma = compute_ema(m5_vols, 20)

    # Technical Indicators on M15
    print("Computing M15 indicators...")
    m15_atr14 = compute_atr(m15_highs, m15_lows, m15_closes, 14)
    m15_ema9 = compute_ema(m15_closes, 9)
    m15_ema21 = compute_ema(m15_closes, 21)
    m15_ema150 = compute_ema(m15_closes, 150)
    m15_trend_fast, _ = compute_supertrend(m15_highs, m15_lows, m15_closes, 12, 2.8)
    m15_trend_core, _ = compute_supertrend(m15_highs, m15_lows, m15_closes, 14, 3.0)
    m15_rsi5 = compute_rsi(m15_closes, 5)

    # M15 Donchian High/Low 20
    m15_donchian_high = pd.Series(m15_highs).rolling(20).max().shift(1).fillna(99999).values
    m15_donchian_low = pd.Series(m15_lows).rolling(20).min().shift(1).fillna(0).values

    results = []

    # -------------------------------------------------------------------------
    # S281: M5 Supertrend Scalper (London/NY Session 07-17 UTC + ATR >= $1.80 Gate)
    # -------------------------------------------------------------------------
    print("Evaluating S281: M5 Supertrend Scalper (Session + ATR >= $1.80 Gate)...")
    bull_sigs = np.zeros(n5, dtype=bool)
    bear_sigs = np.zeros(n5, dtype=bool)
    for i in range(1, n5):
        if (7 <= m5_hours[i] <= 17) and m5_atr14[i] >= 1.80:
            if m5_trend[i - 1] == -1 and m5_trend[i] == 1:
                bull_sigs[i] = True
            elif m5_trend[i - 1] == 1 and m5_trend[i] == -1:
                bear_sigs[i] = True

    res_281 = run_scalper(m5_opens, m5_highs, m5_lows, m5_closes, m5_atr14,
                          bull_sigs, bear_sigs, m5_months,
                          exit_mode="ratchet_trailing", trailing_mult=3.0, sl_mult=1.5)
    res_281["strategy_id"] = "S281"
    res_281["strategy_name"] = "M5 Supertrend Scalper (Session + ATR >= $1.80)"
    res_281["status"] = "CHAMPION" if res_281["pf"] >= 1.20 else ("TACTICAL CANDIDATE" if res_281["net_profit"] > 0 else "REJECTED")
    results.append(res_281)

    # -------------------------------------------------------------------------
    # S282: M5 Fast RSI Dip Scalper (Session + ATR >= $1.80 Gate)
    # -------------------------------------------------------------------------
    print("Evaluating S282: M5 Fast RSI Dip Scalper (Session + ATR >= $1.80 Gate)...")
    bull_sigs = np.zeros(n5, dtype=bool)
    bear_sigs = np.zeros(n5, dtype=bool)
    for i in range(1, n5):
        if (7 <= m5_hours[i] <= 17) and m5_atr14[i] >= 1.80:
            if m5_rsi5[i - 1] < 20 and m5_rsi5[i] >= 20:
                bull_sigs[i] = True
            elif m5_rsi5[i - 1] > 80 and m5_rsi5[i] <= 80:
                bear_sigs[i] = True

    res_282 = run_scalper(m5_opens, m5_highs, m5_lows, m5_closes, m5_atr14,
                          bull_sigs, bear_sigs, m5_months,
                          exit_mode="fixed_rr", sl_mult=1.2, tp_mult=3.0, max_hold=18)
    res_282["strategy_id"] = "S282"
    res_282["strategy_name"] = "M5 Fast RSI Dip (Session + ATR >= $1.80)"
    res_282["status"] = "CHAMPION" if res_282["pf"] >= 1.20 else ("TACTICAL CANDIDATE" if res_282["net_profit"] > 0 else "REJECTED")
    results.append(res_282)

    # -------------------------------------------------------------------------
    # S283: M5 Volume Spike Momentum Scalper (Vol > 2.0x SMA + ATR >= $1.80)
    # -------------------------------------------------------------------------
    print("Evaluating S283: M5 Volume Spike Momentum Scalper...")
    bull_sigs = np.zeros(n5, dtype=bool)
    bear_sigs = np.zeros(n5, dtype=bool)
    for i in range(1, n5):
        if (7 <= m5_hours[i] <= 17) and m5_atr14[i] >= 1.80 and m5_vols[i] >= 2.0 * m5_vol_sma[i]:
            if m5_closes[i] > m5_opens[i] + 0.5 * m5_atr14[i]:
                bull_sigs[i] = True
            elif m5_opens[i] > m5_closes[i] + 0.5 * m5_atr14[i]:
                bear_sigs[i] = True

    res_283 = run_scalper(m5_opens, m5_highs, m5_lows, m5_closes, m5_atr14,
                          bull_sigs, bear_sigs, m5_months,
                          exit_mode="ratchet_trailing", trailing_mult=2.5, sl_mult=1.5)
    res_283["strategy_id"] = "S283"
    res_283["strategy_name"] = "M5 Volume Spike Scalper (Vol > 2x + ATR >= $1.80)"
    res_283["status"] = "CHAMPION" if res_283["pf"] >= 1.20 else ("TACTICAL CANDIDATE" if res_283["net_profit"] > 0 else "REJECTED")
    results.append(res_283)

    # -------------------------------------------------------------------------
    # S284: M15 Supertrend Ratchet Fast (ATR 12, Mult 2.8, EMA 150)
    # -------------------------------------------------------------------------
    print("Evaluating S284: M15 Supertrend Ratchet Fast...")
    bull_sigs = np.zeros(n15, dtype=bool)
    bear_sigs = np.zeros(n15, dtype=bool)
    for i in range(1, n15):
        if m15_trend_fast[i - 1] == -1 and m15_trend_fast[i] == 1 and m15_closes[i] > m15_ema150[i]:
            bull_sigs[i] = True
        elif m15_trend_fast[i - 1] == 1 and m15_trend_fast[i] == -1 and m15_closes[i] < m15_ema150[i]:
            bear_sigs[i] = True

    res_284 = run_scalper(m15_opens, m15_highs, m15_lows, m15_closes, m15_atr14,
                          bull_sigs, bear_sigs, m15_months,
                          exit_mode="ratchet_trailing", trailing_mult=2.8, sl_mult=1.5)
    res_284["strategy_id"] = "S284"
    res_284["strategy_name"] = "M15 Supertrend Fast (ATR 12, Mult 2.8, EMA 150)"
    res_284["status"] = "CHAMPION" if res_284["pf"] >= 1.20 else ("TACTICAL CANDIDATE" if res_284["net_profit"] > 0 else "REJECTED")
    results.append(res_284)

    # -------------------------------------------------------------------------
    # S285: M15 Donchian Pulse Scalper (20-bar Breakout with Ratchet Exit)
    # -------------------------------------------------------------------------
    print("Evaluating S285: M15 Donchian Pulse Scalper...")
    bull_sigs = np.zeros(n15, dtype=bool)
    bear_sigs = np.zeros(n15, dtype=bool)
    for i in range(20, n15):
        if m15_closes[i] > m15_donchian_high[i]:
            bull_sigs[i] = True
        elif m15_closes[i] < m15_donchian_low[i]:
            bear_sigs[i] = True

    res_285 = run_scalper(m15_opens, m15_highs, m15_lows, m15_closes, m15_atr14,
                          bull_sigs, bear_sigs, m15_months,
                          exit_mode="ratchet_trailing", trailing_mult=3.0, sl_mult=1.5)
    res_285["strategy_id"] = "S285"
    res_285["strategy_name"] = "M15 Donchian Pulse Scalper (20-bar Ratchet)"
    res_285["status"] = "CHAMPION" if res_285["pf"] >= 1.20 else ("TACTICAL CANDIDATE" if res_285["net_profit"] > 0 else "REJECTED")
    results.append(res_285)

    # -------------------------------------------------------------------------
    # S286: M15 EMA 9/21 Ribbon Cross Scalper
    # -------------------------------------------------------------------------
    print("Evaluating S286: M15 EMA 9/21 Ribbon Cross Scalper...")
    bull_sigs = np.zeros(n15, dtype=bool)
    bear_sigs = np.zeros(n15, dtype=bool)
    for i in range(1, n15):
        if m15_ema9[i - 1] <= m15_ema21[i - 1] and m15_ema9[i] > m15_ema21[i]:
            bull_sigs[i] = True
        elif m15_ema9[i - 1] >= m15_ema21[i - 1] and m15_ema9[i] < m15_ema21[i]:
            bear_sigs[i] = True

    res_286 = run_scalper(m15_opens, m15_highs, m15_lows, m15_closes, m15_atr14,
                          bull_sigs, bear_sigs, m15_months,
                          exit_mode="ratchet_trailing", trailing_mult=3.0, sl_mult=1.5)
    res_286["strategy_id"] = "S286"
    res_286["strategy_name"] = "M15 EMA 9/21 Cross Scalper (Ratchet Trailing)"
    res_286["status"] = "CHAMPION" if res_286["pf"] >= 1.20 else ("TACTICAL CANDIDATE" if res_286["net_profit"] > 0 else "REJECTED")
    results.append(res_286)

    # -------------------------------------------------------------------------
    # S287: M15 Fast RSI Snapshot Scalper (Oversold Dip 20 / Overbought 80)
    # -------------------------------------------------------------------------
    print("Evaluating S287: M15 Fast RSI Snapshot Scalper...")
    bull_sigs = np.zeros(n15, dtype=bool)
    bear_sigs = np.zeros(n15, dtype=bool)
    for i in range(1, n15):
        if m15_rsi5[i - 1] < 20 and m15_rsi5[i] >= 20:
            bull_sigs[i] = True
        elif m15_rsi5[i - 1] > 80 and m15_rsi5[i] <= 80:
            bear_sigs[i] = True

    res_287 = run_scalper(m15_opens, m15_highs, m15_lows, m15_closes, m15_atr14,
                          bull_sigs, bear_sigs, m15_months,
                          exit_mode="fixed_rr", sl_mult=1.2, tp_mult=3.0, max_hold=16)
    res_287["strategy_id"] = "S287"
    res_287["strategy_name"] = "M15 Fast RSI Snapshot Scalper (3.0:1.2 RR)"
    res_287["status"] = "CHAMPION" if res_287["pf"] >= 1.20 else ("TACTICAL CANDIDATE" if res_287["net_profit"] > 0 else "REJECTED")
    results.append(res_287)

    # -------------------------------------------------------------------------
    # S288: M15 Tactical Duo Scalper (S284 Fast Supertrend + S287 Fast RSI)
    # -------------------------------------------------------------------------
    print("Evaluating S288: M15 Tactical Duo Ensemble...")
    trades_288 = res_284["trades"] + res_287["trades"]
    if trades_288:
        pnls = np.array([t["pnl"] for t in trades_288])
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
        df_c = pd.DataFrame(trades_288)
        m_pnl = df_c.groupby("month")["pnl"].sum()
        mcr = (np.sum(m_pnl > 0) / len(m_pnl) * 100.0) if len(m_pnl) > 0 else 0.0

        res_288 = {
            "strategy_id": "S288",
            "strategy_name": "M15 Tactical Duo (Fast Supertrend + Fast RSI)",
            "total_trades": len(trades_288),
            "annual_trades": round(len(trades_288) / 6.0, 1),
            "net_profit": round(float(net_profit), 2),
            "pf": round(float(pf), 3),
            "win_rate": round(float(win_rate), 2),
            "max_dd": round(float(max_dd), 2),
            "romad": round(float(romad), 2),
            "mcr": round(float(mcr), 2),
            "status": "CHAMPION" if pf >= 1.20 else ("TACTICAL CANDIDATE" if net_profit > 0 else "REJECTED")
        }
    else:
        res_288 = {"strategy_id": "S288", "strategy_name": "M15 Tactical Duo", "annual_trades": 0, "net_profit": 0, "pf": 0, "win_rate": 0, "max_dd": 0, "romad": 0, "mcr": 0, "status": "REJECTED"}
    results.append(res_288)

    # -------------------------------------------------------------------------
    # S289: M15 Tri-Force Scalper (S284 Supertrend + S287 RSI + S285 Donchian)
    # -------------------------------------------------------------------------
    print("Evaluating S289: M15 Tri-Force Scalper Ensemble...")
    trades_289 = res_284["trades"] + res_287["trades"] + res_285["trades"]
    if trades_289:
        pnls = np.array([t["pnl"] for t in trades_289])
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
        df_c = pd.DataFrame(trades_289)
        m_pnl = df_c.groupby("month")["pnl"].sum()
        mcr = (np.sum(m_pnl > 0) / len(m_pnl) * 100.0) if len(m_pnl) > 0 else 0.0

        res_289 = {
            "strategy_id": "S289",
            "strategy_name": "M15 Tri-Force Scalper (Supertrend + RSI + Donchian)",
            "total_trades": len(trades_289),
            "annual_trades": round(len(trades_289) / 6.0, 1),
            "net_profit": round(float(net_profit), 2),
            "pf": round(float(pf), 3),
            "win_rate": round(float(win_rate), 2),
            "max_dd": round(float(max_dd), 2),
            "romad": round(float(romad), 2),
            "mcr": round(float(mcr), 2),
            "status": "CHAMPION" if pf >= 1.20 else ("TACTICAL CANDIDATE" if net_profit > 0 else "REJECTED")
        }
    else:
        res_289 = {"strategy_id": "S289", "strategy_name": "M15 Tri-Force Scalper", "annual_trades": 0, "net_profit": 0, "pf": 0, "win_rate": 0, "max_dd": 0, "romad": 0, "mcr": 0, "status": "REJECTED"}
    results.append(res_289)

    # -------------------------------------------------------------------------
    # S290: Mega-Scalper Quadrant (S284 Supertrend + S287 RSI + S285 Donchian + S286 EMA)
    # -------------------------------------------------------------------------
    print("Evaluating S290: Mega-Scalper Quadrant Ensemble...")
    trades_290 = res_284["trades"] + res_287["trades"] + res_285["trades"] + res_286["trades"]
    if trades_290:
        pnls = np.array([t["pnl"] for t in trades_290])
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
        df_c = pd.DataFrame(trades_290)
        m_pnl = df_c.groupby("month")["pnl"].sum()
        mcr = (np.sum(m_pnl > 0) / len(m_pnl) * 100.0) if len(m_pnl) > 0 else 0.0

        res_290 = {
            "strategy_id": "S290",
            "strategy_name": "Mega-Scalper Quadrant Ensemble (Supertrend+RSI+Donch+EMA)",
            "total_trades": len(trades_290),
            "annual_trades": round(len(trades_290) / 6.0, 1),
            "net_profit": round(float(net_profit), 2),
            "pf": round(float(pf), 3),
            "win_rate": round(float(win_rate), 2),
            "max_dd": round(float(max_dd), 2),
            "romad": round(float(romad), 2),
            "mcr": round(float(mcr), 2),
            "status": "CHAMPION" if pf >= 1.20 else ("TACTICAL CANDIDATE" if net_profit > 0 else "REJECTED")
        }
    else:
        res_290 = {"strategy_id": "S290", "strategy_name": "Mega-Scalper Quadrant", "annual_trades": 0, "net_profit": 0, "pf": 0, "win_rate": 0, "max_dd": 0, "romad": 0, "mcr": 0, "status": "REJECTED"}
    results.append(res_290)

    # -------------------------------------------------------------------------
    # Format & Export Results
    # -------------------------------------------------------------------------
    for r in results:
        if "trades" in r:
            del r["trades"]

    df_out = pd.DataFrame(results)
    csv_path = os.path.join(RESULTS_DIR, "massive_scalping_expansion_batch_281_290_matrix.csv")
    json_path = os.path.join(RESULTS_DIR, "massive_scalping_expansion_batch_281_290_results.json")

    df_out.to_csv(csv_path, index=False)
    with open(json_path, "w") as f:
        json.dump({"generated_at": time.strftime("%Y-%m-%d %H:%M:%S"), "total_runtime_s": round(time.time() - t0, 2), "results": results}, f, indent=2)

    print("\n" + "=" * 80)
    print("BATCH 9 (S281 - S290) EXECUTION COMPLETED IN {:.2f}s".format(time.time() - t0))
    print("=" * 80)
    print(df_out[["strategy_id", "strategy_name", "annual_trades", "net_profit", "pf", "win_rate", "max_dd", "romad", "mcr", "status"]].to_string(index=False))
    print("=" * 80)

if __name__ == "__main__":
    main()
