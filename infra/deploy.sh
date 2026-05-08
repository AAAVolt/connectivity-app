#!/usr/bin/env bash
# Bizkaia Connectivity – Build and deploy to Cloud Run.
#
# Usage:
#   bash infra/deploy.sh [prod|staging]
#
# Defaults to prod. Per-target config (project, bucket, service name, sizing)
# lives in infra/env/<target>.env so the script itself stays generic.
set -euo pipefail

TARGET="${1:-prod}"
ENV_FILE="infra/env/${TARGET}.env"

if [ ! -f "${ENV_FILE}" ]; then
  echo "ERROR: env file not found: ${ENV_FILE}"
  echo "Available targets:"
  ls infra/env/*.env 2>/dev/null | xargs -n1 basename | sed 's/\.env$//' | sed 's/^/  /'
  exit 1
fi

# shellcheck disable=SC1090
source "${ENV_FILE}"

SA_EMAIL="${SA_NAME}@${PROJECT_ID}.iam.gserviceaccount.com"
IMAGE="${REGION}-docker.pkg.dev/${PROJECT_ID}/${AR_REPO}/${SERVICE}"
TAG="${IMAGE}:$(date +%Y%m%d-%H%M%S)"
TAG_LATEST="${IMAGE}:latest"

echo "==> Target: ${TARGET}"
echo "    Project: ${PROJECT_ID}"
echo "    Service: ${SERVICE}"
echo "    Bucket:  ${BUCKET}"
echo ""

# ── Ensure JWT secret exists in Secret Manager ──
echo "==> Checking Secret Manager for ${SECRET_NAME}"
if ! gcloud secrets describe "${SECRET_NAME}" --project="${PROJECT_ID}" &>/dev/null; then
  echo "  Creating new secret and generating random value..."
  gcloud secrets create "${SECRET_NAME}" \
    --project="${PROJECT_ID}" \
    --replication-policy="user-managed" \
    --locations="${REGION}"
  openssl rand -base64 32 | tr -d '\n' | \
    gcloud secrets versions add "${SECRET_NAME}" --project="${PROJECT_ID}" --data-file=-
  # Grant the Cloud Run SA read access
  gcloud secrets add-iam-policy-binding "${SECRET_NAME}" \
    --project="${PROJECT_ID}" \
    --member="serviceAccount:${SA_EMAIL}" \
    --role="roles/secretmanager.secretAccessor"
  echo "  Secret created and access granted."
else
  echo "  Secret already exists."
fi

echo "==> Building image"
docker build --platform linux/amd64 -f docker/cloudrun.Dockerfile -t "${TAG}" -t "${TAG_LATEST}" .

echo "==> Pushing to Artifact Registry"
docker push "${TAG}"
docker push "${TAG_LATEST}"

echo "==> Deploying to Cloud Run"
gcloud run deploy "${SERVICE}" \
  --image="${TAG}" \
  --region="${REGION}" \
  --project="${PROJECT_ID}" \
  --service-account="${SA_EMAIL}" \
  --memory="${MEMORY}" \
  --cpu="${CPU}" \
  --min-instances="${MIN_INSTANCES}" \
  --max-instances="${MAX_INSTANCES}" \
  --timeout="${TIMEOUT_SECONDS}" \
  --startup-probe="httpGet.path=/readiness,initialDelaySeconds=5,periodSeconds=5,failureThreshold=20" \
  --set-env-vars="DATA_SOURCE=gcs,GCS_BUCKET=${BUCKET},GCS_PREFIX=serving,ENVIRONMENT=${ENVIRONMENT},CORS_ORIGINS=${CORS_ORIGINS:-},CORS_ORIGIN_REGEX=${CORS_ORIGIN_REGEX}" \
  --set-secrets="JWT_SECRET=${SECRET_NAME}:latest" \
  --allow-unauthenticated

URL=$(gcloud run services describe "${SERVICE}" --region="${REGION}" --project="${PROJECT_ID}" --format="value(status.url)")
echo ""
echo "==> Deployed!"
echo "    Target: ${TARGET}"
echo "    URL:    ${URL}"
echo "    Docs:   ${URL}/docs"
