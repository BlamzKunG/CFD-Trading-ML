#!/usr/bin/env python3
"""
===============================================================================
STRATEGY 96: GOLD H1 MESA ADAPTIVE MOVING AVERAGE (MAMA-FAMA-KFD) SWEEP
===============================================================================
Asset: XAUUSD (Gold CFD)
Timeframe: H1
Data Source: Lightweight Parquet Cache (Mobile Hardware Protected, Zero OOM)
Horizon: 2020-01-01 to 2025-12-30 (72 Calendar Months)
Execution Model: Next-Bar Open Fill, $0.25 Spread ($2.50/0.10 lot), $6/lot Comm ($0.60/0.10 lot)
Hypothesis:
  John F. Ehlers' MESA Adaptive Moving Average (MAMA) adapts its smoothing factor alpha dynamically
  based on the rate of change of the phase angle of the dominant cycle (measured via Hilbert Transform):
    When market is in strong trend -> Phase changes slowly -> Alpha decreases -> Smooth trend holding.
    When market turns or accelerates -> Phase changes rapidly -> Alpha increases -> Rapid realignment.
  FAMA (Following Adaptive Moving Average) acts as an adaptive signal line.
  Crossover of MAMA and FAMA combined with Katz Fractal Gating (KFD <= 1.40) provides institutional entries.
===============================================================================
"""

import os
import sys
import gc
import time
import json
import argparse
import numpy as np
import pandas as pd

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
        sub = closes[i - period + 1 : i + 1]
        c_first = sub[0]
        c_last = sub[-1]
        euclid_d = abs(c_last - c_first)
        diffs = np.abs(np.diff(sub))
        total_len = np.sum(diffs)
        if total_len > 1e-6 and euclid_d > 1e-6:
            val = np.log10(period) / (np.log10(period) + np.log10(euclid_d / total_len))
            kfd[i] = max(1.0, min(2.0, val))
        else:
            kfd[i] = 1.5
    return kfd

def compute_mama_fama(highs: np.ndarray, lows: np.ndarray, closes: np.ndarray, fast_limit: float = 0.5, slow_limit: float = 0.05):
    """
    Computes Ehlers' MAMA (MESA Adaptive Moving Average) and FAMA (Following Adaptive Moving Average)
    using the Hilbert Transform Phase Discriminator.
    """
    n = len(closes)
    price = (highs + lows) / 2.0
    smooth = np.zeros(n, dtype=np.float64)
    detrender = np.zeros(n, dtype=np.float64)
    i1 = np.zeros(n, dtype=np.float64)
    q1 = np.zeros(n, dtype=np.float64)
    j_i = np.zeros(n, dtype=np.float64)
    j_q = np.zeros(n, dtype=np.float64)
    i2 = np.zeros(n, dtype=np.float64)
    q2 = np.zeros(n, dtype=np.float64)
    re = np.zeros(n, dtype=np.float64)
    im = np.zeros(n, dtype=np.float64)
    period = np.full(n, 15.0, dtype=np.float64)
    smooth_period = np.full(n, 15.0, dtype=np.float64)
    phase = np.zeros(n, dtype=np.float64)
    mama = np.copy(price)
    fama = np.copy(price)

    rad2deg = 180.0 / np.pi

    for i in range(6, n):
        # 4-bar WMA smoothing
        smooth[i] = (4.0 * price[i] + 3.0 * price[i - 1] + 2.0 * price[i - 2] + price[i - 3]) / 10.0
        
        # Hilbert Transform Detrender
        adj = 0.075 * period[i - 1] + 0.54
        detrender[i] = (0.0962 * smooth[i] + 0.5769 * smooth[i - 2] - 0.5769 * smooth[i - 4] - 0.0962 * smooth[i - 6]) * adj

        # In-phase and Quadrature components
        q1[i] = (0.0962 * detrender[i] + 0.5769 * detrender[i - 2] - 0.5769 * detrender[i - 4] - 0.0962 * detrender[i - 6]) * adj
        i1[i] = detrender[i - 3]

        # Advance the phase of I1 and Q1 by 90 degrees
        j_i[i] = (0.0962 * i1[i] + 0.5769 * i1[i - 2] - 0.5769 * i1[i - 4] - 0.0962 * i1[i - 6]) * adj
        j_q[i] = (0.0962 * q1[i] + 0.5769 * q1[i - 2] - 0.5769 * q1[i - 4] - 0.0962 * q1[i - 6]) * adj

        # Phasor addition for 3-bar averaging
        i2[i] = i1[i] - j_q[i]
        q2[i] = q1[i] + j_i[i]

        # Smooth the components
        i2[i] = 0.2 * i2[i] + 0.8 * i2[i - 1]
        q2[i] = 0.2 * q2[i] + 0.8 * q2[i - 1]

        # Homodyne Discriminator
        re[i] = i2[i] * i2[i - 1] + q2[i] * q2[i - 1]
        im[i] = i2[i] * q2[i - 1] - q2[i] * i2[i - 1]

        re[i] = 0.2 * re[i] + 0.8 * re[i - 1]
        im[i] = 0.2 * im[i] + 0.8 * im[i - 1]

        if abs(im[i]) > 1e-6 and abs(re[i]) > 1e-6:
            period[i] = 360.0 / (np.arctan(im[i] / re[i]) * rad2deg)
        else:
            period[i] = period[i - 1]

        period[i] = max(6.0, min(50.0, period[i]))
        smooth_period[i] = 0.33 * period[i] + 0.67 * smooth_period[i - 1]

        # Phase calculation
        if abs(i1[i]) > 1e-6:
            phase[i] = np.arctan(q1[i] / i1[i]) * rad2deg
        else:
            phase[i] = phase[i - 1]

        delta_phase = phase[i - 1] - phase[i]
        if delta_phase < 1.0:
            delta_phase = 1.0

        alpha = fast_limit / delta_phase
        if alpha < slow_limit:
            alpha = slow_limit
        elif alpha > fast_limit:
            alpha = fast_limit

        mama[i] = alpha * price[i] + (1.0 - alpha) * mama[i - 1]
        fama[i] = 0.5 * alpha * mama[i] + (1.0 - 0.5 * alpha) * fama[i - 1]

    return mama, fama

def simulate_mama_strategy(
    opens: np.ndarray,
    highs: np.ndarray,
    lows: np.ndarray,
    closes: np.ndarray,
    atr14: np.ndarray,
    ema200: np.ndarray,
    kfd: np.ndarray,
    mama: np.ndarray,
    fama: np.ndarray,
    months: np.ndarray,
    dates: pd.DatetimeIndex,
    use_kfd: bool = True,
    kfd_thresh: float = 1.40,
    tp_mult: float = 4.0,
    sl_mult: float = 2.0,
    monthly_profit_lock: float = 200.0,
    monthly_loss_breaker: float = 250.0,
    lot_size: float = 0.10,
    spread: float = 0.25,
    commission: float = 6.0
):
    n = len(closes)
    trades = []
    pos = 0 # 1 = Long, -1 = Short, 0 = Flat
    entry_p = 0.0
    sl_p = 0.0
    tp_p = 0.0
    entry_i = 0

    fixed_friction = (spread * lot_size * 100.0) + (commission * lot_size) # $3.10 / 0.10 lot

    cur_m = months[0]
    cur_m_pnl = 0.0
    locked_m = False

    for i in range(50, n - 1):
        bar_m = months[i]
        if bar_m != cur_m:
            cur_m = bar_m
            cur_m_pnl = 0.0
            locked_m = False

        if pos != 0:
            nxt_h = highs[i]
            nxt_l = lows[i]
            hit_tp = False
            hit_sl = False

            if pos == 1:
                if nxt_l <= sl_p: hit_sl = True
                elif nxt_h >= tp_p: hit_tp = True
            elif pos == -1:
                if nxt_h >= sl_p: hit_sl = True
                elif nxt_l <= tp_p: hit_tp = True

            if hit_sl and hit_tp:
                hit_tp = False; hit_sl = True

            if hit_sl or hit_tp:
                exit_p = tp_p if hit_tp else sl_p
                raw_diff = (exit_p - entry_p) if pos == 1 else (entry_p - exit_p)
                pnl = (raw_diff * lot_size * 100.0) - fixed_friction
                cur_m_pnl += pnl
                trades.append({
                    "entry_date": str(dates[entry_i]),
                    "exit_date": str(dates[i]),
                    "pos": pos,
                    "pnl": round(pnl, 2),
                    "month": cur_m,
                    "reason": "TP" if hit_tp else "SL",
                    "holding_bars": i - entry_i
                })
                pos = 0

                if monthly_profit_lock > 0 and cur_m_pnl >= monthly_profit_lock:
                    locked_m = True
                if monthly_loss_breaker > 0 and cur_m_pnl <= -monthly_loss_breaker:
                    locked_m = True

        if pos == 0 and not locked_m:
            c_atr = atr14[i]
            if c_atr < 0.5: continue

            kfd_ok = (kfd[i] <= kfd_thresh) if use_kfd else True
            ema_long_ok = (closes[i] > ema200[i])
            ema_short_ok = (closes[i] < ema200[i])

            # MAMA crosses over FAMA
            bull_cross = (mama[i] > fama[i]) and (mama[i - 1] <= fama[i - 1]) and ema_long_ok and kfd_ok
            bear_cross = (mama[i] < fama[i]) and (mama[i - 1] >= fama[i - 1]) and ema_short_ok and kfd_ok

            if bull_cross:
                pos = 1
                entry_i = i + 1
                entry_p = opens[i + 1]
                sl_p = entry_p - sl_mult * c_atr
                tp_p = entry_p + tp_mult * c_atr
            elif bear_cross:
                pos = -1
                entry_i = i + 1
                entry_p = opens[i + 1]
                sl_p = entry_p + sl_mult * c_atr
                tp_p = entry_p - tp_mult * c_atr

    return trades

def evaluate_metrics(trades, total_months=72):
    if not trades:
        return {"total_trades": 0, "net_profit": 0.0, "pf": 0.0, "win_rate": 0.0, "max_dd": 0.0, "romad": 0.0, "mcr": 0.0}
    df = pd.DataFrame(trades)
    pnls = df["pnl"].values
    net_p = float(np.sum(pnls))
    wins = pnls[pnls > 0]
    losses = pnls[pnls < 0]
    gw = float(np.sum(wins)) if len(wins) > 0 else 0.0
    gl = float(abs(np.sum(losses))) if len(losses) > 0 else 1e-4
    pf = float(gw / gl)
    wr = float(len(wins) / len(pnls) * 100.0)

    eq = np.cumsum(pnls)
    pk = np.maximum.accumulate(eq)
    dd = pk - eq
    mdd = float(np.max(dd)) if len(dd) > 0 else 0.0
    romad = float(net_p / mdd) if mdd > 0 else 0.0

    monthly = df.groupby("month")["pnl"].sum().to_dict()
    pos_m = sum(1 for m, val in monthly.items() if val > 0.0)
    mcr = float(round(pos_m / total_months * 100.0, 2))
    tpy = float(round(len(trades) / (total_months / 12.0), 1))

    return {
        "total_trades": len(trades),
        "trades_per_year": tpy,
        "net_profit": round(net_p, 2),
        "pf": round(pf, 3),
        "win_rate": round(wr, 2),
        "max_dd": round(mdd, 2),
        "romad": round(romad, 2),
        "mcr": mcr,
        "pos_months": pos_m,
        "total_months": total_months
    }

def main():
    parser = argparse.ArgumentParser(description="Sweep Strategy 96: MESA Adaptive Moving Average")
    parser.add_argument("--data_path", type=str, default="projects/quant_strategy_discovery/data/XAUUSD_H1.parquet")
    parser.add_argument("--out_dir", type=str, default="projects/quant_strategy_discovery/results")
    args = parser.parse_args()
    os.makedirs(args.out_dir, exist_ok=True)

    t0 = time.time()
    print("[*] Loading XAUUSD H1 Lightweight Parquet Cache...", flush=True)
    df = pd.read_parquet(args.data_path)
    opens = df["open"].values.astype(np.float64)
    highs = df["high"].values.astype(np.float64)
    lows = df["low"].values.astype(np.float64)
    closes = df["close"].values.astype(np.float64)
    dates = df.index
    months = (dates.year.values * 100 + dates.month.values).astype(np.int32)

    print("[*] Precomputing Technical Indicators (ATR, EMA200, KFD)...", flush=True)
    atr14 = compute_atr(highs, lows, closes, 14)
    ema200 = compute_ema(closes, 200)
    kfd24 = compute_katz_fractal_dimension(closes, atr14, 24)

    mama_configs = [
        (0.5, 0.05), # Classic Ehlers standard
        (0.4, 0.04), # Smoother swing
        (0.6, 0.06)  # Fast responsive
    ]
    mama_dict = {}
    for fl, sl in mama_configs:
        mama_dict[(fl, sl)] = compute_mama_fama(highs, lows, closes, fast_limit=fl, slow_limit=sl)

    tp_mults = [3.5, 4.0, 4.5]
    sl_mults = [2.0, 2.5]
    kfd_threshs = [1.40, 1.45]
    profit_locks = [200.0, 250.0]

    results = []
    print("[*] Running Targeted Parameter Grid Sweep (36 Configurations)...", flush=True)
    for fl, sl in mama_configs:
        m_series, f_series = mama_dict[(fl, sl)]
        for tp in tp_mults:
            for sl_m in sl_mults:
                for kfd_t in kfd_threshs:
                    for plock in profit_locks:
                        trades = simulate_mama_strategy(
                            opens=opens, highs=highs, lows=lows, closes=closes,
                            atr14=atr14, ema200=ema200, kfd=kfd24, mama=m_series, fama=f_series,
                            months=months, dates=dates,
                            use_kfd=True, kfd_thresh=kfd_t,
                            tp_mult=tp, sl_mult=sl_m,
                            monthly_profit_lock=plock, monthly_loss_breaker=250.0
                        )
                        m = evaluate_metrics(trades)
                        cfg = {
                            "fast_limit": fl, "slow_limit": sl,
                            "tp_mult": tp, "sl_mult": sl_m,
                            "kfd_thresh": kfd_t, "monthly_profit_lock": plock
                        }
                        results.append({**cfg, **m})

    df_res = pd.DataFrame(results)
    out_csv = os.path.join(args.out_dir, "strategy_96_mama_sweep_results.csv")
    df_res.to_csv(out_csv, index=False)
    print(f"[+] Saved {len(df_res)} sweep configurations to {out_csv}", flush=True)

    df_cand = df_res[(df_res["total_trades"] >= 60) & (df_res["net_profit"] > 0)].copy()
    if not df_cand.empty:
        df_cand.sort_values(by=["pf", "net_profit"], ascending=[False, False], inplace=True)
        top5 = df_cand.head(5)
        print("\n" + "=" * 95, flush=True)
        print("TOP 5 PERFORMING CONFIGURATIONS - STRATEGY 96: GOLD H1 MESA ADAPTIVE MOVING AVERAGE", flush=True)
        print("=" * 95, flush=True)
        print(top5[["fast_limit", "slow_limit", "tp_mult", "sl_mult", "kfd_thresh", "monthly_profit_lock", "total_trades", "trades_per_year", "net_profit", "pf", "max_dd", "romad", "mcr"]].to_string(index=False), flush=True)
        print("=" * 95, flush=True)

        champ = top5.iloc[0].to_dict()
        champ_file = os.path.join(args.out_dir, "strategy_96_champion.json")
        with open(champ_file, "w") as f:
            json.dump({
                "strategy_id": "STRATEGY_96",
                "strategy_name": "Gold H1 MESA Adaptive Moving Average (MAMA-FAMA-KFD)",
                "champion_metrics": champ,
                "runtime_seconds": round(time.time() - t0, 2)
            }, f, indent=2)
        print(f"[+] Saved Strategy 96 Champion to {champ_file}", flush=True)

    del df
    gc.collect()

if __name__ == "__main__":
    main()
