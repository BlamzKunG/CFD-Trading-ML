"""
=============================================================================
CFD QUANTITATIVE STRATEGY DISCOVERY & REVERSE-ENGINEERING
Autonomous Research Under Constitution V5.0
Portfolio Study: Reverse-Engineered Multi-Engine Sovereign Ensemble
Engines:
  1. Quantum Titan Core B (H1 Swing Pivot Pullback, SL 2.5x, TP 3.5x ATR)
  2. Ghost Scalper Lane A (H1 Medium Swing, SL $5.00, TP $15.00)
  3. Ghost Scalper Lane B (H1 Fast Swing + Session, SL $5.00, TP $25.00)
  4. Ghost Scalper Lane C (H1 Micro Swing, SL $10.00, TP $25.00)
  5. Ghost Scalper Lane D (H1 Macro Swing, SL $8.00, TP $17.00)
Asset: XAUUSD (Gold CFD) | 72 Months (2020-01 to 2025-12)
Execution Environment: Google Colab Cloud VM
Zero Martingale / Zero Recovery Rule: Pure Disciplined Stop Loss & Take Profit
=============================================================================
"""

import os
import sys
import json
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
        tr[i] = max(hl, hc, lc)
    atr = np.zeros(n, dtype=np.float64)
    atr[period - 1] = np.mean(tr[:period])
    alpha = 1.0 / period
    for i in range(period, n):
        atr[i] = (atr[i - 1] * (1.0 - alpha)) + (tr[i] * alpha)
    return atr

def compute_ema(series: np.ndarray, period: int) -> np.ndarray:
    n = len(series)
    ema = np.zeros(n, dtype=np.float64)
    ema[0] = series[0]
    alpha = 2.0 / (period + 1.0)
    for i in range(1, n):
        ema[i] = (series[i] * alpha) + (ema[i - 1] * (1.0 - alpha))
    return ema

def compute_katz_fractal_dimension(closes: np.ndarray, period: int = 24) -> np.ndarray:
    n = len(closes)
    kfd = np.full(n, 1.5, dtype=np.float64)
    for i in range(period, n):
        window = closes[i - period:i + 1]
        ll = np.sum(np.abs(np.diff(window)))
        d = np.max(np.abs(window - window[0]))
        if ll > 0 and d > 0:
            k = np.log10(period) / (np.log10(period) + np.log10(d / ll))
            kfd[i] = max(1.0, min(2.0, k))
        else:
            kfd[i] = 1.5
    return kfd

def detect_ghost_swings(highs: np.ndarray, lows: np.ndarray, left_bars: int, right_bars: int):
    n = len(highs)
    is_swing_high = np.zeros(n, dtype=bool)
    is_swing_low = np.zeros(n, dtype=bool)
    for i in range(left_bars, n - right_bars):
        cand_h = highs[i]
        cand_l = lows[i]
        if np.all(highs[i - left_bars:i] < cand_h) and np.all(highs[i + 1:i + right_bars + 1] < cand_h):
            is_swing_high[i] = True
        if np.all(lows[i - left_bars:i] > cand_l) and np.all(lows[i + 1:i + right_bars + 1] > cand_l):
            is_swing_low[i] = True
    return is_swing_high, is_swing_low

# -----------------------------------------------------------------
# SIMULATE QUANTUM TITAN CORE B
# -----------------------------------------------------------------
def simulate_quantum_titan_core_b(opens, highs, lows, closes, atr14, ema200, kfd24,
                                   months, dates,
                                   lookback=30, pullback_atr=0.5, sl_mult=2.5, tp_mult=3.5,
                                   kfd_thresh=1.42, spread_pts=0.25, comm_dollars=0.60, point_value=100.0):
    n = len(closes)
    trades = []
    in_pos = False
    pos_type = 0
    entry_price = 0.0
    sl_price = 0.0
    tp_price = 0.0
    entry_idx = 0

    p_high = pd.Series(highs).rolling(lookback).max().shift(1).values
    p_low = pd.Series(lows).rolling(lookback).min().shift(1).values

    for i in range(200, n - 1):
        c_atr = atr14[i]

        if in_pos:
            hit_tp = False
            hit_sl = False
            exit_price = 0.0

            if pos_type == 1:
                if lows[i] <= sl_price:
                    hit_sl = True
                    exit_price = sl_price
                elif highs[i] >= tp_price:
                    hit_tp = True
                    exit_price = tp_price
            elif pos_type == -1:
                if highs[i] >= sl_price:
                    hit_sl = True
                    exit_price = sl_price
                elif lows[i] <= tp_price:
                    hit_tp = True
                    exit_price = tp_price

            if hit_tp or hit_sl:
                if pos_type == 1:
                    pnl = (exit_price - entry_price) * point_value - comm_dollars
                else:
                    pnl = (entry_price - exit_price) * point_value - comm_dollars

                trades.append({
                    "engine": "QuantumTitan_CoreB",
                    "entry_idx": entry_idx, "exit_idx": i,
                    "pos_type": pos_type, "entry_price": entry_price, "exit_price": exit_price,
                    "pnl": pnl, "month": months[entry_idx], "date": pd.to_datetime(dates[i])
                })
                in_pos = False
                continue

        if not in_pos:
            kfd_ok = (kfd24[i] <= kfd_thresh)
            trend_bull = (closes[i] > ema200[i])
            trend_bear = (closes[i] < ema200[i])

            buy_pullback = (closes[i] <= p_high[i] - pullback_atr * c_atr) and (closes[i - 1] > p_high[i] - pullback_atr * c_atr)
            sell_pullback = (closes[i] >= p_low[i] + pullback_atr * c_atr) and (closes[i - 1] < p_low[i] + pullback_atr * c_atr)

            if buy_pullback and trend_bull and kfd_ok:
                in_pos = True
                pos_type = 1
                entry_idx = i + 1
                entry_price = opens[i + 1] + spread_pts
                sl_price = entry_price - (sl_mult * c_atr)
                tp_price = entry_price + (tp_mult * c_atr)
            elif sell_pullback and trend_bear and kfd_ok:
                in_pos = True
                pos_type = -1
                entry_idx = i + 1
                entry_price = opens[i + 1]
                sl_price = entry_price + (sl_mult * c_atr)
                tp_price = entry_price - (tp_mult * c_atr)

    return trades

# -----------------------------------------------------------------
# SIMULATE GHOST SCALPER LANE
# -----------------------------------------------------------------
def simulate_ghost_lane(opens, highs, lows, closes, atr14, ema200, kfd24,
                        hours, months, dates,
                        lane_name="Ghost_A",
                        left_bars_buy=10, right_bars_buy=7, offset_buy=-1.80,
                        left_bars_sell=10, right_bars_sell=7, offset_sell=1.80,
                        sl_val=5.0, tp_val=15.0,
                        use_session=False, start_sec=4500, end_sec=80100,
                        trail_activation=0.0, trail_distance=0.90, trail_step=0.30,
                        kfd_thresh=1.42, spread_pts=0.25, comm_dollars=0.60, point_value=100.0):
    n = len(closes)
    trades = []
    
    sh_buy, _ = detect_ghost_swings(highs, lows, left_bars_buy, right_bars_buy)
    _, sl_sell = detect_ghost_swings(highs, lows, left_bars_sell, right_bars_sell)

    in_pos = False
    pos_type = 0
    entry_price = 0.0
    sl_price = 0.0
    tp_price = 0.0
    entry_idx = 0

    buy_pending_level = 0.0
    buy_pending_active = False
    sell_pending_level = 0.0
    sell_pending_active = False

    for i in range(200, n - 1):
        c_atr = atr14[i]
        sec_of_day = hours[i] * 3600
        session_open = (sec_of_day >= start_sec and sec_of_day < end_sec) if use_session else True

        if in_pos:
            hit_tp = False
            hit_sl = False
            exit_price = 0.0

            # Trailing stop
            if pos_type == 1:
                pnl_pts = highs[i] - entry_price
                if pnl_pts >= trail_activation:
                    cand_sl = highs[i] - trail_distance
                    if cand_sl > sl_price + trail_step:
                        sl_price = cand_sl
            elif pos_type == -1:
                pnl_pts = entry_price - lows[i]
                if pnl_pts >= trail_activation:
                    cand_sl = lows[i] + trail_distance
                    if cand_sl < sl_price - trail_step:
                        sl_price = cand_sl

            # Exit
            if pos_type == 1:
                if lows[i] <= sl_price:
                    hit_sl = True
                    exit_price = sl_price
                elif highs[i] >= tp_price:
                    hit_tp = True
                    exit_price = tp_price
            elif pos_type == -1:
                if highs[i] >= sl_price:
                    hit_sl = True
                    exit_price = sl_price
                elif lows[i] <= tp_price:
                    hit_tp = True
                    exit_price = tp_price

            if hit_tp or hit_sl:
                if pos_type == 1:
                    pnl = (exit_price - entry_price) * point_value - comm_dollars
                else:
                    pnl = (entry_price - exit_price) * point_value - comm_dollars

                trades.append({
                    "engine": lane_name,
                    "entry_idx": entry_idx, "exit_idx": i,
                    "pos_type": pos_type, "entry_price": entry_price, "exit_price": exit_price,
                    "pnl": pnl, "month": months[entry_idx], "date": pd.to_datetime(dates[i])
                })
                in_pos = False
                continue

        p_buy = i - right_bars_buy
        if p_buy >= 0 and sh_buy[p_buy]:
            buy_pending_level = highs[p_buy] + offset_buy
            buy_pending_active = True

        p_sell = i - right_bars_sell
        if p_sell >= 0 and sl_sell[p_sell]:
            sell_pending_level = lows[p_sell] + offset_sell
            sell_pending_active = True

        if not in_pos and session_open:
            kfd_ok = (kfd24[i] <= kfd_thresh)
            trend_bull = (closes[i] > ema200[i])
            trend_bear = (closes[i] < ema200[i])

            if buy_pending_active and trend_bull and kfd_ok:
                if lows[i] <= buy_pending_level <= highs[i]:
                    in_pos = True
                    pos_type = 1
                    entry_idx = i
                    entry_price = buy_pending_level + spread_pts
                    sl_price = entry_price - sl_val
                    tp_price = entry_price + tp_val
                    buy_pending_active = False
                elif closes[i] > buy_pending_level + (c_atr * 3.0):
                    buy_pending_active = False

            if not in_pos and sell_pending_active and trend_bear and kfd_ok:
                if lows[i] <= sell_pending_level <= highs[i]:
                    in_pos = True
                    pos_type = -1
                    entry_idx = i
                    entry_price = sell_pending_level
                    sl_price = entry_price + sl_val
                    tp_price = entry_price - tp_val
                    sell_pending_active = False
                elif closes[i] < sell_pending_level - (c_atr * 3.0):
                    sell_pending_active = False

    return trades

# -----------------------------------------------------------------
# METRICS CALCULATION
# -----------------------------------------------------------------
def calculate_metrics(trades, all_months, label=""):
    if not trades:
        return {
            "label": label, "trades": 0, "net_profit": 0.0, "profit_factor": 0.0,
            "win_rate": 0.0, "max_dd": 0.0, "romad": 0.0, "mcr": 0.0,
            "profitable_months": 0, "total_months": len(all_months)
        }
    df = pd.DataFrame(trades)
    net_profit = df["pnl"].sum()
    gross_profit = df[df["pnl"] > 0]["pnl"].sum()
    gross_loss = abs(df[df["pnl"] < 0]["pnl"].sum())
    pf = (gross_profit / gross_loss) if gross_loss > 0 else (999.0 if gross_profit > 0 else 0.0)
    win_rate = (len(df[df["pnl"] > 0]) / len(df)) * 100.0

    df["cum_pnl"] = df["pnl"].cumsum()
    df["peak"] = df["cum_pnl"].cummax()
    df["dd"] = df["peak"] - df["cum_pnl"]
    max_dd = df["dd"].max() if len(df) > 0 else 0.0
    romad = (net_profit / max_dd) if max_dd > 0 else 0.0

    m_agg = df.groupby("month")["pnl"].sum().to_dict()
    prof_m = sum(1 for m in all_months if m_agg.get(m, 0.0) > 0)
    mcr = (prof_m / len(all_months)) * 100.0 if all_months else 0.0

    return {
        "label": label,
        "trades": len(df),
        "net_profit": round(float(net_profit), 2),
        "profit_factor": round(float(pf), 3),
        "win_rate": round(float(win_rate), 2),
        "max_dd": round(float(max_dd), 2),
        "romad": round(float(romad), 2),
        "mcr": round(float(mcr), 2),
        "profitable_months": prof_m,
        "total_months": len(all_months)
    }

# -----------------------------------------------------------------
# MAIN EXPERIMENT EXECUTION
# -----------------------------------------------------------------
def main():
    print("=" * 85)
    print("CFD QUANTITATIVE DISCOVERY: REVERSE-ENGINEERED SOVEREIGN ENSEMBLE")
    print("Quantum Titan Core B + Ghost Scalper (A, B, C, D)")
    print("Strict Zero-Martingale Discipline (Pure Single-Order SL & TP)")
    print("=" * 85)

    data_paths = [
        "projects/quant_strategy_discovery/data/XAUUSD_H1.parquet",
        "/content/CFD-Trading-ML/projects/quant_strategy_discovery/data/XAUUSD_H1.parquet",
        "data/XAUUSD_H1.parquet"
    ]
    xau_path = None
    for p in data_paths:
        if os.path.exists(p):
            xau_path = p
            break

    if not xau_path:
        print(f"[-] ERROR: Dataset not found in {data_paths}")
        sys.exit(1)

    print(f"[+] Loading XAUUSD H1 dataset from: {xau_path}")
    df = pd.read_parquet(xau_path)
    if not isinstance(df.index, pd.DatetimeIndex):
        if "time" in df.columns:
            df["time"] = pd.to_datetime(df["time"])
            df = df.set_index("time")
        else:
            df.index = pd.to_datetime(df.index)
    df = df.sort_index()
    df = df[(df.index >= "2020-01-01") & (df.index < "2026-01-01")]

    opens = df["open"].values.astype(np.float64)
    highs = df["high"].values.astype(np.float64)
    lows = df["low"].values.astype(np.float64)
    closes = df["close"].values.astype(np.float64)
    dates = df.index
    hours = dates.hour.values.astype(np.int32)
    months = (dates.year.values * 100 + dates.month.values).astype(np.int32)
    all_months = sorted(list(set(months)))
    print(f"[+] Loaded {len(df)} H1 bars across {len(all_months)} calendar months.")

    atr14 = compute_atr(highs, lows, closes, 14)
    ema200 = compute_ema(closes, 200)
    kfd24 = compute_katz_fractal_dimension(closes, 24)

    # 1. Run Quantum Titan Core B
    print("\n[*] Simulating Engine 1: Quantum Titan Core B (Pivot Pullback)...")
    tr_titan = simulate_quantum_titan_core_b(
        opens, highs, lows, closes, atr14, ema200, kfd24,
        months, dates, lookback=30, pullback_atr=0.5, sl_mult=2.5, tp_mult=3.5, kfd_thresh=1.42
    )
    m_titan = calculate_metrics(tr_titan, all_months, "Quantum_Titan_CoreB")
    print(f"[Engine 1: Quantum Titan Core B] Trades: {m_titan['trades']:4d} | Net: ${m_titan['net_profit']:10.2f} | PF: {m_titan['profit_factor']:.3f} | MaxDD: ${m_titan['max_dd']:8.2f} | MCR: {m_titan['mcr']:.1f}%")

    # 2. Run Ghost Scalper Lanes
    print("\n[*] Simulating Ghost Scalper Lanes (A, B, C, D)...")
    lanes_config = [
        {"name": "Ghost_A", "left_buy": 10, "right_buy": 7, "offset_buy": -1.80, "left_sell": 10, "right_sell": 7, "offset_sell": 1.80, "sl": 5.0, "tp": 15.0, "use_sess": False, "act": 0.0, "dist": 0.90, "step": 0.30},
        {"name": "Ghost_B", "left_buy": 13, "right_buy": 3, "offset_buy": -1.50, "left_sell": 10, "right_sell": 4, "offset_sell": 1.90, "sl": 5.0, "tp": 25.0, "use_sess": True, "act": 0.15, "dist": 1.15, "step": 0.40},
        {"name": "Ghost_C", "left_buy": 7, "right_buy": 5, "offset_buy": -2.20, "left_sell": 7, "right_sell": 5, "offset_sell": 2.20, "sl": 10.0, "tp": 25.0, "use_sess": False, "act": 0.15, "dist": 0.90, "step": 0.20},
        {"name": "Ghost_D", "left_buy": 26, "right_buy": 20, "offset_buy": -1.80, "left_sell": 26, "right_sell": 20, "offset_sell": 1.80, "sl": 8.0, "tp": 17.0, "use_sess": False, "act": 1.00, "dist": 0.35, "step": 0.55}
    ]

    ghost_trades = []
    for cfg in lanes_config:
        tr = simulate_ghost_lane(
            opens, highs, lows, closes, atr14, ema200, kfd24,
            hours, months, dates,
            lane_name=cfg["name"],
            left_bars_buy=cfg["left_buy"], right_bars_buy=cfg["right_buy"], offset_buy=cfg["offset_buy"],
            left_bars_sell=cfg["left_sell"], right_bars_sell=cfg["right_sell"], offset_sell=cfg["offset_sell"],
            sl_val=cfg["sl"], tp_val=cfg["tp"],
            use_session=cfg["use_sess"],
            trail_activation=cfg["act"], trail_distance=cfg["dist"], trail_step=cfg["step"],
            kfd_thresh=1.42
        )
        m = calculate_metrics(tr, all_months, cfg["name"])
        print(f"[Engine: {cfg['name']:7s}] Trades: {m['trades']:4d} | Net: ${m['net_profit']:10.2f} | PF: {m['profit_factor']:.3f} | MaxDD: ${m['max_dd']:8.2f} | MCR: {m['mcr']:.1f}%")
        ghost_trades.extend(tr)

    # 3. Combined Sovereign Ensemble (Titan + Ghost A + B + C + D)
    print("\n" + "=" * 85)
    print("PHASE 3: COMBINED 5-ENGINE SOVEREIGN ENSEMBLE BACKTEST")
    print("=" * 85)
    all_ensemble_trades = tr_titan + ghost_trades
    all_ensemble_trades.sort(key=lambda x: x["entry_idx"])

    m_ensemble = calculate_metrics(all_ensemble_trades, all_months, "Titan_Ghost_Sovereign_Ensemble")
    print(f"\n[TITAN + GHOST 5-ENGINE SOVEREIGN ENSEMBLE]")
    print(f"Total Trades:           {m_ensemble['trades']}")
    print(f"Net Profit:             ${m_ensemble['net_profit']:,.2f} USD")
    print(f"Profit Factor (PF):     {m_ensemble['profit_factor']:.3f} 🏆")
    print(f"Win Rate:               {m_ensemble['win_rate']:.2f}%")
    print(f"Max Drawdown:           ${m_ensemble['max_dd']:,.2f} USD")
    print(f"Return on Max DD:       {m_ensemble['romad']:.2f}x 🏆")
    print(f"Monthly Consistency:    {m_ensemble['mcr']:.2f}% ({m_ensemble['profitable_months']}/{m_ensemble['total_months']} months profitable) 🏆")

    # Save results
    out_dir = "projects/quant_strategy_discovery/results"
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, "titan_ghost_sovereign_ensemble_results.json")
    results = {
        "Quantum_Titan_CoreB": m_titan,
        "Ghost_Scalper_Enhanced_Portfolio": calculate_metrics(ghost_trades, all_months, "Ghost_Enhanced"),
        "Titan_Ghost_Sovereign_Ensemble": m_ensemble
    }
    with open(out_path, "w") as f:
        json.dump(results, f, indent=2)
    print(f"\n[+] Results saved successfully to {out_path}")
    print("=" * 85)

if __name__ == "__main__":
    main()
