import os
import sys
import glob
import shutil

def backup():
    src_dir = os.path.abspath("projects/xauusd_trading_policy/docs/experiments")
    dst_dir = "/storage/emulated/0/Download/EA/CFD-Trading-ML/experiments"
    os.makedirs(dst_dir, exist_ok=True)

    print(f"[Backup] Syncing from {src_dir} to {dst_dir}...")
    count = 0
    for f in glob.glob(os.path.join(src_dir, "*")):
        fname = os.path.basename(f)
        dst_path = os.path.join(dst_dir, fname)
        shutil.copyfile(f, dst_path)
        count += 1

    registry_src = os.path.abspath("projects/xauusd_trading_policy/docs/EXPERIMENT_REGISTRY.md")
    registry_dst = "/storage/emulated/0/Download/EA/CFD-Trading-ML/EXPERIMENT_REGISTRY.md"
    if os.path.exists(registry_src):
        shutil.copyfile(registry_src, registry_dst)
        print(f"[Backup] Synced EXPERIMENT_REGISTRY.md")

    models_src = os.path.abspath("projects/xauusd_trading_policy/models")
    models_dst = "/storage/emulated/0/Download/EA/CFD-Trading-ML/production"
    os.makedirs(models_dst, exist_ok=True)
    for f in glob.glob(os.path.join(models_src, "*")):
        if os.path.isfile(f):
            shutil.copyfile(f, os.path.join(models_dst, os.path.basename(f)))

    print(f"[Backup] Successfully copied {count} experiment files and models.")

if __name__ == "__main__":
    backup()
