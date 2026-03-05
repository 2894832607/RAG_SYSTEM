$ErrorActionPreference = 'Stop'

$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$python = Join-Path $root '.venv\Scripts\python.exe'
$backendEnvFile = Join-Path $root 'backend\local-env.ps1'
$aiEnvFile = Join-Path $root 'ai-service\local-env.ps1'
$frontendUrl = 'http://127.0.0.1:5173'
$backendHealthUrl = 'http://127.0.0.1:8080/actuator/health'
$aiHealthUrl = 'http://127.0.0.1:8000/ai/health'

function Ensure-MySqlServiceRunning {
  $candidateNames = @('MySQL80', 'MySQL', 'mysql', 'MariaDB', 'mariadb')
  $service = $null

  foreach ($name in $candidateNames) {
    $service = Get-Service -Name $name -ErrorAction SilentlyContinue
    if ($null -ne $service) { break }
  }

  if ($null -eq $service) {
    $service = Get-Service | Where-Object { $_.Name -match 'mysql|mariadb' } | Select-Object -First 1
  }

  if ($null -eq $service) {
    Write-Host "MySQL service not found. Please ensure MySQL is installed and running."
    return
  }

  if ($service.Status -eq 'Running') {
    Write-Host "MySQL service is already running: $($service.Name)"
    return
  }

  # 先尝试普通启动，如果权限不足则自动提权
  # 同时处理可能被禁用的情况（启动类型变为 Disabled）
  try {
    Start-Service -Name $service.Name -ErrorAction Stop
    Write-Host "MySQL service started: $($service.Name)"
  } catch {
    Write-Host "Attempting to start MySQL with elevated privileges..."
    try {
      $svcName = $service.Name
      # 提权同时恢复启动类型为 Automatic 并启动服务
      $elevatedCmd = "Set-Service '$svcName' -StartupType Automatic; Start-Service '$svcName'"
      $p = Start-Process powershell -Verb RunAs -ArgumentList '-NoProfile', '-Command', $elevatedCmd -Wait -PassThru -ErrorAction Stop
      Start-Sleep -Seconds 3
      $service.Refresh()
      if ($service.Status -eq 'Running') {
        Write-Host "MySQL service started with elevated privileges: $($service.Name)"
      } else {
        Write-Host "WARNING: MySQL service still not running after elevation. Check Windows Event Log."
      }
    } catch {
      Write-Host "Failed to start MySQL service ($($service.Name)). Please start it manually as Administrator."
    }
  }
}

function Ensure-PortFree {
  param(
    [int]$Port
  )

  $connections = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue
  if ($null -eq $connections) {
    return
  }

  $processIds = $connections | Select-Object -ExpandProperty OwningProcess -Unique
  foreach ($processId in $processIds) {
    try {
      $proc = Get-Process -Id $processId -ErrorAction SilentlyContinue
      $name = if ($null -ne $proc) { $proc.ProcessName } else { 'unknown' }
      Stop-Process -Id $processId -Force -ErrorAction Stop
      Write-Host "Freed port $Port by stopping PID=$processId ($name)"
    } catch {
      Write-Host "Failed to free port $Port from PID=${processId}: $($_.Exception.Message)"
    }
  }
  # 等待端口完全释放
  $waitDeadline = (Get-Date).AddSeconds(10)
  while ((Get-Date) -lt $waitDeadline) {
    $still = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue
    if ($null -eq $still) { break }
    Start-Sleep -Milliseconds 500
  }
}

function Wait-HttpReady {
  param(
    [string]$Url,
    [int]$TimeoutSeconds = 40
  )

  $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
  while ((Get-Date) -lt $deadline) {
    try {
      $res = Invoke-WebRequest -Uri $Url -UseBasicParsing -TimeoutSec 3
      if ($res.StatusCode -ge 200 -and $res.StatusCode -lt 600) {
        return $res.StatusCode
      }
    } catch [System.Net.WebException] {
      # 4xx/5xx responses still mean the server is up
      $webResponse = $_.Exception.Response
      if ($null -ne $webResponse) {
        return [int]$webResponse.StatusCode
      }
      Start-Sleep -Milliseconds 800
    } catch {
      Start-Sleep -Milliseconds 800
    }
  }
  return 'TIMEOUT'
}

if (-not (Test-Path $python)) {
  Write-Error "Python virtual env not found: $python"
}

if (Test-Path $backendEnvFile) {
  . $backendEnvFile
  Write-Host "Loaded backend env from backend/local-env.ps1"
} else {
  Write-Host "backend/local-env.ps1 not found, backend may fail if DB env vars are missing."
}

if (Test-Path $aiEnvFile) {
  . $aiEnvFile
  Write-Host "Loaded AI env from ai-service/local-env.ps1"
} else {
  Write-Host "ai-service/local-env.ps1 not found, AI service will use fallback config."
}

Ensure-MySqlServiceRunning
Ensure-PortFree -Port 8000
Ensure-PortFree -Port 8080
Ensure-PortFree -Port 5173

Write-Host "[1/3] Starting AI service on 8000..."
$aiStartCmd = if (Test-Path $aiEnvFile) {
  "Set-Location '$root\ai-service'; `$env:PYTHONPATH='.'; . '$aiEnvFile'; & '$python' -m uvicorn app.main:app --host 127.0.0.1 --port 8000"
} else {
  "Set-Location '$root\ai-service'; `$env:PYTHONPATH='.'; & '$python' -m uvicorn app.main:app --host 127.0.0.1 --port 8000"
}
Start-Process powershell -ArgumentList @('-NoExit', '-Command', $aiStartCmd)

Write-Host "[2/3] Starting backend service on 8080..."
$backendJar = Join-Path $root 'backend\target\poetry-visualization-0.1.0.jar'
if (-not (Test-Path $backendJar)) {
  Write-Host "ERROR: Backend jar not found at $backendJar. Run 'mvn package -DskipTests' in backend/ first."
  exit 1
}
$backendStartCmd = if (Test-Path $backendEnvFile) {
  ". '$backendEnvFile'; java -jar '$backendJar'"
} else {
  "java -jar '$backendJar'"
}
Start-Process powershell -ArgumentList @('-NoExit', '-Command', $backendStartCmd)

Write-Host "[3/3] Starting frontend service on 5173..."
Start-Process powershell -ArgumentList @(
  '-NoExit',
  '-Command',
  "Set-Location '$root\frontend'; npm run dev"
)

Write-Host "Startup commands sent."
Write-Host "AI: $aiHealthUrl"
Write-Host "Backend: $backendHealthUrl"
Write-Host "Frontend: $frontendUrl"
Write-Host "Note: Backend requires MySQL with schema in backend/sql/schema.sql"

Write-Host "Waiting for services to be ready (backend may take ~60s)..."
$aiCode = Wait-HttpReady -Url $aiHealthUrl -TimeoutSeconds 60
# 后端 /actuator/health 在DB连接异常时返回503但服务本身可用，所以改用根路径或登录接口探测
$backendCode = Wait-HttpReady -Url 'http://127.0.0.1:8080/api/v1/auth/login' -TimeoutSeconds 90
$frontendCode = Wait-HttpReady -Url $frontendUrl -TimeoutSeconds 30
Write-Host "- AI      $aiHealthUrl -> $aiCode"
Write-Host "- Backend $backendHealthUrl -> $backendCode"
Write-Host "- Frontend $frontendUrl -> $frontendCode"

if ($backendCode -ne 'TIMEOUT' -and $frontendCode -ne 'TIMEOUT') {
  Write-Host "All services ready! Opening browser..."
  Start-Process $frontendUrl
  Write-Host "Browser opened: $frontendUrl"
} else {
  Write-Host "WARNING: Some services are not healthy. Check the startup windows."
  Write-Host "Backend: $backendCode  Frontend: $frontendCode"
  Write-Host "You can still open the browser manually when ready: $frontendUrl"
}
