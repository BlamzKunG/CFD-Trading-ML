#!/usr/bin/env python3
"""
===============================================================================
MASSIVE PARALLEL SCALPING DISCOVERY BATCH: STRATEGIES 201 - 210
MULTI-TIMEFRAME MATRIX (M1, M5, M15) ON XAUUSD (2020-2025)
===============================================================================
Target Asset: XAUUSD (Gold)
Timeframes: M1, M5, M15 (Tested Simultaneously)
Frictions: Spread = $0.25 ($25.00/lot), Commission = $6.00/lot ($0.60/0.10 lot)
Target Annual Volume: ~300+ Trades/Year (Scalping Active Turnover)

Strategies Evaluated:
  - S201: Asian Liquidity Sweep & London Reversal Scalper
  - S202: Session Open Momentum & Volume Breakout Scalper
  - S203: Fast Bollinger Bandwidth Squeeze & Expansion
  - S204: EMA Ribbon Dynamic Pullback & Wick Rejection
  - S205: Fast RSI Extreme Mean-Reversion Scalper
  - S206: Keltner Channel Volatility Surge Breakout
  - S207: Microstructure Fair Value Gap (FVG) Retest
  - S208: Intraday VWAP Standard Deviation Scalper
  - S209: Fast Supertrend Micro-Trailing Scalper
  - S210: Candle Imbalance & High-Volume Pinbar Rejection
===============================================================================
"""

import os
import sys
import gc
import time
import json
import numpy as np
import pandas as pd

# Check local vs cloud path
if os.path.exists("/content/CFD-Trading-ML"):
    REPO_ROOT = "/content/CFD-Trading-ML"
else:
    REPO_ROOT = "/root/CFD-Trading-ML"

DATA_DIR = os.path.join(REPO_ROOT, "projects/quant_strategy_discovery/data")
RESULTS_DIR = os.path.join(REPO_ROOT, "projects/quant_strategy_discovery/results")

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

def compute_rsi(closes: np.ndarray, period: int = 7) -> np.ndarray:
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

def run_scalping_backtest(opens, highs, lows, closes, atr, bull_sigs, bear_sigs, months, dates,
                          tp_mult=2.0, sl_mult=1.5, max_bars_hold=30, spread_pts=0.25, comm_dollars=0.60):
    """
    High-fidelity scalping simulator with strict causality:
    - Entry at bar i+1 open + spread
    - Worst-case intrabar SL/TP collision
    - Time-stop (max_bars_hold) for fast capital recycling
    - Standard contract: 0.10 lot ($100 per point)
    """
    n = len(closes)
    trades = []
    in_pos = False
    pos_type = 0
    entry_price = 0.0
    sl_price = 0.0
    tp_price = 0.0
    entry_idx = 0
    point_value = 100.0

    for i in range(100, n - 1):
        if in_pos:
            hit_tp = False
            hit_sl = False
            exit_price = 0.0
            
            # Check holding period
            if (i - entry_idx) >= max_bars_hold:
                exit_price = opens[i]
                if pos_type == 1:
                    exit_price -= spread_pts
                    pnl = (exit_price - entry_price) * point_value - comm_dollars
                else:
                    pnl = (entry_price - exit_price) * point_value - comm_dollars
                trades.append({
                    "pnl": pnl, "month": months[entry_idx], "bars_held": i - entry_idx
                })
                in_pos = False
                continue

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
                    "pnl": pnl, "month": months[entry_idx], "bars_held": i - entry_idx
                })
                in_pos = False
                continue

        if not in_pos:
            atr_val = atr[i]
            if atr_val <= 0:
                continue
            if bull_sigs[i]:
                in_pos = True
                pos_type = 1
                entry_idx = i + 1
                entry_price = opens[i + 1] + spread_pts
                sl_price = entry_price - (sl_mult * atr_val)
                tp_price = entry_price + (tp_mult * atr_val)
            elif bear_sigs[i]:
                in_pos = True
                pos_type = -1
                entry_idx = i + 1
                entry_price = opens[i + 1]
                sl_price = entry_price + (sl_mult * atr_val)
                tp_price = entry_price - (tp_mult * atr_val)

    if not trades:
        return {
            "total_trades": 0, "annual_trades": 0, "net_profit": 0.0, "pf": 0.0,
            "win_rate": 0.0, "max_dd": 0.0, "romad": 0.0, "mcr": 0.0
        }

    pnls = np.array([t["pnl"] for t in trades])
    net_profit = np.sum(pnls)
    gross_win = np.sum(pnls[pnls > 0])
    gross_loss = abs(np.sum(pnls[pnls < 0]))
    pf = (gross_win / gross_loss) if gross_loss > 0 else (99.0 if gross_win > 0 else 0.0)
    win_rate = (len(pnls[pnls > 0]) / len(pnls)) * 100.0

    # Drawdown
    equity = np.cumsum(pnls)
    peak = np.maximum.accumulate(equity)
    dd = peak - equity
    max_dd = np.max(dd) if len(dd) > 0 else 0.0
    romad = (net_profit / max_dd) if max_dd > 0 else 0.0

    # Monthly Consistency Ratio (MCR)
    df_trades = pd.DataFrame(trades)
    m_pnl = df_trades.groupby("month")["pnl"].sum()
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
        "mcr": round(float(mcr), 2)
    }

# =============================================================================
# STRATEGY SIGNAL GENERATORS (S201 - S210)
# =============================================================================

def gen_s201_asian_liquidity_sweep(opens, highs, lows, closes, hours, atr):
    """S201: Asian Liquidity Sweep & London Reversal Scalper"""
    n = len(closes)
    bull = np.zeros(n, dtype=bool)
    bear = np.zeros(n, dtype=bool)
    
    # Track Asian session (00:00 - 06:00) High/Low
    asia_high = 0.0
    asia_low = 999999.0
    for i in range(1, n):
        h = hours[i]
        if h == 0 and hours[i-1] != 0:
            asia_high = highs[i]
            asia_low = lows[i]
        elif 0 <= h < 6:
            asia_high = max(asia_high, highs[i])
            asia_low = min(asia_low, lows[i])
        elif 7 <= h <= 11:  # London Open window
            # Bearish sweep: pierced Asian high then closed back below
            if highs[i] > asia_high and closes[i] < asia_high:
                bear[i] = True
            # Bullish sweep: pierced Asian low then closed back above
            elif lows[i] < asia_low and closes[i] > asia_low:
                bull[i] = True
    return bull, bear

def gen_s202_session_momentum_breakout(opens, highs, lows, closes, volumes, hours, atr):
    """S202: Session Open Momentum & Volume Breakout Scalper"""
    n = len(closes)
    bull = np.zeros(n, dtype=bool)
    bear = np.zeros(n, dtype=bool)
    lookback = 12
    for i in range(lookback + 1, n):
        h = hours[i]
        if (7 <= h <= 9) or (12 <= h <= 14):
            recent_high = np.max(highs[i - lookback:i])
            recent_low = np.min(lows[i - lookback:i])
            bar_range = highs[i] - lows[i]
            body = abs(closes[i] - opens[i])
            if bar_range > 0 and (body / bar_range) >= 0.60:
                if closes[i] > recent_high:
                    bull[i] = True
                elif closes[i] < recent_low:
                    bear[i] = True
    return bull, bear

def gen_s203_bollinger_bandwidth_squeeze(opens, highs, lows, closes, atr):
    """S203: Fast Bollinger Bandwidth Squeeze & Expansion"""
    n = len(closes)
    bull = np.zeros(n, dtype=bool)
    bear = np.zeros(n, dtype=bool)
    period = 20
    sma = pd.Series(closes).rolling(period).mean().values
    std = pd.Series(closes).rolling(period).std().values
    upper = sma + 2.0 * std
    lower = sma - 2.0 * std
    bandwidth = (upper - lower) / np.where(sma > 0, sma, 1.0)
    bw_min = pd.Series(bandwidth).rolling(40).min().values
    
    for i in range(40, n):
        if bandwidth[i - 1] <= bw_min[i - 1] * 1.05 and bandwidth[i] > bandwidth[i - 1]:
            if closes[i] > upper[i]:
                bull[i] = True
            elif closes[i] < lower[i]:
                bear[i] = True
    return bull, bear

def gen_s204_ema_ribbon_pullback(opens, highs, lows, closes, atr):
    """S204: EMA Ribbon Dynamic Pullback & Wick Rejection"""
    n = len(closes)
    bull = np.zeros(n, dtype=bool)
    bear = np.zeros(n, dtype=bool)
    ema8 = compute_ema(closes, 8)
    ema13 = compute_ema(closes, 13)
    ema21 = compute_ema(closes, 21)
    ema55 = compute_ema(closes, 55)
    
    for i in range(55, n):
        bar_range = highs[i] - lows[i]
        if bar_range <= 0:
            continue
        # Uptrend ribbon
        if ema8[i] > ema13[i] > ema21[i] > ema55[i]:
            # Pullback touch ema13 or ema21 with lower wick
            if lows[i] <= ema21[i] and closes[i] > ema13[i]:
                lower_wick = min(opens[i], closes[i]) - lows[i]
                if (lower_wick / bar_range) >= 0.35:
                    bull[i] = True
        # Downtrend ribbon
        elif ema8[i] < ema13[i] < ema21[i] < ema55[i]:
            if highs[i] >= ema21[i] and closes[i] < ema13[i]:
                upper_wick = highs[i] - max(opens[i], closes[i])
                if (upper_wick / bar_range) >= 0.35:
                    bear[i] = True
    return bull, bear

def gen_s205_fast_rsi_extremes(opens, highs, lows, closes, atr):
    """S205: Fast RSI Extreme Mean-Reversion Scalper"""
    n = len(closes)
    bull = np.zeros(n, dtype=bool)
    bear = np.zeros(n, dtype=bool)
    rsi = compute_rsi(closes, period=7)
    ema50 = compute_ema(closes, 50)
    
    for i in range(50, n):
        # Oversold in macro context or range
        if rsi[i - 1] <= 18 and rsi[i] > 18 and closes[i] > opens[i]:
            bull[i] = True
        elif rsi[i - 1] >= 82 and rsi[i] < 82 and closes[i] < opens[i]:
            bear[i] = True
    return bull, bear

def gen_s206_keltner_surge_breakout(opens, highs, lows, closes, atr):
    """S206: Keltner Channel Volatility Surge Breakout"""
    n = len(closes)
    bull = np.zeros(n, dtype=bool)
    bear = np.zeros(n, dtype=bool)
    ema20 = compute_ema(closes, 20)
    upper_kc = ema20 + 1.5 * atr
    lower_kc = ema20 - 1.5 * atr
    
    for i in range(25, n):
        if closes[i] > upper_kc[i] and closes[i - 1] <= upper_kc[i - 1]:
            bull[i] = True
        elif closes[i] < lower_kc[i] and closes[i - 1] >= lower_kc[i - 1]:
            bear[i] = True
    return bull, bear

def gen_s207_micro_fvg_retest(opens, highs, lows, closes, atr):
    """S207: Microstructure Fair Value Gap (FVG) Retest"""
    n = len(closes)
    bull = np.zeros(n, dtype=bool)
    bear = np.zeros(n, dtype=bool)
    
    for i in range(10, n):
        # Bullish FVG formed at i-2: Low[i-1] > High[i-3]
        if lows[i - 2] > highs[i - 4] and (lows[i - 2] - highs[i - 4]) >= 0.25 * atr[i]:
            fvg_top = lows[i - 2]
            fvg_bot = highs[i - 4]
            # Retest at current bar
            if lows[i] <= fvg_top and closes[i] >= fvg_bot:
                bull[i] = True
        # Bearish FVG formed at i-2: High[i-1] < Low[i-3]
        elif highs[i - 2] < lows[i - 4] and (lows[i - 4] - highs[i - 2]) >= 0.25 * atr[i]:
            fvg_bot = highs[i - 2]
            fvg_top = lows[i - 4]
            if highs[i] >= fvg_bot and closes[i] <= fvg_top:
                bear[i] = True
    return bull, bear

def gen_s208_vwap_sd_scalper(opens, highs, lows, closes, volumes, hours, atr):
    """S208: Intraday VWAP Standard Deviation Scalper"""
    n = len(closes)
    bull = np.zeros(n, dtype=bool)
    bear = np.zeros(n, dtype=bool)
    
    # Cumulative daily VWAP
    cum_pv = 0.0
    cum_v = 0.0
    typical_price = (highs + lows + closes) / 3.0
    vwap = np.zeros(n, dtype=np.float64)
    
    for i in range(n):
        if i > 0 and hours[i] == 0 and hours[i - 1] != 0:
            cum_pv = 0.0
            cum_v = 0.0
        v = volumes[i] if volumes[i] > 0 else 1.0
        cum_pv += typical_price[i] * v
        cum_v += v
        vwap[i] = cum_pv / cum_v if cum_v > 0 else closes[i]

    dist = closes - vwap
    for i in range(30, n):
        atr_val = atr[i]
        if atr_val <= 0:
            continue
        # Mean reversion when extended > 2.0 ATR away from VWAP
        if dist[i] <= -2.0 * atr_val and closes[i] > opens[i]:
            bull[i] = True
        elif dist[i] >= 2.0 * atr_val and closes[i] < opens[i]:
            bear[i] = True
    return bull, bear

def gen_s209_supertrend_micro(opens, highs, lows, closes, atr):
    """S209: Fast Supertrend Micro-Trailing Scalper"""
    n = len(closes)
    bull = np.zeros(n, dtype=bool)
    bear = np.zeros(n, dtype=bool)
    multiplier = 1.8
    trend = np.ones(n, dtype=np.int32)
    upper_band = (highs + lows) / 2.0 + multiplier * atr
    lower_band = (highs + lows) / 2.0 - multiplier * atr
    
    for i in range(1, n):
        if closes[i - 1] > lower_band[i - 1]:
            lower_band[i] = max(lower_band[i], lower_band[i - 1])
        if closes[i - 1] < upper_band[i - 1]:
            upper_band[i] = min(upper_band[i], upper_band[i - 1])
            
        if trend[i - 1] == 1:
            if closes[i] < lower_band[i]:
                trend[i] = -1
                bear[i] = True
            else:
                trend[i] = 1
        else:
            if closes[i] > upper_band[i]:
                trend[i] = 1
                bull[i] = True
            else:
                trend[i] = -1
    return bull, bear

def gen_s210_candle_imbalance_pinbar(opens, highs, lows, closes, volumes, atr):
    """S210: Candle Imbalance & High-Volume Pinbar Rejection"""
    n = len(closes)
    bull = np.zeros(n, dtype=bool)
    bear = np.zeros(n, dtype=bool)
    vol_sma = pd.Series(volumes).rolling(20).mean().values
    
    for i in range(20, n):
        bar_range = highs[i] - lows[i]
        if bar_range <= 0 or atr[i] <= 0:
            continue
        body = abs(closes[i] - opens[i])
        upper_wick = highs[i] - max(opens[i], closes[i])
        lower_wick = min(opens[i], closes[i]) - lows[i]
        
        # High volume confirmation
        if volumes[i] >= 1.6 * vol_sma[i] and bar_range >= 0.8 * atr[i]:
            # Bullish pinbar / rejection
            if (lower_wick / bar_range) >= 0.55 and body <= 0.30 * bar_range:
                bull[i] = True
            # Bearish pinbar / rejection
            elif (upper_wick / bar_range) >= 0.55 and body <= 0.30 * bar_range:
                bear[i] = True
    return bull, bear

# =============================================================================
# MULTI-TIMEFRAME EVALUATOR ENGINE
# =============================================================================

def evaluate_multi_tf_matrix(timeframes=["M15", "M5", "M1"]):
    t_start = time.time()
    print("=" * 105)
    print("🚀 MASSIVE PARALLEL SCALPING DISCOVERY BATCH: STRATEGIES 201 - 210")
    print(f"📊 Multi-Timeframe Matrix Architecture: {', '.join(timeframes)} on XAUUSD (2020-2025)")
    print(f"🎯 Target Volume Expectation: ~300+ Trades/Year | Friction: Spread $0.25 + Comm $6.00/Lot")
    print("=" * 105)

    strategy_registry = [
        ("S201", "Asian Liquidity Sweep & London Reversal", gen_s201_asian_liquidity_sweep),
        ("S202", "Session Open Momentum & Volume Breakout", gen_s202_session_momentum_breakout),
        ("S203", "Fast Bollinger Bandwidth Squeeze & Expansion", gen_s203_bollinger_bandwidth_squeeze),
        ("S204", "EMA Ribbon Dynamic Pullback & Wick Rejection", gen_s204_ema_ribbon_pullback),
        ("S205", "Fast RSI Extreme Mean-Reversion Scalper", gen_s205_fast_rsi_extremes),
        ("S206", "Keltner Channel Volatility Surge Breakout", gen_s206_keltner_surge_breakout),
        ("S207", "Microstructure Fair Value Gap (FVG) Retest", gen_s207_micro_fvg_retest),
        ("S208", "Intraday VWAP Standard Deviation Scalper", gen_s208_vwap_sd_scalper),
        ("S209", "Fast Supertrend Micro-Trailing Scalper", gen_s209_supertrend_micro),
        ("S210", "Candle Imbalance & High-Volume Pinbar Rejection", gen_s210_candle_imbalance_pinbar)
    ]

    all_matrix_results = []

    for tf in timeframes:
        parquet_file = os.path.join(DATA_DIR, f"XAUUSD_{tf}.parquet")
        if not os.path.exists(parquet_file):
            print(f"[!] Warning: Parquet file {parquet_file} not found. Skipping {tf}...")
            continue

        print(f"\n>>> [TIMEFRAME: {tf}] Loading data from {parquet_file}...")
        df = pd.read_parquet(parquet_file)
        n_bars = len(df)
        print(f"    Loaded {n_bars:,} bars ({df.index[0]} to {df.index[-1]})")

        opens = df['open'].values.astype(np.float64)
        highs = df['high'].values.astype(np.float64)
        lows = df['low'].values.astype(np.float64)
        closes = df['close'].values.astype(np.float64)
        volumes = df['tick_volume'].values.astype(np.float64) if 'tick_volume' in df.columns else np.ones(n_bars, dtype=np.float64)
        hours = df.index.hour.values
        months = df.index.strftime('%Y-%m').values
        dates = df.index.strftime('%Y-%m-%d').values
        
        atr = compute_atr(highs, lows, closes, 14)
        del df
        gc.collect()

        # Adjust holding bars based on TF
        if tf == "M1":
            max_bars = 45   # 45 minutes
            tp_mult, sl_mult = 2.5, 1.8
        elif tf == "M5":
            max_bars = 24   # 120 minutes
            tp_mult, sl_mult = 2.2, 1.5
        else: # M15
            max_bars = 16   # 4 hours
            tp_mult, sl_mult = 2.0, 1.4

        for sid, sname, gen_func in strategy_registry:
            t0 = time.time()
            if sid in ["S201"]:
                bull, bear = gen_func(opens, highs, lows, closes, hours, atr)
            elif sid in ["S202", "S208"]:
                bull, bear = gen_func(opens, highs, lows, closes, volumes, hours, atr)
            elif sid in ["S210"]:
                bull, bear = gen_func(opens, highs, lows, closes, volumes, atr)
            else:
                bull, bear = gen_func(opens, highs, lows, closes, atr)

            metrics = run_scalping_backtest(
                opens, highs, lows, closes, atr, bull, bear, months, dates,
                tp_mult=tp_mult, sl_mult=sl_mult, max_bars_hold=max_bars
            )
            dur = round(time.time() - t0, 2)

            # Evaluate status
            if metrics["pf"] >= 1.50 and metrics["net_profit"] > 0 and metrics["annual_trades"] >= 200:
                status = "🏆 CHAMPION SCALPER"
            elif metrics["net_profit"] > 0 and metrics["annual_trades"] >= 100:
                status = "TACTICAL CANDIDATE"
            else:
                status = "NEEDS REFINEMENT"

            entry = {
                "strategy_id": sid,
                "strategy_name": sname,
                "timeframe": tf,
                "total_trades": metrics["total_trades"],
                "annual_trades": metrics["annual_trades"],
                "net_profit": metrics["net_profit"],
                "pf": metrics["pf"],
                "win_rate": metrics["win_rate"],
                "max_dd": metrics["max_dd"],
                "romad": metrics["romad"],
                "mcr": metrics["mcr"],
                "status": status,
                "compute_time_s": dur
            }
            all_matrix_results.append(entry)
            print(f"  [{tf}] {sid}: {sname:<45} | Tr/Yr: {metrics['annual_trades']:<5} | Net: ${metrics['net_profit']:<9.2f} | PF: {metrics['pf']:<5.3f} | DD: ${metrics['max_dd']:<8.2f} | MCR: {metrics['mcr']:<5.1f}% | {status} ({dur}s)", flush=True)

        del opens, highs, lows, closes, volumes, hours, months, dates, atr
        gc.collect()

    print("\n" + "=" * 105)
    print("🏆 MULTI-TIMEFRAME SCALPING MATRIX LEADERBOARD SUMMARY (2020-2025)")
    print("=" * 105)
    df_matrix = pd.DataFrame(all_matrix_results)
    if not df_matrix.empty:
        df_matrix.sort_values(by=["pf", "annual_trades", "net_profit"], ascending=[False, False, False], inplace=True)
        print(df_matrix[["strategy_id", "timeframe", "strategy_name", "annual_trades", "net_profit", "pf", "win_rate", "max_dd", "romad", "mcr", "status"]].to_string(index=False))

    os.makedirs(RESULTS_DIR, exist_ok=True)
    out_json = os.path.join(RESULTS_DIR, "massive_scalping_multi_tf_batch_201_210_results.json")
    out_csv = os.path.join(RESULTS_DIR, "massive_scalping_multi_tf_batch_201_210_matrix.csv")

    with open(out_json, "w") as f:
        json.dump({
            "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            "total_runtime_s": round(time.time() - t_start, 2),
            "results": all_matrix_results
        }, f, indent=2)

    df_matrix.to_csv(out_csv, index=False)
    print(f"\n[+] Saved Matrix Results to:\n    - {out_json}\n    - {out_csv}")
    print("=" * 105)

if __name__ == "__main__":
    evaluate_multi_tf_matrix(timeframes=["M15", "M5", "M1"])
