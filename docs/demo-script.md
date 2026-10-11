# Demo video script — draft under three minutes

Target runtime: **2:35**. Record in English for the hackathon. Use the project's
own interface and terminal output, no background music, and no unrelated
company logos or marks. Keep the browser and terminal at readable zoom.

This script uses evidence already recorded for MR !2. Before recording, fetch
the current artifacts and confirm the SHA and IDs below still match; do not
present an old artifact as current state.

## Recording outline

| Time | Screen | Narration |
| --- | --- | --- |
| 0:00–0:20 | Title card, then a two-line authorization change in the MR diff. | “When teams can open more changes than people can carefully review, diff size is a poor guide. Two lines can change an access boundary; thousands of generated lines may not. TO BUILD A FIRE routes human attention using evidence and explicit policy.” |
| 0:20–0:45 | Show the MR pipeline and its bounded authorization check result. | “This seeded, unmerged control makes an authorization function allow every authenticated user. The check reports `FAIL`. The pipeline itself passes because it successfully produced its evidence package; that does not mean the authorization claim passed.” |
| 0:45–1:15 | Open the live `review-package.json` in Review Package Explorer. Focus on head SHA, unresolved claim, check, route, and task. | “The package is bound to this exact commit. It keeps the authorization claim `UNRESOLVED`, names the missing or failing evidence, and routes the change to `TARGETED_REVIEW`. A reviewer can see why and where attention is needed.” |
| 1:15–1:45 | Show the Duo session checkpoint and the approved internal note on the MR. | “A read-only Change Mapper reports candidate observations from the diff. It pauses for a person before posting an internal note. The agent does not approve or merge the change.” |
| 1:45–2:10 | Show `assessment-link-status.json` in the terminal, then the package SHA beside it. | “A separate job linked the approved assessment to the package only when project, merge request, and head SHA matched. This run returned `linked` for the exact same SHA. The note API does not independently certify which flow authored it.” |
| 2:10–2:35 | Return to the router view, ending on `TARGETED_REVIEW` and the human task. | “The system does not decide that the change is safe. It makes the unresolved work, its evidence, and its human decision point visible. That is the product: allocating scarce review attention with a receipt for every route.” |

## Evidence to have ready

- MR !2, still open and labeled as a seeded control not to merge.
- A current snapshot whose `change.head_sha` matches the MR head and whose
  authorization check reports `FAIL`.
- The matching Review Package showing `UNRESOLVED` and `TARGETED_REVIEW`.
- The assessment-link status for the same SHA with `status: linked`.
- The Duo session showing the human approval checkpoint and resulting internal
  note. Do not expose tokens, account settings, or unrelated personal data.

## Answers for likely questions

- **Did the pipeline pass the authorization claim?** No. The check reported
  `FAIL`; the pipeline passed because it generated the receipt.
- **Does the assessment link authenticate the agent or flow?** No. It checks
  project, MR IID, and exact head SHA and records the configured source; the
  Notes API does not attest flow identity.
- **Has this reduced review time or false positives?** Not measured yet. The
  project has a seeded control and a benign control, but no population-level
  evaluation or time baseline.
- **Is Cloud Run live?** Only say yes after the protected environment is
  configured, the manual deployment succeeds, and the public URL is verified.

Do not end on the pending deployment. End on the verified attention route and
the human decision it preserves. Add the Cloud Run segment only after it is
actually live; keep the final video below three minutes.
