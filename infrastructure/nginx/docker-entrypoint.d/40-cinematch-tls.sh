#!/bin/sh
# Configure HTTP-only or HTTPS (on-box TLS) based on TLS_ENABLED.
# Certificate paths are supplied via env — never baked into the image.
set -eu

TEMPLATES_DIR=/etc/nginx/templates-cinematch
CONF_DIR=/etc/nginx/conf.d

SERVER_NAME="${SERVER_NAME:-_}"
TLS_ENABLED="${TLS_ENABLED:-false}"
TLS_CERT_FILE="${TLS_CERT_FILE:-/etc/nginx/certs/fullchain.pem}"
TLS_KEY_FILE="${TLS_KEY_FILE:-/etc/nginx/certs/privkey.pem}"

export SERVER_NAME TLS_CERT_FILE TLS_KEY_FILE

rm -f "${CONF_DIR}/default.conf" "${CONF_DIR}/https.conf" "${CONF_DIR}/00-http.conf"

if [ "${TLS_ENABLED}" = "true" ] || [ "${TLS_ENABLED}" = "1" ]; then
  if [ ! -f "${TLS_CERT_FILE}" ] || [ ! -f "${TLS_KEY_FILE}" ]; then
    echo "TLS_ENABLED=true but certificate files are missing:" >&2
    echo "  TLS_CERT_FILE=${TLS_CERT_FILE}" >&2
    echo "  TLS_KEY_FILE=${TLS_KEY_FILE}" >&2
    echo "Mount certs or set TLS_ENABLED=false when TLS terminates at a load balancer." >&2
    exit 1
  fi
  envsubst '${SERVER_NAME}' < "${TEMPLATES_DIR}/https.conf" > "${CONF_DIR}/00-http.conf"
  envsubst '${SERVER_NAME} ${TLS_CERT_FILE} ${TLS_KEY_FILE}' \
    < "${TEMPLATES_DIR}/https.conf.server" > "${CONF_DIR}/https.conf"
  echo "Nginx TLS mode enabled for server_name=${SERVER_NAME}"
else
  cp "${TEMPLATES_DIR}/http-only.conf" "${CONF_DIR}/00-http.conf"
  echo "Nginx HTTP mode (use only behind trusted TLS termination or for local staging)."
fi
