# Linking a Duo assessment to a Review Package

`tbaf-link-assessment` creates a `tbaf.review-package-link/v1` envelope from a
deterministic `tbaf.review-package/v2` artifact and a structured
`tbaf.duo-assessment/v1` candidate assessment. The input can be a JSON file or
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

The checked-in flow YAML now requests a human-readable assessment plus exactly
one structured JSON block. The active GitLab UI flow is a separate object and
must be updated from the checked-in configuration before its notes use this
schema. Fetching the correct CI artifact and note automatically is still
required for an end-to-end connection; this command currently accepts local
files and does not contact GitLab.

## Input shape

```json
{
  "schema_version": "tbaf.duo-assessment/v1",
  "change": {
    "project": "group/project",
    "mr_iid": 2,
    "head_sha": "<40-character lowercase Git SHA>"
  },
  "source": {
    "agent": "inspect_mr",
    "version": "1"
  },
  "observations": []
}
```

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
