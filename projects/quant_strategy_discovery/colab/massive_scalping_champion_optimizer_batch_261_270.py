#!/usr/bin/env python3
"""
===============================================================================
SCALPING CHAMPION OPTIMIZER BATCH 7: STRATEGIES 261 - 270
FINE-TUNING SUPERTREND & DUAL-ENGINE SCALPER TO ACHIEVE PF >= 1.40 - 1.55+
TARGETING 300 - 500 TRADES/YEAR ON XAUUSD (M15 / M5)
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

def run_supertrend_optimized(opens, highs, lows, closes, hours, months,
                             atr_period=14, multiplier=3.0, ema_period=200,
                             session_mode="24h", tp_mult=0.0):
    n = len(closes)
    atr = compute_atr(highs, lows, closes, atr_period)
    ema = compute_ema(closes, ema_period) if ema_period > 0 else np.zeros(n)
    upper = (highs + lows) / 2.0 + multiplier * atr
    lower = (highs + lows) / 2.0 - multiplier * atr
    trend = np.ones(n, dtype=np.int32)

    trades = []
    in_pos = False
    pos_type = 0
    entry_price = 0.0
    entry_idx = 0
    point_value = 100.0

    for i in range(max(ema_period, atr_period) + 1, n - 1):
        if closes[i - 1] > lower[i - 1]:
            lower[i] = max(lower[i], lower[i - 1])
        if closes[i - 1] < upper[i - 1]:
            upper[i] = min(upper[i], upper[i - 1])

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

        # Session filter check
        in_session = True
        if session_mode == "London_NY":
            in_session = (7 <= hours[i] <= 19)

        # Exit
        if in_pos:
            hit = False
            exit_price = 0.0
            if pos_type == 1 and (lows[i] <= lower[i] or flip_bear):
                hit = True
                exit_price = min(lower[i], opens[i]) - 0.25
            elif pos_type == -1 and (highs[i] >= upper[i] or flip_bull):
                hit = True
                exit_price = max(upper[i], opens[i])

            if hit:
                pnl = ((exit_price - entry_price) if pos_type == 1 else (entry_price - exit_price)) * point_value - 0.60
                trades.append({"bar": i, "month": months[entry_idx], "pnl": pnl})
                in_pos = False

        # Entry
        if not in_pos and in_session:
            if flip_bull and (ema_period == 0 or closes[i] > ema[i]):
                in_pos = True
                pos_type = 1
                entry_idx = i + 1
                entry_price = opens[i + 1] + 0.25
            elif flip_bear and (ema_period == 0 or closes[i] < ema[i]):
                in_pos = True
                pos_type = -1
                entry_idx = i + 1
                entry_price = opens[i + 1]

    if not trades:
        return {"total_trades": 0, "annual_trades": 0, "net_profit": 0, "pf": 0, "win_rate": 0, "max_dd": 0, "mcr": 0}

    pnls = np.array([t["pnl"] for t in trades])
    net_profit = np.sum(pnls)
    gw = np.sum(pnls[pnls > 0])
    gl = abs(np.sum(pnls[pnls < 0]))
    pf = (gw / gl) if gl > 0 else 99.0
    win_rate = len(pnls[pnls > 0]) / len(pnls) * 100.0
    eq = np.cumsum(pnls)
    peak = np.maximum.accumulate(eq)
    max_dd = np.max(peak - eq) if len(eq) > 0 else 0.0
    
    df_t = pd.DataFrame(trades)
    m_pnl = df_t.groupby("month")["pnl"].sum()
    mcr = np.sum(m_pnl > 0) / len(m_pnl) * 100.0

    return {
        "total_trades": len(trades),
        "annual_trades": round(len(trades) / 6.0, 1),
        "net_profit": round(float(net_profit), 2),
        "pf": round(float(pf), 3),
        "win_rate": round(float(win_rate), 2),
        "max_dd": round(float(max_dd), 2),
        "mcr": round(float(mcr), 2)
    }

def main():
    t_start = time.time()
    tf = "M15"
    parquet_file = os.path.join(DATA_DIR, f"XAUUSD_{tf}.parquet")
    print("=" * 105)
    print("🚀 SCALPING CHAMPION OPTIMIZER BATCH 7: STRATEGIES 261 - 270")
    print(f"📊 Fine-tuning Supertrend Trailing & Multi-TF Scalpers on XAUUSD (2020-2025)")
    print(f"🎯 Target: Profit Factor >= 1.40 - 1.55+ & Annual Trades ~300+ / Year")
    print("=" * 105)

    df = pd.read_parquet(parquet_file)
    opens = df['open'].values.astype(np.float64)
    highs = df['high'].values.astype(np.float64)
    lows = df['low'].values.astype(np.float64)
    closes = df['close'].values.astype(np.float64)
    hours = df.index.hour.values
    months = df.index.strftime('%Y-%m').values
    del df
    gc.collect()

    configs = [
        ("S261", "Supertrend (ATR 14, Mult 3.0, EMA 200, 24h)", 14, 3.0, 200, "24h"),
        ("S262", "Supertrend (ATR 14, Mult 3.0, EMA 200, London/NY)", 14, 3.0, 200, "London_NY"),
        ("S263", "Supertrend (ATR 10, Mult 2.5, EMA 200, 24h)", 10, 2.5, 200, "24h"),
        ("S264", "Supertrend (ATR 10, Mult 2.5, EMA 200, London/NY)", 10, 2.5, 200, "London_NY"),
        ("S265", "Supertrend (ATR 14, Mult 3.5, EMA 200, 24h)", 14, 3.5, 200, "24h"),
        ("S266", "Supertrend (ATR 14, Mult 3.5, EMA 100, 24h)", 14, 3.5, 100, "24h"),
        ("S267", "Supertrend (ATR 7,  Mult 2.2, EMA 200, London/NY)", 7, 2.2, 200, "London_NY"),
        ("S268", "Supertrend (ATR 14, Mult 3.0, EMA 300, 24h)", 14, 3.0, 300, "24h"),
        ("S269", "Supertrend (ATR 20, Mult 3.0, EMA 200, 24h)", 20, 3.0, 200, "24h"),
        ("S270", "Supertrend (ATR 14, Mult 2.8, EMA 200, 24h)", 14, 2.8, 200, "24h")
    ]

    results = []
    print("\n" + "=" * 105)
    print("🏆 BATCH 7 SUPERTREND SCALPING CHAMPION LEADERBOARD (2020-2025)")
    print("=" * 105)

    for sid, sname, ap, mult, ema_p, sess in configs:
        t0 = time.time()
        m = run_supertrend_optimized(opens, highs, lows, closes, hours, months,
                                     atr_period=ap, multiplier=mult, ema_period=ema_p, session_mode=sess)
        dur = round(time.time() - t0, 2)
        status = "🏆 CHAMPION SCALPER" if m["pf"] >= 1.35 and m["annual_trades"] >= 250 else ("TACTICAL CANDIDATE" if m["net_profit"] > 0 else "REJECTED")
        print(f"  {sid}: {sname:<55} | Tr/Yr: {m['annual_trades']:<5} | Net: ${m['net_profit']:<9.2f} | PF: {m['pf']:<5.3f} | DD: ${m['max_dd']:<8.2f} | MCR: {m['mcr']:<5.1f}% | {status} ({dur}s)")
        results.append({
            "strategy_id": sid,
            "strategy_name": sname,
            "annual_trades": m["annual_trades"],
            "net_profit": m["net_profit"],
            "pf": m["pf"],
            "win_rate": m["win_rate"],
            "max_dd": m["max_dd"],
            "mcr": m["mcr"],
            "status": status
        })

    df_res = pd.DataFrame(results)
    df_res.sort_values(by=["pf", "annual_trades", "net_profit"], ascending=[False, False, False], inplace=True)
    print("\n" + "=" * 105)
    print(df_res[["strategy_id", "strategy_name", "annual_trades", "net_profit", "pf", "win_rate", "max_dd", "mcr", "status"]].to_string(index=False))
    print("=" * 105)

    os.makedirs(RESULTS_DIR, exist_ok=True)
    out_json = os.path.join(RESULTS_DIR, "massive_scalping_champion_batch_261_270_results.json")
    out_csv = os.path.join(RESULTS_DIR, "massive_scalping_champion_batch_261_270_matrix.csv")

    with open(out_json, "w") as f:
        json.dump({
            "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            "total_runtime_s": round(time.time() - t_start, 2),
            "results": results
        }, f, indent=2)

    df_res.to_csv(out_csv, index=False)
    print(f"\n[+] Saved Results to {out_csv}")

if __name__ == "__main__":
    main()
