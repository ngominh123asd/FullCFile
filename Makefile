# FileForge - Makefile
# Common commands for development and deployment

.PHONY: help build up down restart logs ps clean dev prod test

# Default target
help:
	@echo "FileForge - Available Commands:"
	@echo "  make build      - Build all Docker images"
	@echo "  make up         - Start all services (development)"
	@echo "  make down       - Stop all services"
	@echo "  make restart    - Restart all services"
	@echo "  make logs       - View logs from all services"
	@echo "  make ps         - List running services"
	@echo "  make dev        - Start with frontend dev server"
	@echo "  make prod       - Start in production mode"
	@echo "  make clean      - Remove all containers, volumes"
	@echo "  make test       - Run tests"

# Build images
build:
	docker-compose build

# Start all services
up:
	docker-compose up -d
	@echo "✅ FileForge is starting..."
	@echo "   Frontend:  http://localhost:3000"
	@echo "   Backend:   http://localhost:8000"
	@echo "   API Docs:  http://localhost:8000/docs"
	@echo "   MinIO:     http://localhost:9001"

# Stop services
down:
	docker-compose down

# Restart services
restart:
	docker-compose restart

# View logs
logs:
	docker-compose logs -f --tail=100

# List services
ps:
	docker-compose ps

# Development mode with hot-reload
dev:
	docker-compose -f docker-compose.yml -f docker-compose.dev.yml up

# Production mode
prod:
	docker-compose -f docker-compose.yml -f docker-compose.prod.yml up -d

# Clean everything
clean:
	docker-compose down -v --remove-orphans
	docker system prune -f

# Run backend tests
test:
	docker-compose exec backend pytest

# Shell into backend
shell-backend:
	docker-compose exec backend bash

# Shell into frontend
shell-frontend:
	docker-compose exec frontend sh

# View specific service logs
logs-backend:
	docker-compose logs -f --tail=100 backend

logs-frontend:
	docker-compose logs -f --tail=100 frontend

logs-db:
	docker-compose logs -f --tail=100 postgres

# Rebuild specific service
rebuild-backend:
	docker-compose build --no-cache backend
	docker-compose up -d backend

rebuild-frontend:
	docker-compose build --no-cache frontend
	docker-compose up -d frontend