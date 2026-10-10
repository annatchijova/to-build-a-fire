"""Build a read-only Review Package for one GitLab MR from a default-branch CI job.

Protect the default branch before treating its policy as trusted. This reads MR
metadata through CI_JOB_TOKEN and treats the fetched merge-request ref as data:
it never checks out or executes code from that ref.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import selectors
import subprocess
import sys
import time
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener

from .auth_invariants import MAX_SOURCE_BYTES, build_authorization_check
from .contract import ContractError, parse_input
from .router import build_artifact

_SHA_RE = re.compile(r"\A(?:[0-9a-f]{40}|[0-9a-f]{64})\Z")
_INTEGER_RE = re.compile(r"\A[1-9][0-9]{0,8}\Z")
_MAX_RESPONSE_BYTES = 2_000_000
_MAX_CHANGED_PATH_BYTES = 2_000_000
_MAX_CHANGED_PATHS = 2_000


def _required_env(name: str, *, maximum: int = 512) -> str:
    value = os.environ.get(name, "")
    if not value or len(value) > maximum or "\x00" in value:
        raise ContractError(f"required CI variable {name} is missing or malformed")
    return value


def _git(args: list[str], *, maximum_output: int = _MAX_RESPONSE_BYTES) -> bytes:
    env = os.environ.copy()
    env.update({
        "GIT_CONFIG_NOSYSTEM": "1",
        "GIT_CONFIG_GLOBAL": os.devnull,
        "GIT_TERMINAL_PROMPT": "0",
        "GIT_NO_REPLACE_OBJECTS": "1",
        "GIT_OPTIONAL_LOCKS": "0",
    })
    try:
        process = subprocess.Popen(
            ["git", *args], stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
            env=env, bufsize=0,
        )
    except OSError as exc:
        raise ContractError("Git metadata command could not start") from exc
    if process.stdout is None:
        process.kill()
        process.wait()
        raise ContractError("Git metadata output could not be read")
    output = bytearray()
    deadline = time.monotonic() + 60
    try:
        with selectors.DefaultSelector() as selector:
            selector.register(process.stdout, selectors.EVENT_READ)
            while True:
                remaining = deadline - time.monotonic()
                if remaining <= 0 or not selector.select(remaining):
                    raise ContractError("Git metadata command timed out")
                chunk = os.read(
                    process.stdout.fileno(),
                    min(65_536, maximum_output - len(output) + 1),
                )
                if not chunk:
                    break
                output.extend(chunk)
                if len(output) > maximum_output:
                    raise ContractError("Git metadata output exceeds the configured size limit")
        if process.wait(timeout=max(0, deadline - time.monotonic())) != 0:
            raise ContractError("Git metadata command could not resolve the requested revision")
    except (OSError, subprocess.TimeoutExpired) as exc:
        process.kill()
        process.wait()
        raise ContractError("Git metadata command failed or timed out") from exc
    except ContractError:
        process.kill()
        process.wait()
        raise
    finally:
        process.stdout.close()
    if process.returncode != 0:
        raise ContractError("Git metadata command could not resolve the requested revision")
    return bytes(output)


def _api_json(api_root: str, project_id: str, mr_iid: str, job_token: str) -> dict[str, Any]:
    parts = urlsplit(api_root)
    server_parts = urlsplit(_required_env("CI_SERVER_URL", maximum=2048))
    if (parts.scheme != "https" or not parts.netloc or parts.username or parts.password
            or parts.query or parts.fragment or not parts.path.rstrip("/").endswith("/api/v4")
            or server_parts.scheme != "https" or parts.netloc.lower() != server_parts.netloc.lower()):
        raise ContractError("CI_API_V4_URL must be an HTTPS GitLab API v4 URL")
    endpoint = f"{api_root.rstrip('/')}/projects/{quote(project_id, safe='')}/merge_requests/{mr_iid}"
    request = Request(endpoint, headers={"JOB-TOKEN": job_token, "Accept": "application/json"})

    class RejectRedirects(HTTPRedirectHandler):
        def redirect_request(self, req, fp, code, msg, headers, new_url):
            return None

    try:
        opener = build_opener(RejectRedirects())
        with opener.open(request, timeout=20) as response:
            payload = response.read(_MAX_RESPONSE_BYTES + 1)
    except (HTTPError, URLError, TimeoutError, OSError) as exc:
        raise ContractError("GitLab did not return the requested merge request") from exc
    if len(payload) > _MAX_RESPONSE_BYTES:
        raise ContractError("GitLab merge-request response exceeds the 2 MB limit")

    def unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                raise ContractError(f"duplicate key in GitLab response: {key}")
            result[key] = value
        return result

    try:
        value = json.loads(
            payload.decode("utf-8", "strict"),
            object_pairs_hook=unique_object,
            parse_constant=lambda token: (_ for _ in ()).throw(
                ContractError(f"invalid JSON number in GitLab response: {token}")
            ),
        )
    except (UnicodeDecodeError, json.JSONDecodeError, RecursionError) as exc:
        raise ContractError("GitLab returned invalid bounded JSON") from exc
    if not isinstance(value, dict):
        raise ContractError("GitLab merge-request response must be an object")
    return value


def _changed_paths(base_sha: str, head_sha: str) -> list[str]:
    raw = _git([
        "diff", "--no-ext-diff", "--no-renames", "--name-only", "-z",
        base_sha, head_sha, "--",
    ], maximum_output=_MAX_CHANGED_PATH_BYTES)
    if not raw:
        raise ContractError("the merge request diff contains no changed paths")
    try:
        paths = raw.decode("utf-8", "strict").split("\x00")
    except UnicodeDecodeError as exc:
        raise ContractError("a changed path is not valid UTF-8") from exc
    if paths[-1] == "":
        paths.pop()
    if not paths or len(paths) > _MAX_CHANGED_PATHS:
        raise ContractError("merge request must change between 1 and 2000 paths")
    if len(set(paths)) != len(paths):
        raise ContractError("Git returned duplicate changed paths")
    for path in paths:
        segments = path.split("/")
        if (not path or path.startswith("/") or "\\" in path
                or any(part in ("", ".", "..") for part in segments)
                or any(char in path for char in "*?[")):
            raise ContractError("Git returned a path outside the supported repository-path contract")
    return sorted(paths)


def create_snapshot(mr_iid: str) -> dict[str, Any]:
    if not _INTEGER_RE.fullmatch(mr_iid):
        raise ContractError("merge-request IID must be a positive decimal integer")

    project_path = _required_env("CI_PROJECT_PATH", maximum=255)
    project_id = _required_env("CI_PROJECT_ID", maximum=32)
    if not _INTEGER_RE.fullmatch(project_id):
        raise ContractError("CI_PROJECT_ID must be a positive decimal integer")
    api_root = _required_env("CI_API_V4_URL", maximum=2048)
    job_token = _required_env("CI_JOB_TOKEN", maximum=4096)
    policy_revision = _required_env("CI_COMMIT_SHA", maximum=64)
    if not _SHA_RE.fullmatch(policy_revision):
        raise ContractError("CI_COMMIT_SHA must be a lowercase Git object ID")

    mr = _api_json(api_root, project_id, mr_iid, job_token)
    response_iid = mr.get("iid")
    if (isinstance(response_iid, bool) or not isinstance(response_iid, int)
            or response_iid != int(mr_iid) or str(mr.get("project_id")) != project_id):
        raise ContractError("GitLab returned a different project or merge request")
    if mr.get("state") != "opened":
        raise ContractError("only an open merge request can be snapshotted")
    diff_refs = mr.get("diff_refs")
    if not isinstance(diff_refs, dict):
        raise ContractError("GitLab has not populated merge-request diff references yet")
    base_sha = diff_refs.get("base_sha")
    head_sha = diff_refs.get("head_sha")
    if not isinstance(base_sha, str) or not _SHA_RE.fullmatch(base_sha):
        raise ContractError("GitLab merge-request base SHA is missing or malformed")
    if not isinstance(head_sha, str) or not _SHA_RE.fullmatch(head_sha):
        raise ContractError("GitLab merge-request head SHA is missing or malformed")
    api_head_sha = mr.get("sha")
    if not isinstance(api_head_sha, str) or not _SHA_RE.fullmatch(api_head_sha):
        raise ContractError("GitLab merge-request SHA is missing or malformed")
    if api_head_sha != head_sha:
        raise ContractError("GitLab merge-request metadata is stale; retry after the diff refs refresh")

    # Fetch the MR ref as an object source, but never check out or execute its code.
    _git(["fetch", "--no-tags", "origin", f"refs/merge-requests/{mr_iid}/head"])
    fetched_head = _git(["rev-parse", "--verify", "FETCH_HEAD^{commit}"]).decode("ascii", "strict").strip()
    if fetched_head != head_sha:
        raise ContractError("the MR changed during capture; rerun against its current head")
    _git(["cat-file", "-e", f"{base_sha}^{{commit}}"])

    policy_data = _git(["show", f"{policy_revision}:examples/policy.json"])
    changed_paths = _changed_paths(base_sha, head_sha)
    checks: list[dict[str, Any]] = []
    if "src/auth.py" in changed_paths:
        try:
            auth_source = _git(["show", f"{head_sha}:src/auth.py"], maximum_output=MAX_SOURCE_BYTES)
        except ContractError:
            auth_source = None
        checks.append(build_authorization_check(auth_source, head_sha))

    review_input = {
        "schema_version": "tbaf.review-input/v1",
        "change": {
            "project": project_path,
            "mr_iid": int(mr_iid),
            "base_sha": base_sha,
            "head_sha": head_sha,
            "paths": changed_paths,
        },
        "observations": [],
        "checks": checks,
    }
    parsed = parse_input(json.dumps(review_input, ensure_ascii=False), policy_data)
    return build_artifact(parsed)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="tbaf-snapshot-mr",
        description="Create a read-only, revision-bound attention snapshot for one open GitLab MR.",
    )
    parser.add_argument("mr_iid", help="open MR IID in the current GitLab project")
    args = parser.parse_args(argv)
    try:
        artifact = create_snapshot(args.mr_iid)
    except (ContractError, ValueError) as exc:
        print(f"tbaf-snapshot-mr: rejected: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(artifact, ensure_ascii=False, sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
