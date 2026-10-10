"""Falsifiable controls for exact-head Duo assessment linking."""

from __future__ import annotations

import json
import unittest
from pathlib import Path

from tbaf.contract import ContractError, parse_input
from tbaf.gitlab_assessment_link import link_latest_assessment
from tbaf.link_assessment import link_assessment
from tbaf.router import build_artifact


PROJECT = "gitlab-ai-hackathon/transcend-october-2026/1688368/showcase"
MR_IID = 2
BASE_SHA = "2a9e7f9b82b90d7d6a97bd9f24aa7db878c763f6"
HEAD_SHA = "e843e0d8128f5c6363d47e6272850fb709e4badc"
STALE_SHA = "3a4fb86487d819a8589ec11770487ecf110313cb"
MAPPER_USER_ID = 43107902


def make_review_package() -> dict:
    policy_path = Path(__file__).parents[1] / "examples" / "policy.json"
    policy = json.loads(policy_path.read_text(encoding="utf-8"))
    review_input = {
        "schema_version": "tbaf.review-input/v1",
        "change": {
            "project": PROJECT,
            "mr_iid": MR_IID,
            "base_sha": BASE_SHA,
            "head_sha": HEAD_SHA,
            "paths": ["src/auth.py"],
        },
        "observations": [],
        "checks": [{
            "id": "authorization-invariants",
            "claim_id": "authorization-boundary",
            "status": "FAIL",
            "revision": HEAD_SHA,
            "source": {"name": "bounded-ast-probe", "version": "1"},
            "scope": "Authorization boundary fixture",
            "artifact_ref": "ci://fixture/snapshot",
        }],
    }
    parsed = parse_input(json.dumps(review_input), json.dumps(policy))
    return build_artifact(parsed)


def make_assessment(head_sha: str = HEAD_SHA) -> str:
    assessment = {
        "schema_version": "tbaf.duo-assessment/v1",
        "change": {"project": PROJECT, "mr_iid": MR_IID, "head_sha": head_sha},
        "source": {"agent": "inspect_mr", "version": "1"},
        "observations": [{
            "id": "CMAP-001",
            "kind": "impact_candidate",
            "claim_id": "authorization-boundary",
            "impact": "affected",
            "source": {"agent": "inspect_mr", "version": "1"},
            "revision": head_sha,
            "scope": "Authorization boundary",
            "text": "Candidate observation from the supplied MR diff; not a safety conclusion.",
            "locations": [{"path": "src/auth.py", "start_line": 9, "end_line": 13}],
        }],
    }
    return "Assessment follows.\n```json\n" + json.dumps(assessment) + "\n```"


def make_note(note_id: int, head_sha: str, created_at: str) -> dict:
    return {
        "id": note_id,
        "author": {"id": MAPPER_USER_ID},
        "internal": True,
        "system": False,
        "created_at": created_at,
        "body": make_assessment(head_sha),
    }


class GitLabAssessmentLinkTests(unittest.TestCase):
    def setUp(self):
        self.package = make_review_package()
        self.package_data = json.dumps(self.package, sort_keys=True).encode("utf-8")
        self.original_package = json.loads(self.package_data)
        self.config = {
            "project_id": 87290826,
            "flow_id": "1016156",
            "change_mapper_user_id": MAPPER_USER_ID,
        }

    def test_stale_head_is_rejected_and_never_changes_the_review_package(self):
        stale_body = make_assessment(STALE_SHA).split("```json\n", 1)[1].split("\n```", 1)[0]
        with self.assertRaisesRegex(ContractError, "head_sha does not match"):
            link_assessment(self.package_data, stale_body.encode("utf-8"))

        status, linked = link_latest_assessment(
            self.package_data,
            [make_note(3967085782, STALE_SHA, "2026-10-09T12:00:00Z")],
            self.config,
        )

        self.assertEqual(status["status"], "not_found")
        self.assertEqual(status["reason"], "no_valid_assessment_for_package_head")
        self.assertEqual(status["head_sha"], HEAD_SHA)
        self.assertEqual(status["mapper_notes_seen"], 1)
        self.assertIsNone(linked)
        self.assertEqual(self.package, self.original_package)

    def test_exact_head_wins_over_newer_stale_note_and_preserves_original_package(self):
        exact_note = make_note(3990952436, HEAD_SHA, "2026-10-10T21:01:49Z")
        stale_note = make_note(3967085782, STALE_SHA, "2026-10-11T12:00:00Z")

        status, linked = link_latest_assessment(
            self.package_data,
            [exact_note, stale_note],
            self.config,
        )

        self.assertEqual(status["status"], "linked")
        self.assertEqual(status["head_sha"], HEAD_SHA)
        self.assertEqual(status["gitlab_note_id"], exact_note["id"])
        self.assertEqual(status["mapper_notes_seen"], 2)
        self.assertEqual(status["candidate_observation_count"], 1)
        self.assertIsNotNone(linked)
        self.assertEqual(linked["review_package"], self.original_package)
        self.assertEqual(linked["review_package"]["sha256"], self.package["sha256"])
        self.assertEqual(
            linked["review_package"]["attention"], self.package["attention"],
        )
        self.assertEqual(linked["review_package"]["claims"], self.package["claims"])
        self.assertEqual(linked["change_mapper"]["epistemic_status"], "CANDIDATE")


if __name__ == "__main__":
    unittest.main()
