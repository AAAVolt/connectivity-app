#!/usr/bin/env bash
# Bizkaia Connectivity – Sync local data/ with GCS bucket
# Usage:
#   bash scripts/sync-data.sh push   # Upload local data → GCS
#   bash scripts/sync-data.sh pull   # Download GCS → local data
#
# Prerequisites: gcloud CLI authenticated (gcloud auth login)
set -euo pipefail

BUCKET="gs://bizkaia-data-pub"
DATA_DIR="data"

# Subdirectories to sync (everything needed to run locally)
DIRS=(gtfs network output pois processed raw serving)

usage() {
  echo "Usage: $0 {push|pull}"
  echo ""
  echo "  push  – Upload local data/ to GCS bucket"
  echo "  pull  – Download GCS bucket to local data/"
  exit 1
}

check_gcloud() {
  if ! command -v gcloud &> /dev/null; then
    echo "ERROR: gcloud CLI not found. Install it from https://cloud.google.com/sdk/docs/install"
    exit 1
  fi
  # Quick auth check
  if ! gcloud auth print-access-token &> /dev/null 2>&1; then
    echo "ERROR: Not authenticated. Run: gcloud auth login"
    exit 1
  fi
}

do_push() {
  echo "==> Uploading local data/ → ${BUCKET}/data/"
  for dir in "${DIRS[@]}"; do
    local_path="${DATA_DIR}/${dir}"
    if [ -d "${local_path}" ]; then
      echo "    Syncing ${dir}/..."
      gcloud storage rsync "${local_path}" "${BUCKET}/data/${dir}" \
        --recursive \
        --delete-unmatched-destination-objects
    else
      echo "    Skipping ${dir}/ (not found locally)"
    fi
  done
  echo ""
  echo "==> Done! Data uploaded to ${BUCKET}/data/"
}

do_pull() {
  echo "==> Downloading ${BUCKET}/data/ → local data/"
  mkdir -p "${DATA_DIR}"
  for dir in "${DIRS[@]}"; do
    remote_path="${BUCKET}/data/${dir}"
    local_path="${DATA_DIR}/${dir}"
    # Check if remote dir has objects
    if gcloud storage ls "${remote_path}/" &> /dev/null 2>&1; then
      echo "    Syncing ${dir}/..."
      mkdir -p "${local_path}"
      gcloud storage rsync "${remote_path}" "${local_path}" \
        --recursive \
        --delete-unmatched-destination-objects
    else
      echo "    Skipping ${dir}/ (not found in GCS)"
    fi
  done
  echo ""
  echo "==> Done! Data downloaded to ${DATA_DIR}/"
}

# --- Main ---
check_gcloud

case "${1:-}" in
  push) do_push ;;
  pull) do_pull ;;
  *)    usage ;;
esac
