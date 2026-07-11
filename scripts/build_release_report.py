import argparse

def main():
    p = argparse.ArgumentParser()
    sub = p.add_subparsers(dest="action")
    sub.add_parser("create")
    print("Bundle CLI create command registered")

if __name__ == "__main__":
    main()
