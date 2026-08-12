#!/usr/bin/env bash
# Scan a local Docker image with Trivy (CRITICAL/HIGH).
# Usage: scripts/security/scan_image.sh <image-ref> [report-basename]
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
IMAGE_REF="${1:-}"
BASENAME="${2:-trivy-image}"
REPORT_DIR="${ROOT}/security/reports"
IGNORE_FILE="${ROOT}/security/.trivyignore"

if [[ -z "${IMAGE_REF}" ]]; then
  echo "Usage: $0 <image-ref> [report-basename]" >&2
  exit 2
fi

mkdir -p "${REPORT_DIR}"

if ! command -v trivy >/dev/null 2>&1 && ! command -v docker >/dev/null 2>&1; then
  echo "Neither trivy nor docker is available for scanning." >&2
  exit 2
fi

TRIVY_ARGS=(
  image
  --severity CRITICAL,HIGH
  --exit-code 1
  --ignore-unfixed
  --format table
  --output "${REPORT_DIR}/${BASENAME}.txt"
)

if [[ -f "${IGNORE_FILE}" ]]; then
  TRIVY_ARGS+=(--ignorefile "${IGNORE_FILE}")
fi

echo "Scanning ${IMAGE_REF} (CRITICAL/HIGH; ignore-unfixed; exceptions in security/.trivyignore)"
echo "Readable report -> security/reports/${BASENAME}.txt"

if command -v trivy >/dev/null 2>&1; then
  # Also emit JSON for archival.
  trivy "${TRIVY_ARGS[@]}" "${IMAGE_REF}"
  trivy image --severity CRITICAL,HIGH --ignore-unfixed --format json \
    --ignorefile "${IGNORE_FILE}" \
    --output "${REPORT_DIR}/${BASENAME}.json" \
    "${IMAGE_REF}" || true
else
  # Fallback: official Trivy container (needs docker.sock).
  docker run --rm \
    -v /var/run/docker.sock:/var/run/docker.sock \
    -v "${REPORT_DIR}:/reports" \
    -v "${IGNORE_FILE}:/tmp/.trivyignore:ro" \
    aquasec/trivy:0.58.2 \
    image --severity CRITICAL,HIGH --exit-code 1 --ignore-unfixed \
    --ignorefile /tmp/.trivyignore \
    --format table --output "/reports/${BASENAME}.txt" \
    "${IMAGE_REF}"
fi

echo "Container security gate passed for ${IMAGE_REF}"
