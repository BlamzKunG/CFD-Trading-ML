#!/usr/bin/env python3
"""
SWEEP LIZARD & GOLD REAPER CLEAN QUANT (MULTI-HORIZON ASYMMETRIC BREAKOUT ENGINE)
Autonomous Quantitative Reverse-Engineering & Backtest Sweep on Google Colab Cloud VM
Assets: XAUUSD (Gold CFD) and EURUSD
Test Span: 72 Calendar Months (2020-01-01 to 2025-12-31)
Rule Mandate: Constitution V5.0 - Strictly Single-Position per Lane, Disciplined SL/TP, Zero Martingale/Grid.
"""

import sys
import os
import json
import numpy as np
import pandas as pd
from datetime import datetime

# Load dataset
def load_data(parquet_path):
    print(f"[*] Loading data from: {parquet_path}")
    df = pd.read_parquet(parquet_path)
    if not isinstance(df.index, pd.DatetimeIndex):
        if 'time' in df.columns:
            df['time'] = pd.to_datetime(df['time'])
            df.set_index('time', inplace=True)
        elif 'datetime' in df.columns:
            df['datetime'] = pd.to_datetime(df['datetime'])
            df.set_index('datetime', inplace=True)
    df.sort_index(inplace=True)
    # Ensure standard OHLC columns
    df.columns = [c.lower() for c in df.columns]
    return df

def compute_kfd(series_close, n=24):
    """Katz Fractal Dimension"""
    closes = series_close.values
    kfd = np.full(len(closes), 1.5)
    for i in range(n, len(closes)):
        window = closes[i - n : i + 1]
        d = np.max(np.abs(window - window[0]))
        L = np.sum(np.abs(np.diff(window)))
        if L > 0 and d > 0:
            kfd[i] = np.log10(n) / (np.log10(n) + np.log10(d / L))
        else:
            kfd[i] = 1.5
    return kfd

def precompute_fractals(df_tf, left_bars, right_bars, max_search):
    """
    Find fractal swing highs and lows on the given timeframe.
    Returns:
      swing_high_level: array of unbroken swing high price at bar t
      swing_low_level: array of unbroken swing low price at bar t
    """
    n = len(df_tf)
    highs = df_tf['high'].values
    lows = df_tf['low'].values
    
    swing_highs = np.full(n, np.nan)
    swing_lows = np.full(n, np.nan)
    
    # Identify swing highs and lows
    # A bar p is confirmed at p + right_bars
    is_swing_high = np.zeros(n, dtype=bool)
    is_swing_low = np.zeros(n, dtype=bool)
    
    for p in range(left_bars, n - right_bars):
        # High check
        h_p = highs[p]
        if np.all(h_p > highs[p - left_bars : p]) and np.all(h_p > highs[p + 1 : p + right_bars + 1]):
            is_swing_high[p] = True
            
        # Low check
        l_p = lows[p]
        if np.all(l_p < lows[p - left_bars : p]) and np.all(l_p < lows[p + 1 : p + right_bars + 1]):
            is_swing_low[p] = True
            
    # For each bar t, look back up to max_search bars for the most recent unbroken swing
    for t in range(right_bars + 1, n):
        # Look for unbroken swing high
        for p in range(t - right_bars, max(0, t - max_search), -1):
            if is_swing_high[p]:
                h_level = highs[p]
                # Check if broken between p+1 and t-1
                if p + 1 < t:
                    if np.max(highs[p + 1 : t]) < h_level:
                        swing_highs[t] = h_level
                        break
                else:
                    swing_highs[t] = h_level
                    break
                    
        # Look for unbroken swing low
        for p in range(t - right_bars, max(0, t - max_search), -1):
            if is_swing_low[p]:
                l_level = lows[p]
                # Check if broken between p+1 and t-1
                if p + 1 < t:
                    if np.min(lows[p + 1 : t]) > l_level:
                        swing_lows[t] = l_level
                        break
                else:
                    swing_lows[t] = l_level
                    break
                    
    return swing_highs, swing_lows

def simulate_lane(df_exec, swing_highs, swing_lows, 
                  offset_buy, offset_sell, sl_dist, tp_dist, 
                  trail_act, trail_dist, trail_step,
                  ema_filter=None, kfd_filter=None, kfd_thresh=1.42,
                  spread=0.25, lot=0.10, point_val=10.0):
    """
    Simulate a single lane's execution on df_exec (H1).
    """
    n = len(df_exec)
    times = df_exec.index
    opens = df_exec['open'].values
    highs = df_exec['high'].values
    lows = df_exec['low'].values
    closes = df_exec['close'].values
    
    trades = []
    
    # State
    in_pos = 0 # +1 for long, -1 for short
    entry_price = 0.0
    entry_time = None
    curr_sl = 0.0
    curr_tp = 0.0
    
    for i in range(1, n):
        t = times[i]
        o = opens[i]
        h = highs[i]
        l = lows[i]
        c = closes[i]
        
        # 1. Manage active position
        if in_pos == 1:
            # Check SL
            if l <= curr_sl:
                exit_price = min(o, curr_sl)
                pnl = (exit_price - entry_price) * point_val * lot
                trades.append({
                    'entry_time': entry_time, 'exit_time': t,
                    'direction': 'BUY', 'entry_price': entry_price, 'exit_price': exit_price,
                    'pnl': pnl, 'type': 'SL'
                })
                in_pos = 0
            # Check TP
            elif h >= curr_tp:
                exit_price = max(o, curr_tp)
                pnl = (exit_price - entry_price) * point_val * lot
                trades.append({
                    'entry_time': entry_time, 'exit_time': t,
                    'direction': 'BUY', 'entry_price': entry_price, 'exit_price': exit_price,
                    'pnl': pnl, 'type': 'TP'
                })
                in_pos = 0
            else:
                # Update trailing stop
                if trail_dist > 0:
                    profit = h - entry_price
                    if profit >= trail_act:
                        new_sl = h - trail_dist
                        if new_sl >= curr_sl + trail_step:
                            curr_sl = new_sl
                            
        elif in_pos == -1:
            # Check SL
            if h >= curr_sl:
                exit_price = max(o, curr_sl)
                pnl = (entry_price - exit_price) * point_val * lot
                trades.append({
                    'entry_time': entry_time, 'exit_time': t,
                    'direction': 'SELL', 'entry_price': entry_price, 'exit_price': exit_price,
                    'pnl': pnl, 'type': 'SL'
                })
                in_pos = 0
            # Check TP
            elif l <= curr_tp:
                exit_price = min(o, curr_tp)
                pnl = (entry_price - exit_price) * point_val * lot
                trades.append({
                    'entry_time': entry_time, 'exit_time': t,
                    'direction': 'SELL', 'entry_price': entry_price, 'exit_price': exit_price,
                    'pnl': pnl, 'type': 'TP'
                })
                in_pos = 0
            else:
                # Update trailing stop
                if trail_dist > 0:
                    profit = entry_price - l
                    if profit >= trail_act:
                        new_sl = l + trail_dist
                        if new_sl <= curr_sl - trail_step:
                            curr_sl = new_sl
                            
        # 2. Check new entries if flat
        if in_pos == 0:
            # Gating checks
            can_long = True
            can_short = True
            
            if ema_filter is not None:
                if closes[i - 1] < ema_filter[i - 1]:
                    can_long = False
                if closes[i - 1] > ema_filter[i - 1]:
                    can_short = False
                    
            if kfd_filter is not None:
                if kfd_filter[i - 1] > kfd_thresh:
                    can_long = False
                    can_short = False
                    
            sh = swing_highs[i - 1]
            sl = swing_lows[i - 1]
            
            # Buy breakout check
            if can_long and not np.isnan(sh):
                trigger_buy = sh + offset_buy
                if o <= trigger_buy and h >= trigger_buy:
                    in_pos = 1
                    entry_price = trigger_buy + spread
                    entry_time = t
                    curr_sl = entry_price - sl_dist
                    curr_tp = entry_price + tp_dist
                    continue
                    
            # Sell breakdown check
            if can_short and not np.isnan(sl):
                trigger_sell = sl - offset_sell
                if o >= trigger_sell and l <= trigger_sell:
                    in_pos = -1
                    entry_price = trigger_sell
                    entry_time = t
                    curr_sl = entry_price + sl_dist
                    curr_tp = entry_price - tp_dist
                    continue
                    
    return pd.DataFrame(trades)

def evaluate_performance(df_trades, initial_balance=10000.0):
    if df_trades.empty or len(df_trades) == 0:
        return {
            'trades': 0, 'net_profit': 0.0, 'profit_factor': 0.0,
            'win_rate': 0.0, 'max_dd': 0.0, 'romad': 0.0, 'mcr': 0.0,
            'profitable_months': 0, 'total_months': 72
        }
        
    trades = df_trades.copy()
    trades.sort_values('exit_time', inplace=True)
    trades['cum_pnl'] = trades['pnl'].cumsum()
    trades['equity'] = initial_balance + trades['cum_pnl']
    trades['peak'] = trades['equity'].cummax()
    trades['dd'] = trades['peak'] - trades['equity']
    max_dd = float(trades['dd'].max())
    
    wins = trades[trades['pnl'] > 0]['pnl']
    losses = trades[trades['pnl'] < 0]['pnl']
    
    gross_profit = float(wins.sum()) if len(wins) > 0 else 0.0
    gross_loss = abs(float(losses.sum())) if len(losses) > 0 else 0.0
    
    pf = round(gross_profit / gross_loss, 3) if gross_loss > 0 else (999.0 if gross_profit > 0 else 0.0)
    net_profit = round(float(trades['pnl'].sum()), 2)
    win_rate = round(len(wins) / len(trades) * 100.0, 2)
    romad = round(net_profit / max_dd, 2) if max_dd > 0 else 999.0
    
    # Monthly Consistency Ratio (MCR)
    trades['month_key'] = trades['exit_time'].dt.to_period('M')
    monthly = trades.groupby('month_key')['pnl'].sum()
    
    # Range of 72 months (2020-01 to 2025-12)
    all_months = pd.period_range('2020-01', '2025-12', freq='M')
    monthly = monthly.reindex(all_months, fill_value=0.0)
    
    profitable_months = int((monthly > 0).sum())
    total_months = len(all_months)
    mcr = round(profitable_months / total_months * 100.0, 2)
    
    return {
        'trades': len(trades),
        'net_profit': net_profit,
        'profit_factor': pf,
        'win_rate': win_rate,
        'max_dd': round(max_dd, 2),
        'romad': romad,
        'mcr': mcr,
        'profitable_months': profitable_months,
        'total_months': total_months
    }

def main():
    print("=" * 80)
    print("AUTONOMOUS RESEARCH: LIZARD & GOLD REAPER CLEAN QUANT (MULTI-HORIZON BREAKOUT)")
    print("=" * 80)
    
    xau_path = "/content/projects/quant_strategy_discovery/data/XAUUSD_H1.parquet"
    eur_path = "/content/projects/quant_strategy_discovery/data/EURUSD_H1.parquet"
    
    if not os.path.exists(xau_path):
        print(f"[!] Error: {xau_path} not found.")
        return
        
    df_xau = load_data(xau_path)
    df_xau = df_xau.loc['2020-01-01':'2025-12-31']
    print(f"[*] XAUUSD H1 loaded: {len(df_xau)} bars from {df_xau.index[0]} to {df_xau.index[-1]}")
    
    # Resample to H4 and D1 for higher-timeframe fractals
    df_xau_h4 = df_xau.resample('4h', label='right', closed='right').agg({
        'open': 'first', 'high': 'max', 'low': 'min', 'close': 'last'
    }).dropna()
    
    df_xau_d1 = df_xau.resample('1D', label='right', closed='right').agg({
        'open': 'first', 'high': 'max', 'low': 'min', 'close': 'last'
    }).dropna()
    
    print(f"[*] Aggregated: H4={len(df_xau_h4)} bars, D1={len(df_xau_d1)} bars")
    
    # Calculate 200 EMA and Katz Fractal Dimension on H1
    df_xau['ema200'] = df_xau['close'].ewm(span=200, adjust=False).mean()
    df_xau['kfd24'] = compute_kfd(df_xau['close'], n=24)
    
    # Define the 9 Lizard / Gold Reaper Lanes
    lanes_cfg = {
        'Lane_0_D1_Conservative': {
            'tf': 'D1', 'left': 24, 'right': 3, 'search': 105,
            'offset_buy': -2.75, 'offset_sell': -2.75, 'sl': 61.0, 'tp': 14.5,
            'trail_act': 10.0, 'trail_dist': 18.0, 'trail_step': 1.0
        },
        'Lane_1_D1_Asymmetric': {
            'tf': 'D1', 'left': 15, 'right': 3, 'search': 230,
            'offset_buy': -1.70, 'offset_sell': -1.70, 'sl': 10.0, 'tp': 41.0,
            'trail_act': 5.0, 'trail_dist': 4.5, 'trail_step': 0.5
        },
        'Lane_2_D1_Agile': {
            'tf': 'D1', 'left': 7, 'right': 2, 'search': 20,
            'offset_buy': -1.12, 'offset_sell': -1.12, 'sl': 7.0, 'tp': 36.3,
            'trail_act': 5.0, 'trail_dist': 5.0, 'trail_step': 0.5
        },
        'Lane_3_H4_Asymmetric': {
            'tf': 'H4', 'left': 12, 'right': 8, 'search': 90,
            'offset_buy': -0.40, 'offset_sell': -1.00, 'sl': 8.0, 'tp': 49.0,
            'trail_act': 8.0, 'trail_dist': 13.0, 'trail_step': 1.0
        },
        'Lane_4_H1_Medium': {
            'tf': 'H1', 'left': 30, 'right': 19, 'search': 110,
            'offset_buy': -1.15, 'offset_sell': -1.15, 'sl': 53.0, 'tp': 9.27,
            'trail_act': 5.0, 'trail_dist': 4.95, 'trail_step': 0.5
        },
        'Lane_5_H1_MicroRetest': {
            'tf': 'H1', 'left': 26, 'right': 24, 'search': 140,
            'offset_buy': -1.05, 'offset_sell': -1.05, 'sl': 101.0, 'tp': 8.24,
            'trail_act': 5.0, 'trail_dist': 5.0, 'trail_step': 0.5
        },
        'Lane_6_H1_Momentum': {
            'tf': 'H1', 'left': 25, 'right': 23, 'search': 145,
            'offset_buy': -0.55, 'offset_sell': -0.55, 'sl': 22.5, 'tp': 15.22,
            'trail_act': 5.0, 'trail_dist': 4.5, 'trail_step': 0.5
        },
        'Lane_7_H1_MacroHorizon': {
            'tf': 'H1', 'left': 26, 'right': 20, 'search': 235,
            'offset_buy': -1.40, 'offset_sell': -1.40, 'sl': 19.0, 'tp': 12.84,
            'trail_act': 8.0, 'trail_dist': 12.5, 'trail_step': 1.0
        },
        'Lane_8_H1_FastFractal': {
            'tf': 'H1', 'left': 7, 'right': 5, 'search': 200,
            'offset_buy': -1.30, 'offset_sell': -1.30, 'sl': 39.0, 'tp': 14.85,
            'trail_act': 5.0, 'trail_dist': 4.45, 'trail_step': 0.5
        }
    }
    
    # Precompute fractals for each TF and map back to H1 index
    print("\n[*] Precomputing fractal swing levels...")
    fractals_h1_map = {}
    
    for lane_id, cfg in lanes_cfg.items():
        tf = cfg['tf']
        l, r, s = cfg['left'], cfg['right'], cfg['search']
        print(f"  -> Precomputing {lane_id} ({tf}, L={l}, R={r}, Search={s})...")
        
        if tf == 'D1':
            sh, sl = precompute_fractals(df_xau_d1, l, r, s)
            # Reindex to H1 using forward fill
            s_sh = pd.Series(sh, index=df_xau_d1.index).reindex(df_xau.index, method='ffill')
            s_sl = pd.Series(sl, index=df_xau_d1.index).reindex(df_xau.index, method='ffill')
            fractals_h1_map[lane_id] = (s_sh.values, s_sl.values)
        elif tf == 'H4':
            sh, sl = precompute_fractals(df_xau_h4, l, r, s)
            s_sh = pd.Series(sh, index=df_xau_h4.index).reindex(df_xau.index, method='ffill')
            s_sl = pd.Series(sl, index=df_xau_h4.index).reindex(df_xau.index, method='ffill')
            fractals_h1_map[lane_id] = (s_sh.values, s_sl.values)
        else: # H1
            sh, sl = precompute_fractals(df_xau, l, r, s)
            fractals_h1_map[lane_id] = (sh, sl)
            
    # Run backtests for all lanes
    results = {}
    lane_trades_raw = {}
    lane_trades_enh = {}
    
    print("\n" + "=" * 80)
    print("PHASE 1: INDIVIDUAL LANE BACKTESTS (72 MONTHS XAUUSD H1)")
    print("=" * 80)
    
    for lane_id, cfg in lanes_cfg.items():
        sh, sl = fractals_h1_map[lane_id]
        
        # 1. Raw Execution
        trades_raw = simulate_lane(
            df_xau, sh, sl,
            cfg['offset_buy'], cfg['offset_sell'], cfg['sl'], cfg['tp'],
            cfg['trail_act'], cfg['trail_dist'], cfg['trail_step'],
            ema_filter=None, kfd_filter=None, spread=0.25, lot=0.10
        )
        perf_raw = evaluate_performance(trades_raw)
        results[f"{lane_id}_Raw"] = perf_raw
        lane_trades_raw[lane_id] = trades_raw
        
        # 2. Enhanced Execution (+200 EMA + Katz Fractal Dimension <= 1.42)
        trades_enh = simulate_lane(
            df_xau, sh, sl,
            cfg['offset_buy'], cfg['offset_sell'], cfg['sl'], cfg['tp'],
            cfg['trail_act'], cfg['trail_dist'], cfg['trail_step'],
            ema_filter=df_xau['ema200'].values, kfd_filter=df_xau['kfd24'].values, kfd_thresh=1.42,
            spread=0.25, lot=0.10
        )
        perf_enh = evaluate_performance(trades_enh)
        results[f"{lane_id}_Enhanced"] = perf_enh
        lane_trades_enh[lane_id] = trades_enh
        
        print(f"\n[{lane_id}]")
        print(f"  RAW      : {perf_raw['trades']:4d} trds | Net: +${perf_raw['net_profit']:10.2f} | PF: {perf_raw['profit_factor']:.3f} | WR: {perf_raw['win_rate']:5.2f}% | MaxDD: ${perf_raw['max_dd']:8.2f} | RoMaD: {perf_raw['romad']:6.2f}x | MCR: {perf_raw['mcr']:.1f}%")
        print(f"  ENHANCED : {perf_enh['trades']:4d} trds | Net: +${perf_enh['net_profit']:10.2f} | PF: {perf_enh['profit_factor']:.3f} | WR: {perf_enh['win_rate']:5.2f}% | MaxDD: ${perf_enh['max_dd']:8.2f} | RoMaD: {perf_enh['romad']:6.2f}x | MCR: {perf_enh['mcr']:.1f}%")
        
    print("\n" + "=" * 80)
    print("PHASE 2: COMPOSITE PORTFOLIO SYNTHESIS")
    print("=" * 80)
    
    # Portfolio 1: Full 9-Lane Raw Composite
    all_raw_trades = pd.concat([t for t in lane_trades_raw.values() if not t.empty], ignore_index=True)
    perf_all_raw = evaluate_performance(all_raw_trades)
    results['Full_9Lane_Raw_Portfolio'] = perf_all_raw
    print(f"\n[Full 9-Lane Raw Portfolio]")
    print(f"  {perf_all_raw['trades']:4d} trds | Net: +${perf_all_raw['net_profit']:10.2f} | PF: {perf_all_raw['profit_factor']:.3f} | WR: {perf_all_raw['win_rate']:5.2f}% | MaxDD: ${perf_all_raw['max_dd']:8.2f} | RoMaD: {perf_all_raw['romad']:6.2f}x | MCR: {perf_all_raw['mcr']:.1f}%")
    
    # Portfolio 2: Asymmetric Trio (Lane 1 [D1] + Lane 2 [D1] + Lane 3 [H4]) Raw & Enhanced
    trio_raw_trades = pd.concat([
        lane_trades_raw['Lane_1_D1_Asymmetric'],
        lane_trades_raw['Lane_2_D1_Agile'],
        lane_trades_raw['Lane_3_H4_Asymmetric']
    ], ignore_index=True)
    perf_trio_raw = evaluate_performance(trio_raw_trades)
    results['Asymmetric_Trio_Raw_Portfolio'] = perf_trio_raw
    print(f"\n[Asymmetric Trio Raw (L1+L2+L3)]")
    print(f"  {perf_trio_raw['trades']:4d} trds | Net: +${perf_trio_raw['net_profit']:10.2f} | PF: {perf_trio_raw['profit_factor']:.3f} | WR: {perf_trio_raw['win_rate']:5.2f}% | MaxDD: ${perf_trio_raw['max_dd']:8.2f} | RoMaD: {perf_trio_raw['romad']:6.2f}x | MCR: {perf_trio_raw['mcr']:.1f}%")

    trio_enh_trades = pd.concat([
        lane_trades_enh['Lane_1_D1_Asymmetric'],
        lane_trades_enh['Lane_2_D1_Agile'],
        lane_trades_enh['Lane_3_H4_Asymmetric']
    ], ignore_index=True)
    perf_trio_enh = evaluate_performance(trio_enh_trades)
    results['Asymmetric_Trio_Enhanced_Portfolio'] = perf_trio_enh
    print(f"\n[Asymmetric Trio Enhanced (L1+L2+L3 + EMA + KFD)]")
    print(f"  {perf_trio_enh['trades']:4d} trds | Net: +${perf_trio_enh['net_profit']:10.2f} | PF: {perf_trio_enh['profit_factor']:.3f} | WR: {perf_trio_enh['win_rate']:5.2f}% | MaxDD: ${perf_trio_enh['max_dd']:8.2f} | RoMaD: {perf_trio_enh['romad']:6.2f}x | MCR: {perf_trio_enh['mcr']:.1f}%")

    # Portfolio 3: Top-Alpha High Sharpe Multi-Lane Portfolio (L1, L2, L3, L6, L7 Enhanced)
    top_enh_trades = pd.concat([
        lane_trades_enh['Lane_1_D1_Asymmetric'],
        lane_trades_enh['Lane_2_D1_Agile'],
        lane_trades_enh['Lane_3_H4_Asymmetric'],
        lane_trades_enh['Lane_6_H1_Momentum'],
        lane_trades_enh['Lane_7_H1_MacroHorizon']
    ], ignore_index=True)
    perf_top_enh = evaluate_performance(top_enh_trades)
    results['Top5_Clean_Quant_Portfolio'] = perf_top_enh
    print(f"\n[Top 5 Clean Quant Multi-Horizon Portfolio (L1+L2+L3+L6+L7 Enhanced)]")
    print(f"  {perf_top_enh['trades']:4d} trds | Net: +${perf_top_enh['net_profit']:10.2f} | PF: {perf_top_enh['profit_factor']:.3f} | WR: {perf_top_enh['win_rate']:5.2f}% | MaxDD: ${perf_top_enh['max_dd']:8.2f} | RoMaD: {perf_top_enh['romad']:6.2f}x | MCR: {perf_top_enh['mcr']:.1f}%")

    # Save results to JSON
    out_dir = "/content/projects/quant_strategy_discovery/results"
    os.makedirs(out_dir, exist_ok=True)
    out_file = os.path.join(out_dir, "lizard_gold_reaper_clean_quant_results.json")
    with open(out_file, "w") as f:
        json.dump(results, f, indent=2)
    print(f"\n[✓] Results successfully saved to: {out_file}")

if __name__ == "__main__":
    main()
