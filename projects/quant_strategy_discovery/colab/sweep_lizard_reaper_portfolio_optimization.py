#!/usr/bin/env python3
"""
LIZARD & GOLD REAPER CLEAN QUANT: PORTFOLIO OPTIMIZATION & CROSS-ASSET SWEEP
Autonomous Quantitative Research on Google Colab Cloud VM
Assets: XAUUSD (Gold CFD) and EURUSD
Span: 72 Months (2020-01-01 to 2025-12-31)
Rule Mandate: Constitution V5.0 - Strictly Single-Position per Lane, Disciplined SL/TP, Zero Martingale/Grid.
"""

import sys
import os
import json
import numpy as np
import pandas as pd

def load_data(parquet_path):
    df = pd.read_parquet(parquet_path)
    if not isinstance(df.index, pd.DatetimeIndex):
        if 'time' in df.columns:
            df['time'] = pd.to_datetime(df['time'])
            df.set_index('time', inplace=True)
        elif 'datetime' in df.columns:
            df['datetime'] = pd.to_datetime(df['datetime'])
            df.set_index('datetime', inplace=True)
    df.sort_index(inplace=True)
    df.columns = [c.lower() for c in df.columns]
    return df

def precompute_fractals(df_tf, left_bars, right_bars, max_search):
    n = len(df_tf)
    highs = df_tf['high'].values
    lows = df_tf['low'].values
    
    swing_highs = np.full(n, np.nan)
    swing_lows = np.full(n, np.nan)
    
    is_swing_high = np.zeros(n, dtype=bool)
    is_swing_low = np.zeros(n, dtype=bool)
    
    for p in range(left_bars, n - right_bars):
        h_p = highs[p]
        if np.all(h_p > highs[p - left_bars : p]) and np.all(h_p > highs[p + 1 : p + right_bars + 1]):
            is_swing_high[p] = True
            
        l_p = lows[p]
        if np.all(l_p < lows[p - left_bars : p]) and np.all(l_p < lows[p + 1 : p + right_bars + 1]):
            is_swing_low[p] = True
            
    for t in range(right_bars + 1, n):
        for p in range(t - right_bars, max(0, t - max_search), -1):
            if is_swing_high[p]:
                h_level = highs[p]
                if p + 1 < t:
                    if np.max(highs[p + 1 : t]) < h_level:
                        swing_highs[t] = h_level
                        break
                else:
                    swing_highs[t] = h_level
                    break
                    
        for p in range(t - right_bars, max(0, t - max_search), -1):
            if is_swing_low[p]:
                l_level = lows[p]
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
                  spread=0.25, lot=0.10, contract_size=100.0, lane_name="Lane"):
    n = len(df_exec)
    times = df_exec.index
    opens = df_exec['open'].values
    highs = df_exec['high'].values
    lows = df_exec['low'].values
    closes = df_exec['close'].values
    
    trades = []
    in_pos = 0
    entry_price = 0.0
    entry_time = None
    curr_sl = 0.0
    curr_tp = 0.0
    
    multiplier = contract_size * lot
    
    for i in range(1, n):
        t = times[i]
        o = opens[i]
        h = highs[i]
        l = lows[i]
        c = closes[i]
        
        # Position management
        if in_pos == 1:
            if l <= curr_sl:
                exit_price = min(o, curr_sl)
                pnl = (exit_price - entry_price) * multiplier
                trades.append({
                    'lane': lane_name, 'entry_time': entry_time, 'exit_time': t,
                    'direction': 'BUY', 'entry_price': entry_price, 'exit_price': exit_price,
                    'pnl': pnl, 'type': 'SL'
                })
                in_pos = 0
            elif h >= curr_tp:
                exit_price = max(o, curr_tp)
                pnl = (exit_price - entry_price) * multiplier
                trades.append({
                    'lane': lane_name, 'entry_time': entry_time, 'exit_time': t,
                    'direction': 'BUY', 'entry_price': entry_price, 'exit_price': exit_price,
                    'pnl': pnl, 'type': 'TP'
                })
                in_pos = 0
            else:
                if trail_dist > 0:
                    profit = h - entry_price
                    if profit >= trail_act:
                        new_sl = h - trail_dist
                        if new_sl >= curr_sl + trail_step:
                            curr_sl = new_sl
                            
        elif in_pos == -1:
            if h >= curr_sl:
                exit_price = max(o, curr_sl)
                pnl = (entry_price - exit_price) * multiplier
                trades.append({
                    'lane': lane_name, 'entry_time': entry_time, 'exit_time': t,
                    'direction': 'SELL', 'entry_price': entry_price, 'exit_price': exit_price,
                    'pnl': pnl, 'type': 'SL'
                })
                in_pos = 0
            elif l <= curr_tp:
                exit_price = min(o, curr_tp)
                pnl = (entry_price - exit_price) * multiplier
                trades.append({
                    'lane': lane_name, 'entry_time': entry_time, 'exit_time': t,
                    'direction': 'SELL', 'entry_price': entry_price, 'exit_price': exit_price,
                    'pnl': pnl, 'type': 'TP'
                })
                in_pos = 0
            else:
                if trail_dist > 0:
                    profit = entry_price - l
                    if profit >= trail_act:
                        new_sl = l + trail_dist
                        if new_sl <= curr_sl - trail_step:
                            curr_sl = new_sl
                            
        # Entry check
        if in_pos == 0:
            sh = swing_highs[i - 1]
            sl = swing_lows[i - 1]
            
            if not np.isnan(sh):
                trigger_buy = sh + offset_buy
                if o <= trigger_buy and h >= trigger_buy:
                    in_pos = 1
                    entry_price = trigger_buy + spread
                    entry_time = t
                    curr_sl = entry_price - sl_dist
                    curr_tp = entry_price + tp_dist
                    continue
                    
            if not np.isnan(sl):
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
    
    trades['month_key'] = trades['exit_time'].dt.to_period('M')
    monthly = trades.groupby('month_key')['pnl'].sum()
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

def run_asset_test(symbol, h1_path, spread, contract_size, lot=0.10):
    print(f"\n=======================================================")
    print(f"RUNNING TEST FOR: {symbol} (Spread: {spread}, ContractSize: {contract_size})")
    print(f"=======================================================")
    
    df_h1 = load_data(h1_path)
    df_h1 = df_h1.loc['2020-01-01':'2025-12-31']
    
    df_h4 = df_h1.resample('4h', label='right', closed='right').agg({
        'open': 'first', 'high': 'max', 'low': 'min', 'close': 'last'
    }).dropna()
    
    df_d1 = df_h1.resample('1D', label='right', closed='right').agg({
        'open': 'first', 'high': 'max', 'low': 'min', 'close': 'last'
    }).dropna()
    
    # Scale parameters if EURUSD (Gold points vs EURUSD pips)
    scale = 1.0 if symbol == 'XAUUSD' else 0.001
    
    lanes_cfg = {
        'Lane_0_D1_Conservative': {
            'tf': 'D1', 'left': 24, 'right': 3, 'search': 105,
            'offset_buy': -2.75 * scale, 'offset_sell': -2.75 * scale,
            'sl': 61.0 * scale, 'tp': 14.5 * scale,
            'trail_act': 10.0 * scale, 'trail_dist': 18.0 * scale, 'trail_step': 1.0 * scale
        },
        'Lane_1_D1_Asymmetric': {
            'tf': 'D1', 'left': 15, 'right': 3, 'search': 230,
            'offset_buy': -1.70 * scale, 'offset_sell': -1.70 * scale,
            'sl': 10.0 * scale, 'tp': 41.0 * scale,
            'trail_act': 5.0 * scale, 'trail_dist': 4.5 * scale, 'trail_step': 0.5 * scale
        },
        'Lane_2_D1_Agile': {
            'tf': 'D1', 'left': 7, 'right': 2, 'search': 20,
            'offset_buy': -1.12 * scale, 'offset_sell': -1.12 * scale,
            'sl': 7.0 * scale, 'tp': 36.3 * scale,
            'trail_act': 5.0 * scale, 'trail_dist': 5.0 * scale, 'trail_step': 0.5 * scale
        },
        'Lane_3_H4_Asymmetric': {
            'tf': 'H4', 'left': 12, 'right': 8, 'search': 90,
            'offset_buy': -0.40 * scale, 'offset_sell': -1.00 * scale,
            'sl': 8.0 * scale, 'tp': 49.0 * scale,
            'trail_act': 8.0 * scale, 'trail_dist': 13.0 * scale, 'trail_step': 1.0 * scale
        },
        'Lane_4_H1_Medium': {
            'tf': 'H1', 'left': 30, 'right': 19, 'search': 110,
            'offset_buy': -1.15 * scale, 'offset_sell': -1.15 * scale,
            'sl': 53.0 * scale, 'tp': 9.27 * scale,
            'trail_act': 5.0 * scale, 'trail_dist': 4.95 * scale, 'trail_step': 0.5 * scale
        },
        'Lane_5_H1_MicroRetest': {
            'tf': 'H1', 'left': 26, 'right': 24, 'search': 140,
            'offset_buy': -1.05 * scale, 'offset_sell': -1.05 * scale,
            'sl': 101.0 * scale, 'tp': 8.24 * scale,
            'trail_act': 5.0 * scale, 'trail_dist': 5.0 * scale, 'trail_step': 0.5 * scale
        }
    }
    
    fractals_map = {}
    for lane_id, cfg in lanes_cfg.items():
        tf = cfg['tf']
        l, r, s = cfg['left'], cfg['right'], cfg['search']
        if tf == 'D1':
            sh, sl = precompute_fractals(df_d1, l, r, s)
            s_sh = pd.Series(sh, index=df_d1.index).reindex(df_h1.index, method='ffill')
            s_sl = pd.Series(sl, index=df_d1.index).reindex(df_h1.index, method='ffill')
            fractals_map[lane_id] = (s_sh.values, s_sl.values)
        elif tf == 'H4':
            sh, sl = precompute_fractals(df_h4, l, r, s)
            s_sh = pd.Series(sh, index=df_h4.index).reindex(df_h1.index, method='ffill')
            s_sl = pd.Series(sl, index=df_h4.index).reindex(df_h1.index, method='ffill')
            fractals_map[lane_id] = (s_sh.values, s_sl.values)
        else:
            sh, sl = precompute_fractals(df_h1, l, r, s)
            fractals_map[lane_id] = (sh, sl)
            
    lane_trades = {}
    lane_perf = {}
    for lane_id, cfg in lanes_cfg.items():
        sh, sl = fractals_map[lane_id]
        tr = simulate_lane(
            df_h1, sh, sl,
            cfg['offset_buy'], cfg['offset_sell'], cfg['sl'], cfg['tp'],
            cfg['trail_act'], cfg['trail_dist'], cfg['trail_step'],
            spread=spread, lot=lot, contract_size=contract_size, lane_name=lane_id
        )
        lane_trades[lane_id] = tr
        perf = evaluate_performance(tr)
        lane_perf[lane_id] = perf
        print(f"[{lane_id}] {perf['trades']:4d} trds | Net: +${perf['net_profit']:10.2f} | PF: {perf['profit_factor']:.3f} | WR: {perf['win_rate']:5.2f}% | MaxDD: ${perf['max_dd']:8.2f} | RoMaD: {perf['romad']:6.2f}x | MCR: {perf['mcr']:.1f}%")
        
    # Portfolio Combinations
    portfolios = {}
    
    # 1. Asymmetric Trio: L1 (D1) + L2 (D1) + L3 (H4)
    trio_tr = pd.concat([lane_trades['Lane_1_D1_Asymmetric'], lane_trades['Lane_2_D1_Agile'], lane_trades['Lane_3_H4_Asymmetric']], ignore_index=True)
    portfolios['Asymmetric_Trio_L1_L2_L3'] = evaluate_performance(trio_tr)
    
    # 2. Asymmetric Duo (High R:R): L1 (D1) + L3 (H4)
    duo_tr = pd.concat([lane_trades['Lane_1_D1_Asymmetric'], lane_trades['Lane_3_H4_Asymmetric']], ignore_index=True)
    portfolios['Asymmetric_Duo_L1_L3'] = evaluate_performance(duo_tr)
    
    # 3. High Expectancy Quad: L1 (D1) + L3 (H4) + L4 (H1) + L5 (H1)
    quad_tr = pd.concat([lane_trades['Lane_1_D1_Asymmetric'], lane_trades['Lane_3_H4_Asymmetric'], lane_trades['Lane_4_H1_Medium'], lane_trades['Lane_5_H1_MicroRetest']], ignore_index=True)
    portfolios['High_Expectancy_Quad_L1_L3_L4_L5'] = evaluate_performance(quad_tr)
    
    # 4. Multi-Horizon Quintet: L0 + L1 + L3 + L4 + L5
    quint_tr = pd.concat([lane_trades['Lane_0_D1_Conservative'], lane_trades['Lane_1_D1_Asymmetric'], lane_trades['Lane_3_H4_Asymmetric'], lane_trades['Lane_4_H1_Medium'], lane_trades['Lane_5_H1_MicroRetest']], ignore_index=True)
    portfolios['Multi_Horizon_Quintet_L0_L1_L3_L4_L5'] = evaluate_performance(quint_tr)
    
    print(f"\n--- PORTFOLIO SYNTHESIS ({symbol}) ---")
    for pname, pperf in portfolios.items():
        print(f"[{pname}]")
        print(f"  Trades: {pperf['trades']:4d} | Net: +${pperf['net_profit']:10.2f} | PF: {pperf['profit_factor']:.3f} | WR: {pperf['win_rate']:5.2f}% | MaxDD: ${pperf['max_dd']:8.2f} | RoMaD: {pperf['romad']:6.2f}x | MCR: {pperf['mcr']:.1f}%")
        
    return {
        'lanes': lane_perf,
        'portfolios': portfolios
    }

def main():
    print("=" * 80)
    print("LIZARD & GOLD REAPER CLEAN QUANT: FULL 72-MONTH MULTI-ASSET OPTIMIZATION")
    print("=" * 80)
    
    xau_path = "/content/projects/quant_strategy_discovery/data/XAUUSD_H1.parquet"
    eur_path = "/content/projects/quant_strategy_discovery/data/EURUSD_H1.parquet"
    
    all_results = {}
    
    # 1. Gold (XAUUSD): spread = $0.25, contract_size = 100.0, lot = 0.10
    if os.path.exists(xau_path):
        all_results['XAUUSD'] = run_asset_test('XAUUSD', xau_path, spread=0.25, contract_size=100.0, lot=0.10)
        
    # 2. EURUSD: spread = 0.00015 (1.5 pips), contract_size = 100,000.0, lot = 0.10
    if os.path.exists(eur_path):
        all_results['EURUSD'] = run_asset_test('EURUSD', eur_path, spread=0.00015, contract_size=100000.0, lot=0.10)
        
    out_dir = "/content/projects/quant_strategy_discovery/results"
    os.makedirs(out_dir, exist_ok=True)
    out_file = os.path.join(out_dir, "lizard_gold_reaper_portfolio_optimization_results.json")
    with open(out_file, "w") as f:
        json.dump(all_results, f, indent=2)
    print(f"\n[✓] All optimization results saved to: {out_file}")

if __name__ == "__main__":
    main()
