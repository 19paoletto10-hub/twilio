#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
RELEASE_TAG="${1:-ver3.1.2}"
DIST_DIR="$ROOT_DIR/release/dist/$RELEASE_TAG"

INCLUDE_PATHS=(
  "Dockerfile"
  "docker-compose.yml"
  "docker-compose.production.yml"
  "Makefile"
  "manage.py"
  "run.py"
  "requirements.txt"
  "README.md"
  "CHANGELOG.md"
  "app"
  "deploy"
  "docs"
  "scripts"
)

EXCLUDES=(
  "*.pyc"
  "__pycache__"
  ".DS_Store"
  "*.log"
  "release/dist"
  "scripts/prepare_release_bundle.sh"
)

SENSITIVE_PATHS=(
  ".env"
  "data"
  "X1_data"
  ".git"
  ".venv"
)

mkdir -p "$DIST_DIR"
rm -rf "$DIST_DIR"/*

copy_path() {
  local path="$1"
  local source="$ROOT_DIR/$path"
  if [[ ! -e "$source" ]]; then
    echo "[WARN] Pomijam brakujący path: $path" >&2
    return
  fi

  local rsync_args=(-a)
  for ex in "${EXCLUDES[@]}"; do
    rsync_args+=("--exclude=$ex")
  done

  rsync "${rsync_args[@]}" "$source" "$DIST_DIR"
}

for path in "${INCLUDE_PATHS[@]}"; do
  copy_path "$path"
done

cat > "$DIST_DIR/MANIFEST.md" <<'EOF'
# Release manifest

Ten katalog został zbudowany przez `scripts/prepare_release_bundle.sh`.
Zawiera tylko pliki potrzebne do uruchomienia aplikacji w środowiskach
produkcyjnych/testowych. Wykluczono następujące katalogi i pliki:

- .env (sekrety środowiskowe)
- data/ (baza SQLite)
- X1_data/ (scrapy, FAISS i dane newsowe)
- .git/, .venv/ oraz inne artefakty deweloperskie

Przed publikacją paczki zweryfikuj, że w `release/dist/<tag>/` nie pojawiły się
żadne pliki wymagające dodatkowej anonimizacji.
EOF

cat > "$DIST_DIR/README.md" <<EOF
# Twilio Chat App – $RELEASE_TAG (release bundle)

- Kod źródłowy: katalogi app/, docs/, deploy/, scripts/.
- Uruchomienie: korzystaj z Dockerfile + docker-compose.production.yml.
- Dokumentacja wydania: deploy/releases/$RELEASE_TAG.md.
- Brak danych wrażliwych: katalogi data/, X1_data/ oraz plik .env zostały pominięte.
EOF

cat <<EOF
Release bundle przygotowany w: $DIST_DIR
Możesz teraz wykonać:
  tar -czf "$ROOT_DIR/release/$RELEASE_TAG.tar.gz" -C "$DIST_DIR" .
EOF
