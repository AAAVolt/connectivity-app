#!/usr/bin/env bash
# Bizkaia Connectivity – Build and deploy to Cloud Run via Cloud Build.
#
# Usage:
#   bash infra/deploy.sh [prod|staging]
#
# Defaults to prod. Per-target config lives in infra/env/<target>.env.
#
# Build + image push + Cloud Run deploy all happen in Cloud Build using
# cloudbuild.yaml as the source of truth — there's no local Docker
# requirement, so this works from any laptop without Docker Desktop.
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

echo "==> Target: ${TARGET}"
echo "    Project: ${PROJECT_ID}"
echo "    Service: ${SERVICE}"
echo "    Bucket:  ${BUCKET}"
echo ""

# ── Ensure JWT secret exists in Secret Manager ──
# Pre-flight check, since Cloud Build's deploy step assumes the secret
# already exists. This is a one-time bootstrap.
echo "==> Checking Secret Manager for ${SECRET_NAME}"
if ! gcloud secrets describe "${SECRET_NAME}" --project="${PROJECT_ID}" &>/dev/null; then
  echo "  Creating new secret and generating random value..."
  gcloud secrets create "${SECRET_NAME}" \
    --project="${PROJECT_ID}" \
    --replication-policy="user-managed" \
    --locations="${REGION}"
  openssl rand -base64 32 | tr -d '\n' | \
    gcloud secrets versions add "${SECRET_NAME}" --project="${PROJECT_ID}" --data-file=-
  gcloud secrets add-iam-policy-binding "${SECRET_NAME}" \
    --project="${PROJECT_ID}" \
    --member="serviceAccount:${SA_EMAIL}" \
    --role="roles/secretmanager.secretAccessor"
  echo "  Secret created and access granted."
else
  echo "  Secret already exists."
fi

# ── Submit the build ──
# We use gcloud's alternate-delimiter substitutions form (`^@^...`) so
# values can safely contain commas — CORS_ORIGINS is documented as
# comma-separated, and CORS_ORIGIN_REGEX is regex-shaped. The default `,`
# delimiter would silently truncate either. `@` is chosen because no
# legitimate substitution value should contain it; if that ever changes,
# pick a different sentinel here.
echo "==> Submitting build to Cloud Build (project: ${PROJECT_ID})"
gcloud builds submit \
  --project="${PROJECT_ID}" \
  --config=cloudbuild.yaml \
  --substitutions="^@^\
_BUCKET=${BUCKET}@\
_SERVICE=${SERVICE}@\
_ENVIRONMENT=${ENVIRONMENT}@\
_CORS_REGEX=${CORS_ORIGIN_REGEX}@\
_CORS_ORIGINS=${CORS_ORIGINS:-}@\
_MEMORY=${MEMORY}@\
_CPU=${CPU}@\
_MIN_INSTANCES=${MIN_INSTANCES}@\
_MAX_INSTANCES=${MAX_INSTANCES}@\
_TIMEOUT=${TIMEOUT_SECONDS}@\
_SA_NAME=${SA_NAME}@\
_SECRET_NAME=${SECRET_NAME}@\
_AR_REPO=${AR_REPO}" \
  .

URL=$(gcloud run services describe "${SERVICE}" --region="${REGION}" --project="${PROJECT_ID}" --format="value(status.url)")

# ── Warm cold endpoints ──
# Cloud Run scales to zero and the dashboard *-ranking endpoints run a
# heavy spatial join (~30s cold). The frontend's apiFetch has a 25s
# timeout, so the first real visitor after a fresh deploy would see
# municipality-ranking time out. CI does this same warm-up before e2e
# (.github/workflows/ci.yml), but a manual deploy needs it too.
echo ""
echo "==> Warming new revision (cold ranking endpoints exceed frontend timeout)"
DEPT="departure_time=08:00"
TENANT_HEADER="X-Tenant-ID: 00000000-0000-0000-0000-000000000001"
for i in 1 2 3; do
  if curl -sf -m 60 "${URL}/readiness" >/dev/null; then
    echo "    backend ready"; break
  fi
  echo "    readiness attempt ${i} failed, retrying..."; sleep 5
done
for path in "/dashboard/comarca-ranking?${DEPT}" "/dashboard/municipality-ranking?${DEPT}" "/sociodemographic/profiles"; do
  echo "    warming ${path}"
  curl -sf -m 60 "${URL}${path}" -H "${TENANT_HEADER}" >/dev/null \
    || echo "      warm of ${path} failed (continuing)"
done

echo ""
echo "==> Deployed!"
echo "    Target: ${TARGET}"
echo "    URL:    ${URL}"
echo "    Docs:   ${URL}/docs"
