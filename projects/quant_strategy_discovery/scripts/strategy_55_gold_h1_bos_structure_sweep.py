#!/usr/bin/env python3
"""
===============================================================================
STRATEGY 55: GOLD H1 MARKET STRUCTURE BREAK OF STRUCTURE (BOS-KFD) SWEEP
===============================================================================
Asset: XAUUSD (Gold CFD)
Timeframe: H1 (Resampled from raw M1 ticks)
Horizon: 2020-01-01 to 2025-12-30 (72 Calendar Months)
Execution Model: Next-Bar Open Fill, $0.25 Spread ($2.50/0.10 lot), $6/lot Comm ($0.60/0.10 lot)
Objective: Explore pure Quantitative Price Action / Institutional Market Structure
           Break of Structure (BOS) with Katz Fractal Gating & ASAR Risk Budget.
===============================================================================
"""

import os
import sys
import time
import json
import argparse
import numpy as np
import pandas as pd

def compute_atr(highs, lows, closes, period=14):
    n = len(closes)
    atr = np.zeros(n, dtype=np.float64)
    tr = np.zeros(n, dtype=np.float64)
    tr[0] = highs[0] - lows[0]
    for i in range(1, n):
        hl = highs[i] - lows[i]
        hc = abs(highs[i] - closes[i - 1])
        lc = abs(lows[i] - closes[i - 1])
        tr[i] = max(hl, max(hc, lc))
    
    atr[period - 1] = np.mean(tr[:period])
    alpha = 1.0 / period
    for i in range(period, n):
        atr[i] = (tr[i] * alpha) + (atr[i - 1] * (1.0 - alpha))
    return atr

def compute_ema(series, period):
    n = len(series)
    ema = np.zeros(n, dtype=np.float64)
    ema[0] = series[0]
    alpha = 2.0 / (period + 1.0)
    for i in range(1, n):
        ema[i] = (series[i] * alpha) + (ema[i - 1] * (1.0 - alpha))
    return ema

def compute_katz_fractal_dimension(closes, atr, period=24):
    n = len(closes)
    kfd = np.full(n, 1.5, dtype=np.float64)
    for i in range(period, n):
        sub = closes[i - period + 1 : i + 1]
        c_first = sub[0]
        c_last = sub[-1]
        euclid_d = abs(c_last - c_first)
        
        diffs = np.abs(np.diff(sub))
        total_len = np.sum(diffs)
        
        if total_len > 1e-6 and euclid_d > 1e-6:
            val = np.log10(period) / (np.log10(period) + np.log10(euclid_d / total_len))
            kfd[i] = max(1.0, min(2.0, val))
        else:
            kfd[i] = 1.5
    return kfd

def compute_confirmed_swing_levels(highs, lows, k=5):
    """
    Computes confirmed swing highs and swing lows without look-ahead bias.
    A swing high at bar j requires k bars before and k bars after to be strictly lower.
    Therefore, the swing high at j is ONLY confirmed at bar j + k.
    From bar j + k onwards, it becomes the active 'recent_swing_high'.
    """
    n = len(highs)
    recent_sh = np.zeros(n, dtype=np.float64)
    recent_sl = np.zeros(n, dtype=np.float64)
    
    last_sh = highs[0]
    last_sl = lows[0]
    
    for i in range(k * 2, n):
        # Check if bar (i - k) is a swing high
        cand_idx = i - k
        is_sh = True
        cand_h = highs[cand_idx]
        for b in range(cand_idx - k, cand_idx + k + 1):
            if b != cand_idx and highs[b] >= cand_h:
                is_sh = False
                break
        if is_sh:
            last_sh = cand_h
            
        # Check if bar (i - k) is a swing low
        is_sl = True
        cand_l = lows[cand_idx]
        for b in range(cand_idx - k, cand_idx + k + 1):
            if b != cand_idx and lows[b] <= cand_l:
                is_sl = False
                break
        if is_sl:
            last_sl = cand_l
            
        recent_sh[i] = last_sh
        recent_sl[i] = last_sl
        
    return recent_sh, recent_sl

def simulate_bos_strategy(
    opens, highs, lows, closes, atr14, ema200, kfd,
    recent_sh, recent_sl, months, dates,
    use_kfd=True, kfd_thresh=1.40,
    use_ema200=True,
    tp_mult=4.0, sl_mult=2.0,
    monthly_profit_lock=250.0, monthly_loss_breaker=250.0,
    lot_size=0.10, spread=0.25, commission=6.0
):
    n = len(closes)
    trades = []
    pos = 0 # 1 = Long, -1 = Short, 0 = Flat
    entry_p = 0.0
    sl_p = 0.0
    tp_p = 0.0
    entry_i = 0
    
    comm_cost = commission * lot_size
    spread_cost = spread * lot_size * 100.0 # Gold 100 oz per standard lot -> 0.1 lot = 10 oz -> $0.25 * 10 = $2.50
    fixed_friction = spread_cost + comm_cost
    
    cur_m = months[0]
    cur_m_pnl = 0.0
    locked_m = False
    
    for i in range(50, n - 1):
        bar_m = months[i]
        if bar_m != cur_m:
            cur_m = bar_m
            cur_m_pnl = 0.0
            locked_m = False
            
        # Active trade management
        if pos != 0:
            nxt_h = highs[i]
            nxt_l = lows[i]
            hit_tp = False
            hit_sl = False
            
            if pos == 1:
                if nxt_l <= sl_p:
                    hit_sl = True
                elif nxt_h >= tp_p:
                    hit_tp = True
            elif pos == -1:
                if nxt_h >= sl_p:
                    hit_sl = True
                elif nxt_l <= tp_p:
                    hit_tp = True
                    
            if hit_sl and hit_tp:
                hit_tp = False
                hit_sl = True
                
            if hit_sl or hit_tp:
                exit_p = tp_p if hit_tp else sl_p
                raw_diff = (exit_p - entry_p) if pos == 1 else (entry_p - exit_p)
                pnl = (raw_diff * lot_size * 100.0) - fixed_friction
                cur_m_pnl += pnl
                trades.append({
                    "entry_date": str(dates[entry_i]),
                    "exit_date": str(dates[i]),
                    "pos": pos,
                    "entry_p": round(entry_p, 2),
                    "exit_p": round(exit_p, 2),
                    "pnl": round(pnl, 2),
                    "month": cur_m,
                    "reason": "TP" if hit_tp else "SL",
                    "holding_bars": i - entry_i
                })
                pos = 0
                
                if monthly_profit_lock > 0 and cur_m_pnl >= monthly_profit_lock:
                    locked_m = True
                if monthly_loss_breaker > 0 and cur_m_pnl <= -monthly_loss_breaker:
                    locked_m = True
                    
        # Check new entry signals if flat and not month-locked
        if pos == 0 and not locked_m:
            c_atr = atr14[i]
            if c_atr < 0.5:
                continue
                
            sh = recent_sh[i]
            sl = recent_sl[i]
            if sh <= 0.0 or sl <= 0.0:
                continue
                
            # Filter checks
            kfd_ok = (kfd[i] <= kfd_thresh) if use_kfd else True
            ema_long_ok = (closes[i] > ema200[i]) if use_ema200 else True
            ema_short_ok = (closes[i] < ema200[i]) if use_ema200 else True
            
            # Break of Structure (BOS) condition
            # Close breaks above confirmed Swing High
            bull_bos = (closes[i] > sh) and (closes[i - 1] <= sh) and ema_long_ok and kfd_ok
            # Close breaks below confirmed Swing Low
            bear_bos = (closes[i] < sl) and (closes[i - 1] >= sl) and ema_short_ok and kfd_ok
            
            if bull_bos:
                pos = 1
                entry_i = i + 1
                entry_p = opens[i + 1]
                sl_p = entry_p - sl_mult * c_atr
                tp_p = entry_p + tp_mult * c_atr
            elif bear_bos:
                pos = -1
                entry_i = i + 1
                entry_p = opens[i + 1]
                sl_p = entry_p + sl_mult * c_atr
                tp_p = entry_p - tp_mult * c_atr
                
    return trades

def evaluate_metrics(trades, total_months=72):
    if not trades:
        return {
            "total_trades": 0, "net_profit": 0.0, "pf": 0.0,
            "win_rate": 0.0, "max_dd": 0.0, "romad": 0.0, "mcr": 0.0,
            "trades_per_year": 0.0
        }
    df = pd.DataFrame(trades)
    pnls = df["pnl"].values
    net_p = float(np.sum(pnls))
    wins = pnls[pnls > 0]
    losses = pnls[pnls < 0]
    gw = float(np.sum(wins)) if len(wins) > 0 else 0.0
    gl = float(abs(np.sum(losses))) if len(losses) > 0 else 1e-4
    pf = float(gw / gl)
    wr = float(len(wins) / len(pnls) * 100.0)
    
    eq = np.cumsum(pnls)
    pk = np.maximum.accumulate(eq)
    dd = pk - eq
    mdd = float(np.max(dd)) if len(dd) > 0 else 0.0
    romad = float(net_p / mdd) if mdd > 0 else 0.0
    
    monthly = df.groupby("month")["pnl"].sum().to_dict()
    pos_m = sum(1 for m, val in monthly.items() if val > 0.0)
    mcr = float(round(pos_m / total_months * 100.0, 2))
    tpy = float(round(len(trades) / (total_months / 12.0), 1))
    
    return {
        "total_trades": len(trades),
        "trades_per_year": tpy,
        "net_profit": round(net_p, 2),
        "pf": round(pf, 3),
        "win_rate": round(wr, 2),
        "max_dd": round(mdd, 2),
        "romad": round(romad, 2),
        "mcr": mcr,
        "pos_months": pos_m,
        "total_months": total_months
    }

def main():
    parser = argparse.ArgumentParser(description="Sweep Strategy 55: Gold H1 BOS Structure")
    parser.add_argument("--gold_data", type=str, default="/mnt/sdcard/Download/EA/XAUUSD_M1.csv.gz")
    parser.add_argument("--out_dir", type=str, default="projects/quant_strategy_discovery/results")
    args = parser.parse_args()
    os.makedirs(args.out_dir, exist_ok=True)
    
    t0 = time.time()
    print("[*] Loading Gold raw M1 data...")
    df = pd.read_csv(args.gold_data, usecols=["datetime", "open", "high", "low", "close"])
    df["datetime"] = pd.to_datetime(df["datetime"])
    df.set_index("datetime", inplace=True)
    df.sort_index(inplace=True)
    
    print("[*] Resampling to H1...")
    df_h1 = df.resample("1h").agg({"open": "first", "high": "max", "low": "min", "close": "last"}).dropna()
    opens = df_h1["open"].values.astype(np.float64)
    highs = df_h1["high"].values.astype(np.float64)
    lows = df_h1["low"].values.astype(np.float64)
    closes = df_h1["close"].values.astype(np.float64)
    dates = df_h1.index
    months = (dates.year.values * 100 + dates.month.values).astype(np.int32)
    
    print("[*] Computing Technical Indicators (ATR, EMA200, KFD)...")
    atr14 = compute_atr(highs, lows, closes, 14)
    ema200 = compute_ema(closes, 200)
    kfd24 = compute_katz_fractal_dimension(closes, atr14, 24)
    
    # Precompute swing levels for various k lookbacks
    swing_configs = [3, 4, 5, 7, 10]
    swing_levels = {}
    for k in swing_configs:
        print(f"[*] Precomputing confirmed swing levels for k={k}...")
        sh, sl = compute_confirmed_swing_levels(highs, lows, k)
        swing_levels[k] = (sh, sl)
        
    # Grid Parameter Combinations
    tp_mults = [2.5, 3.0, 3.5, 4.0, 4.5]
    sl_mults = [1.5, 2.0]
    kfd_threshs = [1.35, 1.40, 1.45, 999.0] # 999.0 means no KFD filter
    monthly_budget_configs = [
        (0.0, 0.0),       # Unrestricted
        (250.0, 250.0),   # Standard ASAR
        (350.0, 350.0)    # Expanded ASAR
    ]
    
    print("[*] Running parameter grid sweep...")
    results = []
    
    for k in swing_configs:
        sh, sl = swing_levels[k]
        for tp in tp_mults:
            for sl_m in sl_mults:
                for kfd_t in kfd_threshs:
                    use_kfd = (kfd_t < 100.0)
                    for plock, lbreak in monthly_budget_configs:
                        trades = simulate_bos_strategy(
                            opens=opens, highs=highs, lows=lows, closes=closes,
                            atr14=atr14, ema200=ema200, kfd=kfd24,
                            recent_sh=sh, recent_sl=sl,
                            months=months, dates=dates,
                            use_kfd=use_kfd, kfd_thresh=kfd_t,
                            use_ema200=True,
                            tp_mult=tp, sl_mult=sl_m,
                            monthly_profit_lock=plock, monthly_loss_breaker=lbreak
                        )
                        m = evaluate_metrics(trades)
                        cfg = {
                            "swing_k": k,
                            "tp_mult": tp,
                            "sl_mult": sl_m,
                            "kfd_thresh": kfd_t if use_kfd else None,
                            "monthly_profit_lock": plock,
                            "monthly_loss_breaker": lbreak,
                            "use_kfd": use_kfd
                        }
                        results.append({**cfg, **m})
                        
    df_res = pd.DataFrame(results)
    out_csv = os.path.join(args.out_dir, "strategy_55_bos_sweep_results.csv")
    df_res.to_csv(out_csv, index=False)
    print(f"[+] Saved {len(df_res)} sweep configurations to {out_csv}")
    
    # Filter for candidates with >= 60 trades and positive net profit
    df_candidates = df_res[(df_res["total_trades"] >= 60) & (df_res["net_profit"] > 0)].copy()
    if not df_candidates.empty:
        df_candidates.sort_values(by=["pf", "net_profit"], ascending=[False, False], inplace=True)
        top5 = df_candidates.head(5)
        print("\n" + "=" * 95)
        print("TOP 5 PERFORMING CONFIGURATIONS - STRATEGY 55: GOLD H1 BOS STRUCTURE")
        print("=" * 95)
        print(top5[["swing_k", "tp_mult", "sl_mult", "kfd_thresh", "monthly_profit_lock", "total_trades", "trades_per_year", "net_profit", "pf", "max_dd", "romad", "mcr"]].to_string(index=False))
        print("=" * 95)
        
        champ = top5.iloc[0].to_dict()
        champ_file = os.path.join(args.out_dir, "strategy_55_champion.json")
        with open(champ_file, "w") as f:
            json.dump({
                "strategy_id": "STRATEGY_55",
                "strategy_name": "Gold H1 Market Structure Break of Structure (BOS-KFD)",
                "champion_metrics": champ,
                "runtime_seconds": round(time.time() - t0, 2)
            }, f, indent=2)
        print(f"[+] Saved Strategy 55 Champion to {champ_file}")
    else:
        print("[!] No configuration met candidate criteria. Exporting rejected summary.")
        rej_file = os.path.join(args.out_dir, "strategy_55_rejected.json")
        with open(rej_file, "w") as f:
            json.dump({
                "strategy_id": "STRATEGY_55",
                "status": "REJECTED",
                "total_configs": len(df_res),
                "runtime_seconds": round(time.time() - t0, 2)
            }, f, indent=2)
            
if __name__ == "__main__":
    main()
