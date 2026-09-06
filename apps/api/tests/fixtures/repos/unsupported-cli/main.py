#!/usr/bin/env python3
"""CLI-only Python application for testing."""
import argparse
import sys


def main():
    parser = argparse.ArgumentParser(description="Process some integers.")
    parser.add_argument("integers", metavar="N", type=int, nargs="+",
                        help="an integer for the accumulator")
    parser.add_argument("--sum", dest="accumulate", action="store_const",
                        const=sum, default=max,
                        help="sum the integers (default: find the max)")

    args = parser.parse_args()
    result = args.accumulate(args.integers)
    print(result)


if __name__ == "__main__":
    main()
