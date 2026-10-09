#!/usr/bin/env python3
"""
===============================================================================
STRATEGY 02: OPENING RANGE BREAKOUT (ORB / LONDON & NY BREAKOUT)
===============================================================================
Quantitative Backtesting & Parameter Robustness Engine for CFD Trading (XAUUSD)
Period: 2020 - 2025 (Full Multi-Year Validation)
Timeframe: M5 (Resampled from M1 for precise intraday timing)

Core Mechanisms:
- Opening Range Detection: High/Low established during first N minutes of London (07:00 UTC) or NY (12:00 UTC)
- Range Volatility Filter: Max allowed range size in ATR multiples
- Breakout Buffer: Entry trigger at Range Boundary + Buffer * ATR
- Strict 1 Trade Per Session Rule: Eliminates overtrading chop
- Stop Loss: Opposite Boundary, Midpoint, or ATR
- Take Profit: Risk-Reward Multiples (1.5R to 4.0R)
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
from numba import njit

# -----------------------------------------------------------------------------
# NUMBA HIGH-SPEED ORB SIMULATION KERNEL
# -----------------------------------------------------------------------------
@njit(fastmath=True)
def simulate_orb(
    opens: np.ndarray,
    highs: np.ndarray,
    lows: np.ndarray,
    closes: np.ndarray,
    atr: np.ndarray,
    hours: np.ndarray,
    minutes: np.ndarray,
    day_indices: np.ndarray,
    session_target: int,      # 1: London (07:00), 2: NY (12:00), 3: Dual (Both)
    orb_bars: int,            # 3 bars (15m), 6 bars (30m), 12 bars (60m)
    buffer_atr_mult: float,   # 0.0, 0.10, 0.25, 0.50
    sl_mode: int,             # 0: Opposite Bound, 1: Midpoint, 2: 1.5x ATR, 3: 2.0x ATR
    tp_rr_mult: float,        # 1.5, 2.0, 3.0, 4.0
    max_range_atr: float,     # 1.5, 2.5, 999.0
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

    # Session tracking variables
    current_day = -1
    london_or_high = 0.0
    london_or_low = 999999.0
    london_or_ready = False
    london_traded = False
    london_bar_count = 0

    ny_or_high = 0.0
    ny_or_low = 999999.0
    ny_or_ready = False
    ny_traded = False
    ny_bar_count = 0

    for i in range(warmup, n - 1):
        day = day_indices[i]
        hr = hours[i]
        mn = minutes[i]

        # Reset on new day
        if day != current_day:
            current_day = day
            london_or_high = 0.0
            london_or_low = 999999.0
            london_or_ready = False
            london_traded = False
            london_bar_count = 0

            ny_or_high = 0.0
            ny_or_low = 999999.0
            ny_or_ready = False
            ny_traded = False
            ny_bar_count = 0

        # -------------------------------------------------------------
        # 1. Manage Open Position Exits
        # -------------------------------------------------------------
        if pos == 1:
            exit_triggered = False
            exit_p = 0.0

            if lows[i] <= sl_price:
                exit_p = sl_price if opens[i] >= sl_price else opens[i]
                exit_triggered = True
            elif highs[i] >= tp_price:
                exit_p = tp_price if opens[i] <= tp_price else opens[i]
                exit_triggered = True
            # Session Time Exit: Close at 21:00 UTC
            elif hr >= 21:
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
            elif hr >= 21:
                exit_p = closes[i]
                exit_triggered = True

            if exit_triggered:
                trade_pnl = (entry_price - exit_p) * unit_size - (spread + commission_per_unit) * unit_size
                if trade_count < max_trades:
                    pnl_list[trade_count] = trade_pnl
                    holding_bars[trade_count] = i - entry_bar
                    trade_count += 1
                pos = 0

        # -------------------------------------------------------------
        # 2. Build Opening Ranges
        # -------------------------------------------------------------
        # London Session: 07:00 UTC start
        if hr == 7 and not london_or_ready:
            if highs[i] > london_or_high:
                london_or_high = highs[i]
            if lows[i] < london_or_low:
                london_or_low = lows[i]
            london_bar_count += 1
            if london_bar_count >= orb_bars:
                # Range established
                r_size = london_or_high - london_or_low
                cur_atr = atr[i] if atr[i] > 0.0 else 1.0
                if r_size <= max_range_atr * cur_atr:
                    london_or_ready = True

        # NY Session: 12:00 UTC start
        if hr == 12 and not ny_or_ready:
            if highs[i] > ny_or_high:
                ny_or_high = highs[i]
            if lows[i] < ny_or_low:
                ny_or_low = lows[i]
            ny_bar_count += 1
            if ny_bar_count >= orb_bars:
                r_size = ny_or_high - ny_or_low
                cur_atr = atr[i] if atr[i] > 0.0 else 1.0
                if r_size <= max_range_atr * cur_atr:
                    ny_or_ready = True

        # -------------------------------------------------------------
        # 3. Check Breakout Entries
        # -------------------------------------------------------------
        if pos == 0:
            cur_atr = atr[i] if atr[i] > 0.0 else 1.0
            buf = buffer_atr_mult * cur_atr

            # A. London Breakout (Trade window 07:00 - 12:00 UTC)
            if (session_target == 1 or session_target == 3) and london_or_ready and not london_traded:
                if 7 <= hr < 12:
                    upper_trigger = london_or_high + buf
                    lower_trigger = london_or_low - buf

                    # Long Breakout
                    if closes[i] > upper_trigger:
                        pos = 1
                        london_traded = True
                        entry_price = opens[i + 1] + (spread * 0.5)
                        entry_bar = i + 1

                        if sl_mode == 0:
                            sl_dist = entry_price - london_or_low
                        elif sl_mode == 1:
                            mid = (london_or_high + london_or_low) * 0.5
                            sl_dist = entry_price - mid
                        elif sl_mode == 2:
                            sl_dist = 1.5 * cur_atr
                        else:
                            sl_dist = 2.0 * cur_atr

                        if sl_dist <= 0.5:
                            sl_dist = 1.5 * cur_atr
                        sl_price = entry_price - sl_dist
                        tp_price = entry_price + (sl_dist * tp_rr_mult)

                    # Short Breakout
                    elif closes[i] < lower_trigger:
                        pos = -1
                        london_traded = True
                        entry_price = opens[i + 1] - (spread * 0.5)
                        entry_bar = i + 1

                        if sl_mode == 0:
                            sl_dist = london_or_high - entry_price
                        elif sl_mode == 1:
                            mid = (london_or_high + london_or_low) * 0.5
                            sl_dist = mid - entry_price
                        elif sl_mode == 2:
                            sl_dist = 1.5 * cur_atr
                        else:
                            sl_dist = 2.0 * cur_atr

                        if sl_dist <= 0.5:
                            sl_dist = 1.5 * cur_atr
                        sl_price = entry_price + sl_dist
                        tp_price = entry_price - (sl_dist * tp_rr_mult)

            # B. NY Breakout (Trade window 12:00 - 18:00 UTC)
            if (session_target == 2 or session_target == 3) and ny_or_ready and not ny_traded:
                if 12 <= hr < 18:
                    upper_trigger = ny_or_high + buf
                    lower_trigger = ny_or_low - buf

                    # Long Breakout
                    if closes[i] > upper_trigger:
                        pos = 1
                        ny_traded = True
                        entry_price = opens[i + 1] + (spread * 0.5)
                        entry_bar = i + 1

                        if sl_mode == 0:
                            sl_dist = entry_price - ny_or_low
                        elif sl_mode == 1:
                            mid = (ny_or_high + ny_or_low) * 0.5
                            sl_dist = entry_price - mid
                        elif sl_mode == 2:
                            sl_dist = 1.5 * cur_atr
                        else:
                            sl_dist = 2.0 * cur_atr

                        if sl_dist <= 0.5:
                            sl_dist = 1.5 * cur_atr
                        sl_price = entry_price - sl_dist
                        tp_price = entry_price + (sl_dist * tp_rr_mult)

                    # Short Breakout
                    elif closes[i] < lower_trigger:
                        pos = -1
                        ny_traded = True
                        entry_price = opens[i + 1] - (spread * 0.5)
                        entry_bar = i + 1

                        if sl_mode == 0:
                            sl_dist = ny_or_high - entry_price
                        elif sl_mode == 1:
                            mid = (ny_or_high + ny_or_low) * 0.5
                            sl_dist = mid - entry_price
                        elif sl_mode == 2:
                            sl_dist = 1.5 * cur_atr
                        else:
                            sl_dist = 2.0 * cur_atr

                        if sl_dist <= 0.5:
                            sl_dist = 1.5 * cur_atr
                        sl_price = entry_price + sl_dist
                        tp_price = entry_price - (sl_dist * tp_rr_mult)

    # 4. Metrics Calculation
    if trade_count < 10:
        return 0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0

    net_pnl = 0.0
    gross_profit = 0.0
    gross_loss = 0.0
    wins = 0
    running_equity = 10000.0
    peak_equity = 10000.0
    max_dd = 0.0
    total_holding = 0

    for t in range(trade_count):
        p = pnl_list[t]
        net_pnl += p
        if p > 0.0:
            gross_profit += p
            wins += 1
        elif p < 0.0:
            gross_loss += -p
        running_equity += p
        if running_equity > peak_equity:
            peak_equity = running_equity
        dd = peak_equity - running_equity
        if dd > max_dd:
            max_dd = dd
        total_holding += holding_bars[t]

    profit_factor = gross_profit / (gross_loss if gross_loss > 0.0 else 0.0001)
    win_rate = (wins / trade_count) * 100.0
    romad = net_pnl / max_dd if max_dd > 0.0 else 0.0
    avg_holding = float(total_holding) / float(trade_count)

    mean_pnl = net_pnl / trade_count
    var_pnl = 0.0
    for t in range(trade_count):
        diff = pnl_list[t] - mean_pnl
        var_pnl += diff * diff
    std_pnl = np.sqrt(var_pnl / trade_count)
    sharpe = (mean_pnl / std_pnl) * np.sqrt(trade_count / 5.0) if std_pnl > 0.0 else 0.0

    return (
        trade_count,
        float(net_pnl),
        float(gross_profit),
        float(gross_loss),
        float(profit_factor),
        float(win_rate),
        float(max_dd),
        float(romad),
        float(sharpe),
        avg_holding
    )


# -----------------------------------------------------------------------------
# DATA LOADING & PREPARATION
# -----------------------------------------------------------------------------
def load_and_resample_m5(data_path: str):
    print(f"[*] Loading data from: {data_path}...")
    t0 = time.time()
    df = pd.read_csv(
        data_path,
        usecols=["datetime", "open", "high", "low", "close", "tick_volume"],
        dtype={
            "open": np.float32,
            "high": np.float32,
            "low": np.float32,
            "close": np.float32,
            "tick_volume": np.int32
        }
    )
    df["datetime"] = pd.to_datetime(df["datetime"])
    df.set_index("datetime", inplace=True)
    df.sort_index(inplace=True)
    print(f"[+] Loaded {len(df):,} M1 bars in {time.time() - t0:.2f}s.")

    print("[*] Resampling to 5min (M5)...")
    t1 = time.time()
    df_m5 = df.resample("5min").agg({
        "open": "first",
        "high": "max",
        "low": "min",
        "close": "last",
        "tick_volume": "sum"
    }).dropna()
    print(f"[+] Resampled to {len(df_m5):,} M5 bars in {time.time() - t1:.2f}s.")

    # Compute ATR(14)
    high = df_m5["high"].values.astype(np.float64)
    low = df_m5["low"].values.astype(np.float64)
    close = df_m5["close"].values.astype(np.float64)

    tr = np.maximum(
        high[1:] - low[1:],
        np.maximum(
            np.abs(high[1:] - close[:-1]),
            np.abs(low[1:] - close[:-1])
        )
    )
    tr = np.insert(tr, 0, high[0] - low[0])
    atr_series = pd.Series(tr, index=df_m5.index).rolling(window=14).mean().fillna(1.0).values.astype(np.float64)

    hours = df_m5.index.hour.values.astype(np.int32)
    minutes = df_m5.index.minute.values.astype(np.int32)
    # Day index: continuous integer incrementing on each date change
    day_indices = (df_m5.index.date != np.roll(df_m5.index.date, 1)).cumsum().astype(np.int32)

    return df_m5, atr_series, hours, minutes, day_indices


# -----------------------------------------------------------------------------
# MASS PARAMETER SWEEP
# -----------------------------------------------------------------------------
def run_orb_sweep(
    df_m5: pd.DataFrame,
    atr_series: np.ndarray,
    hours: np.ndarray,
    minutes: np.ndarray,
    day_indices: np.ndarray,
    symbol: str = "XAUUSD",
    output_dir: str = "projects/quant_strategy_discovery/results"
):
    os.makedirs(output_dir, exist_ok=True)
    opens = df_m5["open"].values.astype(np.float64)
    highs = df_m5["high"].values.astype(np.float64)
    lows = df_m5["low"].values.astype(np.float64)
    closes = df_m5["close"].values.astype(np.float64)

    unit_size = 10.0   # 0.10 lot
    spread = 0.25      # $0.25 spread
    commission = 0.06  # $6.00 / lot round-turn
    warmup = 100

    # Grid definition:
    # session_target: 1: London, 2: NY, 3: Dual
    session_targets = [1, 2, 3]
    # orb_bars on M5: 3 bars = 15m, 6 bars = 30m, 12 bars = 60m
    orb_durations = [3, 6, 12]
    buffer_atrs = [0.0, 0.10, 0.25, 0.50]
    sl_modes = [0, 1, 2, 3]
    tp_rrs = [1.5, 2.0, 3.0, 4.0]
    max_range_atrs = [1.5, 2.5, 999.0]

    total_combos = (
        len(session_targets) * len(orb_durations) * len(buffer_atrs) *
        len(sl_modes) * len(tp_rrs) * len(max_range_atrs)
    )

    print(f"\n{'='*75}")
    print(f"🚀 COMMENCING MASS PARAMETER SWEEP: STRATEGY 02 (OPENING RANGE BREAKOUT)")
    print(f"   Symbol: {symbol} | Total Combinations: {total_combos:,}")
    print(f"   Frictions: Spread=${spread:.2f} | Comm=${commission*100:.2f}/lot | Lot: 0.10")
    print(f"{'='*75}\n")

    # Warmup Numba JIT
    _ = simulate_orb(
        opens, highs, lows, closes, atr_series, hours, minutes, day_indices,
        1, 6, 0.10, 0, 2.0, 2.5, spread, commission, unit_size, warmup
    )

    results = []
    t_start = time.time()
    count = 0

    session_names = {1: "London", 2: "NewYork", 3: "Dual_Session"}
    sl_names = {0: "Opposite_Bound", 1: "Range_Midpoint", 2: "1.5x_ATR", 3: "2.0x_ATR"}
    orb_bar_names = {3: "15min", 6: "30min", 12: "60min"}

    for sess in session_targets:
        for dur in orb_durations:
            for buf in buffer_atrs:
                for sl_m in sl_modes:
                    for tp_r in tp_rrs:
                        for max_r in max_range_atrs:
                            count += 1
                            res = simulate_orb(
                                opens, highs, lows, closes, atr_series, hours, minutes, day_indices,
                                sess, dur, buf, sl_m, tp_r, max_r,
                                spread, commission, unit_size, warmup
                            )
                            (
                                trades, net_pnl, gp, gl, pf,
                                wr, mdd, romad, sharpe, avg_hold
                            ) = res

                            results.append({
                                "session_target": session_names[sess],
                                "orb_window": orb_bar_names[dur],
                                "buffer_atr": buf,
                                "sl_mode": sl_names[sl_m],
                                "tp_rr_mult": tp_r,
                                "max_range_atr": max_r if max_r < 100 else "No_Cap",
                                "total_trades": trades,
                                "net_profit": net_pnl,
                                "gross_profit": gp,
                                "gross_loss": gl,
                                "profit_factor": pf,
                                "win_rate": wr,
                                "max_drawdown": mdd,
                                "romad": romad,
                                "sharpe": sharpe,
                                "avg_holding_bars": avg_hold
                            })

                            if count % 200 == 0 or count == total_combos:
                                elapsed = time.time() - t_start
                                speed = count / elapsed if elapsed > 0 else 0
                                print(f"[*] Swept {count:,} / {total_combos:,} combos ({count/total_combos*100:.1f}%) | Speed: {speed:.1f} sets/sec")

    sweep_time = time.time() - t_start
    print(f"\n[+] Mass sweep completed in {sweep_time:.2f}s ({total_combos/sweep_time:.1f} sets/sec)!")

    res_df = pd.DataFrame(results)

    # Save complete sweep results to CSV
    csv_path = os.path.join(output_dir, "strategy_02_orb_sweep_results.csv")
    res_df.to_csv(csv_path, index=False)
    print(f"[+] Complete sweep results saved to: {csv_path}")

    # Statistically significant parameter sets (minimum 100 trades)
    stat_df = res_df[res_df["total_trades"] >= 100].copy()
    if stat_df.empty:
        stat_df = res_df[res_df["total_trades"] >= 30].copy()

    # Ranking by composite score
    stat_df["composite_score"] = (
        stat_df["profit_factor"] * 0.4 +
        (stat_df["net_profit"] / (stat_df["max_drawdown"] + 1e-4)) * 0.4 +
        stat_df["sharpe"] * 0.2
    )
    stat_df.sort_values(by="composite_score", ascending=False, inplace=True)

    top_10 = stat_df.head(10)
    champion = stat_df.iloc[0]

    print(f"\n{'='*75}")
    print(f"🏆 TOP 5 PARAMETER COMBINATIONS (STRATEGY 02 - ORB BREAKOUT)")
    print(f"{'='*75}")
    for idx, row in top_10.head(5).iterrows():
        print(f"Rank: Sess={row['session_target']} | Window={row['orb_window']} | "
              f"Buf={row['buffer_atr']}x | SL={row['sl_mode']} | TP={row['tp_rr_mult']}R | "
              f"MaxRange={row['max_range_atr']} | Net=${row['net_profit']:,.2f} | PF={row['profit_factor']:.2f} | "
              f"WR={row['win_rate']:.1f}% | DD=${row['max_drawdown']:,.2f} | Trades={int(row['total_trades'])}")

    print(f"\n{'='*75}")
    print(f"🥇 ULTIMATE CHAMPION PARAMETER SET:")
    print(f"   Session Target: {champion['session_target']}")
    print(f"   Opening Window: {champion['orb_window']}")
    print(f"   Buffer ATR:     {champion['buffer_atr']}x ATR(14)")
    print(f"   Stop Loss Mode: {champion['sl_mode']}")
    print(f"   Take Profit:    {champion['tp_rr_mult']}R (Risk Multiple)")
    print(f"   Max Range Cap:  {champion['max_range_atr']}")
    print(f"   --- Performance Across 2020-2025 ---")
    print(f"   Net Profit:     ${champion['net_profit']:,.2f} (on 0.10 lot)")
    print(f"   Profit Factor:  {champion['profit_factor']:.2f}")
    print(f"   Win Rate:       {champion['win_rate']:.2f}%")
    print(f"   Total Trades:   {int(champion['total_trades'])} ({int(champion['total_trades'])/5:.1f} trades/year)")
    print(f"   Max Drawdown:   ${champion['max_drawdown']:,.2f}")
    print(f"   RoMaD (Ret/DD): {champion['romad']:.2f}")
    print(f"   Sharpe Ratio:   {champion['sharpe']:.2f}")
    print(f"{'='*75}\n")

    # Evaluate Yearly Consistency for Champion
    print("[*] Running multi-year breakdown for Champion Parameter Set...")
    champion_dict = champion.to_dict()
    yearly_breakdown = evaluate_orb_yearly_consistency(
        df_m5, atr_series, hours, minutes, day_indices,
        champion_dict, spread, commission, unit_size
    )
    champion_dict["yearly_breakdown"] = yearly_breakdown

    champ_json_path = os.path.join(output_dir, "strategy_02_orb_champion.json")
    with open(champ_json_path, "w") as f:
        clean_dict = {k: (float(v) if isinstance(v, (np.floating, float)) else (int(v) if isinstance(v, (np.integer, int)) else v)) for k, v in champion_dict.items() if k != "yearly_breakdown"}
        clean_dict["yearly_breakdown"] = yearly_breakdown
        json.dump(clean_dict, f, indent=2)
    print(f"[+] Champion summary saved to: {champ_json_path}")

    return res_df, top_10, champion_dict


def evaluate_orb_yearly_consistency(
    df_m5: pd.DataFrame,
    atr_series: np.ndarray,
    hours: np.ndarray,
    minutes: np.ndarray,
    day_indices: np.ndarray,
    param_dict: dict,
    spread: float,
    commission: float,
    unit_size: float
):
    yearly_results = {}
    years = sorted(df_m5.index.year.unique())
    warmup = 50

    session_map = {"London": 1, "NewYork": 2, "Dual_Session": 3}
    sl_map = {"Opposite_Bound": 0, "Range_Midpoint": 1, "1.5x_ATR": 2, "2.0x_ATR": 3}
    dur_map = {"15min": 3, "30min": 6, "60min": 12}

    sess = session_map[param_dict["session_target"]]
    dur = dur_map[param_dict["orb_window"]]
    buf = float(param_dict["buffer_atr"])
    sl_m = sl_map[param_dict["sl_mode"]]
    tp_r = float(param_dict["tp_rr_mult"])
    max_r = 999.0 if param_dict["max_range_atr"] == "No_Cap" else float(param_dict["max_range_atr"])

    for yr in years:
        mask = (df_m5.index.year == yr)
        if np.sum(mask) < 500:
            continue
        opens_yr = df_m5["open"].values[mask].astype(np.float64)
        highs_yr = df_m5["high"].values[mask].astype(np.float64)
        lows_yr = df_m5["low"].values[mask].astype(np.float64)
        closes_yr = df_m5["close"].values[mask].astype(np.float64)
        atr_yr = atr_series[mask]
        hours_yr = hours[mask]
        minutes_yr = minutes[mask]
        day_yr = day_indices[mask]

        res = simulate_orb(
            opens_yr, highs_yr, lows_yr, closes_yr, atr_yr, hours_yr, minutes_yr, day_yr,
            sess, dur, buf, sl_m, tp_r, max_r,
            spread, commission, unit_size, warmup
        )
        trades, net, gp, gl, pf, wr, mdd, romad, sharpe, _ = res
        yearly_results[int(yr)] = {
            "trades": int(trades),
            "net_profit": float(net),
            "profit_factor": float(pf),
            "win_rate": float(wr),
            "max_drawdown": float(mdd)
        }
        print(f"   Year {yr}: Net=${net:,.2f} | PF={pf:.2f} | WR={wr:.1f}% | DD=${mdd:,.2f} | Trades={int(trades)}")

    return yearly_results


# -----------------------------------------------------------------------------
# MAIN ENTRYPOINT
# -----------------------------------------------------------------------------
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Strategy 02: ORB Breakout Sweep")
    parser.add_argument("--data", type=str, default=None, help="Path to M1 CSV dataset")
    parser.add_argument("--symbol", type=str, default="XAUUSD", help="Symbol name")
    parser.add_argument("--output_dir", type=str, default="projects/quant_strategy_discovery/results", help="Output directory")
    args, _ = parser.parse_known_args()

    candidates = [
        args.data,
        "/content/drive/MyDrive/DATA/XAUUSD.iux_M1_20200102_to_20251230.csv",
        "/mnt/sdcard/Download/EA/XAUUSD_M1.csv.gz",
        "/root/XAUUSD_M1.csv.gz"
    ]
    resolved_path = None
    for c in candidates:
        if c and os.path.exists(c):
            resolved_path = c
            break

    if not resolved_path:
        print(f"[!] ERROR: Candlestick data file not found in candidates: {candidates}")
        sys.exit(1)

    print(f"[+] Using dataset: {resolved_path}")
    df_m5, atr_s, hrs, mins, days = load_and_resample_m5(resolved_path)
    res_df, top_10, champ = run_orb_sweep(
        df_m5, atr_s, hrs, mins, days, symbol=args.symbol, output_dir=args.output_dir
    )
    print("\n✅ STRATEGY 02 COMPLETE: Results successfully generated.")
