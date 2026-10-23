# Reproduced and deployment evidence — 2026-10-23

This record covers two things checked against public GitLab data on
2026-10-23: a local rebuild of the MR !2 Review Package, and the first Cloud Run
deployment attempt.

## Why the MR !2 package was rebuilt

The snapshot and assessment-link jobs kept their artifacts for one week. The
artifacts behind the earlier records are no longer downloadable, including
pipeline [#2935454761](https://gitlab.com/gitlab-ai-hackathon/transcend-october-2026/1688368/showcase/-/pipelines/2935454761)
and snapshot pipeline [#2932600822](https://gitlab.com/gitlab-ai-hackathon/transcend-october-2026/1688368/showcase/-/pipelines/2932600822).
Their job logs require sign-in. The CI configuration now keeps these artifacts
for one year; earlier artifacts cannot be restored.

## Reproduced MR !2 Review Package

- **File:** [`evidence/mr2-review-package-2026-10-23.json`](evidence/mr2-review-package-2026-10-23.json).
- **Command:** `python scripts/reproduce_public_mr_snapshot.py 2`, run from a
  clone of the GitLab project at `main` commit
  `21f422b8e8bbb2d61b9fade510c63e5b49b8675b`.
- **Method:** the same `create_snapshot` code as the CI job. The only
  difference is that MR metadata comes from the public API without a job token.
  Two consecutive runs produced byte-identical output.
- **Input MR:** [!2 — Seeded authorization boundary control (do not merge)](https://gitlab.com/gitlab-ai-hackathon/transcend-october-2026/1688368/showcase/-/merge_requests/2), still open.
- **Policy:** `examples/policy.json` at the commit above, digest
  `49cc222d887b249ceae3da8083407af4c918182cb0f74cabb3a46e3d635518e4`.

| Field | Value |
| --- | --- |
| `schema_version` | `tbaf.review-package/v3` |
| `change.base_sha` | `2a9e7f9b82b90d7d6a97bd9f24aa7db878c763f6` |
| `change.head_sha` | `e843e0d8128f5c6363d47e6272850fb709e4badc` |
| `change.paths` | `src/auth.py` |
| `authorization-invariants` | `FAIL` (`authenticated_non_owner_denied` violated) |
| Claim `authorization-boundary` | `UNRESOLVED`, consequence `critical` |
| Attention route | `TARGETED_REVIEW`, reason `required_check_fail:authorization-invariants` |
| Schedule | `WITHIN_CAPACITY`, 90-minute capacity, 35-minute known demand |
| SAST evidence | `unavailable`, reason `sast_job_or_artifact_unavailable` |
| Package digest | `a1cf033f892eebe6fc6c459d1626e7d3572e263892e465039ac70509a71531b9` |

The route, check result, claim state and schedule match the result reported for
snapshot pipeline #2932600822 in [`live-evidence-2026-10-09.md`](live-evidence-2026-10-09.md).
SAST is unavailable here because no retrievable SAST report is tied to this MR
head; the package records that instead of reporting a clean scan.

**Limits.** This is a locally reproduced artifact, not a CI artifact. No
pipeline attests where it was produced. It contains no Duo candidate
observations: the linked assessment is a confidential note and was not read.
A fresh CI run (`glab ci run --branch main --input 'mr_iid:2'`) produces the
attested equivalent.

## First Cloud Run deployment

- **Pipeline:** [#2979674219](https://gitlab.com/gitlab-ai-hackathon/transcend-october-2026/1688368/showcase/-/pipelines/2979674219) on `main` at `5ac8c9342c8876be4bb92ef2b1e8fa68a6273b6b`.
- **Deploy job:** `deploy-cloud-run-review-explorer`. The first attempt failed;
  the retry (job 17405524347) succeeded.
- **Deployment artifact:** revision `tbaf-review-explorer-00001-6cs`, URL
  `https://tbaf-review-explorer-zxmd2hmaaa-uc.a.run.app`, source SHA
  `5ac8c9342c8876be4bb92ef2b1e8fa68a6273b6b`.
- **Health check:** job 17405402516 failed. `GET /healthz` returned HTTP 404
  because Cloud Run reserves some paths ending in `z`. MR !29 moved the
  endpoint to `/health`. That change is on `main`
  (`21f422b8e8bbb2d61b9fade510c63e5b49b8675b`) but has not been deployed.

**Still to do:** run the manual deploy and health jobs on the current `main`
pipeline, then record the revision and the health artifact. Until the health
job passes, the service is deployed but its health is unverified.
