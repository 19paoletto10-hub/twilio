# Manifest – ver3.1.2

## Zawarte katalogi / pliki

- Dockerfile, docker-compose*.yml, Makefile, manage.py, run.py, requirements.txt
- app/
- deploy/
- docs/
- scripts/
- README.md, CHANGELOG.md

## Wykluczone (wrażliwe / operacyjne)

- .env (wszystkie sekrety)
- data/
- X1_data/
- .git/, .venv/, artefakty IDE
- tymczasowe pliki logów, *.pyc, __pycache__

## Instrukcja budowy

1. `./scripts/prepare_release_bundle.sh ver3.1.2`
2. Zweryfikuj `release/dist/ver3.1.2/` (czy zawiera tylko wymienione ścieżki).
3. Spakuj katalog i załącz do GitHub Release `ver3.1.2 – Multi-SMS batches & ops bundling`.
