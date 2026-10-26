"""Falsifiable tests for the route matrix generator and its reproducibility check."""

from __future__ import annotations

import json
import unittest
from pathlib import Path

from tbaf.contract import ContractError, parse_input
from tbaf.generated_artifacts import OUTPUT_PATH, SPEC_PATH, build_generated_artifacts_check
from tbaf.route_matrix import DIMENSIONS, MAX_CASES, generate, parse_spec
from tbaf.router import build_artifact


ROOT = Path(__file__).resolve().parents[1]
BASE = "a" * 40
HEAD = "b" * 40
SPEC = (ROOT / SPEC_PATH).read_bytes()
TABLE = (ROOT / OUTPUT_PATH).read_bytes()
POLICY = (ROOT / "examples" / "policy.json").read_bytes()


def _reader(files: dict[str, bytes]):
    def read(path: str, maximum: int) -> bytes | None:
        data = files.get(path)
        return None if data is None or len(data) > maximum else data
    return read


class RouteMatrixTests(unittest.TestCase):
    def test_committed_table_matches_generator(self):
        self.assertEqual(generate(SPEC), TABLE, "regenerate with: python -m tbaf.route_matrix " + SPEC_PATH)

    def test_generation_is_independent_of_spec_value_order(self):
        spec = json.loads(SPEC)
        spec["paths"].reverse()
        reordered = json.dumps(spec).encode()
        self.assertEqual(json.loads(generate(reordered))["cases"], json.loads(TABLE)["cases"])

    def test_unknown_duplicate_and_oversized_specs_are_rejected(self):
        spec = json.loads(SPEC)
        for name, value in (("check_states", ["PASS", "MAYBE"]), ("paths", ["unmapped_only", "unmapped_only"]),
                            ("observations", [])):
            mutated = dict(spec, **{name: value})
            with self.subTest(name=name), self.assertRaises(ContractError):
                parse_spec(json.dumps(mutated).encode())
        with self.assertRaises(ContractError):
            parse_spec(json.dumps(dict(spec, extra=True)).encode())

    def test_every_known_value_fits_within_case_limit(self):
        spec = {"schema_version": "tbaf.route-matrix-spec/v1", **{name: list(values) for name, values in DIMENSIONS.items()}}
        parsed = parse_spec(json.dumps(spec).encode())
        count = 1
        for values in parsed.values():
            count *= len(values)
        self.assertLessEqual(count, MAX_CASES)

    def test_table_records_unmapped_paths_as_deep_review(self):
        cases = json.loads(TABLE)["cases"]
        unmapped = [case for case in cases if case["inputs"]["paths"] != "protected_only"]
        self.assertTrue(unmapped)
        self.assertTrue(all(case["route"] == "DEEP_REVIEW" for case in unmapped))


class GeneratedArtifactsCheckTests(unittest.TestCase):
    def test_reproduced_table_passes(self):
        check = build_generated_artifacts_check(_reader({SPEC_PATH: SPEC, OUTPUT_PATH: TABLE}), HEAD)
        self.assertEqual(check["status"], "PASS")
        self.assertEqual(check["revision"], HEAD)

    def test_hand_edited_table_fails_with_location(self):
        tampered = TABLE.replace(b'"route": "DEEP_REVIEW"', b'"route": "COVERED_BY_EVIDENCE"', 1)
        self.assertNotEqual(tampered, TABLE)
        check = build_generated_artifacts_check(_reader({SPEC_PATH: SPEC, OUTPUT_PATH: tampered}), HEAD)
        self.assertEqual(check["status"], "FAIL")
        self.assertIn("starting at line", check["details"])

    def test_spec_changed_without_regenerating_fails(self):
        spec = json.loads(SPEC)
        spec["consequences"] = ["low", "high", "critical"]
        check = build_generated_artifacts_check(
            _reader({SPEC_PATH: json.dumps(spec).encode(), OUTPUT_PATH: TABLE}), HEAD)
        self.assertEqual(check["status"], "FAIL")

    def test_missing_invalid_or_oversized_inputs_are_not_run(self):
        for files in ({SPEC_PATH: SPEC}, {OUTPUT_PATH: TABLE}, {SPEC_PATH: b"{}", OUTPUT_PATH: TABLE},
                      {SPEC_PATH: SPEC + b" " * 20_000, OUTPUT_PATH: TABLE}):
            with self.subTest(files=sorted(files)):
                check = build_generated_artifacts_check(_reader(files), HEAD)
                self.assertEqual(check["status"], "NOT_RUN")

    def _route(self, check: dict) -> dict:
        review_input = {
            "schema_version": "tbaf.review-input/v1",
            "change": {"project": "example/service", "mr_iid": 3, "base_sha": BASE, "head_sha": HEAD,
                       "paths": [OUTPUT_PATH, SPEC_PATH]},
            "observations": [],
            "checks": [check],
        }
        return build_artifact(parse_input(json.dumps(review_input), POLICY))

    def test_large_reproduced_diff_is_covered_by_evidence(self):
        artifact = self._route(build_generated_artifacts_check(_reader({SPEC_PATH: SPEC, OUTPUT_PATH: TABLE}), HEAD))
        self.assertEqual(artifact["attention"]["route"], "COVERED_BY_EVIDENCE")
        self.assertEqual(artifact["attention"]["known_demand_minutes"], 0)

    def test_tampered_table_routes_to_targeted_review(self):
        tampered = TABLE.replace(b'"route": "DEEP_REVIEW"', b'"route": "COVERED_BY_EVIDENCE"', 1)
        artifact = self._route(build_generated_artifacts_check(_reader({SPEC_PATH: SPEC, OUTPUT_PATH: tampered}), HEAD))
        self.assertEqual(artifact["attention"]["route"], "TARGETED_REVIEW")
        self.assertIn("required_check_fail:generated-artifacts-reproducible", artifact["attention"]["reasons"])


if __name__ == "__main__":
    unittest.main()
