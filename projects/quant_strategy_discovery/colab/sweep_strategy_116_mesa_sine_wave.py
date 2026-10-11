#!/usr/bin/env python3
"""
===============================================================================
STRATEGY 116: EHLERS MESA SINE WAVE INDICATOR OPTIMIZATION SWEEP ON GOOGLE COLAB
===============================================================================
Asset: XAUUSD (Gold CFD)
Timeframe: H1
Execution Platform: Google Colab Cloud VM (x86_64)
Hypothesis:
  Ehlers MESA Sine Wave captures cycle turning points and phase reversals before
  traditional lagging indicators. By fine-tuning cycle periods, phase offsets,
  and asymmetric reward-to-risk ratios (TP/SL), we maximize Profit Factor >= 1.70+
  while maintaining robust Monthly Consistency (MCR).
===============================================================================
"""

import os
import sys
import time
import json
import itertools
import numpy as np
import pandas as pd

REPO_ROOT = "/content/CFD-Trading-ML"
DATA_DIR = os.path.join(REPO_ROOT, "projects/quant_strategy_discovery/data")
sys.argv = [sys.argv[0]]

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

def compute_ehlers_mesa_sine(closes: np.ndarray, cycle_period: int = 14, phase_deg: float = 45.0):
    n = len(closes)
    smooth = (4 * closes + 3 * pd.Series(closes).shift(1).fillna(closes[0]).values +
              2 * pd.Series(closes).shift(2).fillna(closes[0]).values +
              pd.Series(closes).shift(3).fillna(closes[0]).values) / 10.0
    half_c = max(3, cycle_period // 2)
    cycle = pd.Series(smooth - pd.Series(smooth).shift(half_c).fillna(smooth[0]).values).rolling(cycle_period).apply(
        lambda x: np.arctan2(x[-1], x[0]) if len(x) > 0 and x[0] != 0 else 0.0, raw=True
    ).fillna(0.0).values
    sine = np.sin(cycle)
    leadsine = np.sin(cycle + np.radians(phase_deg))
    return sine, leadsine

def simulate_mesa_sine(opens, highs, lows, closes, atr14, ema200, kfd24, sine, leadsine, months, dates,
                        kfd_thresh=1.40, tp_mult=4.5, sl_mult=2.0, plock=200.0, lbreak=250.0):
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

    cross_up = (sine > leadsine) & (pd.Series(sine <= leadsine).shift(1).fillna(False).values)
    cross_dn = (sine < leadsine) & (pd.Series(sine >= leadsine).shift(1).fillna(False).values)

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
            kfd_ok = kfd24[i] <= kfd_thresh
            trend_bull = closes[i] > ema200[i]
            trend_bear = closes[i] < ema200[i]

            bull_sig = cross_up[i] and trend_bull and kfd_ok
            bear_sig = cross_dn[i] and trend_bear and kfd_ok

            atr_val = atr14[i]
            if bull_sig:
                in_pos = True
                pos_type = 1
                entry_idx = i + 1
                entry_price = opens[i + 1] + spread_pts
                sl_price = entry_price - (sl_mult * atr_val)
                tp_price = entry_price + (tp_mult * atr_val)
            elif bear_sig:
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

def main():
    t_start = time.time()
    print("=" * 95)
    print("🚀 STRATEGY 116: EHLERS MESA SINE WAVE INDICATOR FINE-TUNING SWEEP (GOOGLE COLAB)")
    print("=" * 95)

    data_path = os.path.join(DATA_DIR, "XAUUSD_H1.parquet")
    df = pd.read_parquet(data_path)
    opens = df["open"].values.astype(np.float64)
    highs = df["high"].values.astype(np.float64)
    lows = df["low"].values.astype(np.float64)
    closes = df["close"].values.astype(np.float64)
    dates = df.index
    months = (dates.year.values * 100 + dates.month.values).astype(np.int32)

    atr14 = compute_atr(highs, lows, closes, 14)
    ema200 = compute_ema(closes, 200)
    kfd24 = compute_katz_fractal_dimension(closes, atr14, 24)

    # Grid search across parameters
    cycle_periods = [10, 14, 20]
    phase_degs = [30.0, 45.0, 60.0]
    tp_mults = [3.5, 4.5, 5.5]
    sl_mults = [1.5, 2.0, 2.5]
    kfd_threshs = [1.38, 1.42]

    combos = list(itertools.product(cycle_periods, phase_degs, tp_mults, sl_mults, kfd_threshs))
    print(f"[*] Exploring {len(combos)} Parameter Combinations across Colab Cloud VM...")

    # Cache precomputed Sine / LeadSine for cycle and phase
    cache_sine = {}
    for c_per, p_deg in itertools.product(cycle_periods, phase_degs):
        cache_sine[(c_per, p_deg)] = compute_ehlers_mesa_sine(closes, c_per, p_deg)

    results = []
    for c_per, p_deg, tp, sl, kfd_th in combos:
        s, ls = cache_sine[(c_per, p_deg)]
        res = simulate_mesa_sine(opens, highs, lows, closes, atr14, ema200, kfd24, s, ls, months, dates,
                                 kfd_thresh=kfd_th, tp_mult=tp, sl_mult=sl, plock=200.0, lbreak=250.0)
        res["cycle_period"] = c_per
        res["phase_deg"] = p_deg
        res["tp_mult"] = tp
        res["sl_mult"] = sl
        res["kfd_thresh"] = kfd_th
        results.append(res)

    df_res = pd.DataFrame(results)
    df_res.sort_values(by=["pf", "net_profit"], ascending=[False, False], inplace=True)
    df_valid = df_res[df_res["total_trades"] >= 40]

    print("\n" + "=" * 95)
    print("TOP 10 S116 PARAMETER CONFIGURATIONS (SORTED BY PROFIT FACTOR)")
    print("=" * 95)
    cols = ["cycle_period", "phase_deg", "tp_mult", "sl_mult", "kfd_thresh", "total_trades", "net_profit", "pf", "win_rate", "max_dd", "romad", "mcr"]
    print(df_valid[cols].head(10).to_string(index=False))
    print("=" * 95)

    champion = df_valid.iloc[0].to_dict()
    print(f"\n🏆 S116 CHAMPION DISCOVERED:")
    print(f"   Cycle Period: {champion['cycle_period']}, Phase Shift: {champion['phase_deg']} deg")
    print(f"   TP Mult: {champion['tp_mult']}x ATR, SL Mult: {champion['sl_mult']}x ATR, KFD Thresh: {champion['kfd_thresh']}")
    print(f"   Trades: {champion['total_trades']}, Net Profit: +${champion['net_profit']:,.2f}, PF: {champion['pf']:.3f}, Max DD: ${champion['max_dd']:,.2f}, RoMaD: {champion['romad']:.2f}x, MCR: {champion['mcr']:.1f}%")

    out_file = os.path.join(REPO_ROOT, "projects/quant_strategy_discovery/results/strategy_116_champion.json")
    with open(out_file, "w") as f:
        json.dump({
            "strategy_id": "STRATEGY_116",
            "strategy_name": "Ehlers MESA Sine Wave Indicator Cycle Turning Points",
            "champion": champion,
            "runtime_seconds": round(time.time() - t_start, 2)
        }, f, indent=2)
    print(f"[+] Saved S116 Champion to {out_file}")

if __name__ == "__main__":
    main()
