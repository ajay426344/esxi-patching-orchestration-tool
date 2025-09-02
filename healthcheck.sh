#!/bin/bash

echo "🔍 ESXi Orchestrator Health Check"

echo "================================="

# Function to check service

check_service() {

    local service=$1

    local url=$2

    local name=$3

    

    if curl -s -f "$url" > /dev/null; then

        echo "✅ $name is healthy"

    else

        echo "❌ $name is not responding"

    fi

}

# Check all services

check_service "backend" "http://localhost:8000/health" "Backend API"

check_service "frontend" "http://localhost/health" "Frontend"

# Check database

echo -n "Database: "

docker compose exec -T db pg_isready -U esxi_admin > /dev/null 2>&1 && echo "✅ Healthy" || echo "❌ Not responding"

# Check Redis

echo -n "Redis: "

docker compose exec -T redis redis-cli ping > /dev/null 2>&1 && echo "✅ Healthy" || echo "❌ Not responding"

# Show running containers

echo ""

echo "📦 Running Containers:"

docker compose ps --format "table {{.Name}}\t{{.Status}}\t{{.Ports}}"
