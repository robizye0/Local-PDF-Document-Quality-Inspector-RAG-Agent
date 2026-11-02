#!/usr/bin/env bash
# quickstart.sh — spin up the entire stack with one command
set -euo pipefail

echo "🔧 SpecCheck Quickstart"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# Check Docker is available
if ! command -v docker &>/dev/null; then
    echo "❌ Docker is not installed. Please install Docker Desktop first."
    exit 1
fi

echo "✅ Docker found"

# Check for required model in Ollama
if ! docker compose exec -T ollama ollama list 2>/dev/null | grep -q "qwen2.5:7b"; then
    echo "📦 Pulling qwen2.5:7b (first run only)..."
    docker compose exec ollama ollama pull qwen2.5:7b
else
    echo "✅ Model already present"
fi

echo "🚀 Starting services..."
docker compose up -d

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "✅ SpecCheck is running!"
echo ""
echo "  🌐  UI:            http://localhost:8000"
echo "  📚  Swagger API:   http://localhost:8000/docs"
echo "  🔍  Health check:  http://localhost:8000/health"
echo "  🤖  Ollama:        http://localhost:11434"
echo ""
echo "  To stop:   docker compose down"
echo "  To logs:   docker compose logs -f api"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
