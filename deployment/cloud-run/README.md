# Cloud Run deployment

This service is a static Review Package viewer. It serves the page and an illustrative sample; a selected package is read by JavaScript in the browser and is never uploaded. The container has no API, database, or package storage.

## Local container

Build and run from the repository root:

```sh
docker build -t tbaf-review-explorer .
docker run --rm -p 8080:8080 tbaf-review-explorer
```

Open `http://localhost:8080` and check `http://localhost:8080/health`.

## GitLab OIDC setup

The protected-main manual deploy job requires a Google Workload Identity Federation provider and a deploy service account. Do not store a service-account key in GitLab. From a terminal authenticated with the Google account that can manage IAM in the target project and a GitLab CLI with API write access, run:

```sh
bash scripts/setup-cloud-run-gcp.sh PROJECT_ID [REGION]
```

The script verifies that the active `gcloud` project matches `PROJECT_ID`, derives the project number, prints the exact target resources, and asks you to type the project ID before making changes. It enables the required APIs, creates or checks the `gitlab` workload identity pool and `showcase-main` provider, and creates separate deploy, build, and runtime service accounts. The build uses its own `roles/run.builder` identity. It creates or updates these **protected** GitLab variables for the Showcase project:

- `GCP_PROJECT_ID` = target project ID
- `GCP_PROJECT_NUMBER` = derived from the target project
- `GCP_WIF_POOL_ID` = `gitlab`
- `GCP_WIF_PROVIDER_ID` = `showcase-main`
- `GCP_DEPLOYER_SERVICE_ACCOUNT` = `tbaf-gitlab-deployer@PROJECT_ID.iam.gserviceaccount.com`
- `GCP_RUNTIME_SERVICE_ACCOUNT` = `tbaf-review-explorer-runtime@PROJECT_ID.iam.gserviceaccount.com`
- `GCP_BUILD_SERVICE_ACCOUNT` = `tbaf-cloud-build@PROJECT_ID.iam.gserviceaccount.com`
- `GCP_REGION` = `us-central1`

This changes the deployment target used by later protected-main pipelines. It does not delete resources from any previous Google Cloud project. To point GitLab back to a previous project, rerun the script with that project ID and region; resources created in the other project remain until separately reviewed and removed.

The provider maps `google.subject=assertion.sub,attribute.project_id=assertion.project_id,attribute.ref_path=assertion.ref_path` and restricts identity tokens to this GitLab project and its protected `main` branch:

```text
assertion.project_id == '87290826' && assertion.ref_path == 'refs/heads/main'
```

The deploy job is manual and restricted to protected `main`; its Google settings are protected GitLab variables. A GitLab Maintainer can additionally protect the `cloud-run-demo` environment to restrict who may deploy. Protecting an environment requires the Maintainer role, so it is optional when the project role cannot configure it. The project and provider IDs are public identifiers; GitLab API credentials are not written to files or included in command arguments by the script.

The job exchanges a GitLab ID token for short-lived Google credentials, builds from the repository's `Dockerfile` with the dedicated build service account, and deploys the static image as a **private** service. It runs manually from protected `main` after the verify stage passes and records the deployed source SHA, Cloud Run revision, and service URL in a dotenv artifact. It deliberately does not change the service's IAM policy.

After the Cloud Run service URL is anonymously reachable (for example, after the service-level invoker binding below), the protected-main pipeline exposes a separate manual `cloud-run-review-explorer-health` job. It sends an unauthenticated `GET /health`, requires HTTP 200 with the exact body `ok`, and writes `artifacts/cloud-run-health.json` with the check time, HTTP status, deployed revision, and source SHA. Run it only after an authorized administrator has enabled anonymous invocation; it does not change IAM or receive Cloud credentials. If access is provided through a gateway instead, this direct-URL check needs to be adapted to that approved endpoint first. The check confirms that Cloud Run reached the NGINX health handler. It does not verify that every static asset loads or independently prove which source was built.

After the first successful deploy, an authorized Google Cloud administrator can make the static demo publicly readable with this one-time service-level binding:

```sh
gcloud run services add-iam-policy-binding tbaf-review-explorer \
  --project "$GCP_PROJECT_ID" \
  --region "$GCP_REGION" \
  --member allUsers \
  --role roles/run.invoker
```

This grants public invocation of the static page only. The page contains an illustrative package; selected user packages are read in the browser and never sent to the service. If organization policy forbids public Cloud Run invokers, use an approved public access path before claiming a public demo URL.

The configuration follows GitLab's [Google Cloud Workload Identity Federation guide](https://docs.gitlab.com/ci/cloud_services/google_cloud/), Google's [Cloud Run source deployment permissions](https://docs.cloud.google.com/run/docs/deploying-source-code), and the [Cloud Run build service account guidance](https://docs.cloud.google.com/run/docs/configuring/services/build-service-account). IAM roles and current region availability should be checked before deployment.
