# Windows PowerShell 测试运行脚本（与 scripts/run_pytest.sh 对应）
# 用法: .\scripts\run_pytest.ps1 [pytest 参数]
# 首次运行会自动创建测试数据库（约需 1-3 分钟），之后可用 --reuse-db 加速

$ErrorActionPreference = "Stop"

# 自动定位 Python 解释器（优先项目虚拟环境）
if (Test-Path ".\.venv\Scripts\python.exe") {
    $PythonBin = ".\.venv\Scripts\python.exe"
} elseif (Test-Path ".\venv_archery\Scripts\python.exe") {
    $PythonBin = ".\venv_archery\Scripts\python.exe"
} elseif (Test-Path ".\venv\Scripts\python.exe") {
    $PythonBin = ".\venv\Scripts\python.exe"
} else {
    $PythonBin = "python"
}

# 默认参数：复用测试数据库加速（首次无库会自动创建）
$ArgsList = @("--reuse-db") + $args

& $PythonBin -m pytest @ArgsList
exit $LASTEXITCODE
