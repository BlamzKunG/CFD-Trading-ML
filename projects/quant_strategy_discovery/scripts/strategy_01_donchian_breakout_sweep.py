#!/usr/bin/env python3
"""
===============================================================================
STRATEGY 01: DONCHIAN / TURTLE BREAKOUT MASS PARAMETER SWEEP
===============================================================================
Quantitative Backtesting & Parameter Robustness Engine for CFD Trading (XAUUSD)
Period: 2020 - 2025 (Full Multi-Year Validation)
Timeframe: M15 (Resampled from M1)

Core Mechanisms:
- Entry: Breakout of N-period Highest High (Long) / Lowest Low (Short)
- Trend Filter: Exponential Moving Average (EMA 100 / 200 / None)
- Dynamic Exit: M-period Donchian Exit Channel (Turtle Trailing) OR ATR Multiple
- Stop Loss: Volatility-based ATR Stop Loss
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
# NUMBA HIGH-SPEED SIMULATION KERNEL
# -----------------------------------------------------------------------------
@njit(fastmath=True)
def simulate_donchian(
    opens: np.ndarray,
    highs: np.ndarray,
    lows: np.ndarray,
    closes: np.ndarray,
    atr: np.ndarray,
    hours: np.ndarray,
    upper_entry: np.ndarray,
    lower_entry: np.ndarray,
    upper_exit: np.ndarray,
    lower_exit: np.ndarray,
    ema: np.ndarray,
    use_ema: int,
    session_mode: int,
    sl_atr_mult: float,
    tp_atr_mult: float,
    spread: float,
    commission_per_unit: float,
    unit_size: float,
    warmup: int
):
    """
    Ultra-fast bar-by-bar backtest kernel with zero lookahead bias.
    Orders placed at Open[t+1] following breakout at bar t.
    """
    n = len(closes)
    # Pre-allocate trade buffer
    max_trades = 20000
    pnl_list = np.zeros(max_trades, dtype=np.float64)
    holding_bars = np.zeros(max_trades, dtype=np.int32)
    trade_count = 0

    pos = 0  # 0: flat, 1: long, -1: short
    entry_price = 0.0
    sl_price = 0.0
    tp_price = 0.0
    entry_bar = 0

    for i in range(warmup, n - 1):
        # 1. Check open position exit triggers on current bar i
        if pos == 1:
            exit_triggered = False
            exit_p = 0.0

            # Stop Loss Trigger (checked first for risk preservation)
            if lows[i] <= sl_price:
                exit_p = sl_price if opens[i] >= sl_price else opens[i]  # Gap slippage
                exit_triggered = True
            # Take Profit Trigger (if enabled)
            elif tp_atr_mult > 0.0 and highs[i] >= tp_price:
                exit_p = tp_price if opens[i] <= tp_price else opens[i]
                exit_triggered = True
            # Donchian Exit Channel Trigger (Turtle trailing exit)
            elif lows[i] <= lower_exit[i]:
                exit_p = lower_exit[i] if opens[i] >= lower_exit[i] else opens[i]
                exit_triggered = True

            if exit_triggered:
                # Long PnL = (exit_p - entry_price) * units - friction
                trade_pnl = (exit_p - entry_price) * unit_size - (spread + commission_per_unit) * unit_size
                if trade_count < max_trades:
                    pnl_list[trade_count] = trade_pnl
                    holding_bars[trade_count] = i - entry_bar
                    trade_count += 1
                pos = 0

        elif pos == -1:
            exit_triggered = False
            exit_p = 0.0

            # Stop Loss Trigger
            if highs[i] >= sl_price:
                exit_p = sl_price if opens[i] <= sl_price else opens[i]
                exit_triggered = True
            # Take Profit Trigger
            elif tp_atr_mult > 0.0 and lows[i] <= tp_price:
                exit_p = tp_price if opens[i] >= tp_price else opens[i]
                exit_triggered = True
            # Donchian Exit Channel Trigger
            elif highs[i] >= upper_exit[i]:
                exit_p = upper_exit[i] if opens[i] <= upper_exit[i] else opens[i]
                exit_triggered = True

            if exit_triggered:
                # Short PnL = (entry_price - exit_p) * units - friction
                trade_pnl = (entry_price - exit_p) * unit_size - (spread + commission_per_unit) * unit_size
                if trade_count < max_trades:
                    pnl_list[trade_count] = trade_pnl
                    holding_bars[trade_count] = i - entry_bar
                    trade_count += 1
                pos = 0

        # 2. Check new entry signals at close of bar i (executed at Open[i+1])
        if pos == 0:
            # Session filter check
            hour = hours[i]
            in_session = True
            if session_mode == 1:
                # London & NY prime window: 07:00 to 20:00 UTC
                if hour < 7 or hour >= 20:
                    in_session = False

            if in_session and atr[i] > 0.0:
                # Long Breakout Condition: Close > prior N-bar High
                if closes[i] > upper_entry[i]:
                    ema_ok = True
                    if use_ema == 1 and closes[i] < ema[i]:
                        ema_ok = False

                    if ema_ok:
                        pos = 1
                        entry_price = opens[i + 1] + (spread * 0.5)
                        sl_price = entry_price - (sl_atr_mult * atr[i])
                        tp_price = entry_price + (tp_atr_mult * atr[i]) if tp_atr_mult > 0.0 else 999999.0
                        entry_bar = i + 1

                # Short Breakout Condition: Close < prior N-bar Low
                elif closes[i] < lower_entry[i]:
                    ema_ok = True
                    if use_ema == 1 and closes[i] > ema[i]:
                        ema_ok = False

                    if ema_ok:
                        pos = -1
                        entry_price = opens[i + 1] - (spread * 0.5)
                        sl_price = entry_price + (sl_atr_mult * atr[i])
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

    # Sharpe ratio
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
# DATA LOADING & TIMEFRAME PREPARATION
# -----------------------------------------------------------------------------
def load_and_resample_data(data_path: str, timeframe: str = "15min"):
    """
    Loads M1 data and resamples to target timeframe (e.g., M15).
    """
    print(f"[*] Loading data from: {data_path}...")
    t0 = time.time()
    
    # Read CSV with optimized dtypes
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

    # Resample to M15
    print(f"[*] Resampling to {timeframe}...")
    t1 = time.time()
    ohlc_dict = {
        "open": "first",
        "high": "max",
        "low": "min",
        "close": "last",
        "tick_volume": "sum"
    }
    df_resampled = df.resample(timeframe).agg(ohlc_dict).dropna()
    print(f"[+] Resampled to {len(df_resampled):,} {timeframe} bars in {time.time() - t1:.2f}s.")
    return df_resampled


def compute_pre_indicators(df: pd.DataFrame):
    """
    Precomputes ATR, EMAs, and Donchian channels for all lookback values.
    Shifted by 1 bar to eliminate lookahead bias!
    """
    print("[*] Pre-computing indicator matrix across all parameter ranges...")
    t0 = time.time()
    high = df["high"].values.astype(np.float64)
    low = df["low"].values.astype(np.float64)
    close = df["close"].values.astype(np.float64)

    # 1. ATR(14)
    tr = np.maximum(
        high[1:] - low[1:],
        np.maximum(
            np.abs(high[1:] - close[:-1]),
            np.abs(low[1:] - close[:-1])
        )
    )
    tr = np.insert(tr, 0, high[0] - low[0])
    atr_series = pd.Series(tr, index=df.index).rolling(window=14).mean().fillna(1.0).values.astype(np.float64)

    # 2. EMAs
    ema_dict = {}
    for span in [100, 200]:
        ema_series = pd.Series(close, index=df.index).ewm(span=span, adjust=False).mean().values.astype(np.float64)
        ema_dict[span] = ema_series

    # 3. Donchian Entry Channels (Shifted by 1)
    entry_lookbacks = [15, 20, 30, 45, 60, 90]
    donchian_entry_upper = {}
    donchian_entry_lower = {}
    for lb in entry_lookbacks:
        # Shift 1: Bar t can only look at bars t-lb to t-1
        u = pd.Series(high, index=df.index).shift(1).rolling(window=lb).max().fillna(999999.0).values.astype(np.float64)
        l = pd.Series(low, index=df.index).shift(1).rolling(window=lb).min().fillna(0.0).values.astype(np.float64)
        donchian_entry_upper[lb] = u
        donchian_entry_lower[lb] = l

    # 4. Donchian Exit Channels (Shifted by 1)
    exit_lookbacks = [5, 10, 15, 20]
    donchian_exit_upper = {}
    donchian_exit_lower = {}
    for lb in exit_lookbacks:
        u = pd.Series(high, index=df.index).shift(1).rolling(window=lb).max().fillna(999999.0).values.astype(np.float64)
        l = pd.Series(low, index=df.index).shift(1).rolling(window=lb).min().fillna(0.0).values.astype(np.float64)
        donchian_exit_upper[lb] = u
        donchian_exit_lower[lb] = l

    hours = df.index.hour.values.astype(np.int32)

    print(f"[+] Indicators pre-computed in {time.time() - t0:.2f}s.")
    return (
        atr_series,
        hours,
        ema_dict,
        donchian_entry_upper,
        donchian_entry_lower,
        donchian_exit_upper,
        donchian_exit_lower
    )


# -----------------------------------------------------------------------------
# MASS PARAMETER SWEEP ORCHESTRATION
# -----------------------------------------------------------------------------
def run_mass_parameter_sweep(
    df: pd.DataFrame,
    symbol: str = "XAUUSD",
    output_dir: str = "projects/quant_strategy_discovery/results"
):
    os.makedirs(output_dir, exist_ok=True)
    opens = df["open"].values.astype(np.float64)
    highs = df["high"].values.astype(np.float64)
    lows = df["low"].values.astype(np.float64)
    closes = df["close"].values.astype(np.float64)

    (
        atr_series,
        hours,
        ema_dict,
        donchian_entry_upper,
        donchian_entry_lower,
        donchian_exit_upper,
        donchian_exit_lower
    ) = compute_pre_indicators(df)

    # CFD Frictions (0.10 standard lot = 10 oz for gold)
    unit_size = 10.0  # 0.10 lot
    spread = 0.25     # $0.25 spread ($2.50 per 0.1 lot)
    commission = 0.06 # $0.06/oz = $0.60 per 0.1 lot ($6.00/lot standard)

    # Parameter Grids
    entry_lbs = [15, 20, 30, 45, 60, 90]
    exit_lbs = [5, 10, 15, 20]
    sl_mults = [1.5, 2.0, 2.5, 3.0]
    tp_mults = [0.0, 3.0, 5.0]  # 0.0 = Trailing Donchian exit only
    ema_filters = [0, 100, 200]
    session_modes = [0, 1]  # 0: 24h, 1: London+NY (07-20 UTC)

    total_combos = (
        len(entry_lbs) * len(exit_lbs) * len(sl_mults) *
        len(tp_mults) * len(ema_filters) * len(session_modes)
    )

    print(f"\n{'='*75}")
    print(f"🚀 COMMENCING MASS PARAMETER SWEEP: STRATEGY 01 (DONCHIAN BREAKOUT)")
    print(f"   Symbol: {symbol} | Total Combinations: {total_combos:,}")
    print(f"   Frictions: Spread=${spread:.2f} | Comm=${commission*100:.2f}/lot | Lot: 0.10")
    print(f"{'='*75}\n")

    results = []
    t_start = time.time()
    warmup = 250
    dummy_ema = np.zeros(len(closes), dtype=np.float64)

    # Warmup Numba compilation on first call
    _ = simulate_donchian(
        opens, highs, lows, closes, atr_series, hours,
        donchian_entry_upper[20], donchian_entry_lower[20],
        donchian_exit_upper[10], donchian_exit_lower[10],
        dummy_ema, 0, 0, 2.0, 0.0, spread, commission, unit_size, warmup
    )

    count = 0
    for e_lb in entry_lbs:
        u_entry = donchian_entry_upper[e_lb]
        l_entry = donchian_entry_lower[e_lb]
        for x_lb in exit_lbs:
            u_exit = donchian_exit_upper[x_lb]
            l_exit = donchian_exit_lower[x_lb]
            for sl in sl_mults:
                for tp in tp_mults:
                    for ema_f in ema_filters:
                        use_ema_flag = 1 if ema_f > 0 else 0
                        ema_arr = ema_dict[ema_f] if ema_f > 0 else dummy_ema
                        for sess in session_modes:
                            count += 1
                            res = simulate_donchian(
                                opens, highs, lows, closes, atr_series, hours,
                                u_entry, l_entry, u_exit, l_exit,
                                ema_arr, use_ema_flag, sess,
                                sl, tp, spread, commission, unit_size, warmup
                            )
                            (
                                trades, net_pnl, gp, gl, pf,
                                wr, mdd, romad, sharpe, avg_hold
                            ) = res

                            results.append({
                                "entry_lookback": e_lb,
                                "exit_lookback": x_lb,
                                "sl_atr_mult": sl,
                                "tp_atr_mult": tp,
                                "ema_filter": ema_f,
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

                            if count % 200 == 0 or count == total_combos:
                                elapsed = time.time() - t_start
                                speed = count / elapsed if elapsed > 0 else 0
                                print(f"[*] Swept {count:,} / {total_combos:,} combos ({count/total_combos*100:.1f}%) | Speed: {speed:.1f} sets/sec")

    sweep_time = time.time() - t_start
    print(f"\n[+] Mass sweep completed in {sweep_time:.2f}s ({total_combos/sweep_time:.1f} sets/sec)!")

    # Convert to DataFrame
    res_df = pd.DataFrame(results)

    # Save complete sweep results to CSV
    csv_path = os.path.join(output_dir, "strategy_01_donchian_sweep_results.csv")
    res_df.to_csv(csv_path, index=False)
    print(f"[+] Complete sweep results saved to: {csv_path}")

    # Filter statistically significant parameter sets (minimum 100 trades over 5 years)
    stat_df = res_df[res_df["total_trades"] >= 100].copy()
    if stat_df.empty:
        stat_df = res_df[res_df["total_trades"] >= 30].copy()

    # Sort by Profit Factor and Net Profit
    stat_df["composite_score"] = (
        stat_df["profit_factor"] * 0.4 +
        (stat_df["net_profit"] / (stat_df["max_drawdown"] + 1e-4)) * 0.4 +
        stat_df["sharpe"] * 0.2
    )
    stat_df.sort_values(by="composite_score", ascending=False, inplace=True)

    top_10 = stat_df.head(10)
    champion = stat_df.iloc[0]

    print(f"\n{'='*75}")
    print(f"🏆 TOP 5 PARAMETER COMBINATIONS (STRATEGY 01 - DONCHIAN BREAKOUT)")
    print(f"{'='*75}")
    for idx, row in top_10.head(5).iterrows():
        print(f"Rank {row.name + 1 if hasattr(row, 'name') else ''}: Entry LB={row['entry_lookback']} | Exit LB={row['exit_lookback']} | "
              f"SL={row['sl_atr_mult']}x | TP={row['tp_atr_mult']}x | EMA={row['ema_filter']} | "
              f"Sess={row['session_mode']} | Net=${row['net_profit']:,.2f} | PF={row['profit_factor']:.2f} | "
              f"WR={row['win_rate']:.1f}% | DD=${row['max_drawdown']:,.2f} | Trades={int(row['total_trades'])}")

    print(f"\n{'='*75}")
    print(f"🥇 ULTIMATE CHAMPION PARAMETER SET:")
    print(f"   Entry Lookback: {champion['entry_lookback']} bars (M15 = {champion['entry_lookback']*15/60:.1f} hours)")
    print(f"   Exit Lookback:  {champion['exit_lookback']} bars (M15 = {champion['exit_lookback']*15/60:.1f} hours)")
    print(f"   SL ATR Mult:    {champion['sl_atr_mult']}x ATR(14)")
    print(f"   TP ATR Mult:    {champion['tp_atr_mult']}x ATR(14) {'(Trailing Donchian)' if champion['tp_atr_mult'] == 0 else ''}")
    print(f"   EMA Filter:     {champion['ema_filter']} {'(No Filter)' if champion['ema_filter'] == 0 else ''}")
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

    # 4. Run Multi-Year Stability Check on Champion
    print("[*] Running multi-year breakdown for Champion Parameter Set...")
    champion_dict = champion.to_dict()
    yearly_breakdown = evaluate_yearly_consistency(
        df, champion_dict, spread, commission, unit_size
    )
    champion_dict["yearly_breakdown"] = yearly_breakdown

    # Save champion summary JSON
    champ_json_path = os.path.join(output_dir, "strategy_01_donchian_champion.json")
    with open(champ_json_path, "w") as f:
        # Convert numpy types to python natives
        clean_dict = {k: (float(v) if isinstance(v, (np.floating, float)) else (int(v) if isinstance(v, (np.integer, int)) else v)) for k, v in champion_dict.items() if k != "yearly_breakdown"}
        clean_dict["yearly_breakdown"] = yearly_breakdown
        json.dump(clean_dict, f, indent=2)
    print(f"[+] Champion summary saved to: {champ_json_path}")

    return res_df, top_10, champion_dict


def evaluate_yearly_consistency(
    df: pd.DataFrame,
    param_dict: dict,
    spread: float,
    commission: float,
    unit_size: float
):
    """
    Evaluates champion parameter set year-by-year from 2020 to 2025.
    """
    yearly_results = {}
    years = sorted(df.index.year.unique())
    warmup = 100

    e_lb = int(param_dict["entry_lookback"])
    x_lb = int(param_dict["exit_lookback"])
    sl = float(param_dict["sl_atr_mult"])
    tp = float(param_dict["tp_atr_mult"])
    ema_f = int(param_dict["ema_filter"])
    sess_mode = 1 if param_dict["session_mode"] == "London_NY" else 0

    for yr in years:
        df_yr = df[df.index.year == yr].copy()
        if len(df_yr) < 500:
            continue
        (
            atr_s, hours, ema_d,
            u_entry, l_entry, u_exit, l_exit
        ) = compute_pre_indicators(df_yr)

        opens = df_yr["open"].values.astype(np.float64)
        highs = df_yr["high"].values.astype(np.float64)
        lows = df_yr["low"].values.astype(np.float64)
        closes = df_yr["close"].values.astype(np.float64)

        ema_arr = ema_d[ema_f] if ema_f > 0 else np.zeros(len(closes), dtype=np.float64)
        use_ema = 1 if ema_f > 0 else 0

        res = simulate_donchian(
            opens, highs, lows, closes, atr_s, hours,
            u_entry[e_lb], l_entry[e_lb],
            u_exit[x_lb], l_exit[x_lb],
            ema_arr, use_ema, sess_mode,
            sl, tp, spread, commission, unit_size, warmup
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
    parser = argparse.ArgumentParser(description="Strategy 01: Donchian Breakout Sweep")
    parser.add_argument("--data", type=str, default=None, help="Path to M1 CSV dataset")
    parser.add_argument("--symbol", type=str, default="XAUUSD", help="Symbol name")
    parser.add_argument("--timeframe", type=str, default="15min", help="Backtest timeframe")
    parser.add_argument("--output_dir", type=str, default="projects/quant_strategy_discovery/results", help="Output directory")
    args, _ = parser.parse_known_args()

    # Resolve data path
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
    res_df, top_10, champ = run_mass_parameter_sweep(
        df_m15, symbol=args.symbol, output_dir=args.output_dir
    )
    print("\n✅ STRATEGY 01 COMPLETE: Results successfully generated.")
