#!/usr/bin/env python3
"""
===============================================================================
STRATEGY 14: LONDON SESSION LIQUIDITY MOMENTUM (EURUSD-LSOM)
===============================================================================
Bespoke Forex Major Strategy Logic Template
Asset: EURUSD CFD / Forex (2020 - 2025, 72 Calendar Months)
Timeframe: M15 (Resampled from M1)

Core Quantitative Hypothesis for Forex:
- Unlike Gold, EURUSD has distinct session liquidity clustering centered around the
  London / Frankfurt open (07:00 - 11:00 UTC).
- European currencies exhibit structural directional continuation when London volume
  expands beyond the Asian Range (00:00 - 06:00 UTC).
- Engine Logic:
  1. Establishes Asian Range High & Low (00:00 - 06:00 UTC).
  2. During London Open window (07:00 - 11:00 UTC):
     - Bullish: M15 close breaks above Asian High + Close > EMA(200).
     - Bearish: M15 close breaks below Asian Low + Close < EMA(200).
  3. Causal Entry: Open of bar i+1.
  4. SL: Asian Midline OR 1.5x - 2.5x ATR(14).
  5. TP: Asymmetric Risk-Reward (2.0R, 3.0R, 4.0R).
  6. Frictions: 0.5 pip spread ($5/lot) + $6/lot round-turn commission ($1.10/0.10 lot).
  7. 72-Month Consistency Heatmap Analysis across 2020 - 2025.
===============================================================================
"""

import os
import sys
import time
import json
import argparse
import numpy as np
import pandas as pd

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

def precompute_asian_ranges(df_m15: pd.DataFrame, asian_end_hour: int = 6):
    dates = df_m15.index.date
    hours = df_m15.index.hour
    n = len(df_m15)
    
    asian_highs = np.zeros(n, dtype=np.float64)
    asian_lows = np.zeros(n, dtype=np.float64)
    
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

def simulate_eurusd_momentum(
    opens: np.ndarray,
    highs: np.ndarray,
    lows: np.ndarray,
    closes: np.ndarray,
    atr14: np.ndarray,
    ema200: np.ndarray,
    asian_highs: np.ndarray,
    asian_lows: np.ndarray,
    hours: np.ndarray,
    day_indices: np.ndarray,
    dates: pd.DatetimeIndex,
    sl_mode: int,               # 0: Asian Midline, 1: ATR-based (1.5x), 2: ATR-based (2.5x)
    tp_rr_mult: float,          # 2.0, 3.0, 4.0
    use_ema_filter: bool,       # True, False
    spread_pips: float = 0.5,   # 0.5 pip
    commission_per_lot: float = 6.0, # $6/lot
    lot_size: float = 0.10,     # 0.10 lot ($1/pip)
    warmup: int = 200
):
    n = len(closes)
    pip_val = 10.0 # $10 per pip on 1.0 lot, so $1.00 per pip on 0.10 lot
    pip_factor = 0.0001
    pip_cost_per_trade = (spread_pips * 1.0) + (commission_per_lot * lot_size) # ~$1.10

    trades = []
    pos = 0
    entry_p = 0.0
    sl_p = 0.0
    tp_p = 0.0
    entry_i = 0

    curr_day = -1
    daily_trade_done = False

    for i in range(warmup, n - 1):
        d_idx = day_indices[i]
        hr = hours[i]

        if d_idx != curr_day:
            curr_day = d_idx
            daily_trade_done = False

        # 1. Manage Exits
        if pos == 1:
            exit_triggered = False
            exit_p = 0.0
            if lows[i] <= sl_p:
                exit_p = sl_p if opens[i] >= sl_p else opens[i]
                exit_triggered = True
            elif highs[i] >= tp_p:
                exit_p = tp_p if opens[i] <= tp_p else opens[i]
                exit_triggered = True
            elif hr >= 21: # End of day close
                exit_p = closes[i]
                exit_triggered = True

            if exit_triggered:
                pnl_pips = (exit_p - entry_p) / pip_factor
                pnl_usd = (pnl_pips * lot_size * pip_val) - pip_cost_per_trade
                trades.append({
                    "pnl": pnl_usd, "entry_bar": entry_i, "exit_bar": i,
                    "date": dates[i], "type": "BUY"
                })
                pos = 0

        elif pos == -1:
            exit_triggered = False
            exit_p = 0.0
            if highs[i] >= sl_p:
                exit_p = sl_p if opens[i] <= sl_p else opens[i]
                exit_triggered = True
            elif lows[i] <= tp_p:
                exit_p = tp_p if opens[i] >= tp_p else opens[i]
                exit_triggered = True
            elif hr >= 21:
                exit_p = closes[i]
                exit_triggered = True

            if exit_triggered:
                pnl_pips = (entry_p - exit_p) / pip_factor
                pnl_usd = (pnl_pips * lot_size * pip_val) - pip_cost_per_trade
                trades.append({
                    "pnl": pnl_usd, "entry_bar": entry_i, "exit_bar": i,
                    "date": dates[i], "type": "SELL"
                })
                pos = 0

        # 2. Check Entries during London Open Window (07:00 - 11:00 UTC)
        if pos == 0 and (not daily_trade_done) and (7 <= hr < 11):
            a_h = asian_highs[i]
            a_l = asian_lows[i]
            c_atr = atr14[i]

            if a_h > 0 and a_l > 0 and c_atr > 0:
                # Bullish Breakout
                if closes[i] > a_h:
                    trend_ok = (closes[i] > ema200[i]) if use_ema_filter else True
                    if trend_ok:
                        pos = 1
                        entry_p = opens[i + 1] + (spread_pips * 0.5 * pip_factor)
                        if sl_mode == 0:
                            sl_p = (a_h + a_l) * 0.5 # Asian Midline
                        elif sl_mode == 1:
                            sl_p = entry_p - (1.5 * c_atr)
                        else:
                            sl_p = entry_p - (2.5 * c_atr)

                        risk = entry_p - sl_p
                        if risk < 5.0 * pip_factor:
                            risk = 5.0 * pip_factor
                            sl_p = entry_p - risk
                        tp_p = entry_p + (tp_rr_mult * risk)
                        entry_i = i + 1
                        daily_trade_done = True
                        continue

                # Bearish Breakout
                elif closes[i] < a_l:
                    trend_ok = (closes[i] < ema200[i]) if use_ema_filter else True
                    if trend_ok:
                        pos = -1
                        entry_p = opens[i + 1] - (spread_pips * 0.5 * pip_factor)
                        if sl_mode == 0:
                            sl_p = (a_h + a_l) * 0.5
                        elif sl_mode == 1:
                            sl_p = entry_p + (1.5 * c_atr)
                        else:
                            sl_p = entry_p + (2.5 * c_atr)

                        risk = sl_p - entry_p
                        if risk < 5.0 * pip_factor:
                            risk = 5.0 * pip_factor
                            sl_p = entry_p + risk
                        tp_p = entry_p - (tp_rr_mult * risk)
                        entry_i = i + 1
                        daily_trade_done = True
                        continue

    return trades

def evaluate_monthly_consistency(trades: list) -> dict:
    if len(trades) < 20:
        return {
            "total_trades": len(trades), "net_profit": 0.0, "pf": 0.0,
            "win_rate": 0.0, "max_dd": 0.0, "mcr": 0.0,
            "total_months": 0, "pos_months": 0, "neg_months": 0
        }

    df_t = pd.DataFrame(trades)
    df_t["year_month"] = pd.to_datetime(df_t["date"]).dt.to_period("M")

    pnls = df_t["pnl"].values
    wins = pnls[pnls > 0]
    losses = pnls[pnls < 0]
    gp = float(np.sum(wins)) if len(wins) > 0 else 0.0
    gl = float(abs(np.sum(losses))) if len(losses) > 0 else 0.0
    net = float(np.sum(pnls))
    pf = (gp / gl) if gl > 0 else 99.0
    wr = (len(wins) / len(pnls)) * 100.0

    eq = 10000.0 + np.cumsum(pnls)
    peaks = np.maximum.accumulate(eq)
    max_dd = float(np.max(peaks - eq)) if len(eq) > 0 else 0.0

    monthly_pnl = df_t.groupby("year_month")["pnl"].sum()
    total_months = len(monthly_pnl)
    pos_months = int(np.sum(monthly_pnl > 0))
    neg_months = int(np.sum(monthly_pnl <= 0))
    mcr = (pos_months / total_months * 100.0) if total_months > 0 else 0.0

    return {
        "total_trades": len(trades),
        "net_profit": round(net, 2),
        "pf": round(pf, 3),
        "win_rate": round(wr, 2),
        "max_dd": round(max_dd, 2),
        "mcr": round(mcr, 2),
        "total_months": total_months,
        "pos_months": pos_months,
        "neg_months": neg_months
    }

def main():
    parser = argparse.ArgumentParser(description="Sweep Strategy 14: EURUSD London Liquidity Momentum")
    parser.add_argument("--data", type=str, default="/mnt/sdcard/Download/EA/EURUSD_M1.csv.gz", help="Path to M1 data")
    parser.add_argument("--out_dir", type=str, default="/root/CFD-Trading-ML/projects/quant_strategy_discovery/results", help="Results dir")
    args = parser.parse_args()

    os.makedirs(args.out_dir, exist_ok=True)

    print(f"[*] Loading M1 data from {args.data}...")
    t0 = time.time()
    df_raw = pd.read_csv(
        args.data,
        usecols=["datetime", "open", "high", "low", "close", "tick_volume"],
        dtype={"open": np.float32, "high": np.float32, "low": np.float32, "close": np.float32, "tick_volume": np.int32}
    )
    df_raw["datetime"] = pd.to_datetime(df_raw["datetime"])
    df_raw.set_index("datetime", inplace=True)
    df_raw.sort_index(inplace=True)
    print(f"[+] Loaded {len(df_raw):,} M1 bars in {time.time() - t0:.2f}s.")

    print(f"[*] Resampling to M15 timeframe...")
    df_m15 = df_raw.resample("15min").agg({
        "open": "first", "high": "max", "low": "min", "close": "last", "tick_volume": "sum"
    }).dropna()
    print(f"[+] Resampled M15 bars: {len(df_m15):,} bars.")

    opens = df_m15["open"].values.astype(np.float64)
    highs = df_m15["high"].values.astype(np.float64)
    lows = df_m15["low"].values.astype(np.float64)
    closes = df_m15["close"].values.astype(np.float64)
    hours = df_m15.index.hour.values.astype(np.int32)
    dates = df_m15.index

    day_series = pd.Series(df_m15.index.date)
    day_indices = (day_series != day_series.shift(1)).cumsum().values.astype(np.int32)

    atr14 = compute_atr(highs, lows, closes, 14)
    ema200 = compute_ema(closes, 200)

    print("[*] Precomputing Asian ranges (00:00 - 06:00 UTC)...")
    a_highs, a_lows = precompute_asian_ranges(df_m15, asian_end_hour=6)

    # Parameter grid for mass sweep
    sl_modes = [0, 1, 2] # Midline (0), 1.5x ATR (1), 2.5x ATR (2)
    tp_rr_mults = [2.0, 3.0, 4.0]
    use_ema_filters = [True, False]

    # Total combinations = 3 * 3 * 2 = 18 combinations
    total_combs = len(sl_modes) * len(tp_rr_mults) * len(use_ema_filters)
    print(f"[*] Sweeping {total_combs} EURUSD momentum combinations across 72 calendar months...")

    results = []
    c_idx = 0
    t_start = time.time()

    for slm in sl_modes:
        for tpr in tp_rr_mults:
            for ef in use_ema_filters:
                c_idx += 1
                trades = simulate_eurusd_momentum(
                    opens, highs, lows, closes, atr14, ema200,
                    a_highs, a_lows, hours, day_indices, dates,
                    sl_mode=slm, tp_rr_mult=tpr, use_ema_filter=ef
                )
                metrics = evaluate_monthly_consistency(trades)
                metrics.update({
                    "sl_mode": "AsianMidline" if slm == 0 else f"{1.5 if slm==1 else 2.5}xATR",
                    "tp_rr_mult": tpr,
                    "use_ema_filter": ef
                })
                results.append(metrics)

                if c_idx % 5 == 0 or c_idx == total_combs:
                    print(f"[{c_idx}/{total_combs}] Completed ({c_idx/total_combs*100:.1f}%) | Elapsed: {time.time()-t_start:.1f}s")

    df_res = pd.DataFrame(results)
    csv_path = os.path.join(args.out_dir, "strategy_14_eurusd_momentum_sweep_results.csv")
    df_res.to_csv(csv_path, index=False)
    print(f"[+] Full sweep results saved to: {csv_path}")

    viable = df_res[(df_res["total_trades"] >= 200) & (df_res["pf"] >= 1.05)]
    if len(viable) > 0:
        champ = viable.sort_values(by=["mcr", "net_profit"], ascending=[False, False]).iloc[0]
    else:
        champ = df_res.sort_values(by=["mcr", "net_profit"], ascending=[False, False]).iloc[0]

    champ_dict = champ.to_dict()
    json_path = os.path.join(args.out_dir, "strategy_14_eurusd_momentum_champion.json")
    with open(json_path, "w") as f:
        json.dump(champ_dict, f, indent=2)
    print(f"[+] Champion JSON saved to: {json_path}")

    print("\n" + "="*70)
    print("🏆 CHAMPION PARAMETER SET (STRATEGY 14: EURUSD MOMENTUM)")
    print("="*70)
    for k, v in champ_dict.items():
        print(f"  {k}: {v}")
    print("="*70)

if __name__ == "__main__":
    main()
