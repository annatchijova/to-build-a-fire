#!/usr/bin/env bash
set -euo pipefail

# One-time Google Cloud and GitLab setup for the protected-main Cloud Run job.
# Requires gcloud access to modify IAM in vigia-497422 and GitLab API write
# access for the Showcase project. No long-lived credential is created.

readonly PROJECT_ID="vigia-497422"
readonly PROJECT_NUMBER="1028999311218"
readonly REGION="us-central1"
readonly GITLAB_PROJECT_ID="87290826"
readonly GITLAB_REPO="git@gitlab.com:gitlab-ai-hackathon/transcend-october-2026/1688368/showcase.git"
readonly POOL_ID="gitlab"
readonly PROVIDER_ID="showcase-main"
readonly DEPLOYER_NAME="tbaf-gitlab-deployer"
readonly RUNTIME_NAME="tbaf-review-explorer-runtime"
readonly DEPLOYER_EMAIL="${DEPLOYER_NAME}@${PROJECT_ID}.iam.gserviceaccount.com"
readonly RUNTIME_EMAIL="${RUNTIME_NAME}@${PROJECT_ID}.iam.gserviceaccount.com"
readonly BUILD_SERVICE_ACCOUNT="${PROJECT_NUMBER}-compute@developer.gserviceaccount.com"
readonly ATTRIBUTE_CONDITION="assertion.project_id == '${GITLAB_PROJECT_ID}' && assertion.ref_path == 'refs/heads/main'"

die() {
  printf 'ERROR: %s\n' "$1" >&2
  exit 1
}

command -v gcloud >/dev/null || die "Install and authenticate gcloud first."
command -v glab >/dev/null || die "Install and authenticate glab first."
command -v jq >/dev/null || die "Install jq first."

ACTIVE_ACCOUNT="$(gcloud auth list --filter=status:ACTIVE --format='value(account)')"
ACTUAL_PROJECT_NUMBER="$(gcloud projects describe "$PROJECT_ID" --format='value(projectNumber)')"
[[ "$ACTUAL_PROJECT_NUMBER" == "$PROJECT_NUMBER" ]] \
  || die "Configured project number does not match $PROJECT_ID; stop and inspect the gcloud target."
ACTUAL_BUILD_SERVICE_ACCOUNT="$(gcloud builds get-default-service-account --project="$PROJECT_ID")"
[[ "$ACTUAL_BUILD_SERVICE_ACCOUNT" == "$BUILD_SERVICE_ACCOUNT" ]] \
  || die "Cloud Build's current service account differs from the one reviewed in this script."
glab auth status --hostname gitlab.com >/dev/null || die "Authenticate glab with GitLab API access first."

if [[ -n "$ACTIVE_ACCOUNT" ]]; then
  printf 'Google principal: %s\n' "$ACTIVE_ACCOUNT"
else
  printf 'Google CLI is using its configured credential source (no active account listed).\n'
fi
printf 'Project: %s (%s)\nCloud Build service account: %s\n' \
  "$PROJECT_ID" "$PROJECT_NUMBER" "$BUILD_SERVICE_ACCOUNT"
printf 'This will enable APIs, create two service accounts, and add narrowly scoped IAM bindings.\n'

gcloud services enable \
  run.googleapis.com cloudbuild.googleapis.com artifactregistry.googleapis.com \
  iam.googleapis.com iamcredentials.googleapis.com sts.googleapis.com \
  --project="$PROJECT_ID"

if ! gcloud iam workload-identity-pools describe "$POOL_ID" \
  --location=global --project="$PROJECT_ID" >/dev/null 2>&1; then
  gcloud iam workload-identity-pools create "$POOL_ID" \
    --location=global \
    --display-name="GitLab CI" \
    --project="$PROJECT_ID"
fi

PROVIDER_JSON="$(gcloud iam workload-identity-pools providers describe "$PROVIDER_ID" \
  --location=global --workload-identity-pool="$POOL_ID" \
  --project="$PROJECT_ID" --format=json 2>/dev/null || true)"
if [[ -z "$PROVIDER_JSON" ]]; then
  gcloud iam workload-identity-pools providers create-oidc "$PROVIDER_ID" \
    --location=global \
    --workload-identity-pool="$POOL_ID" \
    --display-name="GitLab Showcase main" \
    --issuer-uri="https://gitlab.com" \
    --allowed-audiences="https://gitlab.com" \
    --attribute-mapping="google.subject=assertion.sub,attribute.project_id=assertion.project_id,attribute.ref_path=assertion.ref_path" \
    --attribute-condition="$ATTRIBUTE_CONDITION" \
    --project="$PROJECT_ID"
else
  jq -e \
    --arg condition "$ATTRIBUTE_CONDITION" \
    '.oidc.issuerUri == "https://gitlab.com"
      and ((.oidc.allowedAudiences // []) | index("https://gitlab.com") != null)
      and .attributeCondition == $condition
      and .attributeMapping["google.subject"] == "assertion.sub"
      and .attributeMapping["attribute.project_id"] == "assertion.project_id"
      and .attributeMapping["attribute.ref_path"] == "assertion.ref_path"' \
    <<< "$PROVIDER_JSON" >/dev/null \
    || die "Existing provider $PROVIDER_ID has different settings; inspect it before changing IAM."
  printf 'Existing OIDC provider settings match the expected GitLab project and main-branch restriction.\n'
fi

for account in "$DEPLOYER_EMAIL" "$RUNTIME_EMAIL"; do
  if ! gcloud iam service-accounts describe "$account" --project="$PROJECT_ID" >/dev/null 2>&1; then
    account_name="${account%%@*}"
    gcloud iam service-accounts create "$account_name" \
      --display-name="$account_name" --project="$PROJECT_ID"
  fi
done

gcloud projects add-iam-policy-binding "$PROJECT_ID" \
  --member="serviceAccount:${DEPLOYER_EMAIL}" --role="roles/run.sourceDeveloper" --condition=None --quiet
gcloud projects add-iam-policy-binding "$PROJECT_ID" \
  --member="serviceAccount:${DEPLOYER_EMAIL}" --role="roles/serviceusage.serviceUsageConsumer" --condition=None --quiet
gcloud projects add-iam-policy-binding "$PROJECT_ID" \
  --member="serviceAccount:${BUILD_SERVICE_ACCOUNT}" --role="roles/run.builder" --condition=None --quiet
gcloud iam service-accounts add-iam-policy-binding "$RUNTIME_EMAIL" \
  --project="$PROJECT_ID" \
  --member="serviceAccount:${DEPLOYER_EMAIL}" \
  --role="roles/iam.serviceAccountUser" --condition=None --quiet

readonly FEDERATED_PRINCIPAL="principalSet://iam.googleapis.com/projects/${PROJECT_NUMBER}/locations/global/workloadIdentityPools/${POOL_ID}/attribute.project_id/${GITLAB_PROJECT_ID}"
gcloud iam service-accounts add-iam-policy-binding "$DEPLOYER_EMAIL" \
  --project="$PROJECT_ID" \
  --member="$FEDERATED_PRINCIPAL" \
  --role="roles/iam.workloadIdentityUser" --condition=None --quiet

set_gitlab_variable() {
  local key="$1" value="$2"
  local path="projects/${GITLAB_PROJECT_ID}/variables/${key}"
  if glab api "$path" --repo "$GITLAB_REPO" >/dev/null 2>&1; then
    glab api -X PUT "$path" --repo "$GITLAB_REPO" \
      -f "value=${value}" -f protected=true -f raw=true >/dev/null
  else
    glab api -X POST "projects/${GITLAB_PROJECT_ID}/variables" --repo "$GITLAB_REPO" \
      -f "key=${key}" -f "value=${value}" -f protected=true -f raw=true >/dev/null
  fi
  printf 'Configured protected GitLab variable: %s\n' "$key"
}

set_gitlab_variable GCP_PROJECT_ID "$PROJECT_ID"
set_gitlab_variable GCP_PROJECT_NUMBER "$PROJECT_NUMBER"
set_gitlab_variable GCP_WIF_POOL_ID "$POOL_ID"
set_gitlab_variable GCP_WIF_PROVIDER_ID "$PROVIDER_ID"
set_gitlab_variable GCP_DEPLOYER_SERVICE_ACCOUNT "$DEPLOYER_EMAIL"
set_gitlab_variable GCP_RUNTIME_SERVICE_ACCOUNT "$RUNTIME_EMAIL"
set_gitlab_variable GCP_REGION "$REGION"

printf '\nSetup complete. Protect the GitLab cloud-run-demo environment, then run the manual deploy job on protected main.\n'
printf 'After first deploy, an authorized Google Cloud administrator must grant allUsers roles/run.invoker to publish the static demo.\n'
