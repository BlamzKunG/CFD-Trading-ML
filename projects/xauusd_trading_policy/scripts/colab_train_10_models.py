"""
=============================================================================
Colab Runner: End-to-End Execution for 10 Quant ML Models
=============================================================================
Executed directly within the Google Colab VM:
1. Verifies GPU & CUDA environment
2. Clones / syncs latest CFD-Trading-ML repo
3. Installs missing packages (lightgbm, catboost, xgboost, onnx, onnxscript)
4. Executes train_and_benchmark_10_models.py
5. Syncs trained models & benchmark reports back to GitHub
=============================================================================
"""

import os
import sys
import subprocess

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
    print("=" * 80)
    print("🚀 COLAB GPU WORKER: 10 QUANT ML TRADING MODELS TRAINING & BENCHMARK")
    print("=" * 80)

    # 1. Environment & GPU Check
    try:
        import torch
        print(f"[Hardware] PyTorch Version: {torch.__version__}")
        print(f"[Hardware] CUDA Available:  {torch.cuda.is_available()}")
        if torch.cuda.is_available():
            print(f"[Hardware] GPU Model:       {torch.cuda.get_device_name(0)}")
            print(f"[Hardware] Device Count:    {torch.cuda.device_count()}")
    except Exception as e:
        print(f"[Hardware] Error checking PyTorch: {e}")

    # 2. Sync Repository
    repo_dir = "/content/CFD-Trading-ML"
    if not os.path.exists(repo_dir):
        print("\n[Step 1/5] Cloning repository...")
        run_cmd(["git", "clone", "https://github.com/BlamzKunG/CFD-Trading-ML.git", repo_dir])
    else:
        print("\n[Step 1/5] Pulling latest repository updates...")
        run_cmd(f"cd {repo_dir} && git pull origin main", check=False)

    # 3. Install Required Dependencies
    print("\n[Step 2/5] Ensuring required Quant ML packages are installed...")
    run_cmd(["pip", "install", "-q", "lightgbm", "catboost", "xgboost", "onnx", "onnxscript", "matplotlib", "scikit-learn"])

    # 4. Check Dataset
    data_path = "/content/XAUUSD_M1.csv.gz"
    if not os.path.exists(data_path):
        # Fallback to uncompressed
        if os.path.exists("/content/xauusd_m1.csv"):
            data_path = "/content/xauusd_m1.csv"
        else:
            raise FileNotFoundError(f"Dataset not found at {data_path}")
    print(f"\n[Step 3/5] Verified dataset at: {data_path} ({os.path.getsize(data_path):,} bytes)")

    # 5. Run 10 Models Training & Benchmark Suite
    print("\n[Step 4/5] Launching train_and_benchmark_10_models.py on Colab GPU...")
    bench_script = os.path.join(repo_dir, "projects", "xauusd_trading_policy", "scripts", "train_and_benchmark_10_models.py")
    train_cmd = [
        sys.executable,
        "-u",
        bench_script,
        "--data-path", data_path,
        "--models", "all",
        "--subsample-step", "6",
        "--horizon", "60"
    ]
    run_cmd(train_cmd)

    # 6. Commit and Push Results to GitHub
    print("\n[Step 5/5] Committing and pushing results back to GitHub...")
    gh_token = os.environ.get("GITHUB_TOKEN", "")
    run_cmd(f"cd {repo_dir} && git config user.name 'BlamzKunG'")
    run_cmd(f"cd {repo_dir} && git config user.email 'blamzkung@users.noreply.github.com'")
    if gh_token:
        run_cmd(f"cd {repo_dir} && git remote set-url origin https://BlamzKunG:{gh_token}@github.com/BlamzKunG/CFD-Trading-ML.git")

    run_cmd(f"cd {repo_dir} && git add projects/xauusd_trading_policy/models/ projects/xauusd_trading_policy/docs/")
    run_cmd(f"cd {repo_dir} && git commit -m 'feat(benchmark): trained 10 Quant ML models and 2025 out-of-sample benchmark [skip ci]'", check=False)
    run_cmd(f"cd {repo_dir} && git pull --rebase origin main", check=False)
    run_cmd(f"cd {repo_dir} && git push origin main", check=False)

    print("\n" + "=" * 80)
    print("🎉 ALL 10 QUANT ML MODELS TRAINED, BENCHMARKED & SYNCED TO GITHUB!")
    print("=" * 80)

if __name__ == "__main__":
    main()
