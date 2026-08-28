# Windows 部署管理脚本（对应 Linux/macOS 的 admin.sh）
# 用法:
#   .\scripts\deploy_windows.ps1 -Init        # 创建虚拟环境并安装依赖
#   .\scripts\deploy_windows.ps1 -Migrate     # 执行数据库迁移
#   .\scripts\deploy_windows.ps1 -AddUser     # 创建超级管理员
#   .\scripts\deploy_windows.ps1 -Check       # Django 系统检查

param(
    [switch]$Init,
    [switch]$Migrate,
    [switch]$AddUser,
    [switch]$Check
)

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $PSScriptRoot
Set-Location $ProjectRoot

$PythonBin = "python"

function Ensure-Venv {
    if (-not (Test-Path "$ProjectRoot\.venv\Scripts\python.exe")) {
        Write-Host "创建虚拟环境 .venv ..." -ForegroundColor Cyan
        & $PythonBin -m venv .venv
        if ($LASTEXITCODE -ne 0) { throw "创建虚拟环境失败" }
    }
    $script:PythonBin = "$ProjectRoot\.venv\Scripts\python.exe"
    Write-Host "虚拟环境 Python: $PythonBin" -ForegroundColor Cyan
}

if ($Init) {
    Ensure-Venv
    Write-Host "==> 安装依赖 requirements.txt ..." -ForegroundColor Cyan
    & $PythonBin -m pip install --upgrade pip
    & $PythonBin -m pip install -r requirements.txt
    # Windows 需要 waitress 作为 WSGI 服务器（gunicorn 不支持 Windows）
    & $PythonBin -m pip install waitress
    # 开发/测试依赖
    if (Test-Path "dev-requirements.txt") {
        & $PythonBin -m pip install -r dev-requirements.txt
    }
    Write-Host "依赖安装完成。请配置 .env 后执行 -Migrate" -ForegroundColor Green
}

if ($Migrate) {
    Ensure-Venv
    Write-Host "==> 执行数据库迁移 ..." -ForegroundColor Cyan
    & $PythonBin manage.py makemigrations sql
    & $PythonBin manage.py migrate
    Write-Host "迁移完成。请导入基础数据（如 auth_group 等）" -ForegroundColor Green
}

if ($AddUser) {
    Ensure-Venv
    Write-Host "==> 创建超级管理员 ..." -ForegroundColor Cyan
    & $PythonBin manage.py createsuperuser
}

if ($Check) {
    Ensure-Venv
    Write-Host "==> Django 系统检查 ..." -ForegroundColor Cyan
    & $PythonBin manage.py check
}

if (-not ($Init -or $Migrate -or $AddUser -or $Check)) {
    Write-Host @"
Windows 部署管理脚本用法:
  .\scripts\deploy_windows.ps1 -Init        # 创建虚拟环境并安装依赖
  .\scripts\deploy_windows.ps1 -Migrate     # 执行数据库迁移
  .\scripts\deploy_windows.ps1 -AddUser     # 创建超级管理员
  .\scripts\deploy_windows.ps1 -Check       # Django 系统检查

启动服务:
  .\scripts\start_windows.ps1               # 启动 Web + qcluster

运行测试:
  .\scripts\run_pytest.ps1
"@
}
