"""Rebuild an MR Review Package outside CI from public GitLab data.

This runs the same code as the `attention-router-mr-snapshot` job, but reads the
public merge-request endpoint without a job token. It works only for a public
project and an open MR. Run it from a clone whose `origin` is the GitLab
project, with `HEAD` at the policy revision to evaluate:

    python scripts/reproduce_public_mr_snapshot.py 2 > review-package.json

The result is a locally reproduced artifact, not a CI artifact: no pipeline
attests where or by whom it was produced.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlsplit
from urllib.request import HTTPRedirectHandler, HTTPSHandler, Request, build_opener

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from tbaf import gitlab_mr_snapshot as snapshot  # noqa: E402
from tbaf.contract import ContractError  # noqa: E402

PROJECT_PATH = "gitlab-ai-hackathon/transcend-october-2026/1688368/showcase"
PROJECT_ID = "87290826"
SERVER_URL = "https://gitlab.com"


def _public_mr(api_root: str, project_id: str, mr_iid: str, _job_token: str) -> dict:
    parts = urlsplit(api_root)
    if (
        parts.scheme != "https"
        or parts.hostname != "gitlab.com"
        or parts.port is not None
        or parts.username is not None
        or parts.password is not None
        or parts.path.rstrip("/") != "/api/v4"
        or parts.query
        or parts.fragment
        or project_id != PROJECT_ID
        or re.fullmatch(r"[1-9][0-9]{0,8}", mr_iid) is None
    ):
        raise ContractError("public snapshot requests are restricted to this GitLab project API")

    request = Request(
        f"{api_root.rstrip('/')}/projects/{quote(project_id, safe='')}/merge_requests/{mr_iid}",
        headers={"Accept": "application/json"},
    )
    class RejectRedirects(HTTPRedirectHandler):
        def redirect_request(self, req, fp, code, msg, headers, new_url):
            return None

    try:
        opener = build_opener(HTTPSHandler(), RejectRedirects())
        with opener.open(request, timeout=20) as response:
            payload = response.read(2_000_001)
    except (HTTPError, URLError, TimeoutError, OSError) as exc:
        raise ContractError("GitLab did not return the requested public merge request") from exc
    if len(payload) > 2_000_000:
        raise ContractError("GitLab merge-request response exceeds the 2 MB limit")
    value = json.loads(payload.decode("utf-8", "strict"))
    if not isinstance(value, dict):
        raise ContractError("GitLab merge-request response must be an object")
    return value


def main() -> int:
    if len(sys.argv) != 2:
        print("usage: reproduce_public_mr_snapshot.py MR_IID", file=sys.stderr)
        return 2
    head = subprocess.run(
        ["git", "rev-parse", "HEAD"], check=True, capture_output=True, text=True,
    ).stdout.strip()
    os.environ.update({
        "CI_PROJECT_PATH": PROJECT_PATH,
        "CI_PROJECT_ID": PROJECT_ID,
        "CI_SERVER_URL": SERVER_URL,
        "CI_API_V4_URL": f"{SERVER_URL}/api/v4",
        "CI_JOB_TOKEN": "unused-public-read",
        "CI_COMMIT_SHA": head,
    })
    snapshot._api_json = _public_mr
    try:
        artifact = snapshot.create_snapshot(sys.argv[1])
    except (ContractError, ValueError) as exc:
        print(f"reproduce_public_mr_snapshot: rejected: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(artifact, ensure_ascii=False, sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
