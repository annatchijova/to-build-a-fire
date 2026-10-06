"""Bounded, strict parsing for the internal Review Package input contract.

The contract accepts observations from upstream agents and checks. It never
interprets agent prose as instruction and never lets an observation set policy.
"""

from __future__ import annotations

import json
import re
from typing import Any

INPUT_SCHEMA = "tbaf.review-input/v1"
MAX_INPUT_BYTES = 2_000_000
MAX_ITEMS = 2_000
MAX_TEXT = 10_000
_SHA_RE = re.compile(r"\A(?:[0-9a-f]{40}|[0-9a-f]{64})\Z")
_IDENT_RE = re.compile(r"\A[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}\Z")
_PROJECT_RE = re.compile(r"\A[A-Za-z0-9_.-]+(?:/[A-Za-z0-9_.-]+)+\Z")


class ContractError(ValueError):
    """The input is malformed or outside the supported contract."""


def _object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ContractError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def _keys(value: Any, required: set[str], allowed: set[str], where: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ContractError(f"{where} must be an object")
    missing = required - value.keys()
    extra = value.keys() - allowed
    if missing:
        raise ContractError(f"{where} missing keys: {', '.join(sorted(missing))}")
    if extra:
        raise ContractError(f"{where} has unsupported keys: {', '.join(sorted(extra))}")
    return value


def _text(value: Any, where: str, *, limit: int = 512, allow_empty: bool = False) -> str:
    if not isinstance(value, str) or len(value) > limit:
        raise ContractError(f"{where} must be text of at most {limit} characters")
    if not allow_empty and not value.strip():
        raise ContractError(f"{where} must not be empty")
    if "\x00" in value:
        raise ContractError(f"{where} contains a null byte")
    return value


def _integer(value: Any, where: str, *, minimum: int = 0, maximum: int = 1_000_000) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or not minimum <= value <= maximum:
        raise ContractError(f"{where} must be an integer from {minimum} to {maximum}")
    return value


def _list(value: Any, where: str, *, maximum: int = MAX_ITEMS) -> list[Any]:
    if not isinstance(value, list) or len(value) > maximum:
        raise ContractError(f"{where} must be a list with at most {maximum} entries")
    return value


def _path(value: Any, where: str) -> str:
    path = _text(value, where, limit=1024)
    if path.startswith("/") or "\\" in path or any(part in ("", ".", "..") for part in path.split("/")):
        raise ContractError(f"{where} must be a normalized repository-relative path")
    return path


def _paths(value: Any, where: str, *, patterns: bool = False) -> list[str]:
    paths = _list(value, where, maximum=MAX_ITEMS)
    output = []
    for index, item in enumerate(paths):
        path = _text(item, f"{where}[{index}]", limit=1024)
        segments = path.split("/")
        if path.startswith("/") or "\\" in path or any(part in ("", ".", "..") for part in segments):
            raise ContractError(f"{where}[{index}] must be repository-relative")
        if not patterns and any(ch in path for ch in "*?["):
            raise ContractError(f"{where}[{index}] must be a concrete path")
        output.append(path)
    return output


def _identity(value: Any, where: str) -> str:
    text = _text(value, where, limit=128)
    if not _IDENT_RE.fullmatch(text):
        raise ContractError(f"{where} contains unsupported identifier characters")
    return text


def _decode_json(data: bytes | str, where: str) -> Any:
    if isinstance(data, bytes):
        if len(data) > MAX_INPUT_BYTES:
            raise ContractError(f"{where} exceeds the 2 MB limit")
        try:
            source = data.decode("utf-8", errors="strict")
        except UnicodeDecodeError as exc:
            raise ContractError(f"{where} must be UTF-8") from exc
    elif isinstance(data, str):
        if len(data.encode("utf-8")) > MAX_INPUT_BYTES:
            raise ContractError(f"{where} exceeds the 2 MB limit")
        source = data
    else:
        raise ContractError(f"{where} must be UTF-8 JSON bytes or text")

    try:
        return json.loads(source, object_pairs_hook=_object, parse_constant=lambda v: (_ for _ in ()).throw(ContractError(f"invalid number: {v}")))
    except ContractError:
        raise
    except (json.JSONDecodeError, RecursionError) as exc:
        raise ContractError(f"{where} is not valid bounded JSON") from exc


def parse_policy(data: bytes | str) -> dict[str, Any]:
    """Parse the separately supplied repository policy v1 document."""
    raw = _decode_json(data, "policy")
    policy = _keys(raw, {"schema_version", "id", "version", "capacity_minutes", "claims"},
                   {"schema_version", "id", "version", "capacity_minutes", "claims"}, "policy")
    if policy["schema_version"] != "tbaf.policy/v1":
        raise ContractError("policy.schema_version must be tbaf.policy/v1")
    policy_id = _identity(policy["id"], "policy.id")
    policy_version = _text(policy["version"], "policy.version", limit=128)
    capacity = policy["capacity_minutes"]
    if capacity is not None:
        capacity = _integer(capacity, "policy.capacity_minutes", maximum=100_000)

    claims: list[dict[str, Any]] = []
    seen_claims: set[str] = set()
    for index, item in enumerate(_list(policy["claims"], "policy.claims")):
        where = f"policy.claims[{index}]"
        claim = _keys(item, {"id", "statement", "consequence", "path_globs", "required_checks", "review_route", "attention_minutes", "estimate_source"},
                      {"id", "statement", "consequence", "path_globs", "required_checks", "review_route", "attention_minutes", "estimate_source"}, where)
        claim_id = _identity(claim["id"], f"{where}.id")
        if claim_id in seen_claims:
            raise ContractError(f"duplicate claim id: {claim_id}")
        seen_claims.add(claim_id)
        consequence = _text(claim["consequence"], f"{where}.consequence", limit=16)
        if consequence not in {"low", "medium", "high", "critical"}:
            raise ContractError(f"{where}.consequence must be low, medium, high, or critical")
        route = _text(claim["review_route"], f"{where}.review_route", limit=16)
        if route not in {"targeted", "deep"}:
            raise ContractError(f"{where}.review_route must be targeted or deep")
        minutes = claim["attention_minutes"]
        if minutes is not None:
            minutes = _integer(minutes, f"{where}.attention_minutes", minimum=1, maximum=10_000)
        estimate_source = claim["estimate_source"]
        if estimate_source is not None:
            estimate_source = _text(estimate_source, f"{where}.estimate_source", limit=256)
        if (minutes is None) != (estimate_source is None):
            raise ContractError(f"{where} must provide both attention_minutes and estimate_source, or neither")
        checks = [_identity(v, f"{where}.required_checks[]") for v in _list(claim["required_checks"], f"{where}.required_checks", maximum=100)]
        if len(set(checks)) != len(checks):
            raise ContractError(f"{where}.required_checks contains duplicates")
        path_globs = _paths(claim["path_globs"], f"{where}.path_globs", patterns=True)
        if not path_globs:
            raise ContractError(f"{where}.path_globs must declare at least one protected path")
        claims.append({
            "id": claim_id,
            "statement": _text(claim["statement"], f"{where}.statement", limit=MAX_TEXT),
            "consequence": consequence,
            "path_globs": path_globs,
            "required_checks": checks,
            "review_route": route,
            "attention_minutes": minutes,
            "estimate_source": estimate_source,
        })
    if not claims:
        raise ContractError("policy.claims must contain at least one declared protected claim")
    return {"id": policy_id, "version": policy_version, "capacity_minutes": capacity, "claims": claims}


def parse_input(data: bytes | str, policy_data: bytes | str) -> dict[str, Any]:
    """Parse one untrusted MR record under a separately supplied policy."""
    raw = _decode_json(data, "input")

    top = _keys(raw, {"schema_version", "change", "observations", "checks"},
                {"schema_version", "change", "observations", "checks"}, "input")
    if top["schema_version"] != INPUT_SCHEMA:
        raise ContractError(f"schema_version must be {INPUT_SCHEMA}")

    change = _keys(top["change"], {"project", "mr_iid", "base_sha", "head_sha", "paths"},
                   {"project", "mr_iid", "base_sha", "head_sha", "paths"}, "change")
    project = _text(change["project"], "change.project", limit=255)
    if not _PROJECT_RE.fullmatch(project):
        raise ContractError("change.project must be a namespace/project path")
    mr_iid = _integer(change["mr_iid"], "change.mr_iid", minimum=1)
    base_sha = _text(change["base_sha"], "change.base_sha", limit=64)
    head_sha = _text(change["head_sha"], "change.head_sha", limit=64)
    if not _SHA_RE.fullmatch(base_sha) or not _SHA_RE.fullmatch(head_sha):
        raise ContractError("base_sha and head_sha must be lowercase 40- or 64-character Git object IDs")
    if base_sha == head_sha:
        raise ContractError("base_sha and head_sha must identify different revisions")
    paths = _paths(change["paths"], "change.paths")
    if not paths:
        raise ContractError("change.paths must contain at least one changed path")
    if len(set(paths)) != len(paths):
        raise ContractError("change.paths contains duplicates")

    policy = parse_policy(policy_data)
    claims = policy["claims"]

    observations: list[dict[str, Any]] = []
    seen_observations: set[str] = set()
    for index, item in enumerate(_list(top["observations"], "observations", maximum=MAX_ITEMS)):
        where = f"observations[{index}]"
        obs = _keys(item, {"id", "kind", "claim_id", "impact", "source", "revision", "scope", "text", "locations"},
                    {"id", "kind", "claim_id", "impact", "source", "revision", "scope", "text", "locations"}, where)
        obs_id = _identity(obs["id"], f"{where}.id")
        if obs_id in seen_observations:
            raise ContractError(f"duplicate observation id: {obs_id}")
        seen_observations.add(obs_id)
        kind = _text(obs["kind"], f"{where}.kind", limit=32)
        if kind not in {"impact_candidate", "counterexample_candidate"}:
            raise ContractError(f"{where}.kind must be impact_candidate or counterexample_candidate")
        claim_id = obs["claim_id"]
        if claim_id is not None:
            claim_id = _identity(claim_id, f"{where}.claim_id")
        impact = _text(obs["impact"], f"{where}.impact", limit=16)
        if impact not in {"affected", "not_affected", "unknown"}:
            raise ContractError(f"{where}.impact must be affected, not_affected, or unknown")
        source = _keys(obs["source"], {"agent", "version"}, {"agent", "version"}, f"{where}.source")
        revision = _text(obs["revision"], f"{where}.revision", limit=64)
        if not _SHA_RE.fullmatch(revision):
            raise ContractError(f"{where}.revision must be a lowercase Git object ID")
        locations = []
        for li, location_item in enumerate(_list(obs["locations"], f"{where}.locations", maximum=100)):
            lw = f"{where}.locations[{li}]"
            location = _keys(location_item, {"path", "start_line", "end_line"}, {"path", "start_line", "end_line"}, lw)
            start = _integer(location["start_line"], f"{lw}.start_line", minimum=1, maximum=10_000_000)
            end = _integer(location["end_line"], f"{lw}.end_line", minimum=start, maximum=10_000_000)
            locations.append({"path": _path(location["path"], f"{lw}.path"), "start_line": start, "end_line": end})
        observations.append({
            "id": obs_id,
            "kind": kind,
            "claim_id": claim_id,
            "impact": impact,
            "source": {
                "agent": _identity(source["agent"], f"{where}.source.agent"),
                "version": _text(source["version"], f"{where}.source.version", limit=128),
            },
            "revision": revision,
            "scope": _text(obs["scope"], f"{where}.scope", limit=MAX_TEXT),
            "text": _text(obs["text"], f"{where}.text", limit=MAX_TEXT),
            "locations": locations,
            "epistemic_status": "CANDIDATE",
        })

    changed_paths = set(paths)
    for observation in observations:
        for location in observation["locations"]:
            if location["path"] not in changed_paths:
                raise ContractError(f"observation {observation['id']} location is outside the changed paths")

    checks: list[dict[str, Any]] = []
    seen_checks: set[str] = set()
    for index, item in enumerate(_list(top["checks"], "checks", maximum=MAX_ITEMS)):
        where = f"checks[{index}]"
        check = _keys(item, {"id", "claim_id", "status", "revision", "source", "scope", "artifact_ref"},
                      {"id", "claim_id", "status", "revision", "source", "scope", "artifact_ref"}, where)
        check_id = _identity(check["id"], f"{where}.id")
        if check_id in seen_checks:
            raise ContractError(f"duplicate check id: {check_id}")
        seen_checks.add(check_id)
        claim_id = _identity(check["claim_id"], f"{where}.claim_id")
        status = _text(check["status"], f"{where}.status", limit=16)
        if status not in {"PASS", "FAIL", "CONTRADICTED", "NOT_RUN", "UNAVAILABLE"}:
            raise ContractError(f"{where}.status is unsupported")
        revision = _text(check["revision"], f"{where}.revision", limit=64)
        if not _SHA_RE.fullmatch(revision):
            raise ContractError(f"{where}.revision must be a lowercase Git object ID")
        source = _keys(check["source"], {"name", "version"}, {"name", "version"}, f"{where}.source")
        artifact_ref = check["artifact_ref"]
        if artifact_ref is not None:
            artifact_ref = _text(artifact_ref, f"{where}.artifact_ref", limit=2048)
        checks.append({
            "id": check_id,
            "claim_id": claim_id,
            "status": status,
            "revision": revision,
            "source": {
                "name": _identity(source["name"], f"{where}.source.name"),
                "version": _text(source["version"], f"{where}.source.version", limit=128),
            },
            "scope": _text(check["scope"], f"{where}.scope", limit=MAX_TEXT),
            "artifact_ref": artifact_ref,
        })

    known_claims = {claim["id"] for claim in claims}
    for check in checks:
        if check["claim_id"] not in known_claims:
            raise ContractError(f"check {check['id']} refers to unknown claim {check['claim_id']}")

    return {
        "schema_version": INPUT_SCHEMA,
        "change": {"project": project, "mr_iid": mr_iid, "base_sha": base_sha, "head_sha": head_sha, "paths": paths},
        "policy": policy,
        "observations": observations,
        "checks": checks,
    }
