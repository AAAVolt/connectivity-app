#!/usr/bin/env bash
# Bizkaia Connectivity – GCP infrastructure setup
# Run once: bash infra/setup-gcp.sh
set -euo pipefail

PROJECT_ID="bizkaia-492317"
REGION="europe-southwest1"          # Madrid – closest to Bizkaia
BUCKET="bizkaia-conn-data"
SA_NAME="bizkaia-backend"
SA_EMAIL="${SA_NAME}@${PROJECT_ID}.iam.gserviceaccount.com"
AR_REPO="bizkaia-images"
CLOUD_RUN_SERVICE="bizkaia-api"

echo "==> Setting project to ${PROJECT_ID}"
gcloud config set project "${PROJECT_ID}"

echo "==> Enabling required APIs"
gcloud services enable \
  storage.googleapis.com \
  run.googleapis.com \
  artifactregistry.googleapis.com \
  cloudbuild.googleapis.com \
  secretmanager.googleapis.com

# ── Cloud Storage ──────────────────────────────────────────
echo "==> Creating bucket gs://${BUCKET}"
gcloud storage buckets create "gs://${BUCKET}" \
  --location="${REGION}" \
  --uniform-bucket-level-access \
  --public-access-prevention 2>/dev/null || echo "  (bucket already exists)"

# Create folder structure
echo "==> Creating bucket folder structure"
echo "" | gcloud storage cp - "gs://${BUCKET}/serving/.keep"
echo "" | gcloud storage cp - "gs://${BUCKET}/raw/.keep"

# ── Service Account ───────────────────────────────────────
echo "==> Creating service account ${SA_NAME}"
gcloud iam service-accounts create "${SA_NAME}" \
  --display-name="Bizkaia Backend (Cloud Run)" 2>/dev/null || echo "  (SA already exists)"

# Grant storage read access
echo "==> Granting storage.objectViewer to SA"
gcloud storage buckets add-iam-policy-binding "gs://${BUCKET}" \
  --member="serviceAccount:${SA_EMAIL}" \
  --role="roles/storage.objectViewer"

# ── Artifact Registry ─────────────────────────────────────
echo "==> Creating Artifact Registry repo"
gcloud artifacts repositories create "${AR_REPO}" \
  --repository-format=docker \
  --location="${REGION}" \
  --description="Bizkaia Connectivity Docker images" 2>/dev/null || echo "  (repo already exists)"

# Configure docker auth for this registry
echo "==> Configuring Docker auth"
gcloud auth configure-docker "${REGION}-docker.pkg.dev" --quiet

# ── Summary ───────────────────────────────────────────────
IMAGE_BASE="${REGION}-docker.pkg.dev/${PROJECT_ID}/${AR_REPO}"

cat <<EOF

============================================================
  GCP setup complete!
============================================================

  Project:          ${PROJECT_ID}
  Region:           ${REGION}
  Bucket:           gs://${BUCKET}
  Service Account:  ${SA_EMAIL}
  Image Registry:   ${IMAGE_BASE}

  Next steps:

  1. Build & push the backend image:
     docker build -f docker/cloudrun.Dockerfile -t ${IMAGE_BASE}/${CLOUD_RUN_SERVICE}:latest .
     docker push ${IMAGE_BASE}/${CLOUD_RUN_SERVICE}:latest

  2. Deploy to Cloud Run:
     gcloud run deploy ${CLOUD_RUN_SERVICE} \\
       --image=${IMAGE_BASE}/${CLOUD_RUN_SERVICE}:latest \\
       --region=${REGION} \\
       --service-account=${SA_EMAIL} \\
       --memory=2Gi \\
       --cpu=1 \\
       --min-instances=0 \\
       --max-instances=5 \\
       --set-env-vars="DATA_SOURCE=gcs,GCS_BUCKET=${BUCKET},GCS_PREFIX=serving,ENVIRONMENT=production" \\
       --no-allow-unauthenticated

  3. Upload serving data:
     gcloud storage cp data/serving/*.parquet gs://${BUCKET}/serving/

EOF
