# 补下载零售数据（给 A / B 两个项目用）
# 用法： .\get-retail-data.ps1
#
# 说明：UCI 的服务器从国内下载很慢（实测约 13KB/s，整份文件要一小时以上），
#      所以这里做成"慢慢下、断了能续、下完自动校验"的形式。
#      下载完成后 A 和 B 都能直接跑。

$ErrorActionPreference = "Stop"
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
$target = Join-Path $here "A-offline-warehouse\data\raw"
New-Item -ItemType Directory -Force -Path $target | Out-Null
$out = Join-Path $target "Online Retail.xlsx"
$tmp = Join-Path $target "download.tmp"

$urls = @(
    "https://archive.ics.uci.edu/ml/machine-learning-databases/00352/Online%20Retail.xlsx",
    "https://archive.ics.uci.edu/static/public/352/online+retail.zip"
)

if (Test-Path $out) {
    $mb = [math]::Round((Get-Item $out).Length / 1MB, 2)
    Write-Host "已存在 $out （$mb MB），无需下载。" -ForegroundColor Green
    exit 0
}

foreach ($url in $urls) {
    Write-Host "尝试下载：$url"
    try {
        # 已下过一部分就接着下
        if (Test-Path $tmp) {
            $existing = (Get-Item $tmp).Length
            Write-Host "  检测到临时文件 $([math]::Round($existing/1MB,2)) MB，尝试续传"
            curl.exe -L -C - --retry 5 --retry-delay 5 -o $tmp $url
        }
        else {
            curl.exe -L --retry 5 --retry-delay 5 -o $tmp $url
        }
        if ($LASTEXITCODE -ne 0) { throw "curl 退出码 $LASTEXITCODE" }

        # 校验：xlsx 和 zip 都是 PK 开头
        $head = [System.IO.File]::ReadAllBytes($tmp)[0..1]
        if ($head[0] -ne 0x50 -or $head[1] -ne 0x4B) {
            throw "下载的文件不是有效的 xlsx/zip（文件头不对），可能被截断"
        }

        if ($url.EndsWith(".zip")) {
            Expand-Archive -LiteralPath $tmp -DestinationPath $target -Force
            Remove-Item $tmp -Force
        }
        else {
            Move-Item -LiteralPath $tmp -Destination $out -Force
        }
        Write-Host "完成：$target" -ForegroundColor Green
        exit 0
    }
    catch {
        Write-Host "  失败：$($_.Exception.Message)" -ForegroundColor Yellow
    }
}

Write-Host "两个地址都失败了。可以改用镜像或手动下载，放到：" -ForegroundColor Red
Write-Host "  $target"
