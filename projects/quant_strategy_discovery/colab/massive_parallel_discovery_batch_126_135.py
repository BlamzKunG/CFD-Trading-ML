#!/usr/bin/env python3
"""
===============================================================================
MASSIVE PARALLEL DISCOVERY BATCH: WAVE C (STRATEGIES 126–135)
===============================================================================
Execution Platform: Google Colab Cloud VM (x86_64, High-RAM Architecture)
Dataset: XAUUSD H1 (Gold CFD, 72 Calendar Months: 2020-01-01 to 2025-12-30)
Simulation Engine: Institutional Event-Driven Bar-by-Bar Vectorized Runner
Transaction Costs: Spread 0.25 pts ($2.50/lot), Commission $0.60/lot ($0.06/0.1lot)
Risk Governance: ASAR Monthly Profit Lock ($200) & Monthly Loss Breaker ($250)

Strategies in Batch:
  - S126: Heikin-Ashi Volatility Delta Smoothed Trend (HAS-VD)
  - S127: Kaufman Adaptive Envelope Volatility Expansion (KAE-VE)
  - S128: Money Flow Index Volume Divergence & Ignition (MFI-IGN)
  - S129: Rate of Change Zero-Lag Band Breakout (ROC-ZL)
  - S130: Variable Index Dynamic Average Adaptive Filter (VIDYA-AF)
  - S131: Ehlers Decycler High-Pass Volatility Detrender (E-DECYC)
  - S132: Fractal Chaos Bands Breakout Extension (FCB-EXT)
  - S133: Dynamic Momentum Index Variable Period Explosion (DMI-EXP)
  - S134: Range Action Verification Index Trend Break (RAVI-TB)
  - S135: Price Volume Trend Volume Flow Acceleration (PVT-ACC)
===============================================================================
"""

import os
import sys
import time
import json
import numpy as np
import pandas as pd

REPO_ROOT = "/content/CFD-Trading-ML"
DATA_DIR = os.path.join(REPO_ROOT, "projects/quant_strategy_discovery/data")
OUT_DIR = os.path.join(REPO_ROOT, "projects/quant_strategy_discovery/results")

if not os.path.exists(DATA_DIR):
    if os.path.exists("projects/quant_strategy_discovery/data"):
        DATA_DIR = "projects/quant_strategy_discovery/data"
    elif os.path.exists("/root/CFD-Trading-ML/projects/quant_strategy_discovery/data"):
        DATA_DIR = "/root/CFD-Trading-ML/projects/quant_strategy_discovery/data"

if not os.path.exists(OUT_DIR):
    os.makedirs(OUT_DIR, exist_ok=True)

# ---------------------------------------------------------
# TECHNICAL INDICATOR COMPUTATIONS
# ---------------------------------------------------------
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

def compute_katz_fractal_dimension(closes: np.ndarray, period: int = 24) -> np.ndarray:
    n = len(closes)
    kfd = np.full(n, 1.5, dtype=np.float64)
    for i in range(period, n):
        window = closes[i - period:i + 1]
        ll = np.sum(np.abs(np.diff(window)))
        d = np.max(np.abs(window - window[0]))
        if ll > 0 and d > 0:
            k = np.log10(period) / (np.log10(period) + np.log10(d / ll))
            kfd[i] = max(1.0, min(2.0, k))
        else:
            kfd[i] = 1.5
    return kfd

# 1. Heikin-Ashi Volatility Delta
def compute_heikin_ashi(opens: np.ndarray, highs: np.ndarray, lows: np.ndarray, closes: np.ndarray):
    n = len(closes)
    ha_close = (opens + highs + lows + closes) / 4.0
    ha_open = np.zeros(n, dtype=np.float64)
    ha_open[0] = (opens[0] + closes[0]) / 2.0
    for i in range(1, n):
        ha_open[i] = (ha_open[i - 1] + ha_close[i - 1]) / 2.0
    ha_high = np.maximum(highs, np.maximum(ha_open, ha_close))
    ha_low = np.minimum(lows, np.minimum(ha_open, ha_close))
    return ha_open, ha_high, ha_low, ha_close

# 2. Kaufman Adaptive Moving Average (KAMA) & Efficiency Ratio (ER)
def compute_kama(closes: np.ndarray, period: int = 10, fast: int = 2, slow: int = 30):
    n = len(closes)
    kama = np.copy(closes)
    er = np.zeros(n, dtype=np.float64)
    sc_fast = 2.0 / (fast + 1)
    sc_slow = 2.0 / (slow + 1)
    for i in range(period, n):
        change = abs(closes[i] - closes[i - period])
        vol = np.sum(np.abs(np.diff(closes[i - period:i + 1])))
        eff = change / vol if vol > 1e-9 else 0.0
        er[i] = eff
        sc = (eff * (sc_fast - sc_slow) + sc_slow) ** 2
        kama[i] = kama[i - 1] + sc * (closes[i] - kama[i - 1])
    return kama, er

# 3. Money Flow Index (MFI)
def compute_mfi(highs: np.ndarray, lows: np.ndarray, closes: np.ndarray, volumes: np.ndarray, period: int = 14):
    n = len(closes)
    tp = (highs + lows + closes) / 3.0
    mf = tp * volumes
    pos_mf = np.zeros(n, dtype=np.float64)
    neg_mf = np.zeros(n, dtype=np.float64)
    for i in range(1, n):
        if tp[i] > tp[i - 1]:
            pos_mf[i] = mf[i]
        elif tp[i] < tp[i - 1]:
            neg_mf[i] = mf[i]
    mfi = np.full(n, 50.0, dtype=np.float64)
    for i in range(period, n):
        pos_sum = np.sum(pos_mf[i - period + 1:i + 1])
        neg_sum = np.sum(neg_mf[i - period + 1:i + 1])
        if neg_sum > 0:
            mr = pos_sum / neg_sum
            mfi[i] = 100.0 - (100.0 / (1.0 + mr))
        else:
            mfi[i] = 100.0 if pos_sum > 0 else 50.0
    return mfi

# 4. Normalized Rate of Change (ROC)
def compute_roc(closes: np.ndarray, period: int = 12):
    n = len(closes)
    roc = np.zeros(n, dtype=np.float64)
    for i in range(period, n):
        if closes[i - period] > 0:
            roc[i] = ((closes[i] - closes[i - period]) / closes[i - period]) * 100.0
    return roc

# 5. Variable Index Dynamic Average (VIDYA)
def compute_vidya(closes: np.ndarray, cmo_period: int = 9, ema_period: int = 21):
    n = len(closes)
    # CMO calculation
    diff = np.diff(closes, prepend=closes[0])
    gains = np.where(diff > 0, diff, 0.0)
    losses = np.where(diff < 0, -diff, 0.0)
    g_sum = pd.Series(gains).rolling(cmo_period).sum().values
    l_sum = pd.Series(losses).rolling(cmo_period).sum().values
    total = g_sum + l_sum
    cmo = np.where(total > 0, 100.0 * (g_sum - l_sum) / total, 0.0)
    
    vidya = np.copy(closes)
    alpha = 2.0 / (ema_period + 1.0)
    for i in range(1, n):
        k = abs(cmo[i]) / 100.0 * alpha
        vidya[i] = k * closes[i] + (1.0 - k) * vidya[i - 1]
    return vidya, cmo

# 6. Ehlers Decycler
def compute_ehlers_decycler(closes: np.ndarray, hp_period: int = 30):
    n = len(closes)
    alpha = (np.cos(np.radians(360.0 / hp_period)) + np.sin(np.radians(360.0 / hp_period)) - 1.0) / np.cos(np.radians(360.0 / hp_period))
    hp = np.zeros(n, dtype=np.float64)
    decycler = np.copy(closes)
    for i in range(2, n):
        hp[i] = (1.0 - alpha / 2.0) ** 2 * (closes[i] - 2 * closes[i - 1] + closes[i - 2]) + 2 * (1.0 - alpha) * hp[i - 1] - (1.0 - alpha) ** 2 * hp[i - 2]
        decycler[i] = closes[i] - hp[i]
    return decycler

# 7. Fractal Chaos Bands (FCB)
def compute_fcb(highs: np.ndarray, lows: np.ndarray, lookback: int = 24):
    n = len(highs)
    fcb_high = pd.Series(highs).rolling(lookback).max().shift(1).fillna(highs[0]).values
    fcb_low = pd.Series(lows).rolling(lookback).min().shift(1).fillna(lows[0]).values
    return fcb_high, fcb_low

# 8. Dynamic Momentum Index (DMI)
def compute_dmi(closes: np.ndarray, std_period: int = 5, avg_period: int = 14):
    n = len(closes)
    std = pd.Series(closes).rolling(std_period).std().fillna(1.0).values
    avg_std = pd.Series(std).rolling(avg_period).mean().fillna(1.0).values
    ratio = np.where(avg_std > 0, std / avg_std, 1.0)
    rsi_period = np.clip(np.round(14 / ratio).astype(int), 5, 30)
    
    dmi = np.full(n, 50.0, dtype=np.float64)
    diff = np.diff(closes, prepend=closes[0])
    gains = np.where(diff > 0, diff, 0.0)
    losses = np.where(diff < 0, -diff, 0.0)
    for i in range(35, n):
        p = rsi_period[i]
        g = np.mean(gains[i - p + 1:i + 1])
        l = np.mean(losses[i - p + 1:i + 1])
        if l > 0:
            rs = g / l
            dmi[i] = 100.0 - (100.0 / (1.0 + rs))
        else:
            dmi[i] = 100.0 if g > 0 else 50.0
    return dmi

# 9. Range Action Verification Index (RAVI)
def compute_ravi(closes: np.ndarray, fast_p: int = 7, slow_p: int = 65):
    sma_fast = pd.Series(closes).rolling(fast_p).mean().values
    sma_slow = pd.Series(closes).rolling(slow_p).mean().values
    ravi = np.where(sma_slow > 0, 100.0 * (sma_fast - sma_slow) / sma_slow, 0.0)
    return ravi

# 10. Price Volume Trend (PVT)
def compute_pvt(closes: np.ndarray, volumes: np.ndarray, ema_p: int = 14):
    n = len(closes)
    pvt = np.zeros(n, dtype=np.float64)
    for i in range(1, n):
        if closes[i - 1] > 0:
            ret = (closes[i] - closes[i - 1]) / closes[i - 1]
            pvt[i] = pvt[i - 1] + (ret * volumes[i])
        else:
            pvt[i] = pvt[i - 1]
    pvt_ema = compute_ema(pvt, ema_p)
    return pvt, pvt_ema


# ---------------------------------------------------------
# GENERIC VECTORIZED EXECUTION RUNNER
# ---------------------------------------------------------
def simulate_strategy_signals(opens, highs, lows, closes, atr, bull_signals, bear_signals,
                              months, dates, strategy_name, tp_mult=4.5, sl_mult=2.0,
                              plock=200.0, lbreak=250.0):
    n = len(closes)
    trades = []
    in_pos = False
    pos_type = 0
    entry_price = 0.0
    sl_price = 0.0
    tp_price = 0.0
    entry_idx = 0

    curr_m = months[0]
    m_pnl = 0.0
    m_locked = False

    spread_pts = 0.25
    comm_dollars = 0.60
    point_value = 100.0

    for i in range(200, n - 1):
        if months[i] != curr_m:
            curr_m = months[i]
            m_pnl = 0.0
            m_locked = False

        if in_pos:
            hit_tp = False
            hit_sl = False
            exit_price = 0.0

            if pos_type == 1:
                if lows[i] <= sl_price:
                    hit_sl = True
                    exit_price = sl_price
                elif highs[i] >= tp_price:
                    hit_tp = True
                    exit_price = tp_price
            elif pos_type == -1:
                if highs[i] >= sl_price:
                    hit_sl = True
                    exit_price = sl_price
                elif lows[i] <= tp_price:
                    hit_tp = True
                    exit_price = tp_price

            if hit_tp or hit_sl:
                if pos_type == 1:
                    pnl = (exit_price - entry_price) * point_value - comm_dollars
                else:
                    pnl = (entry_price - exit_price) * point_value - comm_dollars

                trades.append({
                    "entry_idx": entry_idx, "exit_idx": i,
                    "pos_type": pos_type, "entry_price": entry_price, "exit_price": exit_price,
                    "pnl": pnl, "month": months[entry_idx], "date": pd.to_datetime(dates[i]),
                    "strategy": strategy_name
                })
                m_pnl += pnl
                if m_pnl >= plock or m_pnl <= -lbreak:
                    m_locked = True
                in_pos = False
                continue

        if not in_pos and not m_locked:
            bull_sig = bull_signals[i]
            bear_sig = bear_signals[i]

            atr_val = atr[i]
            if bull_sig:
                in_pos = True
                pos_type = 1
                entry_idx = i + 1
                entry_price = opens[i + 1] + spread_pts
                sl_price = entry_price - (sl_mult * atr_val)
                tp_price = entry_price + (tp_mult * atr_val)
            elif bear_sig:
                in_pos = True
                pos_type = -1
                entry_idx = i + 1
                entry_price = opens[i + 1]
                sl_price = entry_price + (sl_mult * atr_val)
                tp_price = entry_price - (tp_mult * atr_val)

    return trades

def evaluate_metrics(trades, label="Strategy"):
    if len(trades) == 0:
        return {
            "label": label, "total_trades": 0, "net_profit": 0.0, "pf": 0.0,
            "win_rate": 0.0, "max_dd": 0.0, "romad": 0.0, "mcr": 0.0,
            "pos_months": 0, "total_months": 72
        }
    df_tr = pd.DataFrame(trades)
    pnls = df_tr["pnl"].values
    net_profit = float(np.sum(pnls))
    wins = pnls[pnls > 0]
    losses = pnls[pnls < 0]
    gross_win = float(np.sum(wins)) if len(wins) > 0 else 0.0
    gross_loss = float(abs(np.sum(losses))) if len(losses) > 0 else 1e-4
    pf = float(gross_win / gross_loss)
    win_rate = float(len(wins) / len(pnls) * 100.0)

    equity = np.cumsum(pnls)
    peak = np.maximum.accumulate(equity)
    dd = peak - equity
    max_dd = float(np.max(dd)) if len(dd) > 0 else 1e-4
    romad = float(net_profit / max_dd)

    m_pnl = df_tr.groupby("month")["pnl"].sum()
    pos_m = int((m_pnl > 0).sum())
    total_m = 72
    mcr = float(pos_m / total_m * 100.0)

    return {
        "label": label,
        "total_trades": len(trades),
        "net_profit": round(net_profit, 2),
        "pf": round(pf, 3),
        "win_rate": round(win_rate, 2),
        "max_dd": round(max_dd, 2),
        "romad": round(romad, 2),
        "mcr": round(mcr, 2),
        "pos_months": pos_m,
        "total_months": total_m
    }


def main():
    print("=" * 100, flush=True)
    print("MASSIVE PARALLEL DISCOVERY BATCH: WAVE C (STRATEGIES 126–135) EXECUTION", flush=True)
    print("=" * 100, flush=True)

    t0 = time.time()
    gold_path = os.path.join(DATA_DIR, "XAUUSD_H1.parquet")
    print(f"[*] Loading Gold H1 dataset from {gold_path}...", flush=True)
    df = pd.read_parquet(gold_path)
    
    opens = df["open"].values.astype(np.float64)
    highs = df["high"].values.astype(np.float64)
    lows = df["low"].values.astype(np.float64)
    closes = df["close"].values.astype(np.float64)
    volumes = df["tick_volume"].values.astype(np.float64)
    dates = df.index
    months = (dates.year.values * 100 + dates.month.values).astype(np.int32)
    n = len(closes)
    print(f"[*] Loaded {n} bars across 72 calendar months (2020-2025).", flush=True)

    atr14 = compute_atr(highs, lows, closes, 14)
    ema200 = compute_ema(closes, 200)
    kfd24 = compute_katz_fractal_dimension(closes, 24)
    trend_bull = closes > ema200
    trend_bear = closes < ema200

    results = []

    # -------------------------------------------------------------
    # S126: Heikin-Ashi Volatility Delta Smoothed Trend (HAS-VD)
    # -------------------------------------------------------------
    print("[*] Simulating S126: Heikin-Ashi Volatility Delta Smoothed Trend...", flush=True)
    ha_o, ha_h, ha_l, ha_c = compute_heikin_ashi(opens, highs, lows, closes)
    ha_delta = ha_c - ha_o
    s126_bull = (ha_delta > 0.4 * atr14) & trend_bull & (kfd24 <= 1.40)
    s126_bear = (ha_delta < -0.4 * atr14) & trend_bear & (kfd24 <= 1.40)
    tr_126 = simulate_strategy_signals(opens, highs, lows, closes, atr14, s126_bull, s126_bear,
                                       months, dates, "S126_HEIKIN_ASHI_VOLATILITY_DELTA", tp_mult=4.5, sl_mult=2.0)
    m_126 = evaluate_metrics(tr_126, "S126: Heikin-Ashi Volatility Delta Smoothed Trend")
    results.append(m_126)

    # -------------------------------------------------------------
    # S127: Kaufman Adaptive Envelope Volatility Expansion (KAE-VE)
    # -------------------------------------------------------------
    print("[*] Simulating S127: Kaufman Adaptive Envelope Volatility Expansion...", flush=True)
    kama10, er10 = compute_kama(closes, period=10)
    kae_up = kama10 + 1.2 * atr14
    kae_lo = kama10 - 1.2 * atr14
    s127_bull = (closes > kae_up) & (er10 >= 0.40) & trend_bull & (kfd24 <= 1.42)
    s127_bear = (closes < kae_lo) & (er10 >= 0.40) & trend_bear & (kfd24 <= 1.42)
    tr_127 = simulate_strategy_signals(opens, highs, lows, closes, atr14, s127_bull, s127_bear,
                                       months, dates, "S127_KAUFMAN_ADAPTIVE_ENVELOPE", tp_mult=4.0, sl_mult=2.5)
    m_127 = evaluate_metrics(tr_127, "S127: Kaufman Adaptive Envelope Volatility Expansion")
    results.append(m_127)

    # -------------------------------------------------------------
    # S128: Money Flow Index Volume Divergence & Ignition (MFI-IGN)
    # -------------------------------------------------------------
    print("[*] Simulating S128: Money Flow Index Volume Divergence & Ignition...", flush=True)
    mfi14 = compute_mfi(highs, lows, closes, volumes, period=14)
    s128_bull = (mfi14 > 55.0) & (pd.Series(mfi14 <= 55.0).shift(1).fillna(False).values) & trend_bull & (kfd24 <= 1.38)
    s128_bear = (mfi14 < 45.0) & (pd.Series(mfi14 >= 45.0).shift(1).fillna(False).values) & trend_bear & (kfd24 <= 1.38)
    tr_128 = simulate_strategy_signals(opens, highs, lows, closes, atr14, s128_bull, s128_bear,
                                       months, dates, "S128_MONEY_FLOW_INDEX_IGNITION", tp_mult=5.0, sl_mult=2.0)
    m_128 = evaluate_metrics(tr_128, "S128: Money Flow Index Volume Divergence & Ignition")
    results.append(m_128)

    # -------------------------------------------------------------
    # S129: Rate of Change Zero-Lag Band Breakout (ROC-ZL)
    # -------------------------------------------------------------
    print("[*] Simulating S129: Rate of Change Zero-Lag Band Breakout...", flush=True)
    roc12 = compute_roc(closes, period=12)
    roc_std = pd.Series(roc12).rolling(30).std().fillna(1.0).values
    norm_roc = np.where(roc_std > 0, roc12 / roc_std, 0.0)
    s129_bull = (norm_roc > 1.5) & trend_bull & (kfd24 <= 1.40)
    s129_bear = (norm_roc < -1.5) & trend_bear & (kfd24 <= 1.40)
    tr_129 = simulate_strategy_signals(opens, highs, lows, closes, atr14, s129_bull, s129_bear,
                                       months, dates, "S129_ROC_BAND_BREAKOUT", tp_mult=4.5, sl_mult=2.0)
    m_129 = evaluate_metrics(tr_129, "S129: Rate of Change Zero-Lag Band Breakout")
    results.append(m_129)

    # -------------------------------------------------------------
    # S130: Variable Index Dynamic Average Adaptive Filter (VIDYA-AF)
    # -------------------------------------------------------------
    print("[*] Simulating S130: Variable Index Dynamic Average Adaptive Filter...", flush=True)
    vidya21, cmo9 = compute_vidya(closes, cmo_period=9, ema_period=21)
    vidya_cross_up = (closes > vidya21) & (pd.Series(closes <= vidya21).shift(1).fillna(False).values)
    vidya_cross_dn = (closes < vidya21) & (pd.Series(closes >= vidya21).shift(1).fillna(False).values)
    s130_bull = vidya_cross_up & (cmo9 > 15.0) & trend_bull & (kfd24 <= 1.42)
    s130_bear = vidya_cross_dn & (cmo9 < -15.0) & trend_bear & (kfd24 <= 1.42)
    tr_130 = simulate_strategy_signals(opens, highs, lows, closes, atr14, s130_bull, s130_bear,
                                       months, dates, "S130_VIDYA_ADAPTIVE_FILTER", tp_mult=4.5, sl_mult=2.5)
    m_130 = evaluate_metrics(tr_130, "S130: Variable Index Dynamic Average Adaptive Filter")
    results.append(m_130)

    # -------------------------------------------------------------
    # S131: Ehlers Decycler High-Pass Volatility Detrender (E-DECYC)
    # -------------------------------------------------------------
    print("[*] Simulating S131: Ehlers Decycler High-Pass Volatility Detrender...", flush=True)
    decycler30 = compute_ehlers_decycler(closes, hp_period=30)
    dec_slope = decycler30 - pd.Series(decycler30).shift(1).fillna(decycler30[0]).values
    s131_bull = (dec_slope > 0) & (closes > decycler30) & trend_bull & (kfd24 <= 1.40)
    s131_bear = (dec_slope < 0) & (closes < decycler30) & trend_bear & (kfd24 <= 1.40)
    tr_131 = simulate_strategy_signals(opens, highs, lows, closes, atr14, s131_bull, s131_bear,
                                       months, dates, "S131_EHLERS_DECYCLER_TREND", tp_mult=4.5, sl_mult=2.0)
    m_131 = evaluate_metrics(tr_131, "S131: Ehlers Decycler High-Pass Volatility Detrender")
    results.append(m_131)

    # -------------------------------------------------------------
    # S132: Fractal Chaos Bands Breakout Extension (FCB-EXT)
    # -------------------------------------------------------------
    print("[*] Simulating S132: Fractal Chaos Bands Breakout Extension...", flush=True)
    fcb_h, fcb_l = compute_fcb(highs, lows, lookback=24)
    fcb_cross_up = (closes > fcb_h) & (pd.Series(closes <= fcb_h).shift(1).fillna(False).values)
    fcb_cross_dn = (closes < fcb_l) & (pd.Series(closes >= fcb_l).shift(1).fillna(False).values)
    s132_bull = fcb_cross_up & trend_bull & (kfd24 <= 1.38)
    s132_bear = fcb_cross_dn & trend_bear & (kfd24 <= 1.38)
    tr_132 = simulate_strategy_signals(opens, highs, lows, closes, atr14, s132_bull, s132_bear,
                                       months, dates, "S132_FRACTAL_CHAOS_BANDS", tp_mult=5.0, sl_mult=2.0)
    m_132 = evaluate_metrics(tr_132, "S132: Fractal Chaos Bands Breakout Extension")
    results.append(m_132)

    # -------------------------------------------------------------
    # S133: Dynamic Momentum Index Variable Period Explosion (DMI-EXP)
    # -------------------------------------------------------------
    print("[*] Simulating S133: Dynamic Momentum Index Variable Period Explosion...", flush=True)
    dmi_chande = compute_dmi(closes, std_period=5, avg_period=14)
    s133_bull = (dmi_chande > 55.0) & (pd.Series(dmi_chande <= 55.0).shift(1).fillna(False).values) & trend_bull & (kfd24 <= 1.40)
    s133_bear = (dmi_chande < 45.0) & (pd.Series(dmi_chande >= 45.0).shift(1).fillna(False).values) & trend_bear & (kfd24 <= 1.40)
    tr_133 = simulate_strategy_signals(opens, highs, lows, closes, atr14, s133_bull, s133_bear,
                                       months, dates, "S133_DYNAMIC_MOMENTUM_INDEX", tp_mult=4.5, sl_mult=2.5)
    m_133 = evaluate_metrics(tr_133, "S133: Dynamic Momentum Index Variable Period Explosion")
    results.append(m_133)

    # -------------------------------------------------------------
    # S134: Range Action Verification Index Trend Break (RAVI-TB)
    # -------------------------------------------------------------
    print("[*] Simulating S134: Range Action Verification Index Trend Break...", flush=True)
    ravi = compute_ravi(closes, fast_p=7, slow_p=65)
    ravi_diff = ravi - pd.Series(ravi).shift(1).fillna(0.0).values
    s134_bull = (ravi > 1.2) & (ravi_diff > 0) & trend_bull & (kfd24 <= 1.40)
    s134_bear = (ravi < -1.2) & (ravi_diff < 0) & trend_bear & (kfd24 <= 1.40)
    tr_134 = simulate_strategy_signals(opens, highs, lows, closes, atr14, s134_bull, s134_bear,
                                       months, dates, "S134_RAVI_TREND_BREAK", tp_mult=4.5, sl_mult=2.0)
    m_134 = evaluate_metrics(tr_134, "S134: Range Action Verification Index Trend Break")
    results.append(m_134)

    # -------------------------------------------------------------
    # S135: Price Volume Trend Volume Flow Acceleration (PVT-ACC)
    # -------------------------------------------------------------
    print("[*] Simulating S135: Price Volume Trend Volume Flow Acceleration...", flush=True)
    pvt, pvt_ema = compute_pvt(closes, volumes, ema_p=14)
    pvt_cross_up = (pvt > pvt_ema) & (pd.Series(pvt <= pvt_ema).shift(1).fillna(False).values)
    pvt_cross_dn = (pvt < pvt_ema) & (pd.Series(pvt >= pvt_ema).shift(1).fillna(False).values)
    s135_bull = pvt_cross_up & trend_bull & (kfd24 <= 1.40)
    s135_bear = pvt_cross_dn & trend_bear & (kfd24 <= 1.40)
    tr_135 = simulate_strategy_signals(opens, highs, lows, closes, atr14, s135_bull, s135_bear,
                                       months, dates, "S135_PRICE_VOLUME_TREND_FLOW", tp_mult=4.5, sl_mult=2.5)
    m_135 = evaluate_metrics(tr_135, "S135: Price Volume Trend Volume Flow Acceleration")
    results.append(m_135)

    print("\n" + "=" * 115, flush=True)
    print("MASSIVE PARALLEL DISCOVERY BATCH: WAVE C (S126–S135) RESULTS", flush=True)
    print("=" * 115, flush=True)
    print(f"{'Strategy Architecture':<55} | {'Trades':<7} | {'Net Profit':<12} | {'PF':<6} | {'Max DD':<9} | {'RoMaD':<6} | MCR", flush=True)
    print("-" * 115, flush=True)
    for m in results:
        print(f"{m['label']:<55} | {m['total_trades']:<7} | ${m['net_profit']:<11.2f} | {m['pf']:<6.3f} | ${m['max_dd']:<8.2f} | {m['romad']:<6.2f} | {m['mcr']:.1f}% ({m['pos_months']}/{m['total_months']})", flush=True)
    print("=" * 115, flush=True)

    out_file = os.path.join(OUT_DIR, "colab_batch_126_135_results.json")
    with open(out_file, "w") as f:
        json.dump({
            "batch": "WAVE_C",
            "strategies": results,
            "runtime_seconds": round(time.time() - t0, 2)
        }, f, indent=2)
    print(f"[+] Saved Wave C batch discovery results to {out_file}", flush=True)

if __name__ == "__main__":
    main()
