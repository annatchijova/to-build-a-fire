# Live GitLab evidence — Duo assessment v2 link — 2026-10-11

This record captures the project owner's terminal output for the second
end-to-end assessment-link run on MR !2. It records one successful run and is
not a quality, security, or productivity benchmark.

## Provenance

- **Source:** project owner report of the GitLab Duo session, pipeline, and JSON artifact.
- **Merge request:** [!2 — Seeded authorization boundary control](https://gitlab.com/gitlab-ai-hackathon/transcend-october-2026/1688368/showcase/-/merge_requests/2).
- **Package head SHA:** `e843e0d8128f5c6363d47e6272850fb709e4badc`.
- **Duo session:** `9294299`; the owner reported that it reached human approval, finished, and posted an internal note.
- **Assessment note:** [internal note 3992319519](https://gitlab.com/gitlab-ai-hackathon/transcend-october-2026/1688368/showcase/-/merge_requests/2#note_3992319519).
- **Link pipeline:** [#2935454761](https://gitlab.com/gitlab-ai-hackathon/transcend-october-2026/1688368/showcase/-/pipelines/2935454761), run on `main` with input `mr_iid:2`.
- **Link job:** [17091419381 — `attention-router-link-duo-assessment`](https://gitlab.com/gitlab-ai-hackathon/transcend-october-2026/1688368/showcase/-/jobs/17091419381).

## Assessment evidence

The session trace reported `tbaf.duo-assessment/v2` for project
`gitlab-ai-hackathon/transcend-october-2026/1688368/showcase`, MR IID `2`, and
the exact package head above. It reported `diff_coverage.status: complete`,
with empty `paths` and `limitations`. The response contained two candidate
observations: one with `impact: affected` for the authorization surface and one
with `impact: unknown` for module reachability. Both revisions matched the MR
head. The owner approved the human-input checkpoint; the flow then posted the
internal note and finished.

## Link artifact result

The owner retrieved the JSON file directly from job `17091419381` using the
GitLab Jobs Artifacts API. The reported fields were:

| Field | Reported value |
| --- | --- |
| `status` | `linked` |
| `schema_version` | `tbaf.assessment-link-status/v2` |
| `project` | `gitlab-ai-hackathon/transcend-october-2026/1688368/showcase` |
| `mr_iid` | `2` |
| `head_sha` | `e843e0d8128f5c6363d47e6272850fb709e4badc` |
| `gitlab_note_id` | `3992319519` |
| `candidate_observation_count` | `2` |
| `mapper_notes_seen` | `3` |
| `diff_coverage_status` | `complete` |

An earlier session, `9293620`, ended before any flow component emitted an event.
The next trigger produced session `9294299`, which completed through the human
checkpoint. This documents the observed sequence; it does not establish the
underlying cause of the earlier no-output session.

This is one observed exact-head link. It does not establish a population-level
error rate or review-time reduction. As documented in
[`duo-assessment-link.md`](duo-assessment-link.md), the Notes API does not
independently attest flow identity or authenticate the agent's claimed source.
The mapper-reported coverage value is metadata and does not alter the
deterministic Review Package or route.
