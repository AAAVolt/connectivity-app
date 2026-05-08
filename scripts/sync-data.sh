#!/usr/bin/env bash
# Bizkaia Connectivity – Sync local data/ with GCS bucket
# Usage:
#   bash scripts/sync-data.sh push [--mirror] [--dry-run]   # Upload local data → GCS
#   bash scripts/sync-data.sh pull [--mirror] [--dry-run]   # Download GCS → local data
#
# Flags:
#   --mirror   Delete remote/local objects that no longer exist on the source.
#              DESTRUCTIVE — only use when you intentionally want a 1:1 copy.
#              Without this flag, sync is additive (safer default).
#   --dry-run  Print what would be transferred without writing anything.
#
# Prerequisites: gcloud CLI authenticated (gcloud auth login)
set -euo pipefail

BUCKET="gs://bizkaia-data-pub"
DATA_DIR="data"

# Subdirectories to sync (everything needed to run locally)
DIRS=(gtfs network output pois processed raw serving)

usage() {
  cat <<EOF
Usage: $0 {push|pull} [--mirror] [--dry-run]

  push       Upload local data/ to GCS bucket (additive by default).
  pull       Download GCS bucket to local data/ (additive by default).

Flags:
  --mirror   Delete objects on the destination that don't exist on the source.
             DESTRUCTIVE. Without this flag, sync only adds/updates files.
  --dry-run  Preview changes without writing anything.

Examples:
  $0 push                  # safe additive upload
  $0 push --dry-run        # preview what would be uploaded
  $0 push --mirror         # delete remote files missing locally  (DANGEROUS)
EOF
  exit 1
}

check_gcloud() {
  if ! command -v gcloud &> /dev/null; then
    echo "ERROR: gcloud CLI not found. Install it from https://cloud.google.com/sdk/docs/install"
    exit 1
  fi
  if ! gcloud auth print-access-token &> /dev/null 2>&1; then
    echo "ERROR: Not authenticated. Run: gcloud auth login"
    exit 1
  fi
}

# Build the rsync arg list based on flags.
build_rsync_flags() {
  local flags=("--recursive")
  if [ "${MIRROR}" = "1" ]; then
    flags+=("--delete-unmatched-destination-objects")
  fi
  if [ "${DRY_RUN}" = "1" ]; then
    flags+=("--dry-run")
  fi
  printf '%s\n' "${flags[@]}"
}

confirm_mirror() {
  local direction="$1"
  if [ "${MIRROR}" != "1" ] || [ "${DRY_RUN}" = "1" ]; then
    return 0
  fi
  cat <<EOF
⚠️  --mirror is enabled. Files on the destination that are missing from the
    source will be DELETED.

    Direction: ${direction}
    Source:    $([ "${direction}" = "push" ] && echo "local ${DATA_DIR}/" || echo "${BUCKET}/data/")
    Target:    $([ "${direction}" = "push" ] && echo "${BUCKET}/data/" || echo "local ${DATA_DIR}/")

EOF
  read -r -p "Type 'mirror' to confirm: " ans
  if [ "${ans}" != "mirror" ]; then
    echo "Aborted."
    exit 1
  fi
}

do_push() {
  confirm_mirror push
  mapfile -t flags < <(build_rsync_flags)
  echo "==> Uploading local data/ → ${BUCKET}/data/  (mirror=${MIRROR}, dry-run=${DRY_RUN})"
  for dir in "${DIRS[@]}"; do
    local_path="${DATA_DIR}/${dir}"
    if [ -d "${local_path}" ]; then
      echo "    Syncing ${dir}/..."
      gcloud storage rsync "${local_path}" "${BUCKET}/data/${dir}" "${flags[@]}"
    else
      echo "    Skipping ${dir}/ (not found locally)"
    fi
  done
  echo ""
  echo "==> Done."
}

do_pull() {
  confirm_mirror pull
  mapfile -t flags < <(build_rsync_flags)
  echo "==> Downloading ${BUCKET}/data/ → local ${DATA_DIR}/  (mirror=${MIRROR}, dry-run=${DRY_RUN})"
  mkdir -p "${DATA_DIR}"
  for dir in "${DIRS[@]}"; do
    remote_path="${BUCKET}/data/${dir}"
    local_path="${DATA_DIR}/${dir}"
    if gcloud storage ls "${remote_path}/" &> /dev/null 2>&1; then
      echo "    Syncing ${dir}/..."
      mkdir -p "${local_path}"
      gcloud storage rsync "${remote_path}" "${local_path}" "${flags[@]}"
    else
      echo "    Skipping ${dir}/ (not found in GCS)"
    fi
  done
  echo ""
  echo "==> Done."
}

# --- Parse args ---
MIRROR=0
DRY_RUN=0
ACTION=""
for arg in "$@"; do
  case "${arg}" in
    push|pull) ACTION="${arg}" ;;
    --mirror)  MIRROR=1 ;;
    --dry-run) DRY_RUN=1 ;;
    -h|--help) usage ;;
    *)         echo "Unknown argument: ${arg}"; usage ;;
  esac
done

[ -z "${ACTION}" ] && usage

check_gcloud

case "${ACTION}" in
  push) do_push ;;
  pull) do_pull ;;
esac
