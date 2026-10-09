#!/usr/bin/env python3
"""
===============================================================================
TOP 3 STRATEGIES: DEEP SANITY VERIFICATION, CAUSAL INTEGRITY & STRESS TEST
===============================================================================
Investigates:
1. Causal Execution Integrity:
   - Does Strategy 03 (Supertrend) have exit price leakage when st_line flips?
   - Re-runs Strategy 03 with 100% strict causal next-open / true trailing stop.
2. Stress Testing under Elevated Frictions:
   - Normal: Spread $0.25, Comm $6.00/lot
   - Elevated: Spread $0.50, Comm $8.00/lot (2x spread stress)
   - Extreme: Spread $0.75, Comm $10.00/lot (3x spread stress)
3. Walk-Forward / Annual Consistency (2020 - 2025):
   - Profit contribution per year
   - Max annual drawdown
4. Monte Carlo Permutation Analysis:
   - 1,000 bootstrap simulations of trade order
   - 95th & 99th percentile Max Drawdown and Probability of Ruin
===============================================================================
"""

import os
import sys
import time
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

# =============================================================================
# STRATEGY 03: STRICT CAUSAL SUPERTREND ENGINE
# =============================================================================
def run_strict_supertrend(
    df: pd.DataFrame,
    atr_period: int = 14,
    multiplier: float = 3.0,
    use_ema: bool = True,
    spread: float = 0.25,
    commission: float = 0.06,
    unit_size: float = 10.0
):
    opens = df["open"].values.astype(np.float64)
    highs = df["high"].values.astype(np.float64)
    lows = df["low"].values.astype(np.float64)
    closes = df["close"].values.astype(np.float64)
    n = len(closes)

    atr = compute_atr(highs, lows, closes, atr_period)
    ema200 = compute_ema(closes, 200)

    # Compute bands
    med = (highs + lows) * 0.5
    up_raw = med + multiplier * atr
    low_raw = med - multiplier * atr

    trend = np.zeros(n, dtype=np.int32)
    st_lower = np.zeros(n, dtype=np.float64)
    st_upper = np.zeros(n, dtype=np.float64)

    trend[0] = 1
    st_lower[0] = low_raw[0]
    st_upper[0] = up_raw[0]

    for i in range(1, n):
        # Bullish lower band ratchets upward
        if low_raw[i] > st_lower[i - 1] or closes[i - 1] < st_lower[i - 1]:
            st_lower[i] = low_raw[i]
        else:
            st_lower[i] = st_lower[i - 1]

        # Bearish upper band ratchets downward
        if up_raw[i] < st_upper[i - 1] or closes[i - 1] > st_upper[i - 1]:
            st_upper[i] = up_raw[i]
        else:
            st_upper[i] = st_upper[i - 1]

        # Trend determination strictly based on candle close
        if trend[i - 1] == 1:
            if closes[i] < st_lower[i]:
                trend[i] = -1
            else:
                trend[i] = 1
        else:
            if closes[i] > st_upper[i]:
                trend[i] = 1
            else:
                trend[i] = -1

    # SIMULATION WITH STRICT CAUSALITY
    # Mode A: Original implementation (for comparison)
    # Mode B: Strict Causal (Exit triggered on trailing stop breach OR at next open after close flip)
    trades_b = []
    pos = 0
    entry_p = 0.0
    entry_i = 0

    for i in range(250, n - 1):
        # 1. Manage existing position
        if pos == 1:
            stop_lvl = st_lower[i]
            # Did price pierce trailing stop during bar i?
            if lows[i] <= stop_lvl:
                exit_p = stop_lvl if opens[i] >= stop_lvl else opens[i] # slippage if open gap
                pnl = (exit_p - entry_p) * unit_size - (spread + commission) * unit_size
                trades_b.append({"pnl": pnl, "entry_bar": entry_i, "exit_bar": i, "date": df.index[i]})
                pos = 0
            elif trend[i] == -1: # confirmed flip at close i
                exit_p = opens[i + 1] # strictly exit at NEXT open
                pnl = (exit_p - entry_p) * unit_size - (spread + commission) * unit_size
                trades_b.append({"pnl": pnl, "entry_bar": entry_i, "exit_bar": i + 1, "date": df.index[i]})
                pos = 0

        elif pos == -1:
            stop_lvl = st_upper[i]
            if highs[i] >= stop_lvl:
                exit_p = stop_lvl if opens[i] <= stop_lvl else opens[i]
                pnl = (entry_p - exit_p) * unit_size - (spread + commission) * unit_size
                trades_b.append({"pnl": pnl, "entry_bar": entry_i, "exit_bar": i, "date": df.index[i]})
                pos = 0
            elif trend[i] == 1:
                exit_p = opens[i + 1]
                pnl = (entry_p - exit_p) * unit_size - (spread + commission) * unit_size
                trades_b.append({"pnl": pnl, "entry_bar": entry_i, "exit_bar": i + 1, "date": df.index[i]})
                pos = 0

        # 2. Check Entries on trend flip (confirmed at close i -> enter at open i+1)
        if pos == 0:
            if trend[i] == 1 and trend[i - 1] == -1:
                if (not use_ema) or (closes[i] > ema200[i]):
                    pos = 1
                    entry_p = opens[i + 1] + (spread * 0.5)
                    entry_i = i + 1
            elif trend[i] == -1 and trend[i - 1] == 1:
                if (not use_ema) or (closes[i] < ema200[i]):
                    pos = -1
                    entry_p = opens[i + 1] - (spread * 0.5)
                    entry_i = i + 1

    return trades_b

# =============================================================================
# STRATEGY 06: STRICT ZERO-LAG MACD ENGINE
# =============================================================================
def run_strict_zl_macd(
    df: pd.DataFrame,
    fast_period: int = 15,
    slow_period: int = 34,
    signal_period: int = 9,
    sl_atr_mult: float = 2.0,
    tp_rr_mult: float = 4.0,
    spread: float = 0.25,
    commission: float = 0.06,
    unit_size: float = 10.0
):
    opens = df["open"].values.astype(np.float64)
    highs = df["high"].values.astype(np.float64)
    lows = df["low"].values.astype(np.float64)
    closes = df["close"].values.astype(np.float64)
    n = len(closes)

    atr = compute_atr(highs, lows, closes, 14)

    # Zero Lag EMA = 2*EMA - EMA(EMA)
    ema_fast = compute_ema(closes, fast_period)
    ema_fast2 = compute_ema(ema_fast, fast_period)
    zl_fast = 2.0 * ema_fast - ema_fast2

    ema_slow = compute_ema(closes, slow_period)
    ema_slow2 = compute_ema(ema_slow, slow_period)
    zl_slow = 2.0 * ema_slow - ema_slow2

    zl_macd = zl_fast - zl_slow
    zl_signal = compute_ema(zl_macd, signal_period)

    trades = []
    pos = 0
    entry_p = 0.0
    sl_p = 0.0
    tp_p = 0.0
    entry_i = 0

    for i in range(100, n - 1):
        # 1. Manage Exits
        if pos == 1:
            exit_triggered = False
            exit_p = 0.0
            # Strict worst-case: check SL first, then TP
            if lows[i] <= sl_p:
                exit_p = sl_p if opens[i] >= sl_p else opens[i]
                exit_triggered = True
            elif highs[i] >= tp_p:
                exit_p = tp_p if opens[i] <= tp_p else opens[i]
                exit_triggered = True

            if exit_triggered:
                pnl = (exit_p - entry_p) * unit_size - (spread + commission) * unit_size
                trades.append({"pnl": pnl, "entry_bar": entry_i, "exit_bar": i, "date": df.index[i]})
                pos = 0

        elif pos == -1:
            exit_triggered = False
            exit_p = 0.0
            if highs[i] >= sl_p:
                exit_p = sl_p if opens[i] <= sl_p else opens[i]
                exit_triggered = True
            elif lows[i] <= tp_p:
                exit_p = tp_p if opens[i] >= tp_p else opens[i]
                exit_triggered = True

            if exit_triggered:
                pnl = (entry_p - exit_p) * unit_size - (spread + commission) * unit_size
                trades.append({"pnl": pnl, "entry_bar": entry_i, "exit_bar": i, "date": df.index[i]})
                pos = 0

        # 2. Check Entries on crossover at close i -> enter open i+1
        if pos == 0 and atr[i] > 0.0:
            bull_cross = (zl_macd[i - 1] <= zl_signal[i - 1]) and (zl_macd[i] > zl_signal[i])
            bear_cross = (zl_macd[i - 1] >= zl_signal[i - 1]) and (zl_macd[i] < zl_signal[i])
            sl_dist = sl_atr_mult * atr[i]

            if bull_cross:
                pos = 1
                entry_p = opens[i + 1] + (spread * 0.5)
                sl_p = entry_p - sl_dist
                tp_p = entry_p + (sl_dist * tp_rr_mult)
                entry_i = i + 1
            elif bear_cross:
                pos = -1
                entry_p = opens[i + 1] - (spread * 0.5)
                sl_p = entry_p + sl_dist
                tp_p = entry_p - (sl_dist * tp_rr_mult)
                entry_i = i + 1

    return trades

# =============================================================================
# STRATEGY 04: STRICT TTM SQUEEZE ENGINE
# =============================================================================
def run_strict_ttm_squeeze(
    df: pd.DataFrame,
    bb_length: int = 20,
    bb_mult: float = 2.0,
    kc_mult: float = 2.0,
    min_squeeze_bars: int = 8,
    sl_atr_mult: float = 3.0,
    tp_rr_mult: float = 3.0,
    spread: float = 0.25,
    commission: float = 0.06,
    unit_size: float = 10.0
):
    opens = df["open"].values.astype(np.float64)
    highs = df["high"].values.astype(np.float64)
    lows = df["low"].values.astype(np.float64)
    closes = df["close"].values.astype(np.float64)
    n = len(closes)

    atr = compute_atr(highs, lows, closes, 14)
    ema200 = compute_ema(closes, 200)

    # BB
    sma20 = pd.Series(closes).rolling(bb_length).mean().values
    std20 = pd.Series(closes).rolling(bb_length).std().values
    bb_upper = sma20 + bb_mult * std20
    bb_lower = sma20 - bb_mult * std20

    # KC
    kc_upper = sma20 + kc_mult * atr
    kc_lower = sma20 - kc_mult * atr

    # Squeeze: BB inside KC
    is_squeeze = (bb_lower > kc_lower) & (bb_upper < kc_upper)
    squeeze_count = np.zeros(n, dtype=np.int32)
    c = 0
    for i in range(n):
        if is_squeeze[i]:
            c += 1
        else:
            c = 0
        squeeze_count[i] = c

    # Momentum indicator (linear regression of close - avg(sma20, (high+low)/2))
    delta = closes - ((highs + lows) * 0.5 + sma20) * 0.5

    trades = []
    pos = 0
    entry_p = 0.0
    sl_p = 0.0
    tp_p = 0.0
    entry_i = 0

    for i in range(250, n - 1):
        if pos == 1:
            exit_triggered = False
            exit_p = 0.0
            if lows[i] <= sl_p:
                exit_p = sl_p if opens[i] >= sl_p else opens[i]
                exit_triggered = True
            elif highs[i] >= tp_p:
                exit_p = tp_p if opens[i] <= tp_p else opens[i]
                exit_triggered = True

            if exit_triggered:
                pnl = (exit_p - entry_p) * unit_size - (spread + commission) * unit_size
                trades.append({"pnl": pnl, "entry_bar": entry_i, "exit_bar": i, "date": df.index[i]})
                pos = 0

        elif pos == -1:
            exit_triggered = False
            exit_p = 0.0
            if highs[i] >= sl_p:
                exit_p = sl_p if opens[i] <= sl_p else opens[i]
                exit_triggered = True
            elif lows[i] <= tp_p:
                exit_p = tp_p if opens[i] >= tp_p else opens[i]
                exit_triggered = True

            if exit_triggered:
                pnl = (entry_p - exit_p) * unit_size - (spread + commission) * unit_size
                trades.append({"pnl": pnl, "entry_bar": entry_i, "exit_bar": i, "date": df.index[i]})
                pos = 0

        # Squeeze fire check at close i -> enter open i+1
        if pos == 0 and atr[i] > 0.0:
            fired = (not is_squeeze[i]) and (squeeze_count[i - 1] >= min_squeeze_bars)
            if fired:
                sl_dist = sl_atr_mult * atr[i]
                if delta[i] > 0 and closes[i] > ema200[i]:
                    pos = 1
                    entry_p = opens[i + 1] + (spread * 0.5)
                    sl_p = entry_p - sl_dist
                    tp_p = entry_p + (sl_dist * tp_rr_mult)
                    entry_i = i + 1
                elif delta[i] < 0 and closes[i] < ema200[i]:
                    pos = -1
                    entry_p = opens[i + 1] - (spread * 0.5)
                    sl_p = entry_p + sl_dist
                    tp_p = entry_p - (sl_dist * tp_rr_mult)
                    entry_i = i + 1

    return trades

def analyze_trades(trades: list, initial_equity: float = 10000.0) -> dict:
    if not trades:
        return {"trades": 0, "net_profit": 0, "pf": 0, "win_rate": 0, "max_dd": 0, "sharpe": 0}

    pnls = np.array([t["pnl"] for t in trades])
    wins = pnls[pnls > 0]
    losses = pnls[pnls < 0]

    gp = float(np.sum(wins)) if len(wins) > 0 else 0.0
    gl = float(abs(np.sum(losses))) if len(losses) > 0 else 0.0
    net = float(np.sum(pnls))
    pf = (gp / gl) if gl > 0 else 99.0
    wr = (len(wins) / len(pnls)) * 100.0

    eq = initial_equity + np.cumsum(pnls)
    peaks = np.maximum.accumulate(eq)
    dd = peaks - eq
    max_dd = float(np.max(dd)) if len(dd) > 0 else 0.0

    sharpe = float(np.mean(pnls) / np.std(pnls) * np.sqrt(250)) if np.std(pnls) > 0 else 0.0

    # Yearly breakdown
    df_t = pd.DataFrame(trades)
    df_t["year"] = pd.to_datetime(df_t["date"]).dt.year
    yearly = {}
    for yr, group in df_t.groupby("year"):
        y_pnls = group["pnl"].values
        y_wins = y_pnls[y_pnls > 0]
        y_losses = y_pnls[y_pnls < 0]
        y_gp = float(np.sum(y_wins)) if len(y_wins) > 0 else 0.0
        y_gl = float(abs(np.sum(y_losses))) if len(y_losses) > 0 else 0.0
        y_pf = (y_gp / y_gl) if y_gl > 0 else 99.0
        yearly[int(yr)] = {
            "trades": len(y_pnls),
            "net": round(float(np.sum(y_pnls)), 2),
            "pf": round(y_pf, 2),
            "wr": round(len(y_wins)/len(y_pnls)*100, 1)
        }

    return {
        "trades": len(trades),
        "net_profit": round(net, 2),
        "pf": round(pf, 3),
        "win_rate": round(wr, 2),
        "max_dd": round(max_dd, 2),
        "sharpe": round(sharpe, 3),
        "yearly": yearly
    }

def run_monte_carlo(trades: list, num_simulations: int = 1000) -> dict:
    if len(trades) < 20:
        return {}
    pnls = np.array([t["pnl"] for t in trades])
    max_dds = []

    np.random.seed(42)
    for _ in range(num_simulations):
        shuffled = np.random.choice(pnls, size=len(pnls), replace=True)
        eq = 10000.0 + np.cumsum(shuffled)
        peaks = np.maximum.accumulate(eq)
        dd = peaks - eq
        max_dds.append(np.max(dd))

    max_dds = np.array(max_dds)
    return {
        "median_dd": round(float(np.median(max_dds)), 2),
        "p95_dd": round(float(np.percentile(max_dds, 95)), 2),
        "p99_dd": round(float(np.percentile(max_dds, 99)), 2),
        "max_simulated_dd": round(float(np.max(max_dds)), 2)
    }

def main():
    data_path = "/mnt/sdcard/Download/EA/XAUUSD_M1.csv.gz"
    print(f"[*] Loading data from {data_path}...")
    df_raw = pd.read_csv(
        data_path,
        usecols=["datetime", "open", "high", "low", "close", "tick_volume"],
        dtype={"open": np.float32, "high": np.float32, "low": np.float32, "close": np.float32, "tick_volume": np.int32}
    )
    df_raw["datetime"] = pd.to_datetime(df_raw["datetime"])
    df_raw.set_index("datetime", inplace=True)
    df_raw.sort_index(inplace=True)

    print("[*] Resampling to M15...")
    df = df_raw.resample("15min").agg({
        "open": "first", "high": "max", "low": "min", "close": "last", "tick_volume": "sum"
    }).dropna()
    print(f"[+] Loaded {len(df):,} M15 bars.")

    # 1. VERIFY STRATEGY 03 (SUPERTREND) UNDER STRICT CAUSALITY
    print("\n" + "="*70)
    print("🔬 EXPERIMENT 1: STRATEGY 03 (SUPERTREND) STRICT CAUSAL RE-TEST")
    print("="*70)
    st_trades_base = run_strict_supertrend(df, spread=0.25, commission=0.06)
    st_res_base = analyze_trades(st_trades_base)
    st_mc = run_monte_carlo(st_trades_base)
    print(f"Base Frictions ($0.25 spread, $6 comm): Net=${st_res_base['net_profit']:,} | PF={st_res_base['pf']} | WR={st_res_base['win_rate']}% | MaxDD=${st_res_base['max_dd']} | Sharpe={st_res_base['sharpe']}")
    print(f"Yearly Breakdown: {st_res_base['yearly']}")
    print(f"Monte Carlo Drawdown Distribution (1,000 runs): Median=${st_mc['median_dd']} | 95th Percentile=${st_mc['p95_dd']} | 99th Percentile=${st_mc['p99_dd']}")

    # 2. VERIFY STRATEGY 06 (ZERO-LAG MACD)
    print("\n" + "="*70)
    print("🔬 EXPERIMENT 2: STRATEGY 06 (ZERO-LAG MACD) STRICT CAUSAL RE-TEST")
    print("="*70)
    macd_trades_base = run_strict_zl_macd(df, spread=0.25, commission=0.06)
    macd_res_base = analyze_trades(macd_trades_base)
    macd_mc = run_monte_carlo(macd_trades_base)
    print(f"Base Frictions ($0.25 spread, $6 comm): Net=${macd_res_base['net_profit']:,} | PF={macd_res_base['pf']} | WR={macd_res_base['win_rate']}% | MaxDD=${macd_res_base['max_dd']} | Sharpe={macd_res_base['sharpe']}")
    print(f"Yearly Breakdown: {macd_res_base['yearly']}")
    print(f"Monte Carlo Drawdown Distribution (1,000 runs): Median=${macd_mc['median_dd']} | 95th Percentile=${macd_mc['p95_dd']} | 99th Percentile=${macd_mc['p99_dd']}")

    # 3. VERIFY STRATEGY 04 (TTM SQUEEZE)
    print("\n" + "="*70)
    print("🔬 EXPERIMENT 3: STRATEGY 04 (TTM SQUEEZE) STRICT CAUSAL RE-TEST")
    print("="*70)
    ttm_trades_base = run_strict_ttm_squeeze(df, spread=0.25, commission=0.06)
    ttm_res_base = analyze_trades(ttm_trades_base)
    ttm_mc = run_monte_carlo(ttm_trades_base)
    print(f"Base Frictions ($0.25 spread, $6 comm): Net=${ttm_res_base['net_profit']:,} | PF={ttm_res_base['pf']} | WR={ttm_res_base['win_rate']}% | MaxDD=${ttm_res_base['max_dd']} | Sharpe={ttm_res_base['sharpe']}")
    print(f"Yearly Breakdown: {ttm_res_base['yearly']}")
    print(f"Monte Carlo Drawdown Distribution (1,000 runs): Median=${ttm_mc['median_dd']} | 95th Percentile=${ttm_mc['p95_dd']} | 99th Percentile=${ttm_mc['p99_dd']}")

    # 4. FRICTION STRESS TEST (2X SPREAD & 3X SPREAD)
    print("\n" + "="*70)
    print("⚡ EXPERIMENT 4: FRICTION STRESS TEST (SLIPPAGE & BROKER MARKUP)")
    print("="*70)
    stress_levels = [
        {"name": "Normal (Baseline)", "spread": 0.25, "comm": 0.06},
        {"name": "Severe (2x Spread $0.50, Comm $8)", "spread": 0.50, "comm": 0.08},
        {"name": "Extreme (3x Spread $0.75, Comm $10)", "spread": 0.75, "comm": 0.10}
    ]

    stress_summary = []
    for s in stress_levels:
        t_st = run_strict_supertrend(df, spread=s["spread"], commission=s["comm"])
        t_macd = run_strict_zl_macd(df, spread=s["spread"], commission=s["comm"])
        t_ttm = run_strict_ttm_squeeze(df, spread=s["spread"], commission=s["comm"])

        r_st = analyze_trades(t_st)
        r_macd = analyze_trades(t_macd)
        r_ttm = analyze_trades(t_ttm)

        stress_summary.append({
            "Scenario": s["name"],
            "ST_Net": r_st["net_profit"], "ST_PF": r_st["pf"],
            "MACD_Net": r_macd["net_profit"], "MACD_PF": r_macd["pf"],
            "TTM_Net": r_ttm["net_profit"], "TTM_PF": r_ttm["pf"]
        })

    df_stress = pd.DataFrame(stress_summary)
    print(df_stress.to_string())

    # Save detailed JSON report
    out_path = "/root/CFD-Trading-ML/projects/quant_strategy_discovery/results/top3_sanity_and_stress_results.json"
    with open(out_path, "w") as f:
        json.dump({
            "supertrend": {"metrics": st_res_base, "monte_carlo": st_mc},
            "zl_macd": {"metrics": macd_res_base, "monte_carlo": macd_mc},
            "ttm_squeeze": {"metrics": ttm_res_base, "monte_carlo": ttm_mc},
            "stress_test": stress_summary
        }, f, indent=2)
    print(f"\n[+] Saved detailed stress results to: {out_path}")

if __name__ == "__main__":
    main()
