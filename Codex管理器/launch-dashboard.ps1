$ErrorActionPreference = 'Stop'

$scanner = Join-Path $PSScriptRoot '零件箱\Scan-CodexInventory.ps1'
$report = Join-Path $PSScriptRoot '零件箱\库存仪表盘.html'

try {
    & $scanner
    if (-not (Test-Path -LiteralPath $report -PathType Leaf)) {
        throw '库存报告没有生成。'
    }
    Start-Process -FilePath $report
}
catch {
    Write-Host "生成 Codex 库存报告失败：$($_.Exception.Message)" -ForegroundColor Red
    Read-Host '按 Enter 键关闭'
    exit 1
}
