# quickstart.ps1 — Windows PowerShell one-liner
param()

Write-Host ""
Write-Host "🔧 SpecCheck Quickstart (Windows)" -ForegroundColor Cyan
Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor DarkGray

if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    Write-Host "❌ Docker is not installed. Install Docker Desktop first." -ForegroundColor Red
    exit 1
}
Write-Host "✅ Docker found" -ForegroundColor Green

Write-Host "🚀 Starting services (this may take ~2 min on first run)..." -ForegroundColor Yellow
docker compose up -d

Write-Host ""
Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor DarkGray
Write-Host "✅ SpecCheck is running!" -ForegroundColor Green
Write-Host ""
Write-Host "  🌐  UI:            http://localhost:8000"
Write-Host "  📚  Swagger API:   http://localhost:8000/docs"
Write-Host "  🔍  Health check:  http://localhost:8000/health"
Write-Host "  🤖  Ollama:        http://localhost:11434"
Write-Host ""
Write-Host "  To stop:   docker compose down"
Write-Host "  To logs:   docker compose logs -f api"
Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor DarkGray
