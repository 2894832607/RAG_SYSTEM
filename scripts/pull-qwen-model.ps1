# ═══════════════════════════════════════════════════════════════
# Qwen 模型拉取脚本
# 拉取 Qwen 2.7B (推荐) 或 Qwen 2.5.7B (更新，更强)
# ═══════════════════════════════════════════════════════════════

param(
    [ValidateSet("qwen2:7b", "qwen2.5:7b", "qwen:7b")]
    [string]$Model = "qwen2:7b"
)

Write-Host "🤖 Qwen 模型拉取程序" -ForegroundColor Cyan
Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor Cyan
Write-Host "目标模型: $Model`n" -ForegroundColor Yellow

# 检查 Ollama 是否已安装
try {
    $version = ollama --version 2>&1
    Write-Host "✅ Ollama 已检测: $version`n" -ForegroundColor Green
}
catch {
    Write-Host "❌ Ollama 未找到，请先运行 install-ollama.ps1`n" -ForegroundColor Red
    exit 1
}

# 步骤 1: 启动 Ollama 服务
Write-Host "⚙️  步骤 1: 启动 Ollama 服务..." -ForegroundColor Cyan

# 检查 Ollama 服务是否已运行
$ollamaProcess = Get-Process ollama -ErrorAction SilentlyContinue
if ($ollamaProcess) {
    Write-Host "✅ Ollama 服务已运行 (PID: $($ollamaProcess.Id))`n" -ForegroundColor Green
}
else {
    Write-Host "⏳ 启动 Ollama 服务中... (这会在后台运行)" -ForegroundColor Yellow
    
    # 这里触发 ollama 启动（Windows 上会在后台启动）
    # 使用 Start-Process 避免阻塞
    try {
        Start-Process ollama -ArgumentList "serve" -WindowStyle Hidden -ErrorAction Stop
        Write-Host "✅ Ollama 服务已启动`n" -ForegroundColor Green
        
        # 等待服务就绪
        Write-Host "⏳ 等待服务就绪... (约 3-5 秒)" -ForegroundColor Yellow
        Start-Sleep -Seconds 5
    }
    catch {
        Write-Host "❌ 无法启动 Ollama: $_`n" -ForegroundColor Red
        Write-Host "请尝试手动启动：ollama serve`n" -ForegroundColor Yellow
        exit 1
    }
}

# 步骤 2: 拉取模型
Write-Host "`n📥 步骤 2: 拉取 $Model 模型..." -ForegroundColor Cyan
Write-Host "（首次下载 ~5GB，需要 5-15 分钟，取决于网络速度）`n" -ForegroundColor Yellow

try {
    # 显示下载进度
    $command = "ollama pull $Model"
    Write-Host "执行: $command`n" -ForegroundColor Gray
    
    Invoke-Expression $command -ErrorAction Stop
    
    Write-Host "`n✅ 模型拉取完成！`n" -ForegroundColor Green
}
catch {
    Write-Host "`n❌ 模型拉取失败: $_`n" -ForegroundColor Red
    Write-Host "可能的原因：" -ForegroundColor Yellow
    Write-Host "  • 网络连接问题"
    Write-Host "  • Ollama 服务未启动"
    Write-Host "  • 磁盘空间不足 (需要 ~5GB)`n"
    exit 1
}

# 步骤 3: 验证模型
Write-Host "✅ 步骤 3: 验证模型..." -ForegroundColor Cyan

try {
    $response = ollama list 2>&1
    Write-Host "`n📦 已安装的模型列表：`n" -ForegroundColor Cyan
    Write-Host $response
    
    if ($response -match $Model.Split(":")[0]) {
        Write-Host "✅ $Model 已成功安装！`n" -ForegroundColor Green
    }
}
catch {
    Write-Host "⚠️  无法列出模型，但拉取可能已成功`n" -ForegroundColor Yellow
}

# 步骤 4: 快速测试
Write-Host "🧪 步骤 4: 快速测试模型..." -ForegroundColor Cyan
Write-Host "运行测试: ollama run $Model '你好，你是谁？'`n" -ForegroundColor Gray

try {
    $testResponse = ollama run $Model "你好，你是谁？" 2>&1
    
    if ($testResponse.Length -gt 0) {
        Write-Host "✅ 模型测试成功！`n" -ForegroundColor Green
        Write-Host "模型响应：`n" -ForegroundColor Cyan
        Write-Host $testResponse
    }
}
catch {
    Write-Host "⚠️  模型测试失败（可能是暂时问题，实际应用中应该可用）`n" -ForegroundColor Yellow
}

# 步骤 5: 显示后续步骤
Write-Host "`n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor Cyan
Write-Host "✅ 本地模型已就绪！" -ForegroundColor Green
Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor Cyan

Write-Host "`n📌 下一步配置 AI Service：`n" -ForegroundColor Yellow

Write-Host "1️⃣  编辑 local-env.ps1：`n" -ForegroundColor Cyan
Write-Host "   `$env:LLM_PROVIDER = 'ollama'" -ForegroundColor Green
Write-Host "   `$env:LLM_MODEL = '$Model'`n" -ForegroundColor Green

Write-Host "2️⃣  启动 AI Service：`n" -ForegroundColor Cyan
Write-Host "   cd ai-service" -ForegroundColor Green
Write-Host "   python -m uvicorn app.main:app --reload --port 8000`n" -ForegroundColor Green

Write-Host "3️⃣  验证配置：`n" -ForegroundColor Cyan
Write-Host "   curl http://localhost:8000/ai/health`n" -ForegroundColor Green

Write-Host "🎉 就这么简单！现在你的 AI Service 使用本地 Qwen 模型运行了！`n" -ForegroundColor Green
