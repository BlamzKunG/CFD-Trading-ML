#!/usr/bin/env python3
"""
===============================================================================
SCALPING VOLATILITY ALPHA BATCH 5: STRATEGIES 241 - 250
BEATING THE BROKER FRICTION: VOLATILITY GATING (ATR >= $2.00) & ASYMMETRIC 2.2:1.2 RR
===============================================================================
Target Asset: XAUUSD (Gold)
Timeframe: M15 (Optimal Friction-to-Range Window)
Friction: Spread $0.25 ($25/lot) + Commission $6.00/lot ($0.60/0.10 lot)
Target Annual Volume: ~250 - 450+ Trades/Year
Target Profit Factor: >= 1.50
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
                           tp_mult=2.2, sl_mult=1.2, max_bars_hold=18,
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
            if atr_val < 1.80:  # Hard volatility filter to beat friction
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
# STRATEGIES 241 - 250: VOLATILITY-GATED ALPHA ENGINES
# =============================================================================

def gen_s241_volatility_asian_sweep(opens, highs, lows, closes, hours, atr):
    """S241: Volatility-Gated Asian Sweep (London Open 07:00-09:00 UTC only)"""
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
        elif 7 <= h <= 9:  # Peak London Open liquidity
            if highs[i] > asia_high and closes[i] < asia_high and closes[i] < opens[i]:
                bear[i] = True
            elif lows[i] < asia_low and closes[i] > asia_low and closes[i] > opens[i]:
                bull[i] = True
    return bull, bear

def gen_s242_deep_rsi_snapshot_volatility(opens, highs, lows, closes, hours, atr):
    """S242: Deep RSI Snapshot with High Volatility Alignment"""
    n = len(closes)
    bull = np.zeros(n, dtype=bool)
    bear = np.zeros(n, dtype=bool)
    rsi = compute_rsi(closes, period=5)
    macro_ema = compute_ema(closes, 50 * 4)  # H1 EMA50
    for i in range(200, n):
        if 7 <= hours[i] <= 18:
            if closes[i] > macro_ema[i] and rsi[i - 1] <= 18 and closes[i] > opens[i]:
                bull[i] = True
            elif closes[i] < macro_ema[i] and rsi[i - 1] >= 82 and closes[i] < opens[i]:
                bear[i] = True
    return bull, bear

def gen_s243_bollinger_bandwidth_explosion(opens, highs, lows, closes, hours, atr):
    """S243: High-Expansion Bollinger Squeeze Explosion"""
    n = len(closes)
    bull = np.zeros(n, dtype=bool)
    bear = np.zeros(n, dtype=bool)
    sma = pd.Series(closes).rolling(20).mean().values
    std = pd.Series(closes).rolling(20).std().values
    upper = sma + 2.0 * std
    lower = sma - 2.0 * std
    bw = (upper - lower) / np.where(sma > 0, sma, 1.0)
    bw_min = pd.Series(bw).rolling(20).min().values
    for i in range(25, n):
        if 7 <= hours[i] <= 18:
            if bw[i - 1] <= bw_min[i - 1] * 1.08:
                if closes[i] > upper[i] and closes[i] > opens[i]:
                    bull[i] = True
                elif closes[i] < lower[i] and closes[i] < opens[i]:
                    bear[i] = True
    return bull, bear

def gen_s244_london_ny_overlap_surge(opens, highs, lows, closes, volumes, hours, atr):
    """S244: London-NY Overlap Volatility Surge (12:00 - 15:00 UTC)"""
    n = len(closes)
    bull = np.zeros(n, dtype=bool)
    bear = np.zeros(n, dtype=bool)
    vol_sma = pd.Series(volumes).rolling(12).mean().values
    for i in range(15, n):
        h = hours[i]
        if 12 <= h <= 15:
            bar_range = highs[i] - lows[i]
            body = abs(closes[i] - opens[i])
            if bar_range >= 1.0 * atr[i] and (body / bar_range) >= 0.60 and volumes[i] >= 1.5 * vol_sma[i]:
                if closes[i] > opens[i]:
                    bull[i] = True
                else:
                    bear[i] = True
    return bull, bear

def gen_s245_fvg_retest_elevated_vol(opens, highs, lows, closes, hours, atr):
    """S245: FVG Liquidity Absorption with Volatility Gating"""
    n = len(closes)
    bull = np.zeros(n, dtype=bool)
    bear = np.zeros(n, dtype=bool)
    macro_ema = compute_ema(closes, 30 * 4)
    for i in range(120, n):
        if 7 <= hours[i] <= 16:
            if lows[i - 2] > highs[i - 4] and (lows[i - 2] - highs[i - 4]) >= 0.30 * atr[i]:
                if closes[i] > macro_ema[i] and lows[i] <= lows[i - 2] and closes[i] >= highs[i - 4]:
                    bull[i] = True
            elif highs[i - 2] < lows[i - 4] and (lows[i - 4] - highs[i - 2]) >= 0.30 * atr[i]:
                if closes[i] < macro_ema[i] and highs[i] >= highs[i - 2] and closes[i] <= lows[i - 4]:
                    bear[i] = True
    return bull, bear

def gen_s246_dual_tf_trend_impulse(opens, highs, lows, closes, hours, atr):
    """S246: Dual-TF Trend Impulse (H1 Direction + M15 Pullback + Elevated ATR)"""
    n = len(closes)
    bull = np.zeros(n, dtype=bool)
    bear = np.zeros(n, dtype=bool)
    h1_ema = compute_ema(closes, 50 * 4)
    fast_ema = compute_ema(closes, 8)
    med_ema = compute_ema(closes, 21)
    for i in range(200, n):
        if 7 <= hours[i] <= 18:
            if closes[i] > h1_ema[i] and fast_ema[i] > med_ema[i]:
                if lows[i] <= med_ema[i] and closes[i] > fast_ema[i] and closes[i] > opens[i]:
                    bull[i] = True
            elif closes[i] < h1_ema[i] and fast_ema[i] < med_ema[i]:
                if highs[i] >= med_ema[i] and closes[i] < fast_ema[i] and closes[i] < opens[i]:
                    bear[i] = True
    return bull, bear

def gen_s247_tri_confluence_scalp(opens, highs, lows, closes, volumes, hours, atr):
    """S247: Tri-Confluence Precision Scalper (RSI + FVG + Trend Rejection)"""
    n = len(closes)
    bull = np.zeros(n, dtype=bool)
    bear = np.zeros(n, dtype=bool)
    rsi = compute_rsi(closes, period=6)
    macro_ema = compute_ema(closes, 40 * 4)
    for i in range(160, n):
        if 7 <= hours[i] <= 18:
            bar_range = highs[i] - lows[i]
            if bar_range <= 0:
                continue
            lower_wick = min(opens[i], closes[i]) - lows[i]
            upper_wick = highs[i] - max(opens[i], closes[i])
            if closes[i] > macro_ema[i] and rsi[i - 1] <= 28 and (lower_wick / bar_range) >= 0.40:
                bull[i] = True
            elif closes[i] < macro_ema[i] and rsi[i - 1] >= 72 and (upper_wick / bar_range) >= 0.40:
                bear[i] = True
    return bull, bear

def gen_s248_vwap_stretched_reversion(opens, highs, lows, closes, volumes, hours, atr):
    """S248: VWAP Stretched Mean Reversion (> 2.3 ATR Deviation)"""
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
            if dist[i] <= -2.3 * atr[i] and closes[i] > opens[i]:
                bull[i] = True
            elif dist[i] >= 2.3 * atr[i] and closes[i] < opens[i]:
                bear[i] = True
    return bull, bear

def gen_s249_ema_ribbon_surge(opens, highs, lows, closes, hours, atr):
    """S249: EMA Ribbon Trend Surge in High ATR Regime"""
    n = len(closes)
    bull = np.zeros(n, dtype=bool)
    bear = np.zeros(n, dtype=bool)
    ema8 = compute_ema(closes, 8)
    ema21 = compute_ema(closes, 21)
    ema55 = compute_ema(closes, 55)
    for i in range(55, n):
        if 7 <= hours[i] <= 18:
            if ema8[i] > ema21[i] > ema55[i]:
                if lows[i] <= ema21[i] and closes[i] > ema8[i]:
                    bull[i] = True
            elif ema8[i] < ema21[i] < ema55[i]:
                if highs[i] >= ema21[i] and closes[i] < ema8[i]:
                    bear[i] = True
    return bull, bear

def gen_s250_ensemble_portfolio_signals(opens, highs, lows, closes, volumes, hours, atr):
    """S250: Multi-Engine Scalping Ensemble (Union of S241 Sweep + S242 RSI + S243 Squeeze)"""
    b1, s1 = gen_s241_volatility_asian_sweep(opens, highs, lows, closes, hours, atr)
    b2, s2 = gen_s242_deep_rsi_snapshot_volatility(opens, highs, lows, closes, hours, atr)
    b3, s3 = gen_s243_bollinger_bandwidth_explosion(opens, highs, lows, closes, hours, atr)
    bull = b1 | b2 | b3
    bear = s1 | s2 | s3
    return bull, bear

# =============================================================================
# MAIN RUNNER
# =============================================================================

def main():
    t_start = time.time()
    tf = "M15"
    parquet_file = os.path.join(DATA_DIR, f"XAUUSD_{tf}.parquet")
    print("=" * 105)
    print("🚀 SCALPING VOLATILITY ALPHA BATCH 5: STRATEGIES 241 - 250")
    print(f"📊 Focus Timeframe: {tf} on XAUUSD (2020-2025)")
    print(f"🎯 Target Volume: ~250-450 Trades/Year | Friction: Spread $0.25 + Comm $6.00/Lot")
    print("⚙️  Edge Optimization: Volatility Threshold (ATR >= $1.80) & Asymmetric 2.2x : 1.2x RR")
    print("=" * 105)

    df = pd.read_parquet(parquet_file)
    n_bars = len(df)
    print(f"[*] Loaded {n_bars:,} bars ({df.index[0]} to {df.index[-1]})")

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

    strategy_registry = [
        ("S241", "Volatility-Gated Asian Sweep", gen_s241_volatility_asian_sweep),
        ("S242", "Deep RSI Snapshot Scalper", gen_s242_deep_rsi_snapshot_volatility),
        ("S243", "Bollinger Bandwidth Explosion", gen_s243_bollinger_bandwidth_explosion),
        ("S244", "London-NY Overlap Volatility Surge", gen_s244_london_ny_overlap_surge),
        ("S245", "FVG Retest with Elevated Volatility", gen_s245_fvg_retest_elevated_vol),
        ("S246", "Dual-TF Trend Impulse Scalper", gen_s246_dual_tf_trend_impulse),
        ("S247", "Tri-Confluence Precision Scalper", gen_s247_tri_confluence_scalp),
        ("S248", "VWAP Stretched Mean Reversion", gen_s248_vwap_stretched_reversion),
        ("S249", "EMA Ribbon Trend Surge", gen_s249_ema_ribbon_surge),
        ("S250", "Multi-Engine Scalping Ensemble", gen_s250_ensemble_portfolio_signals)
    ]

    all_matrix_results = []

    for sid, sname, gen_func in strategy_registry:
        t0 = time.time()
        if sid in ["S244", "S247", "S248", "S250"]:
            bull, bear = gen_func(opens, highs, lows, closes, volumes, hours, atr)
        else:
            bull, bear = gen_func(opens, highs, lows, closes, hours, atr)

        metrics = run_scalping_simulation(
            opens, highs, lows, closes, atr, bull, bear, months, dates,
            tp_mult=2.2, sl_mult=1.2, max_bars_hold=18
        )
        dur = round(time.time() - t0, 2)

        if metrics["pf"] >= 1.50 and metrics["net_profit"] > 0 and metrics["annual_trades"] >= 200:
            status = "🏆 CHAMPION SCALPER"
        elif metrics["pf"] >= 1.10 and metrics["net_profit"] > 0:
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

    print("\n" + "=" * 105)
    print("🏆 BATCH 5 VOLATILITY-GATED SCALPING LEADERBOARD SUMMARY (2020-2025)")
    print("=" * 105)
    df_matrix = pd.DataFrame(all_matrix_results)
    if not df_matrix.empty:
        df_matrix.sort_values(by=["pf", "annual_trades", "net_profit"], ascending=[False, False, False], inplace=True)
        print(df_matrix[["strategy_id", "timeframe", "strategy_name", "annual_trades", "net_profit", "pf", "win_rate", "max_dd", "romad", "mcr", "status"]].to_string(index=False))

    os.makedirs(RESULTS_DIR, exist_ok=True)
    out_json = os.path.join(RESULTS_DIR, "massive_scalping_volatility_batch_241_250_results.json")
    out_csv = os.path.join(RESULTS_DIR, "massive_scalping_volatility_batch_241_250_matrix.csv")

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
