#!/usr/bin/env python3
"""
===============================================================================
SCALPING FRONTIER BATCH 14: STRATEGIES 331 - 340
SESSION MOMENTUM BREAKOUT CONTINUATION (LONDON & NY VOLATILITY EXPANSION)
===============================================================================
Hypothesis:
Gold is a fat-tailed trending commodity. While fading session extremes (Judas swing)
struggles under trend expansion, entering IN THE DIRECTION OF THE BREAKOUT
(Asian Range Breakout at London Open & London Range Breakout at NY Open) paired with
dynamic ratchet trailing exits captures massive directional runs at low risk.
===============================================================================
"""

import os
import sys
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

from simulate_scalping_master_ensemble_batch_291_300 import (
    run_engine_supertrend, run_engine_ttm_squeeze, compute_atr, compute_ema
)

def run_session_breakout_sim(opens, highs, lows, closes, atr, ema200, dates,
                             mode="asian_london", use_ema=True, min_atr_gate=0.0,
                             trailing_mult=3.0, sl_mult=1.5,
                             spread=0.25, comm=0.60, unit_size=10.0):
    n = len(closes)
    trades = []
    in_pos = False
    pos = 0
    entry_p = 0.0
    stop_p = 0.0
    extreme_p = 0.0
    entry_idx = 0

    months = np.array([f"{d.year}-{d.month:02d}" for d in dates])
    hours = np.array([d.hour for d in dates])
    day_tags = np.array([d.strftime("%Y-%m-%d") for d in dates])

    df_bars = pd.DataFrame({
        "open": opens, "high": highs, "low": lows, "close": closes,
        "hour": hours, "day": day_tags
    }, index=dates)

    # 1. Asian range: 00:00 to 06:45 UTC
    asian_df = df_bars[df_bars["hour"] < 7].groupby("day").agg({"high": "max", "low": "min"})
    asian_high_map = asian_df["high"].to_dict()
    asian_low_map = asian_df["low"].to_dict()

    # 2. London range: 07:00 to 11:45 UTC
    london_df = df_bars[(df_bars["hour"] >= 7) & (df_bars["hour"] < 12)].groupby("day").agg({"high": "max", "low": "min"})
    london_high_map = london_df["high"].to_dict()
    london_low_map = london_df["low"].to_dict()

    trades_today = 0
    cur_day = ""

    for i in range(50, n - 1):
        d_tag = day_tags[i]
        hr = hours[i]
        if d_tag != cur_day:
            cur_day = d_tag
            trades_today = 0

        # Position exit management (Ratchet Trailing Stop)
        if in_pos:
            hit = False
            exit_p = 0.0
            trail_dist = trailing_mult * atr[i]

            if pos == 1:
                if highs[i] > extreme_p:
                    extreme_p = highs[i]
                    new_stop = extreme_p - trail_dist
                    if new_stop > stop_p: stop_p = new_stop
                if lows[i] <= stop_p:
                    hit = True; exit_p = min(stop_p, opens[i]) - spread * 0.5
            elif pos == -1:
                if lows[i] < extreme_p:
                    extreme_p = lows[i]
                    new_stop = extreme_p + trail_dist
                    if new_stop < stop_p: stop_p = new_stop
                if highs[i] >= stop_p:
                    hit = True; exit_p = max(stop_p, opens[i]) + spread * 0.5

            if hit:
                pnl = ((exit_p - entry_p) if (pos == 1) else (entry_p - exit_p)) * unit_size - (spread + (comm / unit_size)) * unit_size
                trades.append({"pnl": pnl, "month": months[entry_idx], "entry_idx": entry_idx, "exit_idx": i, "type": "Long" if pos==1 else "Short"})
                in_pos = False
                continue

        # Signal check (Breakout in direction of momentum)
        if not in_pos and trades_today < 2:
            if min_atr_gate > 0 and atr[i] < min_atr_gate:
                continue

            sig_long = False
            sig_short = False

            if mode in ["asian_london", "both"]:
                if 7 <= hr <= 11 and d_tag in asian_high_map:
                    ref_h = asian_high_map[d_tag]
                    ref_l = asian_low_map[d_tag]
                    if closes[i] > ref_h and (not use_ema or closes[i] > ema200[i]):
                        sig_long = True
                    elif closes[i] < ref_l and (not use_ema or closes[i] < ema200[i]):
                        sig_short = True

            if mode in ["london_ny", "both"] and not (sig_long or sig_short):
                if 12 <= hr <= 16 and d_tag in london_high_map:
                    ref_h = london_high_map[d_tag]
                    ref_l = london_low_map[d_tag]
                    if closes[i] > ref_h and (not use_ema or closes[i] > ema200[i]):
                        sig_long = True
                    elif closes[i] < ref_l and (not use_ema or closes[i] < ema200[i]):
                        sig_short = True

            if sig_long:
                in_pos = True
                pos = 1
                entry_idx = i + 1
                entry_p = opens[i + 1] + spread * 0.5
                extreme_p = entry_p
                stop_p = entry_p - sl_mult * atr[i]
                trades_today += 1
            elif sig_short:
                in_pos = True
                pos = -1
                entry_idx = i + 1
                entry_p = opens[i + 1] - spread * 0.5
                extreme_p = entry_p
                stop_p = entry_p + sl_mult * atr[i]
                trades_today += 1

    return trades

def analyze_trade_list(trades, name, strategy_id):
    if not trades:
        return {"strategy_id": strategy_id, "strategy_name": name, "annual_trades": 0, "net_profit": 0, "pf": 0, "win_rate": 0, "max_dd": 0, "romad": 0, "mcr": 0, "status": "REJECTED"}

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
    mcr = (np.sum(m_pnl > 0) / len(m_pnl) * 100.0) if len(m_pnl) > 0 else 0.0
    annual_trades = round(len(trades_sorted) / 6.0, 1)

    status = "CHAMPION" if (pf >= 1.20 and annual_trades >= 150) else ("TACTICAL CANDIDATE" if net_profit > 0 else "REJECTED")

    return {
        "strategy_id": strategy_id,
        "strategy_name": name,
        "annual_trades": annual_trades,
        "net_profit": round(float(net_profit), 2),
        "pf": round(float(pf), 3),
        "win_rate": round(float(win_rate), 2),
        "max_dd": round(float(max_dd), 2),
        "romad": round(float(romad), 2),
        "mcr": round(float(mcr), 2),
        "status": status,
        "trades": trades_sorted
    }

def main():
    print("=" * 80)
    print("STARTING SCALPING FRONTIER BATCH 14: STRATEGIES 331 - 340")
    print("SESSION MOMENTUM BREAKOUT CONTINUATION (LONDON & NY VOLATILITY EXPANSION)")
    print("=" * 80)
    t0 = time.time()

    df_m15 = pd.read_parquet(os.path.join(DATA_DIR, "XAUUSD_M15.parquet"))
    opens = df_m15["open"].values.astype(np.float64)
    highs = df_m15["high"].values.astype(np.float64)
    lows = df_m15["low"].values.astype(np.float64)
    closes = df_m15["close"].values.astype(np.float64)
    dates = df_m15.index

    atr14 = compute_atr(highs, lows, closes, 14)
    ema200 = compute_ema(closes, 200)

    print("Running Session Momentum Breakout Simulations...")
    t_asian_unfiltered = run_session_breakout_sim(opens, highs, lows, closes, atr14, ema200, dates, mode="asian_london", use_ema=False)
    t_asian_filtered = run_session_breakout_sim(opens, highs, lows, closes, atr14, ema200, dates, mode="asian_london", use_ema=True)
    t_london_unfiltered = run_session_breakout_sim(opens, highs, lows, closes, atr14, ema200, dates, mode="london_ny", use_ema=False)
    t_london_filtered = run_session_breakout_sim(opens, highs, lows, closes, atr14, ema200, dates, mode="london_ny", use_ema=True)
    t_dual_filtered = run_session_breakout_sim(opens, highs, lows, closes, atr14, ema200, dates, mode="both", use_ema=True)
    t_dual_vol_gated = run_session_breakout_sim(opens, highs, lows, closes, atr14, ema200, dates, mode="both", use_ema=True, min_atr_gate=2.0)

    # Core Champions from previous batches
    months = np.array([f"{d.year}-{d.month:02d}" for d in dates])
    t_st = run_engine_supertrend(opens, highs, lows, closes, atr14, ema200, months)
    t_ttm = run_engine_ttm_squeeze(opens, highs, lows, closes, atr14, ema200, months)
    t_296 = t_st + t_ttm

    results = []

    # S331: Asian Range Breakout (London Open, Unfiltered)
    res_331 = analyze_trade_list(t_asian_unfiltered, "Asian Breakout London Open (Unfiltered)", "S331")
    results.append(res_331)

    # S332: Asian Range Breakout (London Open + EMA 200 Filter)
    res_332 = analyze_trade_list(t_asian_filtered, "Asian Breakout London Open (EMA 200 Filter)", "S332")
    results.append(res_332)

    # S333: London Range Breakout (NY Open, Unfiltered)
    res_333 = analyze_trade_list(t_london_unfiltered, "London Breakout NY Open (Unfiltered)", "S333")
    results.append(res_333)

    # S334: London Range Breakout (NY Open + EMA 200 Filter)
    res_334 = analyze_trade_list(t_london_filtered, "London Breakout NY Open (EMA 200 Filter)", "S334")
    results.append(res_334)

    # S335: Dual-Session Breakout Expansion (London + NY + EMA 200)
    res_335 = analyze_trade_list(t_dual_filtered, "Dual-Session Breakout Expansion (EMA 200)", "S335")
    results.append(res_335)

    # S336: Volatility-Gated Dual Breakout (ATR >= $2.00)
    res_336 = analyze_trade_list(t_dual_vol_gated, "Volatility-Gated Dual Breakout (ATR >= $2.00)", "S336")
    results.append(res_336)

    # S337: Trend-Breakout Duo: S291 Supertrend + S332 Asian Breakout
    res_337 = analyze_trade_list(t_st + t_asian_filtered, "Trend-Breakout Duo: Supertrend + Asian Breakout", "S337")
    results.append(res_337)

    # S338: Trend-Breakout Duo: S291 Supertrend + S335 Dual-Session Breakout
    res_338 = analyze_trade_list(t_st + t_dual_filtered, "Trend-Breakout Duo: Supertrend + Dual Breakout", "S338")
    results.append(res_338)

    # S339: Sovereign Trend-Breakout Trinity: S296 (ST+TTM) + S335 Dual Breakout
    res_339 = analyze_trade_list(t_296 + t_dual_filtered, "Sovereign Trend-Breakout Trinity: S296 + Dual Breakout", "S339")
    results.append(res_339)

    # S340: Master Sovereign Breakout Suite (ST + TTM + Asian + London Balanced)
    # Balanced weights: ST (1.0), TTM (0.8), Asian (0.7), London (0.7)
    t_340 = []
    for t in t_st: tw = dict(t); tw["pnl"] = t["pnl"] * 1.0; t_340.append(tw)
    for t in t_ttm: tw = dict(t); tw["pnl"] = t["pnl"] * 0.8; t_340.append(tw)
    for t in t_asian_filtered: tw = dict(t); tw["pnl"] = t["pnl"] * 0.7; t_340.append(tw)
    for t in t_london_filtered: tw = dict(t); tw["pnl"] = t["pnl"] * 0.7; t_340.append(tw)
    res_340 = analyze_trade_list(t_340, "Master Sovereign Breakout Suite (Balanced)", "S340")
    results.append(res_340)

    for r in results:
        if "trades" in r: del r["trades"]

    df_out = pd.DataFrame(results)
    csv_path = os.path.join(RESULTS_DIR, "massive_scalping_session_breakout_batch_331_340_matrix.csv")
    json_path = os.path.join(RESULTS_DIR, "massive_scalping_session_breakout_batch_331_340_results.json")
    df_out.to_csv(csv_path, index=False)
    with open(json_path, "w") as f:
        json.dump({"generated_at": time.strftime("%Y-%m-%d %H:%M:%S"), "total_runtime_s": round(time.time() - t0, 2), "results": results}, f, indent=2)

    print("\n" + "=" * 80)
    print("BATCH 14 SESSION BREAKOUT AUDIT COMPLETED IN {:.2f}s".format(time.time() - t0))
    print("=" * 80)
    print(df_out[["strategy_id", "strategy_name", "annual_trades", "net_profit", "pf", "win_rate", "max_dd", "romad", "mcr", "status"]].to_string(index=False))
    print("=" * 80)

if __name__ == "__main__":
    main()
