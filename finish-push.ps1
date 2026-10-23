# 一键完成 GitHub 推送（两个仓库）
#
# 用法：
#   cd "D:\Users\八岐\Documents\deepseek-harness\default-workspace\portfolio"
#   .\finish-push.ps1
#
# 运行后：
#   1. 输入 GitHub 用户名（不是邮箱）
#   2. 自动设置远端并推送
#   3. 第一次推送会弹出浏览器，登录 GitHub 点授权即可
#
# 如果你的第二个仓库还叫 bank-campaign（没改名），可以这样跑：
#   .\finish-push.ps1 -PortfolioRepo bank-campaign

param(
    [string]$User,
    [string]$PortfolioRepo = "data-projects"
)

$ErrorActionPreference = "Stop"

$here = Split-Path -Parent $MyInvocation.MyCommand.Path
$git = Join-Path $here "tools\git\cmd\git.exe"
if (-not (Test-Path $git)) { throw "找不到 git：$git" }

# 用浏览器授权（GCM），不把密码落盘
& $git config --global credential.helper manager
& $git config --global user.name  "黄鑫"
& $git config --global user.email "3066089845@qq.com"

if ([string]::IsNullOrWhiteSpace($User)) {
    Write-Host ""
    Write-Host "GitHub 用户名不是邮箱。打开 https://github.com ，右上角头像旁边就是你现在的用户名。"
    $User = Read-Host "请输入 GitHub 用户名"
}
if ([string]::IsNullOrWhiteSpace($User)) { throw "用户名不能为空" }
$User = $User.Trim()

$repos = [ordered]@{
    "wechat-ledger" = @{
        path = (Join-Path (Split-Path -Parent $here) "wechat-ledger")
        repo = "wechat-ledger"
    }
    "data-projects" = @{
        path = $here
        repo = $PortfolioRepo
    }
}

$ok = 0
foreach ($label in $repos.Keys) {
    $path = $repos[$label].path
    $repo = $repos[$label].repo
    $url = "https://github.com/$User/$repo.git"

    Write-Host ""
    Write-Host "=== $label  ->  $url ===" -ForegroundColor Cyan
    Push-Location $path
    try {
        if (-not (Test-Path (Join-Path $path ".git"))) {
            throw "这里不是 git 仓库：$path"
        }
        $remotes = & $git remote
        if ($remotes -contains "origin") {
            & $git remote set-url origin $url
        }
        else {
            & $git remote add origin $url
        }

        Write-Host "正在推送，如果弹出浏览器请登录并授权……" -ForegroundColor Yellow
        & $git push -u origin main
        if ($LASTEXITCODE -eq 0) {
            $ok++
            Write-Host "成功 -> https://github.com/$User/$repo" -ForegroundColor Green
        }
        else {
            Write-Host "失败。常见原因：仓库不存在、用户名填错、浏览器授权没完成。" -ForegroundColor Red
        }
    }
    catch {
        Write-Host "出错：$($_.Exception.Message)" -ForegroundColor Red
    }
    finally {
        Pop-Location
    }
}

Write-Host ""
if ($ok -eq 2) {
    Write-Host "两个仓库都推好了：https://github.com/$User" -ForegroundColor Green
    Write-Host "下一步：把简历里的 github.com/（待填写）改成这个地址。"
}
else {
    Write-Host "成功 $ok / 2 个。" -ForegroundColor Yellow
    Write-Host "检查：1) 用户名是否填成邮箱了  2) 仓库是否已经建好  3) 浏览器授权是否点了"
}
