$ports = @(5173, 8000, 8080)

foreach ($port in $ports) {
  $connections = Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue
  if ($null -ne $connections) {
    $processIds = $connections | Select-Object -ExpandProperty OwningProcess -Unique
    foreach ($processId in $processIds) {
      try {
        Stop-Process -Id $processId -Force -ErrorAction Stop
        Write-Host "已停止端口 $port 的进程 PID=$processId"
      } catch {
        Write-Warning "停止 PID=$processId 失败: $($_.Exception.Message)"
      }
    }
  }
}
