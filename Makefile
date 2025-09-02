.PHONY: help up down restart logs clean build

help:

	@echo "Available commands:"

	@echo "  make up        - Start all services"

	@echo "  make down      - Stop all services"

	@echo "  make restart   - Restart all services"

	@echo "  make logs      - View logs"

	@echo "  make clean     - Clean up volumes"

	@echo "  make build     - Build images"

up:

	docker compose up -d

	@echo "Waiting for services to be healthy..."

	@sleep 10

	@docker-compose ps

	@echo "\n✅ Application is running!"

	@echo "📊 Dashboard: http://localhost"

	@echo "🔧 API: http://localhost:8000"

down:

	docker compose down

restart:

	docker compose restart

logs:

	docker compose logs -f

clean:

	docker compose down -v

	rm -rf data/*

build:

	docker compose build --no-cache

status:

	@docker-compose ps

	@echo "\n--- Health Status ---"

	@docker compose exec backend curl -s http://localhost:8000/health || echo "Backend: ❌"

	@docker compose exec frontend curl -s http://localhost/health || echo "Frontend: ❌"
