PYTHON?=python
IMAGE_NAME=twilio-chat
TAG=latest

.PHONY: help build run compose-up compose-prod logs stop clean run-dev

help:
	@echo "Available targets:"
	@echo "  make build           - build docker image"
	@echo "  make run             - run container locally (docker run)"
	@echo "  make compose-up      - docker-compose up (dev)"
	@echo "  make compose-prod    - docker-compose -f docker-compose.production.yml up -d"
	@echo "  make logs            - docker compose logs -f"
	@echo "  make stop            - stop docker compose services"
	@echo "  make clean           - remove image and containers"
	@echo "  make run-dev         - run app locally in venv"

build:
	docker build -t $(IMAGE_NAME):$(TAG) .

run:
	docker run --rm -it -p 3000:3000 --env-file .env -v $(shell pwd)/data:/app/data $(IMAGE_NAME):$(TAG)

compose-up:
	docker compose up --build

compose-prod:
	docker compose -f docker-compose.production.yml up --build -d

logs:
	docker compose logs -f

stop:
	docker compose down

clean:
	docker compose down --rmi all --volumes --remove-orphans || true

run-dev:
	$(PYTHON) -m venv .venv && . .venv/bin/activate && pip install -r requirements.txt && python run.py
