# Generated artifacts: the route matrix

Diff size is a poor guide to review effort. This repository shows that with one
of its own files.

## What is generated

[`evaluation/generated/route-matrix.json`](../evaluation/generated/route-matrix.json)
is a decision table for the deterministic router. For every combination
selected by [`evaluation/route-matrix-spec.json`](../evaluation/route-matrix-spec.json)
(consequence, review route, check state, candidate observation, and changed
paths), it records the route, the claim state, the reasons, and the demand.
The current spec selects 504 cases, about 10,000 lines.

Regenerate it after changing the spec or the router:

```sh
PYTHONPATH=src python -m tbaf.route_matrix evaluation/route-matrix-spec.json > evaluation/generated/route-matrix.json
```

`tests/test_generated_artifacts.py` fails if the committed table differs from
the generator output.

## Claim and check

The policy claim `generated-artifacts` covers the spec and the table. Its
required check, `generated-artifacts-reproducible`, runs in the
`attention-router-mr-snapshot` job when either path changes:

1. It reads the spec and the table from the MR head as Git data.
2. It runs the default-branch generator on that spec. Nothing from the MR is
   executed.
3. It compares the result with the committed table, byte for byte.

| Result | Meaning | Route effect |
| --- | --- | --- |
| `PASS` | The table is exactly what the trusted generator produces from the MR's spec | Claim `SUPPORTED`; with no other open claims the MR is `COVERED_BY_EVIDENCE` |
| `FAIL` | The table differs; `details` names the first differing line | Claim `UNRESOLVED`, `TARGETED_REVIEW` |
| `NOT_RUN` | The spec is invalid, or a file is missing or over its size limit | Claim `UNRESOLVED`, `TARGETED_REVIEW` |

**Limits.** A pass shows reproducibility only. It does not judge whether the
spec change was a good idea; the claim is marked low consequence for that
reason. If an MR also changes the router or any other unmapped path, that path
routes to `DEEP_REVIEW` as usual. If the router changes on the default branch,
the committed table must be regenerated, or the check will fail for every MR
that touches the table.

## Seeded controls

Two branches, based on the commit that introduced the check, exercise both
outcomes:

| Branch | Change | Expected result |
| --- | --- | --- |
| `seed/route-matrix-large-diff` | Adds `high` to the spec's consequences and regenerates the table: 2 files, +5,042 / −3 lines | Check `PASS`, `COVERED_BY_EVIDENCE`, 0 minutes of known demand |
| `seed/route-matrix-hand-edit` | Edits one route inside the table by hand: 1 file, +1 / −1 line | Check `FAIL` at line 5395, `TARGETED_REVIEW`, 10 minutes |

Both results were reproduced locally on 2026-10-23 with the snapshot's own
functions (changed-path listing, check, policy from the base commit, and
router) against the real Git objects. That local run used no GitLab API and is
not a CI artifact.

To produce CI evidence, after this change is on the GitLab default branch:

1. Push both branches to the GitLab project. Open an MR for each against `main`
   and label both as seeded controls. Do not merge them: the snapshot only
   reads open MRs.
2. Run the snapshot for each MR IID:
   `glab ci run --branch main --input 'mr_iid:<iid>'`.
3. Download `artifacts/review-package.json` from each run, keep a copy in
   [`evidence/`](evidence/), and record the pipeline and SHA here.

Together with MR !2 (two changed lines, `TARGETED_REVIEW`, 35 minutes), these
show the contrast in the [README](../README.md#a-useful-distinction): routing
follows claims and evidence, not line counts.
