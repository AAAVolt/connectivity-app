#!/usr/bin/env bash
# Bizkaia Connectivity – Build and deploy to Cloud Run
# Usage: bash infra/deploy.sh
set -euo pipefail

PROJECT_ID="laxi-ai"
REGION="europe-southwest1"
AR_REPO="bizkaia-images"
SERVICE="bizkaia-api"
SA_EMAIL="bizkaia-backend@${PROJECT_ID}.iam.gserviceaccount.com"
BUCKET="bizkaia-data-laxi"
IMAGE="${REGION}-docker.pkg.dev/${PROJECT_ID}/${AR_REPO}/${SERVICE}"
TAG="${IMAGE}:$(date +%Y%m%d-%H%M%S)"
TAG_LATEST="${IMAGE}:latest"
SECRET_NAME="bizkaia-jwt-secret"

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
  --memory=2Gi \
  --cpu=1 \
  --min-instances=0 \
  --max-instances=5 \
  --timeout=120 \
  --set-env-vars="DATA_SOURCE=gcs,GCS_BUCKET=${BUCKET},GCS_PREFIX=serving,ENVIRONMENT=production,CORS_ORIGINS=${CORS_ORIGINS:-}" \
  --set-secrets="JWT_SECRET=${SECRET_NAME}:latest" \
  --no-allow-unauthenticated

URL=$(gcloud run services describe "${SERVICE}" --region="${REGION}" --project="${PROJECT_ID}" --format="value(status.url)")
echo ""
echo "==> Deployed!"
echo "    URL: ${URL}"
echo "    Docs: ${URL}/docs"
