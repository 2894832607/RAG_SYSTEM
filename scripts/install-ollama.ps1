# ═══════════════════════════════════════════════════════════════
# Ollama 本地模型一键安装脚本
# 支持 Windows 10/11
# ═══════════════════════════════════════════════════════════════

Write-Host "🚀 Ollama 安装程序" -ForegroundColor Cyan
Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor Cyan

# 检查 Ollama 是否已安装
try {
    $version = ollama --version 2>&1
    Write-Host "✅ Ollama 已安装：$version" -ForegroundColor Green
    exit 0
}
catch {
    Write-Host "⚠️  Ollama 未检测到，准备安装..." -ForegroundColor Yellow
}

# 设置下载 URL
$downloadUrl = "https://ollama.ai/download/OllamaSetup.exe"
$installerPath = "$env:TEMP\OllamaSetup.exe"

Write-Host "`n📥 步骤 1: 下载 Ollama 安装程序..."
Write-Host "URL: $downloadUrl"
Write-Host "保存位置: $installerPath`n"

try {
    # 配置 TLS 1.2
    [System.Net.ServicePointManager]::SecurityProtocol = [System.Net.ServicePointManager]::SecurityProtocol -bor [System.Net.SecurityProtocolType]::Tls12
    
    # 下载
    Invoke-WebRequest -Uri $downloadUrl -OutFile $installerPath -UseBasicParsing -ErrorAction Stop
    
    if (Test-Path $installerPath) {
        $fileSize = (Get-Item $installerPath).Length / 1MB
        Write-Host "✅ 下载完成！文件大小: $([math]::Round($fileSize, 2)) MB`n" -ForegroundColor Green
    }
}
catch {
    Write-Host "❌ 下载失败: $_" -ForegroundColor Red
    Write-Host "`n📌 手动安装方案：`n" -ForegroundColor Yellow
    Write-Host "1. 访问 https://ollama.ai/download`n"
    Write-Host "2. 下载 Windows 版本 OllamaSetup.exe`n"
    Write-Host "3. 运行安装程序，按提示完成安装`n"
    Write-Host "4. 重启 PowerShell 或系统后，重新运行本脚本`n"
    exit 1
}

Write-Host "⚙️  步骤 2: 运行安装程序..."
Write-Host "（可能需要管理员权限）`n"

try {
    Start-Process -FilePath $installerPath -Wait -ErrorAction Stop
    Write-Host "✅ Ollama 安装完成！`n" -ForegroundColor Green
}
catch {
    Write-Host "❌ 安装失败: $_" -ForegroundColor Red
    Write-Host "请手动运行: $installerPath" -ForegroundColor Yellow
    exit 1
}

# 重新检查
Write-Host "✅ 步骤 3: 验证安装..."
try {
    $version = ollama --version 2>&1
    Write-Host "✅ Ollama 已成功安装！版本: $version`n" -ForegroundColor Green
}
catch {
    Write-Host "⚠️  Ollama 命令未找到，可能需要重启 PowerShell 或系统`n" -ForegroundColor Yellow
    Write-Host "请重启后运行以下命令来启动 Ollama：" -ForegroundColor Cyan
    Write-Host "`n  ollama serve`n" -ForegroundColor Green
    exit 0
}

Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor Cyan
Write-Host "📌 后续内容" -ForegroundColor Cyan
Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor Cyan
Write-Host "`n接下来，请运行模型拉取脚本：" -ForegroundColor Yellow
Write-Host "`n  powershell .scripts/pull-qwen-model.ps1`n" -ForegroundColor Green
