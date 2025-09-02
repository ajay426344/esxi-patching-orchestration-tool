#!/bin/bash

echo "🚀 ESXi Orchestrator - Quick Start"

echo "================================="

# Check prerequisites

command -v docker >/dev/null 2>&1 || { echo "❌ Docker is required but not installed. Aborting." >&2; exit 1; }

command -v docker compose >/dev/null 2>&1 || { echo "❌ Docker Compose is required but not installed. Aborting." >&2; exit 1; }

# Create necessary directories

echo "📁 Creating directories..."

mkdir -p data/{patches,logs,ssl} 

mkdir -p backups

mkdir -p ansible/patches

# Build and start services

echo "🔨 Building Docker images..."

docker compose build

echo "🚀 Starting services..."

docker compose up -d

# Wait for services to be healthy

echo "⏳ Waiting for services to be healthy..."

sleep 15

# Check service status

echo "✅ Checking service status..."

docker compose ps

echo ""

echo "🎉 ESXi Orchestrator is ready!"

echo "================================="

echo "📊 Dashboard: http://localhost"

echo "🔧 API Docs: http://localhost:8000/docs"

echo ""

echo "📖 Admin Login: ajay / Ajay@426344"
