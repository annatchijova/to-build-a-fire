# Linking a Duo assessment to a Review Package

`tbaf-link-assessment` creates a `tbaf.review-package-link/v1` envelope from a
deterministic `tbaf.review-package/v2` artifact and a structured
`tbaf.duo-assessment/v1` candidate file. It rejects a mismatch in project,
merge-request IID, head SHA, or policy digest. Candidate locations must belong
to paths changed by the MR, and each observation revision must equal the
package head SHA.

The envelope embeds the original package unchanged. Its route, claims, checks,
and schedule are not recalculated or modified by this command. Duo observations
remain `CANDIDATE`; the reported flow/session provenance is explicitly marked
as not independently authenticated. The envelope's SHA-256 detects changes
relative to the supplied file, but does not establish who created that file.
Use a trusted GitLab artifact or another verified transport for the package.

The current GitLab flow emits a human-readable assessment, not this structured
input schema. This command is a local integration primitive; converting the
active flow to produce a structured assessment and passing the CI artifact into
this command are still required for an automated end-to-end connection.

## Input shape

```json
{
  "schema_version": "tbaf.duo-assessment/v1",
  "change": {
    "project": "group/project",
    "mr_iid": 2,
    "head_sha": "<40-character lowercase Git SHA>"
  },
  "policy_sha256": "<64-character lowercase SHA-256>",
  "source": {
    "flow_id": "1016156",
    "session_id": "9114560",
    "agent": "inspect_mr",
    "version": "<reported agent version>"
  },
  "observations": []
}
```

Each observation uses the existing `tbaf.review-input/v1` observation shape,
including `id`, `kind`, `claim_id`, `impact`, `source`, `revision`, `scope`,
`text`, and `locations`. Its `source.agent` and `source.version` must match the
assessment source above.

## Local command

```sh
PYTHONPATH=src python -m tbaf.link_assessment review-package.json duo-assessment.json
```

The command writes the linked envelope to standard output and rejects malformed
inputs with exit status 2. It performs no GitLab writes and cannot approve,
merge, release, or deploy.
