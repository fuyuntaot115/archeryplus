# Windows 部署启动脚本（替代 Linux/macOS 的 startup.sh + supervisord）
# 说明:
#   - Windows 上 gunicorn/supervisord 不可用，使用 waitress（纯 Python WSGI 服务器）
#   - 首次使用请先执行: .\scripts\deploy_windows.ps1 -Init
# 用法:
#   .\scripts\start_windows.ps1            # 启动 Web(8888) + qcluster
#   .\scripts\start_windows.ps1 -WebOnly   # 仅启动 Web，不启动 qcluster
#   .\scripts\start_windows.ps1 -Port 9123 # 指定端口

param(
    [int]$Port = 8888,
    [switch]$WebOnly
)

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $PSScriptRoot
Set-Location $ProjectRoot

# 自动定位 Python 解释器
if (Test-Path "$ProjectRoot\.venv\Scripts\python.exe") {
    $PythonBin = "$ProjectRoot\.venv\Scripts\python.exe"
} elseif (Test-Path "$ProjectRoot\venv_archery\Scripts\python.exe") {
    $PythonBin = "$ProjectRoot\venv_archery\Scripts\python.exe"
} elseif (Test-Path "$ProjectRoot\venv\Scripts\python.exe") {
    $PythonBin = "$ProjectRoot\venv\Scripts\python.exe"
} else {
    $PythonBin = "python"
}

Write-Host "使用 Python: $PythonBin" -ForegroundColor Cyan

# 1. 收集静态文件
Write-Host "==> 收集静态文件 (collectstatic) ..." -ForegroundColor Cyan
& $PythonBin manage.py collectstatic -v0 --noinput
if ($LASTEXITCODE -ne 0) { throw "collectstatic 失败" }

# 2. 启动 qcluster（后台进程，处理异步任务/工作流）
if (-not $WebOnly) {
    Write-Host "==> 启动 django-q cluster（异步任务队列）..." -ForegroundColor Cyan
    $qcluster = Start-Process -FilePath $PythonBin -ArgumentList "manage.py", "qcluster" -WindowStyle Hidden -PassThru
    Write-Host "qcluster 已启动 (PID: $($qcluster.Id))"
} else {
    Write-Host "==> 跳过 qcluster（-WebOnly）" -ForegroundColor Yellow
}

# 3. 启动 Web 服务（waitress，WSGI 逻辑见 scripts/wsgi_waitress.py）
Write-Host "==> 启动 Web 服务 (waitress, 端口 $Port) ..." -ForegroundColor Cyan
Write-Host "    Ctrl+C 停止。访问 http://127.0.0.1:$Port"
& $PythonBin "$ProjectRoot\scripts\wsgi_waitress.py" $Port
