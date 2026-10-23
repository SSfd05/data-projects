# 把项目传到 GitHub

两个项目的**本地仓库已经建好并提交了**，只差远端。你需要做的只有三步。

> ⚠️ 先说一件要紧的事：`wechat-ledger/cloudfunctions/voice/config.json` 里是**真实的腾讯云 SecretId / SecretKey**。
> 这个文件已经从 git 里移除了（`.gitignore` 已忽略，另留了 `config.example.json` 作模板），
> 但工作区根目录的 `wechat-ledger.zip` 里**还带着这份密钥**。如果那个 zip 发给过别人，
> 请立刻去腾讯云控制台把这组密钥删掉重建。

---

## 第 1 步：在 GitHub 建两个空仓库

打开 https://github.com/new ，建两个仓库，**都不要勾选** Add a README / .gitignore / license：

| 仓库名 | 说明 |
| --- | --- |
| `wechat-ledger` | 拾光账本小程序 |
| `bank-campaign` | 银行营销响应分析 |

公开（Public）即可，简历上放链接需要公开仓库。

## 第 2 步：一键推送

在 PowerShell 里执行（把 `你的用户名` 换成 GitHub 用户名）：

```powershell
cd "D:\Users\八岐\Documents\deepseek-harness\default-workspace\portfolio"
.\push.ps1 -User 你的用户名
```

第一次推送会弹出登录窗口，选 "Sign in with your browser" 授权即可。

## 第 3 步：检查

- https://github.com/你的用户名/wechat-ledger
- https://github.com/你的用户名/bank-campaign

打开 `bank-campaign`，README 里的 ROI 图应该能直接显示；`reports/findings.md` 是可以点开看的结论文档。

---

## 如果推送超时

GitHub 在国内经常连不上（这台机器上 `raw.githubusercontent.com` 就已经超时了）。两个办法：

**办法一：改用 Gitee（推荐，最省事）**

在 gitee.com 建两个同名仓库，然后：

```powershell
.\push.ps1 -User 你的Gitee用户名 -Host gitee.com
```

**办法二：开代理后重试**

```powershell
$env:HTTPS_PROXY = "http://127.0.0.1:7890"   # 换成你自己的代理端口
.\push.ps1 -User 你的用户名
```

---

## 附：以后怎么提交

```powershell
$git = "D:\Users\八岐\Documents\deepseek-harness\default-workspace\portfolio\tools\git\cmd\git.exe"
cd "D:\Users\八岐\Documents\deepseek-harness\default-workspace\portfolio\bank-campaign"
& $git add -A
& $git commit -m "更新指标计算"
& $git push
```

这台机器没有装系统级 git，用的是同目录下免安装的便携版（`portfolio/tools/git`）。
