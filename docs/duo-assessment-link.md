# Linking a Duo assessment to a Review Package

`tbaf-link-assessment` creates a `tbaf.review-package-link/v2` envelope from a
deterministic `tbaf.review-package/v2` or v3 artifact and a structured
`tbaf.duo-assessment/v2` candidate assessment. It also accepts v1 assessments
for compatibility and maps their missing completeness metadata to `unknown`.
The input can be a JSON file or
a human-readable note containing exactly one fenced `json` block. It rejects a
mismatch in project, merge-request IID, or head SHA. Candidate locations must
belong to paths changed by the MR, and each observation revision must equal the
package head SHA.

The envelope embeds the original package unchanged. Its route, claims, checks,
and schedule are not recalculated or modified by this command. Duo observations
remain `CANDIDATE`; the reported agent provenance is explicitly marked
as not independently authenticated. The package's policy digest is recorded
in the envelope; the Change Mapper does not claim to have inspected that
policy. The envelope's SHA-256 detects changes relative to the supplied files,
but does not establish who created them. Verify the GitLab project, pipeline,
job, and commit when obtaining the package artifact.

The v2 envelope carries `change_mapper.diff_coverage` with `complete`, `partial`,
or `unknown`, affected paths, and limitations. For v2 this is explicitly marked
as agent-reported and not independently verified. It is display metadata only:
it cannot lower or replace the deterministic route. Legacy v1 assessments map
to `unknown`; missing metadata never means complete. The linker checks that
listed paths belong to the package's changed paths and that incomplete states
include a limitation, but cannot prove the mapper's statement is true.

The checked-in flow YAML requests a human-readable assessment plus exactly one
structured JSON block. The active GitLab UI flow is a separate object and must
be updated from the checked-in configuration before its notes use this schema.

On the default branch, `.gitlab-ci.yml` runs
`tbaf.gitlab_assessment_link` after the MR snapshot job when `TBAF_MR_IID` is
set. It reads MR notes with `CI_JOB_TOKEN`, considers only internal notes
authored by the configured Change Mapper user, and accepts only a structured
assessment that matches the Review Package project, IID, and head SHA. It
publishes `assessment-link-status.json` and, when linked,
`linked-review-package.json` as artifacts. The deterministic package and its
route remain unchanged.

To request a snapshot from a terminal, the pipeline exposes a validated
`mr_iid` input. On a `glab` version that supports pipeline inputs, run:

```sh
glab ci run --branch main --input 'mr_iid:2'
```

The input accepts an empty value for ordinary pipelines or a positive decimal
MR IID. It maps to `TBAF_MR_IID` only inside the pipeline configuration, so a
user does not need permission to override pipeline variables. Older `glab`
versions without `--input` must be upgraded before using this command.

## Exact-head linker controls

Run the focused local evaluation with:

```sh
PYTHONPATH=src python3 -m unittest discover -s tests -p 'test_gitlab_assessment_link.py' -v
```

The stale-only fixture must produce `not_found`; a fixture containing both an
older note and a valid exact-head note must link the exact-head note. The test
also checks that the embedded Review Package, including its digest, route, and
claims, is structurally identical after JSON parsing to the original package.
These are local deterministic fixtures; they measure linker behavior, not live
GitLab false-positive or false-negative rates.

The GitLab Notes API exposes the note author and confidentiality but does not
attest which flow created a note. The linked artifact therefore records the
configured flow ID as context and marks flow identity as
`configured_not_attested_by_notes_api`. It also does not independently
authenticate the agent's claimed source. If the job token cannot read MR notes,
the job publishes `status: unavailable` rather than implying that no assessment
exists. A successful CI run must still be checked for `status: linked` before
using the candidate observations.

## Input shape

```json
{
  "schema_version": "tbaf.duo-assessment/v2",
  "change": {
    "project": "group/project",
    "mr_iid": 2,
    "head_sha": "<40-character lowercase Git SHA>"
  },
  "source": {
    "agent": "inspect_mr",
    "version": "1"
  },
  "diff_coverage": {
    "status": "unknown",
    "paths": [],
    "limitations": ["The tool response did not establish complete patch coverage"]
  },
  "observations": []
}
```

Use `complete` only when the supplied response establishes that the changed-file
list and every patch are complete. Use `partial` when a file is marked collapsed
or too large, or a patch is visibly truncated; list the affected changed paths.
Use `unknown` when completeness cannot be established. `partial` and `unknown`
require at least one limitation; `complete` requires empty `paths` and
`limitations` arrays.

The note can include human-readable context outside the single JSON block. Each
observation uses the existing `tbaf.review-input/v1` observation shape,
including `id`, `kind`, `claim_id`, `impact`, `source`, `revision`, `scope`,
`text`, and `locations`. Its `source.agent` and `source.version` must match the
assessment source above. Set `change.project`, `change.mr_iid`, and
`change.head_sha` from the MR record supplied to the flow. This tool validates
them against the deterministic package before linking.

## Local command

```sh
PYTHONPATH=src python -m tbaf.link_assessment review-package.json duo-assessment.json
```

The command writes the linked envelope to standard output and rejects malformed
inputs with exit status 2. It performs no GitLab writes and cannot approve,
merge, release, or deploy.
