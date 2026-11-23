#!/usr/bin/env python3
"""Create a .env file with freshly generated random secrets.

    python scripts/generate_env.py            # writes ./.env (refuses to overwrite)
    python scripts/generate_env.py --force    # overwrite an existing .env

It copies .env.example and replaces every placeholder secret with a random
value.  Nothing is printed except the path: open the file to read the generated
bootstrap account passwords.  Uses only the Python standard library.
"""
from __future__ import annotations

import argparse
import secrets
import string
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _token(length: int = 48) -> str:
    return secrets.token_hex(length // 2)


def _password() -> str:
    """Readable password that satisfies the platform policy."""
    alphabet = string.ascii_letters + string.digits
    while True:
        value = "".join(secrets.choice(alphabet) for _ in range(18))
        if any(c.islower() for c in value) and any(c.isupper() for c in value) and any(c.isdigit() for c in value):
            return value


GENERATORS = {
    "POSTGRES_PASSWORD": lambda: _token(32),
    "SECRET_KEY": lambda: _token(64),
    "ALERT_WEBHOOK_TOKEN": lambda: _token(40),
    "DEMO_APP_CONTROL_TOKEN": lambda: _token(40),
    "DEMO_APP_RECOVERY_TOKEN": lambda: _token(40),
    "BOOTSTRAP_ADMIN_PASSWORD": _password,
    "BOOTSTRAP_OPERATOR_PASSWORD": _password,
}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--force", action="store_true", help="overwrite an existing .env")
    parser.add_argument("--output", default=str(ROOT / ".env"), help="file to write (default: ./.env)")
    args = parser.parse_args()

    template = ROOT / ".env.example"
    output = Path(args.output)
    if output.exists() and not args.force:
        print(f"{output} already exists; use --force to overwrite it.", file=sys.stderr)
        return 1

    lines = []
    for line in template.read_text(encoding="utf-8").splitlines():
        key, separator, _value = line.partition("=")
        if separator and key in GENERATORS:
            line = f"{key}={GENERATORS[key]()}"
        lines.append(line)
    output.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Wrote {output} with generated secrets. Bootstrap account passwords are inside that file.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
