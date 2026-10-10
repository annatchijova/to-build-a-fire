# Hackathon build contract — Path B, Assisted

**Event:** GitLab Transcend: Life After Code  
**Path:** Bring Your Own  
**Autonomy:** Assisted  
**Build window:** new automation and deployment work begins on or after 2026-10-05.  
**Cloud target:** Google Cloud Run, selected by the project owner for the optional Google Cloud track.

This document separates the product's maturity levels from hackathon lifecycle coverage. A maturity level is a complete, useful product state. The nine GitLab lifecycle stages are a coverage axis that the first connected end-to-end level must cross. They are not nine disconnected mini-projects.

## Intended end-to-end demonstration

1. A human opens or marks an MR ready in the public GitLab project.
2. A GitLab Duo Agent Platform flow starts in GitLab CI/CD, reads the MR and repository context, and produces candidate change observations. GitLab CI runs deterministic checks and scanners against the exact revision.
3. The flow presents its plan and consequential transitions for human approval. A rejection stops or returns the work for revision; it cannot silently continue to merge or deploy.
4. The deterministic policy and Attention Router produce a decision receipt that links the MR SHA, policy, bounded evidence, unresolved claims, human attention, capacity, and approvals.
5. After the required human merge/release approval, GitLab CI builds and deploys the approved revision to Cloud Run using short-lived OIDC federation rather than a stored service-account key.
6. A health check and declared runtime signals are attached to the deployment. A failure or regression reopens a linked work item and Attention Router assessment.
7. A reviewer can follow the public MR, flow/session, CI pipeline, decision receipt, release/deployment, and live service without relying on screenshots of simulated results.

The flow is Assisted only if human checkpoints and GitLab's protected merge/deployment gates are active in the live project and shown in the demo. A prompt asking the model to wait is not an approval control.

## Nine-stage coverage contract

| GitLab stage | Project action in the end-to-end path | Evidence shown in the demo | State |
| --- | --- | --- | --- |
| **Plan** | Duo maps the MR diff to protected claims and proposes an evidence/review plan. | Candidate output with provenance, paths and exact MR SHA; human approval checkpoint. | Flow exercised on MRs !1 and !2; approval and internal-note path observed |
| **Create** | Duo proposes a bounded repair or follow-up change as a separate, reviewable patch/MR. | Proposed diff; no direct merge; human approves whether to create/open it. | Planned |
| **Verify** | GitLab CI runs deterministic tests, contract/invariant checks and records skipped checks distinctly. | Visible job results and artifact references bound to the tested SHA. | Live CI observed; seeded authorization invariant reported `FAIL` while its job passed |
| **Package** | The router emits the versioned Review Package and human-attention receipt. | Downloadable, reproducible receipt linked to policy, evidence and candidate observations. | Live read-only MR snapshot inspected; see [`live-evidence-2026-10-09.md`](live-evidence-2026-10-09.md) |
| **Secure** | Security checks cover dependencies, secret exposure and relevant protected surfaces; Duo Falsifier suggests counterexamples as candidates. | Scanner artifacts, scope/limitations, and unresolved findings; no agent self-certification. | Planned |
| **Release** | CI creates a release/deployment candidate only after the required approvals and evidence gates. | Protected environment approval, approved source SHA, release record and actor. | Planned |
| **Configure** | Deployment config carries the approved revision and versioned runtime policy into Cloud Run. | Infrastructure/deployment files in the repo; OIDC identity and configuration tied to the release. | Planned |
| **Monitor** | A live health check and explicitly selected runtime signals watch the deployed revision. | Public service URL, health status and a controlled failure/regression demonstration. | Planned |
| **Govern** | Receipts join the flow, tool/check provenance, policy version, human approvals, release and monitor events. | Reviewer can reconstruct one end-to-end decision and see what was not established. | Local receipt partial; full chain pending |

Coverage counts only when the corresponding action runs in GitLab and leaves inspectable evidence. A diagram, prompt, local command, or configured-but-never-executed stage does not count as demonstrated coverage.

## Product maturity levels

### Level 1 — One change, end to end

One GitLab project and one MR complete the nine-stage path above, with an operable Attention Router, evidence bound to the exact revision, a real Duo flow, human checkpoints, CI/security results, an approval-gated Cloud Run deployment, and post-deploy health evidence. This is the hackathon target state.

**Done means:** a live, reproducible demonstration covers the full path; consequential uncertainty remains visible; merge/release/deploy gates are effective; the public repo contains runnable instructions and deployment code; the deployed URL stays live through winner announcements; and the public pipeline/session history proves the automation ran. Evaluation uses contrasting adversarial changes and benign controls, with limitations and false escalations reported.

### Level 2 — Team attention scheduler

Aggregate immutable Level 1 receipts across concurrent MRs, allocate declared human capacity using transparent consequence, uncertainty, ownership and effort, and show the cutoff plus consequential work left uncovered.

### Level 3 — Re-evaluation after a human-approved repair

Connect the original MR to a proposed repair, new revision, repeated checks, a new receipt, approval-gated redeployment, and reopened monitoring. This level adds safe repair/recovery depth beyond the Level 1 lifecycle demonstration.

### Level 4 — Repository portfolio

Coordinate versioned claims, policies, dependencies and receipts across related repositories, then report measured review outcomes without weakening policy automatically.

These levels are product states. Detailed implementation checkpoints may be split further, but no lifecycle stage is reported complete on its own while the end-to-end product path is absent.

## Authority, identity, and approval boundaries

- MR text, diffs, repository files on an MR branch, logs, tool outputs, MCP results and all agent outputs are untrusted data. They cannot grant instructions or alter protected policy.
- Change Mapper and Falsifier outputs remain `CANDIDATE`; deterministic checks provide only bounded evidence. Policy evaluation and routing stay deterministic.
- Mapper and Falsifier components have read-only GitLab/Orbit context. A later, separate action component can receive a narrowly scoped write tool only after the preceding `HumanInputComponent` checkpoint; its inputs are schema-validated data, never free-form agent authority. Protected `CODEOWNERS` covers the flow, CI, policy, and deployment configuration.
- Each consequential transition is preceded by a GitLab `HumanInputComponent` approval request. Every agent component that can invoke tools sets `require_tool_approval: true`; no write tool is pre-approved. Merge and production deployment also use GitLab's protected branch/environment controls. The human sees the proposed action and artifact before approval.
- Per-tool approval is an explicit Flow Registry setting, not an automatic property of remote flow execution. We will verify the pause/approve/reject path on this project before enabling writes. If the project cannot enforce it, the flow keeps write/deploy actions outside the agent and requires a human-operated GitLab action.
- Cloud deployment uses GitLab OIDC federation into a narrowly scoped Google service identity. No long-lived cloud key is stored in CI variables or artifacts.
- A passing pipeline, a clean scanner, an agent summary, or `COVERED_BY_EVIDENCE` never means globally safe or implicitly authorizes merge/deploy.

GitLab UI flows run in CI/CD. The Flow Registry supports `require_tool_approval: true` for an `AgentComponent`, and `HumanInputComponent` for stage-level approvals. Neither is a guarantee unless configured and exercised. The project will require both for tool-capable agents and consequential transitions. See [Flow Registry tool approval](https://docs.gitlab.com/user/duo_agent_platform/flows/claude-edit-v1-flow-registry/#tool-approval), [GitLab flow sessions and human checkpoints](https://docs.gitlab.com/user/duo_agent_platform/sessions/), and [GitLab security boundaries for agentic systems](https://docs.gitlab.com/user/duo_agent_platform/security_threats/).

## GitLab project prerequisites and access gate

- The custom flow configuration must be present on the default branch and flow execution/runners must be enabled.
- Creating MR-event triggers and configuring the project's `agent-config.yml` require Maintainer or Owner according to current GitLab documentation. Anna's current project role is the custom **Developer + AI** role; verify the effective abilities before implementation depends on them. If the role cannot configure triggers or flow execution, a project Maintainer must do that setup.
- Hosted or approved GitLab runners must execute flows and produce visible CI history.
- The read-only MR snapshot job runs only on the default branch and requires a manually supplied `TBAF_MR_IID`. It reads one open MR through the `CI_JOB_TOKEN`, fetches `refs/merge-requests/<iid>/head`, verifies the fetched SHA against GitLab's `diff_refs.head_sha`, and compares the exact base/head revisions. It never checks out or runs MR code. The policy is read from the pipeline's own commit, not the MR ref. Its output contains no passing checks by default, is still only a routing artifact, and cannot authorize merge or deployment. **Before treating policy from the default branch as trusted, protect that branch**; do not expose deployment secrets to untrusted MR pipelines. GitLab documents the job-token MR endpoints in [CI/CD job token access](https://docs.gitlab.com/ci/jobs/ci_job_token/) and the fetchable MR head ref in [MR troubleshooting](https://docs.gitlab.com/user/project/merge_requests/merge_request_troubleshooting/#check-out-merge-requests-locally-through-the-head-ref).
- Orbit Remote MCP is an optional read-only structural context provider for ownership/dependency mapping. It is not the policy authority or evidence verifier. The demo must still work and explain its limitation if Orbit is unavailable.
- Anthropic Claude is used through the GitLab Duo model/provider configuration; the project does not require a separate Anthropic credential.

The project flow was created in GitLab's UI, enabled, and exercised on MRs !1 and !2 with human approval before posting internal notes. The checked-in `.gitlab/duo/flows/attention-review.yml` is a repository copy; the project UI flow is the active object and is not automatically loaded from that path in this project. Keep them synchronized deliberately and revalidate after changes. Later flow/MCP configuration must be checked against the schema and permissions enabled on this project. References: [custom flow schema](https://docs.gitlab.com/user/duo_agent_platform/flows/custom_flows_schema/), [flow execution](https://docs.gitlab.com/user/duo_agent_platform/flows/execution/), [triggers](https://docs.gitlab.com/user/duo_agent_platform/triggers/), and [Duo MCP clients](https://docs.gitlab.com/user/gitlab_duo/model_context_protocol/mcp_clients/).

## Path B submission evidence

- Original MIT project URL: `https://github.com/annatchijova/to-build-a-fire`.
- Public hackathon GitLab project: `https://gitlab.com/gitlab-ai-hackathon/transcend-october-2026/1688368/showcase`.
- Public visibility and MIT license displayed in the GitLab project's About section: pending verification.
- New work after the October 5 start: commit history for Duo flows/automation, end-to-end GitLab CI, and deployment code. Keep the current local router, documentation, and pre-existing files distinguishable from new integration work.
- Public Cloud Run URL: pending deployment; do not submit a placeholder.
- Live CI/session history and public demonstration video under three minutes: pending.
- Deployment remains live through the announced winners timeframe; teardown date must be scheduled after November 16, 2026.

## Current state

The local deterministic router and contract exist. GitLab CI has a test job, an `attention-router-example` job, an `attention-router-mr-snapshot` job, and a new `attention-router-link-duo-assessment` job that links a matching confidential note when the default-branch pipeline can read MR notes. Live snapshot runs have been observed; the note-linking job has not yet had a live run. After MR !4 added the bounded authorization check, snapshot pipeline [#2932600822](https://gitlab.com/gitlab-ai-hackathon/transcend-october-2026/1688368/showcase/-/pipelines/2932600822) generated an artifact for MR !2 at head `e843e0d8128f5c6363d47e6272850fb709e4badc`. The artifact reported `authorization-invariants: FAIL`, claim `authorization-boundary: UNRESOLVED`, and route `TARGETED_REVIEW` with reason `required_check_fail:authorization-invariants`. The snapshot job and pipeline passed; that means the receipt was produced, not that the check passed. The seeded control and scope limits are documented in [`live-evidence-2026-10-09.md`](live-evidence-2026-10-09.md). Both snapshot and note-link jobs run from the default-branch revision only when `TBAF_MR_IID` is provided. Snapshot reads one open MR's metadata with the job token, fetches the MR head ref without checking it out, verifies the head SHA, and reads policy from its own commit. The note-link job reads confidential MR notes, selects the configured Change Mapper account, and verifies package project/IID/head binding; flow identity is configured context rather than API-attested provenance. Neither job executes MR code or authorizes merge/deployment. The project Duo flow has also been enabled and exercised on MRs !1 and !2: it fetched MR diffs, generated candidate assessments, paused for human input, and posted internal notes after approval. Cloud Run deployment and monitoring remain unfinished parts of the Path B/Assisted Level 1 target.

To run the MR snapshot from the GitLab UI, start a pipeline on the protected default branch and set the pipeline variable `TBAF_MR_IID` to the IID of an open MR in this project. Download `artifacts/review-package.json` from the `attention-router-mr-snapshot` job. The artifact binds the policy digest, base SHA, head SHA, changed paths, required checks, and attention route; it does not claim that any check passed.
