#!/usr/bin/env bash
# Generate a PDF from the HTML using headless Chrome/Chromium
# Usage: ./scripts/generate_pdf_chrome.sh [input-html] [output-pdf]
set -euo pipefail

INPUT=${1:-deploy/releases/full_documentation.html}
OUTPUT=${2:-twilio-chat-app.pdf}

ROOT_DIR="$(pwd)"
HTML_PATH="${ROOT_DIR}/${INPUT}"

TMP_PROFILE_DIR=""
cleanup() {
  if [ -n "${TMP_PROFILE_DIR}" ] && [ -d "${TMP_PROFILE_DIR}" ]; then
    rm -rf "${TMP_PROFILE_DIR}" || true
  fi
}
trap cleanup EXIT
TMP_PROFILE_DIR="$(mktemp -d -t chrome-pdf-XXXXXX)"

if [ ! -f "${HTML_PATH}" ]; then
  echo "[ERROR] Input HTML not found: ${HTML_PATH}" >&2
  exit 2
fi

mkdir -p "$(dirname "${OUTPUT}")"

# Create a self-contained HTML to avoid local-file access issues.
INLINE_HTML="${HTML_PATH}"
if [ -f "${ROOT_DIR}/scripts/inline_assets_for_pdf.py" ]; then
  INLINE_HTML="${TMP_PROFILE_DIR}/input.inlined.html"
  python "${ROOT_DIR}/scripts/inline_assets_for_pdf.py" "${HTML_PATH}" "${INLINE_HTML}" >/dev/null
fi

if command -v google-chrome >/dev/null 2>&1; then
  CHROME=google-chrome
elif command -v chromium-browser >/dev/null 2>&1; then
  CHROME=chromium-browser
elif command -v chromium >/dev/null 2>&1; then
  CHROME=chromium
else
  echo "No Chrome/Chromium binary found in PATH. Install Google Chrome or Chromium." >&2
  exit 2
fi

set +e
timeout 180s ${CHROME} \
  --headless=new \
  --disable-gpu \
  --disable-features=Vulkan,UseSkiaRenderer \
  --use-angle=swiftshader \
  --use-gl=swiftshader \
  --no-sandbox \
  --disable-dev-shm-usage \
  --allow-file-access-from-files \
  --hide-scrollbars \
  --user-data-dir="${TMP_PROFILE_DIR}" \
  --no-first-run \
  --no-default-browser-check \
  --disable-extensions \
  --disable-background-networking \
  --disable-sync \
  --metrics-recording-only \
  --safebrowsing-disable-auto-update \
  --disable-component-update \
  --disable-client-side-phishing-detection \
  --disable-default-apps \
  --window-size=1280,720 \
  --accept-lang=pl-PL \
  --virtual-time-budget=60000 \
  --print-to-pdf-no-header \
  --print-to-pdf="${OUTPUT}" \
  "file://${INLINE_HTML}" >"${TMP_PROFILE_DIR}/chrome.log" 2>&1

STATUS=$?
set -e

if [ ${STATUS} -ne 0 ] || [ ! -s "${OUTPUT}" ]; then
  echo "[ERROR] Chromium PDF export failed (exit=${STATUS}). See ${TMP_PROFILE_DIR}/chrome.log for details." >&2
  cat "${TMP_PROFILE_DIR}/chrome.log" >&2
  exit 3
fi

echo "PDF generated: ${OUTPUT}"
