import os
import sys
import glob
import shutil

def backup():
    base_src = os.path.abspath("projects/xauusd_trading_policy")
    base_dst = "/storage/emulated/0/Download/EA/CFD-Trading-ML"
    os.makedirs(base_dst, exist_ok=True)

    print(f"[Backup] Starting comprehensive backup from {base_src} to {base_dst}...")

    # 1. Models & Registries
    models_src = os.path.join(base_src, "models")
    models_dst = os.path.join(base_dst, "models")
    prod_dst = os.path.join(base_dst, "production")
    os.makedirs(models_dst, exist_ok=True)
    os.makedirs(prod_dst, exist_ok=True)
    m_count = 0
    for f in glob.glob(os.path.join(models_src, "*")):
        if os.path.isfile(f):
            fname = os.path.basename(f)
            shutil.copyfile(f, os.path.join(models_dst, fname))
            shutil.copyfile(f, os.path.join(prod_dst, fname))
            m_count += 1
    print(f"[Backup] Synced {m_count} model binaries & registries.")

    # 2. Expert Advisors (MQL5)
    ea_src = os.path.join(base_src, "ea")
    ea_dst = os.path.join(base_dst, "ea")
    os.makedirs(ea_dst, exist_ok=True)
    ea_count = 0
    for f in glob.glob(os.path.join(ea_src, "*.mq5")):
        if os.path.isfile(f):
            fname = os.path.basename(f)
            shutil.copyfile(f, os.path.join(ea_dst, fname))
            ea_count += 1
    print(f"[Backup] Synced {ea_count} MQL5 Expert Advisors.")

    # 3. Experiment Docs & Charts
    docs_src = os.path.join(base_src, "docs", "experiments")
    docs_dst = os.path.join(base_dst, "docs", "experiments")
    exp_dst = os.path.join(base_dst, "experiments")
    os.makedirs(docs_dst, exist_ok=True)
    os.makedirs(exp_dst, exist_ok=True)
    d_count = 0
    for f in glob.glob(os.path.join(docs_src, "*")):
        if os.path.isfile(f):
            fname = os.path.basename(f)
            shutil.copyfile(f, os.path.join(docs_dst, fname))
            shutil.copyfile(f, os.path.join(exp_dst, fname))
            d_count += 1
    print(f"[Backup] Synced {d_count} experiment documentation reports and charts.")

    # 4. Scripts
    scripts_src = os.path.join(base_src, "scripts")
    scripts_dst = os.path.join(base_dst, "scripts")
    os.makedirs(scripts_dst, exist_ok=True)
    s_count = 0
    for f in glob.glob(os.path.join(scripts_src, "*.py")):
        if os.path.isfile(f):
            fname = os.path.basename(f)
            shutil.copyfile(f, os.path.join(scripts_dst, fname))
            s_count += 1
    print(f"[Backup] Synced {s_count} quantitative research scripts.")

    # 5. Registries
    reg_src = os.path.join(base_src, "docs", "EXPERIMENT_REGISTRY.md")
    if os.path.exists(reg_src):
        shutil.copyfile(reg_src, os.path.join(base_dst, "docs", "EXPERIMENT_REGISTRY.md"))
        shutil.copyfile(reg_src, os.path.join(base_dst, "EXPERIMENT_REGISTRY.md"))
        print("[Backup] Synced EXPERIMENT_REGISTRY.md")

    print("\n" + "=" * 60)
    print("✅ COMPREHENSIVE BACKUP TO PHONE STORAGE COMPLETED!")
    print(f"Target: {base_dst}")
    print("=" * 60)

if __name__ == "__main__":
    backup()
