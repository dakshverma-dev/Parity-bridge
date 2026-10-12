import argparse

def run_demo():
    for f in ("surface", "qldpc"):
        for side in ("a", "b"):
            print(f"Generate run {f}-{side}")
