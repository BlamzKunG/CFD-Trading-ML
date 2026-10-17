#!/usr/bin/env python3
"""
===============================================================================
SCALPING MASTER ENSEMBLE BATCH 10: STRATEGIES 291 - 300
VALIDATING HIGH-TURNOVER MULTI-ENGINE SCALPING SUITES (300 - 1,200 TRADES/YR)
ON XAUUSD (M15) UNDER INSTITUTIONAL CFD FRICTIONS ($0.25 SPREAD + $6.00 COMM)
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
# Fast Indicator Helpers
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

# -----------------------------------------------------------------------------
# 1. Engine 03: Supertrend Dynamic Volatility Trailing Ratchet
# -----------------------------------------------------------------------------
def run_engine_supertrend(opens, highs, lows, closes, atr, ema200, months,
                          multiplier=3.0, unit_size=10.0, spread=0.25, comm=0.60):
    n = len(closes)
    upper = (highs + lows) / 2.0 + multiplier * atr
    lower = (highs + lows) / 2.0 - multiplier * atr
    trend = np.ones(n, dtype=np.int32)
    st = np.zeros(n, dtype=np.float64)

    for i in range(15, n):
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

    trades = []
    pos = 0
    entry_p = 0.0
    entry_idx = 0

    for i in range(200, n - 1):
        cur_t = trend[i]
        prev_t = trend[i - 1]
        cur_st = st[i]

        if pos == 1:
            hit = False
            exit_p = 0.0
            if lows[i] <= cur_st:
                exit_p = cur_st if opens[i] >= cur_st else opens[i]
                hit = True
            elif cur_t == -1:
                exit_p = opens[i + 1] - spread * 0.5
                hit = True
            if hit:
                pnl = (exit_p - entry_p) * unit_size - (spread + (comm / unit_size)) * unit_size
                trades.append({"pnl": pnl, "month": months[entry_idx], "entry_idx": entry_idx, "exit_idx": i, "engine": "Supertrend"})
                pos = 0

        elif pos == -1:
            hit = False
            exit_p = 0.0
            if highs[i] >= cur_st:
                exit_p = cur_st if opens[i] <= cur_st else opens[i]
                hit = True
            elif cur_t == 1:
                exit_p = opens[i + 1] + spread * 0.5
                hit = True
            if hit:
                pnl = (entry_p - exit_p) * unit_size - (spread + (comm / unit_size)) * unit_size
                trades.append({"pnl": pnl, "month": months[entry_idx], "entry_idx": entry_idx, "exit_idx": i, "engine": "Supertrend"})
                pos = 0

        if pos == 0:
            if cur_t == 1 and prev_t == -1 and closes[i] > ema200[i]:
                pos = 1
                entry_p = opens[i + 1] + spread * 0.5
                entry_idx = i + 1
            elif cur_t == -1 and prev_t == 1 and closes[i] < ema200[i]:
                pos = -1
                entry_p = opens[i + 1] - spread * 0.5
                entry_idx = i + 1

    return trades

# -----------------------------------------------------------------------------
# 2. Engine 06: Zero-Lag MACD Momentum Inflection
# -----------------------------------------------------------------------------
def run_engine_zl_macd(opens, highs, lows, closes, atr, months,
                       fast_p=15, slow_p=34, sig_p=9, sl_mult=2.0, tp_mult=4.0,
                       unit_size=10.0, spread=0.25, comm=0.60):
    n = len(closes)
    # Zero-lag EMA
    ema_fast1 = compute_ema(closes, fast_p)
    ema_fast2 = compute_ema(ema_fast1, fast_p)
    zl_fast = 2 * ema_fast1 - ema_fast2

    ema_slow1 = compute_ema(closes, slow_p)
    ema_slow2 = compute_ema(ema_slow1, slow_p)
    zl_slow = 2 * ema_slow1 - ema_slow2

    zl_macd = zl_fast - zl_slow
    zl_sig = compute_ema(zl_macd, sig_p)

    trades = []
    pos = 0
    entry_p = 0.0
    sl_p = 0.0
    tp_p = 0.0
    entry_idx = 0

    for i in range(slow_p * 2, n - 1):
        if pos == 1:
            hit = False
            exit_p = 0.0
            if lows[i] <= sl_p:
                hit = True
                exit_p = sl_p
            elif highs[i] >= tp_p:
                hit = True
                exit_p = tp_p
            if hit:
                pnl = (exit_p - entry_p) * unit_size - (spread + (comm / unit_size)) * unit_size
                trades.append({"pnl": pnl, "month": months[entry_idx], "entry_idx": entry_idx, "exit_idx": i, "engine": "ZL_MACD"})
                pos = 0

        elif pos == -1:
            hit = False
            exit_p = 0.0
            if highs[i] >= sl_p:
                hit = True
                exit_p = sl_p
            elif lows[i] <= tp_p:
                hit = True
                exit_p = tp_p
            if hit:
                pnl = (entry_p - exit_p) * unit_size - (spread + (comm / unit_size)) * unit_size
                trades.append({"pnl": pnl, "month": months[entry_idx], "entry_idx": entry_idx, "exit_idx": i, "engine": "ZL_MACD"})
                pos = 0

        if pos == 0:
            if zl_macd[i - 1] <= zl_sig[i - 1] and zl_macd[i] > zl_sig[i]:
                pos = 1
                entry_idx = i + 1
                entry_p = opens[i + 1] + spread * 0.5
                sl_dist = sl_mult * atr[i]
                sl_p = entry_p - sl_dist
                tp_p = entry_p + (tp_mult * sl_dist)
            elif zl_macd[i - 1] >= zl_sig[i - 1] and zl_macd[i] < zl_sig[i]:
                pos = -1
                entry_idx = i + 1
                entry_p = opens[i + 1] - spread * 0.5
                sl_dist = sl_mult * atr[i]
                sl_p = entry_p + sl_dist
                tp_p = entry_p - (tp_mult * sl_dist)

    return trades

# -----------------------------------------------------------------------------
# 3. Engine 04: TTM Squeeze Volatility Breakout
# -----------------------------------------------------------------------------
def run_engine_ttm_squeeze(opens, highs, lows, closes, atr, ema200, months,
                           bb_p=20, bb_mult=2.0, kc_mult=2.0, min_squeeze=8,
                           sl_mult=3.0, tp_mult=3.0, unit_size=10.0, spread=0.25, comm=0.60):
    n = len(closes)
    bb_mid = compute_ema(closes, bb_p)
    bb_std = pd.Series(closes).rolling(bb_p).std().fillna(1.0).values
    bb_up = bb_mid + bb_mult * bb_std
    bb_lo = bb_mid - bb_mult * bb_std

    kc_up = bb_mid + kc_mult * atr
    kc_lo = bb_mid - kc_mult * atr

    # Squeeze is on when BB is completely inside KC
    squeeze = (bb_up <= kc_up) & (bb_lo >= kc_lo)
    squeeze_bars = np.zeros(n, dtype=int)
    for i in range(1, n):
        if squeeze[i]:
            squeeze_bars[i] = squeeze_bars[i - 1] + 1
        else:
            squeeze_bars[i] = 0

    trades = []
    pos = 0
    entry_p = 0.0
    sl_p = 0.0
    tp_p = 0.0
    entry_idx = 0

    for i in range(bb_p * 2, n - 1):
        if pos == 1:
            hit = False
            exit_p = 0.0
            if lows[i] <= sl_p:
                hit = True
                exit_p = sl_p
            elif highs[i] >= tp_p:
                hit = True
                exit_p = tp_p
            if hit:
                pnl = (exit_p - entry_p) * unit_size - (spread + (comm / unit_size)) * unit_size
                trades.append({"pnl": pnl, "month": months[entry_idx], "entry_idx": entry_idx, "exit_idx": i, "engine": "TTM_Squeeze"})
                pos = 0

        elif pos == -1:
            hit = False
            exit_p = 0.0
            if highs[i] >= sl_p:
                hit = True
                exit_p = sl_p
            elif lows[i] <= tp_p:
                hit = True
                exit_p = tp_p
            if hit:
                pnl = (entry_p - exit_p) * unit_size - (spread + (comm / unit_size)) * unit_size
                trades.append({"pnl": pnl, "month": months[entry_idx], "entry_idx": entry_idx, "exit_idx": i, "engine": "TTM_Squeeze"})
                pos = 0

        if pos == 0:
            # Squeeze fired (was squeezing for >= min_squeeze bars, now broke out)
            if squeeze_bars[i - 1] >= min_squeeze and not squeeze[i]:
                if closes[i] > bb_mid[i] and closes[i] > ema200[i]:
                    pos = 1
                    entry_idx = i + 1
                    entry_p = opens[i + 1] + spread * 0.5
                    sl_dist = sl_mult * atr[i]
                    sl_p = entry_p - sl_dist
                    tp_p = entry_p + (tp_mult * sl_dist)
                elif closes[i] < bb_mid[i] and closes[i] < ema200[i]:
                    pos = -1
                    entry_idx = i + 1
                    entry_p = opens[i + 1] - spread * 0.5
                    sl_dist = sl_mult * atr[i]
                    sl_p = entry_p + sl_dist
                    tp_p = entry_p - (tp_mult * sl_dist)

    return trades

# -----------------------------------------------------------------------------
# 4. Engine 10: Fair Value Gap (FVG) Retest Mitigation
# -----------------------------------------------------------------------------
def run_engine_fvg_retest(opens, highs, lows, closes, atr, ema200, months,
                          min_gap_atr=0.4, sl_buf_atr=0.5, tp_rr=3.0,
                          unit_size=10.0, spread=0.25, comm=0.60):
    n = len(closes)
    trades = []
    pos = 0
    entry_p = 0.0
    sl_p = 0.0
    tp_p = 0.0
    entry_idx = 0

    bull_fvg_top = 0.0
    bull_fvg_bot = 0.0
    bull_active = False

    bear_fvg_top = 0.0
    bear_fvg_bot = 0.0
    bear_active = False

    for i in range(50, n - 1):
        # 1. Manage active position
        if pos == 1:
            hit = False
            exit_p = 0.0
            if lows[i] <= sl_p:
                hit = True
                exit_p = sl_p
            elif highs[i] >= tp_p:
                hit = True
                exit_p = tp_p
            if hit:
                pnl = (exit_p - entry_p) * unit_size - (spread + (comm / unit_size)) * unit_size
                trades.append({"pnl": pnl, "month": months[entry_idx], "entry_idx": entry_idx, "exit_idx": i, "engine": "FVG_Retest"})
                pos = 0

        elif pos == -1:
            hit = False
            exit_p = 0.0
            if highs[i] >= sl_p:
                hit = True
                exit_p = sl_p
            elif lows[i] <= tp_p:
                hit = True
                exit_p = tp_p
            if hit:
                pnl = (entry_p - exit_p) * unit_size - (spread + (comm / unit_size)) * unit_size
                trades.append({"pnl": pnl, "month": months[entry_idx], "entry_idx": entry_idx, "exit_idx": i, "engine": "FVG_Retest"})
                pos = 0

        # 2. Detect new FVG creation
        if lows[i] - highs[i - 2] >= min_gap_atr * atr[i]:
            bull_fvg_top = lows[i]
            bull_fvg_bot = highs[i - 2]
            bull_active = True
            bear_active = False
        elif lows[i - 2] - highs[i] >= min_gap_atr * atr[i]:
            bear_fvg_top = lows[i - 2]
            bear_fvg_bot = highs[i]
            bear_active = True
            bull_active = False

        # 3. Check Retest Entry
        if pos == 0:
            if bull_active and closes[i] > ema200[i]:
                if lows[i] <= bull_fvg_top:
                    pos = 1
                    entry_idx = i + 1
                    entry_p = opens[i + 1] + spread * 0.5
                    sl_dist = (entry_p - bull_fvg_bot) + (sl_buf_atr * atr[i])
                    sl_p = entry_p - max(sl_dist, 1.0 * atr[i])
                    tp_p = entry_p + tp_rr * (entry_p - sl_p)
                    bull_active = False
            elif bear_active and closes[i] < ema200[i]:
                if highs[i] >= bear_fvg_bot:
                    pos = -1
                    entry_idx = i + 1
                    entry_p = opens[i + 1] - spread * 0.5
                    sl_dist = (bear_fvg_top - entry_p) + (sl_buf_atr * atr[i])
                    sl_p = entry_p + max(sl_dist, 1.0 * atr[i])
                    tp_p = entry_p - tp_rr * (sl_p - entry_p)
                    bear_active = False

    return trades

# -----------------------------------------------------------------------------
# Metrics Analyzer
# -----------------------------------------------------------------------------
def analyze_trades(trades, name, strategy_id):
    if not trades:
        return {"strategy_id": strategy_id, "strategy_name": name, "annual_trades": 0, "net_profit": 0, "pf": 0, "win_rate": 0, "max_dd": 0, "romad": 0, "mcr": 0, "status": "REJECTED"}

    # Sort trades by entry time
    trades_sorted = sorted(trades, key=lambda x: x["entry_idx"])
    pnls = np.array([t["pnl"] for t in trades_sorted])
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

    df_t = pd.DataFrame(trades_sorted)
    m_pnl = df_t.groupby("month")["pnl"].sum()
    total_months = len(m_pnl)
    win_months = np.sum(m_pnl > 0)
    mcr = (win_months / total_months * 100.0) if total_months > 0 else 0.0
    annual_trades = round(len(trades_sorted) / 6.0, 1)

    status = "CHAMPION" if (pf >= 1.25 and annual_trades >= 300) else ("TACTICAL CANDIDATE" if net_profit > 0 else "REJECTED")

    return {
        "strategy_id": strategy_id,
        "strategy_name": name,
        "total_trades": len(trades_sorted),
        "annual_trades": annual_trades,
        "net_profit": round(float(net_profit), 2),
        "pf": round(float(pf), 3),
        "win_rate": round(float(win_rate), 2),
        "max_dd": round(float(max_dd), 2),
        "romad": round(float(romad), 2),
        "mcr": round(float(mcr), 2),
        "status": status
    }

# -----------------------------------------------------------------------------
# Main Execution Pipeline
# -----------------------------------------------------------------------------
def main():
    print("=" * 80)
    print("STARTING SCALPING MASTER ENSEMBLE BATCH 10: STRATEGIES 291 - 300")
    print("VALIDATING MULTI-ENGINE HIGH-TURNOVER SCALPING SUITES ON XAUUSD (M15)")
    print("=" * 80)
    t0 = time.time()

    print("Loading XAUUSD M15 Dataset...")
    df_m15 = pd.read_parquet(os.path.join(DATA_DIR, "XAUUSD_M15.parquet"))
    opens = df_m15["open"].values.astype(np.float64)
    highs = df_m15["high"].values.astype(np.float64)
    lows = df_m15["low"].values.astype(np.float64)
    closes = df_m15["close"].values.astype(np.float64)
    dates = df_m15.index
    months = np.array([f"{d.year}-{d.month:02d}" for d in dates])

    print("Computing technical features...")
    atr14 = compute_atr(highs, lows, closes, 14)
    ema200 = compute_ema(closes, 200)

    print("\nRunning Individual Core Engines...")
    t_st = run_engine_supertrend(opens, highs, lows, closes, atr14, ema200, months)
    print(f"-> Engine 03 (Supertrend Trailing) generated {len(t_st)} trades ({len(t_st)/6.0:.1f} tr/yr)")

    t_macd = run_engine_zl_macd(opens, highs, lows, closes, atr14, months)
    print(f"-> Engine 06 (Zero-Lag MACD) generated {len(t_macd)} trades ({len(t_macd)/6.0:.1f} tr/yr)")

    t_ttm = run_engine_ttm_squeeze(opens, highs, lows, closes, atr14, ema200, months)
    print(f"-> Engine 04 (TTM Squeeze) generated {len(t_ttm)} trades ({len(t_ttm)/6.0:.1f} tr/yr)")

    t_fvg = run_engine_fvg_retest(opens, highs, lows, closes, atr14, ema200, months)
    print(f"-> Engine 10 (FVG Retest) generated {len(t_fvg)} trades ({len(t_fvg)/6.0:.1f} tr/yr)")

    results = []

    # 1. S291: Solo Supertrend Trailing
    results.append(analyze_trades(t_st, "Solo Supertrend Trailing Core", "S291"))

    # 2. S292: Solo Zero-Lag MACD
    results.append(analyze_trades(t_macd, "Solo Zero-Lag MACD 4R", "S292"))

    # 3. S293: Solo TTM Squeeze Breakout
    results.append(analyze_trades(t_ttm, "Solo TTM Squeeze Breakout 3R", "S293"))

    # 4. S294: Solo FVG Retest Mitigation
    results.append(analyze_trades(t_fvg, "Solo FVG Retest Mitigation 3R", "S294"))

    # 5. S295: Tactical Duo A: Supertrend + Zero-Lag MACD
    results.append(analyze_trades(t_st + t_macd, "Tactical Duo A: Supertrend + ZL-MACD", "S295"))

    # 6. S296: Tactical Duo B: Supertrend + TTM Squeeze
    results.append(analyze_trades(t_st + t_ttm, "Tactical Duo B: Supertrend + TTM Squeeze", "S296"))

    # 7. S297: Tactical Duo C: Supertrend + FVG Retest
    results.append(analyze_trades(t_st + t_fvg, "Tactical Duo C: Supertrend + FVG Retest", "S297"))

    # 8. S298: Dynamic Trinity: Supertrend + ZL-MACD + TTM Squeeze
    results.append(analyze_trades(t_st + t_macd + t_ttm, "Dynamic Trinity: Supertrend + ZL-MACD + TTM", "S298"))

    # 9. S299: Sovereign Quartet: Supertrend + ZL-MACD + TTM + FVG
    results.append(analyze_trades(t_st + t_macd + t_ttm + t_fvg, "Sovereign Quartet: ST + ZL + TTM + FVG", "S299"))

    # 10. S300: Production Scalper Master Suite (Dynamic Risk Balanced 4-Engine Suite)
    # Balanced weights: ST (0.10 lot), ZL (0.07 lot), TTM (0.08 lot), FVG (0.05 lot)
    t_weighted = []
    for t in t_st:
        tw = dict(t); tw["pnl"] = t["pnl"] * 1.0; t_weighted.append(tw)
    for t in t_macd:
        tw = dict(t); tw["pnl"] = t["pnl"] * 0.7; t_weighted.append(tw)
    for t in t_ttm:
        tw = dict(t); tw["pnl"] = t["pnl"] * 0.8; t_weighted.append(tw)
    for t in t_fvg:
        tw = dict(t); tw["pnl"] = t["pnl"] * 0.5; t_weighted.append(tw)

    results.append(analyze_trades(t_weighted, "Master Scalper Balanced Suite (ST+ZL+TTM+FVG)", "S300"))

    df_out = pd.DataFrame(results)
    csv_path = os.path.join(RESULTS_DIR, "massive_scalping_master_ensemble_batch_291_300_matrix.csv")
    json_path = os.path.join(RESULTS_DIR, "massive_scalping_master_ensemble_batch_291_300_results.json")

    df_out.to_csv(csv_path, index=False)
    with open(json_path, "w") as f:
        json.dump({"generated_at": time.strftime("%Y-%m-%d %H:%M:%S"), "total_runtime_s": round(time.time() - t0, 2), "results": results}, f, indent=2)

    print("\n" + "=" * 80)
    print("BATCH 10 (S291 - S300) COMPLETED IN {:.2f}s".format(time.time() - t0))
    print("=" * 80)
    print(df_out[["strategy_id", "strategy_name", "annual_trades", "net_profit", "pf", "win_rate", "max_dd", "romad", "mcr", "status"]].to_string(index=False))
    print("=" * 80)

if __name__ == "__main__":
    main()
