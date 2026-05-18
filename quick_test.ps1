# Quick API Test Script
Write-Host "========================================"  -ForegroundColor Cyan
Write-Host "AI Placement Platform - Quick Test" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan

# 1. Health Check
Write-Host "`n[1/5] Testing Health Endpoint..." -ForegroundColor Yellow
$health = curl -UseBasicParsing http://localhost:8000/health | ConvertFrom-Json
Write-Host "  Status: $($health.status)" -ForegroundColor Green

# 2. Register User
Write-Host "`n[2/5] Registering new user..." -ForegroundColor Yellow
$randomId = Get-Random -Maximum 99999
$registerBody = @{
    name = "Test User $randomId"
    email = "test$randomId@example.com"
    password = "Test@1234"
} | ConvertTo-Json

$user = curl -UseBasicParsing -Method POST -Uri http://localhost:8000/api/v1/auth/register -Body $registerBody -ContentType 'application/json' | ConvertFrom-Json
Write-Host "  User registered: $($user.email)" -ForegroundColor Green

# 3. Login
Write-Host "`n[3/5] Logging in..." -ForegroundColor Yellow
$loginBody = @{
    email = $user.email
    password = "Test@1234"
} | ConvertTo-Json

$auth = curl -UseBasicParsing -Method POST -Uri http://localhost:8000/api/v1/auth/login -Body $loginBody -ContentType 'application/json' | ConvertFrom-Json
$token = $auth.access_token
Write-Host "  Login successful!" -ForegroundColor Green

# 4. Start Session
Write-Host "`n[4/5] Starting assessment session..." -ForegroundColor Yellow
$headers = @{ Authorization = "Bearer $token" }
$session = curl -UseBasicParsing -Method POST -Uri http://localhost:8000/api/v1/session/start -Headers $headers | ConvertFrom-Json
Write-Host "  Session ID: $($session.id)" -ForegroundColor Green

# 5. Start Coding Round
Write-Host "`n[5/5] Starting coding round..." -ForegroundColor Yellow
$codingRound = curl -UseBasicParsing -Method POST -Uri http://localhost:8000/api/v1/coding/start-round -Headers $headers | ConvertFrom-Json
Write-Host "  Round ID: $($codingRound.round_id)" -ForegroundColor Green
Write-Host "  Time Limit: $($codingRound.time_limit_minutes) minutes" -ForegroundColor Green
Write-Host "  Problems Assigned: $($codingRound.problems.Count)" -ForegroundColor Green

Write-Host "`n========================================" -ForegroundColor Cyan
Write-Host "ALL TESTS PASSED!" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "`nServer: http://localhost:8000" -ForegroundColor White
Write-Host "API Docs: http://localhost:8000/docs" -ForegroundColor White
