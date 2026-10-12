# GitLab SAST evidence in Review Packages

Snapshot packages use `tbaf.review-package/v3` when they include the optional
`tbaf.sast-evidence/v1` section. The viewer and linker continue to accept
historical `tbaf.review-package/v2` packages.

## Capture and binding

The default-branch snapshot job reads GitLab's public read-only Pipelines and
Jobs APIs for the exact MR ref and current head SHA. It accepts a report only
when the pipeline is a successful `merge_request_event` for
`refs/merge-requests/<iid>/head`, the pipeline SHA matches the snapshot head,
the `semgrep-sast` job succeeded in that pipeline, and the job metadata reports
the same commit SHA. It then downloads `gl-sast-report.json` from that job ID.
The MR head is checked again after capture; if it moved, the whole snapshot is
rejected and should be rerun.

The APIs are queried without a token because CI job tokens do not generally
have permission to list pipelines and jobs. If the project does not expose this
read-only metadata or artifact publicly, the Review Package records SAST as
unavailable. The snapshot job never receives a broader token for this feature.

## What the package records

The report parser is bounded to 2 MB and 20,000 reported findings. It displays
at most 500 findings located in changed paths. Findings in unchanged paths are
counted separately and are not attributed to the MR. If the display cap is
reached, the evidence status is `partial` and the omitted count is explicit.
Invalid reports, missing exact-head pipelines, missing jobs, and inaccessible
artifacts produce an `unavailable` status with a stable reason code.

Each displayed item contains the scanner finding name, severity, repository
path, line range, and up to 20 scanner identifiers. The package binds the data
to the GitLab pipeline and job metadata, and its SHA-256 digest covers the
SAST section.

## Limits

SAST evidence is a separate advisory section. It does not create policy checks,
clear claims, or change the deterministic attention route. A finding is a
scanner report, not a confirmed vulnerability. An empty report is not proof of
security or complete scanner coverage.

The MR controls its CI configuration, so a successful MR pipeline can alter or
omit scanner behavior. GitLab pipeline/job metadata and the report are not a
cryptographic attestation of the scanner configuration or execution. The
Review Package does not claim otherwise. SAST remains non-blocking in this
project; merge and deployment decisions remain outside the package.

The live result that motivated this feature is documented in
[`live-sast-2026-10-10.md`](live-sast-2026-10-10.md).
