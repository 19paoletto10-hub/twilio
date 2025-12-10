#!/usr/bin/env bash
# Generate a PDF from the HTML using headless Chrome/Chromium
# Usage: ./scripts/generate_pdf_chrome.sh [input-html] [output-pdf]
INPUT=${1:-deploy/releases/full_documentation.html}
OUTPUT=${2:-twilio-chat-app.pdf}

HTML_PATH="$(pwd)/${INPUT}"

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

${CHROME} --headless --disable-gpu --no-sandbox --print-to-pdf="${OUTPUT}" "file://${HTML_PATH}"
echo "PDF generated: ${OUTPUT}"
