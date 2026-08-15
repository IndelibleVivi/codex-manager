$ErrorActionPreference = 'Stop'

$manager = Join-Path $PSScriptRoot '零件箱\Codex配置管理器.py'
$python = Get-Command 'python.exe' -ErrorAction SilentlyContinue

if (-not $python) {
    Write-Host '没有找到 Python 3。请先安装 Python 3，并勾选 Add python.exe to PATH。' -ForegroundColor Red
    Read-Host '按 Enter 键关闭'
    exit 1
}

try {
    & $python.Source $manager
    if ($LASTEXITCODE -ne 0) {
        throw "Codex 管理器退出，代码：$LASTEXITCODE"
    }
}
catch {
    Write-Host "启动 Codex 管理器失败：$($_.Exception.Message)" -ForegroundColor Red
    Read-Host '按 Enter 键关闭'
    exit 1
}
