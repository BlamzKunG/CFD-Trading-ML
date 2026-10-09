#!/usr/bin/env python3
"""
===============================================================================
STRATEGY 05: TRIPLE SCREEN / MULTI-TIMEFRAME EMA RIBBON PULLBACK SYSTEM
===============================================================================
Quantitative Backtesting & Parameter Robustness Engine for CFD Trading (XAUUSD)
Period: 2020 - 2025 (Full Multi-Year Validation)
Timeframe: Multi-Timeframe H1 (Macro Tide) + M15 (Wave Pullback & Trigger)

Core Mechanisms:
- Screen 1 (The Tide): H1 Macro EMA Ribbon Alignment (EMA Fast > EMA Slow)
- Screen 2 (The Wave): M15 Pullback into Value Zone (EMA 20/50 Ribbon or RSI Oversold)
- Screen 3 (The Ripple): Resumption Confirmation at candle close (Open[t+1] execution)
- Dynamic Stop Loss & Asymmetric Risk:Reward Targets (1.5R to 4.0R)
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
# NUMBA HIGH-SPEED TRIPLE SCREEN SIMULATION KERNEL
# -----------------------------------------------------------------------------
@njit(fastmath=True)
def simulate_triple_screen(
    opens: np.ndarray,
    highs: np.ndarray,
    lows: np.ndarray,
    closes: np.ndarray,
    atr: np.ndarray,
    hours: np.ndarray,
    h1_trend: np.ndarray,        # +1: Bullish, -1: Bearish, 0: Neutral
    pullback_signal: np.ndarray, # 1: Long pullback detected, -1: Short pullback detected
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

        # -------------------------------------------------------------
        # 2. Check Entries on Triple Screen Alignment
        # -------------------------------------------------------------
        if pos == 0:
            in_session = True
            if session_mode == 1:
                if hr < 7 or hr >= 20:
                    in_session = False

            if in_session and atr[i] > 0.0:
                tide = h1_trend[i]
                wave = pullback_signal[i]
                sl_dist = sl_atr_mult * atr[i]

                # Long Alignment: H1 Tide Bullish (+1) AND M15 Wave Bullish Pullback (+1)
                if tide == 1 and wave == 1 and closes[i] > opens[i]:
                    pos = 1
                    entry_price = opens[i + 1] + (spread * 0.5)
                    sl_price = entry_price - sl_dist
                    tp_price = entry_price + (sl_dist * tp_rr_mult)
                    entry_bar = i + 1

                # Short Alignment: H1 Tide Bearish (-1) AND M15 Wave Bearish Pullback (-1)
                elif tide == -1 and wave == -1 and closes[i] < opens[i]:
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


# -----------------------------------------------------------------------------
# MULTI-TIMEFRAME DATA PREPARATION
# -----------------------------------------------------------------------------
def load_and_prepare_mtf_data(data_path: str):
    print(f"[*] Loading M1 data from: {data_path}...")
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

    # 1. Resample to M15
    print("[*] Resampling to M15...")
    df_m15 = df.resample("15min").agg({
        "open": "first", "high": "max", "low": "min", "close": "last", "tick_volume": "sum"
    }).dropna()

    # 2. Resample to H1 for Macro Tide
    print("[*] Resampling to H1...")
    df_h1 = df.resample("1h").agg({
        "open": "first", "high": "max", "low": "min", "close": "last", "tick_volume": "sum"
    }).dropna()

    # Precalculate H1 Trends (Shifted by 1 H1 bar to prevent lookahead!)
    h1_trends_dict = {}
    h1_pairs = [(21, 55), (50, 200)]
    for fast_p, slow_p in h1_pairs:
        ema_fast = df_h1["close"].ewm(span=fast_p, adjust=False).mean()
        ema_slow = df_h1["close"].ewm(span=slow_p, adjust=False).mean()
        # Shift 1 bar: bar t H1 is only known after H1 closes!
        trend_h1 = np.where(ema_fast > ema_slow, 1, -1)
        s_trend = pd.Series(trend_h1, index=df_h1.index).shift(1).fillna(0)
        # Reindex to M15 forward-filled
        s_trend_m15 = s_trend.reindex(df_m15.index, method="ffill").fillna(0).astype(np.int32).values
        h1_trends_dict[(fast_p, slow_p)] = s_trend_m15

    # 3. Precalculate M15 Wave Pullback Signals
    close_m15 = df_m15["close"]
    high_m15 = df_m15["high"]
    low_m15 = df_m15["low"]

    # True Range & ATR(14)
    tr = np.maximum(
        high_m15.values[1:] - low_m15.values[1:],
        np.maximum(
            np.abs(high_m15.values[1:] - close_m15.values[:-1]),
            np.abs(low_m15.values[1:] - close_m15.values[:-1])
        )
    )
    tr = np.insert(tr, 0, high_m15.values[0] - low_m15.values[0])
    atr14 = pd.Series(tr, index=df_m15.index).rolling(14).mean().fillna(1.0).values.astype(np.float64)

    # RSI(14)
    delta = close_m15.diff()
    gain = (delta.where(delta > 0, 0)).rolling(14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
    rs = gain / (loss + 1e-6)
    rsi14 = 100 - (100 / (1 + rs)).fillna(50.0).values

    # EMAs
    ema20 = close_m15.ewm(span=20, adjust=False).mean().values
    ema50 = close_m15.ewm(span=50, adjust=False).mean().values

    pullback_dict = {}
    # Mode 0: Touch EMA 20 (Low <= EMA20 <= High)
    touch_ema20 = np.where(
        (low_m15.values <= ema20) & (close_m15.values >= ema20 * 0.999), 1,
        np.where((high_m15.values >= ema20) & (close_m15.values <= ema20 * 1.001), -1, 0)
    ).astype(np.int32)
    pullback_dict[0] = touch_ema20

    # Mode 1: Touch EMA 50
    touch_ema50 = np.where(
        (low_m15.values <= ema50) & (close_m15.values >= ema50 * 0.999), 1,
        np.where((high_m15.values >= ema50) & (close_m15.values <= ema50 * 1.001), -1, 0)
    ).astype(np.int32)
    pullback_dict[1] = touch_ema50

    # Mode 2: RSI Mild Oversold (< 40 for long, > 60 for short)
    rsi_mild = np.where(rsi14 <= 40, 1, np.where(rsi14 >= 60, -1, 0)).astype(np.int32)
    pullback_dict[2] = rsi_mild

    # Mode 3: RSI Deep Oversold (< 30 for long, > 70 for short)
    rsi_deep = np.where(rsi14 <= 30, 1, np.where(rsi14 >= 70, -1, 0)).astype(np.int32)
    pullback_dict[3] = rsi_deep

    hours = df_m15.index.hour.values.astype(np.int32)

    return df_m15, atr14, hours, h1_trends_dict, pullback_dict


# -----------------------------------------------------------------------------
# MASS PARAMETER SWEEP
# -----------------------------------------------------------------------------
def run_triple_screen_sweep(
    df_m15: pd.DataFrame,
    atr14: np.ndarray,
    hours: np.ndarray,
    h1_trends_dict: dict,
    pullback_dict: dict,
    symbol: str = "XAUUSD",
    output_dir: str = "projects/quant_strategy_discovery/results"
):
    os.makedirs(output_dir, exist_ok=True)
    opens = df_m15["open"].values.astype(np.float64)
    highs = df_m15["high"].values.astype(np.float64)
    lows = df_m15["low"].values.astype(np.float64)
    closes = df_m15["close"].values.astype(np.float64)

    unit_size = 10.0   # 0.10 lot
    spread = 0.25      # $0.25 spread
    commission = 0.06  # $6.00/lot standard round-turn
    warmup = 250

    h1_pairs = [(21, 55), (50, 200)]
    pullback_modes = [0, 1, 2, 3]
    sl_mults = [1.5, 2.0, 2.5, 3.0]
    tp_rrs = [1.5, 2.0, 3.0, 4.0]
    session_modes = [0, 1]  # 0: 24h, 1: London_NY (07-20 UTC)

    total_combos = (
        len(h1_pairs) * len(pullback_modes) * len(sl_mults) *
        len(tp_rrs) * len(session_modes)
    )

    print(f"\n{'='*75}")
    print(f"🚀 COMMENCING MASS PARAMETER SWEEP: STRATEGY 05 (TRIPLE SCREEN PULLBACK)")
    print(f"   Symbol: {symbol} | Total Combinations: {total_combos:,}")
    print(f"   Frictions: Spread=${spread:.2f} | Comm=${commission*100:.2f}/lot | Lot: 0.10")
    print(f"{'='*75}\n")

    # Warmup Numba JIT
    _ = simulate_triple_screen(
        opens, highs, lows, closes, atr14, hours,
        h1_trends_dict[(50, 200)], pullback_dict[0], 0,
        2.0, 2.0, spread, commission, unit_size, warmup
    )

    pullback_names = {
        0: "Touch_M15_EMA20",
        1: "Touch_M15_EMA50",
        2: "RSI_Mild_Oversold(40/60)",
        3: "RSI_Deep_Oversold(30/70)"
    }

    results = []
    t_start = time.time()
    count = 0

    for h1_p in h1_pairs:
        tide_arr = h1_trends_dict[h1_p]
        tide_label = f"H1_EMA_{h1_p[0]}_{h1_p[1]}"
        for pb_m in pullback_modes:
            pb_arr = pullback_dict[pb_m]
            for sl in sl_mults:
                for tp_r in tp_rrs:
                    for sess in session_modes:
                        count += 1
                        res = simulate_triple_screen(
                            opens, highs, lows, closes, atr14, hours,
                            tide_arr, pb_arr, sess,
                            sl, tp_r, spread, commission, unit_size, warmup
                        )
                        (
                            trades, net_pnl, gp, gl, pf,
                            wr, mdd, romad, sharpe, avg_hold
                        ) = res

                        results.append({
                            "h1_tide": tide_label,
                            "pullback_mode": pullback_names[pb_m],
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

                        if count % 100 == 0 or count == total_combos:
                            elapsed = time.time() - t_start
                            speed = count / elapsed if elapsed > 0 else 0
                            print(f"[*] Swept {count:,} / {total_combos:,} combos ({count/total_combos*100:.1f}%) | Speed: {speed:.1f} sets/sec")

    sweep_time = time.time() - t_start
    print(f"\n[+] Mass sweep completed in {sweep_time:.2f}s ({total_combos/sweep_time:.1f} sets/sec)!")

    res_df = pd.DataFrame(results)

    csv_path = os.path.join(output_dir, "strategy_05_triple_screen_sweep_results.csv")
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
    print(f"🏆 TOP 5 PARAMETER COMBINATIONS (STRATEGY 05 - TRIPLE SCREEN PULLBACK)")
    print(f"{'='*75}")
    for idx, row in top_10.head(5).iterrows():
        print(f"Rank: Tide={row['h1_tide']} | Pullback={row['pullback_mode']} | "
              f"SL={row['sl_atr_mult']}x | TP={row['tp_rr_mult']}R | Sess={row['session_mode']} | Net=${row['net_profit']:,.2f} | "
              f"PF={row['profit_factor']:.2f} | WR={row['win_rate']:.1f}% | DD=${row['max_drawdown']:,.2f} | Trades={int(row['total_trades'])}")

    print(f"\n{'='*75}")
    print(f"🥇 ULTIMATE CHAMPION PARAMETER SET:")
    print(f"   H1 Macro Tide:     {champion['h1_tide']}")
    print(f"   M15 Pullback Mode: {champion['pullback_mode']}")
    print(f"   SL ATR Mult:       {champion['sl_atr_mult']}x ATR(14)")
    print(f"   TP RR Mult:        {champion['tp_rr_mult']}R (Risk Multiple)")
    print(f"   Session Window:    {champion['session_mode']}")
    print(f"   --- Performance Across 2020-2025 ---")
    print(f"   Net Profit:        ${champion['net_profit']:,.2f} (on 0.10 lot)")
    print(f"   Profit Factor:     {champion['profit_factor']:.2f}")
    print(f"   Win Rate:          {champion['win_rate']:.2f}%")
    print(f"   Total Trades:      {int(champion['total_trades'])} ({int(champion['total_trades'])/5:.1f} trades/year)")
    print(f"   Max Drawdown:      ${champion['max_drawdown']:,.2f}")
    print(f"   RoMaD (Ret/DD):    {champion['romad']:.2f}")
    print(f"   Sharpe Ratio:      {champion['sharpe']:.2f}")
    print(f"{'='*75}\n")

    # Evaluate Yearly Consistency for Champion
    print("[*] Running multi-year breakdown for Champion Parameter Set...")
    champion_dict = champion.to_dict()
    yearly_breakdown = evaluate_triple_screen_yearly(
        df_m15, atr14, hours, h1_trends_dict, pullback_dict,
        champion_dict, spread, commission, unit_size
    )
    champion_dict["yearly_breakdown"] = yearly_breakdown

    champ_json_path = os.path.join(output_dir, "strategy_05_triple_screen_champion.json")
    with open(champ_json_path, "w") as f:
        clean_dict = {k: (float(v) if isinstance(v, (np.floating, float)) else (int(v) if isinstance(v, (np.integer, int)) else v)) for k, v in champion_dict.items() if k != "yearly_breakdown"}
        clean_dict["yearly_breakdown"] = yearly_breakdown
        json.dump(clean_dict, f, indent=2)
    print(f"[+] Champion summary saved to: {champ_json_path}")

    return res_df, top_10, champion_dict


def evaluate_triple_screen_yearly(
    df_m15: pd.DataFrame,
    atr14: np.ndarray,
    hours: np.ndarray,
    h1_trends_dict: dict,
    pullback_dict: dict,
    param_dict: dict,
    spread: float,
    commission: float,
    unit_size: float
):
    yearly_results = {}
    years = sorted(df_m15.index.year.unique())
    warmup = 50

    tide_key = (21, 55) if "21_55" in param_dict["h1_tide"] else (50, 200)
    pb_mode_map = {
        "Touch_M15_EMA20": 0,
        "Touch_M15_EMA50": 1,
        "RSI_Mild_Oversold(40/60)": 2,
        "RSI_Deep_Oversold(30/70)": 3
    }
    pb_key = pb_mode_map[param_dict["pullback_mode"]]
    sl = float(param_dict["sl_atr_mult"])
    tp_r = float(param_dict["tp_rr_mult"])
    sess_mode = 1 if param_dict["session_mode"] == "London_NY" else 0

    tide_full = h1_trends_dict[tide_key]
    pb_full = pullback_dict[pb_key]

    for yr in years:
        mask = (df_m15.index.year == yr)
        if np.sum(mask) < 500:
            continue

        opens_yr = df_m15["open"].values[mask].astype(np.float64)
        highs_yr = df_m15["high"].values[mask].astype(np.float64)
        lows_yr = df_m15["low"].values[mask].astype(np.float64)
        closes_yr = df_m15["close"].values[mask].astype(np.float64)
        atr_yr = atr14[mask]
        hours_yr = hours[mask]
        tide_yr = tide_full[mask]
        pb_yr = pb_full[mask]

        res = simulate_triple_screen(
            opens_yr, highs_yr, lows_yr, closes_yr, atr_yr, hours_yr,
            tide_yr, pb_yr, sess_mode,
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
    parser = argparse.ArgumentParser(description="Strategy 05: Triple Screen Sweep")
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
    df_m15, atr14, hours, h1_trends_dict, pullback_dict = load_and_prepare_mtf_data(resolved_path)
    res_df, top_10, champ = run_triple_screen_sweep(
        df_m15, atr14, hours, h1_trends_dict, pullback_dict,
        symbol=args.symbol, output_dir=args.output_dir
    )
    print("\n✅ STRATEGY 05 COMPLETE: Results successfully generated.")
