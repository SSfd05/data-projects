# 一键完成 GitHub 推送
# 用法：在 PowerShell 里执行
#   cd "D:\Users\八岐\Documents\deepseek-harness\default-workspace\portfolio"
#   .\finish-push.ps1
#
# 运行后会：
#   1. 问你 GitHub 用户名（不是邮箱）
#   2. 给两个仓库设置远端地址
#   3. 推送 —— 第一次会弹出浏览器让你登录 GitHub，点一下授权即可
#   4. 打印两个仓库的地址，方便你核对

$ErrorActionPreference = "Stop"

$here = Split-Path -Parent $MyInvocation.MyCommand.Path
$git = Join-Path $here "tools\git\cmd\git.exe"
if (-not (Test-Path $git)) { throw "找不到 git：$git" }

# 用浏览器授权，不把密码存在磁盘上
& $git config --global credential.helper manager
& $git config --global user.name  "黄鑫"
& $git config --global user.email "3066089845@qq.com"

Write-Host ""
$user = Read-Host "请输入你的 GitHub 用户名（比如 zhangsan，不是邮箱）"
if ([string]::IsNullOrWhiteSpace($user)) { throw "用户名不能为空" }
$user = $user.Trim()

$repos = [ordered]@{
    "wechat-ledger" = (Join-Path (Split-Path -Parent $here) "wechat-ledger")
    "bank-campaign" = (Join-Path $here "bank-campaign")
}

$ok = 0
foreach ($name in $repos.Keys) {
    $path = $repos[$name]
    $url = "https://github.com/$user/$name.git"
    Write-Host ""
    Write-Host "=== $name ===" -ForegroundColor Cyan
    Push-Location $path
    try {
        $remotes = & $git remote
        if ($remotes -contains "origin") {
            & $git remote set-url origin $url
        }
        else {
            & $git remote add origin $url
        }
        Write-Host "远端：$url"

        if ($name -eq "bank-campaign") {
            Write-Host "提示：这个仓库可能还没有提交过 bank-campaign 项目，先用 A/B/C 三个新项目替换。" -ForegroundColor Yellow
        }

        & $git push -u origin main
        if ($LASTEXITCODE -eq 0) {
            $ok++
            Write-Host "推送成功 -> https://github.com/$user/$name" -ForegroundColor Green
        }
        else {
            Write-Host "推送失败，看上面的报错。" -ForegroundColor Red
        }
    }
    finally {
        Pop-Location
    }
}

Write-Host ""
if ($ok -eq 2) {
    Write-Host "两个仓库都推好了。" -ForegroundColor Green
    Write-Host "打开确认：https://github.com/$user"
}
else {
    Write-Host "成功 $ok / 2 个。常见原因：" -ForegroundColor Yellow
    Write-Host "  - 用户名填错（要填 GitHub 用户名，不是邮箱）"
    Write-Host "  - 仓库名和你建的不一致"
    Write-Host "  - 浏览器登录没完成"
}
