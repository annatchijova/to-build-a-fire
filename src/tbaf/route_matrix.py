"""Generate the router decision table from a bounded, data-only spec.

The table runs the deterministic router over every combination the spec
selects. It documents routing behavior and is the repository's generated
artifact: `generated_artifacts` checks that a committed table is exactly what
this generator produces from the committed spec.
"""

from __future__ import annotations

import argparse
import hashlib
import itertools
import json
import sys
from pathlib import Path
from typing import Any

from .contract import ContractError, _decode_json, _keys, parse_input
from .router import build_artifact

SPEC_SCHEMA = "tbaf.route-matrix-spec/v1"
MATRIX_SCHEMA = "tbaf.route-matrix/v1"
GENERATOR = {"name": "tbaf-route-matrix", "version": "1"}
MAX_SPEC_BYTES = 16_384
MAX_CASES = 2_048

# Canonical dimension values, in output order. A spec selects a subset.
DIMENSIONS: dict[str, tuple[str, ...]] = {
    "consequences": ("low", "medium", "high", "critical"),
    "review_routes": ("targeted", "deep"),
    "check_states": ("PASS", "FAIL", "CONTRADICTED", "NOT_RUN", "UNAVAILABLE", "STALE", "MISSING"),
    "observations": ("none", "affected", "not_affected", "counterexample", "stale", "unscoped"),
    "paths": ("protected_only", "protected_and_unmapped", "unmapped_only"),
}

_BASE = "a" * 40
_HEAD = "b" * 40
_OTHER = "c" * 40
_PROTECTED = "src/protected.py"
_UNMAPPED = "docs/notes.md"


def parse_spec(data: bytes) -> dict[str, list[str]]:
    """Validate an untrusted spec; values must be known and are put in canonical order."""
    if len(data) > MAX_SPEC_BYTES:
        raise ContractError(f"route-matrix spec exceeds {MAX_SPEC_BYTES} bytes")
    raw = _keys(_decode_json(data, "route-matrix spec"), {"schema_version", *DIMENSIONS},
                {"schema_version", *DIMENSIONS}, "route-matrix spec")
    if raw["schema_version"] != SPEC_SCHEMA:
        raise ContractError(f"route-matrix spec schema_version must be {SPEC_SCHEMA}")
    spec: dict[str, list[str]] = {}
    for name, allowed in DIMENSIONS.items():
        values = raw[name]
        if (not isinstance(values, list) or not values
                or any(not isinstance(value, str) or value not in allowed for value in values)
                or len(set(values)) != len(values)):
            raise ContractError(f"route-matrix spec {name} must be a non-empty list of distinct known values")
        spec[name] = [value for value in allowed if value in values]
    count = 1
    for values in spec.values():
        count *= len(values)
    if count > MAX_CASES:
        raise ContractError(f"route-matrix spec selects {count} cases; the limit is {MAX_CASES}")
    return spec


def _case_input(consequence: str, review_route: str, check_state: str, observation: str, paths: str) -> tuple[str, str]:
    policy = {
        "schema_version": "tbaf.policy/v1",
        "id": "route-matrix",
        "version": "1",
        "capacity_minutes": 60,
        "claims": [{
            "id": "protected-claim",
            "statement": "Synthetic claim used to tabulate routing behavior.",
            "consequence": consequence,
            "path_globs": [_PROTECTED],
            "required_checks": ["invariant"],
            "review_route": review_route,
            "attention_minutes": 30,
            "estimate_source": "Route matrix fixture",
        }],
    }
    changed = {
        "protected_only": [_PROTECTED],
        "protected_and_unmapped": [_PROTECTED, _UNMAPPED],
        "unmapped_only": [_UNMAPPED],
    }[paths]
    checks = []
    if check_state != "MISSING":
        checks.append({
            "id": "invariant",
            "claim_id": "protected-claim",
            "status": "PASS" if check_state == "STALE" else check_state,
            "revision": _OTHER if check_state == "STALE" else _HEAD,
            "source": {"name": "route-matrix", "version": "1"},
            "scope": "synthetic check",
            "artifact_ref": None,
        })
    observations = []
    if observation != "none":
        observations.append({
            "id": "candidate",
            "kind": "counterexample_candidate" if observation == "counterexample" else "impact_candidate",
            "claim_id": None if observation == "unscoped" else "protected-claim",
            "impact": {"not_affected": "not_affected", "unscoped": "unknown"}.get(observation, "affected"),
            "source": {"agent": "route-matrix", "version": "1"},
            "revision": _OTHER if observation == "stale" else _HEAD,
            "scope": "synthetic observation",
            "text": "Synthetic candidate observation.",
            "locations": [],
        })
    review_input = {
        "schema_version": "tbaf.review-input/v1",
        "change": {"project": "example/route-matrix", "mr_iid": 1, "base_sha": _BASE, "head_sha": _HEAD, "paths": changed},
        "observations": observations,
        "checks": checks,
    }
    return json.dumps(review_input), json.dumps(policy)


def generate(spec_data: bytes) -> bytes:
    """Return the canonical table bytes for a spec, ending in a newline."""
    spec = parse_spec(spec_data)
    cases = []
    for combination in itertools.product(*spec.values()):
        inputs = dict(zip(("consequence", "review_route", "check_state", "observation", "paths"), combination))
        artifact = build_artifact(parse_input(*_case_input(*combination)))
        claim = artifact["claims"][0]
        attention = artifact["attention"]
        cases.append({
            "id": "|".join(f"{key}={value}" for key, value in inputs.items()),
            "inputs": inputs,
            "route": attention["route"],
            "claim_state": claim["evidence_state"],
            "attention_reasons": attention["reasons"],
            "known_demand_minutes": attention["known_demand_minutes"],
            "unknown_demand_tasks": attention["unknown_demand_tasks"],
            "schedule_state": attention["schedule_state"],
        })
    document: dict[str, Any] = {
        "schema_version": MATRIX_SCHEMA,
        "generator": GENERATOR,
        "spec_sha256": hashlib.sha256(spec_data).hexdigest(),
        "case_count": len(cases),
        "cases": cases,
    }
    return (json.dumps(document, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode("utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="tbaf-route-matrix", description="Generate the router decision table.")
    parser.add_argument("spec", type=Path, help="tbaf.route-matrix-spec/v1 JSON file")
    parser.add_argument("--check", type=Path, metavar="TABLE",
                        help="compare against an existing table instead of printing")
    args = parser.parse_args(argv)
    try:
        output = generate(args.spec.read_bytes())
    except (OSError, ContractError) as exc:
        print(f"tbaf-route-matrix: rejected: {exc}", file=sys.stderr)
        return 2
    if args.check is not None:
        if args.check.read_bytes() != output:
            print(f"tbaf-route-matrix: {args.check} does not match the generator output", file=sys.stderr)
            return 1
        return 0
    sys.stdout.buffer.write(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
