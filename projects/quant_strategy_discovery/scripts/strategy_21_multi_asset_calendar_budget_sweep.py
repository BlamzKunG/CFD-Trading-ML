#!/usr/bin/env python3
"""
===============================================================================
STRATEGY 21: MULTI-ASSET CROSS-REGIME ENSEMBLE WITH CALENDAR RISK BUDGETING
===============================================================================
Quantitative CFD Strategy Discovery Engine (Target: MCR >= 80% "กำไรทุกเดือน")
Assets: XAUUSD (Gold) + EURUSD CFD (2020 - 2025, 72 Calendar Months)
Timeframe: M15 (Resampled from M1)

Quantitative Rationale:
1. Institutional Asset Complementarity:
   - Gold (Commodity): Fat-tailed momentum trend follower during London/NY.
   - EURUSD (Major FX): Strong mean-reverter (75% ranging), thrives during Asian session.
2. Seasonality Calendar De-Risking (The Summer/Holiday Cure):
   - Quantitative audits of Strategy 17 revealed that >65% of losing months occur in
     July, August, and late December (summer liquidity drains & holiday consolidation).
   - Seasonality Gating: During July & August, reduce position size by 50% or tighten
     loss breakers to prevent chop drawdown from destroying the month.
3. Master Hierarchical Budgeting:
   - Monthly Ensemble Profit Lock: +$300 (locks the winning month).
   - Monthly Ensemble Loss Breaker: -$250 (halts until 1st of next month).
   - Weekly Circuit Breaker: -$120 (halts until Monday if bad streak occurs).
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

def simulate_multi_asset_calendar_ensemble(
    gold_df: pd.DataFrame,
    eur_df: pd.DataFrame,
    monthly_profit_lock: float = 300.0,
    monthly_loss_breaker: float = 250.0,
    weekly_loss_breaker: float = 120.0,
    summer_risk_factor: float = 0.5,
    gold_trend_tp: float = 4.0,
    gold_rev_std: float = 2.8,
    eur_rev_std: float = 2.5,
    warmup: int = 250
):
    # Align on common datetime index
    common_idx = gold_df.index.intersection(eur_df.index)
    df_g = gold_df.loc[common_idx]
    df_e = eur_df.loc[common_idx]

    dates = common_idx
    months = (dates.year.values * 100 + dates.month.values).astype(np.int32)
    weeks = (dates.year.values * 100 + dates.isocalendar().week.values).astype(np.int32)
    cal_months = dates.month.values.astype(np.int32)
    hours = dates.hour.values.astype(np.int32)

    # Gold arrays
    g_opens = df_g["open"].values.astype(np.float64)
    g_highs = df_g["high"].values.astype(np.float64)
    g_lows = df_g["low"].values.astype(np.float64)
    g_closes = df_g["close"].values.astype(np.float64)
    g_atr = compute_atr(g_highs, g_lows, g_closes, 14)
    g_ema200 = compute_ema(g_closes, 200)
    g_sma20 = pd.Series(g_closes).rolling(20).mean().values
    g_std20 = pd.Series(g_closes).rolling(20).std().values
    g_bb_u = g_sma20 + gold_rev_std * g_std20
    g_bb_l = g_sma20 - gold_rev_std * g_std20

    # EURUSD arrays
    e_opens = df_e["open"].values.astype(np.float64)
    e_highs = df_e["high"].values.astype(np.float64)
    e_lows = df_e["low"].values.astype(np.float64)
    e_closes = df_e["close"].values.astype(np.float64)
    e_atr = compute_atr(e_highs, e_lows, e_closes, 14)
    e_sma20 = pd.Series(e_closes).rolling(20).mean().values
    e_std20 = pd.Series(e_closes).rolling(20).std().values
    e_bb_u = e_sma20 + eur_rev_std * e_std20
    e_bb_l = e_sma20 - eur_rev_std * e_std20

    n = len(dates)
    trades = []

    # State variables
    g_pos = 0; g_entry_p = 0.0; g_sl_p = 0.0; g_tp_p = 0.0; g_sub = ""; g_lot = 10.0
    e_pos = 0; e_entry_p = 0.0; e_sl_p = 0.0; e_tp_p = 0.0; e_lot = 10.0

    curr_month = None
    curr_week = None
    month_cum_pnl = 0.0
    week_cum_pnl = 0.0
    month_locked = False
    week_locked = False

    gold_spread = 0.25; gold_comm = 0.06
    eur_spread = 0.00008; eur_comm = 0.00006  # 0.8 pip spread + commission ($6/lot)

    for i in range(warmup, n - 1):
        m_key = months[i]
        w_key = weeks[i]
        c_month = cal_months[i]
        hr = hours[i]

        # Reset month budget
        if m_key != curr_month:
            curr_month = m_key
            month_cum_pnl = 0.0
            month_locked = False

        # Reset week budget
        if w_key != curr_week:
            curr_week = w_key
            week_cum_pnl = 0.0
            week_locked = False

        # Summer seasonality scaling (July & August)
        is_summer = (c_month == 7 or c_month == 8)
        current_risk_mult = summer_risk_factor if is_summer else 1.0

        # --- MANAGE EXITS ---
        # 1. Gold Exit Management
        if g_pos == 1:
            exit_trig = False; exit_p = 0.0
            if g_lows[i] <= g_sl_p:
                exit_p = g_sl_p if g_opens[i] >= g_sl_p else g_opens[i]
                exit_trig = True
            elif g_sub == "TREND" and g_highs[i] >= g_tp_p:
                exit_p = g_tp_p if g_opens[i] <= g_tp_p else g_opens[i]
                exit_trig = True
            elif g_sub == "REV" and g_highs[i] >= g_sma20[i]:
                exit_p = g_sma20[i] if g_opens[i] <= g_sma20[i] else g_opens[i]
                exit_trig = True

            if exit_trig:
                pnl = (exit_p - g_entry_p) * g_lot - (gold_spread + gold_comm) * g_lot
                trades.append({"pnl": pnl, "date": dates[i], "asset": "GOLD", "engine": g_sub, "month": m_key})
                month_cum_pnl += pnl; week_cum_pnl += pnl
                g_pos = 0

        elif g_pos == -1:
            exit_trig = False; exit_p = 0.0
            if g_highs[i] >= g_sl_p:
                exit_p = g_sl_p if g_opens[i] <= g_sl_p else g_opens[i]
                exit_trig = True
            elif g_sub == "TREND" and g_lows[i] <= g_tp_p:
                exit_p = g_tp_p if g_opens[i] >= g_tp_p else g_opens[i]
                exit_trig = True
            elif g_sub == "REV" and g_lows[i] <= g_sma20[i]:
                exit_p = g_sma20[i] if g_opens[i] >= g_sma20[i] else g_opens[i]
                exit_trig = True

            if exit_trig:
                pnl = (g_entry_p - exit_p) * g_lot - (gold_spread + gold_comm) * g_lot
                trades.append({"pnl": pnl, "date": dates[i], "asset": "GOLD", "engine": g_sub, "month": m_key})
                month_cum_pnl += pnl; week_cum_pnl += pnl
                g_pos = 0

        # 2. EURUSD Exit Management (Asian Mean Reversion to SMA20)
        if e_pos == 1:
            exit_trig = False; exit_p = 0.0
            if e_lows[i] <= e_sl_p:
                exit_p = e_sl_p if e_opens[i] >= e_sl_p else e_opens[i]
                exit_trig = True
            elif e_highs[i] >= e_sma20[i]:
                exit_p = e_sma20[i] if e_opens[i] <= e_sma20[i] else e_opens[i]
                exit_trig = True

            if exit_trig:
                pnl = (exit_p - e_entry_p) * 100000.0 * (e_lot / 10.0) - (eur_spread + eur_comm) * 100000.0 * (e_lot / 10.0)
                trades.append({"pnl": pnl, "date": dates[i], "asset": "EURUSD", "engine": "REV", "month": m_key})
                month_cum_pnl += pnl; week_cum_pnl += pnl
                e_pos = 0

        elif e_pos == -1:
            exit_trig = False; exit_p = 0.0
            if e_highs[i] >= e_sl_p:
                exit_p = e_sl_p if e_opens[i] <= e_sl_p else e_opens[i]
                exit_trig = True
            elif e_lows[i] <= e_sma20[i]:
                exit_p = e_sma20[i] if e_opens[i] >= e_sma20[i] else e_opens[i]
                exit_trig = True

            if exit_trig:
                pnl = (e_entry_p - exit_p) * 100000.0 * (e_lot / 10.0) - (eur_spread + eur_comm) * 100000.0 * (e_lot / 10.0)
                trades.append({"pnl": pnl, "date": dates[i], "asset": "EURUSD", "engine": "REV", "month": m_key})
                month_cum_pnl += pnl; week_cum_pnl += pnl
                e_pos = 0

        # Evaluate Circuit Breakers after any closed trade
        if monthly_profit_lock > 0 and month_cum_pnl >= monthly_profit_lock:
            month_locked = True
        elif monthly_loss_breaker > 0 and month_cum_pnl <= -monthly_loss_breaker:
            month_locked = True
        if weekly_loss_breaker > 0 and week_cum_pnl <= -weekly_loss_breaker:
            week_locked = True

        # --- CHECK ENTRIES (Only if not locked) ---
        if not month_locked and not week_locked:
            # 1. Gold Entries
            if g_pos == 0 and g_atr[i] > 0:
                # Engine A: London / NY Trend Breakout (08:00 - 18:00 UTC)
                if 8 <= hr < 18:
                    h8 = np.max(g_highs[i - 8:i])
                    l8 = np.min(g_lows[i - 8:i])
                    if g_closes[i] > h8 and g_closes[i] > g_ema200[i]:
                        g_pos = 1
                        g_lot = 10.0 * current_risk_mult
                        g_entry_p = g_opens[i + 1] + (gold_spread * 0.5)
                        sl_d = 2.5 * g_atr[i]
                        g_sl_p = g_entry_p - sl_d
                        g_tp_p = g_entry_p + (sl_d * gold_trend_tp)
                        g_sub = "TREND"
                    elif g_closes[i] < l8 and g_closes[i] < g_ema200[i]:
                        g_pos = -1
                        g_lot = 10.0 * current_risk_mult
                        g_entry_p = g_opens[i + 1] - (gold_spread * 0.5)
                        sl_d = 2.5 * g_atr[i]
                        g_sl_p = g_entry_p + sl_d
                        g_tp_p = g_entry_p - (sl_d * gold_trend_tp)
                        g_sub = "TREND"

                # Engine B: Gold Asian Mean Reversion (21:00 - 06:00 UTC)
                elif hr >= 21 or hr < 6:
                    if g_lows[i] < g_bb_l[i] and g_closes[i] > g_bb_l[i]:
                        g_pos = 1
                        g_lot = 10.0 * current_risk_mult
                        g_entry_p = g_opens[i + 1] + (gold_spread * 0.5)
                        g_sl_p = g_entry_p - (2.0 * g_atr[i])
                        g_sub = "REV"
                    elif g_highs[i] > g_bb_u[i] and g_closes[i] < g_bb_u[i]:
                        g_pos = -1
                        g_lot = 10.0 * current_risk_mult
                        g_entry_p = g_opens[i + 1] - (gold_spread * 0.5)
                        g_sl_p = g_entry_p + (2.0 * g_atr[i])
                        g_sub = "REV"

            # 2. EURUSD Asian Reversion Entry (21:00 - 06:00 UTC)
            if e_pos == 0 and e_atr[i] > 0 and (hr >= 21 or hr < 6):
                if e_lows[i] < e_bb_l[i] and e_closes[i] > e_bb_l[i]:
                    e_pos = 1
                    e_lot = 10.0 * current_risk_mult
                    e_entry_p = e_opens[i + 1] + (eur_spread * 0.5)
                    e_sl_p = e_entry_p - (1.5 * e_atr[i])
                elif e_highs[i] > e_bb_u[i] and e_closes[i] < e_bb_u[i]:
                    e_pos = -1
                    e_lot = 10.0 * current_risk_mult
                    e_entry_p = e_opens[i + 1] - (eur_spread * 0.5)
                    e_sl_p = e_entry_p + (1.5 * e_atr[i])

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
    parser = argparse.ArgumentParser(description="Sweep Strategy 21: Multi-Asset Calendar Budget Ensemble")
    parser.add_argument("--gold_data", type=str, default="/mnt/sdcard/Download/EA/XAUUSD_M1.csv.gz", help="Path to Gold M1 data")
    parser.add_argument("--eur_data", type=str, default="/mnt/sdcard/Download/EA/EURUSD_M1.csv.gz", help="Path to EURUSD M1 data")
    parser.add_argument("--out_dir", type=str, default="/root/CFD-Trading-ML/projects/quant_strategy_discovery/results", help="Results dir")
    args = parser.parse_args()

    os.makedirs(args.out_dir, exist_ok=True)

    print(f"[*] Loading Gold M1 data from {args.gold_data}...")
    df_raw_g = pd.read_csv(
        args.gold_data,
        usecols=["datetime", "open", "high", "low", "close", "tick_volume"],
        dtype={"open": np.float32, "high": np.float32, "low": np.float32, "close": np.float32, "tick_volume": np.int32}
    )
    df_raw_g["datetime"] = pd.to_datetime(df_raw_g["datetime"])
    df_raw_g.set_index("datetime", inplace=True)
    df_raw_g.sort_index(inplace=True)
    df_m15_g = df_raw_g.resample("15min").agg({
        "open": "first", "high": "max", "low": "min", "close": "last", "tick_volume": "sum"
    }).dropna()
    print(f"[+] Loaded {len(df_m15_g):,} Gold M15 bars.")

    print(f"[*] Loading EURUSD M1 data from {args.eur_data}...")
    df_raw_e = pd.read_csv(
        args.eur_data,
        usecols=["datetime", "open", "high", "low", "close", "tick_volume"],
        dtype={"open": np.float32, "high": np.float32, "low": np.float32, "close": np.float32, "tick_volume": np.int32}
    )
    df_raw_e["datetime"] = pd.to_datetime(df_raw_e["datetime"])
    df_raw_e.set_index("datetime", inplace=True)
    df_raw_e.sort_index(inplace=True)
    df_m15_e = df_raw_e.resample("15min").agg({
        "open": "first", "high": "max", "low": "min", "close": "last", "tick_volume": "sum"
    }).dropna()
    print(f"[+] Loaded {len(df_m15_e):,} EURUSD M15 bars.")

    # Sweep parameters
    profit_locks = [250.0, 350.0, 500.0]
    loss_breakers = [150.0, 250.0, 350.0]
    weekly_breakers = [0.0, 100.0, 150.0]
    summer_factors = [0.2, 0.5, 1.0]

    total_combs = len(profit_locks) * len(loss_breakers) * len(weekly_breakers) * len(summer_factors)
    print(f"[*] Sweeping {total_combs} multi-asset calendar parameter combinations across 72 calendar months...")

    results = []
    t_start = time.time()

    for plock in profit_locks:
        for lbreak in loss_breakers:
            for wbreak in weekly_breakers:
                for sfactor in summer_factors:
                    trades = simulate_multi_asset_calendar_ensemble(
                        gold_df=df_m15_g, eur_df=df_m15_e,
                        monthly_profit_lock=plock,
                        monthly_loss_breaker=lbreak,
                        weekly_loss_breaker=wbreak,
                        summer_risk_factor=sfactor
                    )
                    m = evaluate_metrics(trades)
                    m.update({
                        "profit_lock": plock, "loss_breaker": lbreak,
                        "weekly_breaker": wbreak, "summer_factor": sfactor
                    })
                    results.append(m)

    df_res = pd.DataFrame(results)
    df_res.sort_values(by=["mcr", "net_profit"], ascending=[False, False], inplace=True)

    csv_path = os.path.join(args.out_dir, "strategy_21_multi_asset_calendar_sweep_results.csv")
    df_res.drop(columns=["monthly_series"]).to_csv(csv_path, index=False)
    print(f"[+] Saved sweep results to {csv_path}")

    champion = results[df_res.index[0]]
    champ_json_path = os.path.join(args.out_dir, "strategy_21_champion.json")
    with open(champ_json_path, "w") as f:
        json.dump(champion, f, indent=2)

    print("\n" + "="*80)
    print("STRATEGY 21: MULTI-ASSET CALENDAR ENSEMBLE - TOP CHAMPION")
    print("="*80)
    print(f"Config: ProfitLock=${champion['profit_lock']}, LossBreaker=${champion['loss_breaker']}, WeekBreaker=${champion['weekly_breaker']}, SummerFactor={champion['summer_factor']}")
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
