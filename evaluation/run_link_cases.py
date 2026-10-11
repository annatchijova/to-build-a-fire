"""Check the Duo assessment linker contract against bounded JSON fixtures."""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from tbaf.contract import ContractError, parse_input  # noqa: E402
from tbaf.link_assessment import link_assessment  # noqa: E402
from tbaf.router import _canonical_bytes, build_artifact  # noqa: E402


def _read_json(path: Path) -> dict:
    if path.is_symlink() or not path.is_file():
        raise ValueError(f"expected a regular non-symlink file: {path}")
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"expected a JSON object: {path}")
    return value


def _baseline_package() -> dict:
    review_input = (ROOT / "examples/review-input.json").read_text(encoding="utf-8")
    policy = (ROOT / "examples/policy.json").read_text(encoding="utf-8")
    return build_artifact(parse_input(review_input, policy))


def evaluate() -> list[dict[str, str]]:
    corpus_path = ROOT / "evaluation/linker-cases.json"
    corpus = _read_json(corpus_path)
    if corpus.get("schema_version") != "tbaf.linker-cases/v1":
        raise ValueError("unsupported linker case corpus schema")
    fixtures = ROOT / "evaluation/fixtures"
    baseline = _baseline_package()
    package_data = json.dumps(baseline, ensure_ascii=False, sort_keys=True).encode("utf-8")
    outcomes: list[dict[str, str]] = []

    for case in corpus.get("cases", []):
        fixture_name = case.get("fixture")
        if not isinstance(fixture_name, str) or Path(fixture_name).name != fixture_name:
            raise ValueError(f"invalid fixture path for {case.get('id', 'unknown case')}")
        fixture = _read_json(fixtures / fixture_name)
        expected = case.get("expected", {})
        assessment_data = json.dumps(fixture, ensure_ascii=False).encode("utf-8")
        try:
            linked = link_assessment(package_data, assessment_data)
        except ContractError as exc:
            matched = (
                expected.get("kind") == "rejected"
                and expected.get("error_contains", "") in str(exc)
            )
            outcomes.append({
                "id": case["id"],
                "status": "EXPECTED_REJECTION" if matched else "DISCREPANCY",
            })
            continue

        if expected.get("kind") == "rejected":
            outcomes.append({"id": case["id"], "status": "DISCREPANCY"})
            continue

        unsigned = dict(linked)
        supplied_digest = unsigned.pop("sha256", None)
        valid_digest = (
            isinstance(supplied_digest, str)
            and hashlib.sha256(_canonical_bytes(unsigned)).hexdigest() == supplied_digest
        )
        coverage = linked.get("change_mapper", {}).get("diff_coverage", {})
        unchanged_route = linked.get("review_package", {}).get("attention", {}).get("route") == baseline["attention"]["route"]
        unchanged_package = linked.get("review_package") == baseline
        status_matches = (
            expected.get("kind") == "linked"
            and coverage.get("status") == expected.get("coverage")
            and valid_digest
            and unchanged_route
            and unchanged_package
        )
        outcomes.append({
            "id": case["id"],
            "status": "LINKED_CONTRACT_MATCHED" if status_matches else "DISCREPANCY",
        })
    return outcomes


def main() -> int:
    try:
        outcomes = evaluate()
    except (OSError, ValueError, ContractError, json.JSONDecodeError) as exc:
        print(f"linker evaluation error: {exc}", file=sys.stderr)
        return 2

    for outcome in outcomes:
        print(f"{outcome['status']:24} {outcome['id']}")
    counts = {status: sum(item["status"] == status for item in outcomes) for status in (
        "LINKED_CONTRACT_MATCHED", "EXPECTED_REJECTION", "DISCREPANCY"
    )}
    print(
        "\nLinker contract outcomes: "
        f"linked matches {counts['LINKED_CONTRACT_MATCHED']}; "
        f"expected rejections {counts['EXPECTED_REJECTION']}; "
        f"discrepancies {counts['DISCREPANCY']}"
    )
    print("These fixtures check linker invariants, not agent accuracy or diff completeness truth.")
    return 1 if counts["DISCREPANCY"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
