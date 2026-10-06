"""Deterministic attention routing over a validated review input."""

from __future__ import annotations

import fnmatch
import hashlib
import json
from typing import Any


_CONSEQUENCE_ORDER = {"unknown": 0, "critical": 1, "high": 2, "medium": 3, "low": 4}


def _canonical_bytes(value: Any) -> bytes:
    """Serialize the internal artifact deterministically; floats are forbidden."""
    def reject_float(item: Any) -> None:
        if isinstance(item, float):
            raise ValueError("floating-point values are not allowed in the sealed artifact")
        if isinstance(item, dict):
            for child in item.values():
                reject_float(child)
        elif isinstance(item, list):
            for child in item:
                reject_float(child)

    reject_float(value)
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _path_matches(path: str, pattern: str) -> bool:
    return fnmatch.fnmatchcase(path, pattern)


def _claim_state(claim: dict[str, Any], input_data: dict[str, Any]) -> tuple[str, list[str], list[dict[str, Any]]]:
    change = input_data["change"]
    claim_observations = [o for o in input_data["observations"] if o["claim_id"] == claim["id"]]
    relevant_observations = [o for o in claim_observations if o["revision"] == change["head_sha"]]
    stale_observations = [o for o in claim_observations if o["revision"] != change["head_sha"]]
    path_affected = any(_path_matches(path, pattern) for path in change["paths"] for pattern in claim["path_globs"])
    # Candidate observations can raise attention; they can never dismiss a
    # path that policy maps to a protected claim.
    candidate_affected = any(o["impact"] in {"affected", "unknown"} for o in relevant_observations)
    affected = path_affected or candidate_affected
    if not affected:
        return "UNCHANGED_BY_DECLARED_SCOPE", (["stale_candidate_observation"] if stale_observations else []), relevant_observations + stale_observations

    checks = {c["id"]: c for c in input_data["checks"] if c["claim_id"] == claim["id"]}
    required = claim["required_checks"]
    if not required:
        return "UNRESOLVED", ["policy_has_no_required_evidence"], relevant_observations

    states = []
    reasons = []
    for check_id in required:
        check = checks.get(check_id)
        if check is None:
            states.append("NOT_RUN")
            reasons.append(f"required_check_missing:{check_id}")
        elif check["revision"] != change["head_sha"]:
            states.append("NOT_RUN")
            reasons.append(f"required_check_stale:{check_id}")
        elif check["status"] == "PASS":
            states.append("SUPPORTED")
        elif check["status"] == "CONTRADICTED":
            states.append("CONTRADICTED")
            reasons.append(f"required_check_contradicted:{check_id}")
        else:
            states.append("UNRESOLVED")
            reasons.append(f"required_check_{check['status'].lower()}:{check_id}")

    if stale_observations:
        reasons.append("stale_candidate_observation")
    if any(o["kind"] == "counterexample_candidate" for o in relevant_observations):
        reasons.append("candidate_counterexample_requires_adjudication")
    if "CONTRADICTED" in states:
        return "CONTRADICTED", reasons, relevant_observations
    if any(s != "SUPPORTED" for s in states) or stale_observations or any(o["kind"] == "counterexample_candidate" for o in relevant_observations):
        return "UNRESOLVED", reasons, relevant_observations
    return "SUPPORTED", reasons, relevant_observations


def build_artifact(input_data: dict[str, Any]) -> dict[str, Any]:
    """Create a reproducible internal package and an attention-router receipt."""
    claims = {claim["id"]: claim for claim in input_data["policy"]["claims"]}
    claim_results = []
    tasks = []
    deep_reasons = []
    unknown_observations = []
    unmapped_paths = []
    for path in input_data["change"]["paths"]:
        if not any(_path_matches(path, pattern) for claim in input_data["policy"]["claims"] for pattern in claim["path_globs"]):
            unmapped_paths.append(path)
            deep_reasons.append("changed_path_outside_declared_claim_scope")

    for observation in input_data["observations"]:
        if observation["revision"] != input_data["change"]["head_sha"]:
            deep_reasons.append("stale_candidate_observation")
            unknown_observations.append(observation)
            continue
        if observation["claim_id"] is None or observation["claim_id"] not in claims:
            if observation["impact"] != "not_affected":
                unknown_observations.append(observation)
                deep_reasons.append("unscoped_candidate_observation")

    for claim_id in sorted(claims):
        claim = claims[claim_id]
        state, reasons, observations = _claim_state(claim, input_data)
        claim_results.append({
            "claim_id": claim_id,
            "consequence": claim["consequence"],
            "evidence_state": state,
            "required_checks": list(claim["required_checks"]),
            "reasons": sorted(set(reasons)),
            "candidate_observation_ids": sorted(o["id"] for o in observations),
            "locations": sorted({
                (location["path"], location["start_line"], location["end_line"])
                for observation in observations for location in observation["locations"]
            }),
        })
        if state in {"UNRESOLVED", "CONTRADICTED"}:
            if claim["review_route"] == "deep" or state == "CONTRADICTED":
                deep_reasons.append(f"claim_requires_deep_review:{claim_id}")
            tasks.append({
                "task_id": f"review:{claim_id}",
                "claim_id": claim_id,
                "route": "DEEP_REVIEW" if claim["review_route"] == "deep" or state == "CONTRADICTED" else "TARGETED_REVIEW",
                "consequence": claim["consequence"],
                "reason_codes": sorted(set(reasons)) or ["claim_unresolved"],
                "locations": [
                    {"path": path, "start_line": start, "end_line": end}
                    for path, start, end in claim_results[-1]["locations"]
                ],
                "required_minutes": claim["attention_minutes"],
                "estimate_source": claim["estimate_source"],
            })

    for observation in unknown_observations:
        tasks.append({
            "task_id": f"review:observation:{observation['id']}",
            "claim_id": None,
            "route": "DEEP_REVIEW",
            "consequence": "unknown",
            "reason_codes": ["stale_candidate_observation" if observation["revision"] != input_data["change"]["head_sha"] else "unscoped_candidate_observation", "human_adjudication_required"],
            "locations": observation["locations"],
            "required_minutes": None,
            "estimate_source": None,
        })

    for path in unmapped_paths:
        tasks.append({
            "task_id": "review:unmapped:" + hashlib.sha256(path.encode("utf-8")).hexdigest()[:12],
            "claim_id": None,
            "route": "DEEP_REVIEW",
            "consequence": "unknown",
            "reason_codes": ["changed_path_outside_declared_claim_scope", "human_adjudication_required"],
            "locations": [{"path": path, "start_line": 1, "end_line": 1}],
            "required_minutes": None,
            "estimate_source": None,
        })

    tasks.sort(key=lambda task: (
        _CONSEQUENCE_ORDER[task["consequence"]],
        0 if task["route"] == "DEEP_REVIEW" else 1,
        task["claim_id"] or "~" + task["task_id"],
        task["task_id"],
    ))

    if deep_reasons:
        route = "DEEP_REVIEW"
    elif tasks:
        route = "TARGETED_REVIEW"
    else:
        route = "COVERED_BY_EVIDENCE"

    capacity = input_data["policy"]["capacity_minutes"]
    known_demand = sum(task["required_minutes"] or 0 for task in tasks)
    unknown_count = sum(task["required_minutes"] is None for task in tasks)
    remaining = capacity
    scheduled_ids = []
    unscheduled_ids = []
    scheduled_known_minutes = 0
    for task in tasks:
        minutes = task["required_minutes"]
        if capacity is not None and minutes is not None and remaining is not None and minutes <= remaining:
            scheduled_ids.append(task["task_id"])
            scheduled_known_minutes += minutes
            remaining -= minutes
        else:
            unscheduled_ids.append(task["task_id"])

    if capacity is None:
        schedule_state = "CAPACITY_UNKNOWN"
    elif unknown_count:
        schedule_state = "PARTIAL_UNKNOWN_DEMAND"
    elif known_demand > capacity:
        schedule_state = "OVER_CAPACITY"
    else:
        schedule_state = "WITHIN_CAPACITY"

    artifact = {
        "schema_version": "tbaf.review-package/v1",
        "change": input_data["change"],
        "policy": {"id": input_data["policy"]["id"], "version": input_data["policy"]["version"]},
        "observations": input_data["observations"],
        "checks": input_data["checks"],
        "claims": claim_results,
        "attention": {
            "route": route,
            "reasons": sorted(set(deep_reasons + [reason for task in tasks for reason in task["reason_codes"]])),
            "tasks": tasks,
            "capacity_minutes": capacity,
            "known_demand_minutes": known_demand,
            "unknown_demand_tasks": unknown_count,
            "scheduled_known_minutes": scheduled_known_minutes,
            "uncovered_known_minutes": max(0, known_demand - scheduled_known_minutes),
            "scheduled_task_ids": scheduled_ids,
            "uncovered_task_ids": unscheduled_ids,
            "schedule_state": schedule_state,
        },
    }
    artifact["sha256"] = hashlib.sha256(_canonical_bytes(artifact)).hexdigest()
    return artifact
