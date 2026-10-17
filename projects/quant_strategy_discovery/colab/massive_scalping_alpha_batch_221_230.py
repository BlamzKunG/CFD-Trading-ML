#!/usr/bin/env python3
"""
===============================================================================
SCALPING ALPHA DISCOVERY BATCH 3: STRATEGIES 221 - 230
OPTIMAL FRICTION-CALIBRATED RR (TP 1.5x - 1.8x ATR, SL 1.0x - 1.2x ATR)
NO FALSE BREAKEVEN SCRATCH | CROSS-TIMEFRAME MATRIX (M5 & M15)
===============================================================================
Target Asset: XAUUSD (Gold)
Timeframes: M5 and M15
Friction: Spread $0.25 ($25/lot) + Commission $6.00/lot ($0.60/0.10 lot)
Target Annual Volume: ~250 - 500+ Trades/Year
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

def run_calibrated_scalping_backtest(opens, highs, lows, closes, atr, bull_sigs, bear_sigs, months, dates,
                                     tp_mult=1.6, sl_mult=1.1, max_bars_hold=20,
                                     spread_pts=0.25, comm_dollars=0.60):
    """
    Calibrated scalping backtester:
    - Positive expectancy RR (TP 1.6x ATR vs SL 1.1x ATR)
    - Strict causality: Entry at i+1 Open + Spread
    - Max holding time exit to recycle margin
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

    for i in range(200, n - 1):
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
# STRATEGIES 221 - 230: CALIBRATED EDGE GENERATORS
# =============================================================================

def gen_s221_rsi_snapshot_reversal(opens, highs, lows, closes, hours, atr, tf_bars):
    """S221: Fast RSI Snapshot Scalper (Extreme Oversold/Overbought in Direction of Trend)"""
    n = len(closes)
    bull = np.zeros(n, dtype=bool)
    bear = np.zeros(n, dtype=bool)
    rsi = compute_rsi(closes, period=6)
    macro_ema = compute_ema(closes, 50 * tf_bars)
    
    for i in range(50 * tf_bars, n):
        if 7 <= hours[i] <= 19:
            # Bullish snapshot: Uptrend + RSI dip < 16 + Bullish close
            if closes[i] > macro_ema[i] and rsi[i - 1] <= 16 and closes[i] > opens[i]:
                bull[i] = True
            elif closes[i] < macro_ema[i] and rsi[i - 1] >= 84 and closes[i] < opens[i]:
                bear[i] = True
    return bull, bear

def gen_s222_fvg_institutional_fill(opens, highs, lows, closes, hours, atr, tf_bars):
    """S222: FVG Institutional Fill in Active Session"""
    n = len(closes)
    bull = np.zeros(n, dtype=bool)
    bear = np.zeros(n, dtype=bool)
    macro_ema = compute_ema(closes, 30 * tf_bars)
    
    for i in range(10, n):
        if 7 <= hours[i] <= 19:
            # Bullish FVG
            if lows[i - 2] > highs[i - 4] and (lows[i - 2] - highs[i - 4]) >= 0.25 * atr[i]:
                if closes[i] > macro_ema[i] and lows[i] <= lows[i - 2] and closes[i] >= highs[i - 4]:
                    bull[i] = True
            elif highs[i - 2] < lows[i - 4] and (lows[i - 4] - highs[i - 2]) >= 0.25 * atr[i]:
                if closes[i] < macro_ema[i] and highs[i] >= highs[i - 2] and closes[i] <= lows[i - 4]:
                    bear[i] = True
    return bull, bear

def gen_s223_vwap_mean_reversion_edge(opens, highs, lows, closes, volumes, hours, atr, tf_bars):
    """S223: VWAP Band Expansion Scalper with Quick Snap"""
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
            if dist[i] <= -1.8 * atr[i] and closes[i] > opens[i]:
                bull[i] = True
            elif dist[i] >= 1.8 * atr[i] and closes[i] < opens[i]:
                bear[i] = True
    return bull, bear

def gen_s224_session_momentum_impulse(opens, highs, lows, closes, volumes, hours, atr, tf_bars):
    """S224: London/NY Momentum Impulse Scalper"""
    n = len(closes)
    bull = np.zeros(n, dtype=bool)
    bear = np.zeros(n, dtype=bool)
    vol_sma = pd.Series(volumes).rolling(15).mean().values
    
    for i in range(20, n):
        h = hours[i]
        if (7 <= h <= 9) or (12 <= h <= 14):
            bar_range = highs[i] - lows[i]
            body = abs(closes[i] - opens[i])
            if bar_range >= 1.0 * atr[i] and (body / bar_range) >= 0.65 and volumes[i] >= 1.6 * vol_sma[i]:
                if closes[i] > opens[i]:
                    bull[i] = True
                else:
                    bear[i] = True
    return bull, bear

def gen_s225_ema_ribbon_continuation(opens, highs, lows, closes, hours, atr, tf_bars):
    """S225: EMA Ribbon Trend Continuation Scalper"""
    n = len(closes)
    bull = np.zeros(n, dtype=bool)
    bear = np.zeros(n, dtype=bool)
    ema8 = compute_ema(closes, 8)
    ema21 = compute_ema(closes, 21)
    macro_ema50 = compute_ema(closes, 50 * tf_bars)
    
    for i in range(50 * tf_bars, n):
        if 7 <= hours[i] <= 19:
            if closes[i] > macro_ema50[i] and ema8[i] > ema21[i]:
                if lows[i] <= ema21[i] and closes[i] > ema8[i]:
                    bull[i] = True
            elif closes[i] < macro_ema50[i] and ema8[i] < ema21[i]:
                if highs[i] >= ema21[i] and closes[i] < ema8[i]:
                    bear[i] = True
    return bull, bear

def gen_s226_asian_sweep_reversal_edge(opens, highs, lows, closes, hours, atr, tf_bars):
    """S226: Asian High/Low Liquidity Sweep at London Open"""
    n = len(closes)
    bull = np.zeros(n, dtype=bool)
    bear = np.zeros(n, dtype=bool)
    asia_high, asia_low = 0.0, 999999.0
    
    for i in range(1, n):
        h = hours[i]
        if h == 0 and hours[i - 1] != 0:
            asia_high = highs[i]
            asia_low = lows[i]
        elif 0 <= h < 6:
            asia_high = max(asia_high, highs[i])
            asia_low = min(asia_low, lows[i])
        elif 7 <= h <= 10:
            if highs[i] > asia_high and closes[i] < asia_high:
                bear[i] = True
            elif lows[i] < asia_low and closes[i] > asia_low:
                bull[i] = True
    return bull, bear

def gen_s227_atr_trailing_scalper(opens, highs, lows, closes, hours, atr, tf_bars):
    """S227: Dynamic Supertrend Micro-Pulse Scalper"""
    n = len(closes)
    bull = np.zeros(n, dtype=bool)
    bear = np.zeros(n, dtype=bool)
    fast_upper = (highs + lows) / 2.0 + 1.5 * atr
    fast_lower = (highs + lows) / 2.0 - 1.5 * atr
    trend = np.ones(n, dtype=np.int32)
    macro_ema = compute_ema(closes, 50 * tf_bars)
    
    for i in range(50 * tf_bars, n):
        if closes[i - 1] > fast_lower[i - 1]:
            fast_lower[i] = max(fast_lower[i], fast_lower[i - 1])
        if closes[i - 1] < fast_upper[i - 1]:
            fast_upper[i] = min(fast_upper[i], fast_upper[i - 1])
            
        if trend[i - 1] == 1:
            if closes[i] < fast_lower[i]:
                trend[i] = -1
                if closes[i] < macro_ema[i] and (7 <= hours[i] <= 19):
                    bear[i] = True
            else:
                trend[i] = 1
        else:
            if closes[i] > fast_upper[i]:
                trend[i] = 1
                if closes[i] > macro_ema[i] and (7 <= hours[i] <= 19):
                    bull[i] = True
            else:
                trend[i] = -1
    return bull, bear

def gen_s228_micro_pinbar_edge(opens, highs, lows, closes, volumes, hours, atr, tf_bars):
    """S228: Micro Pinbar Key Rejection Scalper"""
    n = len(closes)
    bull = np.zeros(n, dtype=bool)
    bear = np.zeros(n, dtype=bool)
    vol_sma = pd.Series(volumes).rolling(20).mean().values
    
    for i in range(20, n):
        if 7 <= hours[i] <= 19:
            bar_range = highs[i] - lows[i]
            if bar_range < 0.6 * atr[i]:
                continue
            body = abs(closes[i] - opens[i])
            lower_wick = min(opens[i], closes[i]) - lows[i]
            upper_wick = highs[i] - max(opens[i], closes[i])
            if volumes[i] >= 1.3 * vol_sma[i]:
                if (lower_wick / bar_range) >= 0.55 and body <= 0.30 * bar_range:
                    bull[i] = True
                elif (upper_wick / bar_range) >= 0.55 and body <= 0.30 * bar_range:
                    bear[i] = True
    return bull, bear

def gen_s229_bollinger_squeeze_pulse(opens, highs, lows, closes, hours, atr, tf_bars):
    """S229: Bollinger Squeeze Pulse Breakout"""
    n = len(closes)
    bull = np.zeros(n, dtype=bool)
    bear = np.zeros(n, dtype=bool)
    sma = pd.Series(closes).rolling(20).mean().values
    std = pd.Series(closes).rolling(20).std().values
    upper = sma + 1.8 * std
    lower = sma - 1.8 * std
    bw = (upper - lower) / np.where(sma > 0, sma, 1.0)
    bw_min = pd.Series(bw).rolling(30).min().values
    
    for i in range(30, n):
        if 7 <= hours[i] <= 19:
            if bw[i - 1] <= bw_min[i - 1] * 1.08:
                if closes[i] > upper[i]:
                    bull[i] = True
                elif closes[i] < lower[i]:
                    bear[i] = True
    return bull, bear

def gen_s230_volatility_pulse_expansion(opens, highs, lows, closes, volumes, hours, atr, tf_bars):
    """S230: Volatility Pulse Candle Expansion Scalper"""
    n = len(closes)
    bull = np.zeros(n, dtype=bool)
    bear = np.zeros(n, dtype=bool)
    
    for i in range(15, n):
        if 7 <= hours[i] <= 19:
            bar_range = highs[i] - lows[i]
            prev_ranges = highs[i-5:i] - lows[i-5:i]
            avg_prev = np.mean(prev_ranges)
            if bar_range >= 1.8 * avg_prev and bar_range >= 1.2 * atr[i]:
                if closes[i] > opens[i]:
                    bull[i] = True
                else:
                    bear[i] = True
    return bull, bear

# =============================================================================
# BATCH 3 RUNNER
# =============================================================================

def main():
    t_start = time.time()
    timeframes = ["M15", "M5"]
    print("=" * 105)
    print("🚀 SCALPING ALPHA DISCOVERY BATCH 3: STRATEGIES 221 - 230")
    print(f"📊 Multi-Timeframe Matrix: {', '.join(timeframes)} on XAUUSD (2020-2025)")
    print(f"🎯 Target Volume: ~250-500 Trades/Year | Friction: Spread $0.25 + Comm $6.00/Lot")
    print("⚙️  Engine: Friction-Calibrated TP 1.5x - 1.8x ATR vs SL 1.0x - 1.2x ATR (Positive Expectancy)")
    print("=" * 105)

    strategy_registry = [
        ("S221", "Fast RSI Snapshot Scalper", gen_s221_rsi_snapshot_reversal),
        ("S222", "FVG Institutional Fill", gen_s222_fvg_institutional_fill),
        ("S223", "VWAP Mean Reversion Edge", gen_s223_vwap_mean_reversion_edge),
        ("S224", "Session Momentum Impulse Scalper", gen_s224_session_momentum_impulse),
        ("S225", "EMA Ribbon Trend Continuation", gen_s225_ema_ribbon_continuation),
        ("S226", "Asian High/Low Liquidity Sweep", gen_s226_asian_sweep_reversal_edge),
        ("S227", "Dynamic Supertrend Micro-Pulse", gen_s227_atr_trailing_scalper),
        ("S228", "Micro Pinbar Key Rejection", gen_s228_micro_pinbar_edge),
        ("S229", "Bollinger Squeeze Pulse Breakout", gen_s229_bollinger_squeeze_pulse),
        ("S230", "Volatility Pulse Candle Expansion", gen_s230_volatility_pulse_expansion)
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

        tp_mult = 1.6 if tf == "M5" else 1.5
        sl_mult = 1.1 if tf == "M5" else 1.0
        max_bars = 18 if tf == "M5" else 12

        for sid, sname, gen_func in strategy_registry:
            t0 = time.time()
            if sid in ["S223", "S224", "S228", "S230"]:
                bull, bear = gen_func(opens, highs, lows, closes, volumes, hours, atr, tf_bars)
            else:
                bull, bear = gen_func(opens, highs, lows, closes, hours, atr, tf_bars)

            metrics = run_calibrated_scalping_backtest(
                opens, highs, lows, closes, atr, bull, bear, months, dates,
                tp_mult=tp_mult, sl_mult=sl_mult, max_bars_hold=max_bars
            )
            dur = round(time.time() - t0, 2)

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
            print(f"  [{tf}] {sid}: {sname:<35} | Tr/Yr: {metrics['annual_trades']:<5} | Net: ${metrics['net_profit']:<9.2f} | PF: {metrics['pf']:<5.3f} | DD: ${metrics['max_dd']:<8.2f} | MCR: {metrics['mcr']:<5.1f}% | {status} ({dur}s)", flush=True)

        del opens, highs, lows, closes, volumes, hours, months, dates, atr
        gc.collect()

    print("\n" + "=" * 105)
    print("🏆 BATCH 3 CALIBRATED SCALPING LEADERBOARD SUMMARY (2020-2025)")
    print("=" * 105)
    df_matrix = pd.DataFrame(all_matrix_results)
    if not df_matrix.empty:
        df_matrix.sort_values(by=["pf", "annual_trades", "net_profit"], ascending=[False, False, False], inplace=True)
        print(df_matrix[["strategy_id", "timeframe", "strategy_name", "annual_trades", "net_profit", "pf", "win_rate", "max_dd", "romad", "mcr", "status"]].to_string(index=False))

    os.makedirs(RESULTS_DIR, exist_ok=True)
    out_json = os.path.join(RESULTS_DIR, "massive_scalping_alpha_batch_221_230_results.json")
    out_csv = os.path.join(RESULTS_DIR, "massive_scalping_alpha_batch_221_230_matrix.csv")

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
