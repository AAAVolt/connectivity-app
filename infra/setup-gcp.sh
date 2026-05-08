#!/usr/bin/env bash
# Bizkaia Connectivity – GCP infrastructure setup
#
# Usage:
#   bash infra/setup-gcp.sh [prod|staging]
#
# Idempotent: re-running on an existing project / bucket / service account
# is safe. Creates whatever's missing, applies versioning + soft-delete on
# the bucket, and configures Docker auth.
set -euo pipefail

TARGET="${1:-prod}"
ENV_FILE="infra/env/${TARGET}.env"

if [ ! -f "${ENV_FILE}" ]; then
  echo "ERROR: env file not found: ${ENV_FILE}"
  exit 1
fi

# shellcheck disable=SC1090
source "${ENV_FILE}"

SA_EMAIL="${SA_NAME}@${PROJECT_ID}.iam.gserviceaccount.com"

echo "==> Target: ${TARGET}  (project: ${PROJECT_ID})"
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

# Enable object versioning + 30-day soft-delete so an accidental
# `sync-data.sh push --mirror` (or any rm) is recoverable. Idempotent: safe
# to re-run on an existing bucket.
echo "==> Enabling versioning + 30d soft-delete on gs://${BUCKET}"
gcloud storage buckets update "gs://${BUCKET}" \
  --versioning \
  --soft-delete-duration=30d

# Create folder structure
echo "==> Creating bucket folder structure"
echo "" | gcloud storage cp - "gs://${BUCKET}/serving/.keep"
echo "" | gcloud storage cp - "gs://${BUCKET}/raw/.keep"

# ── Service Account ───────────────────────────────────────
echo "==> Creating service account ${SA_NAME}"
gcloud iam service-accounts create "${SA_NAME}" \
  --display-name="Bizkaia Backend (${TARGET})" 2>/dev/null || echo "  (SA already exists)"

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
  --description="Bizkaia Connectivity Docker images (${TARGET})" 2>/dev/null || echo "  (repo already exists)"

# Configure docker auth for this registry
echo "==> Configuring Docker auth"
gcloud auth configure-docker "${REGION}-docker.pkg.dev" --quiet

# ── Summary ───────────────────────────────────────────────
IMAGE_BASE="${REGION}-docker.pkg.dev/${PROJECT_ID}/${AR_REPO}"

cat <<EOF

============================================================
  GCP setup complete for ${TARGET}!
============================================================

  Project:          ${PROJECT_ID}
  Region:           ${REGION}
  Bucket:           gs://${BUCKET}
  Service Account:  ${SA_EMAIL}
  Image Registry:   ${IMAGE_BASE}

  Next steps:

  1. Upload serving data:
     gcloud storage cp data/serving/*.parquet gs://${BUCKET}/serving/

  2. Deploy the backend:
     bash infra/deploy.sh ${TARGET}

EOF
