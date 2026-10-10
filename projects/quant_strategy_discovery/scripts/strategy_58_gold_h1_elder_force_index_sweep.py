#!/usr/bin/env python3
"""
===============================================================================
STRATEGY 58: GOLD H1 ELDER'S FORCE INDEX DYNAMIC VOLUME BREAKOUT (EFI-KFD) SWEEP
===============================================================================
Asset: XAUUSD (Gold CFD)
Timeframe: H1 (Resampled from raw M1 ticks with aggregated tick_volume)
Horizon: 2020-01-01 to 2025-12-30 (72 Calendar Months)
Execution Model: Next-Bar Open Fill, $0.25 Spread ($2.50/0.10 lot), $6/lot Comm ($0.60/0.10 lot)
Objective: Explore Alexander Elder's Force Index (Price Change x Volume) combined with
           Katz Fractal Dimension Gating and ASAR Calendar Risk Architecture on Gold H1.
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

def compute_elder_force_index(closes, volumes, efi_period=13):
    """
    Computes Alexander Elder's Force Index:
    Raw FI = Volume * (Close_i - Close_{i-1})
    EFI = EMA(Raw FI, efi_period)
    """
    n = len(closes)
    raw_fi = np.zeros(n, dtype=np.float64)
    for i in range(1, n):
        raw_fi[i] = volumes[i] * (closes[i] - closes[i - 1])
    return compute_ema(raw_fi, efi_period)

def simulate_efi_strategy(
    opens, highs, lows, closes, atr14, ema200, kfd, efi,
    months, dates,
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
    spread_cost = spread * lot_size * 100.0 # Gold 100 oz per standard lot -> 0.1 lot = 10 oz -> $2.50
    fixed_friction = spread_cost + comm_cost # $3.10 total roundturn
    
    cur_m = months[0]
    cur_m_pnl = 0.0
    locked_m = False
    
    for i in range(50, n - 1):
        bar_m = months[i]
        if bar_m != cur_m:
            cur_m = bar_m
            cur_m_pnl = 0.0
            locked_m = False
            
        # Manage active position
        if pos != 0:
            nxt_h = highs[i]
            nxt_l = lows[i]
            hit_tp = False
            hit_sl = False
            
            if pos == 1:
                if nxt_l <= sl_p: hit_sl = True
                elif nxt_h >= tp_p: hit_tp = True
            elif pos == -1:
                if nxt_h >= sl_p: hit_sl = True
                elif nxt_l <= tp_p: hit_tp = True
                
            if hit_sl and hit_tp:
                hit_tp = False; hit_sl = True
                
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
                    
        # Check new entries if flat
        if pos == 0 and not locked_m:
            c_atr = atr14[i]
            if c_atr < 0.5: continue
            
            kfd_ok = (kfd[i] <= kfd_thresh) if use_kfd else True
            ema_long_ok = (closes[i] > ema200[i]) if use_ema200 else True
            ema_short_ok = (closes[i] < ema200[i]) if use_ema200 else True
            
            # Elder Force Index Zero-Line Crossover Trigger
            bull_cross = (efi[i] > 0.0) and (efi[i - 1] <= 0.0) and ema_long_ok and kfd_ok
            bear_cross = (efi[i] < 0.0) and (efi[i - 1] >= 0.0) and ema_short_ok and kfd_ok
            
            if bull_cross:
                pos = 1
                entry_i = i + 1
                entry_p = opens[i + 1]
                sl_p = entry_p - sl_mult * c_atr
                tp_p = entry_p + tp_mult * c_atr
            elif bear_cross:
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
    parser = argparse.ArgumentParser(description="Sweep Strategy 58: Gold H1 Elder Force Index")
    parser.add_argument("--gold_data", type=str, default="/mnt/sdcard/Download/EA/XAUUSD_M1.csv.gz")
    parser.add_argument("--out_dir", type=str, default="projects/quant_strategy_discovery/results")
    args = parser.parse_args()
    os.makedirs(args.out_dir, exist_ok=True)
    
    t0 = time.time()
    print("[*] Loading Gold raw M1 data with tick_volume...")
    df = pd.read_csv(args.gold_data, usecols=["datetime", "open", "high", "low", "close", "tick_volume"])
    df["datetime"] = pd.to_datetime(df["datetime"])
    df.set_index("datetime", inplace=True)
    df.sort_index(inplace=True)
    
    print("[*] Resampling to H1 (Aggregating Volume)...")
    df_h1 = df.resample("1h").agg({
        "open": "first", "high": "max", "low": "min", "close": "last", "tick_volume": "sum"
    }).dropna()
    
    opens = df_h1["open"].values.astype(np.float64)
    highs = df_h1["high"].values.astype(np.float64)
    lows = df_h1["low"].values.astype(np.float64)
    closes = df_h1["close"].values.astype(np.float64)
    volumes = df_h1["tick_volume"].values.astype(np.float64)
    dates = df_h1.index
    months = (dates.year.values * 100 + dates.month.values).astype(np.int32)
    
    print("[*] Computing Technical Indicators (ATR, EMA200, KFD)...")
    atr14 = compute_atr(highs, lows, closes, 14)
    ema200 = compute_ema(closes, 200)
    kfd24 = compute_katz_fractal_dimension(closes, atr14, 24)
    
    efi_periods = [8, 13, 21, 34]
    efi_dict = {}
    for p in efi_periods:
        print(f"[*] Precomputing Elder's Force Index for period={p}...")
        efi_dict[p] = compute_elder_force_index(closes, volumes, efi_period=p)
        
    tp_mults = [3.0, 3.5, 4.0, 4.5]
    sl_mults = [1.5, 2.0, 2.5]
    kfd_threshs = [1.35, 1.40, 1.45, 999.0]
    monthly_budget_configs = [
        (0.0, 0.0),       # Unrestricted
        (200.0, 250.0),   # ASAR Conservative
        (250.0, 250.0),   # ASAR Standard
        (350.0, 350.0)    # ASAR Expanded
    ]
    
    print("[*] Running parameter grid sweep on Strategy 58 (Elder Force Index)...")
    results = []
    
    for p in efi_periods:
        efi_series = efi_dict[p]
        for tp in tp_mults:
            for sl_m in sl_mults:
                for kfd_t in kfd_threshs:
                    use_kfd = (kfd_t < 100.0)
                    for plock, lbreak in monthly_budget_configs:
                        trades = simulate_efi_strategy(
                            opens=opens, highs=highs, lows=lows, closes=closes,
                            atr14=atr14, ema200=ema200, kfd=kfd24, efi=efi_series,
                            months=months, dates=dates,
                            use_kfd=use_kfd, kfd_thresh=kfd_t,
                            use_ema200=True,
                            tp_mult=tp, sl_mult=sl_m,
                            monthly_profit_lock=plock, monthly_loss_breaker=lbreak
                        )
                        m = evaluate_metrics(trades)
                        cfg = {
                            "efi_period": p,
                            "tp_mult": tp,
                            "sl_mult": sl_m,
                            "kfd_thresh": kfd_t if use_kfd else None,
                            "monthly_profit_lock": plock,
                            "monthly_loss_breaker": lbreak,
                            "use_kfd": use_kfd
                        }
                        results.append({**cfg, **m})
                        
    df_res = pd.DataFrame(results)
    out_csv = os.path.join(args.out_dir, "strategy_58_efi_sweep_results.csv")
    df_res.to_csv(out_csv, index=False)
    print(f"[+] Saved {len(df_res)} sweep configurations to {out_csv}")
    
    df_candidates = df_res[(df_res["total_trades"] >= 60) & (df_res["net_profit"] > 0)].copy()
    if not df_candidates.empty:
        df_candidates.sort_values(by=["pf", "net_profit"], ascending=[False, False], inplace=True)
        top5 = df_candidates.head(5)
        print("\n" + "=" * 95)
        print("TOP 5 PERFORMING CONFIGURATIONS - STRATEGY 58: GOLD H1 ELDER FORCE INDEX")
        print("=" * 95)
        print(top5[["efi_period", "tp_mult", "sl_mult", "kfd_thresh", "monthly_profit_lock", "total_trades", "trades_per_year", "net_profit", "pf", "max_dd", "romad", "mcr"]].to_string(index=False))
        print("=" * 95)
        
        champ = top5.iloc[0].to_dict()
        champ_file = os.path.join(args.out_dir, "strategy_58_champion.json")
        with open(champ_file, "w") as f:
            json.dump({
                "strategy_id": "STRATEGY_58",
                "strategy_name": "Gold H1 Elder Force Index Dynamic Volume Breakout (EFI-KFD)",
                "champion_metrics": champ,
                "runtime_seconds": round(time.time() - t0, 2)
            }, f, indent=2)
        print(f"[+] Saved Strategy 58 Champion to {champ_file}")
    else:
        print("[!] No configuration met candidate criteria. Exporting rejected summary.")
        rej_file = os.path.join(args.out_dir, "strategy_58_rejected.json")
        with open(rej_file, "w") as f:
            json.dump({
                "strategy_id": "STRATEGY_58",
                "status": "REJECTED",
                "total_configs": len(df_res),
                "runtime_seconds": round(time.time() - t0, 2)
            }, f, indent=2)
            
if __name__ == "__main__":
    main()
