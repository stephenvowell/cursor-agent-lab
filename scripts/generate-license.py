#!/usr/bin/env python3
"""Generate retail license keys for Career Copilot customers.

Usage:
  python scripts/generate-license.py
  python scripts/generate-license.py --count 5
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "app"))

from license import generate_key, validate_key  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate Career Copilot license keys")
    parser.add_argument("--count", type=int, default=1, help="Number of keys to generate")
    args = parser.parse_args()
    print("Career Copilot license keys (one per customer):\n")
    for i in range(max(1, args.count)):
        key = generate_key()
        assert validate_key(key)
        print(f"  {i + 1}. {key}")
    print("\nTrial key (14 days, share freely for demos): CCOP-TRIAL")


if __name__ == "__main__":
    main()
