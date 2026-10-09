#!/usr/bin/env python3
"""
===============================================================================
STRATEGY 23: SQUEEZE-COMPRESSED DUAL-REGIME (SCDR) WITH MONTHLY PROFIT LOCKING
===============================================================================
Institutional Quant Architecture: The Convergence Model for MCR >= 80%
Asset: XAUUSD CFD (2020 - 2025, 72 Calendar Months)
Timeframe: M15 (Resampled from M1)

Quantitative Synthesis:
1. Core Problem Identified in Strategy 17 (66.67% MCR):
   - Strategy 17 lost in 24 months because its London/NY Trend Engine used a raw 8-bar breakout
     without volatility compression, suffering whipsaws during summer consolidation.
2. The Solution (SCDR Engine):
   - Upgrade Engine 1: London/NY Trend Breakout (08:00 - 18:00 UTC) must be CONFIRMED by
     a Volatility Compression Squeeze (Bollinger Bands inside Keltner Channel or VCR <= 0.70)
     + Macro EMA200 filter.
   - Retain Engine 2: Asian Session Mean Reversion (21:00 - 06:00 UTC) fading extreme 2.8 std bands
     back to SMA20.
3. Monthly Capital Preservation Engine:
   - Monthly Profit Lock: +$250 to +$400 -> Locks the winning month.
   - Monthly Circuit Breaker: -$200 to -$300 -> Prevents deep drawdown.
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

def simulate_scdr_budgeted_fast(
    opens: np.ndarray,
    highs: np.ndarray,
    lows: np.ndarray,
    closes: np.ndarray,
    atr14: np.ndarray,
    ema200: np.ndarray,
    sma20: np.ndarray,
    bb_upper: np.ndarray,
    bb_lower: np.ndarray,
    kc_upper: np.ndarray,
    kc_lower: np.ndarray,
    was_squeezed_arr: np.ndarray,
    months: np.ndarray,
    hours: np.ndarray,
    dates: pd.DatetimeIndex,
    trend_tp_mult: float = 3.5,
    trend_sl_mult: float = 2.0,
    rev_std_mult: float = 2.8,
    rev_sl_atr: float = 1.8,
    monthly_profit_lock: float = 300.0,
    monthly_loss_breaker: float = 250.0,
    spread: float = 0.25,
    commission_per_unit: float = 0.06,
    unit_size: float = 10.0,
    warmup: int = 250
):
    n = len(closes)
    trades = []

    pos = 0
    entry_p = 0.0
    sl_p = 0.0
    tp_p = 0.0
    sub_mode = ""

    curr_month = None
    month_cum_pnl = 0.0
    month_locked = False

    # Dynamic Bollinger Bands for Reversion
    std20 = (bb_upper - sma20) / 2.0
    rev_upper = sma20 + rev_std_mult * std20
    rev_lower = sma20 - rev_std_mult * std20

    for i in range(warmup, n - 1):
        m_key = months[i]
        hr = hours[i]
        c_atr = atr14[i]

        # Reset budget at start of each new month
        if m_key != curr_month:
            curr_month = m_key
            month_cum_pnl = 0.0
            month_locked = False

        # 1. Manage Exits
        if pos == 1:
            exit_triggered = False
            exit_p = 0.0
            if lows[i] <= sl_p:
                exit_p = sl_p if opens[i] >= sl_p else opens[i]
                exit_triggered = True
            elif sub_mode == "TREND" and highs[i] >= tp_p:
                exit_p = tp_p if opens[i] <= tp_p else opens[i]
                exit_triggered = True
            elif sub_mode == "REV" and highs[i] >= sma20[i]:
                exit_p = sma20[i] if opens[i] <= sma20[i] else opens[i]
                exit_triggered = True

            if exit_triggered:
                pnl = (exit_p - entry_p) * unit_size - (spread + commission_per_unit) * unit_size
                trades.append({"pnl": pnl, "date": dates[i], "engine": sub_mode, "month": m_key})
                month_cum_pnl += pnl
                pos = 0

                if monthly_profit_lock > 0 and month_cum_pnl >= monthly_profit_lock:
                    month_locked = True
                elif monthly_loss_breaker > 0 and month_cum_pnl <= -monthly_loss_breaker:
                    month_locked = True

        elif pos == -1:
            exit_triggered = False
            exit_p = 0.0
            if highs[i] >= sl_p:
                exit_p = sl_p if opens[i] <= sl_p else opens[i]
                exit_triggered = True
            elif sub_mode == "TREND" and lows[i] <= tp_p:
                exit_p = tp_p if opens[i] >= tp_p else opens[i]
                exit_triggered = True
            elif sub_mode == "REV" and lows[i] <= sma20[i]:
                exit_p = sma20[i] if opens[i] >= sma20[i] else opens[i]
                exit_triggered = True

            if exit_triggered:
                pnl = (entry_p - exit_p) * unit_size - (spread + commission_per_unit) * unit_size
                trades.append({"pnl": pnl, "date": dates[i], "engine": sub_mode, "month": m_key})
                month_cum_pnl += pnl
                pos = 0

                if monthly_profit_lock > 0 and month_cum_pnl >= monthly_profit_lock:
                    month_locked = True
                elif monthly_loss_breaker > 0 and month_cum_pnl <= -monthly_loss_breaker:
                    month_locked = True

        # 2. Check Entries (Only if month is not locked)
        if pos == 0 and c_atr > 0 and not month_locked:
            # Engine 1: Squeeze-Confirmed London / NY Trend Breakout (08:00 - 18:00 UTC)
            if 8 <= hr < 18:
                is_firing = (bb_upper[i] > kc_upper[i]) or (bb_lower[i] < kc_lower[i])
                if was_squeezed_arr[i] and is_firing:
                    if closes[i] > kc_upper[i] and closes[i] > ema200[i]:
                        pos = 1
                        entry_p = opens[i + 1] + (spread * 0.5)
                        sl_dist = trend_sl_mult * c_atr
                        sl_p = entry_p - sl_dist
                        tp_p = entry_p + (sl_dist * trend_tp_mult)
                        sub_mode = "TREND"
                    elif closes[i] < kc_lower[i] and closes[i] < ema200[i]:
                        pos = -1
                        entry_p = opens[i + 1] - (spread * 0.5)
                        sl_dist = trend_sl_mult * c_atr
                        sl_p = entry_p + sl_dist
                        tp_p = entry_p - (sl_dist * trend_tp_mult)
                        sub_mode = "TREND"

            # Engine 2: Asian Mean Reversion (21:00 - 06:00 UTC)
            elif hr >= 21 or hr < 6:
                if lows[i] < rev_lower[i] and closes[i] > rev_lower[i]:
                    pos = 1
                    entry_p = opens[i + 1] + (spread * 0.5)
                    sl_p = entry_p - (rev_sl_atr * c_atr)
                    sub_mode = "REV"
                elif highs[i] > rev_upper[i] and closes[i] < rev_upper[i]:
                    pos = -1
                    entry_p = opens[i + 1] - (spread * 0.5)
                    sl_p = entry_p + (rev_sl_atr * c_atr)
                    sub_mode = "REV"

    return trades

def evaluate_metrics(trades: list) -> dict:
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
    peak = np.maximum.accumulate(eq)
    dd = peak - eq
    max_dd = float(np.max(dd))

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
        "neg_months": neg_months,
        "monthly_series": {str(k): round(float(v), 2) for k, v in monthly_pnl.items()}
    }

def main():
    parser = argparse.ArgumentParser(description="Sweep Strategy 23: Squeeze-Compressed Dual-Regime Ensemble")
    parser.add_argument("--data", type=str, default="/mnt/sdcard/Download/EA/XAUUSD_M1.csv.gz", help="Path to M1 data")
    parser.add_argument("--out_dir", type=str, default="/root/CFD-Trading-ML/projects/quant_strategy_discovery/results", help="Results dir")
    args = parser.parse_args()

    os.makedirs(args.out_dir, exist_ok=True)

    print(f"[*] Loading M1 data from {args.data}...")
    df_raw = pd.read_csv(
        args.data,
        usecols=["datetime", "open", "high", "low", "close", "tick_volume"],
        dtype={"open": np.float32, "high": np.float32, "low": np.float32, "close": np.float32, "tick_volume": np.int32}
    )
    df_raw["datetime"] = pd.to_datetime(df_raw["datetime"])
    df_raw.set_index("datetime", inplace=True)
    df_raw.sort_index(inplace=True)

    print(f"[*] Resampling to M15 timeframe...")
    df_m15 = df_raw.resample("15min").agg({
        "open": "first", "high": "max", "low": "min", "close": "last", "tick_volume": "sum"
    }).dropna()
    print(f"[+] Loaded {len(df_m15):,} M15 bars (2020 - 2025).")

    opens = df_m15["open"].values.astype(np.float64)
    highs = df_m15["high"].values.astype(np.float64)
    lows = df_m15["low"].values.astype(np.float64)
    closes = df_m15["close"].values.astype(np.float64)
    hours = df_m15.index.hour.values.astype(np.int32)
    dates = df_m15.index
    months = (dates.year.values * 100 + dates.month.values).astype(np.int32)

    print(f"[*] Computing Indicators (ATR14, EMA200, Bollinger Bands, Keltner Channels)...")
    atr14 = compute_atr(highs, lows, closes, 14)
    ema200 = compute_ema(closes, 200)

    sma20 = pd.Series(closes).rolling(20).mean().values
    std20 = pd.Series(closes).rolling(20).std().values
    bb_upper = sma20 + 2.0 * std20
    bb_lower = sma20 - 2.0 * std20

    kc_upper = sma20 + 1.5 * atr14
    kc_lower = sma20 - 1.5 * atr14

    # Vectorized check: bar i-1 was squeezed inside Keltner channel
    is_squeezed = (bb_upper <= kc_upper) & (bb_lower >= kc_lower)
    was_squeezed_arr = pd.Series(is_squeezed).shift(1).fillna(False).values

    # Sweep Grid
    trend_tps = [3.0, 4.0]
    trend_sls = [2.0, 2.5]
    profit_locks = [0.0, 250.0, 350.0, 500.0]
    loss_breakers = [0.0, 200.0, 300.0]

    total_combs = len(trend_tps) * len(trend_sls) * len(profit_locks) * len(loss_breakers)
    print(f"[*] Sweeping {total_combs} SCDR parameter combinations across 72 calendar months...")

    results = []
    t_start = time.time()

    for tp_m in trend_tps:
        for sl_m in trend_sls:
            for plock in profit_locks:
                for lbreak in loss_breakers:
                    trades = simulate_scdr_budgeted_fast(
                        opens=opens, highs=highs, lows=lows, closes=closes,
                        atr14=atr14, ema200=ema200, sma20=sma20,
                        bb_upper=bb_upper, bb_lower=bb_lower,
                        kc_upper=kc_upper, kc_lower=kc_lower,
                        was_squeezed_arr=was_squeezed_arr,
                        months=months, hours=hours, dates=dates,
                        trend_tp_mult=tp_m, trend_sl_mult=sl_m,
                        monthly_profit_lock=plock, monthly_loss_breaker=lbreak
                    )
                    m = evaluate_metrics(trades)
                    m.update({
                        "trend_tp": tp_m, "trend_sl": sl_m,
                        "profit_lock": plock, "loss_breaker": lbreak
                    })
                    results.append(m)

    df_res = pd.DataFrame(results)
    df_res.sort_values(by=["mcr", "net_profit"], ascending=[False, False], inplace=True)

    csv_path = os.path.join(args.out_dir, "strategy_23_scdr_ensemble_sweep_results.csv")
    df_res.drop(columns=["monthly_series"]).to_csv(csv_path, index=False)
    print(f"[+] Saved sweep results to {csv_path}")

    champion = results[df_res.index[0]]
    champ_json_path = os.path.join(args.out_dir, "strategy_23_champion.json")
    with open(champ_json_path, "w") as f:
        json.dump(champion, f, indent=2)

    print("\n" + "="*80)
    print("STRATEGY 23: SQUEEZE-COMPRESSED DUAL-REGIME ENSEMBLE - TOP CHAMPION")
    print("="*80)
    print(f"Config: TrendTP={champion['trend_tp']}R, TrendSL={champion['trend_sl']}xATR, ProfitLock=${champion['profit_lock']}, LossBreaker=${champion['loss_breaker']}")
    print(f"Trades: {champion['total_trades']}")
    print(f"Net Profit: ${champion['net_profit']:,.2f}")
    print(f"Profit Factor: {champion['pf']}")
    print(f"Win Rate: {champion['win_rate']}%")
    print(f"Max Drawdown: ${champion['max_dd']:,.2f}")
    print(f"Monthly Consistency Ratio (MCR): {champion['mcr']}% ({champion['pos_months']} profitable / {champion['total_months']} total months)")
    print(f"Elapsed Time: {time.time() - t_start:.2f}s")
    print("="*80)

if __name__ == "__main__":
    main()
