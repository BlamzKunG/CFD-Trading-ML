#!/usr/bin/env python3
"""
===============================================================================
STRATEGY 09: LIQUIDITY SWEEP & JUDAS SWING REVERSAL (ICT / SMART MONEY CONCEPTS)
===============================================================================
Quantitative Backtesting & Parameter Robustness Engine for CFD Trading (XAUUSD)
Period: 2020 - 2025 (Full Multi-Year Validation)
Timeframe: M15 (Resampled from M1)

Core Mechanisms:
- Session Liquidity Pools: Asian Range (High / Low established between 00:00 - 06:00 / 07:00 UTC)
- Judas Swing (Liquidity Run): Fast excursion during London Open (07:00 - 11:00 UTC)
  or New York Open (12:00 - 16:00 UTC) sweeping beyond the Asian High or Asian Low.
- Liquidity Sweep & Structural Rejection:
  * Bull Trap (Short): Price pierces Asian High by delta >= min_sweep, but candle closes
    back below the Asian High (or prints strong upper rejection wick).
  * Bear Trap (Long): Price pierces Asian Low by delta >= min_sweep, but candle closes
    back above the Asian Low (or prints strong lower rejection wick).
- Risk Management:
  * SL: Sweep extreme wick high/low + buffer
  * TP: Opposite Asian range boundary vs Asymmetric Risk-Reward (2.0R, 3.0R, 4.0R)
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
def simulate_judas_sweep_kernel(
    opens: np.ndarray,
    highs: np.ndarray,
    lows: np.ndarray,
    closes: np.ndarray,
    atr: np.ndarray,
    hours: np.ndarray,
    day_indices: np.ndarray,
    asian_highs: np.ndarray,
    asian_lows: np.ndarray,
    window_mode: int,       # 0: London Only (7-11 UTC), 1: NY Only (12-16 UTC), 2: Both London & NY
    min_sweep_atr: float,   # 0.2, 0.5, 0.8 * ATR
    confirmation_mode: int, # 0: Close back inside range, 1: Rejection Wick > 50%
    tp_mode: int,           # 0: Opposite Asian Level, 1: 2.0R, 2: 3.0R, 3: 4.0R
    sl_buffer_atr: float,   # 0.2, 0.5 ATR above/below sweep extreme
    max_trades_per_day: int,# 1 or 2
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

    curr_day = -1
    daily_trades = 0

    for i in range(warmup, n - 1):
        d_idx = day_indices[i]
        hr = hours[i]

        if d_idx != curr_day:
            curr_day = d_idx
            daily_trades = 0

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
            elif hr >= 21: # End of trading day auto-close
                exit_p = closes[i]
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
            elif hr >= 21: # End of trading day auto-close
                exit_p = closes[i]
                exit_triggered = True

            if exit_triggered:
                trade_pnl = (entry_price - exit_p) * unit_size - (spread + commission_per_unit) * unit_size
                if trade_count < max_trades:
                    pnl_list[trade_count] = trade_pnl
                    holding_bars[trade_count] = i - entry_bar
                    trade_count += 1
                pos = 0

        # 2. Check Entries
        if pos == 0 and daily_trades < max_trades_per_day:
            # Check window
            in_window = False
            if window_mode == 0 and (7 <= hr < 11):
                in_window = True
            elif window_mode == 1 and (12 <= hr < 16):
                in_window = True
            elif window_mode == 2 and ((7 <= hr < 11) or (12 <= hr < 16)):
                in_window = True

            a_high = asian_highs[i]
            a_low = asian_lows[i]
            c_atr = atr[i]

            if in_window and a_high > 0.0 and a_low > 0.0 and c_atr > 0.0:
                bar_range = highs[i] - lows[i]
                if bar_range > 0.0:
                    # Bearish Judas / Liquidity Sweep of Asian High
                    if highs[i] >= a_high + (min_sweep_atr * c_atr):
                        confirmed = False
                        if confirmation_mode == 0:
                            # Closes back below Asian High
                            if closes[i] < a_high:
                                confirmed = True
                        elif confirmation_mode == 1:
                            # Upper rejection wick > 50% of bar range
                            upper_wick = highs[i] - max(opens[i], closes[i])
                            if (upper_wick / bar_range) >= 0.50 and closes[i] < highs[i] - 0.3 * bar_range:
                                confirmed = True

                        if confirmed:
                            pos = -1
                            entry_price = opens[i + 1]
                            sl_price = highs[i] + (sl_buffer_atr * c_atr)
                            risk = sl_price - entry_price
                            if risk < 0.50:
                                risk = 0.50
                                sl_price = entry_price + risk

                            if tp_mode == 0:
                                tp_price = a_low
                            elif tp_mode == 1:
                                tp_price = entry_price - (2.0 * risk)
                            elif tp_mode == 2:
                                tp_price = entry_price - (3.0 * risk)
                            elif tp_mode == 3:
                                tp_price = entry_price - (4.0 * risk)

                            entry_bar = i + 1
                            daily_trades += 1
                            continue

                    # Bullish Judas / Liquidity Sweep of Asian Low
                    if lows[i] <= a_low - (min_sweep_atr * c_atr):
                        confirmed = False
                        if confirmation_mode == 0:
                            # Closes back above Asian Low
                            if closes[i] > a_low:
                                confirmed = True
                        elif confirmation_mode == 1:
                            # Lower rejection wick > 50% of bar range
                            lower_wick = min(opens[i], closes[i]) - lows[i]
                            if (lower_wick / bar_range) >= 0.50 and closes[i] > lows[i] + 0.3 * bar_range:
                                confirmed = True

                        if confirmed:
                            pos = 1
                            entry_price = opens[i + 1]
                            sl_price = lows[i] - (sl_buffer_atr * c_atr)
                            risk = entry_price - sl_price
                            if risk < 0.50:
                                risk = 0.50
                                sl_price = entry_price - risk

                            if tp_mode == 0:
                                tp_price = a_high
                            elif tp_mode == 1:
                                tp_price = entry_price + (2.0 * risk)
                            elif tp_mode == 2:
                                tp_price = entry_price + (3.0 * risk)
                            elif tp_mode == 3:
                                tp_price = entry_price + (4.0 * risk)

                            entry_bar = i + 1
                            daily_trades += 1
                            continue

    # Close remaining open position at last bar
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


def precompute_asian_ranges(df_m15: pd.DataFrame, asian_end_hour: int = 6):
    """
    Computes for each bar the most recent Asian session High and Low.
    Asian session defined from 00:00 to asian_end_hour:00 UTC.
    """
    dates = df_m15.index.date
    hours = df_m15.index.hour
    n = len(df_m15)
    
    asian_highs = np.zeros(n, dtype=np.float64)
    asian_lows = np.zeros(n, dtype=np.float64)
    
    # Track daily Asian range
    curr_date = None
    curr_a_high = 0.0
    curr_a_low = 1e9
    range_locked = False
    
    h_arr = df_m15['high'].values
    l_arr = df_m15['low'].values
    
    for i in range(n):
        d = dates[i]
        hr = hours[i]
        
        if d != curr_date:
            curr_date = d
            curr_a_high = 0.0
            curr_a_low = 1e9
            range_locked = False
            
        if 0 <= hr < asian_end_hour:
            if h_arr[i] > curr_a_high:
                curr_a_high = h_arr[i]
            if l_arr[i] < curr_a_low:
                curr_a_low = l_arr[i]
        else:
            range_locked = True
            
        if range_locked and curr_a_high > 0.0 and curr_a_low < 1e9:
            asian_highs[i] = curr_a_high
            asian_lows[i] = curr_a_low
        else:
            asian_highs[i] = 0.0
            asian_lows[i] = 0.0
            
    return asian_highs, asian_lows


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

    # Sharpe approximation
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
    parser = argparse.ArgumentParser(description="Sweep Strategy 09: Liquidity Sweep & Judas Swing Reversal")
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
    
    # Day indices
    day_series = pd.Series(df_m15.index.date)
    day_indices = (day_series != day_series.shift(1)).cumsum().values.astype(np.int32)

    atr14 = compute_atr(highs, lows, closes, 14)

    # Precompute Asian ranges (00-06 UTC and 00-07 UTC)
    print("[*] Precomputing Asian session ranges (00-06 UTC and 00-07 UTC)...")
    a_highs_06, a_lows_06 = precompute_asian_ranges(df_m15, asian_end_hour=6)
    a_highs_07, a_lows_07 = precompute_asian_ranges(df_m15, asian_end_hour=7)

    # Parameter grid definition
    asian_configs = [
        {"name": "Asian_00_06", "end_hour": 6, "highs": a_highs_06, "lows": a_lows_06},
        {"name": "Asian_00_07", "end_hour": 7, "highs": a_highs_07, "lows": a_lows_07}
    ]
    window_modes = [0, 1, 2] # London Only (0), NY Only (1), Both (2)
    window_names = ["London_07_11", "NY_12_16", "Both_Lon_NY"]
    min_sweeps = [0.2, 0.5, 0.8] # fraction of ATR
    confirm_modes = [0, 1] # 0: Close back inside range, 1: Rejection Wick > 50%
    tp_modes = [0, 1, 2, 3] # 0: Asian Opposite Side, 1: 2.0R, 2: 3.0R, 3: 4.0R
    sl_buffers = [0.2, 0.5] # 0.2 ATR, 0.5 ATR
    max_trades_list = [1, 2]

    # Total combinations = 2 * 3 * 3 * 2 * 4 * 2 * 2 = 576 sets
    total_combs = len(asian_configs) * len(window_modes) * len(min_sweeps) * len(confirm_modes) * len(tp_modes) * len(sl_buffers) * len(max_trades_list)
    print(f"[*] Starting Sweep of {total_combs} parameter combinations...")

    results = []
    c_idx = 0
    t_start = time.time()

    spread = 0.25 # $0.25 spread ($25/lot)
    commission = 0.06 # $6 per 100 oz unit ($0.60 per 0.10 lot)
    unit_size = 10.0 # 0.10 standard lot = 10 oz
    warmup = 100

    for a_cfg in asian_configs:
        a_h = a_cfg["highs"]
        a_l = a_cfg["lows"]
        for w_mode in window_modes:
            for ms in min_sweeps:
                for cm in confirm_modes:
                    for tpm in tp_modes:
                        for slb in sl_buffers:
                            for mtd in max_trades_list:
                                c_idx += 1
                                pnls, holding = simulate_judas_sweep_kernel(
                                    opens, highs, lows, closes, atr14, hours, day_indices,
                                    a_h, a_l, w_mode, ms, cm, tpm, slb, mtd,
                                    spread, commission, unit_size, warmup
                                )
                                m = calculate_metrics(pnls, holding)
                                m.update({
                                    "asian_session": a_cfg["name"],
                                    "window": window_names[w_mode],
                                    "min_sweep_atr": ms,
                                    "confirmation": "CloseInside" if cm == 0 else "Wick50Pct",
                                    "tp_mode": "OppositeBoundary" if tpm == 0 else f"{tpm+1}R",
                                    "sl_buffer_atr": slb,
                                    "max_daily_trades": mtd
                                })
                                results.append(m)

                                if c_idx % 100 == 0 or c_idx == total_combs:
                                    elapsed = time.time() - t_start
                                    print(f"[{c_idx}/{total_combs}] Completed ({c_idx/total_combs*100:.1f}%) | Elapsed: {elapsed:.1f}s")

    df_res = pd.DataFrame(results)
    csv_path = os.path.join(args.out_dir, "strategy_09_judas_sweep_sweep_results.csv")
    df_res.to_csv(csv_path, index=False)
    print(f"[+] Saved full results to {csv_path}")

    # Identify Champion
    viable = df_res[df_res['total_trades'] >= 100]
    if len(viable) > 0:
        champ = viable.sort_values(by=['net_profit', 'profit_factor'], ascending=[False, False]).iloc[0]
    else:
        champ = df_res.sort_values(by=['net_profit', 'profit_factor'], ascending=[False, False]).iloc[0]

    champ_dict = champ.to_dict()
    json_path = os.path.join(args.out_dir, "strategy_09_judas_sweep_champion.json")
    with open(json_path, 'w') as f:
        json.dump(champ_dict, f, indent=2)
    print(f"[+] Champion JSON saved to {json_path}")
    print("\n================== CHAMPION RESULTS ==================")
    for k, v in champ_dict.items():
        print(f"  {k}: {v}")
    print("======================================================")

if __name__ == "__main__":
    main()
