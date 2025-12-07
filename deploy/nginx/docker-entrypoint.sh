#!/bin/sh
set -eu

# If a template file exists, render it using envsubst to the live config.
TEMPLATE_FILE="/etc/nginx/conf.d/default.conf.template"
TARGET_FILE="/etc/nginx/conf.d/default.conf"

if [ -f "$TEMPLATE_FILE" ]; then
  echo "[proxy] Rendering nginx template -> $TARGET_FILE"
  envsubst < "$TEMPLATE_FILE" > "$TARGET_FILE"
else
  echo "[proxy] No template found, leaving existing config"
fi

echo "[proxy] Starting nginx..."
exec nginx -g 'daemon off;'
