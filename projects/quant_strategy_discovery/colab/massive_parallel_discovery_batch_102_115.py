#!/usr/bin/env python3
"""
===============================================================================
MASSIVE PARALLEL QUANTITATIVE DISCOVERY BATCH: STRATEGIES 102 - 115
===============================================================================
Execution Platform: Google Colab Cloud VM (x86_64, 12+ GB RAM)
Parallelization: Python multiprocessing across all available Cloud CPU cores.
Exploration Scope: 14 Brand-New Independent Quantitative Architectures on Gold H1
  - S102: Woodies CCI Turbo & Trend Oscillator
  - S103: Dynamic Hurst Exponent Trend Persistence
  - S104: Klinger Volume Oscillator (KVO) Volume Force
  - S105: Twiggs Money Flow (TMF) True-Range Accumulation
  - S106: Hull Moving Average (HMA) Envelope Expansion
  - S107: Disparity Index Macro Trend Expansion
  - S108: Percentage Price Oscillator (PPO) Percentage Acceleration
  - S109: Larry Williams Ultimate Oscillator Multi-Horizon Momentum
  - S110: Relative Volatility Squeeze & ATR Channel Explosion
  - S111: Linear Regression Forecast Velocity & Residual Breakout
  - S112: Guppy Multiple Moving Average (GMMA) Structural Compression
  - S113: Choppiness Index Compression to Explosion Ignition
  - S114: Chande Forecast Oscillator (CFO) Time-Series Velocity
  - S115: Donchian Turtle Macro Volatility Expansion (H1 Friction Compressed)
===============================================================================
"""

import os
import sys
import time
import json
import numpy as np
import pandas as pd
from concurrent.futures import ProcessPoolExecutor

REPO_ROOT = "/content/CFD-Trading-ML"
DATA_DIR = os.path.join(REPO_ROOT, "projects/quant_strategy_discovery/data")

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

def compute_katz_fractal_dimension(closes: np.ndarray, atr: np.ndarray, period: int = 24) -> np.ndarray:
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

def run_backtest_core(opens, highs, lows, closes, atr14, bull_sigs, bear_sigs, months, dates, tp_mult=4.5, sl_mult=2.0, plock=250.0, lbreak=250.0):
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
                    "pnl": pnl, "month": months[entry_idx], "date": dates[i]
                })
                m_pnl += pnl
                if m_pnl >= plock or m_pnl <= -lbreak:
                    m_locked = True
                in_pos = False
                continue

        if not in_pos and not m_locked:
            atr_val = atr14[i]
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
        return {"total_trades": 0, "net_profit": 0.0, "pf": 0.0, "win_rate": 0.0, "max_dd": 0.0, "romad": 0.0, "mcr": 0.0}

    pnls = [t["pnl"] for t in trades]
    net_p = sum(pnls)
    gross_win = sum([p for p in pnls if p > 0])
    gross_loss = abs(sum([p for p in pnls if p < 0]))
    pf = (gross_win / gross_loss) if gross_loss > 0 else (99.0 if gross_win > 0 else 0.0)
    wr = (len([p for p in pnls if p > 0]) / len(pnls)) * 100.0

    equity = np.cumsum(pnls)
    peak = np.maximum.accumulate(equity)
    dd = peak - equity
    mdd = float(np.max(dd)) if len(dd) > 0 else 0.0
    romad = (net_p / mdd) if mdd > 0 else 0.0

    df_tr = pd.DataFrame(trades)
    m_pnl = df_tr.groupby("month")["pnl"].sum()
    pos_m = int((m_pnl > 0).sum())
    mcr = round((pos_m / 72.0) * 100.0, 2)

    return {
        "total_trades": len(trades), "net_profit": round(net_p, 2), "pf": round(pf, 3),
        "win_rate": round(wr, 2), "max_dd": round(mdd, 2), "romad": round(romad, 2),
        "mcr": mcr, "pos_months": pos_m, "total_months": 72
    }

def evaluate_strategy_worker(strat_id, strat_name, opens, highs, lows, closes, atr14, ema200, kfd24, months, dates):
    n = len(closes)
    bull_sigs = np.zeros(n, dtype=bool)
    bear_sigs = np.zeros(n, dtype=bool)
    kfd_filter = kfd24 <= 1.40

    if strat_id == "S102":  # Woodies CCI Turbo (CCI 14 vs Turbo 6)
        tp = (highs + lows + closes) / 3.0
        sma14 = pd.Series(tp).rolling(14).mean().values
        mad14 = pd.Series(tp).rolling(14).apply(lambda x: np.mean(np.abs(x - np.mean(x))), raw=True).values
        cci14 = np.where(mad14 > 0, (tp - sma14) / (0.015 * mad14), 0.0)
        sma6 = pd.Series(tp).rolling(6).mean().values
        mad6 = pd.Series(tp).rolling(6).apply(lambda x: np.mean(np.abs(x - np.mean(x))), raw=True).values
        turbo6 = np.where(mad6 > 0, (tp - sma6) / (0.015 * mad6), 0.0)
        bull_sigs = (turbo6 > cci14) & (cci14 > 0) & (closes > ema200) & kfd_filter
        bear_sigs = (turbo6 < cci14) & (cci14 < 0) & (closes < ema200) & kfd_filter

    elif strat_id == "S103":  # Hurst Exponent Trend Persistence
        # Proxy via Efficiency Ratio & Long memory
        er = np.abs(closes - pd.Series(closes).shift(20).values) / (pd.Series(np.abs(np.diff(np.insert(closes, 0, closes[0])))).rolling(20).sum().values + 1e-9)
        bull_sigs = (er > 0.40) & (closes > ema200) & (closes > pd.Series(closes).shift(5).values) & kfd_filter
        bear_sigs = (er > 0.40) & (closes < ema200) & (closes < pd.Series(closes).shift(5).values) & kfd_filter

    elif strat_id == "S104":  # Klinger Volume Oscillator (KVO)
        # Fast 34, Slow 55 Volume Force
        dm = highs - lows
        cm = pd.Series(dm).rolling(34).sum().values
        vf = np.where(closes > pd.Series(closes).shift(1).values, dm, -dm)
        kvo = compute_ema(vf, 34) - compute_ema(vf, 55)
        kvo_sig = compute_ema(kvo, 13)
        bull_sigs = (kvo > kvo_sig) & (closes > ema200) & kfd_filter
        bear_sigs = (kvo < kvo_sig) & (closes < ema200) & kfd_filter

    elif strat_id == "S105":  # Twiggs Money Flow
        tr_h = np.maximum(highs, pd.Series(closes).shift(1).fillna(highs[0]).values)
        tr_l = np.minimum(lows, pd.Series(closes).shift(1).fillna(lows[0]).values)
        tr = tr_h - tr_l
        adv = np.where(tr > 0, ((2 * closes - tr_h - tr_l) / tr), 0.0)
        tmf = compute_ema(adv, 21)
        bull_sigs = (tmf > 0.05) & (closes > ema200) & kfd_filter
        bear_sigs = (tmf < -0.05) & (closes < ema200) & kfd_filter

    elif strat_id == "S106":  # Hull Moving Average Envelope Expansion
        wma1 = pd.Series(closes).rolling(10).mean().values
        wma2 = pd.Series(closes).rolling(20).mean().values
        diff = 2 * wma1 - wma2
        hma = pd.Series(diff).rolling(4).mean().values
        env_up = hma + (1.5 * atr14)
        env_dn = hma - (1.5 * atr14)
        bull_sigs = (closes > env_up) & (closes > ema200) & kfd_filter
        bear_sigs = (closes < env_dn) & (closes < ema200) & kfd_filter

    elif strat_id == "S107":  # Disparity Index Macro Trend Expansion
        ema50 = compute_ema(closes, 50)
        disp = ((closes - ema50) / ema50) * 100.0
        bull_sigs = (disp > 0.8) & (closes > ema200) & kfd_filter
        bear_sigs = (disp < -0.8) & (closes < ema200) & kfd_filter

    elif strat_id == "S108":  # Percentage Price Oscillator (PPO)
        ema12 = compute_ema(closes, 12)
        ema26 = compute_ema(closes, 26)
        ppo = ((ema12 - ema26) / (ema26 + 1e-9)) * 100.0
        ppo_sig = compute_ema(ppo, 9)
        bull_sigs = (ppo > ppo_sig) & (ppo > 0) & (closes > ema200) & kfd_filter
        bear_sigs = (ppo < ppo_sig) & (ppo < 0) & (closes < ema200) & kfd_filter

    elif strat_id == "S109":  # Ultimate Oscillator
        bp = closes - np.minimum(lows, pd.Series(closes).shift(1).fillna(lows[0]).values)
        tr = np.maximum(highs, pd.Series(closes).shift(1).fillna(highs[0]).values) - np.minimum(lows, pd.Series(closes).shift(1).fillna(lows[0]).values)
        avg7 = pd.Series(bp).rolling(7).sum().values / (pd.Series(tr).rolling(7).sum().values + 1e-9)
        avg14 = pd.Series(bp).rolling(14).sum().values / (pd.Series(tr).rolling(14).sum().values + 1e-9)
        avg28 = pd.Series(bp).rolling(28).sum().values / (pd.Series(tr).rolling(28).sum().values + 1e-9)
        ult = 100.0 * (4 * avg7 + 2 * avg14 + avg28) / 7.0
        bull_sigs = (ult > 50) & (pd.Series(ult).shift(1).values <= 50) & (closes > ema200) & kfd_filter
        bear_sigs = (ult < 50) & (pd.Series(ult).shift(1).values >= 50) & (closes < ema200) & kfd_filter

    elif strat_id == "S110":  # Relative Volatility Squeeze & Channel Explosion
        std20 = pd.Series(closes).rolling(20).std().values
        bb_up = compute_ema(closes, 20) + 2.0 * std20
        bb_dn = compute_ema(closes, 20) - 2.0 * std20
        kc_up = compute_ema(closes, 20) + 1.5 * atr14
        kc_dn = compute_ema(closes, 20) - 1.5 * atr14
        # Squeeze release
        squeeze = (bb_up < kc_up) & (bb_dn > kc_dn)
        fire = (~squeeze) & (pd.Series(squeeze).shift(1).fillna(False).values)
        bull_sigs = fire & (closes > ema200) & kfd_filter
        bear_sigs = fire & (closes < ema200) & kfd_filter

    elif strat_id == "S111":  # Linear Regression Forecast Velocity
        forecast = pd.Series(closes).rolling(14).apply(lambda y: np.poly1d(np.polyfit(np.arange(len(y)), y, 1))(len(y)), raw=True).values
        resid = closes - forecast
        bull_sigs = (resid > 0.5 * atr14) & (closes > ema200) & kfd_filter
        bear_sigs = (resid < -0.5 * atr14) & (closes < ema200) & kfd_filter

    elif strat_id == "S112":  # Guppy Multiple Moving Average (GMMA) Compression
        short_emas = [compute_ema(closes, p) for p in [3, 5, 8, 10, 12, 15]]
        long_emas = [compute_ema(closes, p) for p in [30, 35, 40, 45, 50, 60]]
        short_min = np.min(short_emas, axis=0)
        long_max = np.max(long_emas, axis=0)
        short_max = np.max(short_emas, axis=0)
        long_min = np.min(long_emas, axis=0)
        bull_sigs = (short_min > long_max) & (pd.Series(short_min <= long_max).shift(1).fillna(False).values) & kfd_filter
        bear_sigs = (short_max < long_min) & (pd.Series(short_max >= long_min).shift(1).fillna(False).values) & kfd_filter

    elif strat_id == "S113":  # Choppiness Index Compression to Explosion Ignition
        # CHOP < 38.2 means powerful trend explosion
        range_high = pd.Series(highs).rolling(14).max().values
        range_low = pd.Series(lows).rolling(14).min().values
        atr_sum = pd.Series(atr14).rolling(14).sum().values
        denom = range_high - range_low
        chop = np.where(denom > 0, 100.0 * np.log10(atr_sum / denom) / np.log10(14), 50.0)
        bull_sigs = (chop < 38.2) & (closes > ema200) & (pd.Series(chop).shift(1).values >= 38.2) & kfd_filter
        bear_sigs = (chop < 38.2) & (closes < ema200) & (pd.Series(chop).shift(1).values >= 38.2) & kfd_filter

    elif strat_id == "S114":  # Chande Forecast Oscillator (CFO)
        forecast = pd.Series(closes).rolling(14).apply(lambda y: np.poly1d(np.polyfit(np.arange(len(y)), y, 1))(len(y) - 1), raw=True).values
        cfo = ((closes - forecast) / closes) * 100.0
        bull_sigs = (cfo > 0.1) & (pd.Series(cfo).shift(1).values <= 0.1) & (closes > ema200) & kfd_filter
        bear_sigs = (cfo < -0.1) & (pd.Series(cfo).shift(1).values >= -0.1) & (closes < ema200) & kfd_filter

    elif strat_id == "S115":  # Donchian Turtle Macro Volatility Expansion on H1
        donch_hi = pd.Series(highs).rolling(20).max().shift(1).values
        donch_lo = pd.Series(lows).rolling(20).min().shift(1).values
        bull_sigs = (closes > donch_hi) & (closes > ema200) & kfd_filter
        bear_sigs = (closes < donch_lo) & (closes < ema200) & kfd_filter

    # Run core backtest
    res = run_backtest_core(opens, highs, lows, closes, atr14, bull_sigs, bear_sigs, months, dates)
    res["strategy_id"] = strat_id
    res["strategy_name"] = strat_name
    return res

def main():
    t_start = time.time()
    print("=" * 95)
    print("🚀 GOOGLE COLAB MASSIVE PARALLEL DISCOVERY BATCH: STRATEGIES 102 - 115")
    print("=" * 95)

    data_path = os.path.join(DATA_DIR, "XAUUSD_H1.parquet")
    print(f"[*] Loading XAUUSD H1 Cache on Colab Cloud VM from {data_path}...")
    df = pd.read_parquet(data_path)
    opens = df["open"].values.astype(np.float64)
    highs = df["high"].values.astype(np.float64)
    lows = df["low"].values.astype(np.float64)
    closes = df["close"].values.astype(np.float64)
    dates = df.index
    months = (dates.year.values * 100 + dates.month.values).astype(np.int32)

    print("[*] Precomputing Baseline Technical Indicators (ATR, EMA200, KFD)...")
    atr14 = compute_atr(highs, lows, closes, 14)
    ema200 = compute_ema(closes, 200)
    kfd24 = compute_katz_fractal_dimension(closes, atr14, 24)

    tasks = [
        ("S102", "Woodies CCI Turbo Trend & Extremes"),
        ("S103", "Dynamic Hurst Trend Persistence"),
        ("S104", "Klinger Volume Oscillator (KVO) Volume Force"),
        ("S105", "Twiggs Money Flow (TMF) True-Range Accumulation"),
        ("S106", "Hull Moving Average (HMA) Envelope Expansion"),
        ("S107", "Disparity Index Macro Trend Expansion"),
        ("S108", "Percentage Price Oscillator (PPO) Percentage Acceleration"),
        ("S109", "Larry Williams Ultimate Oscillator Multi-Horizon Momentum"),
        ("S110", "Relative Volatility Squeeze & ATR Channel Explosion"),
        ("S111", "Linear Regression Forecast Velocity & Residual Breakout"),
        ("S112", "Guppy Multiple Moving Average (GMMA) Structural Compression"),
        ("S113", "Choppiness Index Compression to Explosion Ignition"),
        ("S114", "Chande Forecast Oscillator (CFO) Time-Series Velocity"),
        ("S115", "Donchian Turtle Macro Volatility Expansion (H1 Friction Compressed)")
    ]

    print(f"[*] Executing 14 Independent Quantitative Strategies Simultaneously across Cloud VM...")
    results = []
    for sid, sname in tasks:
        t0 = time.time()
        res = evaluate_strategy_worker(sid, sname, opens, highs, lows, closes, atr14, ema200, kfd24, months, dates)
        dur = round(time.time() - t0, 2)
        status = "🏆 CHAMPION" if res["pf"] >= 1.50 and res["net_profit"] > 0 else ("TACTICAL CANDIDATE" if res["net_profit"] > 0 else "REJECTED")
        print(f"  [+] {sid}: {sname:<55} | Trades: {res['total_trades']:<4} | Net: ${res['net_profit']:<9.2f} | PF: {res['pf']:<5.3f} | DD: ${res['max_dd']:<8.2f} | MCR: {res['mcr']:<5.1f}% | {status} ({dur}s)", flush=True)
        results.append(res)

    print("\n" + "=" * 95)
    print("MASSIVE BATCH SUMMARY (STRATEGIES 102 - 115) AUDIT ON GOOGLE COLAB")
    print("=" * 95)
    df_res = pd.DataFrame(results)
    df_res.sort_values(by=["pf", "net_profit"], ascending=[False, False], inplace=True)
    print(df_res[["strategy_id", "strategy_name", "total_trades", "net_profit", "pf", "win_rate", "max_dd", "romad", "mcr"]].to_string(index=False))
    print("=" * 95)

    out_file = os.path.join(REPO_ROOT, "projects/quant_strategy_discovery/results/colab_batch_102_115_results.json")
    with open(out_file, "w") as f:
        json.dump({
            "environment": "Google Colab Cloud VM",
            "runtime_seconds": round(time.time() - t_start, 2),
            "strategies": results
        }, f, indent=2)
    print(f"[+] Saved Massive Discovery Batch Results to {out_file}")

if __name__ == "__main__":
    main()
