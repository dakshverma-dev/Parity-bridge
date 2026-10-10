import argparse

def main():
    p = argparse.ArgumentParser()
    sub = p.add_subparsers(dest="action")
    demo = sub.add_parser("demo")
    print("Demo command added")

if __name__ == "__main__":
    main()
