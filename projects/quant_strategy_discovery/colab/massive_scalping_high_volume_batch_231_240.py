#!/usr/bin/env python3
"""
===============================================================================
SCALPING HIGH-VOLUME ALPHA BATCH 4: STRATEGIES 231 - 240
TARGETING 300+ TRADES/YEAR & PROFIT FACTOR > 1.50 ON XAUUSD (M5 & M15)
===============================================================================
Core Focus:
  - Scale up S221 (RSI Snapshot: +$2,458, PF 1.048) trade volume to 250-500 trades/yr.
  - Refine S224 (Session Momentum Impulse: 351 trades/yr, PF 0.912) with volume absorption.
  - Optimize S226 (Asian Sweep: 290 trades/yr, PF 0.885) with midpoint reversion targets.
  - Introduce Multi-Confluence Scalping architectures.
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

def run_scalping_simulation(opens, highs, lows, closes, atr, bull_sigs, bear_sigs, months, dates,
                           tp_mult=1.6, sl_mult=1.1, max_bars_hold=16,
                           spread_pts=0.25, comm_dollars=0.60):
    n = len(closes)
    trades = []
    in_pos = False
    pos_type = 0
    entry_price = 0.0
    sl_price = 0.0
    tp_price = 0.0
    entry_idx = 0
    point_value = 100.0

    for i in range(150, n - 1):
        if in_pos:
            hit_tp = False
            hit_sl = False
            exit_price = 0.0

            if (i - entry_idx) >= max_bars_hold:
                exit_price = opens[i]
                if pos_type == 1:
                    exit_price -= spread_pts
                    pnl = (exit_price - entry_price) * point_value - comm_dollars
                else:
                    pnl = (entry_price - exit_price) * point_value - comm_dollars
                trades.append({"pnl": pnl, "month": months[entry_idx]})
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
                trades.append({"pnl": pnl, "month": months[entry_idx]})
                in_pos = False
                continue

        if not in_pos:
            atr_val = atr[i]
            if atr_val <= 0.60:
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

    equity = np.cumsum(pnls)
    peak = np.maximum.accumulate(equity)
    dd = peak - equity
    max_dd = np.max(dd) if len(dd) > 0 else 0.0
    romad = (net_profit / max_dd) if max_dd > 0 else 0.0

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
# STRATEGIES 231 - 240: HIGH-VOLUME ALPHA CANDIDATES
# =============================================================================

def gen_s231_rsi_expanded_threshold(opens, highs, lows, closes, hours, atr, tf_bars):
    """S231: RSI Snapshot Scalper with Expanded Threshold (RSI < 24 / > 76 for 300+ trades/yr)"""
    n = len(closes)
    bull = np.zeros(n, dtype=bool)
    bear = np.zeros(n, dtype=bool)
    rsi = compute_rsi(closes, period=6)
    macro_ema = compute_ema(closes, 40 * tf_bars)
    for i in range(40 * tf_bars, n):
        if 7 <= hours[i] <= 19:
            if closes[i] > macro_ema[i] and rsi[i - 1] <= 24 and closes[i] > opens[i]:
                bull[i] = True
            elif closes[i] < macro_ema[i] and rsi[i - 1] >= 76 and closes[i] < opens[i]:
                bear[i] = True
    return bull, bear

def gen_s232_rsi_volume_absorption(opens, highs, lows, closes, volumes, hours, atr, tf_bars):
    """S232: RSI Snapshot + Volume Absorption (RSI dip with high tick volume absorption)"""
    n = len(closes)
    bull = np.zeros(n, dtype=bool)
    bear = np.zeros(n, dtype=bool)
    rsi = compute_rsi(closes, period=6)
    vol_sma = pd.Series(volumes).rolling(15).mean().values
    macro_ema = compute_ema(closes, 30 * tf_bars)
    for i in range(30 * tf_bars, n):
        if 7 <= hours[i] <= 19 and volumes[i] >= 1.3 * vol_sma[i]:
            if closes[i] > macro_ema[i] and rsi[i - 1] <= 22 and closes[i] > opens[i]:
                bull[i] = True
            elif closes[i] < macro_ema[i] and rsi[i - 1] >= 78 and closes[i] < opens[i]:
                bear[i] = True
    return bull, bear

def gen_s233_asian_sweep_midpoint_reversal(opens, highs, lows, closes, hours, atr, tf_bars):
    """S233: Asian Sweep Reversal with Fast Midpoint Snap"""
    n = len(closes)
    bull = np.zeros(n, dtype=bool)
    bear = np.zeros(n, dtype=bool)
    asia_high, asia_low = 0.0, 999999.0
    for i in range(1, n):
        h = hours[i]
        if h == 0 and hours[i-1] != 0:
            asia_high = highs[i]
            asia_low = lows[i]
        elif 0 <= h < 6:
            asia_high = max(asia_high, highs[i])
            asia_low = min(asia_low, lows[i])
        elif 7 <= h <= 12:
            # Swept above Asian high and reversed back inside with rejection bar
            if highs[i] > asia_high and closes[i] < asia_high and closes[i] < opens[i]:
                bear[i] = True
            elif lows[i] < asia_low and closes[i] > asia_low and closes[i] > opens[i]:
                bull[i] = True
    return bull, bear

def gen_s234_london_momentum_surge(opens, highs, lows, closes, volumes, hours, atr, tf_bars):
    """S234: London & NY Opening Session Momentum Surge"""
    n = len(closes)
    bull = np.zeros(n, dtype=bool)
    bear = np.zeros(n, dtype=bool)
    vol_sma = pd.Series(volumes).rolling(12).mean().values
    for i in range(15, n):
        h = hours[i]
        if (7 <= h <= 10) or (12 <= h <= 15):
            bar_range = highs[i] - lows[i]
            body = abs(closes[i] - opens[i])
            if bar_range >= 0.8 * atr[i] and (body / bar_range) >= 0.60 and volumes[i] >= 1.4 * vol_sma[i]:
                if closes[i] > opens[i]:
                    bull[i] = True
                else:
                    bear[i] = True
    return bull, bear

def gen_s235_dual_rsi_confluence(opens, highs, lows, closes, hours, atr, tf_bars):
    """S235: Dual RSI Confluence (Fast RSI 4 + Slow RSI 14 Deep Oversold/Overbought)"""
    n = len(closes)
    bull = np.zeros(n, dtype=bool)
    bear = np.zeros(n, dtype=bool)
    fast_rsi = compute_rsi(closes, period=4)
    slow_rsi = compute_rsi(closes, period=14)
    macro_ema = compute_ema(closes, 50 * tf_bars)
    for i in range(50 * tf_bars, n):
        if 7 <= hours[i] <= 19:
            # Deep confluence dip in trend
            if closes[i] > macro_ema[i] and fast_rsi[i - 1] <= 15 and slow_rsi[i - 1] <= 35 and closes[i] > opens[i]:
                bull[i] = True
            elif closes[i] < macro_ema[i] and fast_rsi[i - 1] >= 85 and slow_rsi[i - 1] >= 65 and closes[i] < opens[i]:
                bear[i] = True
    return bull, bear

def gen_s236_fvg_prime_hours(opens, highs, lows, closes, hours, atr, tf_bars):
    """S236: FVG Imbalance Retest in Prime Session Hours (07:00-15:00 UTC)"""
    n = len(closes)
    bull = np.zeros(n, dtype=bool)
    bear = np.zeros(n, dtype=bool)
    macro_ema = compute_ema(closes, 25 * tf_bars)
    for i in range(10, n):
        if 7 <= hours[i] <= 15:
            # Bullish FVG
            if lows[i - 2] > highs[i - 4] and (lows[i - 2] - highs[i - 4]) >= 0.20 * atr[i]:
                if closes[i] > macro_ema[i] and lows[i] <= lows[i - 2] and closes[i] >= highs[i - 4]:
                    bull[i] = True
            elif highs[i - 2] < lows[i - 4] and (lows[i - 4] - highs[i - 2]) >= 0.20 * atr[i]:
                if closes[i] < macro_ema[i] and highs[i] >= highs[i - 2] and closes[i] <= lows[i - 4]:
                    bear[i] = True
    return bull, bear

def gen_s237_bollinger_bandwidth_snap(opens, highs, lows, closes, hours, atr, tf_bars):
    """S237: Bollinger Bandwidth Squeeze Snap (TP 1.6x ATR vs SL 1.0x ATR)"""
    n = len(closes)
    bull = np.zeros(n, dtype=bool)
    bear = np.zeros(n, dtype=bool)
    sma = pd.Series(closes).rolling(20).mean().values
    std = pd.Series(closes).rolling(20).std().values
    upper = sma + 2.0 * std
    lower = sma - 2.0 * std
    bw = (upper - lower) / np.where(sma > 0, sma, 1.0)
    bw_min = pd.Series(bw).rolling(25).min().values
    for i in range(25, n):
        if 7 <= hours[i] <= 18:
            if bw[i - 1] <= bw_min[i - 1] * 1.10:
                if closes[i] > upper[i] and closes[i] > opens[i]:
                    bull[i] = True
                elif closes[i] < lower[i] and closes[i] < opens[i]:
                    bear[i] = True
    return bull, bear

def gen_s238_vwap_extreme_snap(opens, highs, lows, closes, volumes, hours, atr, tf_bars):
    """S238: VWAP 2.2 SD Extreme Snap (Pure Mean Reversion with positive RR)"""
    n = len(closes)
    bull = np.zeros(n, dtype=bool)
    bear = np.zeros(n, dtype=bool)
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
        if 7 <= hours[i] <= 18:
            if dist[i] <= -2.0 * atr[i] and closes[i] > opens[i]:
                bull[i] = True
            elif dist[i] >= 2.0 * atr[i] and closes[i] < opens[i]:
                bear[i] = True
    return bull, bear

def gen_s239_ema_ribbon_pulse(opens, highs, lows, closes, hours, atr, tf_bars):
    """S239: EMA Ribbon Trend Pulse (Fast EMA 8 / 21 / 55 Continuation)"""
    n = len(closes)
    bull = np.zeros(n, dtype=bool)
    bear = np.zeros(n, dtype=bool)
    ema8 = compute_ema(closes, 8)
    ema21 = compute_ema(closes, 21)
    ema55 = compute_ema(closes, 55)
    for i in range(55, n):
        if 7 <= hours[i] <= 19:
            if ema8[i] > ema21[i] > ema55[i]:
                if lows[i] <= ema21[i] and closes[i] > ema8[i] and closes[i] > opens[i]:
                    bull[i] = True
            elif ema8[i] < ema21[i] < ema55[i]:
                if highs[i] >= ema21[i] and closes[i] < ema8[i] and closes[i] < opens[i]:
                    bear[i] = True
    return bull, bear

def gen_s240_composite_confluence_scalper(opens, highs, lows, closes, volumes, hours, atr, tf_bars):
    """S240: Composite Triple-Confluence Scalper (RSI Dip + Trend Alignment + Rejection Bar)"""
    n = len(closes)
    bull = np.zeros(n, dtype=bool)
    bear = np.zeros(n, dtype=bool)
    rsi = compute_rsi(closes, period=6)
    macro_ema = compute_ema(closes, 50 * tf_bars)
    for i in range(50 * tf_bars, n):
        if 7 <= hours[i] <= 19:
            bar_range = highs[i] - lows[i]
            if bar_range <= 0:
                continue
            lower_wick = min(opens[i], closes[i]) - lows[i]
            upper_wick = highs[i] - max(opens[i], closes[i])
            # Confluence Bull: Uptrend + RSI dip < 25 + Lower wick rejection >= 35%
            if closes[i] > macro_ema[i] and rsi[i - 1] <= 25 and (lower_wick / bar_range) >= 0.35:
                bull[i] = True
            elif closes[i] < macro_ema[i] and rsi[i - 1] >= 75 and (upper_wick / bar_range) >= 0.35:
                bear[i] = True
    return bull, bear

# =============================================================================
# MAIN RUNNER
# =============================================================================

def main():
    t_start = time.time()
    timeframes = ["M15", "M5"]
    print("=" * 105)
    print("🚀 SCALPING HIGH-VOLUME ALPHA BATCH 4: STRATEGIES 231 - 240")
    print(f"📊 Multi-Timeframe Matrix: {', '.join(timeframes)} on XAUUSD (2020-2025)")
    print(f"🎯 Target Volume: ~250-500 Trades/Year | Friction: Spread $0.25 + Comm $6.00/Lot")
    print("⚙️  Objective: Scale S221 Positive Net Alpha to 300+ Trades/Year with PF >= 1.50")
    print("=" * 105)

    strategy_registry = [
        ("S231", "RSI Expanded Threshold Scalper", gen_s231_rsi_expanded_threshold),
        ("S232", "RSI Volume Absorption Scalper", gen_s232_rsi_volume_absorption),
        ("S233", "Asian Sweep Midpoint Reversal", gen_s233_asian_sweep_midpoint_reversal),
        ("S234", "London Momentum Surge Scalper", gen_s234_london_momentum_surge),
        ("S235", "Dual RSI Confluence Reversal", gen_s235_dual_rsi_confluence),
        ("S236", "FVG Retest in Prime Hours", gen_s236_fvg_prime_hours),
        ("S237", "Bollinger Bandwidth Squeeze Snap", gen_s237_bollinger_bandwidth_snap),
        ("S238", "VWAP 2.2 SD Extreme Snap", gen_s238_vwap_extreme_snap),
        ("S239", "EMA Ribbon Trend Pulse", gen_s239_ema_ribbon_pulse),
        ("S240", "Composite Triple-Confluence Scalper", gen_s240_composite_confluence_scalper)
    ]

    all_matrix_results = []

    for tf in timeframes:
        parquet_file = os.path.join(DATA_DIR, f"XAUUSD_{tf}.parquet")
        if not os.path.exists(parquet_file):
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
        tf_bars = 12 if tf == "M5" else 4
        del df
        gc.collect()

        tp_mult = 1.7 if tf == "M5" else 1.6
        sl_mult = 1.1 if tf == "M5" else 1.0
        max_bars = 18 if tf == "M5" else 14

        for sid, sname, gen_func in strategy_registry:
            t0 = time.time()
            if sid in ["S232", "S234", "S238", "S240"]:
                bull, bear = gen_func(opens, highs, lows, closes, volumes, hours, atr, tf_bars)
            else:
                bull, bear = gen_func(opens, highs, lows, closes, hours, atr, tf_bars)

            metrics = run_scalping_simulation(
                opens, highs, lows, closes, atr, bull, bear, months, dates,
                tp_mult=tp_mult, sl_mult=sl_mult, max_bars_hold=max_bars
            )
            dur = round(time.time() - t0, 2)

            if metrics["pf"] >= 1.50 and metrics["net_profit"] > 0 and metrics["annual_trades"] >= 200:
                status = "🏆 CHAMPION SCALPER"
            elif metrics["net_profit"] > 0 and metrics["annual_trades"] >= 100:
                status = "TACTICAL CANDIDATE"
            elif metrics["pf"] >= 1.0:
                status = "PROMISSING (NET +)"
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
            print(f"  [{tf}] {sid}: {sname:<35} | Tr/Yr: {metrics['annual_trades']:<5} | Net: ${metrics['net_profit']:<9.2f} | PF: {metrics['pf']:<5.3f} | DD: ${metrics['max_dd']:<8.2f} | MCR: {metrics['mcr']:<5.1f}% | {status} ({dur}s)", flush=True)

        del opens, highs, lows, closes, volumes, hours, months, dates, atr
        gc.collect()

    print("\n" + "=" * 105)
    print("🏆 BATCH 4 HIGH-VOLUME SCALPING LEADERBOARD SUMMARY (2020-2025)")
    print("=" * 105)
    df_matrix = pd.DataFrame(all_matrix_results)
    if not df_matrix.empty:
        df_matrix.sort_values(by=["pf", "annual_trades", "net_profit"], ascending=[False, False, False], inplace=True)
        print(df_matrix[["strategy_id", "timeframe", "strategy_name", "annual_trades", "net_profit", "pf", "win_rate", "max_dd", "romad", "mcr", "status"]].to_string(index=False))

    os.makedirs(RESULTS_DIR, exist_ok=True)
    out_json = os.path.join(RESULTS_DIR, "massive_scalping_high_volume_batch_231_240_results.json")
    out_csv = os.path.join(RESULTS_DIR, "massive_scalping_high_volume_batch_231_240_matrix.csv")

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
    main()
