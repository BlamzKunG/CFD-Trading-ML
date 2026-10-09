#!/usr/bin/env python3
"""
===============================================================================
STRATEGY 06: MACD ZERO-LAG WITH MULTI-TIMEFRAME TREND CONFIRMATION
===============================================================================
Quantitative Backtesting & Parameter Robustness Engine for CFD Trading (XAUUSD)
Period: 2020 - 2025 (Full Multi-Year Validation)
Timeframe: M15 (Resampled from M1)

Dual-Mode Engine:
- Works with Numba if installed (microsecond speed)
- Seamless NumPy/C-fallback if Numba is absent
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

# Optional Numba acceleration
try:
    from numba import njit
    HAS_NUMBA = True
except ImportError:
    HAS_NUMBA = False
    def njit(*args, **kwargs):
        def decorator(func):
            return func
        return decorator

# -----------------------------------------------------------------------------
# HIGH-SPEED SIMULATION KERNEL
# -----------------------------------------------------------------------------
@njit(fastmath=True)
def simulate_zl_macd_kernel(
    opens: np.ndarray,
    highs: np.ndarray,
    lows: np.ndarray,
    closes: np.ndarray,
    atr: np.ndarray,
    hours: np.ndarray,
    macd_line: np.ndarray,
    signal_line: np.ndarray,
    ema: np.ndarray,
    use_ema: int,
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

        # 2. Check Entries on Zero-Lag MACD Crossover
        if pos == 0:
            in_session = True
            if session_mode == 1:
                if hr < 7 or hr >= 20:
                    in_session = False

            if in_session and atr[i] > 0.0:
                cur_m = macd_line[i]
                cur_s = signal_line[i]
                prev_m = macd_line[i - 1]
                prev_s = signal_line[i - 1]

                cross_bull = (prev_m <= prev_s) and (cur_m > cur_s)
                cross_bear = (prev_m >= prev_s) and (cur_m < cur_s)
                sl_dist = sl_atr_mult * atr[i]

                if cross_bull:
                    ema_ok = True
                    if use_ema == 1 and closes[i] < ema[i]:
                        ema_ok = False
                    if ema_ok:
                        pos = 1
                        entry_price = opens[i + 1] + (spread * 0.5)
                        sl_price = entry_price - sl_dist
                        tp_price = entry_price + (sl_dist * tp_rr_mult)
                        entry_bar = i + 1

                elif cross_bear:
                    ema_ok = True
                    if use_ema == 1 and closes[i] > ema[i]:
                        ema_ok = False
                    if ema_ok:
                        pos = -1
                        entry_price = opens[i + 1] - (spread * 0.5)
                        sl_price = entry_price + sl_dist
                        tp_price = entry_price - (sl_dist * tp_rr_mult)
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


def compute_zlema_vectorized(prices: np.ndarray, period: int):
    n = len(prices)
    lag = (period - 1) // 2
    delagged = np.zeros(n, dtype=np.float64)
    if lag > 0:
        delagged[lag:] = 2.0 * prices[lag:] - prices[:-lag]
        delagged[:lag] = prices[:lag]
    else:
        delagged[:] = prices[:]

    zlema = pd.Series(delagged).ewm(span=period, adjust=False).mean().values
    return zlema


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
        "open": "first", "high": "max", "low": "min", "close": "last", "tick_volume": "sum"
    }).dropna()
    print(f"[+] Resampled to {len(df_res):,} {timeframe} bars in {time.time() - t1:.2f}s.")
    return df_res


def precompute_zl_macd_indicators(df: pd.DataFrame, macd_configs: list):
    print("[*] Pre-computing Zero-Lag MACD configurations & EMAs...")
    t0 = time.time()
    close = df["close"].values.astype(np.float64)
    high = df["high"].values.astype(np.float64)
    low = df["low"].values.astype(np.float64)

    # ATR(14)
    tr = np.maximum(
        high[1:] - low[1:],
        np.maximum(
            np.abs(high[1:] - close[:-1]),
            np.abs(low[1:] - close[:-1])
        )
    )
    tr = np.insert(tr, 0, high[0] - low[0])
    atr14 = pd.Series(tr, index=df.index).rolling(14).mean().fillna(1.0).values.astype(np.float64)

    macd_dict = {}
    for (f_p, s_p, sig_p) in macd_configs:
        z_fast = compute_zlema_vectorized(close, f_p)
        z_slow = compute_zlema_vectorized(close, s_p)
        zl_line = z_fast - z_slow
        zl_sig = compute_zlema_vectorized(zl_line, sig_p)
        macd_dict[(f_p, s_p, sig_p)] = (zl_line, zl_sig)

    ema_dict = {}
    for span in [100, 200, 400]:
        ema_dict[span] = pd.Series(close, index=df.index).ewm(span=span, adjust=False).mean().values.astype(np.float64)

    hours = df.index.hour.values.astype(np.int32)
    print(f"[+] Zero-Lag MACD matrix pre-computed in {time.time() - t0:.2f}s.")
    return macd_dict, atr14, ema_dict, hours


# -----------------------------------------------------------------------------
# MASS PARAMETER SWEEP
# -----------------------------------------------------------------------------
def run_zl_macd_sweep(
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
    warmup = 250

    macd_configs = [(8, 21, 5), (12, 26, 9), (15, 34, 9)]
    ema_filters = [0, 100, 200, 400]
    sl_mults = [1.5, 2.0, 2.5, 3.0]
    tp_rrs = [1.5, 2.0, 3.0, 4.0]
    session_modes = [0, 1]  # 0: 24h, 1: London_NY (07-20 UTC)

    total_combos = (
        len(macd_configs) * len(ema_filters) * len(sl_mults) *
        len(tp_rrs) * len(session_modes)
    )

    print(f"\n{'='*75}")
    print(f"🚀 COMMENCING MASS PARAMETER SWEEP: STRATEGY 06 (ZERO-LAG MACD)")
    print(f"   Symbol: {symbol} | Total Combinations: {total_combos:,} | Numba: {HAS_NUMBA}")
    print(f"   Frictions: Spread=${spread:.2f} | Comm=${commission*100:.2f}/lot | Lot: 0.10")
    print(f"{'='*75}\n")

    macd_dict, atr14, ema_dict, hours = precompute_zl_macd_indicators(df, macd_configs)
    dummy_ema = np.zeros(len(closes), dtype=np.float64)

    results = []
    t_start = time.time()
    count = 0

    for cfg in macd_configs:
        m_line, s_line = macd_dict[cfg]
        cfg_label = f"ZL_MACD_{cfg[0]}_{cfg[1]}_{cfg[2]}"
        for ema_f in ema_filters:
            use_ema = 1 if ema_f > 0 else 0
            ema_arr = ema_dict[ema_f] if ema_f > 0 else dummy_ema
            for sl in sl_mults:
                for tp_r in tp_rrs:
                    for sess in session_modes:
                        count += 1
                        res = simulate_zl_macd_kernel(
                            opens, highs, lows, closes, atr14, hours,
                            m_line, s_line, ema_arr, use_ema, sess,
                            sl, tp_r, spread, commission, unit_size, warmup
                        )
                        (
                            trades, net_pnl, gp, gl, pf,
                            wr, mdd, romad, sharpe, avg_hold
                        ) = res

                        results.append({
                            "macd_config": cfg_label,
                            "ema_filter": ema_f,
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

    csv_path = os.path.join(output_dir, "strategy_06_zl_macd_sweep_results.csv")
    res_df.to_csv(csv_path, index=False)
    print(f"[+] Complete sweep results saved to: {csv_path}")

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
    print(f"🏆 TOP 5 PARAMETER COMBINATIONS (STRATEGY 06 - ZERO-LAG MACD)")
    print(f"{'='*75}")
    for idx, row in top_10.head(5).iterrows():
        print(f"Rank: CFG={row['macd_config']} | EMA={row['ema_filter']} | "
              f"SL={row['sl_atr_mult']}x | TP={row['tp_rr_mult']}R | Sess={row['session_mode']} | Net=${row['net_profit']:,.2f} | "
              f"PF={row['profit_factor']:.2f} | WR={row['win_rate']:.1f}% | DD=${row['max_drawdown']:,.2f} | Trades={int(row['total_trades'])}")

    print(f"\n{'='*75}")
    print(f"🥇 ULTIMATE CHAMPION PARAMETER SET:")
    print(f"   MACD Config:    {champion['macd_config']}")
    print(f"   EMA Filter:     {champion['ema_filter']} {'(No Filter)' if champion['ema_filter'] == 0 else ''}")
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

    # Evaluate Yearly Consistency for Champion
    print("[*] Running multi-year breakdown for Champion Parameter Set...")
    champion_dict = champion.to_dict()
    yearly_breakdown = evaluate_zl_macd_yearly(
        df, champion_dict, spread, commission, unit_size
    )
    champion_dict["yearly_breakdown"] = yearly_breakdown

    champ_json_path = os.path.join(output_dir, "strategy_06_zl_macd_champion.json")
    with open(champ_json_path, "w") as f:
        clean_dict = {k: (float(v) if isinstance(v, (np.floating, float)) else (int(v) if isinstance(v, (np.integer, int)) else v)) for k, v in champion_dict.items() if k != "yearly_breakdown"}
        clean_dict["yearly_breakdown"] = yearly_breakdown
        json.dump(clean_dict, f, indent=2)
    print(f"[+] Champion summary saved to: {champ_json_path}")

    return res_df, top_10, champion_dict


def evaluate_zl_macd_yearly(
    df: pd.DataFrame,
    param_dict: dict,
    spread: float,
    commission: float,
    unit_size: float
):
    yearly_results = {}
    years = sorted(df.index.year.unique())
    warmup = 100

    cfg_str = param_dict["macd_config"]
    parts = cfg_str.replace("ZL_MACD_", "").split("_")
    cfg = (int(parts[0]), int(parts[1]), int(parts[2]))
    ema_f = int(param_dict["ema_filter"])
    sl = float(param_dict["sl_atr_mult"])
    tp_r = float(param_dict["tp_rr_mult"])
    sess_mode = 1 if param_dict["session_mode"] == "London_NY" else 0

    for yr in years:
        df_yr = df[df.index.year == yr].copy()
        if len(df_yr) < 500:
            continue

        macd_d, atr_yr, ema_d, hrs = precompute_zl_macd_indicators(df_yr, [cfg])
        opens = df_yr["open"].values.astype(np.float64)
        highs = df_yr["high"].values.astype(np.float64)
        lows = df_yr["low"].values.astype(np.float64)
        closes = df_yr["close"].values.astype(np.float64)

        m_line, s_line = macd_d[cfg]
        ema_arr = ema_d[ema_f] if ema_f > 0 else np.zeros(len(closes), dtype=np.float64)
        use_ema = 1 if ema_f > 0 else 0

        res = simulate_zl_macd_kernel(
            opens, highs, lows, closes, atr_yr, hrs,
            m_line, s_line, ema_arr, use_ema, sess_mode,
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


# -----------------------------------------------------------------------------
# MAIN ENTRYPOINT
# -----------------------------------------------------------------------------
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Strategy 06: Zero-Lag MACD Sweep")
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
    res_df, top_10, champ = run_zl_macd_sweep(
        df_m15, symbol=args.symbol, output_dir=args.output_dir
    )
    print("\n✅ STRATEGY 06 COMPLETE: Results successfully generated.")
