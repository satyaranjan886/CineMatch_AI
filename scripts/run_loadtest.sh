#!/usr/bin/env bash
# Run a Locust scenario against a local/staging CineMatch API.
# Never point this at public production.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "${ROOT}"

if [[ -x "${ROOT}/.venv/bin/locust" ]]; then
  PATH="${ROOT}/.venv/bin:${PATH}"
fi

SCENARIO="${1:-low}"
HOST="${LOADTEST_HOST:-http://127.0.0.1:8000}"
LABEL="${LOADTEST_LABEL:-baseline}"
CONFIG="${ROOT}/loadtests/config/thresholds.json"
RESULTS_DIR="${ROOT}/loadtests/results"
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
PREFIX="${RESULTS_DIR}/${LABEL}_${SCENARIO}_${STAMP}"

if [[ ! -f "${CONFIG}" ]]; then
  echo "Missing ${CONFIG}" >&2
  exit 2
fi

USERS="$(python3 -c "import json;print(json.load(open('${CONFIG}'))['scenarios']['${SCENARIO}']['users'])")"
SPAWN="$(python3 -c "import json;print(json.load(open('${CONFIG}'))['scenarios']['${SCENARIO}']['spawn_rate'])")"
RUNTIME="${LOADTEST_RUN_TIME:-$(python3 -c "import json;print(json.load(open('${CONFIG}'))['scenarios']['${SCENARIO}']['run_time'])")}"

mkdir -p "${RESULTS_DIR}"

# Load DATABASE_URL / REDIS_URL for the sampler without bash-sourcing .env
# (dotenv files are not always valid shell).
if [[ -f "${ROOT}/.env" ]]; then
  eval "$(
    python3 - <<'PY'
from pathlib import Path
keys = ("DATABASE_URL", "REDIS_URL")
for line in Path(".env").read_text().splitlines():
    line = line.strip()
    if not line or line.startswith("#") or "=" not in line:
        continue
    key, _, value = line.partition("=")
    key = key.strip()
    if key not in keys:
        continue
    value = value.strip().strip("'").strip('"')
    # Escape for eval export
    value = value.replace("\\", "\\\\").replace('"', '\\"')
    print(f'export {key}="{value}"')
PY
  )"
fi

echo "=== CineMatch Locust ==="
echo "host=${HOST}"
echo "scenario=${SCENARIO} users=${USERS} spawn_rate=${SPAWN} run_time=${RUNTIME}"
echo "prefix=${PREFIX}"
echo "WARNING: Use only against local/staging. Do not load-test public production."

# Parse run_time like 2m / 90s into seconds for the system sampler.
SAMPLER_SECS="$(python3 -c "
t='${RUNTIME}'
if t.endswith('m'):
    print(int(float(t[:-1]) * 60) + 15)
elif t.endswith('s'):
    print(int(float(t[:-1])) + 10)
else:
    print(120)
")"

# Optional system sampler in background
python3 "${ROOT}/loadtests/collect_system_metrics.py" \
  --duration "${SAMPLER_SECS}" \
  --interval 5 \
  --output "${PREFIX}_system.json" \
  --metrics-url "${HOST}/metrics/" \
  >/dev/null 2>&1 &
SAMPLER_PID=$!

cleanup() {
  # Give the sampler a moment to flush; SIGTERM handler writes the JSON file.
  kill -TERM "${SAMPLER_PID}" >/dev/null 2>&1 || true
  wait "${SAMPLER_PID}" >/dev/null 2>&1 || true
}
trap cleanup EXIT

# Allow acceptance evaluation to fail without discarding Locust artifacts.
set +e
locust -f "${ROOT}/loadtests/locustfile.py" \
  --host "${HOST}" \
  --users "${USERS}" \
  --spawn-rate "${SPAWN}" \
  --run-time "${RUNTIME}" \
  --headless \
  --only-summary \
  --csv "${PREFIX}" \
  --html "${PREFIX}.html"
LOCUST_RC=$?

python3 "${ROOT}/loadtests/evaluate_results.py" \
  --stats-csv "${PREFIX}_stats.csv" \
  --thresholds "${CONFIG}" \
  --output "${PREFIX}_acceptance.json"
ACCEPT_RC=$?
set -e

echo "Artifacts:"
echo "  ${PREFIX}_stats.csv"
echo "  ${PREFIX}.html"
echo "  ${PREFIX}_acceptance.json"
echo "  ${PREFIX}_system.json"
echo "  ${PREFIX}_rec_stages.json"

if [[ ! -f "${PREFIX}_stats.csv" ]]; then
  exit "${LOCUST_RC}"
fi
# Locust may exit non-zero when any request fails; project acceptance is threshold-based.
exit "${ACCEPT_RC}"
