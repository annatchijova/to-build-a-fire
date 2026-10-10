"""Falsifiable tests for the bounded, non-executing auth source check."""

from __future__ import annotations

import json
import unittest

from tbaf.auth_invariants import MAX_SOURCE_BYTES, build_authorization_check, check_authorization_invariants
from tbaf.contract import parse_input
from tbaf.router import build_artifact


BASE = "a" * 40
HEAD = "b" * 40


SAFE_SOURCE = """
def can_read_record(user, record):
    if not user.is_authenticated:
        return False
    return user.is_admin or record.owner_id == user.id
"""

SEEDED_BYPASS = """
def can_read_record(user, record):
    if not user.is_authenticated:
        return False
    return user.is_admin or record.owner_id == user.id or user.is_authenticated
"""


class AuthorizationInvariantTests(unittest.TestCase):
    def _route_source(self, source: bytes):
        review_input = {
            "schema_version": "tbaf.review-input/v1",
            "change": {
                "project": "example/service", "mr_iid": 2,
                "base_sha": BASE, "head_sha": HEAD, "paths": ["src/auth.py"],
            },
            "observations": [],
            "checks": [build_authorization_check(source, HEAD)],
        }
        policy = {
            "schema_version": "tbaf.policy/v1", "id": "auth", "version": "1",
            "capacity_minutes": 90,
            "claims": [{
                "id": "authorization-boundary",
                "statement": "can_read_record denies unauthenticated users and authenticated non-owner non-admins, and permits authenticated owners or admins.",
                "consequence": "critical", "path_globs": ["src/auth.py"],
                "required_checks": ["authorization-invariants"],
                "review_route": "targeted", "attention_minutes": 35,
                "estimate_source": "team estimate",
            }],
        }
        parsed = parse_input(json.dumps(review_input), json.dumps(policy))
        return build_artifact(parsed)

    def test_safe_fixture_passes_the_declared_scenario_matrix(self):
        result = check_authorization_invariants(SAFE_SOURCE.encode())
        self.assertEqual(result["status"], "PASS")
        self.assertEqual(result["failed_scenarios"], [])

    def test_seeded_authenticated_non_owner_bypass_fails(self):
        result = check_authorization_invariants(SEEDED_BYPASS.encode())
        self.assertEqual(result["status"], "FAIL")
        self.assertEqual(result["failed_scenarios"], [
            "authenticated_non_owner_denied (authenticated=true, admin=false, owner=false)",
        ])

    def test_seeded_violation_stays_unresolved_and_routes_to_human(self):
        artifact = self._route_source(SEEDED_BYPASS.encode())
        self.assertEqual(artifact["checks"][0]["status"], "FAIL")
        self.assertIn("authenticated_non_owner_denied", artifact["checks"][0]["details"])
        self.assertEqual(artifact["claims"][0]["evidence_state"], "UNRESOLVED")
        self.assertEqual(artifact["attention"]["route"], "TARGETED_REVIEW")

    def test_safe_supported_function_covers_the_declared_claim(self):
        artifact = self._route_source(SAFE_SOURCE.encode())
        self.assertEqual(artifact["checks"][0]["status"], "PASS")
        self.assertEqual(artifact["claims"][0]["evidence_state"], "SUPPORTED")
        self.assertEqual(artifact["attention"]["route"], "COVERED_BY_EVIDENCE")

    def test_checker_parses_but_never_executes_module_source(self):
        source = "raise RuntimeError('untrusted module executed')\n" + SAFE_SOURCE
        result = check_authorization_invariants(source.encode())
        self.assertEqual(result["status"], "NOT_RUN")
        self.assertIn("top-level code", result["details"])

    def test_unknown_syntax_degrades_to_not_run(self):
        source = "def can_read_record(user, record):\n    return authorize(user, record)\n"
        result = check_authorization_invariants(source.encode())
        self.assertEqual(result["status"], "NOT_RUN")
        self.assertEqual(result["failed_scenarios"], [])

    def test_literal_specific_identity_rule_degrades_to_not_run(self):
        source = "def can_read_record(user, record):\n    return user.id == 7\n"
        result = check_authorization_invariants(source.encode())
        self.assertEqual(result["status"], "NOT_RUN")

    def test_identity_is_not_accepted_as_a_boolean_condition(self):
        source = "def can_read_record(user, record):\n    return user.id\n"
        result = check_authorization_invariants(source.encode())
        self.assertEqual(result["status"], "NOT_RUN")

    def test_missing_function_degrades_to_not_run(self):
        result = check_authorization_invariants(b"def unrelated():\n    return True\n")
        self.assertEqual(result["status"], "NOT_RUN")

    def test_oversized_and_non_utf8_inputs_degrade_to_not_run(self):
        oversized = check_authorization_invariants(b" " * (MAX_SOURCE_BYTES + 1))
        malformed = check_authorization_invariants(b"\xff")
        self.assertEqual(oversized["status"], "NOT_RUN")
        self.assertEqual(malformed["status"], "NOT_RUN")

    def test_check_record_binds_result_to_exact_revision_and_blob(self):
        revision = "b" * 40
        result = build_authorization_check(SEEDED_BYPASS.encode(), revision)
        self.assertEqual(result["revision"], revision)
        self.assertEqual(result["artifact_ref"], f"git-object:{revision}:src/auth.py")
        self.assertEqual(result["status"], "FAIL")
        self.assertIn("authenticated_non_owner_denied", result["details"])


if __name__ == "__main__":
    unittest.main()
