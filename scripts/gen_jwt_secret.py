#!/usr/bin/env python3
"""Generate a strong JWT_SECRET for Nexora.

HS256 (RFC 7518, Section 3.2) needs a key of at least 32 random bytes; short
values fail fast at startup instead of serving forgeable tokens.

Usage (Windows PowerShell / Linux / macOS):
    python scripts/gen_jwt_secret.py
    # copy the printed value into your .env as:
    # JWT_SECRET=<printed-value>

The secret is printed to stdout only, so it can be captured safely:
    python scripts/gen_jwt_secret.py > jwt_secret.txt
"""

from __future__ import annotations

import argparse
import secrets
import sys


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate a strong JWT_SECRET for Nexora (HS256).")
    parser.add_argument(
        "--bytes",
        type=int,
        default=48,
        help="Random bytes to encode (default: 48, minimum: 32).",
    )
    args = parser.parse_args()
    if args.bytes < 32:
        print("Refusing to generate a JWT secret shorter than 32 bytes.", file=sys.stderr)
        return 2
    print(secrets.token_urlsafe(args.bytes))
    print(
        "Paste the value above into your .env as JWT_SECRET=<value> (keep stdout clean for capture).",
        file=sys.stderr,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
