"""Run the fixture-backed deterministic router scenarios in corpus.json."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from tbaf.contract import ContractError, parse_input  # noqa: E402
from tbaf.router import build_artifact  # noqa: E402


def _read_json(path: Path) -> dict:
    if path.is_symlink() or not path.is_file():
        raise ValueError(f"expected a regular non-symlink file: {path}")
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"expected a JSON object: {path}")
    return value


def evaluate(corpus_path: Path, policy_path: Path) -> list[dict[str, str]]:
    corpus = _read_json(corpus_path)
    policy_data = policy_path.read_bytes()
    fixture_root = (corpus_path.parent / "fixtures").resolve()
    results = []

    for scenario in corpus.get("scenarios", []):
        fixture = scenario.get("fixture")
        if not fixture:
            results.append({"id": scenario["id"], "status": "NOT_EVALUABLE"})
            continue

        fixture_path = fixture_root / fixture
        if fixture_path.resolve().parent != fixture_root or fixture_path.is_symlink():
            raise ValueError(f"fixture path escapes its directory: {fixture}")

        raw = _read_json(fixture_path)
        oracle = scenario.get("oracle", {})
        try:
            parsed = parse_input(json.dumps(raw, ensure_ascii=False), policy_data)
        except ContractError as exc:
            expected = oracle.get("kind") == "input_rejected"
            matched = expected and oracle.get("error_contains", "") in str(exc)
            results.append({"id": scenario["id"], "status": "PASS" if matched else "FAIL"})
            continue

        if oracle.get("kind") == "input_rejected":
            results.append({"id": scenario["id"], "status": "FAIL"})
            continue

        artifact = build_artifact(parsed)
        claim_id = parsed["policy"]["claims"][0]["id"]
        claim = next(item for item in artifact["claims"] if item["claim_id"] == claim_id)
        checks = [
            artifact["attention"]["route"] == scenario["expected"],
            claim["evidence_state"] == oracle.get("claim_state", claim["evidence_state"]),
        ]
        if oracle.get("required_reason"):
            checks.append(oracle["required_reason"] in claim["reasons"])
        if oracle.get("candidate_status"):
            checks.append(all(item["epistemic_status"] == oracle["candidate_status"] for item in parsed["observations"]))
        results.append({"id": scenario["id"], "status": "PASS" if all(checks) else "FAIL"})

    return results


def main() -> int:
    parser = argparse.ArgumentParser(description="Evaluate fixture-backed deterministic router cases.")
    parser.add_argument("--corpus", type=Path, default=ROOT / "evaluation/corpus.json")
    parser.add_argument("--policy", type=Path, default=ROOT / "examples/policy.json")
    args = parser.parse_args()
    try:
        results = evaluate(args.corpus, args.policy)
    except (OSError, ValueError, ContractError, json.JSONDecodeError) as exc:
        print(f"evaluation error: {exc}", file=sys.stderr)
        return 2

    for result in results:
        print(f"{result['status']:13} {result['id']}")
    failures = sum(result["status"] == "FAIL" for result in results)
    print(f"\nCases: {len(results)}; failures: {failures}; not evaluable: {sum(r['status'] == 'NOT_EVALUABLE' for r in results)}")
    print("Case counts are contract checks, not detection-quality or productivity metrics.")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
