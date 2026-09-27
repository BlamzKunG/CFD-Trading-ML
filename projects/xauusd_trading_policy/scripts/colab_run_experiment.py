"""
=============================================================================
Colab Experiment Runner: Autonomous Quant ML Research
=============================================================================
Executes a targeted research experiment on Colab VM and syncs results to GitHub.
=============================================================================
"""

import os
import sys
import subprocess
import argparse

def run_cmd(cmd, check=True):
    print(f"\n[Colab VM] Executing: {' '.join(cmd) if isinstance(cmd, list) else cmd}", flush=True)
    if isinstance(cmd, list):
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1)
        for line in proc.stdout:
            print(line, end="", flush=True)
        ret = proc.wait()
        if check and ret != 0:
            raise subprocess.CalledProcessError(ret, cmd)
        return ret
    else:
        return subprocess.run(cmd, check=check, shell=True)

def main():
    parser = argparse.ArgumentParser(description="Colab Autonomous Quant ML Experiment Runner")
    parser.add_argument("--exp-id", type=str, default="EXP_05_DYNAMIC_BARRIERS", help="Experiment ID to execute")
    args, _ = parser.parse_known_args()

    print("=" * 80)
    print(f"🔬 COLAB WORKER: AUTONOMOUS QUANT ML RESEARCH EXPERIMENT ({args.exp_id})")
    print("=" * 80)

    repo_dir = "/content/CFD-Trading-ML"
    if not os.path.exists(repo_dir):
        print("\n[Step 1/4] Cloning repository...")
        run_cmd(["git", "clone", "https://github.com/BlamzKunG/CFD-Trading-ML.git", repo_dir])
    else:
        print("\n[Step 1/4] Pulling latest repository updates...")
        run_cmd(f"cd {repo_dir} && git pull origin main", check=False)

    print("\n[Step 2/4] Ensuring dependencies are ready...")
    run_cmd(["pip", "install", "-q", "lightgbm", "catboost", "xgboost", "onnx", "onnxscript", "matplotlib", "scikit-learn"])

    data_path = "/content/XAUUSD_M1.csv.gz"
    if not os.path.exists(data_path):
        raise FileNotFoundError(f"Dataset not found at {data_path}")

    print(f"\n[Step 3/4] Launching run_research_experiment.py for {args.exp_id}...")
    exp_script = os.path.join(repo_dir, "projects", "xauusd_trading_policy", "scripts", "run_research_experiment.py")
    exp_cmd = [
        sys.executable,
        "-u",
        exp_script,
        "--exp-id", args.exp_id,
        "--data-path", data_path
    ]
    run_cmd(exp_cmd)

    print(f"\n[Step 4/4] Syncing experiment findings & registry back to GitHub...")
    gh_token = os.environ.get("GITHUB_TOKEN", "")
    run_cmd(f"cd {repo_dir} && git config user.name 'BlamzKunG'")
    run_cmd(f"cd {repo_dir} && git config user.email 'blamzkung@users.noreply.github.com'")
    if gh_token:
        run_cmd(f"cd {repo_dir} && git remote set-url origin https://BlamzKunG:{gh_token}@github.com/BlamzKunG/CFD-Trading-ML.git")

    run_cmd(f"cd {repo_dir} && git add projects/xauusd_trading_policy/docs/ projects/xauusd_trading_policy/models/")
    run_cmd(f"cd {repo_dir} && git commit -m 'docs(experiment): record {args.exp_id} findings [skip ci]'", check=False)
    run_cmd(f"cd {repo_dir} && git pull --rebase origin main", check=False)
    run_cmd(f"cd {repo_dir} && git push origin main", check=False)

    print("\n" + "=" * 80)
    print(f"🎉 EXPERIMENT {args.exp_id} COMPLETED, DOCUMENTED, AND SYNCED TO GITHUB!")
    print("=" * 80)

if __name__ == "__main__":
    main()
