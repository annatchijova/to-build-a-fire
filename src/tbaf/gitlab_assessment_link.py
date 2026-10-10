"""Attach an approved, internal Duo MR note to the matching snapshot artifact.

The job runs from protected default-branch code. The note remains untrusted
candidate data; this module never changes the deterministic package's route.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode, urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener

from .contract import ContractError, _decode_json, _keys, _text
from .link_assessment import link_assessment
from .router import _canonical_bytes

_INTEGER_RE = re.compile(r"\A[1-9][0-9]{0,8}\Z")
_MAX_RESPONSE_BYTES = 2_000_000
_MAX_NOTES_PAGES = 20
_MAX_NOTE_BODY = 100_000


def _required_env(name: str, maximum: int = 4096) -> str:
    value = os.environ.get(name, "")
    if not value or len(value) > maximum or "\x00" in value:
        raise ContractError(f"required CI variable {name} is missing or malformed")
    return value


def _decode_api_json(data: bytes, where: str) -> Any:
    return _decode_json(data, where)


def _load_config(path_text: str, project_id: str) -> dict[str, Any]:
    path = Path(path_text)
    if path.is_symlink() or not path.is_file():
        raise ContractError("integration config must be a regular non-symlink file")
    with path.open("rb") as stream:
        config = _decode_json(stream.read(_MAX_RESPONSE_BYTES + 1), "integration config")
    config = _keys(
        config,
        {"schema_version", "project_id", "flow_id", "change_mapper_user_id"},
        {"schema_version", "project_id", "flow_id", "change_mapper_user_id"},
        "integration config",
    )
    if config["schema_version"] != "tbaf.gitlab-flow-integration/v1":
        raise ContractError("integration config schema_version is unsupported")
    for key in ("project_id", "change_mapper_user_id"):
        value = config[key]
        if isinstance(value, bool) or not isinstance(value, int) or value < 1:
            raise ContractError(f"integration config {key} must be a positive integer")
    if str(config["project_id"]) != project_id:
        raise ContractError("integration config project_id does not match CI_PROJECT_ID")
    return {
        "project_id": config["project_id"],
        "flow_id": _text(config["flow_id"], "integration config flow_id", limit=128),
        "change_mapper_user_id": config["change_mapper_user_id"],
    }


def _notes_endpoint(api_root: str, server_url: str, project_id: str, mr_iid: str) -> str:
    api = urlsplit(api_root)
    server = urlsplit(server_url)
    if (api.scheme != "https" or not api.netloc or api.username or api.password
            or api.query or api.fragment or not api.path.rstrip("/").endswith("/api/v4")
            or server.scheme != "https" or api.netloc.lower() != server.netloc.lower()):
        raise ContractError("CI_API_V4_URL must be an HTTPS GitLab API v4 URL on CI_SERVER_URL")
    path = f"{api_root.rstrip('/')}/projects/{quote(project_id, safe='')}/merge_requests/{mr_iid}/notes"
    return path


def _fetch_notes(endpoint: str, job_token: str) -> list[dict[str, Any]]:
    class RejectRedirects(HTTPRedirectHandler):
        def redirect_request(self, req, fp, code, msg, headers, new_url):
            return None

    opener = build_opener(RejectRedirects())
    notes: list[dict[str, Any]] = []
    for page in range(1, _MAX_NOTES_PAGES + 1):
        url = endpoint + "?" + urlencode({"per_page": 100, "page": page, "sort": "desc", "order_by": "created_at"})
        request = Request(url, headers={"JOB-TOKEN": job_token, "Accept": "application/json"})
        try:
            with opener.open(request, timeout=20) as response:
                payload = response.read(_MAX_RESPONSE_BYTES + 1)
                next_page = response.headers.get("X-Next-Page", "")
        except (HTTPError, URLError, TimeoutError, OSError) as exc:
            raise ContractError("GitLab MR notes are unavailable to this CI job token") from exc
        if len(payload) > _MAX_RESPONSE_BYTES:
            raise ContractError("GitLab MR notes response exceeds the 2 MB limit")
        value = _decode_api_json(payload, "GitLab MR notes response")
        if not isinstance(value, list) or any(not isinstance(item, dict) for item in value):
            raise ContractError("GitLab MR notes response must be a list of objects")
        notes.extend(value)
        if not next_page:
            return notes
        if not next_page.isdecimal() or int(next_page) != page + 1:
            raise ContractError("GitLab MR notes pagination returned an invalid next page")
    raise ContractError("GitLab MR notes exceed the configured pagination limit")


def _note_metadata(note: dict[str, Any], config: dict[str, Any]) -> dict[str, Any] | None:
    author = note.get("author")
    if not isinstance(author, dict):
        return None
    author_id = author.get("id")
    if isinstance(author_id, bool) or author_id != config["change_mapper_user_id"]:
        return None
    if note.get("confidential") is not True or note.get("system") is True:
        return None
    note_id = note.get("id")
    if isinstance(note_id, bool) or not isinstance(note_id, int) or note_id < 1:
        return None
    body = note.get("body")
    if not isinstance(body, str) or len(body.encode("utf-8")) > _MAX_NOTE_BODY or "\x00" in body:
        return None
    created_at = note.get("created_at")
    if not isinstance(created_at, str) or len(created_at) > 64:
        return None
    return {
        "note_id": note_id,
        "author_id": author_id,
        "confidential": True,
        # The Notes API does not attest which flow created a note. Keep the
        # configured flow as context, not as verified provenance.
        "configured_flow_id": config["flow_id"],
        "created_at": created_at,
        "body": body,
    }


def link_latest_assessment(
    package_data: bytes,
    notes: list[dict[str, Any]],
    config: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any] | None]:
    candidates = []
    mapper_notes = 0
    for note in notes:
        metadata = _note_metadata(note, config)
        if metadata is None:
            continue
        mapper_notes += 1
        try:
            linked = link_assessment(package_data, metadata["body"].encode("utf-8"))
        except (ContractError, ValueError):
            continue
        linked.pop("sha256", None)
        linked["change_mapper"]["gitlab_note"] = {
            key: metadata[key]
            for key in ("note_id", "author_id", "confidential", "configured_flow_id", "created_at")
        }
        linked["change_mapper"]["gitlab_note"]["flow_identity"] = "configured_not_attested_by_notes_api"
        linked["sha256"] = hashlib.sha256(_canonical_bytes(linked)).hexdigest()
        candidates.append((metadata["created_at"], metadata["note_id"], linked))

    package = _decode_json(package_data, "review package")
    change = package.get("change", {}) if isinstance(package, dict) else {}
    if not candidates:
        reason = "no_internal_mapper_note" if mapper_notes == 0 else "no_valid_assessment_for_package_head"
        return ({
            "schema_version": "tbaf.assessment-link-status/v1",
            "status": "not_found",
            "project": change.get("project"),
            "mr_iid": change.get("mr_iid"),
            "head_sha": change.get("head_sha"),
            "mapper_notes_seen": mapper_notes,
            "reason": reason,
        }, None)

    _, _, linked = max(candidates, key=lambda item: (item[0], item[1]))
    return ({
        "schema_version": "tbaf.assessment-link-status/v1",
        "status": "linked",
        "project": change.get("project"),
        "mr_iid": change.get("mr_iid"),
        "head_sha": change.get("head_sha"),
        "mapper_notes_seen": mapper_notes,
        "candidate_observation_count": len(linked["change_mapper"]["observations"]),
        "gitlab_note_id": linked["change_mapper"]["gitlab_note"]["note_id"],
    }, linked)


def _write_json(path: Path, value: dict[str, Any]) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="tbaf-link-gitlab-assessment",
        description="Link the approved internal Duo note for the exact MR head to its CI Review Package.",
    )
    parser.add_argument("review_package", help="snapshot job artifact path")
    parser.add_argument("integration_config", help="trusted project/flow identity config from default branch")
    parser.add_argument("output_dir", help="directory for link status and optional linked artifact")
    args = parser.parse_args(argv)
    output_dir = Path(args.output_dir)
    try:
        project_id = _required_env("CI_PROJECT_ID", 32)
        mr_iid = _required_env("TBAF_MR_IID", 9)
        if not _INTEGER_RE.fullmatch(project_id) or not _INTEGER_RE.fullmatch(mr_iid):
            raise ContractError("CI_PROJECT_ID and TBAF_MR_IID must be positive decimal integers")
        config = _load_config(args.integration_config, project_id)
        package_path = Path(args.review_package)
        if package_path.is_symlink() or not package_path.is_file():
            raise ContractError("review package path must be a regular non-symlink file")
        with package_path.open("rb") as stream:
            package_data = stream.read(_MAX_RESPONSE_BYTES + 1)
        if len(package_data) > _MAX_RESPONSE_BYTES:
            raise ContractError("review package exceeds the 2 MB limit")
        package = _decode_json(package_data, "review package")
        change = package.get("change") if isinstance(package, dict) else None
        if (not isinstance(change, dict) or str(change.get("mr_iid")) != mr_iid
                or str(change.get("project")) != _required_env("CI_PROJECT_PATH", 255)):
            raise ContractError("snapshot artifact identity does not match this CI project and MR IID")
        endpoint = _notes_endpoint(
            _required_env("CI_API_V4_URL", 2048),
            _required_env("CI_SERVER_URL", 2048),
            project_id,
            mr_iid,
        )
        notes = _fetch_notes(endpoint, _required_env("CI_JOB_TOKEN"))
        status, linked = link_latest_assessment(package_data, notes, config)
    except (OSError, ContractError, ValueError) as exc:
        status = {
            "schema_version": "tbaf.assessment-link-status/v1",
            "status": "unavailable",
            "reason": str(exc),
        }
        linked = None

    try:
        output_dir.mkdir(parents=True, exist_ok=True)
        _write_json(output_dir / "assessment-link-status.json", status)
        linked_path = output_dir / "linked-review-package.json"
        if linked is not None:
            _write_json(linked_path, linked)
        elif linked_path.exists() and not linked_path.is_symlink():
            linked_path.unlink()
    except OSError as exc:
        print(f"tbaf-link-gitlab-assessment: output failed: {exc}", file=sys.stderr)
        return 2

    print(json.dumps(status, ensure_ascii=False, sort_keys=True))
    if status["status"] != "linked":
        print("tbaf-link-gitlab-assessment: assessment link is unavailable; deterministic package remains unchanged", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
