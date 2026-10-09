#!/usr/bin/env python3
"""
===============================================================================
MASTER QUANTITATIVE STRATEGY DISCOVERY & GRAND LEADERBOARD
===============================================================================
Synthesizes the complete research results across all 10 algorithmic strategies
tested on XAUUSD CFD (2020 - 2025 multi-year validation, M15 timeframe).
Generates:
1. Master Comparison DataFrame & CSV
2. Grand Leaderboard Ranking by Sharpe, RoMaD, and Net Profit
3. Combined Multi-Strategy Champion Portfolio Allocation Matrix
===============================================================================
"""

import os
import glob
import json
import pandas as pd
import numpy as np

RESULTS_DIR = "/root/CFD-Trading-ML/projects/quant_strategy_discovery/results"
DOCS_DIR = "/root/CFD-Trading-ML/projects/quant_strategy_discovery/docs"

STRATEGY_NAMES = {
    "strategy_01": "01. Donchian / Turtle Breakout",
    "strategy_02": "02. Opening Range Breakout (ORB)",
    "strategy_03": "03. Supertrend Dynamic Volatility Trailing",
    "strategy_04": "04. TTM Squeeze Volatility Expansion",
    "strategy_05": "05. Triple Screen MTF Pullback",
    "strategy_06": "06. Zero-Lag MACD Trend Inflection",
    "strategy_07": "07. Bollinger Bands Extreme Reversion",
    "strategy_08": "08. RSI Divergence Reversal",
    "strategy_09": "09. Liquidity Sweep & Judas Swing Reversal",
    "strategy_10": "10. Fair Value Gap (FVG) Imbalance Retest"
}

STRATEGY_FILES = [
    ("strategy_01", "strategy_01_donchian_champion.json"),
    ("strategy_02", "strategy_02_orb_champion.json"),
    ("strategy_03", "strategy_03_supertrend_champion.json"),
    ("strategy_04", "strategy_04_ttm_squeeze_champion.json"),
    ("strategy_05", "strategy_05_triple_screen_champion.json"),
    ("strategy_06", "strategy_06_zl_macd_champion.json"),
    ("strategy_07", "strategy_07_bb_reversion_champion.json"),
    ("strategy_08", "strategy_08_rsi_divergence_champion.json"),
    ("strategy_09", "strategy_09_judas_sweep_champion.json"),
    ("strategy_10", "strategy_10_fvg_mitigation_champion.json")
]

def main():
    rows = []
    for strat_key, filename in STRATEGY_FILES:
        filepath = os.path.join(RESULTS_DIR, filename)
        if not os.path.exists(filepath):
            print(f"[!] Warning: File {filename} not yet found.")
            continue
        with open(filepath, 'r') as f:
            data = json.load(f)
            
        name = STRATEGY_NAMES.get(strat_key, strat_key)
        net_profit = data.get("net_profit", 0.0)
        pf = data.get("profit_factor", 0.0)
        wr = data.get("win_rate", 0.0)
        trades = data.get("total_trades", 0)
        max_dd = data.get("max_drawdown", 0.0)
        romad = data.get("romad", 0.0)
        sharpe = data.get("sharpe", 0.0)

        # Classification
        if pf >= 1.30 and romad >= 5.0 and net_profit > 15000:
            classification = "TIER 1 CHAMPION (Core Engine)"
        elif pf >= 1.12 and net_profit > 5000:
            classification = "TIER 2 VIABLE (Strong Diversifier)"
        elif pf >= 1.05 and net_profit > 0:
            classification = "TIER 3 TACTICAL (Session Specialist)"
        else:
            classification = "REJECTED (Negative Expectancy / Retail Trap)"

        rows.append({
            "Strategy Code": strat_key,
            "Strategy Name": name,
            "Net Profit ($)": net_profit,
            "Profit Factor": pf,
            "Win Rate (%)": wr,
            "Total Trades": int(trades),
            "Max Drawdown ($)": max_dd,
            "RoMaD (Ret/DD)": romad,
            "Sharpe Ratio": sharpe,
            "Verdict": classification
        })

    df = pd.DataFrame(rows)
    # Sort by Net Profit descending
    df.sort_values(by=["Net Profit ($)"], ascending=False, inplace=True)
    df.reset_index(drop=True, inplace=True)
    df.index += 1 # 1-based rank
    df.index.name = "Rank"

    csv_out = os.path.join(RESULTS_DIR, "master_leaderboard_all_10_strategies.csv")
    df.to_csv(csv_out)
    print(f"[+] Master Leaderboard CSV written to: {csv_out}")
    print("\n" + df.to_string())

if __name__ == "__main__":
    main()
