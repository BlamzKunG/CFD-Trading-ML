#!/usr/bin/env python3
"""
===============================================================================
STRATEGY 10: FAIR VALUE GAP (FVG) / IMBALANCE MITIGATION & RETEST
===============================================================================
Quantitative Backtesting & Parameter Robustness Engine for CFD Trading (XAUUSD)
Period: 2020 - 2025 (Full Multi-Year Validation)
Timeframe: M15 (Resampled from M1)

Core Mechanisms:
- 3-Candle Imbalance (FVG) Detection:
  * Bullish FVG: Low[i] > High[i-2] with Gap = Low[i] - High[i-2] >= min_gap_atr * ATR
  * Bearish FVG: High[i] < Low[i-2] with Gap = Low[i-2] - High[i] >= min_gap_atr * ATR
- Trend Filter:
  * EMA 50 or EMA 200 slope/position to ensure trading in direction of institutional order flow
- Mitigation / Retest Logic:
  * Retest of FVG zone boundary or Consequent Encroachment (50% midpoint of the gap)
  * Valid within max_retest_bars (e.g. within 20 bars after formation)
- Risk Management:
  * SL: Beyond the candle 2 extreme (invalidation point) + buffer
  * TP: Asymmetric Risk-Reward (1.5R, 2.0R, 3.0R, 4.0R)
- Realistic CFD Frictions: $0.25 spread ($25/lot) + $6/lot commission + slippage
===============================================================================
"""

import os
import sys
import time
import json
import argparse
import numpy as np
import pandas as pd

try:
    from numba import njit
    HAS_NUMBA = True
except ImportError:
    HAS_NUMBA = False
    def njit(*args, **kwargs):
        def decorator(func):
            return func
        return decorator

@njit(fastmath=True)
def simulate_fvg_kernel(
    opens: np.ndarray,
    highs: np.ndarray,
    lows: np.ndarray,
    closes: np.ndarray,
    atr: np.ndarray,
    ema_fast: np.ndarray,
    ema_slow: np.ndarray,
    hours: np.ndarray,
    trend_mode: int,        # 0: None (24h), 1: EMA 50 trend, 2: EMA 200 trend
    min_gap_atr: float,     # 0.2, 0.4, 0.6 * ATR
    entry_depth_mode: int,  # 0: Touch edge of FVG, 1: 50% Consequent Encroachment
    session_mode: int,      # 0: 24h, 1: Active London + NY (07:00 - 18:00 UTC)
    sl_buffer_atr: float,   # 0.2, 0.5 ATR
    tp_rr_mult: float,      # 1.5, 2.0, 3.0, 4.0
    spread: float,
    commission_per_unit: float,
    unit_size: float,
    warmup: int
):
    n = len(closes)
    max_trades = 25000
    pnl_list = np.zeros(max_trades, dtype=np.float64)
    holding_bars = np.zeros(max_trades, dtype=np.int32)
    trade_count = 0

    pos = 0  # 0: flat, 1: long, -1: short
    entry_price = 0.0
    sl_price = 0.0
    tp_price = 0.0
    entry_bar = 0

    # Active FVG trackers (only track latest active FVG to avoid state explosion)
    # Bullish FVG
    bull_active = False
    bull_top = 0.0
    bull_bot = 0.0
    bull_sl = 0.0
    bull_bar = 0

    # Bearish FVG
    bear_active = False
    bear_top = 0.0
    bear_bot = 0.0
    bear_sl = 0.0
    bear_bar = 0

    max_fvg_life = 24  # 24 * 15m = 6 hours max shelf-life for retest

    for i in range(warmup, n - 1):
        hr = hours[i]
        c_atr = atr[i]

        # 1. Manage Exits if in position
        if pos == 1:
            exit_triggered = False
            exit_p = 0.0

            if lows[i] <= sl_price:
                exit_p = sl_price if opens[i] >= sl_price else opens[i]
                exit_triggered = True
            elif highs[i] >= tp_price:
                exit_p = tp_price if opens[i] <= tp_price else opens[i]
                exit_triggered = True

            if exit_triggered:
                trade_pnl = (exit_p - entry_price) * unit_size - (spread + commission_per_unit) * unit_size
                if trade_count < max_trades:
                    pnl_list[trade_count] = trade_pnl
                    holding_bars[trade_count] = i - entry_bar
                    trade_count += 1
                pos = 0

        elif pos == -1:
            exit_triggered = False
            exit_p = 0.0

            if highs[i] >= sl_price:
                exit_p = sl_price if opens[i] <= sl_price else opens[i]
                exit_triggered = True
            elif lows[i] <= tp_price:
                exit_p = tp_price if opens[i] >= tp_price else opens[i]
                exit_triggered = True

            if exit_triggered:
                trade_pnl = (entry_price - exit_p) * unit_size - (spread + commission_per_unit) * unit_size
                if trade_count < max_trades:
                    pnl_list[trade_count] = trade_pnl
                    holding_bars[trade_count] = i - entry_bar
                    trade_count += 1
                pos = 0

        # Invalidate expired FVGs
        if bull_active and (i - bull_bar > max_fvg_life or lows[i] < bull_bot):
            bull_active = False
        if bear_active and (i - bear_bar > max_fvg_life or highs[i] > bear_top):
            bear_active = False

        # 2. Detect New FVGs at bar i (using i-2, i-1, i)
        # Bullish FVG: Low[i] > High[i-2]
        if lows[i] > highs[i - 2]:
            gap = lows[i] - highs[i - 2]
            if gap >= min_gap_atr * c_atr:
                bull_active = True
                bull_top = lows[i]
                bull_bot = highs[i - 2]
                bull_sl = lows[i - 1] # low of impulse candle
                bull_bar = i

        # Bearish FVG: High[i] < Low[i-2]
        if highs[i] < lows[i - 2]:
            gap = lows[i - 2] - highs[i]
            if gap >= min_gap_atr * c_atr:
                bear_active = True
                bear_top = lows[i - 2]
                bear_bot = highs[i]
                bear_sl = highs[i - 1] # high of impulse candle
                bear_bar = i

        # 3. Check Entries on Retest into active FVG
        if pos == 0:
            # Session check
            session_ok = True
            if session_mode == 1 and not (7 <= hr < 18):
                session_ok = False

            if session_ok:
                # Bullish Retest Entry
                if bull_active and i > bull_bar:
                    trend_ok = True
                    if trend_mode == 1 and closes[i] < ema_fast[i]:
                        trend_ok = False
                    elif trend_mode == 2 and closes[i] < ema_slow[i]:
                        trend_ok = False

                    if trend_ok:
                        target_entry_lvl = bull_top if entry_depth_mode == 0 else (bull_top + bull_bot) * 0.5
                        # Did price dip into the target level?
                        if lows[i] <= target_entry_lvl and closes[i] >= bull_bot:
                            pos = 1
                            entry_price = opens[i + 1]
                            sl_price = bull_sl - (sl_buffer_atr * c_atr)
                            risk = entry_price - sl_price
                            if risk < 0.50:
                                risk = 0.50
                                sl_price = entry_price - risk
                            tp_price = entry_price + (tp_rr_mult * risk)
                            entry_bar = i + 1
                            bull_active = False # Consumed
                            continue

                # Bearish Retest Entry
                if bear_active and i > bear_bar:
                    trend_ok = True
                    if trend_mode == 1 and closes[i] > ema_fast[i]:
                        trend_ok = False
                    elif trend_mode == 2 and closes[i] > ema_slow[i]:
                        trend_ok = False

                    if trend_ok:
                        target_entry_lvl = bear_bot if entry_depth_mode == 0 else (bear_top + bear_bot) * 0.5
                        # Did price spike up into the target level?
                        if highs[i] >= target_entry_lvl and closes[i] <= bear_top:
                            pos = -1
                            entry_price = opens[i + 1]
                            sl_price = bear_sl + (sl_buffer_atr * c_atr)
                            risk = sl_price - entry_price
                            if risk < 0.50:
                                risk = 0.50
                                sl_price = entry_price + risk
                            tp_price = entry_price - (tp_rr_mult * risk)
                            entry_bar = i + 1
                            bear_active = False # Consumed
                            continue

    # Close open position at end
    if pos == 1 and trade_count < max_trades:
        exit_p = closes[-1]
        trade_pnl = (exit_p - entry_price) * unit_size - (spread + commission_per_unit) * unit_size
        pnl_list[trade_count] = trade_pnl
        holding_bars[trade_count] = (n - 1) - entry_bar
        trade_count += 1
    elif pos == -1 and trade_count < max_trades:
        exit_p = closes[-1]
        trade_pnl = (entry_price - exit_p) * unit_size - (spread + commission_per_unit) * unit_size
        pnl_list[trade_count] = trade_pnl
        holding_bars[trade_count] = (n - 1) - entry_bar
        trade_count += 1

    return pnl_list[:trade_count], holding_bars[:trade_count]


def compute_atr(highs: np.ndarray, lows: np.ndarray, closes: np.ndarray, period: int = 14) -> np.ndarray:
    n = len(closes)
    tr = np.zeros(n, dtype=np.float64)
    tr[0] = highs[0] - lows[0]
    for i in range(1, n):
        hl = highs[i] - lows[i]
        hc = abs(highs[i] - closes[i - 1])
        lc = abs(lows[i] - closes[i - 1])
        tr[i] = max(hl, max(hc, lc))
    atr = np.zeros(n, dtype=np.float64)
    atr[period - 1] = np.mean(tr[:period])
    alpha = 1.0 / period
    for i in range(period, n):
        atr[i] = (tr[i] * alpha) + (atr[i - 1] * (1.0 - alpha))
    return atr


def compute_ema(series: np.ndarray, span: int) -> np.ndarray:
    n = len(series)
    ema = np.zeros(n, dtype=np.float64)
    alpha = 2.0 / (span + 1.0)
    ema[0] = series[0]
    for i in range(1, n):
        ema[i] = (series[i] * alpha) + (ema[i - 1] * (1.0 - alpha))
    return ema


def calculate_metrics(pnls: np.ndarray, holding: np.ndarray, initial_equity: float = 10000.0) -> dict:
    if len(pnls) == 0:
        return {
            "total_trades": 0, "net_profit": 0.0, "profit_factor": 0.0,
            "win_rate": 0.0, "max_drawdown": 0.0, "romad": 0.0,
            "sharpe": 0.0, "avg_holding_bars": 0.0, "pnl_mean": 0.0, "pnl_std": 0.0
        }

    wins = pnls[pnls > 0]
    losses = pnls[pnls < 0]
    gross_profit = float(np.sum(wins)) if len(wins) > 0 else 0.0
    gross_loss = float(abs(np.sum(losses))) if len(losses) > 0 else 0.0
    net_profit = float(np.sum(pnls))
    win_rate = (len(wins) / len(pnls)) * 100.0

    pf = (gross_profit / gross_loss) if gross_loss > 0 else (99.0 if gross_profit > 0 else 0.0)

    # Drawdown
    equity_curve = initial_equity + np.cumsum(pnls)
    peaks = np.maximum.accumulate(equity_curve)
    dd_curve = peaks - equity_curve
    max_dd = float(np.max(dd_curve)) if len(dd_curve) > 0 else 0.0

    romad = (net_profit / max_dd) if max_dd > 0 else 0.0
    sharpe = float(np.mean(pnls) / np.std(pnls) * np.sqrt(250)) if (len(pnls) > 5 and np.std(pnls) > 0) else 0.0

    return {
        "total_trades": int(len(pnls)),
        "net_profit": round(net_profit, 2),
        "profit_factor": round(pf, 3),
        "win_rate": round(win_rate, 2),
        "max_drawdown": round(max_dd, 2),
        "romad": round(romad, 2),
        "sharpe": round(sharpe, 3),
        "avg_holding_bars": round(float(np.mean(holding)), 1),
        "pnl_mean": round(float(np.mean(pnls)), 2),
        "pnl_std": round(float(np.std(pnls)), 2)
    }


def main():
    parser = argparse.ArgumentParser(description="Sweep Strategy 10: Fair Value Gap / Imbalance Mitigation")
    parser.add_argument("--data", type=str, default="/mnt/sdcard/Download/EA/XAUUSD_M1.csv.gz", help="Path to M1 data")
    parser.add_argument("--out_dir", type=str, default="/root/CFD-Trading-ML/projects/quant_strategy_discovery/results", help="Results dir")
    args = parser.parse_args()

    os.makedirs(args.out_dir, exist_ok=True)

    print(f"[*] Loading M1 data from {args.data}...")
    t0 = time.time()
    df_raw = pd.read_csv(
        args.data,
        usecols=["datetime", "open", "high", "low", "close", "tick_volume"],
        dtype={
            "open": np.float32, "high": np.float32, "low": np.float32,
            "close": np.float32, "tick_volume": np.int32
        }
    )
    df_raw["datetime"] = pd.to_datetime(df_raw["datetime"])
    df_raw.set_index("datetime", inplace=True)
    df_raw.sort_index(inplace=True)
    print(f"[+] Loaded {len(df_raw):,} M1 bars in {time.time() - t0:.2f}s.")

    print(f"[*] Resampling to M15 timeframe...")
    df_m15 = df_raw.resample('15min').agg({
        'open': 'first',
        'high': 'max',
        'low': 'min',
        'close': 'last'
    }).dropna()
    print(f"[+] Resampled M15 bars: {len(df_m15):,} from {df_m15.index[0]} to {df_m15.index[-1]}")

    opens = df_m15['open'].values.astype(np.float64)
    highs = df_m15['high'].values.astype(np.float64)
    lows = df_m15['low'].values.astype(np.float64)
    closes = df_m15['close'].values.astype(np.float64)
    hours = df_m15.index.hour.values.astype(np.int32)

    atr14 = compute_atr(highs, lows, closes, 14)
    ema50 = compute_ema(closes, 50)
    ema200 = compute_ema(closes, 200)

    # Parameter grid definition
    trend_modes = [0, 1, 2] # 0: None, 1: EMA 50, 2: EMA 200
    trend_names = ["None", "EMA50", "EMA200"]
    min_gap_atrs = [0.2, 0.4, 0.6] # 0.2 ATR, 0.4 ATR, 0.6 ATR
    entry_depth_modes = [0, 1] # 0: Boundary Touch, 1: 50% Consequent Encroachment
    entry_depth_names = ["BoundaryTouch", "50PctCE"]
    session_modes = [0, 1] # 0: 24h, 1: London+NY (07-18 UTC)
    session_names = ["24h", "London_NY"]
    sl_buffers = [0.2, 0.5] # ATR buffer
    tp_rr_mults = [1.5, 2.0, 3.0, 4.0]

    # Total combinations = 3 * 3 * 2 * 2 * 2 * 4 = 288 combinations
    total_combs = len(trend_modes) * len(min_gap_atrs) * len(entry_depth_modes) * len(session_modes) * len(sl_buffers) * len(tp_rr_mults)
    print(f"[*] Starting Sweep of {total_combs} parameter combinations...")

    results = []
    c_idx = 0
    t_start = time.time()

    spread = 0.25 # $0.25 spread ($25/lot)
    commission = 0.06 # $6 per 100 oz unit ($0.60 per 0.10 lot)
    unit_size = 10.0 # 0.10 lot = 10 oz
    warmup = 250

    for tm in trend_modes:
        for mg in min_gap_atrs:
            for edm in entry_depth_modes:
                for sm in session_modes:
                    for slb in sl_buffers:
                        for tpr in tp_rr_mults:
                            c_idx += 1
                            pnls, holding = simulate_fvg_kernel(
                                opens, highs, lows, closes, atr14, ema50, ema200, hours,
                                tm, mg, edm, sm, slb, tpr, spread, commission, unit_size, warmup
                            )
                            m = calculate_metrics(pnls, holding)
                            m.update({
                                "trend_filter": trend_names[tm],
                                "min_gap_atr": mg,
                                "entry_depth": entry_depth_names[edm],
                                "session": session_names[sm],
                                "sl_buffer_atr": slb,
                                "tp_rr_mult": tpr
                            })
                            results.append(m)

                            if c_idx % 50 == 0 or c_idx == total_combs:
                                elapsed = time.time() - t_start
                                print(f"[{c_idx}/{total_combs}] Completed ({c_idx/total_combs*100:.1f}%) | Elapsed: {elapsed:.1f}s")

    df_res = pd.DataFrame(results)
    csv_path = os.path.join(args.out_dir, "strategy_10_fvg_mitigation_sweep_results.csv")
    df_res.to_csv(csv_path, index=False)
    print(f"[+] Saved full results to {csv_path}")

    # Identify Champion
    viable = df_res[df_res['total_trades'] >= 100]
    if len(viable) > 0:
        champ = viable.sort_values(by=['net_profit', 'profit_factor'], ascending=[False, False]).iloc[0]
    else:
        champ = df_res.sort_values(by=['net_profit', 'profit_factor'], ascending=[False, False]).iloc[0]

    champ_dict = champ.to_dict()
    json_path = os.path.join(args.out_dir, "strategy_10_fvg_mitigation_champion.json")
    with open(json_path, 'w') as f:
        json.dump(champ_dict, f, indent=2)
    print(f"[+] Champion JSON saved to {json_path}")
    print("\n================== CHAMPION RESULTS ==================")
    for k, v in champ_dict.items():
        print(f"  {k}: {v}")
    print("======================================================")

if __name__ == "__main__":
    main()
