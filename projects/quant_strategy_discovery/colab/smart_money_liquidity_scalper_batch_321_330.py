#!/usr/bin/env python3
"""
===============================================================================
SCALPING FRONTIER BATCH 13: STRATEGIES 321 - 330
SMART MONEY CONCEPTS (SMC) & MULTI-SESSION LIQUIDITY HUNTING SCALPERS
===============================================================================
Core Mechanisms:
1. Asian Liquidity Sweep (00:00 - 06:00 UTC Asian High/Low swept at London Open 07-11 UTC)
2. London Liquidity Sweep (07:00 - 12:00 UTC London High/Low swept at NY Open 12-16 UTC)
3. Previous Day High/Low (PDH/PDL) Sweep & Structural Rejection
4. Equal Highs / Equal Lows (EQH/EQL) Purge & Reversal
5. Multi-Session Liquidity Trap Ensemble & S296 Hybridization
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

def run_liquidity_sweep_sim(opens, highs, lows, closes, atr, dates,
                            sweep_type="asian_london", min_sweep_atr=0.4,
                            tp_rr=3.5, sl_buf_atr=0.4,
                            spread=0.25, comm=0.60, unit_size=10.0):
    n = len(closes)
    trades = []
    in_pos = False
    pos = 0
    entry_p = 0.0
    sl_p = 0.0
    tp_p = 0.0
    entry_idx = 0

    months = np.array([f"{d.year}-{d.month:02d}" for d in dates])
    hours = np.array([d.hour for d in dates])
    day_tags = np.array([d.strftime("%Y-%m-%d") for d in dates])

    # Precompute session high/low per day
    df_bars = pd.DataFrame({
        "open": opens, "high": highs, "low": lows, "close": closes,
        "hour": hours, "day": day_tags
    }, index=dates)

    # 1. Asian session: 00:00 to 06:45 UTC
    asian_df = df_bars[df_bars["hour"] < 7].groupby("day").agg({"high": "max", "low": "min"})
    asian_high_map = asian_df["high"].to_dict()
    asian_low_map = asian_df["low"].to_dict()

    # 2. London session: 07:00 to 11:45 UTC
    london_df = df_bars[(df_bars["hour"] >= 7) & (df_bars["hour"] < 12)].groupby("day").agg({"high": "max", "low": "min"})
    london_high_map = london_df["high"].to_dict()
    london_low_map = london_df["low"].to_dict()

    # 3. Previous Day:
    prev_day_df = df_bars.groupby("day").agg({"high": "max", "low": "min"}).shift(1)
    pdh_map = prev_day_df["high"].to_dict()
    pdl_map = prev_day_df["low"].to_dict()

    trades_today = 0
    cur_day = ""

    for i in range(50, n - 1):
        d_tag = day_tags[i]
        hr = hours[i]
        if d_tag != cur_day:
            cur_day = d_tag
            trades_today = 0

        # Position management
        if in_pos:
            hit = False
            exit_p = 0.0
            if pos == 1:
                if lows[i] <= sl_p:
                    hit = True; exit_p = sl_p
                elif highs[i] >= tp_p:
                    hit = True; exit_p = tp_p
                if hit:
                    pnl = (exit_p - entry_p) * unit_size - (spread + (comm / unit_size)) * unit_size
                    trades.append({"pnl": pnl, "month": months[entry_idx], "entry_idx": entry_idx, "exit_idx": i, "type": "Long"})
                    in_pos = False
                    continue
            elif pos == -1:
                if highs[i] >= sl_p:
                    hit = True; exit_p = sl_p
                elif lows[i] <= tp_p:
                    hit = True; exit_p = tp_p
                if hit:
                    pnl = (entry_p - exit_p) * unit_size - (spread + (comm / unit_size)) * unit_size
                    trades.append({"pnl": pnl, "month": months[entry_idx], "entry_idx": entry_idx, "exit_idx": i, "type": "Short"})
                    in_pos = False
                    continue

        # Signal check
        if not in_pos and trades_today < 2:
            sig_long = False
            sig_short = False
            ref_high = 0.0
            ref_low = 0.0

            if sweep_type == "asian_london":
                # Look for Asian sweeps during London Open (07:00 - 11:00 UTC)
                if 7 <= hr <= 11 and d_tag in asian_high_map and d_tag in asian_low_map:
                    ref_high = asian_high_map[d_tag]
                    ref_low = asian_low_map[d_tag]
            elif sweep_type == "london_ny":
                # Look for London sweeps during NY Open (12:00 - 16:00 UTC)
                if 12 <= hr <= 16 and d_tag in london_high_map and d_tag in london_low_map:
                    ref_high = london_high_map[d_tag]
                    ref_low = london_low_map[d_tag]
            elif sweep_type == "pdh_pdl":
                # Previous Day High / Low sweep (08:00 - 17:00 UTC)
                if 8 <= hr <= 17 and d_tag in pdh_map and d_tag in pdl_map:
                    ref_high = pdh_map[d_tag]
                    ref_low = pdl_map[d_tag]
            elif sweep_type == "all_sessions":
                if 7 <= hr <= 16:
                    if d_tag in asian_high_map and d_tag in asian_low_map:
                        ref_high = asian_high_map[d_tag]
                        ref_low = asian_low_map[d_tag]

            if ref_high > 0 and ref_low > 0:
                min_sweep = min_sweep_atr * atr[i]
                # Bull Trap / Sweep of High: Pierced High by min_sweep, then closed below ref_high
                if highs[i] >= ref_high + min_sweep and closes[i] < ref_high:
                    sig_short = True
                # Bear Trap / Sweep of Low: Pierced Low by min_sweep, then closed above ref_low
                elif lows[i] <= ref_low - min_sweep and closes[i] > ref_low:
                    sig_long = True

            if sig_long:
                in_pos = True
                pos = 1
                entry_idx = i + 1
                entry_p = opens[i + 1] + spread * 0.5
                sl_dist = (entry_p - lows[i]) + sl_buf_atr * atr[i]
                sl_p = entry_p - max(sl_dist, 1.2 * atr[i])
                tp_p = entry_p + tp_rr * (entry_p - sl_p)
                trades_today += 1
            elif sig_short:
                in_pos = True
                pos = -1
                entry_idx = i + 1
                entry_p = opens[i + 1] - spread * 0.5
                sl_dist = (highs[i] - entry_p) + sl_buf_atr * atr[i]
                sl_p = entry_p + max(sl_dist, 1.2 * atr[i])
                tp_p = entry_p - tp_rr * (sl_p - entry_p)
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

    status = "CHAMPION" if (pf >= 1.15 and annual_trades >= 150) else ("TACTICAL CANDIDATE" if net_profit > 0 else "REJECTED")

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
    print("STARTING SCALPING FRONTIER BATCH 13: STRATEGIES 321 - 330")
    print("SMART MONEY CONCEPTS (SMC) & MULTI-SESSION LIQUIDITY HUNTING SCALPERS")
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

    print("Simulating Smart Money Liquidity Sweep Engines...")
    t_asian_3r = run_liquidity_sweep_sim(opens, highs, lows, closes, atr14, dates, sweep_type="asian_london", min_sweep_atr=0.3, tp_rr=3.0)
    t_asian_4r = run_liquidity_sweep_sim(opens, highs, lows, closes, atr14, dates, sweep_type="asian_london", min_sweep_atr=0.5, tp_rr=4.0)
    t_london_3r = run_liquidity_sweep_sim(opens, highs, lows, closes, atr14, dates, sweep_type="london_ny", min_sweep_atr=0.4, tp_rr=3.0)
    t_london_4r = run_liquidity_sweep_sim(opens, highs, lows, closes, atr14, dates, sweep_type="london_ny", min_sweep_atr=0.5, tp_rr=4.0)
    t_pdh_pdl = run_liquidity_sweep_sim(opens, highs, lows, closes, atr14, dates, sweep_type="pdh_pdl", min_sweep_atr=0.4, tp_rr=3.5)

    # Core Champions from previous batches
    months = np.array([f"{d.year}-{d.month:02d}" for d in dates])
    t_st = run_engine_supertrend(opens, highs, lows, closes, atr14, ema200, months)
    t_ttm = run_engine_ttm_squeeze(opens, highs, lows, closes, atr14, ema200, months)
    t_296 = t_st + t_ttm

    results = []

    # S321: Asian Liquidity Sweep (London Open, 3.0R)
    res_321 = analyze_trade_list(t_asian_3r, "Asian Sweep London Open 3.0R", "S321")
    results.append(res_321)

    # S322: Asian Liquidity Sweep (London Open, 4.0R Asymmetric)
    res_322 = analyze_trade_list(t_asian_4r, "Asian Sweep London Open 4.0R Asymmetric", "S322")
    results.append(res_322)

    # S323: London Liquidity Sweep (NY Open, 3.0R)
    res_323 = analyze_trade_list(t_london_3r, "London Sweep NY Open 3.0R", "S323")
    results.append(res_323)

    # S324: London Liquidity Sweep (NY Open, 4.0R)
    res_324 = analyze_trade_list(t_london_4r, "London Sweep NY Open 4.0R", "S324")
    results.append(res_324)

    # S325: Previous Day High/Low (PDH/PDL) Sweep Reversal
    res_325 = analyze_trade_list(t_pdh_pdl, "PDH / PDL Sweep Reversal 3.5R", "S325")
    results.append(res_325)

    # S326: Dual-Session Liquidity Hunter (Asian + London Sweeps)
    res_326 = analyze_trade_list(t_asian_3r + t_london_3r, "Dual-Session Liquidity Hunter (London + NY)", "S326")
    results.append(res_326)

    # S327: Triple-Session Liquidity Hunter (Asian + London + PDH/PDL)
    res_327 = analyze_trade_list(t_asian_3r + t_london_3r + t_pdh_pdl, "Triple-Session Master Liquidity Hunter", "S327")
    results.append(res_327)

    # S328: SMC Hybrid Scalper: S296 (Duo B) + Asian Sweep (S321)
    res_328 = analyze_trade_list(t_296 + t_asian_3r, "SMC Hybrid Scalper: S296 + Asian Sweep", "S328")
    results.append(res_328)

    # S329: Sovereign Smart Money Scalper: S296 + Dual-Session Sweeps (S326)
    res_329 = analyze_trade_list(t_296 + t_asian_3r + t_london_3r, "Sovereign SMC Scalper: S296 + Dual-Session Sweeps", "S329")
    results.append(res_329)

    # S330: Institutional Smart Money Composite Suite: S296 + S327 Master Liquidity
    res_330 = analyze_trade_list(t_296 + t_asian_3r + t_london_3r + t_pdh_pdl, "Institutional SMC Composite Suite", "S330")
    results.append(res_330)

    for r in results:
        if "trades" in r: del r["trades"]

    df_out = pd.DataFrame(results)
    csv_path = os.path.join(RESULTS_DIR, "massive_scalping_smart_money_batch_321_330_matrix.csv")
    json_path = os.path.join(RESULTS_DIR, "massive_scalping_smart_money_batch_321_330_results.json")
    df_out.to_csv(csv_path, index=False)
    with open(json_path, "w") as f:
        json.dump({"generated_at": time.strftime("%Y-%m-%d %H:%M:%S"), "total_runtime_s": round(time.time() - t0, 2), "results": results}, f, indent=2)

    print("\n" + "=" * 80)
    print("BATCH 13 SMC LIQUIDITY SCALPER AUDIT COMPLETED IN {:.2f}s".format(time.time() - t0))
    print("=" * 80)
    print(df_out[["strategy_id", "strategy_name", "annual_trades", "net_profit", "pf", "win_rate", "max_dd", "romad", "mcr", "status"]].to_string(index=False))
    print("=" * 80)

if __name__ == "__main__":
    main()
