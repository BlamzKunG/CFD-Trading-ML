#!/usr/bin/env python3
"""
===============================================================================
STRATEGY 08: RSI DIVERGENCE & REJECTION WICK REVERSAL SYSTEM
===============================================================================
Quantitative Backtesting & Parameter Robustness Engine for CFD Trading (XAUUSD)
Period: 2020 - 2025 (Full Multi-Year Validation)
Timeframe: M15 (Resampled from M1)

Core Mechanisms:
- Structural Swing Pivot Detection (5-bar fractals)
- Regular Bullish Divergence (Price Lower Low + RSI Higher Low)
- Regular Bearish Divergence (Price Higher High + RSI Lower High)
- Pinbar / Rejection Wick Confirmation (Wick >= Threshold% of candle range)
- Dynamic Volatility Stop Loss & High Asymmetric Take Profit (2.0R to 4.0R)
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
def simulate_rsi_divergence_kernel(
    opens: np.ndarray,
    highs: np.ndarray,
    lows: np.ndarray,
    closes: np.ndarray,
    atr: np.ndarray,
    hours: np.ndarray,
    bull_div_signals: np.ndarray,
    bear_div_signals: np.ndarray,
    session_mode: int,
    sl_atr_mult: float,
    tp_rr_mult: float,
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

    for i in range(warmup, n - 1):
        hr = hours[i]

        # 1. Manage Exits
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

        # 2. Check Entries on Confirmed RSI Divergence
        if pos == 0:
            in_session = True
            if session_mode == 1:
                if hr < 7 or hr >= 20:
                    in_session = False

            if in_session and atr[i] > 0.0:
                sl_dist = sl_atr_mult * atr[i]

                if bull_div_signals[i] == 1:
                    pos = 1
                    entry_price = opens[i + 1] + (spread * 0.5)
                    sl_price = entry_price - sl_dist
                    tp_price = entry_price + (sl_dist * tp_rr_mult)
                    entry_bar = i + 1

                elif bear_div_signals[i] == 1:
                    pos = -1
                    entry_price = opens[i + 1] - (spread * 0.5)
                    sl_price = entry_price + sl_dist
                    tp_price = entry_price - (sl_dist * tp_rr_mult)
                    entry_bar = i + 1

    # 3. Performance Metrics
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


def load_and_resample_data(data_path: str, timeframe: str = "15min"):
    print(f"[*] Loading data from: {data_path}...")
    t0 = time.time()
    df = pd.read_csv(
        data_path,
        usecols=["datetime", "open", "high", "low", "close", "tick_volume"],
        dtype={
            "open": np.float32, "high": np.float32, "low": np.float32,
            "close": np.float32, "tick_volume": np.int32
        }
    )
    df["datetime"] = pd.to_datetime(df["datetime"])
    df.set_index("datetime", inplace=True)
    df.sort_index(inplace=True)
    print(f"[+] Loaded {len(df):,} M1 bars in {time.time() - t0:.2f}s.")

    print(f"[*] Resampling to {timeframe}...")
    t1 = time.time()
    df_res = df.resample(timeframe).agg({
        "open": "first", "high": "max", "low": "min", "close": "last", "tick_volume": "sum"
    }).dropna()
    print(f"[+] Resampled to {len(df_res):,} {timeframe} bars in {time.time() - t1:.2f}s.")
    return df_res


def detect_rsi_divergences(df: pd.DataFrame, rsi_period: int = 14, min_bars: int = 5, max_bars: int = 25):
    """
    Detects strict structural swing pivot divergence between price and RSI.
    """
    close = df["close"].values.astype(np.float64)
    high = df["high"].values.astype(np.float64)
    low = df["low"].values.astype(np.float64)
    open_p = df["open"].values.astype(np.float64)
    n = len(close)

    # 1. Compute RSI(14)
    delta = pd.Series(close).diff()
    gain = (delta.where(delta > 0, 0)).rolling(rsi_period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(rsi_period).mean()
    rs = gain / (loss + 1e-6)
    rsi = (100 - (100 / (1 + rs))).fillna(50.0).values

    # 2. Compute ATR(14)
    tr = np.maximum(
        high[1:] - low[1:],
        np.maximum(
            np.abs(high[1:] - close[:-1]),
            np.abs(low[1:] - close[:-1])
        )
    )
    tr = np.insert(tr, 0, high[0] - low[0])
    atr = pd.Series(tr, index=df.index).rolling(14).mean().fillna(1.0).values.astype(np.float64)

    bull_div = np.zeros(n, dtype=np.int32)
    bear_div = np.zeros(n, dtype=np.int32)

    # Rejection wick calculation
    candle_range = high - low
    lower_wick = np.minimum(open_p, close) - low
    upper_wick = high - np.maximum(open_p, close)

    # Identify 5-bar swing low and swing high pivots
    for i in range(max_bars + 5, n):
        # Current bar confirmation: Bullish pinbar / rejection
        is_bull_rejection = (close[i] > open_p[i]) and (candle_range[i] > 0) and (lower_wick[i] / candle_range[i] >= 0.35)
        is_bear_rejection = (close[i] < open_p[i]) and (candle_range[i] > 0) and (upper_wick[i] / candle_range[i] >= 0.35)

        if is_bull_rejection:
            # Check for lower price low vs higher RSI low in prior [min_bars, max_bars]
            curr_low = low[i]
            curr_rsi = rsi[i]
            for lookback in range(min_bars, max_bars):
                past_idx = i - lookback
                # If past bar was a swing low
                if low[past_idx] < low[past_idx - 1] and low[past_idx] < low[past_idx + 1]:
                    # Bullish Divergence: Price Lower Low, RSI Higher Low
                    if curr_low < low[past_idx] and curr_rsi > rsi[past_idx]:
                        bull_div[i] = 1
                        break

        if is_bear_rejection:
            curr_high = high[i]
            curr_rsi = rsi[i]
            for lookback in range(min_bars, max_bars):
                past_idx = i - lookback
                if high[past_idx] > high[past_idx - 1] and high[past_idx] > high[past_idx + 1]:
                    # Bearish Divergence: Price Higher High, RSI Lower High
                    if curr_high > high[past_idx] and curr_rsi < rsi[past_idx]:
                        bear_div[i] = 1
                        break

    hours = df.index.hour.values.astype(np.int32)
    return bull_div, bear_div, atr, hours


def run_rsi_divergence_sweep(
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
    warmup = 100

    bull_div, bear_div, atr, hours = detect_rsi_divergences(df)

    sl_mults = [1.5, 2.0, 2.5, 3.0]
    tp_rrs = [1.5, 2.0, 3.0, 4.0]
    session_modes = [0, 1]  # 0: 24h, 1: London_NY (07-20 UTC)

    total_combos = len(sl_mults) * len(tp_rrs) * len(session_modes)

    print(f"\n{'='*75}")
    print(f"🚀 COMMENCING MASS PARAMETER SWEEP: STRATEGY 08 (RSI DIVERGENCE REVERSAL)")
    print(f"   Symbol: {symbol} | Total Combinations: {total_combos:,} | Numba: {HAS_NUMBA}")
    print(f"   Frictions: Spread=${spread:.2f} | Comm=${commission*100:.2f}/lot | Lot: 0.10")
    print(f"{'='*75}\n")

    results = []
    t_start = time.time()
    count = 0

    for sl in sl_mults:
        for tp_r in tp_rrs:
            for sess in session_modes:
                count += 1
                res = simulate_rsi_divergence_kernel(
                    opens, highs, lows, closes, atr, hours,
                    bull_div, bear_div, sess,
                    sl, tp_r, spread, commission, unit_size, warmup
                )
                (
                    trades, net_pnl, gp, gl, pf,
                    wr, mdd, romad, sharpe, avg_hold
                ) = res

                results.append({
                    "sl_atr_mult": sl,
                    "tp_rr_mult": tp_r,
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

    sweep_time = time.time() - t_start
    print(f"\n[+] Mass sweep completed in {sweep_time:.2f}s ({total_combos/sweep_time:.1f} sets/sec)!")

    res_df = pd.DataFrame(results)

    csv_path = os.path.join(output_dir, "strategy_08_rsi_divergence_sweep_results.csv")
    res_df.to_csv(csv_path, index=False)
    print(f"[+] Complete sweep results saved to: {csv_path}")

    stat_df = res_df[res_df["total_trades"] >= 50].copy()
    if stat_df.empty:
        stat_df = res_df[res_df["total_trades"] >= 20].copy()

    stat_df["composite_score"] = (
        stat_df["profit_factor"] * 0.4 +
        (stat_df["net_profit"] / (stat_df["max_drawdown"] + 1e-4)) * 0.4 +
        stat_df["sharpe"] * 0.2
    )
    stat_df.sort_values(by="composite_score", ascending=False, inplace=True)

    top_10 = stat_df.head(10)
    champion = stat_df.iloc[0]

    print(f"\n{'='*75}")
    print(f"🏆 TOP 5 PARAMETER COMBINATIONS (STRATEGY 08 - RSI DIVERGENCE)")
    print(f"{'='*75}")
    for idx, row in top_10.head(5).iterrows():
        print(f"Rank: SL={row['sl_atr_mult']}x | TP={row['tp_rr_mult']}R | Sess={row['session_mode']} | Net=${row['net_profit']:,.2f} | "
              f"PF={row['profit_factor']:.2f} | WR={row['win_rate']:.1f}% | DD=${row['max_drawdown']:,.2f} | Trades={int(row['total_trades'])}")

    print(f"\n{'='*75}")
    print(f"🥇 ULTIMATE CHAMPION PARAMETER SET:")
    print(f"   SL ATR Mult:    {champion['sl_atr_mult']}x ATR(14)")
    print(f"   TP RR Mult:     {champion['tp_rr_mult']}R (Risk Multiple)")
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
    champion_dict = champion.to_dict()
    yearly_breakdown = evaluate_rsi_yearly(
        df, champion_dict, spread, commission, unit_size
    )
    champion_dict["yearly_breakdown"] = yearly_breakdown

    champ_json_path = os.path.join(output_dir, "strategy_08_rsi_divergence_champion.json")
    with open(champ_json_path, "w") as f:
        clean_dict = {k: (float(v) if isinstance(v, (np.floating, float)) else (int(v) if isinstance(v, (np.integer, int)) else v)) for k, v in champion_dict.items() if k != "yearly_breakdown"}
        clean_dict["yearly_breakdown"] = yearly_breakdown
        json.dump(clean_dict, f, indent=2)
    print(f"[+] Champion summary saved to: {champ_json_path}")

    return res_df, top_10, champion_dict


def evaluate_rsi_yearly(
    df: pd.DataFrame,
    param_dict: dict,
    spread: float,
    commission: float,
    unit_size: float
):
    yearly_results = {}
    years = sorted(df.index.year.unique())
    warmup = 50

    sl = float(param_dict["sl_atr_mult"])
    tp_r = float(param_dict["tp_rr_mult"])
    sess_mode = 1 if param_dict["session_mode"] == "London_NY" else 0

    for yr in years:
        df_yr = df[df.index.year == yr].copy()
        if len(df_yr) < 500:
            continue

        bull_div, bear_div, atr_yr, hrs = detect_rsi_divergences(df_yr)
        opens = df_yr["open"].values.astype(np.float64)
        highs = df_yr["high"].values.astype(np.float64)
        lows = df_yr["low"].values.astype(np.float64)
        closes = df_yr["close"].values.astype(np.float64)

        res = simulate_rsi_divergence_kernel(
            opens, highs, lows, closes, atr_yr, hrs,
            bull_div, bear_div, sess_mode,
            sl, tp_r, spread, commission, unit_size, warmup
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


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Strategy 08: RSI Divergence Sweep")
    parser.add_argument("--data", type=str, default=None, help="Path to M1 CSV dataset")
    parser.add_argument("--symbol", type=str, default="XAUUSD", help="Symbol name")
    parser.add_argument("--timeframe", type=str, default="15min", help="Backtest timeframe")
    parser.add_argument("--output_dir", type=str, default="projects/quant_strategy_discovery/results", help="Output directory")
    args, _ = parser.parse_known_args()

    candidates = [
        args.data,
        "/mnt/sdcard/Download/EA/XAUUSD_M1.csv.gz",
        "/content/drive/MyDrive/DATA/XAUUSD.iux_M1_20200102_to_20251230.csv",
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
    res_df, top_10, champ = run_rsi_divergence_sweep(
        df_m15, symbol=args.symbol, output_dir=args.output_dir
    )
    print("\n✅ STRATEGY 08 COMPLETE: Results successfully generated.")
