import os
import subprocess

os.chdir("/content/CFD-Trading-ML")
print("[+] Pulling latest code from origin main...")
subprocess.run(["git", "pull", "origin", "main"], check=True)

print("[+] Executing Batch 65 Linear Equity & Monthly Consistency simulation...")
subprocess.run(["python3", "projects/quant_strategy_discovery/colab/batch_65_linear_monthly_consistency.py"], check=True)

print("[+] Adding results to git...")
subprocess.run(["git", "add", "projects/quant_strategy_discovery/results/batch_65*"], check=True)
subprocess.run(["git", "commit", "-m", "feat(quant): add Batch 65 linear equity & monthly consistency results", "--author=BlamzKunG <blamzkung@users.noreply.github.com>"], check=True)

print("[+] Pushing results to GitHub...")
subprocess.run(["git", "push", "origin", "main"], check=True)
print("[+] Batch 65 execution and push completed successfully!")
