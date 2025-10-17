SHELL := /bin/bash

# Local dev
up:
	docker compose up -d

down:
	docker compose down

logs:
	docker compose logs -f

test-chat:
	curl -s http://localhost:8080/v1/chat/completions \
		-H 'Content-Type: application/json' \
		-d '{"model":"mistralai/Mistral-7B-Instruct-v0.3","messages":[{"role":"user","content":"Hello"}]}' | jq .

# Server deployment
up-server:
	docker compose -f docker-compose.yml -f docker-compose.server.yml up -d --build

logs-server:
	docker compose -f docker-compose.yml -f docker-compose.server.yml logs -f

# Worker deployment
up-worker:
	docker compose -f docker-compose.worker.yml up -d

logs-worker:
	docker compose -f docker-compose.worker.yml logs -f

# Testing
test:
	pytest -q --maxfail=1 --cov=services --cov-report=xml --cov-report=term

lint:
	ruff check services && black --check services

type:
	mypy --strict services/api/src services/router/src services/worker_client/src

fix:
	ruff check --fix services && black services

# CI simulation
ci: lint type test

# Deployment helpers
deploy-server:
	./deploy/ci/scripts/remote_deploy.sh server

deploy-worker:
	./deploy/ci/scripts/remote_deploy.sh worker

# Workstation setup
setup-workstation:
	chmod +x dev/scripts/setup_workstation.sh
	./dev/scripts/setup_workstation.sh

detect-hardware:
	python3 dev/scripts/detect_hardware.py

configure-network:
	python3 dev/scripts/configure_network.py

# Development helpers
install-pre-commit:
	pre-commit install

dev-setup: install-pre-commit
	@echo "Setting up development environment..."
	@echo "1. Run 'make detect-hardware' to detect hardware"
	@echo "2. Run 'make configure-network' to setup network"
	@echo "3. Copy machine-config/env.template to .env and configure"
	@echo "4. Run 'make up' to start local stack"
	@echo "5. Run 'make test-chat' to verify setup"

# Cleanup
clean:
	docker compose down -v
	docker system prune -f

clean-all: clean
	docker system prune -a -f
