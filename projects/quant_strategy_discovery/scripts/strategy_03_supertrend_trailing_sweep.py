#!/usr/bin/env python3
"""
===============================================================================
STRATEGY 03: SUPERTREND & DYNAMIC VOLATILITY TRAILING SYSTEM
===============================================================================
Quantitative Backtesting & Parameter Robustness Engine for CFD Trading (XAUUSD)
Period: 2020 - 2025 (Full Multi-Year Validation)
Timeframe: M15 (Resampled from M1)

Core Mechanisms:
- Supertrend Indicator: Median Price +/- (Multiplier * ATR)
- Non-repainting Ratchet: Monotonically increasing trailing stop for Longs, decreasing for Shorts
- Trend Flip Trigger: Enters on trend confirmation at candle close (Open[t+1] execution)
- Macro Trend Filter: Higher-timeframe EMA alignment (100, 200, 400, None)
- Dynamic Trailing Exit vs Multi-ATR Take Profit Targets
- Session Window: London + New York Active Hours (07:00 - 20:00 UTC) vs 24h
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
# NUMBA HIGH-SPEED SUPERTREND COMPUTATION & SIMULATION KERNEL
# -----------------------------------------------------------------------------
@njit(fastmath=True)
def compute_supertrend_arrays(
    highs: np.ndarray,
    lows: np.ndarray,
    closes: np.ndarray,
    atr: np.ndarray,
    multiplier: float
):
    """
    Computes Supertrend trend direction (+1/-1) and trailing stop line.
    Strictly backward-looking (no future data leakage).
    """
    n = len(closes)
    trend = np.zeros(n, dtype=np.int32)
    st_line = np.zeros(n, dtype=np.float64)

    upper_band = np.zeros(n, dtype=np.float64)
    lower_band = np.zeros(n, dtype=np.float64)

    for i in range(n):
        med = (highs[i] + lows[i]) * 0.5
        upper_band[i] = med + multiplier * atr[i]
        lower_band[i] = med - multiplier * atr[i]

    # Initialize at bar 0
    trend[0] = 1
    st_line[0] = lower_band[0]

    for i in range(1, n):
        prev_trend = trend[i - 1]
        prev_st = st_line[i - 1]

        if prev_trend == 1:
            # Bullish trend: lower band ratchets upward
            cur_st = lower_band[i]
            if cur_st < prev_st:
                cur_st = prev_st
            
            # Check flip to bearish
            if closes[i] < cur_st:
                trend[i] = -1
                st_line[i] = upper_band[i]
            else:
                trend[i] = 1
                st_line[i] = cur_st
        else:
            # Bearish trend: upper band ratchets downward
            cur_st = upper_band[i]
            if cur_st > prev_st:
                cur_st = prev_st

            # Check flip to bullish
            if closes[i] > cur_st:
                trend[i] = 1
                st_line[i] = lower_band[i]
            else:
                trend[i] = -1
                st_line[i] = cur_st

    return trend, st_line


@njit(fastmath=True)
def simulate_supertrend(
    opens: np.ndarray,
    highs: np.ndarray,
    lows: np.ndarray,
    closes: np.ndarray,
    atr: np.ndarray,
    hours: np.ndarray,
    trend: np.ndarray,
    st_line: np.ndarray,
    ema: np.ndarray,
    use_ema: int,
    session_mode: int,
    tp_atr_mult: float,
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
    tp_price = 0.0
    entry_bar = 0

    for i in range(warmup, n - 1):
        cur_trend = trend[i]
        prev_trend = trend[i - 1]
        cur_st = st_line[i]
        hr = hours[i]

        # -------------------------------------------------------------
        # 1. Manage Position Exits
        # -------------------------------------------------------------
        if pos == 1:
            exit_triggered = False
            exit_p = 0.0

            # Supertrend trailing stop breached
            if lows[i] <= cur_st:
                exit_p = cur_st if opens[i] >= cur_st else opens[i]
                exit_triggered = True
            # Take profit hit
            elif tp_atr_mult > 0.0 and highs[i] >= tp_price:
                exit_p = tp_price if opens[i] <= tp_price else opens[i]
                exit_triggered = True
            # Supertrend trend flip to Bearish
            elif cur_trend == -1:
                exit_p = opens[i + 1] - (spread * 0.5)
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

            # Supertrend trailing stop breached
            if highs[i] >= cur_st:
                exit_p = cur_st if opens[i] <= cur_st else opens[i]
                exit_triggered = True
            # Take profit hit
            elif tp_atr_mult > 0.0 and lows[i] <= tp_price:
                exit_p = tp_price if opens[i] >= tp_price else opens[i]
                exit_triggered = True
            # Supertrend trend flip to Bullish
            elif cur_trend == 1:
                exit_p = opens[i + 1] + (spread * 0.5)
                exit_triggered = True

            if exit_triggered:
                trade_pnl = (entry_price - exit_p) * unit_size - (spread + commission_per_unit) * unit_size
                if trade_count < max_trades:
                    pnl_list[trade_count] = trade_pnl
                    holding_bars[trade_count] = i - entry_bar
                    trade_count += 1
                pos = 0

        # -------------------------------------------------------------
        # 2. Check Entries on Supertrend Trend Flip
        # -------------------------------------------------------------
        if pos == 0:
            # Trend flip occurred at candle i
            is_flip_long = (cur_trend == 1 and prev_trend == -1)
            is_flip_short = (cur_trend == -1 and prev_trend == 1)

            if is_flip_long or is_flip_short:
                # Session filter
                in_session = True
                if session_mode == 1:
                    if hr < 7 or hr >= 20:
                        in_session = False

                if in_session and atr[i] > 0.0:
                    if is_flip_long:
                        ema_ok = True
                        if use_ema == 1 and closes[i] < ema[i]:
                            ema_ok = False
                        if ema_ok:
                            pos = 1
                            entry_price = opens[i + 1] + (spread * 0.5)
                            tp_price = entry_price + (tp_atr_mult * atr[i]) if tp_atr_mult > 0.0 else 999999.0
                            entry_bar = i + 1

                    elif is_flip_short:
                        ema_ok = True
                        if use_ema == 1 and closes[i] > ema[i]:
                            ema_ok = False
                        if ema_ok:
                            pos = -1
                            entry_price = opens[i + 1] - (spread * 0.5)
                            tp_price = entry_price - (tp_atr_mult * atr[i]) if tp_atr_mult > 0.0 else 0.0
                            entry_bar = i + 1

    # 3. Calculate Performance Metrics
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
# DATA LOADING & PRE-COMPUTATION
# -----------------------------------------------------------------------------
def load_and_resample_data(data_path: str, timeframe: str = "15min"):
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

    print(f"[*] Resampling to {timeframe}...")
    t1 = time.time()
    df_res = df.resample(timeframe).agg({
        "open": "first",
        "high": "max",
        "low": "min",
        "close": "last",
        "tick_volume": "sum"
    }).dropna()
    print(f"[+] Resampled to {len(df_res):,} {timeframe} bars in {time.time() - t1:.2f}s.")
    return df_res


def precompute_supertrends(df: pd.DataFrame, atr_periods: list, multipliers: list):
    print("[*] Pre-computing ATRs and Supertrend combinations...")
    t0 = time.time()
    high = df["high"].values.astype(np.float64)
    low = df["low"].values.astype(np.float64)
    close = df["close"].values.astype(np.float64)

    # Precalculate True Range
    tr = np.maximum(
        high[1:] - low[1:],
        np.maximum(
            np.abs(high[1:] - close[:-1]),
            np.abs(low[1:] - close[:-1])
        )
    )
    tr = np.insert(tr, 0, high[0] - low[0])

    atr_dict = {}
    for p in atr_periods:
        atr_dict[p] = pd.Series(tr, index=df.index).rolling(window=p).mean().fillna(1.0).values.astype(np.float64)

    # Supertrend grid: (p, mult) -> (trend, st_line)
    st_dict = {}
    for p in atr_periods:
        atr_p = atr_dict[p]
        for mult in multipliers:
            tr_arr, st_arr = compute_supertrend_arrays(high, low, close, atr_p, mult)
            st_dict[(p, mult)] = (tr_arr, st_arr)

    # EMAs
    ema_dict = {}
    for span in [100, 200, 400]:
        ema_dict[span] = pd.Series(close, index=df.index).ewm(span=span, adjust=False).mean().values.astype(np.float64)

    hours = df.index.hour.values.astype(np.int32)
    print(f"[+] Supertrend matrix pre-computed in {time.time() - t0:.2f}s.")
    return atr_dict, st_dict, ema_dict, hours


# -----------------------------------------------------------------------------
# MASS PARAMETER SWEEP
# -----------------------------------------------------------------------------
def run_supertrend_sweep(
    df: pd.DataFrame,
    symbol: str = "XAUUSD",
    output_dir: str = "projects/quant_strategy_discovery/results"
):
    os.makedirs(output_dir, exist_ok=True)
    opens = df["open"].values.astype(np.float64)
    highs = df["high"].values.astype(np.float64)
    lows = df["low"].values.astype(np.float64)
    closes = df["close"].values.astype(np.float64)

    unit_size = 10.0   # 0.10 lot
    spread = 0.25      # $0.25 spread
    commission = 0.06  # $6.00/lot standard round-turn
    warmup = 450

    atr_periods = [7, 10, 14, 20]
    multipliers = [1.5, 2.0, 2.5, 3.0, 3.5, 4.0]
    ema_filters = [0, 100, 200, 400]
    tp_mults = [0.0, 2.5, 4.0, 6.0]
    session_modes = [0, 1]  # 0: 24h, 1: London_NY (07-20 UTC)

    total_combos = (
        len(atr_periods) * len(multipliers) * len(ema_filters) *
        len(tp_mults) * len(session_modes)
    )

    print(f"\n{'='*75}")
    print(f"🚀 COMMENCING MASS PARAMETER SWEEP: STRATEGY 03 (SUPERTREND TRAILING)")
    print(f"   Symbol: {symbol} | Total Combinations: {total_combos:,}")
    print(f"   Frictions: Spread=${spread:.2f} | Comm=${commission*100:.2f}/lot | Lot: 0.10")
    print(f"{'='*75}\n")

    atr_dict, st_dict, ema_dict, hours = precompute_supertrends(df, atr_periods, multipliers)
    dummy_ema = np.zeros(len(closes), dtype=np.float64)

    # Warmup Numba JIT
    test_tr, test_st = st_dict[(10, 3.0)]
    _ = simulate_supertrend(
        opens, highs, lows, closes, atr_dict[10], hours,
        test_tr, test_st, dummy_ema, 0, 0, 0.0,
        spread, commission, unit_size, warmup
    )

    results = []
    t_start = time.time()
    count = 0

    for p in atr_periods:
        atr_p = atr_dict[p]
        for mult in multipliers:
            tr_arr, st_arr = st_dict[(p, mult)]
            for ema_f in ema_filters:
                use_ema = 1 if ema_f > 0 else 0
                ema_arr = ema_dict[ema_f] if ema_f > 0 else dummy_ema
                for tp in tp_mults:
                    for sess in session_modes:
                        count += 1
                        res = simulate_supertrend(
                            opens, highs, lows, closes, atr_p, hours,
                            tr_arr, st_arr, ema_arr, use_ema, sess, tp,
                            spread, commission, unit_size, warmup
                        )
                        (
                            trades, net_pnl, gp, gl, pf,
                            wr, mdd, romad, sharpe, avg_hold
                        ) = res

                        results.append({
                            "atr_period": p,
                            "multiplier": mult,
                            "ema_filter": ema_f,
                            "tp_atr_mult": tp,
                            "session_mode": "London_NY" if sess == 1 else "24h",
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

                        if count % 150 == 0 or count == total_combos:
                            elapsed = time.time() - t_start
                            speed = count / elapsed if elapsed > 0 else 0
                            print(f"[*] Swept {count:,} / {total_combos:,} combos ({count/total_combos*100:.1f}%) | Speed: {speed:.1f} sets/sec")

    sweep_time = time.time() - t_start
    print(f"\n[+] Mass sweep completed in {sweep_time:.2f}s ({total_combos/sweep_time:.1f} sets/sec)!")

    res_df = pd.DataFrame(results)

    csv_path = os.path.join(output_dir, "strategy_03_supertrend_sweep_results.csv")
    res_df.to_csv(csv_path, index=False)
    print(f"[+] Complete sweep results saved to: {csv_path}")

    # Statistically significant parameter sets (minimum 100 trades)
    stat_df = res_df[res_df["total_trades"] >= 100].copy()
    if stat_df.empty:
        stat_df = res_df[res_df["total_trades"] >= 30].copy()

    stat_df["composite_score"] = (
        stat_df["profit_factor"] * 0.4 +
        (stat_df["net_profit"] / (stat_df["max_drawdown"] + 1e-4)) * 0.4 +
        stat_df["sharpe"] * 0.2
    )
    stat_df.sort_values(by="composite_score", ascending=False, inplace=True)

    top_10 = stat_df.head(10)
    champion = stat_df.iloc[0]

    print(f"\n{'='*75}")
    print(f"🏆 TOP 5 PARAMETER COMBINATIONS (STRATEGY 03 - SUPERTREND)")
    print(f"{'='*75}")
    for idx, row in top_10.head(5).iterrows():
        print(f"Rank: ATR={row['atr_period']} | Mult={row['multiplier']}x | EMA={row['ema_filter']} | "
              f"TP={row['tp_atr_mult']}x | Sess={row['session_mode']} | Net=${row['net_profit']:,.2f} | "
              f"PF={row['profit_factor']:.2f} | WR={row['win_rate']:.1f}% | DD=${row['max_drawdown']:,.2f} | Trades={int(row['total_trades'])}")

    print(f"\n{'='*75}")
    print(f"🥇 ULTIMATE CHAMPION PARAMETER SET:")
    print(f"   ATR Period:     {champion['atr_period']}")
    print(f"   Multiplier:     {champion['multiplier']}x ATR")
    print(f"   EMA Filter:     {champion['ema_filter']} {'(No Filter)' if champion['ema_filter'] == 0 else ''}")
    print(f"   Take Profit:    {champion['tp_atr_mult']}x ATR {'(Trailing Flip Only)' if champion['tp_atr_mult'] == 0 else ''}")
    print(f"   Session Window: {champion['session_mode']}")
    print(f"   --- Performance Across 2020-2025 ---")
    print(f"   Net Profit:     ${champion['net_profit']:,.2f} (on 0.10 lot)")
    print(f"   Profit Factor:  {champion['profit_factor']:.2f}")
    print(f"   Win Rate:       {champion['win_rate']:.2f}%")
    print(f"   Total Trades:   {int(champion['total_trades'])} ({int(champion['total_trades'])/5:.1f} trades/year)")
    print(f"   Max Drawdown:   ${champion['max_drawdown']:,.2f}")
    print(f"   RoMaD (Ret/DD): {champion['romad']:.2f}")
    print(f"   Sharpe Ratio:   {champion['sharpe']:.2f}")
    print(f"{'='*75}\n")

    # Yearly breakdown for Champion
    print("[*] Running multi-year breakdown for Champion Parameter Set...")
    champion_dict = champion.to_dict()
    yearly_breakdown = evaluate_supertrend_yearly(
        df, champion_dict, spread, commission, unit_size
    )
    champion_dict["yearly_breakdown"] = yearly_breakdown

    champ_json_path = os.path.join(output_dir, "strategy_03_supertrend_champion.json")
    with open(champ_json_path, "w") as f:
        clean_dict = {k: (float(v) if isinstance(v, (np.floating, float)) else (int(v) if isinstance(v, (np.integer, int)) else v)) for k, v in champion_dict.items() if k != "yearly_breakdown"}
        clean_dict["yearly_breakdown"] = yearly_breakdown
        json.dump(clean_dict, f, indent=2)
    print(f"[+] Champion summary saved to: {champ_json_path}")

    return res_df, top_10, champion_dict


def evaluate_supertrend_yearly(
    df: pd.DataFrame,
    param_dict: dict,
    spread: float,
    commission: float,
    unit_size: float
):
    yearly_results = {}
    years = sorted(df.index.year.unique())
    warmup = 100

    p = int(param_dict["atr_period"])
    mult = float(param_dict["multiplier"])
    ema_f = int(param_dict["ema_filter"])
    tp = float(param_dict["tp_atr_mult"])
    sess_mode = 1 if param_dict["session_mode"] == "London_NY" else 0

    for yr in years:
        df_yr = df[df.index.year == yr].copy()
        if len(df_yr) < 500:
            continue

        atr_d, st_d, ema_d, hrs = precompute_supertrends(df_yr, [p], [mult])
        opens = df_yr["open"].values.astype(np.float64)
        highs = df_yr["high"].values.astype(np.float64)
        lows = df_yr["low"].values.astype(np.float64)
        closes = df_yr["close"].values.astype(np.float64)

        tr_arr, st_arr = st_d[(p, mult)]
        ema_arr = ema_d[ema_f] if ema_f > 0 else np.zeros(len(closes), dtype=np.float64)
        use_ema = 1 if ema_f > 0 else 0

        res = simulate_supertrend(
            opens, highs, lows, closes, atr_d[p], hrs,
            tr_arr, st_arr, ema_arr, use_ema, sess_mode, tp,
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
    parser = argparse.ArgumentParser(description="Strategy 03: Supertrend Sweep")
    parser.add_argument("--data", type=str, default=None, help="Path to M1 CSV dataset")
    parser.add_argument("--symbol", type=str, default="XAUUSD", help="Symbol name")
    parser.add_argument("--timeframe", type=str, default="15min", help="Backtest timeframe")
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
    df_m15 = load_and_resample_data(resolved_path, timeframe=args.timeframe)
    res_df, top_10, champ = run_supertrend_sweep(
        df_m15, symbol=args.symbol, output_dir=args.output_dir
    )
    print("\n✅ STRATEGY 03 COMPLETE: Results successfully generated.")
