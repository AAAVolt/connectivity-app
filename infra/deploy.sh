#!/usr/bin/env bash
# Bizkaia Connectivity – Build and deploy to Cloud Run
# Usage: bash infra/deploy.sh
set -euo pipefail

JWT_SECRET="${JWT_SECRET:-$(openssl rand -base64 32)}"

PROJECT_ID="bizkaia-492317"
REGION="europe-southwest1"
AR_REPO="bizkaia-images"
SERVICE="bizkaia-api"
SA_EMAIL="bizkaia-backend@${PROJECT_ID}.iam.gserviceaccount.com"
BUCKET="bizkaia-conn-data"
IMAGE="${REGION}-docker.pkg.dev/${PROJECT_ID}/${AR_REPO}/${SERVICE}"
TAG="${IMAGE}:$(date +%Y%m%d-%H%M%S)"
TAG_LATEST="${IMAGE}:latest"

echo "==> Building image"
docker build -f docker/cloudrun.Dockerfile -t "${TAG}" -t "${TAG_LATEST}" .

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
  --set-env-vars="DATA_SOURCE=gcs,GCS_BUCKET=${BUCKET},GCS_PREFIX=serving,ENVIRONMENT=local,JWT_SECRET=${JWT_SECRET}" \
  --allow-unauthenticated

URL=$(gcloud run services describe "${SERVICE}" --region="${REGION}" --format="value(status.url)")
echo ""
echo "==> Deployed!"
echo "    URL: ${URL}"
echo "    Docs: ${URL}/docs"
