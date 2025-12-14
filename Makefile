PYTHON?=python
IMAGE_NAME=twilio-chat
TAG=latest

.PHONY: help build run compose-up compose-prod compose-ssl logs stop clean run-dev backup restore

help:
	@echo "╔══════════════════════════════════════════════════════════════╗"
	@echo "║           Twilio Chat App - Makefile Commands                ║"
	@echo "╠══════════════════════════════════════════════════════════════╣"
	@echo "║ DEVELOPMENT                                                  ║"
	@echo "║   make run-dev       - run app locally (venv + Flask)        ║"
	@echo "║   make compose-up    - docker compose up (dev, port 3000)    ║"
	@echo "║   make logs          - docker compose logs -f                ║"
	@echo "║   make stop          - stop docker compose services          ║"
	@echo "╠══════════════════════════════════════════════════════════════╣"
	@echo "║ PRODUCTION                                                   ║"
	@echo "║   make compose-prod  - production stack (nginx, port 80)     ║"
	@echo "║   make compose-ssl   - production with SSL (ports 80+443)    ║"
	@echo "╠══════════════════════════════════════════════════════════════╣"
	@echo "║ DOCKER                                                       ║"
	@echo "║   make build         - build docker image                    ║"
	@echo "║   make run           - run container (docker run)            ║"
	@echo "║   make clean         - remove images and containers          ║"
	@echo "╠══════════════════════════════════════════════════════════════╣"
	@echo "║ DATABASE                                                     ║"
	@echo "║   make backup        - backup SQLite database                ║"
	@echo "║   make restore F=... - restore from backup file              ║"
	@echo "╠══════════════════════════════════════════════════════════════╣"
	@echo "║ TESTING                                                      ║"
	@echo "║   make demo-send     - send test SMS                         ║"
	@echo "║   make health        - check /api/health endpoint            ║"
	@echo "╚══════════════════════════════════════════════════════════════╝"

build:
	docker build -t $(IMAGE_NAME):$(TAG) .

run:
	docker run --rm -it -p 3000:3000 --env-file .env -v $(shell pwd)/data:/app/data $(IMAGE_NAME):$(TAG)

compose-up:
	docker compose up --build

compose-prod:
	docker compose -f docker-compose.production.yml up --build -d

compose-ssl:
	docker compose -f docker-compose.ssl.yml up --build -d

compose-demo:
	docker compose -f docker-compose.yml up --build -d

demo-send:
	./scripts/demo_send.sh

logs:
	docker compose logs -f

stop:
	docker compose down

clean:
	docker compose down --rmi all --volumes --remove-orphans || true

run-dev:
	$(PYTHON) -m venv .venv && . .venv/bin/activate && pip install -r requirements.txt && python run.py

# Database operations
backup:
	@./scripts/backup_db.sh

restore:
	@if [ -z "$(F)" ]; then \
		echo "Usage: make restore F=backup/app_YYYYMMDD_HHMMSS.db"; \
		exit 1; \
	fi
	@./scripts/backup_db.sh --restore $(F)

# Health check
health:
	@curl -s http://localhost:3000/api/health | python -m json.tool 2>/dev/null || curl -s http://localhost:3000/api/health
