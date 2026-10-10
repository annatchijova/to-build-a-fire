# Authorization invariant check

`authorization-invariants` is a bounded deterministic check for the sample
`src/auth.py:can_read_record` claim. The trusted snapshot job reads the file
blob from the MR head commit as bytes. It does not check out, import, or execute
the MR's code.

## Rule exercised

The declared access rule is:

- unauthenticated callers are denied;
- authenticated administrators are allowed;
- authenticated record owners are allowed;
- authenticated non-administrators who do not own the record are denied.

The checker statically interprets a deliberately small AST subset: boolean
attributes `user.is_authenticated` and `user.is_admin`, plus equality or
inequality between `user.id` and `record.owner_id`, joined with `and`, `or`, and
`not`. It evaluates all eight combinations of authentication, administrator
status, and owner equality. The subset is intentionally too small to express
arbitrary Python behavior.

## Results in the Review Package

- `PASS`: all eight combinations match the rule within the supported syntax.
- `FAIL`: at least one combination violates the rule; the package retains the
  failed scenario names and routes the claim to human attention.
- `NOT_RUN`: the function is missing, malformed, too large, or uses unsupported
  syntax. This is not a pass; the required claim stays unresolved.

Each result is bound to the MR head SHA and includes the source version, scope,
details, and a Git object reference for `src/auth.py`. A unit test verifies that
the seeded authenticated non-owner bypass fails while a safe implementation
passes. The added check details are part of Review Package v2; earlier v1
artifacts remain unchanged and inspectable as archived CI artifacts.

## Live GitLab run

The project owner reported that snapshot pipeline
[#2932600822](https://gitlab.com/gitlab-ai-hackathon/transcend-october-2026/1688368/showcase/-/pipelines/2932600822)
passed and its `attention-router-mr-snapshot` job
[#17075661487](https://gitlab.com/gitlab-ai-hackathon/transcend-october-2026/1688368/showcase/-/jobs/17075661487)
produced an artifact for MR !2 at head
`e843e0d8128f5c6363d47e6272850fb709e4badc`. The only changed path was
`src/auth.py`. The artifact reported `authorization-invariants: FAIL`, left
`authorization-boundary` `UNRESOLVED`, and routed it to `TARGETED_REVIEW` with
reason `required_check_fail:authorization-invariants`. The check's failure is
the expected detection result for this seeded control; the CI pipeline itself
passed because it successfully generated the receipt.

The earlier artifact for the same head reported
`required_check_missing:authorization-invariants`. See the provenance and
scope limits in [`live-evidence-2026-10-09.md`](live-evidence-2026-10-09.md).

## Limits

This is evidence about one function's behavior under the supported static
language. It does not prove that the function is imported or reachable, that
its objects are trustworthy, or that other authorization paths are correct. A
passing snapshot pipeline means the receipt was generated; it does not mean the
check itself passed. The Review Package carries the check's own `PASS`, `FAIL`,
or `NOT_RUN` status. Do not interpret this check as a repository-wide security
verdict or a merge authorization.
