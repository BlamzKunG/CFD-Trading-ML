"""
=============================================================================
CFD QUANTITATIVE STRATEGY DISCOVERY & REVERSE-ENGINEERING
Autonomous Research Under Constitution V5.0
Candidate EA: One Shoot AI V4.mq5
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
# PIVOT WING DETECTION (ONE SHOOT AI V4 ALGORITHM)
# -----------------------------------------------------------------
def detect_wing_pivots(highs: np.ndarray, lows: np.ndarray, wing: int = 2):
    n = len(highs)
    is_p_high = np.zeros(n, dtype=bool)
    is_p_low = np.zeros(n, dtype=bool)
    for i in range(wing, n - wing):
        cand_h = highs[i]
        cand_l = lows[i]
        # Strict inequality
        if np.all(highs[i - wing:i] < cand_h) and np.all(highs[i + 1:i + wing + 1] <= cand_h):
            is_p_high[i] = True
        if np.all(lows[i - wing:i] > cand_l) and np.all(lows[i + 1:i + wing + 1] >= cand_l):
            is_p_low[i] = True
    return is_p_high, is_p_low

# -----------------------------------------------------------------
# SIMULATION ENGINE: ONE SHOOT AI V4
# -----------------------------------------------------------------
def simulate_one_shoot(opens, highs, lows, closes, atr14, ema34, ema200, kfd24,
                       months, dates,
                       wing=2, buffer_price=0.01, sl_price=5.00, tp_price=15.00,
                       mode="fixed", # 'fixed' or 'dynamic' (ATR multiplier)
                       use_trailing=False, trail_arm=0.28, trail_dist=0.05, trail_step=0.01,
                       use_ema=False, ema_type=200, use_kfd=False, kfd_thresh=1.42,
                       plock=200.0, lbreak=250.0,
                       spread_pts=0.25, comm_dollars=0.60, point_value=100.0):
    n = len(closes)
    trades = []
    
    # Pre-detect pivots
    p_highs, p_lows = detect_wing_pivots(highs, lows, wing=wing)

    curr_m = months[0]
    m_pnl = 0.0
    m_locked = False

    in_pos = False
    pos_type = 0 # 1=Buy, -1=Sell
    entry_price = 0.0
    sl_level = 0.0
    tp_level = 0.0
    entry_idx = 0

    buy_stop_level = 0.0
    buy_stop_active = False
    sell_stop_level = 0.0
    sell_stop_active = False

    ema_ref = ema200 if ema_type == 200 else ema34

    for i in range(200, n - 1):
        if months[i] != curr_m:
            curr_m = months[i]
            m_pnl = 0.0
            m_locked = False

        c_atr = atr14[i]

        # 1. Manage open position
        if in_pos:
            hit_tp = False
            hit_sl = False
            exit_price = 0.0

            # Trailing stop
            if use_trailing:
                cur_arm = trail_arm * c_atr if mode == "dynamic" else trail_arm
                cur_dist = trail_dist * c_atr if mode == "dynamic" else trail_dist
                cur_step = trail_step * c_atr if mode == "dynamic" else trail_step

                if pos_type == 1:
                    favorable = highs[i] - entry_price
                    if favorable >= cur_arm:
                        cand_sl = highs[i] - cur_dist
                        if cand_sl > sl_level + cur_step:
                            sl_level = cand_sl
                elif pos_type == -1:
                    favorable = entry_price - lows[i]
                    if favorable >= cur_arm:
                        cand_sl = lows[i] + cur_dist
                        if cand_sl < sl_level - cur_step:
                            sl_level = cand_sl

            # Check hard SL / TP
            if pos_type == 1:
                if lows[i] <= sl_level:
                    hit_sl = True
                    exit_price = sl_level
                elif highs[i] >= tp_level and tp_level > 0.0:
                    hit_tp = True
                    exit_price = tp_level
            elif pos_type == -1:
                if highs[i] >= sl_level:
                    hit_sl = True
                    exit_price = sl_level
                elif lows[i] <= tp_level and tp_level > 0.0:
                    hit_tp = True
                    exit_price = tp_level

            if hit_tp or hit_sl:
                if pos_type == 1:
                    pnl = (exit_price - entry_price) * point_value - comm_dollars
                else:
                    pnl = (entry_price - exit_price) * point_value - comm_dollars

                trades.append({
                    "entry_idx": entry_idx, "exit_idx": i,
                    "pos_type": pos_type, "entry_price": entry_price, "exit_price": exit_price,
                    "pnl": pnl, "month": months[entry_idx], "date": pd.to_datetime(dates[i])
                })
                m_pnl += pnl
                if m_pnl >= plock or m_pnl <= -lbreak:
                    m_locked = True
                in_pos = False
                continue

        # 2. Check confirmed pivots at bar i
        # Pivot at bar p = i - wing is confirmed at bar i
        p_idx = i - wing
        if p_idx >= 0 and p_highs[p_idx]:
            buf = buffer_price * c_atr if mode == "dynamic" else buffer_price
            buy_stop_level = highs[p_idx] + buf
            buy_stop_active = True

        if p_idx >= 0 and p_lows[p_idx]:
            buf = buffer_price * c_atr if mode == "dynamic" else buffer_price
            sell_stop_level = lows[p_idx] - buf
            sell_stop_active = True

        # 3. Check breakout fill on bar i + 1 (or during bar i)
        if not in_pos and not m_locked:
            kfd_ok = (kfd24[i] <= kfd_thresh) if use_kfd else True
            trend_bull = (closes[i] > ema_ref[i]) if use_ema else True
            trend_bear = (closes[i] < ema_ref[i]) if use_ema else True

            # Buy Stop trigger: highs[i] >= buy_stop_level
            if buy_stop_active and trend_bull and kfd_ok:
                if highs[i] >= buy_stop_level and lows[i] <= buy_stop_level:
                    in_pos = True
                    pos_type = 1
                    entry_idx = i
                    entry_price = buy_stop_level + spread_pts
                    cur_sl_dist = sl_price * c_atr if mode == "dynamic" else sl_price
                    cur_tp_dist = tp_price * c_atr if mode == "dynamic" else tp_price
                    sl_level = entry_price - cur_sl_dist
                    tp_level = entry_price + cur_tp_dist if cur_tp_dist > 0.0 else 0.0
                    buy_stop_active = False
                elif closes[i] > buy_stop_level + (c_atr * 3.0):
                    buy_stop_active = False

            # Sell Stop trigger: lows[i] <= sell_stop_level
            if not in_pos and sell_stop_active and trend_bear and kfd_ok:
                if lows[i] <= sell_stop_level and highs[i] >= sell_stop_level:
                    in_pos = True
                    pos_type = -1
                    entry_idx = i
                    entry_price = sell_stop_level
                    cur_sl_dist = sl_price * c_atr if mode == "dynamic" else sl_price
                    cur_tp_dist = tp_price * c_atr if mode == "dynamic" else tp_price
                    sl_level = entry_price + cur_sl_dist
                    tp_level = entry_price - cur_tp_dist if cur_tp_dist > 0.0 else 0.0
                    sell_stop_active = False
                elif closes[i] < sell_stop_level - (c_atr * 3.0):
                    sell_stop_active = False

    return trades

# -----------------------------------------------------------------
# PERFORMANCE METRICS CALCULATION
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
    print("=" * 80)
    print("CFD QUANTITATIVE RESEARCH: ONE SHOOT AI V4 REVERSE-ENGINEERING")
    print("Evaluation Window: 72 Months (2020-2025)")
    print("Strict Zero-Martingale Discipline (Explicit SL/TP)")
    print("=" * 80)

    # 1. Load Data
    data_paths = [
        "projects/quant_strategy_discovery/data/XAUUSD_M15.parquet",
        "/content/CFD-Trading-ML/projects/quant_strategy_discovery/data/XAUUSD_M15.parquet",
        "data/XAUUSD_M15.parquet",
        "projects/quant_strategy_discovery/data/XAUUSD_H1.parquet",
        "/content/CFD-Trading-ML/projects/quant_strategy_discovery/data/XAUUSD_H1.parquet"
    ]
    xau_path = None
    for p in data_paths:
        if os.path.exists(p):
            xau_path = p
            break

    if not xau_path:
        print(f"[-] ERROR: Dataset not found in {data_paths}")
        sys.exit(1)

    print(f"[+] Loading dataset from: {xau_path}")
    raw_df = pd.read_parquet(xau_path)
    if not isinstance(raw_df.index, pd.DatetimeIndex):
        if "time" in raw_df.columns:
            raw_df["time"] = pd.to_datetime(raw_df["time"])
            raw_df = raw_df.set_index("time")
        else:
            raw_df.index = pd.to_datetime(raw_df.index)
    raw_df = raw_df.sort_index()
    raw_df = raw_df[(raw_df.index >= "2020-01-01") & (raw_df.index < "2026-01-01")]

    # If M15, resample to M30 (Native timeframe of One Shoot AI)
    if "M15" in xau_path:
        print("[+] Resampling M15 data to M30 (Native One Shoot AI timeframe)...")
        ohlc_dict = {
            "open": "first",
            "high": "max",
            "low": "min",
            "close": "last"
        }
        df_m30 = raw_df.resample("30min").agg(ohlc_dict).dropna()
    else:
        df_m30 = raw_df

    opens = df_m30["open"].values.astype(np.float64)
    highs = df_m30["high"].values.astype(np.float64)
    lows = df_m30["low"].values.astype(np.float64)
    closes = df_m30["close"].values.astype(np.float64)
    dates = df_m30.index
    months = (dates.year.values * 100 + dates.month.values).astype(np.int32)
    all_months = sorted(list(set(months)))
    print(f"[+] Loaded {len(df_m30)} M30 bars across {len(all_months)} calendar months.")

    atr14 = compute_atr(highs, lows, closes, 14)
    ema34 = compute_ema(closes, 34)
    ema200 = compute_ema(closes, 200)
    kfd24 = compute_katz_fractal_dimension(closes, 24)

    results = {}

    # =============================================================
    # EXPERIMENT 1: RAW SOURCE CODE BASELINE (Ultra-Tight Scalp Trailing)
    # =============================================================
    print("\n" + "=" * 60)
    print("PHASE 1: RAW ONE SHOOT AI V4 BASELINE (Ultra-Tight Scalp Trailing)")
    print("Wing=2, Buffer=$0.01, SL=$5.00, TrailArm=$0.28, TrailDist=$0.05")
    print("With Real Spread ($0.25) & Commission ($0.60)")
    print("=" * 60)

    raw_trades = simulate_one_shoot(
        opens, highs, lows, closes, atr14, ema34, ema200, kfd24,
        months, dates,
        wing=2, buffer_price=0.01, sl_price=5.00, tp_price=0.0,
        mode="fixed", use_trailing=True, trail_arm=0.28, trail_dist=0.05, trail_step=0.01,
        use_ema=False, use_kfd=False, plock=999999.0, lbreak=999999.0
    )
    m_raw = calculate_metrics(raw_trades, all_months, "Raw_OneShoot_TightTrail")
    results["Raw_OneShoot_TightTrail"] = m_raw
    print(f"[RAW ONE SHOOT AI] Trades: {m_raw['trades']:4d} | Net PnL: ${m_raw['net_profit']:10.2f} | PF: {m_raw['profit_factor']:.3f} | WinRate: {m_raw['win_rate']:.1f}% | MaxDD: ${m_raw['max_dd']:8.2f} | MCR: {m_raw['mcr']:.1f}%")

    # =============================================================
    # EXPERIMENT 2: TESTING REALISTIC FIXED R:R TARGETS (No Micro-Trailing)
    # =============================================================
    print("\n" + "=" * 60)
    print("PHASE 2: REALISTIC FIXED REWARD-TO-RISK TARGETS")
    print("SL=$5.00 | Testing TP=$10, $15, $25 | With & Without EMA Trend Filter")
    print("=" * 60)

    tp_tests = [10.0, 15.0, 20.0, 25.0]
    for tp in tp_tests:
        tr = simulate_one_shoot(
            opens, highs, lows, closes, atr14, ema34, ema200, kfd24,
            months, dates,
            wing=2, buffer_price=0.01, sl_price=5.00, tp_price=tp,
            mode="fixed", use_trailing=False,
            use_ema=False, use_kfd=False, plock=999999.0, lbreak=999999.0
        )
        m = calculate_metrics(tr, all_months, f"Fixed_SL5_TP{int(tp)}")
        results[f"Fixed_SL5_TP{int(tp)}"] = m
        print(f"[SL $5 / TP ${int(tp):2d}] Trades: {m['trades']:4d} | Net PnL: ${m['net_profit']:10.2f} | PF: {m['profit_factor']:.3f} | WinRate: {m['win_rate']:.1f}% | MaxDD: ${m['max_dd']:8.2f} | MCR: {m['mcr']:.1f}%")

    # =============================================================
    # EXPERIMENT 3: QUANTITATIVE ENHANCEMENT (EMA + KFD FILTERING)
    # =============================================================
    print("\n" + "=" * 60)
    print("PHASE 3: ONE SHOOT AI + 200 EMA TREND + KATZ FRACTAL DIMENSION GATING")
    print("=" * 60)

    for tp in [15.0, 20.0, 25.0]:
        tr = simulate_one_shoot(
            opens, highs, lows, closes, atr14, ema34, ema200, kfd24,
            months, dates,
            wing=2, buffer_price=0.01, sl_price=5.00, tp_price=tp,
            mode="fixed", use_trailing=False,
            use_ema=True, ema_type=200, use_kfd=True, kfd_thresh=1.42,
            plock=999999.0, lbreak=999999.0
        )
        m = calculate_metrics(tr, all_months, f"Enhanced_SL5_TP{int(tp)}_EMA200_KFD")
        results[f"Enhanced_SL5_TP{int(tp)}_EMA200_KFD"] = m
        print(f"[ENHANCED SL $5 / TP ${int(tp):2d} + EMA200 + KFD] Trades: {m['trades']:4d} | Net PnL: ${m['net_profit']:10.2f} | PF: {m['profit_factor']:.3f} | WinRate: {m['win_rate']:.1f}% | MaxDD: ${m['max_dd']:8.2f} | RoMaD: {m['romad']:.2f}x | MCR: {m['mcr']:.1f}%")

    # =============================================================
    # EXPERIMENT 4: VOLATILITY-ADAPTIVE DYNAMIC ATR MULTIPLIERS (GRID SEARCH)
    # =============================================================
    print("\n" + "=" * 60)
    print("PHASE 4: VOLATILITY-ADAPTIVE DYNAMIC ATR MULTIPLIERS")
    print("=" * 60)

    best_dynamic = None
    best_dynamic_pf = 0.0

    for sl_m in [1.5, 2.0, 2.5]:
        for tp_m in [3.0, 4.0, 5.0, 6.0]:
            for w in [2, 3]:
                d_trades = simulate_one_shoot(
                    opens, highs, lows, closes, atr14, ema34, ema200, kfd24,
                    months, dates,
                    wing=w, buffer_price=0.10, sl_price=sl_m, tp_price=tp_m,
                    mode="dynamic", use_trailing=False,
                    use_ema=True, ema_type=200, use_kfd=True, kfd_thresh=1.42,
                    plock=999999.0, lbreak=999999.0
                )
                tag = f"Dynamic_Wing{w}_SL{sl_m}_TP{tp_m}"
                m = calculate_metrics(d_trades, all_months, tag)
                if m["trades"] >= 50 and m["profit_factor"] > best_dynamic_pf:
                    best_dynamic_pf = m["profit_factor"]
                    best_dynamic = (tag, m)
                    print(f"[*] NEW BEST DYNAMIC COMBO -> {tag}: Trades={m['trades']} | Net=${m['net_profit']} | PF={m['profit_factor']:.3f} | DD=${m['max_dd']} | RoMaD={m['romad']:.2f}x | MCR={m['mcr']:.1f}%")

    if best_dynamic:
        results["Best_Dynamic_OneShoot"] = {
            "config": best_dynamic[0],
            "metrics": best_dynamic[1]
        }

    # =============================================================
    # EXPERIMENT 5: ASAR CALENDAR RISK GOVERNANCE
    # =============================================================
    print("\n" + "=" * 60)
    print("PHASE 5: ASAR CALENDAR RISK GOVERNANCE ON BEST CANDIDATE")
    print("=" * 60)

    asar_trades = simulate_one_shoot(
        opens, highs, lows, closes, atr14, ema34, ema200, kfd24,
        months, dates,
        wing=2, buffer_price=0.01, sl_price=5.00, tp_price=20.0,
        mode="fixed", use_trailing=False,
        use_ema=True, ema_type=200, use_kfd=True, kfd_thresh=1.42,
        plock=200.0, lbreak=250.0
    )
    asar_m = calculate_metrics(asar_trades, all_months, "ASAR_Governed_OneShoot")
    results["ASAR_Governed_OneShoot"] = asar_m
    print(f"[ASAR GOVERNED ONE SHOOT] Trades: {asar_m['trades']:4d} | Net PnL: ${asar_m['net_profit']:10.2f} | PF: {asar_m['profit_factor']:.3f} | MaxDD: ${asar_m['max_dd']:8.2f} | RoMaD: {asar_m['romad']:.2f}x | MCR: {asar_m['mcr']:.1f}%")

    # =============================================================
    # EXPERIMENT 6: CROSS-ASSET VALIDATION ON EURUSD (72 Months)
    # =============================================================
    print("\n" + "=" * 60)
    print("PHASE 6: CROSS-ASSET VALIDATION ON EURUSD (72 Months)")
    print("=" * 60)

    eur_paths = [
        "projects/quant_strategy_discovery/data/EURUSD_M15.parquet",
        "/content/CFD-Trading-ML/projects/quant_strategy_discovery/data/EURUSD_M15.parquet",
        "projects/quant_strategy_discovery/data/EURUSD_H1.parquet",
        "/content/CFD-Trading-ML/projects/quant_strategy_discovery/data/EURUSD_H1.parquet"
    ]
    eur_path = None
    for p in eur_paths:
        if os.path.exists(p):
            eur_path = p
            break

    if eur_path:
        eur_raw = pd.read_parquet(eur_path)
        if not isinstance(eur_raw.index, pd.DatetimeIndex):
            if "time" in eur_raw.columns:
                eur_raw["time"] = pd.to_datetime(eur_raw["time"])
                eur_raw = eur_raw.set_index("time")
            else:
                eur_raw.index = pd.to_datetime(eur_raw.index)
        eur_raw = eur_raw.sort_index()
        eur_raw = eur_raw[(eur_raw.index >= "2020-01-01") & (eur_raw.index < "2026-01-01")]

        if "M15" in eur_path:
            eur_df = eur_raw.resample("30min").agg(ohlc_dict).dropna()
        else:
            eur_df = eur_raw

        eur_opens = eur_df["open"].values.astype(np.float64)
        eur_highs = eur_df["high"].values.astype(np.float64)
        eur_lows = eur_df["low"].values.astype(np.float64)
        eur_closes = eur_df["close"].values.astype(np.float64)
        eur_dates = eur_df.index
        eur_months = (eur_dates.year.values * 100 + eur_dates.month.values).astype(np.int32)
        eur_all_months = sorted(list(set(eur_months)))

        eur_atr14 = compute_atr(eur_highs, eur_lows, eur_closes, 14)
        eur_ema34 = compute_ema(eur_closes, 34)
        eur_ema200 = compute_ema(eur_closes, 200)
        eur_kfd24 = compute_katz_fractal_dimension(eur_closes, 24)

        eur_trades = simulate_one_shoot(
            eur_opens, eur_highs, eur_lows, eur_closes, eur_atr14, eur_ema34, eur_ema200, eur_kfd24,
            eur_months, eur_dates,
            wing=2, buffer_price=0.10, sl_price=2.0, tp_price=4.0,
            mode="dynamic", use_trailing=False,
            use_ema=True, ema_type=200, use_kfd=True, kfd_thresh=1.42,
            plock=200.0, lbreak=250.0,
            spread_pts=0.00010, comm_dollars=0.60, point_value=100000.0
        )
        eur_m = calculate_metrics(eur_trades, eur_all_months, "EURUSD_OneShoot_Dynamic")
        results["EURUSD_OneShoot_Dynamic"] = eur_m
        print(f"[EURUSD DYNAMIC ONE SHOOT] Trades: {eur_m['trades']:4d} | Net PnL: ${eur_m['net_profit']:10.2f} | PF: {eur_m['profit_factor']:.3f} | MaxDD: ${eur_m['max_dd']:8.2f} | RoMaD: {eur_m['romad']:.2f}x | MCR: {eur_m['mcr']:.1f}%")

    # -------------------------------------------------------------
    # SAVE JSON AUDIT RECORD
    # -------------------------------------------------------------
    out_dir = "projects/quant_strategy_discovery/results"
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, "one_shoot_ai_clean_quant_results.json")
    with open(out_path, "w") as f:
        json.dump(results, f, indent=2)
    print(f"\n[+] Results saved successfully to {out_path}")
    print("=" * 80)

if __name__ == "__main__":
    main()
