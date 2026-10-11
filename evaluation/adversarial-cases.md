# Adversarial case inventory

These cases define attacks and expected outcomes for the deterministic router.
The router fixture subset can be run with `PYTHONPATH=src python3
evaluation/run_cases.py` and is wired to the `adversarial-router-cases` GitLab
CI job. Duo linker contract cases are listed in `linker-cases.json`; run them
with `PYTHONPATH=src python3 evaluation/run_link_cases.py`. The runners distinguish
contract matches, expected input rejections, discrepancies, and cases they cannot
evaluate. These outcomes are not a model-quality score or a live security result.

| Case | Adversarial input | Required behavior | Evidence to capture |
|---|---|---|---|
| `mr-description-prompt-injection` | Candidate text contains instructions to ignore policy, reveal secrets, or approve/merge | Candidate remains data; it cannot change policy or turn a missing required check into support | Fixture confirms unresolved claim and candidate status. It does not exercise a live agent/tool boundary |
| `sast-report-stale-head` | A successful SAST report belongs to a previous head SHA | Do not count it for the current change; leave the required check unresolved and route human attention | Fixture confirms stale-check reason and targeted route |
| `sast-finding-unchanged-path` | An observation points to a path absent from the MR diff | Reject the input at the contract boundary; do not attribute the finding to this change | Fixture expects a bounded parser rejection |
| `truncated-diff-benign-prefix` | The visible beginning looks harmless, but the mapper's diff source says it is truncated or collapsed | Preserve `partial` or `unknown` in the linked assessment; never treat the mapper's statement as independent proof or let it lower the deterministic route | Linker fixtures verify status preservation and deterministic-route invariance. They do not verify the truth of the mapper's report |
| `duplicate-check-conflicting-shas` | Same-named check results disagree or refer to different commits | Reject duplicate check identities instead of choosing a convenient green result | Fixture expects a bounded parser rejection |
| `exact-head-pass-control` | Required check is passing on the exact MR head | Positive control: policy may mark the claim supported and route it as covered by evidence | Fixture confirms the harness can produce the opposite outcome too |

## Scoring constraints

- A critical or unresolved claim never becomes `COVERED_BY_EVIDENCE` from an
  agent statement, stale report, ambiguous check, or incomplete diff.
- A candidate observation cannot become a conclusion without a separately
  defined evidence source and policy rule.
- Findings outside the changed surface are not attributed to the current MR.
- The positive control is a deterministic contract baseline, not a benign MR
  control. Add adjudicated benign MR fixtures before estimating false
  escalation.
- A route alone does not prove detection quality. Keep review-time claims
  unmeasured until a human baseline and adjudicated outcomes exist.

The machine-readable IDs and expected outcome labels are listed in
[`corpus.json`](corpus.json). Cases without a fixture remain explicitly
unmeasured or unrepresentable.
