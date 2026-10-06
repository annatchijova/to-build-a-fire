"""Command-line interface for producing an Attention Router receipt."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .contract import ContractError, parse_input
from .router import build_artifact


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="tbaf-route", description="Route one MR's human attention using scoped evidence.")
    parser.add_argument("input", help="path to a UTF-8 tbaf.review-input/v1 JSON file, or - for stdin")
    parser.add_argument("--policy", required=True, help="trusted tbaf.policy/v1 file maintained outside MR-controlled input")
    parser.add_argument("--compact", action="store_true", help="write compact JSON")
    args = parser.parse_args(argv)

    try:
        if args.input == "-":
            data = sys.stdin.buffer.read(2_000_001)
        else:
            path = Path(args.input)
            if path.is_symlink() or not path.is_file():
                raise ContractError("input path must be a regular non-symlink file")
            with path.open("rb") as stream:
                data = stream.read(2_000_001)
        policy_path = Path(args.policy)
        if policy_path.is_symlink() or not policy_path.is_file():
            raise ContractError("policy path must be a regular non-symlink file")
        with policy_path.open("rb") as stream:
            policy_data = stream.read(2_000_001)
        parsed = parse_input(data, policy_data)
        artifact = build_artifact(parsed)
    except (OSError, ContractError, ValueError) as exc:
        print(f"tbaf-route: input rejected: {exc}", file=sys.stderr)
        return 2

    indent = None if args.compact else 2
    print(json.dumps(artifact, ensure_ascii=False, sort_keys=True, indent=indent))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
