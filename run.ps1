# 一键运行三个项目（用带依赖的 Python，不用你配环境）
#
# 用法：
#   .\run.ps1 A     # 离线数仓
#   .\run.ps1 B     # 留存分析
#   .\run.ps1 C     # 出租车间分析

param(
    [Parameter(Mandatory = $true)]
    [ValidateSet('A', 'B', 'C')]
    [string]$Project
)

$ErrorActionPreference = "Stop"

$py = "C:\Users\八岐\.dsh\dsh-runtimes\dsh-primary-runtime\dependencies\python\python.exe"
if (-not (Test-Path $py)) { throw "找不到 Python：$py" }

$map = @{
    'A' = 'A-offline-warehouse'
    'B' = 'B-retention-analysis'
    'C' = 'C-taxi-sql'
}
$dir = Join-Path $PSScriptRoot $map[$Project]
if (-not (Test-Path $dir)) { throw "项目目录不存在：$dir" }

Write-Host ""
Write-Host "运行 $Project ：$($map[$Project])" -ForegroundColor Cyan
Write-Host "----------------------------------------"
Push-Location $dir
try {
    & $py -X utf8 src\run.py
    $code = $LASTEXITCODE
}
finally {
    Pop-Location
}

Write-Host "----------------------------------------"
if ($code -eq 0) {
    Write-Host "完成。结果在 $dir\reports\" -ForegroundColor Green
    Write-Host "先看 findings.md，再看 metrics.json，最后打开 figs 里的图。" -ForegroundColor Gray
}
else {
    Write-Host "运行失败，退出码 $code" -ForegroundColor Red
}
