# ADR-0001 — Host a local-first Review Package Explorer on Cloud Run

Date: 2026-10-10
Status: accepted
Reversibility: two-way door; replace the static container or hosting target without migrating user data

## Forces at the time

- The project owner selected Google Cloud and Cloud Run for the hackathon deployment and Google Cloud bonus.
- The active local `gcloud` configuration names project `vigia-497422` and region `us-central1` (observed 2026-10-10). No traffic target, latency SLO, or spend ceiling has been stated.
- The core currently emits versioned JSON Review Packages from GitLab CI. The repository has no web application or persistent data store.
- A package may contain private repository paths, review notes, or other sensitive context. The public demonstration must not require sending package contents to the hosted service.
- GitLab is the build and deploy control plane. Its Cloud Run deployment identity should use GitLab OIDC and short-lived Google credentials rather than a stored service-account key.

## Decision

Build a static Review Package Explorer and serve it from a non-root NGINX container on Cloud Run. The page loads the bundled package or reads a user-selected JSON file in the browser. It does not upload, persist, or transmit the selected package. The public page labels the bundled data as illustrative and the package digest as unverified identity metadata. Update (2026-10-23): the bundled package is now the MR !2 snapshot rebuilt from public data, labeled as a recorded local rebuild rather than a live MR.

The initial deployment uses the configured project and region, scales to zero, and caps the service at one instance. GitLab deploys only from protected `main` through a manual job authenticated with OIDC. No package-processing API, database, or user content storage is part of this decision.

## Alternatives rejected

- **Public package-processing API:** it would send user-supplied review data to a server, require request authentication and abuse controls, and create a policy trust boundary that the current product does not need. Its strongest argument is that it could make CI integration easier.
- **Cloud Storage static website:** it fits static hosting with less runtime machinery. Cloud Run is retained because the project owner explicitly chose it for the hackathon deployment and bonus; the portable static files remain easy to move later.
- **GKE or a virtual machine:** either can serve the page, but adds cluster or host operations without a workload requirement that needs them. Their strongest argument is greater control over the runtime.

## Assumption this rests on

A browser-local viewer is useful to the project owner and demo reviewers while keeping private Review Packages on the user's device. If the product needs multi-user queues or live synchronized GitLab data, this service is only the presentation component and will need a separately authenticated data path.

## Consequences

Accepted now: reviewers open a CI artifact manually; the hosted page cannot fetch private GitLab artifacts or recalculate policy. The static runtime has no package persistence or server-side decision logic.

Deferred: authenticated GitLab artifact discovery, multi-MR scheduling, and production monitoring. Deployment remains gated until OIDC/IAM and the project's protected environment are configured.

## Revisit trigger

Reopen this decision when the team needs the hosted app to retrieve private GitLab data, coordinate reviewer queues, or persist adjudications; also revisit the region and instance cap before the service receives sustained public traffic.

## Anchored at

- `web/` — client-side package reader and renderer.
- `Dockerfile` and `deployment/cloud-run/nginx.conf` — static non-root serving configuration.
- `.gitlab-ci.yml` — protected manual deployment job.
