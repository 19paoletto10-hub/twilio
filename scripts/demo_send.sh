#!/usr/bin/env bash
set -euo pipefail

# demo_send.sh
# Sends test SMS via the local API `POST /api/send-message`.
# Usage:
#   ./scripts/demo_send.sh --to "+48123123123" --body "Hello" [--count 3] [--host http://localhost:3000]

# Load .env if present
if [ -f .env ]; then
  # shellcheck disable=SC1091
  export $(grep -v '^#' .env | xargs) || true
fi

HOST=${HOST:-http://localhost:3000}
TO=""
BODY="Demo message from Twilio Chat App"
COUNT=1

print_help(){
  cat <<EOF
Usage: $0 [--to +48123...] [--body "text"] [--count N] [--host http://localhost:3000]

Examples:
  $0 --to +48123123123 --body "Hello from demo"
  HOST=http://127.0.0.1:3000 $0 --to +48123123123 --count 5
EOF
}

while [ "$#" -gt 0 ]; do
  case "$1" in
    --to) TO="$2"; shift 2;;
    --body) BODY="$2"; shift 2;;
    --count) COUNT="$2"; shift 2;;
    --host) HOST="$2"; shift 2;;
    -h|--help) print_help; exit 0;;
    *) echo "Unknown arg: $1"; print_help; exit 1;;
  esac
done

if [ -z "$TO" ]; then
  echo "Missing --to parameter (recipient number)." >&2
  print_help
  exit 2
fi

for i in $(seq 1 "$COUNT"); do
  echo "[$i/$COUNT] Sending to $TO: $BODY"
  resp=$(curl -sS -X POST "$HOST/api/send-message" \
    -H "Content-Type: application/json" \
    -d "{\"to\": \"$TO\", \"body\": \"$BODY\"}" ) || true
  echo "Response: $resp"
  sleep 0.5
done

echo "Done."
