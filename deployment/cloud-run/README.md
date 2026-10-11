# Cloud Run deployment

This service is a static Review Package viewer. It serves the page and an illustrative sample; a selected package is read by JavaScript in the browser and is never uploaded. The container has no API, database, or package storage.

## Local container

Build and run from the repository root:

```sh
docker build -t tbaf-review-explorer .
docker run --rm -p 8080:8080 tbaf-review-explorer
```

Open `http://localhost:8080` and check `http://localhost:8080/healthz`.

## GitLab OIDC setup

The protected manual deploy job requires a Google Workload Identity Federation provider and a deploy service account. Do not store a service-account key in GitLab.

1. Enable Cloud Run, Cloud Build, Artifact Registry, IAM Credentials, and Security Token Service APIs in project `vigia-497422`.
2. Create a Workload Identity Pool named `gitlab` and an OIDC provider named `showcase-main` with issuer `https://gitlab.com` and allowed audience `https://gitlab.com`.
3. Map `google.subject=assertion.sub,attribute.project_id=assertion.project_id,attribute.ref_path=assertion.ref_path` and set this provider condition:

   ```text
   assertion.project_id == '87290826' && assertion.ref_path == 'refs/heads/main'
   ```

   This restricts federation to the Showcase project and its `main` branch. Also protect the GitLab `cloud-run-demo` environment and the default branch.
4. Create a runtime service account with no project roles. Create a deploy service account, grant it `roles/run.sourceDeveloper` and `roles/serviceusage.serviceUsageConsumer` on the project, and grant `roles/iam.serviceAccountUser` on the runtime service account only.
5. Grant the provider identity `roles/iam.workloadIdentityUser` on the deploy service account. Use the pool principal set restricted to `attribute.project_id/87290826`.
6. Grant `roles/run.builder` to the Cloud Build service account used for source deployment. Confirm which build service account the project uses before assigning the role.
7. Add these **protected** GitLab CI/CD variables (they are identifiers, not secrets):

   - `GCP_PROJECT_ID` = `vigia-497422`
   - `GCP_PROJECT_NUMBER` = the numeric project number
   - `GCP_WIF_POOL_ID` = `gitlab`
   - `GCP_WIF_PROVIDER_ID` = `showcase-main`
   - `GCP_DEPLOYER_SERVICE_ACCOUNT` = deploy account email
   - `GCP_RUNTIME_SERVICE_ACCOUNT` = runtime account email
   - `GCP_REGION` = `us-central1`

The job exchanges a GitLab ID token for short-lived Google credentials, builds from the repository's `Dockerfile`, and deploys the static image as a **private** service. It runs manually from protected `main` after the verify stage passes and records the deployed source SHA, Cloud Run revision, and service URL in a dotenv artifact. It deliberately does not change the service's IAM policy.

After the first successful deploy, an authorized Google Cloud administrator can make the static demo publicly readable with this one-time service-level binding:

```sh
gcloud run services add-iam-policy-binding tbaf-review-explorer \
  --project vigia-497422 \
  --region us-central1 \
  --member allUsers \
  --role roles/run.invoker
```

This grants public invocation of the static page only. The page contains an illustrative package; selected user packages are read in the browser and never sent to the service. If organization policy forbids public Cloud Run invokers, use an approved public access path before claiming a public demo URL.

The configuration follows GitLab's [Google Cloud Workload Identity Federation guide](https://docs.gitlab.com/ci/cloud_services/google_cloud/) and Google's [Cloud Run source deployment permissions](https://docs.cloud.google.com/run/docs/deploying-source-code). IAM roles and current region availability should be checked before deployment.
