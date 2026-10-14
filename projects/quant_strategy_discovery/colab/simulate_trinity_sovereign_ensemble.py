#!/usr/bin/env python3
"""
SIMULATE TRINITY SOVEREIGN MULTI-ALPHA ENSEMBLE (GHOST + TITAN + LIZARD/REAPER)
Combines 3 completely orthogonal market mechanics into a unified institutional master portfolio:
1. Ghost Scalper Clean Quant (4 Lanes: Intraday fractal swing structure retest)
2. Quantum Titan Clean Quant (Core B: H1 50 SMA / ATR volatility band pullback)
3. Lizard / Gold Reaper Clean Quant (Lanes 1 & 3: D1 & H4 macro asymmetric breakout)
Assets: XAUUSD (Gold CFD)
Span: 72 Months (2020-01-01 to 2025-12-31)
Rule Mandate: Constitution V5.0 - Strictly Single-Position per Engine, Disciplined SL/TP, Zero Martingale.
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

def compute_kfd(series_close, n=24):
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

def simulate_ghost_lane(df, left_bars, right_bars, offset_buy, offset_sell,
                        sl_points, tp_points, trail_act, trail_dist, trail_step,
                        ema_filter, kfd_filter, kfd_thresh=1.42,
                        spread=0.25, lot=0.10, engine_name="Ghost"):
    n = len(df)
    times = df.index
    opens = df['open'].values
    highs = df['high'].values
    lows = df['low'].values
    closes = df['close'].values
    
    sh, sl = precompute_fractals(df, left_bars, right_bars, max_search=150)
    
    trades = []
    in_pos = 0
    entry_price = 0.0
    entry_time = None
    curr_sl = 0.0
    curr_tp = 0.0
    multiplier = 100.0 * lot
    
    for i in range(1, n):
        t = times[i]
        o = opens[i]
        h = highs[i]
        l = lows[i]
        c = closes[i]
        
        if in_pos == 1:
            if l <= curr_sl:
                exit_price = min(o, curr_sl)
                pnl = (exit_price - entry_price) * multiplier
                trades.append({'engine': engine_name, 'exit_time': t, 'pnl': pnl})
                in_pos = 0
            elif h >= curr_tp:
                exit_price = max(o, curr_tp)
                pnl = (exit_price - entry_price) * multiplier
                trades.append({'engine': engine_name, 'exit_time': t, 'pnl': pnl})
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
                trades.append({'engine': engine_name, 'exit_time': t, 'pnl': pnl})
                in_pos = 0
            elif l <= curr_tp:
                exit_price = min(o, curr_tp)
                pnl = (entry_price - exit_price) * multiplier
                trades.append({'engine': engine_name, 'exit_time': t, 'pnl': pnl})
                in_pos = 0
            else:
                if trail_dist > 0:
                    profit = entry_price - l
                    if profit >= trail_act:
                        new_sl = l + trail_dist
                        if new_sl <= curr_sl - trail_step:
                            curr_sl = new_sl
                            
        if in_pos == 0:
            can_long = True
            can_short = True
            if ema_filter is not None:
                if closes[i - 1] < ema_filter[i - 1]: can_long = False
                if closes[i - 1] > ema_filter[i - 1]: can_short = False
            if kfd_filter is not None and kfd_filter[i - 1] > kfd_thresh:
                can_long = False
                can_short = False
                
            sh_val = sh[i - 1]
            sl_val = sl[i - 1]
            
            if can_long and not np.isnan(sh_val):
                trig = sh_val + offset_buy
                if o <= trig and h >= trig:
                    in_pos = 1
                    entry_price = trig + spread
                    entry_time = t
                    curr_sl = entry_price - sl_points
                    curr_tp = entry_price + tp_points
                    continue
                    
            if can_short and not np.isnan(sl_val):
                trig = sl_val - offset_sell
                if o >= trig and l <= trig:
                    in_pos = -1
                    entry_price = trig
                    entry_time = t
                    curr_sl = entry_price + sl_points
                    curr_tp = entry_price - tp_points
                    continue
                    
    return pd.DataFrame(trades)

def simulate_titan_core_b(df, spread=0.25, lot=0.10):
    df_c = df.copy()
    df_c['sma50'] = df_c['close'].rolling(50).mean()
    df_c['ema200'] = df_c['close'].ewm(span=200, adjust=False).mean()
    
    # ATR 14
    tr1 = df_c['high'] - df_c['low']
    tr2 = (df_c['high'] - df_c['close'].shift(1)).abs()
    tr3 = (df_c['low'] - df_c['close'].shift(1)).abs()
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    df_c['atr14'] = tr.rolling(14).mean()
    
    n = len(df_c)
    times = df_c.index
    opens = df_c['open'].values
    highs = df_c['high'].values
    lows = df_c['low'].values
    closes = df_c['close'].values
    sma50 = df_c['sma50'].values
    ema200 = df_c['ema200'].values
    atr = df_c['atr14'].values
    
    trades = []
    in_pos = 0
    entry_price = 0.0
    curr_sl = 0.0
    curr_tp = 0.0
    multiplier = 100.0 * lot
    
    for i in range(200, n):
        t = times[i]
        o = opens[i]
        h = highs[i]
        l = lows[i]
        c = closes[i]
        
        if in_pos == 1:
            if l <= curr_sl:
                exit_price = min(o, curr_sl)
                pnl = (exit_price - entry_price) * multiplier
                trades.append({'engine': 'Titan_CoreB', 'exit_time': t, 'pnl': pnl})
                in_pos = 0
            elif h >= curr_tp:
                exit_price = max(o, curr_tp)
                pnl = (exit_price - entry_price) * multiplier
                trades.append({'engine': 'Titan_CoreB', 'exit_time': t, 'pnl': pnl})
                in_pos = 0
        elif in_pos == -1:
            if h >= curr_sl:
                exit_price = max(o, curr_sl)
                pnl = (entry_price - exit_price) * multiplier
                trades.append({'engine': 'Titan_CoreB', 'exit_time': t, 'pnl': pnl})
                in_pos = 0
            elif l <= curr_tp:
                exit_price = min(o, curr_tp)
                pnl = (entry_price - exit_price) * multiplier
                trades.append({'engine': 'Titan_CoreB', 'exit_time': t, 'pnl': pnl})
                in_pos = 0
                
        if in_pos == 0:
            c_prev = closes[i - 1]
            sma_prev = sma50[i - 1]
            ema_prev = ema200[i - 1]
            atr_prev = atr[i - 1]
            
            # Pullback to 50 SMA in direction of 200 EMA
            if c_prev > ema_prev and c_prev <= sma_prev and closes[i - 2] > sma50[i - 2]:
                in_pos = 1
                entry_price = o + spread
                curr_sl = entry_price - (atr_prev * 1.5)
                curr_tp = entry_price + (atr_prev * 3.5)
            elif c_prev < ema_prev and c_prev >= sma_prev and closes[i - 2] < sma50[i - 2]:
                in_pos = -1
                entry_price = o
                curr_sl = entry_price + (atr_prev * 1.5)
                curr_tp = entry_price - (atr_prev * 3.5)
                
    return pd.DataFrame(trades)

def simulate_lizard_htf_lane(df_h1, df_htf, left_bars, right_bars, max_search,
                             offset_buy, offset_sell, sl_dist, tp_dist,
                             trail_act, trail_dist, trail_step,
                             spread=0.25, lot=0.10, engine_name="Lizard"):
    sh, sl = precompute_fractals(df_htf, left_bars, right_bars, max_search)
    s_sh = pd.Series(sh, index=df_htf.index).reindex(df_h1.index, method='ffill').values
    s_sl = pd.Series(sl, index=df_htf.index).reindex(df_h1.index, method='ffill').values
    
    n = len(df_h1)
    times = df_h1.index
    opens = df_h1['open'].values
    highs = df_h1['high'].values
    lows = df_h1['low'].values
    
    trades = []
    in_pos = 0
    entry_price = 0.0
    curr_sl = 0.0
    curr_tp = 0.0
    multiplier = 100.0 * lot
    
    for i in range(1, n):
        t = times[i]
        o = opens[i]
        h = highs[i]
        l = lows[i]
        
        if in_pos == 1:
            if l <= curr_sl:
                exit_price = min(o, curr_sl)
                pnl = (exit_price - entry_price) * multiplier
                trades.append({'engine': engine_name, 'exit_time': t, 'pnl': pnl})
                in_pos = 0
            elif h >= curr_tp:
                exit_price = max(o, curr_tp)
                pnl = (exit_price - entry_price) * multiplier
                trades.append({'engine': engine_name, 'exit_time': t, 'pnl': pnl})
                in_pos = 0
            else:
                if trail_dist > 0 and (h - entry_price) >= trail_act:
                    new_sl = h - trail_dist
                    if new_sl >= curr_sl + trail_step: curr_sl = new_sl
        elif in_pos == -1:
            if h >= curr_sl:
                exit_price = max(o, curr_sl)
                pnl = (entry_price - exit_price) * multiplier
                trades.append({'engine': engine_name, 'exit_time': t, 'pnl': pnl})
                in_pos = 0
            elif l <= curr_tp:
                exit_price = min(o, curr_tp)
                pnl = (entry_price - exit_price) * multiplier
                trades.append({'engine': engine_name, 'exit_time': t, 'pnl': pnl})
                in_pos = 0
            else:
                if trail_dist > 0 and (entry_price - l) >= trail_act:
                    new_sl = l + trail_dist
                    if new_sl <= curr_sl - trail_step: curr_sl = new_sl
                    
        if in_pos == 0:
            sh_val = s_sh[i - 1]
            sl_val = s_sl[i - 1]
            if not np.isnan(sh_val):
                trig = sh_val + offset_buy
                if o <= trig and h >= trig:
                    in_pos = 1
                    entry_price = trig + spread
                    curr_sl = entry_price - sl_dist
                    curr_tp = entry_price + tp_dist
                    continue
            if not np.isnan(sl_val):
                trig = sl_val - offset_sell
                if o >= trig and l <= trig:
                    in_pos = -1
                    entry_price = trig
                    curr_sl = entry_price + sl_dist
                    curr_tp = entry_price - tp_dist
                    continue
                    
    return pd.DataFrame(trades)

def evaluate_performance(df_trades, initial_balance=10000.0):
    if df_trades.empty or len(df_trades) == 0:
        return {'trades': 0, 'net_profit': 0.0, 'profit_factor': 0.0, 'win_rate': 0.0, 'max_dd': 0.0, 'romad': 0.0, 'mcr': 0.0}
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
    
    pf = round(gross_profit / gross_loss, 3) if gross_loss > 0 else 999.0
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
        'trades': len(trades), 'net_profit': net_profit, 'profit_factor': pf,
        'win_rate': win_rate, 'max_dd': round(max_dd, 2), 'romad': romad,
        'mcr': mcr, 'profitable_months': profitable_months, 'total_months': total_months
    }

def main():
    print("=" * 80)
    print("AUTONOMOUS RESEARCH: TRINITY SOVEREIGN MULTI-ALPHA ENSEMBLE (72 MONTHS)")
    print("=" * 80)
    
    xau_path = "/content/projects/quant_strategy_discovery/data/XAUUSD_H1.parquet"
    df_h1 = load_data(xau_path).loc['2020-01-01':'2025-12-31']
    df_h4 = df_h1.resample('4h', label='right', closed='right').agg({'open':'first','high':'max','low':'min','close':'last'}).dropna()
    df_d1 = df_h1.resample('1D', label='right', closed='right').agg({'open':'first','high':'max','low':'min','close':'last'}).dropna()
    
    df_h1['ema200'] = df_h1['close'].ewm(span=200, adjust=False).mean()
    df_h1['kfd24'] = compute_kfd(df_h1['close'], n=24)
    
    ema = df_h1['ema200'].values
    kfd = df_h1['kfd24'].values
    
    # 1. Simulate Ghost Scalper Enhanced (4 Lanes)
    print("[*] Simulating Ghost Scalper Enhanced (4 Lanes)...")
    tr_g_a = simulate_ghost_lane(df_h1, 10, 7, -1.8, 1.8, 5.0, 15.0, 0.0, 0.9, 0.3, ema, kfd, engine_name="Ghost_A")
    tr_g_b = simulate_ghost_lane(df_h1, 13, 3, -1.5, 1.9, 5.0, 25.0, 0.15, 1.15, 0.4, ema, kfd, engine_name="Ghost_B")
    tr_g_c = simulate_ghost_lane(df_h1, 7, 5, -2.2, 2.2, 10.0, 25.0, 0.15, 0.9, 0.2, ema, kfd, engine_name="Ghost_C")
    tr_g_d = simulate_ghost_lane(df_h1, 26, 20, -1.8, 1.8, 8.0, 17.0, 1.0, 0.35, 0.55, ema, kfd, engine_name="Ghost_D")
    ghost_all = pd.concat([tr_g_a, tr_g_b, tr_g_c, tr_g_d], ignore_index=True)
    perf_ghost = evaluate_performance(ghost_all)
    
    # 2. Simulate Quantum Titan Core B
    print("[*] Simulating Quantum Titan Core B...")
    tr_titan = simulate_titan_core_b(df_h1)
    perf_titan = evaluate_performance(tr_titan)
    
    # 3. Simulate Lizard / Gold Reaper Asymmetric Lanes (L1 [D1] & L3 [H4])
    print("[*] Simulating Lizard / Gold Reaper Asymmetric Lanes (D1 & H4)...")
    tr_liz_l1 = simulate_lizard_htf_lane(df_h1, df_d1, 15, 3, 230, -1.70, -1.70, 10.0, 41.0, 5.0, 4.5, 0.5, engine_name="Lizard_L1_D1")
    tr_liz_l3 = simulate_lizard_htf_lane(df_h1, df_htf=df_h4, left_bars=12, right_bars=8, max_search=90, offset_buy=-0.40, offset_sell=-1.00, sl_dist=8.0, tp_dist=49.0, trail_act=8.0, trail_dist=13.0, trail_step=1.0, engine_name="Lizard_L3_H4")
    lizard_duo = pd.concat([tr_liz_l1, tr_liz_l3], ignore_index=True)
    perf_lizard = evaluate_performance(lizard_duo)
    
    # 4. Trinity Sovereign Ensemble (Ghost 4 Lanes + Titan Core B + Lizard Asymmetric Duo)
    print("[*] Assembling Trinity Sovereign Ensemble Master Portfolio...")
    trinity_all = pd.concat([ghost_all, tr_titan, lizard_duo], ignore_index=True)
    perf_trinity = evaluate_performance(trinity_all)
    
    results = {
        'Ghost_Scalper_Enhanced': perf_ghost,
        'Quantum_Titan_CoreB': perf_titan,
        'Lizard_Asymmetric_Duo': perf_lizard,
        'Trinity_Sovereign_Master_Ensemble': perf_trinity
    }
    
    print("\n" + "=" * 80)
    print("TRINITY SOVEREIGN MULTI-ALPHA ENSEMBLE RESULTS (72 MONTHS XAUUSD H1)")
    print("=" * 80)
    for name, p in results.items():
        print(f"[{name}]")
        print(f"  Trades: {p['trades']:4d} | Net: +${p['net_profit']:10.2f} | PF: {p['profit_factor']:.3f} | WR: {p['win_rate']:5.2f}% | MaxDD: ${p['max_dd']:8.2f} | RoMaD: {p['romad']:6.2f}x | MCR: {p['mcr']:.1f}% ({p.get('profitable_months', 0)}/72 mo)")
        
    out_file = "/content/projects/quant_strategy_discovery/results/trinity_sovereign_ensemble_results.json"
    with open(out_file, "w") as f:
        json.dump(results, f, indent=2)
    print(f"\n[✓] Results saved to: {out_file}")

if __name__ == "__main__":
    main()
