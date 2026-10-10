# Live GitLab evidence — Duo assessment link — 2026-10-10

This record captures the project owner's terminal output for a live snapshot
and candidate-assessment link on MR !2. The artifact values below were reported
from `glab job artifact`; this documentation change did not independently fetch
the GitLab artifact.

## Provenance

- **Source:** project owner report of the `glab` command and JSON artifact.
- **Pipeline:** [#2934731933](https://gitlab.com/gitlab-ai-hackathon/transcend-october-2026/1688368/showcase/-/pipelines/2934731933), created on `main` with pipeline input `mr_iid:2`.
- **Merge request:** [!2 — Seeded authorization boundary control](https://gitlab.com/gitlab-ai-hackathon/transcend-october-2026/1688368/showcase/-/merge_requests/2).
- **Package head SHA:** `e843e0d8128f5c6363d47e6272850fb709e4badc`.
- **Linked internal note:** [note 3990952436](https://gitlab.com/gitlab-ai-hackathon/transcend-october-2026/1688368/showcase/-/merge_requests/2#note_3990952436).
- **Flow session:** `9290453`; the owner reported that it finished after approval and created the note.

## Link artifact result

| Field | Reported value |
| --- | --- |
| `status` | `linked` |
| `project` | `gitlab-ai-hackathon/transcend-october-2026/1688368/showcase` |
| `mr_iid` | `2` |
| `head_sha` | `e843e0d8128f5c6363d47e6272850fb709e4badc` |
| `gitlab_note_id` | `3990952436` |
| `candidate_observation_count` | `3` |
| `mapper_notes_seen` | `2` |

The earlier link attempt on this same head returned
`no_valid_assessment_for_package_head`: it found only the older internal note
for SHA `3a4fb86487d819a8589ec11770487ecf110313cb`. After the active flow was
updated to emit the structured `tbaf.duo-assessment/v1` block, session `9290453`
produced an approved note for the exact `e843e0d...` head and the linker returned
`linked`. This records one successful exact-head association; it does not
measure review-time reduction or establish repository-wide security.

The linker attaches candidate observations without recalculating the
deterministic package's route, claims, checks, or schedule. As documented in
[`duo-assessment-link.md`](duo-assessment-link.md), the GitLab Notes API does
not independently attest which flow created a note or authenticate the
agent's claimed source.
