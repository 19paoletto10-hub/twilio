#!/usr/bin/env bash
# Generate a PDF using wkhtmltopdf
# Usage: ./scripts/generate_pdf_wkhtml.sh [input-html] [output-pdf]
INPUT=${1:-deploy/releases/full_documentation.html}
OUTPUT=${2:-twilio-chat-app-wkhtml.pdf}

if ! command -v wkhtmltopdf >/dev/null 2>&1; then
  echo "wkhtmltopdf is not installed. Please install it (e.g., apt install wkhtmltopdf)." >&2
  exit 2
fi

wkhtmltopdf "${INPUT}" "${OUTPUT}"
echo "PDF generated: ${OUTPUT}"
