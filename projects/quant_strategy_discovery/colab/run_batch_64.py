import os
import subprocess

os.chdir("/content/CFD-Trading-ML")
print("[+] Pulling latest code from origin main...")
subprocess.run(["git", "pull", "origin", "main"], check=True)

print("[+] Executing Batch 64 simulation...")
subprocess.run(["python3", "projects/quant_strategy_discovery/colab/batch_64_liquidity_sweep_matrix.py"], check=True)

print("[+] Adding results to git...")
subprocess.run(["git", "add", "projects/quant_strategy_discovery/results/batch_64*"], check=True)
subprocess.run(["git", "commit", "-m", "feat(quant): add Batch 64 liquidity sweep results", "--author=BlamzKunG <blamzkung@users.noreply.github.com>"], check=True)

print("[+] Pushing results to GitHub...")
subprocess.run(["git", "push", "origin", "main"], check=True)
print("[+] Batch 64 execution and push completed successfully!")
