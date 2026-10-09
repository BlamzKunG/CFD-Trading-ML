#!/usr/bin/env python3
"""
===============================================================================
STRATEGY 18: ASYMMETRIC VOLATILITY SKEW & ANCHORED VWAP MOMENTUM BANDS (AVS-VWAP)
===============================================================================
Quantitative CFD Strategy Discovery Engine
Asset: XAUUSD & EURUSD CFD (2020 - 2025, 72 Calendar Months)
Timeframe: M15 (Resampled from M1)

Core Quantitative Hypothesis:
1. Microstructure Anchored VWAP (AVWAP):
   - Anchored at 00:00 UTC (start of each trading day).
   - Intraday fair value benchmark weighted by tick volume.
   - Exact running volume-weighted standard deviation bands:
     Upper/Lower Band 1 (+/- k1 * sigma): Regime breakout threshold
     Upper/Lower Band 2 (+/- k2 * sigma): Volatility exhaustion & skew boundary
2. Asymmetric Dual-Regime Execution:
   - London / NY Expansion (08:00 - 18:00 UTC):
     When price breaks outside Band 1 with macro trend (EMA200), ride momentum
     towards Band 2 or 3.5R with trailing VWAP stop.
   - Asian Session Mean Reversion (21:00 - 06:00 UTC):
     When price extends to Band 2 (extreme exhaustion), fade the move back to VWAP.
3. Integrated Monthly Consistency Engine:
   - Evaluated across 72 consecutive months (2020 - 2025).
   - Swept across band multipliers, stop modes, and monthly profit-locking budgets.
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

def compute_anchored_vwap_and_bands(
    highs: np.ndarray,
    lows: np.ndarray,
    closes: np.ndarray,
    volumes: np.ndarray,
    dates: pd.DatetimeIndex,
    atr14: np.ndarray
):
    """
    Computes daily Anchored VWAP (reset at 00:00 UTC) and volume-weighted standard deviation bands.
    Uses running sum of P*V and P^2*V for O(1) performance.
    """
    n = len(closes)
    vwap = np.zeros(n, dtype=np.float64)
    sigma = np.zeros(n, dtype=np.float64)

    typical_p = (highs + lows + closes) / 3.0
    vol = np.maximum(volumes, 1.0)

    cum_pv = 0.0
    cum_pv2 = 0.0
    cum_vol = 0.0
    last_day = None

    for i in range(n):
        c_day = dates[i].date()
        if c_day != last_day:
            last_day = c_day
            cum_pv = 0.0
            cum_pv2 = 0.0
            cum_vol = 0.0

        p = typical_p[i]
        v = vol[i]
        cum_pv += p * v
        cum_pv2 += (p * p) * v
        cum_vol += v

        current_vwap = cum_pv / cum_vol
        vwap[i] = current_vwap

        var = (cum_pv2 / cum_vol) - (current_vwap * current_vwap)
        raw_sigma = np.sqrt(max(var, 0.0))
        # Use floor of 0.3 * ATR to prevent 0 width on first bar of day
        sigma[i] = max(raw_sigma, 0.3 * atr14[i])

    return vwap, sigma

def simulate_avs_vwap_strategy(
    opens: np.ndarray,
    highs: np.ndarray,
    lows: np.ndarray,
    closes: np.ndarray,
    vwap: np.ndarray,
    sigma: np.ndarray,
    atr14: np.ndarray,
    ema200: np.ndarray,
    hours: np.ndarray,
    dates: pd.DatetimeIndex,
    k1: float = 1.5,
    k2: float = 2.5,
    trend_rr: float = 3.5,
    trend_sl_atr: float = 2.0,
    rev_sl_atr: float = 1.8,
    monthly_profit_lock: float = 400.0,
    monthly_loss_breaker: float = 300.0,
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
    months = (dates.year.values * 100 + dates.month.values).astype(np.int32)
    upper_band1 = vwap + (k1 * sigma)
    lower_band1 = vwap - (k1 * sigma)
    upper_band2 = vwap + (k2 * sigma)
    lower_band2 = vwap - (k2 * sigma)

    for i in range(warmup, n - 1):
        m_key = months[i]
        hr = hours[i]
        c_atr = atr14[i]

        # Reset month budget
        if m_key != curr_month:
            curr_month = m_key
            month_cum_pnl = 0.0
            month_locked = False

        # 1. Manage Exits (Strict causal intra-bar execution)
        if pos == 1:
            exit_triggered = False
            exit_p = 0.0
            if lows[i] <= sl_p:
                exit_p = sl_p if opens[i] >= sl_p else opens[i]
                exit_triggered = True
            elif sub_mode == "TREND" and highs[i] >= tp_p:
                exit_p = tp_p if opens[i] <= tp_p else opens[i]
                exit_triggered = True
            elif sub_mode == "REV" and highs[i] >= vwap[i]:
                exit_p = vwap[i] if opens[i] <= vwap[i] else opens[i]
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
            elif sub_mode == "REV" and lows[i] <= vwap[i]:
                exit_p = vwap[i] if opens[i] >= vwap[i] else opens[i]
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

        # 2. Check Entries (at bar i close, executed at opens[i+1])
        if pos == 0 and c_atr > 0 and not month_locked:
            # Engine 1: London / NY Trend Momentum Expansion (08:00 - 18:00 UTC)
            if 8 <= hr < 18:
                # Bullish Momentum: Bar breaks and closes above Band 1 + Macro EMA200 uptrend
                if closes[i] > upper_band1[i] and closes[i - 1] <= upper_band1[i - 1] and closes[i] > ema200[i]:
                    pos = 1
                    entry_p = opens[i + 1] + (spread * 0.5)
                    sl_dist = trend_sl_atr * c_atr
                    sl_p = entry_p - sl_dist
                    tp_p = entry_p + (sl_dist * trend_rr)
                    sub_mode = "TREND"

                # Bearish Momentum: Bar breaks and closes below Band 1 + Macro EMA200 downtrend
                elif closes[i] < lower_band1[i] and closes[i - 1] >= lower_band1[i - 1] and closes[i] < ema200[i]:
                    pos = -1
                    entry_p = opens[i + 1] - (spread * 0.5)
                    sl_dist = trend_sl_atr * c_atr
                    sl_p = entry_p + sl_dist
                    tp_p = entry_p - (sl_dist * trend_rr)
                    sub_mode = "TREND"

            # Engine 2: Asian / Off-Hours Mean Reversion (21:00 - 06:00 UTC)
            elif hr >= 21 or hr < 6:
                # Oversold Exhaustion at Lower Band 2 -> Mean Revert to VWAP
                if lows[i] < lower_band2[i] and closes[i] > lower_band2[i]:
                    pos = 1
                    entry_p = opens[i + 1] + (spread * 0.5)
                    sl_p = entry_p - (rev_sl_atr * c_atr)
                    sub_mode = "REV"

                # Overbought Exhaustion at Upper Band 2 -> Mean Revert to VWAP
                elif highs[i] > upper_band2[i] and closes[i] < upper_band2[i]:
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

    # Monthly breakdown across all calendar months
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
    parser = argparse.ArgumentParser(description="Sweep Strategy 18: Asymmetric Volatility Skew & Anchored VWAP Momentum Bands")
    parser.add_argument("--data", type=str, default="/mnt/sdcard/Download/EA/XAUUSD_M1.csv.gz", help="Path to M1 data")
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

    print(f"[*] Resampling to M15 timeframe...")
    df_m15 = df_raw.resample("15min").agg({
        "open": "first", "high": "max", "low": "min", "close": "last", "tick_volume": "sum"
    }).dropna()
    print(f"[+] Loaded {len(df_m15):,} M15 bars (2020 - 2025).")

    opens = df_m15["open"].values.astype(np.float64)
    highs = df_m15["high"].values.astype(np.float64)
    lows = df_m15["low"].values.astype(np.float64)
    closes = df_m15["close"].values.astype(np.float64)
    volumes = df_m15["tick_volume"].values.astype(np.float64)
    hours = df_m15.index.hour.values.astype(np.int32)
    dates = df_m15.index

    print(f"[*] Computing Indicators (ATR14, EMA200, Daily Anchored VWAP & Variance Bands)...")
    atr14 = compute_atr(highs, lows, closes, 14)
    ema200 = compute_ema(closes, 200)
    vwap, sigma = compute_anchored_vwap_and_bands(highs, lows, closes, volumes, dates, atr14)

    # Parameter Grid Sweep
    k1_list = [1.2, 1.5, 1.8]              # Band 1 multiplier
    k2_list = [2.2, 2.5, 2.8]              # Band 2 multiplier
    rr_list = [3.0, 4.0]                   # Trend R:R target
    profit_locks = [0.0, 350.0, 500.0]     # Monthly profit lock (USD)
    loss_breakers = [0.0, 250.0, 350.0]    # Monthly loss breaker (USD)

    total_combs = len(k1_list) * len(k2_list) * len(rr_list) * len(profit_locks) * len(loss_breakers)
    print(f"[*] Sweeping {total_combs} parameter combinations across 72 calendar months...")

    results = []
    c_idx = 0
    t_start = time.time()

    for k1 in k1_list:
        for k2 in k2_list:
            if k2 <= k1:
                continue
            for rr in rr_list:
                for plock in profit_locks:
                    for lbreak in loss_breakers:
                        c_idx += 1
                        trades = simulate_avs_vwap_strategy(
                            opens=opens, highs=highs, lows=lows, closes=closes,
                            vwap=vwap, sigma=sigma, atr14=atr14, ema200=ema200,
                            hours=hours, dates=dates,
                            k1=k1, k2=k2, trend_rr=rr,
                            monthly_profit_lock=plock, monthly_loss_breaker=lbreak
                        )
                        m = evaluate_metrics(trades)
                        m.update({
                            "k1": k1, "k2": k2, "trend_rr": rr,
                            "profit_lock": plock, "loss_breaker": lbreak
                        })
                        results.append(m)

    df_res = pd.DataFrame(results)
    df_res.sort_values(by=["mcr", "net_profit"], ascending=[False, False], inplace=True)

    csv_path = os.path.join(args.out_dir, "strategy_18_avs_vwap_sweep_results.csv")
    df_res.drop(columns=["monthly_series"]).to_csv(csv_path, index=False)
    print(f"[+] Saved sweep results to {csv_path}")

    # Top Champion
    champion = results[df_res.index[0]]
    champ_json_path = os.path.join(args.out_dir, "strategy_18_champion.json")
    with open(champ_json_path, "w") as f:
        json.dump(champion, f, indent=2)

    print("\n" + "="*80)
    print("STRATEGY 18: ANCHORED VWAP SKEW (AVS-VWAP) - TOP CHAMPION")
    print("="*80)
    print(f"Config: k1={champion['k1']}, k2={champion['k2']}, RR={champion['trend_rr']}, ProfitLock=${champion['profit_lock']}, LossBreaker=${champion['loss_breaker']}")
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
