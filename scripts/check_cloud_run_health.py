"""Check the deployed Review Explorer's public health endpoint."""

from __future__ import annotations

import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, request, file_pointer, code, message, headers, url):
        return None


def main() -> int:
    base_url = os.environ.get("CLOUD_RUN_URL", "").strip()
    revision = os.environ.get("CLOUD_RUN_REVISION", "").strip()
    source_sha = os.environ.get("DEPLOYED_SOURCE_SHA", "").strip()
    output = Path("artifacts/cloud-run-health.json")
    output.parent.mkdir(parents=True, exist_ok=True)

    try:
        parsed = urlsplit(base_url)
        valid_url = (
            parsed.scheme == "https"
            and bool(parsed.hostname)
            and parsed.hostname.endswith(".run.app")
            and parsed.username is None
            and parsed.password is None
            and parsed.port is None
            and parsed.path in ("", "/")
            and not parsed.query
            and not parsed.fragment
        )
    except ValueError:
        valid_url = False
    valid_sha = re.fullmatch(r"[0-9a-f]{40}", source_sha) is not None

    result: dict[str, object] = {
        "schema_version": "tbaf.cloud-run-health/v1",
        "status": "failed",
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "url": f"{base_url.rstrip('/')}/healthz" if base_url else None,
        "revision": revision or None,
        "source_sha": source_sha or None,
        "http_status": None,
        "response_matches": False,
    }

    if not valid_url or not revision or not valid_sha:
        result["reason"] = "missing_or_invalid_deployment_metadata"
        output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
        print("Cloud Run health check failed: deployment metadata is missing or invalid.")
        return 1

    request = Request(
        f"{base_url.rstrip('/')}/healthz",
        headers={"Accept": "text/plain"},
        method="GET",
    )
    try:
        with build_opener(_NoRedirect()).open(request, timeout=10) as response:
            status = response.status
            body = response.read(64)
            oversized = response.read(1) != b""
    except HTTPError as error:
        status = error.code
        body = b""
        oversized = False
    except (URLError, TimeoutError, OSError) as error:
        result["reason"] = f"request_failed:{type(error).__name__}"
        output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
        print(f"Cloud Run health check failed: request error ({type(error).__name__}).")
        return 1

    matches = status == 200 and body == b"ok\n" and not oversized
    result["http_status"] = status
    result["response_matches"] = matches
    if matches:
        result["status"] = "healthy"
    else:
        result["reason"] = "unexpected_http_status_or_response"

    output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    if not matches:
        print(f"Cloud Run health check failed: HTTP {status}, expected HTTP 200 and body 'ok'.")
        return 1

    print(f"Cloud Run health check passed: HTTP 200; revision {revision}; source {source_sha}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
