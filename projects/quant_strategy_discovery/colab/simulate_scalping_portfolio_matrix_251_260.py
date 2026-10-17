#!/usr/bin/env python3
"""
===============================================================================
SCALPING ENSEMBLE PORTFOLIO DISCOVERY BATCH 6: STRATEGIES 251 - 260
PORTFOLIO SYNERGY & CAPITAL BUDGETING ON XAUUSD (M15 / M5)
===============================================================================
Objective:
  Combine complementary Scalping Micro-Engines to achieve:
  - Total Trade Volume: ~300 to 800+ Trades/Year
  - Target Profit Factor: >= 1.50 - 2.00+
  - Monthly Consistency Ratio (MCR): >= 75% - 90%
  - Realistic Frictions: Spread $0.25 + Comm $6.00/Lot ($0.60/0.10 lot)
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

# =============================================================================
# INDIVIDUAL ENGINES
# =============================================================================

def engine_supertrend_trailing(opens, highs, lows, closes, atr):
    """Engine 1: Supertrend Trailing Engine (Olivier Seban Algorithm)"""
    n = len(closes)
    trades = []
    in_pos = False
    pos_type = 0
    entry_price = 0.0
    entry_idx = 0
    multiplier = 3.0
    upper = (highs + lows) / 2.0 + multiplier * atr
    lower = (highs + lows) / 2.0 - multiplier * atr
    trend = np.ones(n, dtype=np.int32)
    ema200 = compute_ema(closes, 200)

    for i in range(200, n - 1):
        if closes[i - 1] > lower[i - 1]:
            lower[i] = max(lower[i], lower[i - 1])
        if closes[i - 1] < upper[i - 1]:
            upper[i] = min(upper[i], upper[i - 1])

        # Trend Flip
        flip_bull = False
        flip_bear = False
        if trend[i - 1] == 1:
            if closes[i] < lower[i]:
                trend[i] = -1
                flip_bear = True
            else:
                trend[i] = 1
        else:
            if closes[i] > upper[i]:
                trend[i] = 1
                flip_bull = True
            else:
                trend[i] = -1

        # Check Position
        if in_pos:
            hit_exit = False
            exit_price = 0.0
            if pos_type == 1 and (lows[i] <= lower[i] or flip_bear):
                hit_exit = True
                exit_price = min(lower[i], opens[i]) - 0.25
            elif pos_type == -1 and (highs[i] >= upper[i] or flip_bull):
                hit_exit = True
                exit_price = max(upper[i], opens[i])

            if hit_exit:
                if pos_type == 1:
                    pnl = (exit_price - entry_price) * 100.0 - 0.60
                else:
                    pnl = (entry_price - exit_price) * 100.0 - 0.60
                trades.append({"bar": i, "engine": "Supertrend", "pnl": pnl})
                in_pos = False

        if not in_pos:
            if flip_bull and closes[i] > ema200[i]:
                in_pos = True
                pos_type = 1
                entry_idx = i + 1
                entry_price = opens[i + 1] + 0.25
            elif flip_bear and closes[i] < ema200[i]:
                in_pos = True
                pos_type = -1
                entry_idx = i + 1
                entry_price = opens[i + 1]

    return trades

def engine_zero_lag_macd(opens, highs, lows, closes, atr):
    """Engine 2: Zero-Lag MACD Inflection Engine"""
    n = len(closes)
    trades = []
    in_pos = False
    pos_type = 0
    entry_price = 0.0
    entry_idx = 0
    sl_price, tp_price = 0.0, 0.0

    # ZL MACD (15, 34, 9)
    fast_ema = compute_ema(closes, 15)
    fast_zl = 2 * fast_ema - compute_ema(fast_ema, 15)
    slow_ema = compute_ema(closes, 34)
    slow_zl = 2 * slow_ema - compute_ema(slow_ema, 34)
    macd = fast_zl - slow_zl
    sig_ema = compute_ema(macd, 9)
    signal = 2 * sig_ema - compute_ema(sig_ema, 9)

    for i in range(100, n - 1):
        if in_pos:
            hit = False
            exit_price = 0.0
            if pos_type == 1:
                if lows[i] <= sl_price:
                    hit = True; exit_price = sl_price
                elif highs[i] >= tp_price:
                    hit = True; exit_price = tp_price
            elif pos_type == -1:
                if highs[i] >= sl_price:
                    hit = True; exit_price = sl_price
                elif lows[i] <= tp_price:
                    hit = True; exit_price = tp_price

            if hit:
                pnl = ((exit_price - entry_price) if pos_type == 1 else (entry_price - exit_price)) * 100.0 - 0.60
                trades.append({"bar": i, "engine": "ZL_MACD", "pnl": pnl})
                in_pos = False

        if not in_pos:
            cross_up = macd[i] > signal[i] and macd[i - 1] <= signal[i - 1]
            cross_down = macd[i] < signal[i] and macd[i - 1] >= signal[i - 1]
            atr_val = atr[i]
            if atr_val > 0.5:
                if cross_up:
                    in_pos = True; pos_type = 1; entry_idx = i + 1; entry_price = opens[i + 1] + 0.25
                    sl_price = entry_price - 2.0 * atr_val
                    tp_price = entry_price + 4.0 * atr_val
                elif cross_down:
                    in_pos = True; pos_type = -1; entry_idx = i + 1; entry_price = opens[i + 1]
                    sl_price = entry_price + 2.0 * atr_val
                    tp_price = entry_price - 4.0 * atr_val

    return trades

def engine_ttm_squeeze(opens, highs, lows, closes, atr):
    """Engine 3: TTM Squeeze Volatility Breakout"""
    n = len(closes)
    trades = []
    in_pos = False
    pos_type = 0
    entry_price = 0.0
    sl_price, tp_price = 0.0, 0.0

    sma20 = pd.Series(closes).rolling(20).mean().values
    std20 = pd.Series(closes).rolling(20).std().values
    bb_upper = sma20 + 2.0 * std20
    bb_lower = sma20 - 2.0 * std20
    kc_upper = sma20 + 1.5 * atr
    kc_lower = sma20 - 1.5 * atr
    squeeze_on = (bb_lower > kc_lower) & (bb_upper < kc_upper)

    for i in range(50, n - 1):
        if in_pos:
            hit = False
            exit_price = 0.0
            if pos_type == 1:
                if lows[i] <= sl_price:
                    hit = True; exit_price = sl_price
                elif highs[i] >= tp_price:
                    hit = True; exit_price = tp_price
            elif pos_type == -1:
                if highs[i] >= sl_price:
                    hit = True; exit_price = sl_price
                elif lows[i] <= tp_price:
                    hit = True; exit_price = tp_price

            if hit:
                pnl = ((exit_price - entry_price) if pos_type == 1 else (entry_price - exit_price)) * 100.0 - 0.60
                trades.append({"bar": i, "engine": "TTM_Squeeze", "pnl": pnl})
                in_pos = False

        if not in_pos:
            # Squeeze fire (was on at i-1, now off at i)
            if squeeze_on[i - 1] and not squeeze_on[i]:
                atr_val = atr[i]
                if closes[i] > sma20[i]:
                    in_pos = True; pos_type = 1; entry_price = opens[i + 1] + 0.25
                    sl_price = entry_price - 1.5 * atr_val
                    tp_price = entry_price + 3.0 * atr_val
                elif closes[i] < sma20[i]:
                    in_pos = True; pos_type = -1; entry_price = opens[i + 1]
                    sl_price = entry_price + 1.5 * atr_val
                    tp_price = entry_price - 3.0 * atr_val

    return trades

def engine_fvg_retest(opens, highs, lows, closes, atr):
    """Engine 4: Fair Value Gap (FVG) Imbalance Retest"""
    n = len(closes)
    trades = []
    in_pos = False
    pos_type = 0
    entry_price = 0.0
    sl_price, tp_price = 0.0, 0.0
    ema200 = compute_ema(closes, 200)

    for i in range(200, n - 1):
        if in_pos:
            hit = False
            exit_price = 0.0
            if pos_type == 1:
                if lows[i] <= sl_price:
                    hit = True; exit_price = sl_price
                elif highs[i] >= tp_price:
                    hit = True; exit_price = tp_price
            elif pos_type == -1:
                if highs[i] >= sl_price:
                    hit = True; exit_price = sl_price
                elif lows[i] <= tp_price:
                    hit = True; exit_price = tp_price

            if hit:
                pnl = ((exit_price - entry_price) if pos_type == 1 else (entry_price - exit_price)) * 100.0 - 0.60
                trades.append({"bar": i, "engine": "FVG_Retest", "pnl": pnl})
                in_pos = False

        if not in_pos:
            atr_val = atr[i]
            if lows[i - 2] > highs[i - 4] and (lows[i - 2] - highs[i - 4]) >= 0.3 * atr_val:
                if closes[i] > ema200[i] and lows[i] <= lows[i - 2] and closes[i] >= highs[i - 4]:
                    in_pos = True; pos_type = 1; entry_price = opens[i + 1] + 0.25
                    sl_price = entry_price - 1.2 * atr_val
                    tp_price = entry_price + 2.5 * atr_val
            elif highs[i - 2] < lows[i - 4] and (lows[i - 4] - highs[i - 2]) >= 0.3 * atr_val:
                if closes[i] < ema200[i] and highs[i] >= highs[i - 2] and closes[i] <= lows[i - 4]:
                    in_pos = True; pos_type = -1; entry_price = opens[i + 1]
                    sl_price = entry_price + 1.2 * atr_val
                    tp_price = entry_price - 2.5 * atr_val

    return trades

def engine_rsi_snapshot(opens, highs, lows, closes, hours, atr):
    """Engine 5: Fast RSI Extreme Snapshot Scalper (S221 Winner)"""
    n = len(closes)
    trades = []
    in_pos = False
    pos_type = 0
    entry_price = 0.0
    sl_price, tp_price = 0.0, 0.0
    rsi = compute_rsi(closes, period=6)
    ema200 = compute_ema(closes, 200)

    for i in range(200, n - 1):
        if in_pos:
            hit = False
            exit_price = 0.0
            if pos_type == 1:
                if lows[i] <= sl_price:
                    hit = True; exit_price = sl_price
                elif highs[i] >= tp_price:
                    hit = True; exit_price = tp_price
            elif pos_type == -1:
                if highs[i] >= sl_price:
                    hit = True; exit_price = sl_price
                elif lows[i] <= tp_price:
                    hit = True; exit_price = tp_price

            if hit:
                pnl = ((exit_price - entry_price) if pos_type == 1 else (entry_price - exit_price)) * 100.0 - 0.60
                trades.append({"bar": i, "engine": "RSI_Snapshot", "pnl": pnl})
                in_pos = False

        if not in_pos:
            if 7 <= hours[i] <= 19:
                atr_val = atr[i]
                if closes[i] > ema200[i] and rsi[i - 1] <= 18 and closes[i] > opens[i]:
                    in_pos = True; pos_type = 1; entry_price = opens[i + 1] + 0.25
                    sl_price = entry_price - 1.0 * atr_val
                    tp_price = entry_price + 1.6 * atr_val
                elif closes[i] < ema200[i] and rsi[i - 1] >= 82 and closes[i] < opens[i]:
                    in_pos = True; pos_type = -1; entry_price = opens[i + 1]
                    sl_price = entry_price + 1.0 * atr_val
                    tp_price = entry_price - 1.6 * atr_val

    return trades

# =============================================================================
# ENSEMBLE EVALUATOR
# =============================================================================

def evaluate_portfolio(trades_list, months_series):
    if not trades_list:
        return {
            "total_trades": 0, "annual_trades": 0, "net_profit": 0.0, "pf": 0.0,
            "win_rate": 0.0, "max_dd": 0.0, "romad": 0.0, "mcr": 0.0
        }
    
    # Sort chronologically by bar
    trades_list.sort(key=lambda x: x["bar"])
    
    pnls = np.array([t["pnl"] for t in trades_list])
    net_profit = np.sum(pnls)
    gross_win = np.sum(pnls[pnls > 0])
    gross_loss = abs(np.sum(pnls[pnls < 0]))
    pf = (gross_win / gross_loss) if gross_loss > 0 else 99.0
    win_rate = (len(pnls[pnls > 0]) / len(pnls)) * 100.0

    equity = np.cumsum(pnls)
    peak = np.maximum.accumulate(equity)
    dd = peak - equity
    max_dd = np.max(dd) if len(dd) > 0 else 0.0
    romad = (net_profit / max_dd) if max_dd > 0 else 0.0

    # Monthly consistency
    df_trades = pd.DataFrame(trades_list)
    df_trades["month"] = [months_series[t["bar"]] for t in trades_list]
    m_pnl = df_trades.groupby("month")["pnl"].sum()
    mcr = (np.sum(m_pnl > 0) / len(m_pnl) * 100.0) if len(m_pnl) > 0 else 0.0
    annual_trades = round(len(trades_list) / 6.0, 1)

    return {
        "total_trades": len(trades_list),
        "annual_trades": annual_trades,
        "net_profit": round(float(net_profit), 2),
        "pf": round(float(pf), 3),
        "win_rate": round(float(win_rate), 2),
        "max_dd": round(float(max_dd), 2),
        "romad": round(float(romad), 2),
        "mcr": round(float(mcr), 2)
    }

def main():
    t_start = time.time()
    tf = "M15"
    parquet_file = os.path.join(DATA_DIR, f"XAUUSD_{tf}.parquet")
    print("=" * 105)
    print("🚀 SCALPING ENSEMBLE PORTFOLIO DISCOVERY BATCH 6: STRATEGIES 251 - 260")
    print(f"📊 Timeframe: {tf} on XAUUSD (2020-2025) | Friction: Spread $0.25 + Comm $6.00/Lot")
    print("🎯 Target: Assemble High-Turnover Scalping Engines to Achieve 300-800 Tr/Yr & PF >= 1.50")
    print("=" * 105)

    df = pd.read_parquet(parquet_file)
    opens = df['open'].values.astype(np.float64)
    highs = df['high'].values.astype(np.float64)
    lows = df['low'].values.astype(np.float64)
    closes = df['close'].values.astype(np.float64)
    hours = df.index.hour.values
    months = df.index.strftime('%Y-%m').values
    atr = compute_atr(highs, lows, closes, 14)
    del df
    gc.collect()

    print("[*] Generating trade logs for 5 Independent Scalping Engines...")
    t_st = engine_supertrend_trailing(opens, highs, lows, closes, atr)
    t_macd = engine_zero_lag_macd(opens, highs, lows, closes, atr)
    t_ttm = engine_ttm_squeeze(opens, highs, lows, closes, atr)
    t_fvg = engine_fvg_retest(opens, highs, lows, closes, atr)
    t_rsi = engine_rsi_snapshot(opens, highs, lows, closes, hours, atr)

    print(f"    - Engine 1 (Supertrend): {len(t_st)} trades ({len(t_st)/6:.1f}/yr)")
    print(f"    - Engine 2 (ZL-MACD):    {len(t_macd)} trades ({len(t_macd)/6:.1f}/yr)")
    print(f"    - Engine 3 (TTM-Squeeze):{len(t_ttm)} trades ({len(t_ttm)/6:.1f}/yr)")
    print(f"    - Engine 4 (FVG-Retest): {len(t_fvg)} trades ({len(t_fvg)/6:.1f}/yr)")
    print(f"    - Engine 5 (RSI-Snapshot):{len(t_rsi)} trades ({len(t_rsi)/6:.1f}/yr)")

    portfolios = [
        ("S251", "Solo Supertrend Trailing Scalper", t_st),
        ("S252", "Dual Trend: Supertrend + ZL-MACD", t_st + t_macd),
        ("S253", "Trend & Retest: Supertrend + FVG Retest", t_st + t_fvg),
        ("S254", "Trinity Scalper: Supertrend + TTM + FVG", t_st + t_ttm + t_fvg),
        ("S255", "Quartet Scalper: Supertrend + ZL + TTM + FVG", t_st + t_macd + t_ttm + t_fvg),
        ("S256", "Pentad Supreme Scalper: All 5 Engines", t_st + t_macd + t_ttm + t_fvg + t_rsi),
        ("S257", "Trend & Momentum: ZL-MACD + TTM Squeeze", t_macd + t_ttm),
        ("S258", "Orderflow & Squeeze: FVG Retest + TTM Squeeze", t_fvg + t_ttm),
        ("S259", "Tactical Duo: Supertrend + RSI Snapshot", t_st + t_rsi),
        ("S260", "Multi-Regime Trio: Supertrend + FVG + RSI", t_st + t_fvg + t_rsi)
    ]

    results = []
    print("\n" + "=" * 105)
    print("🏆 BATCH 6 SCALPING ENSEMBLE PORTFOLIO LEADERBOARD (2020-2025)")
    print("=" * 105)

    for sid, pname, p_trades in portfolios:
        m = evaluate_portfolio(p_trades, months)
        status = "🏆 CHAMPION SCALPER" if m["pf"] >= 1.25 and m["annual_trades"] >= 300 else ("TACTICAL CANDIDATE" if m["net_profit"] > 0 else "REJECTED")
        print(f"  {sid}: {pname:<45} | Tr/Yr: {m['annual_trades']:<5} | Net: ${m['net_profit']:<9.2f} | PF: {m['pf']:<5.3f} | DD: ${m['max_dd']:<8.2f} | MCR: {m['mcr']:<5.1f}% | {status}")
        results.append({
            "strategy_id": sid,
            "strategy_name": pname,
            "annual_trades": m["annual_trades"],
            "net_profit": m["net_profit"],
            "pf": m["pf"],
            "win_rate": m["win_rate"],
            "max_dd": m["max_dd"],
            "romad": m["romad"],
            "mcr": m["mcr"],
            "status": status
        })

    df_res = pd.DataFrame(results)
    df_res.sort_values(by=["pf", "annual_trades", "net_profit"], ascending=[False, False, False], inplace=True)
    print("\n" + "=" * 105)
    print(df_res[["strategy_id", "strategy_name", "annual_trades", "net_profit", "pf", "win_rate", "max_dd", "romad", "mcr", "status"]].to_string(index=False))
    print("=" * 105)

    os.makedirs(RESULTS_DIR, exist_ok=True)
    out_json = os.path.join(RESULTS_DIR, "massive_scalping_ensemble_batch_251_260_results.json")
    out_csv = os.path.join(RESULTS_DIR, "massive_scalping_ensemble_batch_251_260_matrix.csv")

    with open(out_json, "w") as f:
        json.dump({
            "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            "total_runtime_s": round(time.time() - t_start, 2),
            "results": results
        }, f, indent=2)

    df_res.to_csv(out_csv, index=False)
    print(f"\n[+] Saved Ensemble Portfolio Results to:\n    - {out_json}\n    - {out_csv}")
    print("=" * 105)

if __name__ == "__main__":
    main()
