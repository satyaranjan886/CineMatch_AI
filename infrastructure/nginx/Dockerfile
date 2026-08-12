# syntax=docker/dockerfile:1
FROM nginx:1.27-alpine

RUN apk add --no-cache curl gettext \
    && rm -f /etc/nginx/conf.d/default.conf \
    && mkdir -p /etc/nginx/snippets /etc/nginx/templates-cinematch /etc/nginx/certs /var/www/certbot

COPY nginx.conf /etc/nginx/nginx.conf
COPY proxy_params.conf /etc/nginx/proxy_params.conf
COPY snippets/ /etc/nginx/snippets/
COPY templates/ /etc/nginx/templates-cinematch/
COPY docker-entrypoint.d/40-cinematch-tls.sh /docker-entrypoint.d/40-cinematch-tls.sh
RUN chmod +x /docker-entrypoint.d/40-cinematch-tls.sh

# Master process binds privileged ports; workers run as the nginx user (see nginx.conf).
# Do not commit TLS private keys into this image. Mount them at runtime when TLS_ENABLED=true.
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -fsS "http://127.0.0.1/nginx-health" || exit 1

EXPOSE 80 443
