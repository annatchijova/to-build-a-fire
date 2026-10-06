"""Mutation-oriented checks for the v1 attention-routing contract."""

from __future__ import annotations

import copy
import json
import unittest

from tbaf.contract import ContractError, parse_input
from tbaf.router import build_artifact


BASE = "a" * 40
HEAD = "b" * 40


def make_input(*, path="src/auth.py", capacity=180, status="NOT_RUN", observation=None):
    value = {
        "schema_version": "tbaf.review-input/v1",
        "change": {"project": "example/service", "mr_iid": 82, "base_sha": BASE,
                   "head_sha": HEAD, "paths": [path]},
        "policy": {"id": "default", "version": "1", "capacity_minutes": capacity,
                   "claims": [{"id": "authorization", "statement": "Authorization boundaries remain enforced.",
                               "consequence": "critical", "path_globs": ["src/auth.py"],
                               "required_checks": ["auth-invariants"], "review_route": "targeted",
                               "attention_minutes": 35, "estimate_source": "team estimate v1"}]},
        "observations": [],
        "checks": [{"id": "auth-invariants", "claim_id": "authorization", "status": status,
                    "revision": HEAD, "source": {"name": "pytest", "version": "8"},
                    "scope": "authorization invariants", "artifact_ref": "ci://run/1"}],
    }
    if observation is not None:
        value["observations"].append(observation)
    return value


def route(value):
    return build_artifact(parse_input(json.dumps(value)))


class AttentionRouterTests(unittest.TestCase):
    def test_required_check_on_exact_revision_can_cover_declared_scope(self):
        result = route(make_input(status="PASS"))
        self.assertEqual(result["attention"]["route"], "COVERED_BY_EVIDENCE")
        self.assertEqual(result["claims"][0]["evidence_state"], "SUPPORTED")

    def test_missing_or_failed_evidence_routes_to_a_person(self):
        for status in ("NOT_RUN", "UNAVAILABLE", "FAIL"):
            with self.subTest(status=status):
                result = route(make_input(status=status))
                self.assertEqual(result["attention"]["route"], "TARGETED_REVIEW")

    def test_critical_mutations_never_become_covered_without_required_evidence(self):
        mutations = [
            ("missing-test", "src/auth.py", "NOT_RUN"),
            ("auth-widening", "src/auth.py", "FAIL"),
            ("removed-scanner", ".github/workflows/security.yml", "PASS"),
            ("weakened-assertion", "src/auth.py", "CONTRADICTED"),
            ("reduced-coverage-threshold", ".coveragerc", "PASS"),
            ("ci-or-true", ".github/workflows/ci.yml", "PASS"),
        ]
        for case_id, path, status in mutations:
            with self.subTest(case_id=case_id):
                result = route(make_input(path=path, status=status))
                self.assertNotEqual(result["attention"]["route"], "COVERED_BY_EVIDENCE")

    def test_unmapped_changed_path_routes_deep_with_unknown_effort(self):
        result = route(make_input(path=".github/workflows/ci.yml", status="PASS"))
        attention = result["attention"]
        self.assertEqual(attention["route"], "DEEP_REVIEW")
        self.assertEqual(attention["unknown_demand_tasks"], 1)
        self.assertIn("changed_path_outside_declared_claim_scope", attention["reasons"])

    def test_agent_candidate_cannot_downgrade_policy_mapped_change(self):
        obs = {"id": "mapper-1", "kind": "impact_candidate", "claim_id": "authorization",
               "impact": "not_affected", "source": {"agent": "mapper", "version": "1"},
               "revision": HEAD, "scope": "changed file", "text": "Candidate: no impact.",
               "locations": []}
        result = route(make_input(status="NOT_RUN", observation=obs))
        self.assertEqual(result["attention"]["route"], "TARGETED_REVIEW")

    def test_counterexample_candidate_cannot_be_dismissed_by_its_impact_label(self):
        obs = {"id": "falsifier-1", "kind": "counterexample_candidate", "claim_id": "authorization",
               "impact": "not_affected", "source": {"agent": "falsifier", "version": "1"},
               "revision": HEAD, "scope": "policy boundary", "text": "Candidate counterexample.",
               "locations": []}
        result = route(make_input(status="PASS", observation=obs))
        self.assertEqual(result["attention"]["route"], "TARGETED_REVIEW")
        self.assertIn("candidate_counterexample_requires_adjudication", result["attention"]["reasons"])

    def test_stale_observation_forces_deep_review(self):
        obs = {"id": "old-map", "kind": "impact_candidate", "claim_id": "authorization",
               "impact": "affected", "source": {"agent": "mapper", "version": "1"},
               "revision": "c" * 40, "scope": "old revision", "text": "Old candidate.", "locations": []}
        result = route(make_input(status="PASS", observation=obs))
        self.assertEqual(result["attention"]["route"], "DEEP_REVIEW")

    def test_capacity_keeps_uncovered_work_visible(self):
        value = make_input(capacity=20, status="NOT_RUN")
        result = route(value)
        attention = result["attention"]
        self.assertEqual(attention["known_demand_minutes"], 35)
        self.assertEqual(attention["scheduled_known_minutes"], 0)
        self.assertEqual(attention["uncovered_known_minutes"], 35)
        self.assertEqual(attention["schedule_state"], "OVER_CAPACITY")

    def test_receipt_is_reproducible_and_hashes_same_decision(self):
        value = make_input(status="NOT_RUN")
        first = route(value)
        second = route(copy.deepcopy(value))
        self.assertEqual(first, second)
        self.assertEqual(len(first["sha256"]), 64)

    def test_parser_rejects_duplicate_json_keys(self):
        with self.assertRaises(ContractError):
            parse_input('{"schema_version":"x","schema_version":"y"}')

    def test_parser_rejects_empty_policy_and_non_normalized_paths(self):
        value = make_input()
        value["policy"]["claims"] = []
        with self.assertRaises(ContractError):
            parse_input(json.dumps(value))
        value = make_input(path="src/../auth.py")
        with self.assertRaises(ContractError):
            parse_input(json.dumps(value))


if __name__ == "__main__":
    unittest.main()
