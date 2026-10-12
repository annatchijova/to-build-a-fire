"""Collect bounded, exact-head GitLab SAST evidence without changing routing."""

from __future__ import annotations

import hashlib
import json
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode, urlsplit
from urllib.request import Request, build_opener

from .contract import ContractError, _decode_json

_MAX_REPORT_BYTES = 2_000_000
_MAX_PIPELINES = 100
_MAX_JOBS = 100
_MAX_FINDINGS = 500
_SEVERITIES = {"Info", "Unknown", "Low", "Medium", "High", "Critical"}


def _unavailable(reason: str) -> dict[str, Any]:
    return {
        "schema_version": "tbaf.sast-evidence/v1",
        "status": "unavailable",
        "reason_code": reason,
        "source": None,
        "scanner": None,
        "findings": [],
        "reported_finding_count": 0,
        "unchanged_path_finding_count": 0,
        "omitted_finding_count": 0,
    }


def _get(url: str, *, maximum: int = _MAX_REPORT_BYTES) -> bytes | None:
    request = Request(url, headers={"Accept": "application/json", "User-Agent": "tbaf-sast-evidence/1"})
    try:
        with build_opener().open(request, timeout=15) as response:
            body = response.read(maximum + 1)
    except (HTTPError, URLError, TimeoutError, OSError):
        return None
    if len(body) > maximum:
        raise ContractError("GitLab SAST response exceeds the configured size limit")
    return body


def _object(value: Any) -> dict[str, Any] | None:
    return value if isinstance(value, dict) else None


def _positive_int(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value > 0


def _normal_path(value: Any) -> str | None:
    if not isinstance(value, str) or not value or len(value) > 1024 or "\x00" in value:
        return None
    parts = value.split("/")
    if value.startswith("/") or "\\" in value or any(part in {"", ".", ".."} for part in parts):
        return None
    return value


def _reported_string(value: Any, default: str, maximum: int) -> str:
    if not isinstance(value, str) or not value.strip() or len(value) > maximum or "\x00" in value:
        return default
    return value


def _validated_api_root(api_root: str, server_url: str) -> str | None:
    api, server = urlsplit(api_root), urlsplit(server_url)
    if (api.scheme != "https" or not api.netloc or api.username or api.password or api.query or api.fragment
            or not api.path.rstrip("/").endswith("/api/v4") or server.scheme != "https"
            or api.netloc.lower() != server.netloc.lower()):
        return None
    return api_root.rstrip("/")


def _normalize_report(
    report_data: bytes,
    *,
    changed_paths: set[str],
    source: dict[str, Any],
) -> dict[str, Any]:
    report = _decode_json(report_data, "GitLab SAST report")
    report_obj = _object(report)
    scan = _object(report_obj.get("scan")) if report_obj else None
    scanner = _object(scan.get("scanner")) if scan else None
    analyzer = _object(scan.get("analyzer")) if scan else None
    raw_findings = report_obj.get("vulnerabilities") if report_obj else None
    if (not report_obj or scan is None or scan.get("status") != "success"
            or scanner is None or analyzer is None or not isinstance(raw_findings, list)
            or len(raw_findings) > 20_000):
        raise ContractError("GitLab SAST report does not match the supported successful report shape")

    normalized: list[dict[str, Any]] = []
    unchanged_path_count = 0
    for raw in raw_findings:
        vulnerability = _object(raw)
        location = _object(vulnerability.get("location")) if vulnerability else None
        path = _normal_path(location.get("file")) if location else None
        if path is None:
            raise ContractError("GitLab SAST report contains an invalid file path")
        if path not in changed_paths:
            unchanged_path_count += 1
            continue
        start = location.get("start_line")
        end = location.get("end_line", start)
        if not _positive_int(start) or not _positive_int(end) or end < start:
            raise ContractError("GitLab SAST report contains an invalid source line range")
        name = _reported_string(vulnerability.get("name"), "Unnamed scanner finding", 512)
        severity = vulnerability.get("severity")
        if severity not in _SEVERITIES:
            severity = "Unknown"
        raw_identifiers = vulnerability.get("identifiers", [])
        if not isinstance(raw_identifiers, list):
            raw_identifiers = []
        identifiers = []
        for item in raw_identifiers[:20]:
            identifier = _object(item)
            if identifier is None:
                continue
            kind = _reported_string(identifier.get("type"), "unknown", 64)
            value = _reported_string(identifier.get("value"), "unknown", 256)
            identifiers.append({"type": kind, "value": value})
        fingerprint_data = json.dumps(
            {"name": name, "severity": severity, "path": path, "start_line": start,
             "end_line": end, "identifiers": identifiers},
            ensure_ascii=False, sort_keys=True, separators=(",", ":"),
        ).encode("utf-8")
        normalized.append({
            "finding_id": hashlib.sha256(fingerprint_data).hexdigest(),
            "name": name,
            "severity": severity,
            "path": path,
            "start_line": start,
            "end_line": end,
            "identifiers": identifiers,
        })

    normalized.sort(key=lambda item: (
        item["path"], item["start_line"], item["end_line"], item["severity"], item["finding_id"],
    ))
    omitted = max(0, len(normalized) - _MAX_FINDINGS)
    retained = normalized[:_MAX_FINDINGS]
    status = "partial" if omitted else "available" if retained else "no_findings"
    scanner_data = {
        "name": _reported_string(scanner.get("name"), "Unknown scanner", 128),
        "version": _reported_string(scanner.get("version"), "unknown", 128),
        "analyzer": _reported_string(analyzer.get("name"), "Unknown analyzer", 128),
        "analyzer_version": _reported_string(analyzer.get("version"), "unknown", 128),
    }
    return {
        "schema_version": "tbaf.sast-evidence/v1",
        "status": status,
        "reason_code": None,
        "source": source,
        "scanner": scanner_data,
        "findings": retained,
        "reported_finding_count": len(raw_findings),
        "unchanged_path_finding_count": unchanged_path_count,
        "omitted_finding_count": omitted,
    }


def collect_sast_evidence(
    api_root: str,
    server_url: str,
    project_id: str,
    mr_iid: int,
    head_sha: str,
    changed_paths: list[str],
) -> dict[str, Any]:
    """Load only a successful SAST job whose pipeline and job metadata match the MR head."""
    root = _validated_api_root(api_root, server_url)
    if root is None:
        return _unavailable("gitlab_api_unavailable")
    ref = f"refs/merge-requests/{mr_iid}/head"
    base = f"{root}/projects/{quote(project_id, safe='')}"
    query = urlencode({"ref": ref, "sha": head_sha, "source": "merge_request_event", "status": "success", "per_page": _MAX_PIPELINES})
    try:
        pipeline_bytes = _get(f"{base}/pipelines?{query}")
    except ContractError:
        return _unavailable("pipeline_metadata_invalid")
    if pipeline_bytes is None:
        return _unavailable("pipeline_metadata_unavailable")
    try:
        pipelines = _decode_json(pipeline_bytes, "GitLab SAST pipeline list")
    except ContractError:
        return _unavailable("pipeline_metadata_invalid")
    if not isinstance(pipelines, list) or len(pipelines) > _MAX_PIPELINES:
        return _unavailable("pipeline_metadata_invalid")

    exact_pipelines = [item for item in pipelines if isinstance(item, dict)
                       and item.get("sha") == head_sha and item.get("ref") == ref
                       and item.get("source") == "merge_request_event" and item.get("status") == "success"
                       and _positive_int(item.get("id"))]
    exact_pipelines.sort(key=lambda item: item["id"], reverse=True)
    for pipeline in exact_pipelines[:1]:
        if pipeline.get("project_id") is not None and str(pipeline.get("project_id")) != str(project_id):
            continue
        try:
            jobs_data = _get(f"{base}/pipelines/{pipeline['id']}/jobs?per_page={_MAX_JOBS}")
        except ContractError:
            continue
        if jobs_data is None:
            continue
        try:
            jobs = _decode_json(jobs_data, "GitLab pipeline jobs")
        except ContractError:
            continue
        if not isinstance(jobs, list) or len(jobs) > _MAX_JOBS:
            continue
        sast_jobs = [job for job in jobs if isinstance(job, dict) and job.get("name") == "semgrep-sast"
                     and job.get("status") == "success" and _positive_int(job.get("id"))
                     and isinstance(job.get("pipeline"), dict)
                     and job["pipeline"].get("id") == pipeline["id"]
                     and isinstance(job.get("commit"), dict)
                     and job["commit"].get("id") == head_sha]
        if not sast_jobs:
            continue
        sast_jobs.sort(key=lambda job: job["id"], reverse=True)
        job = sast_jobs[0]
        try:
            report_data = _get(f"{base}/jobs/{job['id']}/artifacts/gl-sast-report.json")
        except ContractError:
            return _unavailable("sast_report_invalid")
        if report_data is None:
            continue
        source = {
            "pipeline_id": pipeline["id"],
            "job_id": job["id"],
            "ref": ref,
            "head_sha": head_sha,
            "binding": "gitlab_pipeline_and_job_metadata",
        }
        try:
            return _normalize_report(report_data, changed_paths=set(changed_paths), source=source)
        except ContractError:
            return _unavailable("sast_report_invalid")
    if not exact_pipelines:
        return _unavailable("no_successful_sast_pipeline_for_head")
    return _unavailable("sast_job_or_artifact_unavailable")
