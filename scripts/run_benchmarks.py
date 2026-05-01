import argparse
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from qechybrid import bench

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--only", choices=["surface", "qldpc"], default=None)
    p.add_argument("--profile", default="quick")
    args = p.parse_args()
    print(f"Running profile={args.profile}, only={args.only}")

if __name__ == "__main__":
    main()
