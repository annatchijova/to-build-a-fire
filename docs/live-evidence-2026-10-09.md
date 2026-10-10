# Live GitLab evidence — 2026-10-09

This record captures the GitLab run reported by the project owner after MR !4
was merged. It records the artifact's result, not an independent re-fetch of
the artifact by this documentation change.

## Provenance

- **Source:** project owner report of GitLab pipeline and artifact output.
- **Main pipeline:** [#2932516900](https://gitlab.com/gitlab-ai-hackathon/transcend-october-2026/1688368/showcase/-/pipelines/2932516900), reported passed on `main` at commit prefix `28b44288` after merging MR !4.
- **Snapshot pipeline:** [#2932600822](https://gitlab.com/gitlab-ai-hackathon/transcend-october-2026/1688368/showcase/-/pipelines/2932600822).
- **Snapshot job:** [17075661487](https://gitlab.com/gitlab-ai-hackathon/transcend-october-2026/1688368/showcase/-/jobs/17075661487), `attention-router-mr-snapshot`; reported passed.
- **Input MR:** [!2 — Seeded authorization boundary control](https://gitlab.com/gitlab-ai-hackathon/transcend-october-2026/1688368/showcase/-/merge_requests/2).
- **Input head SHA:** `e843e0d8128f5c6363d47e6272850fb709e4badc`.
- **Changed path:** `src/auth.py`.
- **Temporary input:** `TBAF_MR_IID=2`; the owner reported deleting it with HTTP 204 and verifying it absent with HTTP 404.
- **Scope:** this is one seeded fixture, one MR head, one policy revision, and one GitLab run. The full `main` SHA and raw artifact bytes were not included in the report and remain unrecorded here.

## Reported Review Package result

| Field | Reported value |
| --- | --- |
| `change.head_sha` | `e843e0d8128f5c6363d47e6272850fb709e4badc` |
| `change.paths` | `src/auth.py` |
| `authorization-invariants` | `FAIL` |
| Claim `authorization-boundary` | `UNRESOLVED`, consequence `critical` |
| Claim reason | `required_check_fail:authorization-invariants` |
| Attention route | `TARGETED_REVIEW` |
| Attention reasons | `required_check_fail:authorization-invariants` |
| Schedule | `WITHIN_CAPACITY`, 90-minute capacity, 35-minute known demand |
| Task | `review:authorization-boundary`, 35 minutes, critical consequence |

The CI job and pipeline passed because the snapshot artifact was generated.
The bounded invariant result inside that artifact was `FAIL`. These states are
not contradictory: a green pipeline here means the check ran and recorded its
failure result; it does not mean the authorization claim passed or the change
is safe. The claim remains unresolved and routed to a human.

## Comparison with the earlier snapshot

The earlier snapshot of the same MR head reported
`required_check_missing:authorization-invariants`. After MR !4 added the
bounded check to the default-branch implementation, the subsequent snapshot
reported `required_check_fail:authorization-invariants`. The path, head SHA,
claim, and attention route stayed the same. This is consistent with the
expected transition from an unavailable check to a present check that detects
the seeded authenticated non-owner bypass.

This comparison is scoped to the reported artifacts. It does not establish
repository-wide authorization safety, import reachability, runtime behavior,
coverage outside the supported static subset, or review-time reduction.
Reopen this record if the raw artifact or full pipeline metadata contradicts
the reported values.
