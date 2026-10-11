"""Bind a Duo candidate assessment to an existing Review Package.

This creates a linked envelope. It does not recompute or change the package's
attention route, and it does not authenticate the assessment's claimed source.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Any

from .contract import (
    ContractError,
    _SHA_RE,
    _decode_json,
    _identity,
    _keys,
    _text,
    parse_input,
)
from .router import _canonical_bytes, build_artifact

_HEX_256_RE = re.compile(r"\A[0-9a-f]{64}\Z")
_MAX_DOCUMENT_BYTES = 2_000_000


def _read_regular_file(path_text: str, label: str) -> bytes:
    path = Path(path_text)
    if path.is_symlink() or not path.is_file():
        raise ContractError(f"{label} path must be a regular non-symlink file")
    with path.open("rb") as stream:
        data = stream.read(_MAX_DOCUMENT_BYTES + 1)
    if len(data) > _MAX_DOCUMENT_BYTES:
        raise ContractError(f"{label} exceeds the 2 MB limit")
    return data


def _verified_package(data: bytes) -> dict[str, Any]:
    package = _decode_json(data, "review package")
    if not isinstance(package, dict) or package.get("schema_version") != "tbaf.review-package/v2":
        raise ContractError("review package schema_version must be tbaf.review-package/v2")
    digest = package.get("sha256")
    if not isinstance(digest, str) or not _HEX_256_RE.fullmatch(digest):
        raise ContractError("review package sha256 is missing or malformed")
    unsigned = dict(package)
    del unsigned["sha256"]
    if hashlib.sha256(_canonical_bytes(unsigned)).hexdigest() != digest:
        raise ContractError("review package sha256 does not match its contents")

    policy = package.get("policy")
    if not isinstance(policy, dict):
        raise ContractError("review package policy must be an object")
    policy_digest = policy.get("sha256")
    policy_payload = dict(policy)
    policy_payload.pop("sha256", None)
    if (not isinstance(policy_digest, str) or not _HEX_256_RE.fullmatch(policy_digest)
            or hashlib.sha256(_canonical_bytes(policy_payload)).hexdigest() != policy_digest):
        raise ContractError("review package policy sha256 does not match its contents")

    policy_document = dict(policy_payload)
    policy_document["schema_version"] = "tbaf.policy/v1"
    review_input = {
        "schema_version": "tbaf.review-input/v1",
        "change": package.get("change"),
        "observations": package.get("observations"),
        "checks": package.get("checks"),
    }
    parsed = parse_input(
        json.dumps(review_input, ensure_ascii=False),
        json.dumps(policy_document, ensure_ascii=False),
    )
    if build_artifact(parsed) != package:
        raise ContractError("review package does not match a recomputed deterministic result")
    return package


def _assessment_observations(
    package: dict[str, Any], assessment_data: bytes,
) -> tuple[dict[str, Any], list[dict[str, Any]], dict[str, Any]]:
    try:
        assessment_text = assessment_data.decode("utf-8", errors="strict")
    except UnicodeDecodeError as exc:
        raise ContractError("Duo assessment must be UTF-8") from exc
    json_blocks = re.findall(
        r"```json[ \t]*\r?\n(.*?)\r?\n```",
        assessment_text,
        flags=re.IGNORECASE | re.DOTALL,
    )
    if json_blocks:
        if len(json_blocks) != 1:
            raise ContractError("Duo assessment must contain exactly one fenced JSON block")
        assessment_data = json_blocks[0].encode("utf-8")
    assessment = _decode_json(assessment_data, "Duo assessment")
    if not isinstance(assessment, dict):
        raise ContractError("Duo assessment must be an object")
    assessment_schema = assessment.get("schema_version")
    if assessment_schema == "tbaf.duo-assessment/v1":
        assessment = _keys(
            assessment,
            {"schema_version", "change", "source", "observations"},
            {"schema_version", "change", "source", "observations"},
            "Duo assessment",
        )
        # V1 did not carry completeness metadata. Never infer completeness from
        # the absence of a truncation warning in prose.
        diff_coverage = {
            "status": "unknown",
            "paths": [],
            "limitations": ["legacy_v1_assessment_has_no_structured_diff_coverage"],
            "assertion_source": "compatibility_default_not_independently_verified",
        }
    elif assessment_schema == "tbaf.duo-assessment/v2":
        assessment = _keys(
            assessment,
            {"schema_version", "change", "source", "observations", "diff_coverage"},
            {"schema_version", "change", "source", "observations", "diff_coverage"},
            "Duo assessment",
        )
        coverage = _keys(
            assessment["diff_coverage"],
            {"status", "paths", "limitations"},
            {"status", "paths", "limitations"},
            "Duo assessment diff_coverage",
        )
        status = coverage["status"]
        if not isinstance(status, str) or status not in {"complete", "partial", "unknown"}:
            raise ContractError("Duo assessment diff_coverage.status is unsupported")
        if not isinstance(coverage["paths"], list) or len(coverage["paths"]) > 2000:
            raise ContractError("Duo assessment diff_coverage.paths must be a bounded array")
        if not isinstance(coverage["limitations"], list) or len(coverage["limitations"]) > 100:
            raise ContractError("Duo assessment diff_coverage.limitations must be a bounded array")
        package_paths = package.get("change", {}).get("paths", [])
        coverage_paths = [
            _text(item, "Duo assessment diff_coverage path", limit=2048)
            for item in coverage["paths"]
        ]
        if (len(set(coverage_paths)) != len(coverage_paths)
                or any(path not in package_paths for path in coverage_paths)):
            raise ContractError("Duo assessment diff_coverage path must be a unique changed path")
        limitations = [
            _text(item, "Duo assessment diff_coverage limitation", limit=1000)
            for item in coverage["limitations"]
        ]
        if status == "complete" and (coverage_paths or limitations):
            raise ContractError("complete diff_coverage cannot include paths or limitations")
        if status != "complete" and not limitations:
            raise ContractError("partial or unknown diff_coverage requires a limitation")
        diff_coverage = {
            "status": status,
            "paths": coverage_paths,
            "limitations": limitations,
            "assertion_source": "reported_by_agent_not_independently_verified",
        }
    else:
        raise ContractError("Duo assessment schema_version is unsupported")

    expected_change = package.get("change")
    if not isinstance(expected_change, dict):
        raise ContractError("review package change must be an object")
    change = _keys(
        assessment["change"], {"project", "mr_iid", "head_sha"},
        {"project", "mr_iid", "head_sha"}, "Duo assessment change",
    )
    iid = change["mr_iid"]
    if isinstance(iid, bool) or not isinstance(iid, int) or iid < 1:
        raise ContractError("Duo assessment change.mr_iid must be a positive integer")
    identity = {
        "project": _text(change["project"], "Duo assessment change.project", limit=255),
        "mr_iid": iid,
        "head_sha": _text(change["head_sha"], "Duo assessment change.head_sha", limit=64),
    }
    if not _SHA_RE.fullmatch(identity["head_sha"]):
        raise ContractError("Duo assessment change.head_sha must be a lowercase Git object ID")
    for key in ("project", "mr_iid", "head_sha"):
        if identity[key] != expected_change.get(key):
            raise ContractError(f"Duo assessment {key} does not match the Review Package")

    source = _keys(
        assessment["source"], {"agent", "version"},
        {"agent", "version"}, "Duo assessment source",
    )
    source_record = {
        "agent": _identity(source["agent"], "Duo assessment source.agent"),
        "version": _text(source["version"], "Duo assessment source.version", limit=128),
        "authentication": "reported_by_input_not_independently_verified",
        "bound_policy_sha256": package["policy"]["sha256"],
    }

    policy = dict(package["policy"])
    policy.pop("sha256", None)
    policy["schema_version"] = "tbaf.policy/v1"
    review_input = {
        "schema_version": "tbaf.review-input/v1",
        "change": expected_change,
        "observations": assessment["observations"],
        "checks": [],
    }
    parsed = parse_input(
        json.dumps(review_input, ensure_ascii=False),
        json.dumps(policy, ensure_ascii=False),
    )
    if any(item["revision"] != expected_change["head_sha"] for item in parsed["observations"]):
        raise ContractError("every candidate observation revision must match the Review Package head SHA")
    if any(item["source"]["agent"] != source_record["agent"]
           or item["source"]["version"] != source_record["version"]
           for item in parsed["observations"]):
        raise ContractError("candidate observation source must match the assessment source")
    source_record["assessment_sha256"] = hashlib.sha256(assessment_data).hexdigest()
    return source_record, parsed["observations"], diff_coverage


def link_assessment(package_data: bytes, assessment_data: bytes) -> dict[str, Any]:
    """Create a SHA-bound envelope without changing the original router result."""
    package = _verified_package(package_data)
    source, observations, diff_coverage = _assessment_observations(package, assessment_data)
    linked: dict[str, Any] = {
        "schema_version": "tbaf.review-package-link/v2",
        "review_package": package,
        "change_mapper": {
            "source": source,
            "observations": observations,
            "diff_coverage": diff_coverage,
            "epistemic_status": "CANDIDATE",
            "does_not_authorize": ["merge", "release", "deployment"],
        },
    }
    linked["sha256"] = hashlib.sha256(_canonical_bytes(linked)).hexdigest()
    return linked


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="tbaf-link-assessment",
        description="Bind candidate Duo observations to a matching deterministic Review Package.",
    )
    parser.add_argument("review_package", help="tbaf.review-package/v2 JSON file")
    parser.add_argument("duo_assessment", help="tbaf.duo-assessment/v1 or v2 JSON file")
    parser.add_argument("--compact", action="store_true", help="write compact JSON")
    args = parser.parse_args(argv)
    try:
        linked = link_assessment(
            _read_regular_file(args.review_package, "review package"),
            _read_regular_file(args.duo_assessment, "Duo assessment"),
        )
    except (OSError, ContractError, ValueError) as exc:
        print(f"tbaf-link-assessment: rejected: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(linked, ensure_ascii=False, sort_keys=True, indent=None if args.compact else 2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
