# TO BUILD A FIRE

[English](README.md) · [Español](README.es.md) · [Technical README](TECHNICAL_README.md)

![TO BUILD A FIRE — AI made code cheap. Human attention is scarce.](visual/banner.png)

When people and coding agents can open more merge requests than a team can carefully inspect, another stream of automated review comments can add to the queue. TO BUILD A FIRE is a project idea for directing review effort: gather evidence about a change, identify what remains unresolved, and show people where their judgment matters most.

> **Project status:** GitLab CI has produced a live, read-only MR snapshot and run a bounded authorization invariant check against a seeded control. For MR !2 at head `e843e0d`, the check reported `FAIL`; the Review Package kept the claim `UNRESOLVED` and routed it to `TARGETED_REVIEW`. The pipeline passed because it generated the receipt; that is not a pass for the authorization claim. The Duo MR flow produced a `tbaf.duo-assessment/v2` candidate assessment after human approval. The default-branch linker returned `status: linked` for internal note `3992319519` on the exact package head, with mapper-reported `diff_coverage_status: complete`, in pipeline [#2935454761](https://gitlab.com/gitlab-ai-hackathon/transcend-october-2026/1688368/showcase/-/pipelines/2935454761). This is one live exact-head association, not a measured error rate; the Notes API does not attest flow identity or independently authenticate the claimed agent source. GitLab SAST ran in MR pipeline [#2934776373](https://gitlab.com/gitlab-ai-hackathon/transcend-october-2026/1688368/showcase/-/pipelines/2934776373) and produced one informational `bandit.B101` candidate; the report is not yet part of the Review Package or a merge gate. Google IAM/WIF is configured for Cloud Run; protecting the `cloud-run-demo` GitLab environment returned HTTP 403 for the current role, so deployment and monitoring remain unfinished. The [demo script](docs/demo-script.md) uses verified evidence and marks Cloud Run as pending. See [`docs/hackathon-path-b.md`](docs/hackathon-path-b.md), the [snapshot evidence](docs/live-evidence-2026-10-09.md), the [v1 assessment-link evidence](docs/live-e2e-assessment-link-2026-10-10.md), the [v2 assessment-link evidence](docs/live-e2e-assessment-link-2026-10-11.md), and the [SAST evidence](docs/live-sast-2026-10-10.md).

## The problem

The number of proposed changes can grow faster than human review capacity. Diff size alone is a poor guide: a generated lockfile may span hundreds of lines, while a two-line authorization change may alter who can access sensitive data.

Sending every change to another AI reviewer can leave reviewers with the original diff plus more comments, summaries, and findings to assess. Teams need a way to see what changed, which important properties may have been affected, what evidence exists, and what still needs a person.

## What it does

TO BUILD A FIRE is an **attention router for merge requests**. It allocates finite human review capacity to the changes where consequential uncertainty remains, and shows the reasons, locations, minutes demanded, and work left beyond capacity. A versioned `Review Package` is the internal contract that carries evidence between components; it is not the product. The system does not treat an agent's confidence or a single risk score as proof.

**Agents produce observations. Verification produces bounded evidence. Policy routes attention. Humans resolve what remains consequential and uncertain.**

```mermaid
flowchart TD
    MR[Merge request] --> MAP[Change Mapper agent]
    MAP --> CANDIDATES[Candidate observations]
    CANDIDATES --> EVIDENCE[Evidence Engine: tests, CI, scanners, ownership, contracts]
    EVIDENCE --> PACKAGE[Versioned Review Package: internal contract]
    PACKAGE --> POLICY[Deterministic policy]
    PACKAGE --> FALSIFIER[Falsifier agent: candidate counterexamples]
    POLICY --> ROUTER[Attention Router]
    FALSIFIER --> ROUTER
    ROUTER --> COVERED[COVERED BY EVIDENCE]
    ROUTER --> TARGET[TARGETED REVIEW]
    ROUTER --> DEEP[DEEP REVIEW]
    COVERED --> HUMAN[Human resolves consequential uncertainty]
    TARGET --> HUMAN
    DEEP --> HUMAN
```

The router has three explainable attention routes:

| Route | Meaning |
| --- | --- |
| `COVERED_BY_EVIDENCE` | Declared claims have the evidence required by the stated policy. This does not mean “safe” and does not authorize a merge. |
| `TARGETED_REVIEW` | Specific consequential claims remain uncertain; the router shows the exact claims, evidence gaps, and locations to inspect. |
| `DEEP_REVIEW` | Impact is broad, contradictory, or too uncertain for a narrow review; a person needs to assess the change more fully. |

Evidence states such as `SUPPORTED`, `UNRESOLVED`, `CONTRADICTED`, and `NOT_RUN` describe what checks established. They are separate from attention routes. Explicit merge or release gates are a separate policy decision. The current local core enforces declared path scope and exact-revision checks. GitLab CI now produces live MR evidence and runs a bounded authorization invariant check; this remains a routing aid, not a merge or deployment gate.

## A useful distinction

Consider two changes:

```mermaid
flowchart LR
    subgraph Big[Large diff: 2,438 lines]
      B[Generated files, formatting, tests, application changes]
      B --> BV[Some portions may be mechanically checked]
    end
    subgraph Small[Small diff: 2 lines]
      S[Authorization condition changes]
      S --> SV[Access boundary may have changed]
    end
    BV --> ROUTE[Route attention by affected claims and evidence]
    SV --> ROUTE
```

Line counts can help describe the diff, but they do not establish how much review it needs. The system should report **evidence-covered surface** and **unresolved review surface** separately. A portion that is not currently flagged for human review must not be described as safe merely because it was summarized or classified as mechanical.

## What makes the approach different

| Typical review queue | TO BUILD A FIRE (proposed) |
| --- | --- |
| Sort or prioritize by diff size, labels, or a single score | Explain attention needs through affected claims, policy, and evidence |
| Aggregate automated comments for a person to read | Gather evidence first and point to unresolved locations |
| Treat a clean scan or passing pipeline as a broad signal | State exactly which checks passed and which claims they support |
| Ask an agent whether the change looks safe | Use agents to investigate; use explicit policy and evidence to route decisions |

## How it should behave

The Attention Router should tell a team how much human review is demanded, how much capacity is available, what falls beyond that capacity, and why. Each work item points to affected claims, source locations, evidence and its limits, policy, and the source of its time estimate. If the estimate is unsupported, the demand is `UNKNOWN`, not zero. Candidate claims from agents stay candidates until corroborated or adjudicated.

For example, a team with 180 review minutes and 267 minutes of estimated demand sees 180 minutes scheduled and 87 still uncovered. “Scheduled” describes capacity allocation; it does not mean the code is evidence-covered or safe. These figures illustrate the intended display and are not measured project results.

```text
Review capacity today: 180 min
Estimated demand:      267 min
Scheduled:             180 min
Still uncovered:        87 min

Within capacity                 Still needing attention
MR !82   auth       35 min       MR !109  auth       42 min
MR !91   payments   50 min       MR !114  payments   45 min
MR !77   infra      40 min
MR !103  API        25 min
MR !66   deps       30 min
                         ───                           ───
                         180                            87 min
```

```mermaid
sequenceDiagram
    participant MR as Merge request
    participant Agents as Investigation agents
    participant Checks as Deterministic checks
    participant Falsifier as Falsifier agent
    participant Policy as Deterministic policy
    participant Router as Attention Router
    participant Human as Reviewer
    MR->>Agents: Map the diff and propose candidate claims
    Agents->>Checks: Suggest relevant evidence to collect
    Checks-->>Router: Scoped test, scanner, and CI observations
    Agents-->>Policy: Candidate observations with provenance
    Agents->>Falsifier: Submit claims and evidence to challenge
    Falsifier-->>Router: Candidate counterexamples, never verdicts
    Policy->>Router: Apply repository policy to structured evidence
    Router->>Router: Compare human demand with declared capacity
    Router-->>Human: Route work with evidence, locations, and cutoff
    Human-->>Router: Resolve consequential uncertainty and record disposition
```

## Hackathon direction

The planned evaluation uses seeded changes and benign controls: generated diffs, dependency updates, formatting-only refactors, missing tests, two-line authorization widening, removed scanners, weakened assertions, reduced coverage thresholds, CI commands ending in `|| true`, and stale-versus-exact-head Duo assessments. The inventory is in [`evaluation/corpus.json`](evaluation/corpus.json). Separate fixture-backed CI jobs check the deterministic router contract through [`evaluation/run_cases.py`](evaluation/run_cases.py) and the Duo assessment-link contract through [`evaluation/run_link_cases.py`](evaluation/run_link_cases.py). These checks do not measure attack-detection quality or the truth of mapper-reported diff completeness. [`test_gitlab_assessment_link.py`](tests/test_gitlab_assessment_link.py) also checks that a stale assessment is rejected and an exact-head assessment links without changing the deterministic package. The full evaluation is intended to measure critical cases routed to people, unnecessary benign escalations, minutes of human review against a declared baseline, and unsupported conclusions. No product-level metrics have been measured yet.

The planned demonstration contrasts a large, mostly generated change with a tiny authorization change, then shows the attention demand against team capacity. It should show how evidence and protected claims affect routing, rather than claim that the system has already reduced review time.

The target demo maps one connected MR flow across all nine post-code lifecycle stages. The coverage table and evidence required for each are in the [Path B / Assisted build contract](docs/hackathon-path-b.md#nine-stage-coverage-contract). This is a target, not a claim that the integrations already run.

The concept maps to the post-code lifecycle the GitLab Transcend hackathon asks participants to explore:

```mermaid
flowchart LR
    PLAN[Plan: classify change] --> CREATE[Create: propose repair]
    CREATE --> VERIFY[Verify: tests and invariants]
    VERIFY --> PACKAGE[Package: evidence bundle]
    PACKAGE --> SECURE[Secure: scanners and impact]
    SECURE --> RELEASE[Release: policy gate]
    RELEASE --> CONFIGURE[Configure: deploy settings]
    CONFIGURE --> MONITOR[Monitor: health signals]
    MONITOR --> GOVERN[Govern: record decisions]
    MONITOR -. regression .-> PLAN
```

These stages describe the intended direction, not completed integrations. GitLab Duo has been used for MR mapping and human-approved internal notes; the complete nine-stage workflow, including release, deployment, and monitoring, remains unfinished.

## Review Package Explorer

The browser-only viewer displays a Review Package's attention route, unresolved claims, checks, human tasks, and candidate observations. It also accepts a linked v2 envelope to show Duo's candidate notes and reported diff coverage beside the deterministic route. Coverage remains explicitly unverified and cannot change that route. Select a CI artifact from your device; JavaScript reads it locally and never uploads it. The bundled example is illustrative, and its displayed SHA-256 digest is not verified by the viewer.

Run it locally from the repository root:

```sh
python3 -m http.server 8080 --directory web
```

Open `http://localhost:8080`. A non-root NGINX container and a protected, manual GitLab OIDC deploy job for Cloud Run are also prepared. Google IAM/WIF is configured; first deployment is waiting for a Maintainer or Owner to protect the `cloud-run-demo` environment. The hosted URL and monitoring are not live yet; see [`deployment/cloud-run/README.md`](deployment/cloud-run/README.md).

## Repository map

- `README.md` — project overview and intended behavior.
- `README.es.md` — Spanish version of the overview.
- `TECHNICAL_README.md` — proposed architecture, decision boundary, evidence model, and open questions.
- `TODO.md` — complete product destination, build levels, inherited invariants, and closure criteria.
- `docs/hackathon-path-b.md` — end-to-end Assisted path, lifecycle evidence map, access dependencies, and Path B submission proof.
- `.gitlab/duo/flows/attention-review.yml` — checked-in MR-mapping flow configuration. The live project flow is a separate UI object; keep it synchronized with this file before relying on its structured assessment output.
- `.gitlab-ci.yml` — GitLab SAST on MR pipelines, contract, example-router, default-branch MR snapshot, and conditional Duo-assessment linking jobs. Scanner findings are not yet ingested into the Review Package; these jobs do not gate merge or deployment.
- `web/` — local-first Review Package Explorer and illustrative sample.
- `Dockerfile`, `deployment/cloud-run/`, `.gcloudignore` — static Cloud Run container and deployment configuration; Google IAM/WIF is configured, while environment protection and deployment remain pending.
- `scripts/setup-cloud-run-gcp.sh` — terminal setup for project-scoped Google IAM/WIF and protected GitLab CI variables.
- `docs/adr/` — architecture decisions and their assumptions.
- `.gitignore` — local Python environments, caches, build output, and secrets.
- `visual/` — project banner and future visual assets.
- `docs/red-team/` — adversarial design reviews and their evidence.
- `LICENSE` — MIT License, copyright © 2026 Anna Tchijova.

## Next steps

The product is planned as a set of complete, connected levels. Each level is useful on its own and keeps the evidence, policy, and authority boundaries needed by the full system. The levels below describe the destination and a build path toward it; they are not claims about what this repository already implements.

```mermaid
flowchart LR
    L1[1 · One change, end to end<br/>All nine stages with human gates]
    L2[2 · Team attention scheduler<br/>Allocate capacity across MRs]
    L3[3 · Approved repair<br/>Re-evaluate, release, monitor]
    L4[4 · Repository portfolio<br/>Cross-project contracts and learning]
    L1 --> L2 --> L3 --> L4
```

| Level | Complete, useful state |
| --- | --- |
| **1. One change, end to end** | Run one real GitLab MR across all nine post-code stages, with GitLab Duo, evidence-bound routing, human checkpoints, protected release, Cloud Run deployment, and monitoring. |
| **2. Team attention scheduler** | Allocate a shared review budget across MRs, expose the cutoff, and show consequential work still unreviewed. |
| **3. Approved repair and re-evaluation** | A bounded repair becomes a separately reviewed revision with fresh evidence, release/deploy gates, and monitoring linked to the original decision. |
| **4. Repository portfolio** | Teams can apply compatible policies across related repositories, account for cross-project contracts and dependencies, and compare measured review effort and outcomes. Any tuning remains explainable and cannot silently weaken required evidence or policy. |

The complete destination is a portfolio-aware attention system that follows a change from proposal through post-deploy evidence, directs human judgment to unresolved consequential claims, and records why each action was allowed, routed, or stopped. A hackathon deadline changes how many levels we attempt; it does not change the completion bar or make an unfinished level disposable. See the [Technical README](TECHNICAL_README.md#destination-and-build-levels) for level boundaries, completion evidence, and invariants inherited from the first level.

The implementation language is Python. The project is licensed under the MIT License; see [LICENSE](LICENSE).

### Local router core

The CLI accepts an untrusted, bounded `tbaf.review-input/v1` JSON record and a separately supplied `tbaf.policy/v1` file, then emits a deterministic, SHA-256-addressed internal receipt. Changed files outside declared claim scope and stale candidates route to deep review. Candidate observations cannot clear policy-mapped claims; required checks must be reported as passing on the exact head revision before declared scope can be marked covered. Unknown effort stays unknown. The policy must come from a trusted, protected location; the current CLI does not authenticate check producers or artifact references, so its receipt only evaluates supplied records.

```bash
python -m pip install -e .
tbaf-route examples/review-input.json --policy examples/policy.json
```

This local contract is an early single-MR core, not a merge gate, safety verdict, or measured reviewer-time reduction. The GitLab read-only MR snapshot has run live; see the [recorded result](docs/live-evidence-2026-10-09.md).
See [TODO.md](TODO.md) for the build plan and level completion criteria.
