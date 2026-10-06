# Adversarial design review — GitLab MR snapshot

Date: 2026-10-06  
Scope: `src/tbaf/gitlab_mr_snapshot.py` and the `attention-router-mr-snapshot` CI job.  
Method: source review; no live GitLab execution or hostile-input induction was run.

## Threat model

- **Attacker can:** control an open MR's title, description, commits, file names, and timing; update its head while a snapshot is being captured; submit malformed or unusually large Git objects and path sets.
- **Attacker cannot (assumed):** modify the default branch or GitLab runner configuration; read runner memory; change GitLab's API response; obtain a Maintainer's credentials.
- **Important prerequisite:** protect the default branch and keep deployment secrets unavailable to MR pipelines before relying on the default-branch policy/job as trusted. This project setting has not been verified.

## Epistemic labels

CODE FACT · PLAUSIBLE HYPOTHESIS · CONFIRMED BY INDUCTION · FALSIFIED

## Findings

| ID | Severity | Level | Bucket | Finding |
|---|---|---|---|---|
| SNAP-01 | Informational | CODE FACT | Design boundary | MR content is fetched and diffed as Git data; the job does not check it out or execute it. |
| SNAP-02 | N/A | CODE FACT | Threat-model assumption | The policy is loaded from `CI_COMMIT_SHA`; its authority therefore depends on the default branch and job configuration being protected. |
| SNAP-03 | Medium | CODE FACT | Design limitation | The snapshot supplies no observations or passing checks. The artifact routes missing evidence to human review and cannot authorize merge or deployment. |
| SNAP-04 | Medium | PLAUSIBLE HYPOTHESIS | Operational assumption | A ref update after the exact SHA check can make the artifact stale relative to the live MR, though the artifact remains bound to its captured immutable SHA. Consumers must compare the package head SHA with the current MR head. |

## Mechanisms reviewed

- API URL must use HTTPS and the same authority as `CI_SERVER_URL`; redirects are rejected so the `JOB-TOKEN` header is not forwarded by the HTTP redirect handler.
- The requested IID, target project ID, open state, `sha`, and `diff_refs.base_sha/head_sha` are checked before routing.
- The fetched `refs/merge-requests/<iid>/head` must resolve to the API head SHA. If it moved between API lookup and fetch, capture fails closed.
- Git commands use argument arrays rather than a shell, disable external diff drivers and replacement objects, and bound captured output and execution time. Changed paths are bounded, UTF-8 decoded, and checked against the contract before parsing.
- The job runs only when a default-branch pipeline receives `TBAF_MR_IID`. The runner uses the short-lived `CI_JOB_TOKEN` for the read-only MR API request and repository fetch; this behavior still needs confirmation in the live project.
- `policy.json` is read from the job's own commit, not from the MR ref. The Review Package includes the policy content and digest, but it is not signed or authenticated as a runner attestation.
- The pipeline variable is passed as a quoted argument and the output path is fixed. It is not interpolated into a filesystem path.

## Discarded vectors

| Vector | Assessment | Reason |
|---|---|---|
| Prompt injection in MR text | Not in this adapter's input path | The snapshot reads metadata fields only for IID, project/state, and immutable diff references; it does not send MR text to an agent. |
| Path traversal in changed names | Rejected by the path contract | Paths are not used to open files; they are validated before becoming router input. This is source-based reasoning, not an executed hostile-path test. |
| Head update during fetch | Fails closed if observed | The ref's resolved SHA must equal the API head SHA. A post-capture update can still make a valid snapshot stale. |
| Redirect-based token forwarding | Rejected by construction | The opener has no redirect handler; no live redirect test was run. |

## Not established

- Live job-token permission, fetch behavior, runner image tools, GitLab CI YAML validity, and artifact upload have not been exercised.
- No unit or adversarial test was added or run for this adapter in this turn.
- The artifact hash is a content digest, not a signature or proof that the runner executed the checked-in code.
- No claim is made about tests, scanners, actual source lines, or policy completeness; this snapshot only routes changed paths against configured claims.
