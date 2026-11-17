#!/bin/sh
# Cloudflare Pages build: run from the frontend/ directory (set as the project's root directory).
# Needs VITE_API_BASE_URL, for example https://gamepulse-api.onrender.com (no trailing slash).
set -eu
: "${VITE_API_BASE_URL:?Set VITE_API_BASE_URL to the https URL of the API}"
case "$VITE_API_BASE_URL" in https://*) ;; *) echo "VITE_API_BASE_URL must start with https://" >&2; exit 1 ;; esac

npm ci
npm run build

API_WS="wss://${VITE_API_BASE_URL#https://}"
sed -e "s#__API_HTTP__#${VITE_API_BASE_URL}#" -e "s#__API_WS__#${API_WS}#" \
  ../deploy/cloudflare/_headers.template > dist/_headers
# Single-page app: unknown paths serve the app so deep links and refreshes work.
echo "/* /index.html 200" > dist/_redirects
