"""
=============================================================================
CFD QUANTITATIVE STRATEGY DISCOVERY & REVERSE-ENGINEERING
Autonomous Research Under Constitution V5.0
Candidate EA: Ghost Scalper By Triumm.mq5
Asset Focus: XAUUSD (Gold CFD) & EURUSD
Evaluation Window: 72 Calendar Months (2020-01 to 2025-12)
Execution Environment: Google Colab Cloud VM
Zero Martingale / Zero Recovery Rule: Explicit Disciplined SL & TP
=============================================================================
"""

import os
import sys
import json
import numpy as np
import pandas as pd
from datetime import datetime

# -----------------------------------------------------------------
# TECHNICAL INDICATORS
# -----------------------------------------------------------------
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

# -----------------------------------------------------------------
# SWING DETECTION ACCORDING TO GHOST SCALPER PendingIsSwing
# -----------------------------------------------------------------
def detect_ghost_swings(highs: np.ndarray, lows: np.ndarray, left_bars: int, right_bars: int):
    """
    Identifies fractal swing highs and swing lows.
    A swing at bar p is confirmed after right_bars subsequent bars close (at bar p + right_bars).
    """
    n = len(highs)
    is_swing_high = np.zeros(n, dtype=bool)
    is_swing_low = np.zeros(n, dtype=bool)
    for i in range(left_bars, n - right_bars):
        cand_h = highs[i]
        cand_l = lows[i]
        # Strict inequality on left and right
        if np.all(highs[i - left_bars:i] < cand_h) and np.all(highs[i + 1:i + right_bars + 1] < cand_h):
            is_swing_high[i] = True
        if np.all(lows[i - left_bars:i] > cand_l) and np.all(lows[i + 1:i + right_bars + 1] > cand_l):
            is_swing_low[i] = True
    return is_swing_high, is_swing_low

# -----------------------------------------------------------------
# GHOST SCALPER SINGLE LANE SIMULATION
# -----------------------------------------------------------------
def simulate_ghost_lane(opens, highs, lows, closes, atr14, ema200, kfd24,
                        hours, months, dates,
                        lane_name="GHOST_A",
                        left_bars_buy=10, right_bars_buy=7, offset_buy=-1.80,
                        left_bars_sell=10, right_bars_sell=7, offset_sell=1.80,
                        sl_val=5.0, tp_val=15.0,
                        mode="fixed", # 'fixed' (dollar points) or 'dynamic' (ATR multiplier)
                        use_session=False, start_sec=4500, end_sec=80100,
                        use_ema=False, use_kfd=False, kfd_thresh=1.42,
                        trail_activation=0.0, trail_distance=0.90, trail_step=0.30,
                        use_trailing=True,
                        plock=200.0, lbreak=250.0,
                        spread_pts=0.25, comm_dollars=0.60, point_value=100.0):
    n = len(closes)
    trades = []
    
    # Pre-compute swings
    sh_buy, _ = detect_ghost_swings(highs, lows, left_bars_buy, right_bars_buy)
    _, sl_sell = detect_ghost_swings(highs, lows, left_bars_sell, right_bars_sell)

    curr_m = months[0]
    m_pnl = 0.0
    m_locked = False

    in_pos = False
    pos_type = 0 # 1=Buy, -1=Sell
    entry_price = 0.0
    sl_price = 0.0
    tp_price = 0.0
    entry_idx = 0

    # Active pending orders
    # buy_pending: (level, signal_bar, expiry_bar)
    buy_pending_level = 0.0
    buy_pending_active = False
    sell_pending_level = 0.0
    sell_pending_active = False

    for i in range(200, n - 1):
        if months[i] != curr_m:
            curr_m = months[i]
            m_pnl = 0.0
            m_locked = False

        c_atr = atr14[i]
        c_hour = hours[i]
        sec_of_day = c_hour * 3600

        # Session filter
        if use_session:
            session_open = (sec_of_day >= start_sec and sec_of_day < end_sec)
        else:
            session_open = True

        # 1. Manage open position
        if in_pos:
            hit_tp = False
            hit_sl = False
            exit_price = 0.0

            # Trailing stop update
            if use_trailing:
                cur_dist = trail_distance * c_atr if mode == "dynamic" else trail_distance
                cur_act = trail_activation * c_atr if mode == "dynamic" else trail_activation
                cur_step = trail_step * c_atr if mode == "dynamic" else trail_step
                
                if pos_type == 1:
                    pnl_pts = highs[i] - entry_price
                    if pnl_pts >= cur_act:
                        cand_sl = highs[i] - cur_dist
                        if cand_sl > sl_price + cur_step:
                            sl_price = cand_sl
                elif pos_type == -1:
                    pnl_pts = entry_price - lows[i]
                    if pnl_pts >= cur_act:
                        cand_sl = lows[i] + cur_dist
                        if cand_sl < sl_price - cur_step:
                            sl_price = cand_sl

            # Check exit
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
                    "lane": lane_name,
                    "entry_idx": entry_idx,
                    "exit_idx": i,
                    "pos_type": pos_type,
                    "entry_price": entry_price,
                    "exit_price": exit_price,
                    "pnl": pnl,
                    "month": months[entry_idx],
                    "date": pd.to_datetime(dates[i])
                })
                m_pnl += pnl
                if m_pnl >= plock or m_pnl <= -lbreak:
                    m_locked = True
                in_pos = False
                continue

        # 2. Check pending confirmation at confirmed bar i
        # A swing at bar p = i - right_bars is confirmed at bar i
        p_buy = i - right_bars_buy
        if p_buy >= 0 and sh_buy[p_buy]:
            # New swing high confirmed!
            pivot_h = highs[p_buy]
            off = offset_buy * c_atr if mode == "dynamic" else offset_buy
            buy_pending_level = pivot_h + off
            buy_pending_active = True

        p_sell = i - right_bars_sell
        if p_sell >= 0 and sl_sell[p_sell]:
            # New swing low confirmed!
            pivot_l = lows[p_sell]
            off = offset_sell * c_atr if mode == "dynamic" else offset_sell
            sell_pending_level = pivot_l + off
            sell_pending_active = True

        # 3. Check pending fill on bar i + 1 (or during bar i)
        if not in_pos and not m_locked and session_open:
            kfd_ok = (kfd24[i] <= kfd_thresh) if use_kfd else True
            trend_bull = (closes[i] > ema200[i]) if use_ema else True
            trend_bear = (closes[i] < ema200[i]) if use_ema else True

            # Check Buy Pending fill
            if buy_pending_active and trend_bull and kfd_ok:
                # Level reached if low <= level <= high
                if lows[i] <= buy_pending_level <= highs[i]:
                    in_pos = True
                    pos_type = 1
                    entry_idx = i
                    entry_price = buy_pending_level + spread_pts
                    sl_dist = sl_val * c_atr if mode == "dynamic" else sl_val
                    tp_dist = tp_val * c_atr if mode == "dynamic" else tp_val
                    sl_price = entry_price - sl_dist
                    tp_price = entry_price + tp_dist
                    buy_pending_active = False
                elif closes[i] > buy_pending_level + (c_atr * 3.0):
                    # Market ran away too far without filling, invalidate
                    buy_pending_active = False

            # Check Sell Pending fill
            if not in_pos and sell_pending_active and trend_bear and kfd_ok:
                if lows[i] <= sell_pending_level <= highs[i]:
                    in_pos = True
                    pos_type = -1
                    entry_idx = i
                    entry_price = sell_pending_level
                    sl_dist = sl_val * c_atr if mode == "dynamic" else sl_val
                    tp_dist = tp_val * c_atr if mode == "dynamic" else tp_val
                    sl_price = entry_price + sl_dist
                    tp_price = entry_price - tp_dist
                    sell_pending_active = False
                elif closes[i] < sell_pending_level - (c_atr * 3.0):
                    sell_pending_active = False

    return trades

# -----------------------------------------------------------------
# PERFORMANCE METRICS CALCULATION
# -----------------------------------------------------------------
def calculate_metrics(trades, all_months):
    if not trades:
        return {
            "trades": 0, "net_profit": 0.0, "profit_factor": 0.0,
            "win_rate": 0.0, "max_dd": 0.0, "romad": 0.0, "mcr": 0.0,
            "profitable_months": 0, "total_months": len(all_months)
        }
    df = pd.DataFrame(trades)
    net_profit = df["pnl"].sum()
    gross_profit = df[df["pnl"] > 0]["pnl"].sum()
    gross_loss = abs(df[df["pnl"] < 0]["pnl"].sum())
    pf = (gross_profit / gross_loss) if gross_loss > 0 else (999.0 if gross_profit > 0 else 0.0)
    win_rate = (len(df[df["pnl"] > 0]) / len(df)) * 100.0

    # Drawdown
    df["cum_pnl"] = df["pnl"].cumsum()
    df["peak"] = df["cum_pnl"].cummax()
    df["dd"] = df["peak"] - df["cum_pnl"]
    max_dd = df["dd"].max() if len(df) > 0 else 0.0
    romad = (net_profit / max_dd) if max_dd > 0 else 0.0

    # Monthly consistency
    m_agg = df.groupby("month")["pnl"].sum().to_dict()
    prof_m = sum(1 for m in all_months if m_agg.get(m, 0.0) > 0)
    mcr = (prof_m / len(all_months)) * 100.0 if all_months else 0.0

    return {
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
# MULTI-LANE PORTFOLIO SIMULATION
# -----------------------------------------------------------------
def simulate_ghost_portfolio(opens, highs, lows, closes, atr14, ema200, kfd24,
                             hours, months, dates,
                             lanes_config, mode="fixed",
                             use_ema=False, use_kfd=False, kfd_thresh=1.42,
                             plock=200.0, lbreak=250.0,
                             spread_pts=0.25, comm_dollars=0.60, point_value=100.0):
    all_trades = []
    for cfg in lanes_config:
        trades = simulate_ghost_lane(
            opens, highs, lows, closes, atr14, ema200, kfd24,
            hours, months, dates,
            lane_name=cfg["name"],
            left_bars_buy=cfg["left_buy"], right_bars_buy=cfg["right_buy"], offset_buy=cfg["offset_buy"],
            left_bars_sell=cfg["left_sell"], right_bars_sell=cfg["right_sell"], offset_sell=cfg["offset_sell"],
            sl_val=cfg["sl_val"], tp_val=cfg["tp_val"],
            mode=mode,
            use_session=cfg.get("use_session", False),
            start_sec=cfg.get("start_sec", 4500), end_sec=cfg.get("end_sec", 80100),
            use_ema=use_ema, use_kfd=use_kfd, kfd_thresh=kfd_thresh,
            trail_activation=cfg["trail_act"], trail_distance=cfg["trail_dist"], trail_step=cfg["trail_step"],
            use_trailing=cfg.get("use_trailing", True),
            plock=plock, lbreak=lbreak,
            spread_pts=spread_pts, comm_dollars=comm_dollars, point_value=point_value
        )
        all_trades.extend(trades)
    
    # Sort chronologically
    all_trades.sort(key=lambda x: x["entry_idx"])
    return all_trades

# -----------------------------------------------------------------
# MAIN EXPERIMENT EXECUTION
# -----------------------------------------------------------------
def main():
    print("=" * 80)
    print("CFD QUANTITATIVE RESEARCH: GHOST SCALPER REVERSE-ENGINEERING")
    print("Evaluation Window: 72 Months (2020-2025)")
    print("Strict Zero-Martingale Discipline (Explicit SL/TP)")
    print("=" * 80)

    # Search for data
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
        print(f"[-] ERROR: XAUUSD_H1.parquet not found in {data_paths}")
        sys.exit(1)

    print(f"[+] Loading XAUUSD data from: {xau_path}")
    df = pd.read_parquet(xau_path)
    if not isinstance(df.index, pd.DatetimeIndex):
        if "time" in df.columns:
            df["time"] = pd.to_datetime(df["time"])
            df = df.set_index("time")
        else:
            df.index = pd.to_datetime(df.index)
    df = df.sort_index()

    # 72 Months filter: 2020 to 2025
    df = df[(df.index >= "2020-01-01") & (df.index < "2026-01-01")]
    print(f"[+] Loaded {len(df)} H1 bars from {df.index[0]} to {df.index[-1]}")

    opens = df["open"].values.astype(np.float64)
    highs = df["high"].values.astype(np.float64)
    lows = df["low"].values.astype(np.float64)
    closes = df["close"].values.astype(np.float64)
    dates = df.index
    hours = dates.hour.values.astype(np.int32)
    months = (dates.year.values * 100 + dates.month.values).astype(np.int32)
    all_months = sorted(list(set(months)))
    print(f"[+] Total Calendar Months: {len(all_months)}")

    atr14 = compute_atr(highs, lows, closes, 14)
    ema200 = compute_ema(closes, 200)
    kfd24 = compute_katz_fractal_dimension(closes, 24)

    # -------------------------------------------------------------
    # 4 GHOST LANES DEFINITIONS (FROM Ghost Scalper By Triumm.mq5)
    # -------------------------------------------------------------
    lanes_config = [
        {
            "name": "GHOST_A",
            "left_buy": 10, "right_buy": 7, "offset_buy": -1.80,
            "left_sell": 10, "right_sell": 7, "offset_sell": 1.80,
            "sl_val": 5.00, "tp_val": 15.00,
            "trail_act": 0.0, "trail_dist": 0.90, "trail_step": 0.30,
            "use_session": False
        },
        {
            "name": "GHOST_B",
            "left_buy": 13, "right_buy": 3, "offset_buy": -1.50,
            "left_sell": 10, "right_sell": 4, "offset_sell": 1.90,
            "sl_val": 5.00, "tp_val": 25.00,
            "trail_act": 0.15, "trail_dist": 1.15, "trail_step": 0.40,
            "use_session": True, "start_sec": 4500, "end_sec": 80100
        },
        {
            "name": "GHOST_C",
            "left_buy": 7, "right_buy": 5, "offset_buy": -2.20,
            "left_sell": 7, "right_sell": 5, "offset_sell": 2.20,
            "sl_val": 10.00, "tp_val": 25.00,
            "trail_act": 0.15, "trail_dist": 0.90, "trail_step": 0.20,
            "use_session": False
        },
        {
            "name": "GHOST_D",
            "left_buy": 26, "right_buy": 20, "offset_buy": -1.80,
            "left_sell": 26, "right_sell": 20, "offset_sell": 1.80,
            "sl_val": 8.00, "tp_val": 17.00,
            "trail_act": 1.00, "trail_dist": 0.35, "trail_step": 0.55,
            "use_session": False
        }
    ]

    results = {}

    # =============================================================
    # EXPERIMENT 1: RAW SOURCE CODE BASELINE (Fixed Dollar Points)
    # =============================================================
    print("\n" + "=" * 60)
    print("PHASE 1: RAW GHOST SCALPER SOURCE CODE BASELINE (Fixed Dollar Points)")
    print("=" * 60)

    for cfg in lanes_config:
        lane_name = cfg["name"]
        trades = simulate_ghost_lane(
            opens, highs, lows, closes, atr14, ema200, kfd24,
            hours, months, dates,
            lane_name=lane_name,
            left_bars_buy=cfg["left_buy"], right_bars_buy=cfg["right_buy"], offset_buy=cfg["offset_buy"],
            left_bars_sell=cfg["left_sell"], right_bars_sell=cfg["right_sell"], offset_sell=cfg["offset_sell"],
            sl_val=cfg["sl_val"], tp_val=cfg["tp_val"],
            mode="fixed",
            use_session=cfg.get("use_session", False),
            start_sec=cfg.get("start_sec", 4500), end_sec=cfg.get("end_sec", 80100),
            use_ema=False, use_kfd=False,
            trail_activation=cfg["trail_act"], trail_distance=cfg["trail_dist"], trail_step=cfg["trail_step"],
            use_trailing=True, plock=999999.0, lbreak=999999.0
        )
        m = calculate_metrics(trades, all_months)
        results[f"Raw_{lane_name}"] = m
        print(f"[{lane_name} RAW] Trades: {m['trades']:3d} | Net PnL: ${m['net_profit']:10.2f} | PF: {m['profit_factor']:.3f} | WinRate: {m['win_rate']:.1f}% | MaxDD: ${m['max_dd']:8.2f} | MCR: {m['mcr']:.1f}%")

    # Combined Raw Portfolio (All 4 lanes)
    raw_port_trades = simulate_ghost_portfolio(
        opens, highs, lows, closes, atr14, ema200, kfd24,
        hours, months, dates,
        lanes_config=lanes_config, mode="fixed",
        use_ema=False, use_kfd=False,
        plock=999999.0, lbreak=999999.0
    )
    raw_port_m = calculate_metrics(raw_port_trades, all_months)
    results["Raw_Portfolio_All_4_Lanes"] = raw_port_m
    print(f"\n[RAW 4-LANE PORTFOLIO] Trades: {raw_port_m['trades']:3d} | Net PnL: ${raw_port_m['net_profit']:10.2f} | PF: {raw_port_m['profit_factor']:.3f} | MaxDD: ${raw_port_m['max_dd']:8.2f} | RoMaD: {raw_port_m['romad']:.2f}x | MCR: {raw_port_m['mcr']:.1f}%")

    # =============================================================
    # EXPERIMENT 2: QUANTITATIVE ENHANCEMENT - SECULAR TREND & NOISE GATE
    # =============================================================
    print("\n" + "=" * 60)
    print("PHASE 2: GHOST SCALPER + 200 EMA TREND + KATZ FRACTAL DIMENSION GATING")
    print("=" * 60)

    for cfg in lanes_config:
        lane_name = cfg["name"]
        trades = simulate_ghost_lane(
            opens, highs, lows, closes, atr14, ema200, kfd24,
            hours, months, dates,
            lane_name=lane_name,
            left_bars_buy=cfg["left_buy"], right_bars_buy=cfg["right_buy"], offset_buy=cfg["offset_buy"],
            left_bars_sell=cfg["left_sell"], right_bars_sell=cfg["right_sell"], offset_sell=cfg["offset_sell"],
            sl_val=cfg["sl_val"], tp_val=cfg["tp_val"],
            mode="fixed",
            use_session=cfg.get("use_session", False),
            start_sec=cfg.get("start_sec", 4500), end_sec=cfg.get("end_sec", 80100),
            use_ema=True, use_kfd=True, kfd_thresh=1.42,
            trail_activation=cfg["trail_act"], trail_distance=cfg["trail_dist"], trail_step=cfg["trail_step"],
            use_trailing=True, plock=999999.0, lbreak=999999.0
        )
        m = calculate_metrics(trades, all_months)
        results[f"Enhanced_TrendFilter_{lane_name}"] = m
        print(f"[{lane_name} + TREND+KFD] Trades: {m['trades']:3d} | Net PnL: ${m['net_profit']:10.2f} | PF: {m['profit_factor']:.3f} | WinRate: {m['win_rate']:.1f}% | MaxDD: ${m['max_dd']:8.2f} | MCR: {m['mcr']:.1f}%")

    filtered_port_trades = simulate_ghost_portfolio(
        opens, highs, lows, closes, atr14, ema200, kfd24,
        hours, months, dates,
        lanes_config=lanes_config, mode="fixed",
        use_ema=True, use_kfd=True, kfd_thresh=1.42,
        plock=999999.0, lbreak=999999.0
    )
    filtered_port_m = calculate_metrics(filtered_port_trades, all_months)
    results["Enhanced_Portfolio_Trend_KFD"] = filtered_port_m
    print(f"\n[ENHANCED 4-LANE PORTFOLIO (+EMA+KFD)] Trades: {filtered_port_m['trades']:3d} | Net PnL: ${filtered_port_m['net_profit']:10.2f} | PF: {filtered_port_m['profit_factor']:.3f} | MaxDD: ${filtered_port_m['max_dd']:8.2f} | RoMaD: {filtered_port_m['romad']:.2f}x | MCR: {filtered_port_m['mcr']:.1f}%")

    # =============================================================
    # EXPERIMENT 3: DYNAMIC VOLATILITY-ADAPTIVE ATR MULTIPLIERS
    # =============================================================
    print("\n" + "=" * 60)
    print("PHASE 3: VOLATILITY-ADAPTIVE DYNAMIC ATR MULTIPLIERS (GRID SEARCH)")
    print("=" * 60)

    # Convert fixed points to ATR equivalents and sweep ATR multipliers
    # Gold ATR H1 average ~ $6-$10.
    best_dynamic = None
    best_dynamic_pf = 0.0

    sl_mults = [1.5, 2.0, 2.5]
    tp_mults = [3.0, 4.0, 5.0]
    offset_mults = [0.15, 0.25]

    for sl_m in sl_mults:
        for tp_m in tp_mults:
            for off_m in offset_mults:
                dynamic_lanes = []
                for cfg in lanes_config:
                    c = cfg.copy()
                    c["sl_val"] = sl_m
                    c["tp_val"] = tp_m
                    c["offset_buy"] = -off_m
                    c["offset_sell"] = off_m
                    c["trail_dist"] = 0.5 * sl_m
                    c["trail_step"] = 0.25 * sl_m
                    dynamic_lanes.append(c)

                d_trades = simulate_ghost_portfolio(
                    opens, highs, lows, closes, atr14, ema200, kfd24,
                    hours, months, dates,
                    lanes_config=dynamic_lanes, mode="dynamic",
                    use_ema=True, use_kfd=True, kfd_thresh=1.42,
                    plock=999999.0, lbreak=999999.0
                )
                m = calculate_metrics(d_trades, all_months)
                tag = f"Dynamic_SL{sl_m}_TP{tp_m}_Off{off_m}"
                if m["trades"] >= 50 and m["profit_factor"] > best_dynamic_pf:
                    best_dynamic_pf = m["profit_factor"]
                    best_dynamic = (tag, m)
                    print(f"[*] NEW BEST DYNAMIC COMBO -> {tag}: Trades={m['trades']} | Net=${m['net_profit']} | PF={m['profit_factor']:.3f} | DD=${m['max_dd']} | RoMaD={m['romad']:.2f}x | MCR={m['mcr']:.1f}%")

    if best_dynamic:
        results["Best_Dynamic_Portfolio"] = {
            "config": best_dynamic[0],
            "metrics": best_dynamic[1]
        }

    # =============================================================
    # EXPERIMENT 4: ASAR CALENDAR RISK GOVERNANCE (+ Monthly Lock)
    # =============================================================
    print("\n" + "=" * 60)
    print("PHASE 4: ASAR CALENDAR RISK GOVERNANCE ON BEST CANDIDATE")
    print("=" * 60)

    asar_trades = simulate_ghost_portfolio(
        opens, highs, lows, closes, atr14, ema200, kfd24,
        hours, months, dates,
        lanes_config=lanes_config, mode="fixed",
        use_ema=True, use_kfd=True, kfd_thresh=1.42,
        plock=200.0, lbreak=250.0
    )
    asar_m = calculate_metrics(asar_trades, all_months)
    results["ASAR_Governed_Ghost_Portfolio"] = asar_m
    print(f"[ASAR GOVERNED 4-LANE PORTFOLIO] Trades: {asar_m['trades']:3d} | Net PnL: ${asar_m['net_profit']:10.2f} | PF: {asar_m['profit_factor']:.3f} | MaxDD: ${asar_m['max_dd']:8.2f} | RoMaD: {asar_m['romad']:.2f}x | MCR: {asar_m['mcr']:.1f}%")

    # =============================================================
    # EXPERIMENT 5: CROSS-ASSET VALIDATION (EURUSD H1)
    # =============================================================
    print("\n" + "=" * 60)
    print("PHASE 5: CROSS-ASSET VALIDATION ON EURUSD H1 (72 Months)")
    print("=" * 60)

    eur_paths = [
        "projects/quant_strategy_discovery/data/EURUSD_H1.parquet",
        "/content/CFD-Trading-ML/projects/quant_strategy_discovery/data/EURUSD_H1.parquet",
        "data/EURUSD_H1.parquet"
    ]
    eur_path = None
    for p in eur_paths:
        if os.path.exists(p):
            eur_path = p
            break

    if eur_path:
        eur_df = pd.read_parquet(eur_path)
        if not isinstance(eur_df.index, pd.DatetimeIndex):
            if "time" in eur_df.columns:
                eur_df["time"] = pd.to_datetime(eur_df["time"])
                eur_df = eur_df.set_index("time")
            else:
                eur_df.index = pd.to_datetime(eur_df.index)
        eur_df = eur_df.sort_index()
        eur_df = eur_df[(eur_df.index >= "2020-01-01") & (eur_df.index < "2026-01-01")]

        eur_opens = eur_df["open"].values.astype(np.float64)
        eur_highs = eur_df["high"].values.astype(np.float64)
        eur_lows = eur_df["low"].values.astype(np.float64)
        eur_closes = eur_df["close"].values.astype(np.float64)
        eur_dates = eur_df.index
        eur_hours = eur_dates.hour.values.astype(np.int32)
        eur_months = (eur_dates.year.values * 100 + eur_dates.month.values).astype(np.int32)
        eur_all_months = sorted(list(set(eur_months)))

        eur_atr14 = compute_atr(eur_highs, eur_lows, eur_closes, 14)
        eur_ema200 = compute_ema(eur_closes, 200)
        eur_kfd24 = compute_katz_fractal_dimension(eur_closes, 24)

        # EURUSD: point_value=100,000, spread=0.00010 (1.0 pip), comm=$0.60
        # Dynamic mode is required for EURUSD because fixed dollar points ($5/$15) are meaningless on Forex
        eur_dynamic_lanes = []
        for cfg in lanes_config:
            c = cfg.copy()
            c["sl_val"] = 2.0
            c["tp_val"] = 4.0
            c["offset_buy"] = -0.2
            c["offset_sell"] = 0.2
            c["trail_dist"] = 1.0
            c["trail_step"] = 0.5
            eur_dynamic_lanes.append(c)

        eur_trades = simulate_ghost_portfolio(
            eur_opens, eur_highs, eur_lows, eur_closes, eur_atr14, eur_ema200, eur_kfd24,
            eur_hours, eur_months, eur_dates,
            lanes_config=eur_dynamic_lanes, mode="dynamic",
            use_ema=True, use_kfd=True, kfd_thresh=1.42,
            plock=200.0, lbreak=250.0,
            spread_pts=0.00010, comm_dollars=0.60, point_value=100000.0
        )
        eur_m = calculate_metrics(eur_trades, eur_all_months)
        results["EURUSD_Ghost_Portfolio_Dynamic"] = eur_m
        print(f"[EURUSD DYNAMIC GHOST PORTFOLIO] Trades: {eur_m['trades']:3d} | Net PnL: ${eur_m['net_profit']:10.2f} | PF: {eur_m['profit_factor']:.3f} | MaxDD: ${eur_m['max_dd']:8.2f} | RoMaD: {eur_m['romad']:.2f}x | MCR: {eur_m['mcr']:.1f}%")

    # -------------------------------------------------------------
    # SAVE JSON AUDIT RECORD
    # -------------------------------------------------------------
    out_dir = "projects/quant_strategy_discovery/results"
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, "ghost_scalper_clean_quant_results.json")
    with open(out_path, "w") as f:
        json.dump(results, f, indent=2)
    print(f"\n[+] Results saved successfully to {out_path}")
    print("=" * 80)

if __name__ == "__main__":
    main()
