# 发布到 GitHub：前置条件与验证

本地审查通过只是第一步。真正推上去会卡在账号、权限、凭据这些与文件内容无关的地方。
本文覆盖「从本地仓库到远端可访问」的完整链路。

---

## 一、发布前检查

缺任何一项都会在中途失败，先一次性确认：

| 项 | 检查命令 | 失败表现 |
|---|---|---|
| gh 已安装 | `gh --version` | command not found |
| 已登录 | `gh auth status` | not logged into any GitHub hosts |
| token 含 `workflow` scope | `gh auth status` 看 scopes 行 | push 被整次拒绝（见下） |
| git 凭据助手 | `git config --global --get-regexp credential` | push 卡在 Username 提示 |
| git 身份 | `git config user.name` / `user.email` | commit 失败或作者信息错误 |
| 换行归一 | 存在 `.gitattributes` | 提交后出现全文件 diff |

gh 不在 PATH 时（Windows 常见，安装后需新开终端）：

```powershell
& "C:\Program Files\GitHub CLI\gh.exe" auth status
```

---

## 二、认证与授权

```bash
gh auth login --hostname github.com --git-protocol https --web
gh auth setup-git
```

`auth setup-git` 会写入：

```
credential.https://github.com.helper = !'...gh.exe' auth git-credential
```

没有它，`git push` 会退回账号密码提示；在非交互环境（AI agent、CI、后台进程）里会**永久挂起**，看起来像网络慢。

### workflow scope 陷阱

仓库里只要有 `.github/workflows/*.yml`，GitHub 要求 token 额外具备 `workflow` scope，否则：

```
! [remote rejected] HEAD -> main (refusing to allow an OAuth App to
  create or update workflow `.github/workflows/audit.yml` without `workflow` scope)
```

这是 OAuth App 的 scope 限制，**与仓库权限无关**，仓库 owner 也一样被拒。

```bash
gh auth refresh -s workflow
```

成功后 `gh auth status` 应显示 `Token scopes: 'gist', 'read:org', 'repo', 'workflow'`。

### 非交互环境

```powershell
$env:GIT_TERMINAL_PROMPT = "0"
```

让它快速失败而不是等待输入。

---

## 三、创建并推送

```bash
gh repo create <owner>/<name> --public --source . --remote origin --push \
  --description "<一句话定位>"
gh repo edit <owner>/<name> --add-topic opencode,skill,open-source
```

注意：

- `--push` 失败时**仓库已经创建**（空仓库）。重试只需 `git push -u origin main`，不要重复执行 `repo create`（会报名字已存在）。
- `repo create` 会自动把 remote 命名为 `origin`；已有 remote 时会冲突，先 `git remote -v` 确认。
- 推送成功后的输出是 `* [new branch] main -> main`，不是报错。

---

## 四、远端验证清单

创建成功 ≠ 发布成功。逐项确认：

| 项 | 命令 | 期望 |
|---|---|---|
| 可见性 | `gh repo view --json visibility` | `PUBLIC` |
| 默认分支 | `gh repo view --json defaultBranchRef` | `main` |
| 文件齐全 | `gh api repos/{o}/{r}/git/trees/main?recursive=1 --jq '.tree[].path'` | 含 `LICENSE`、`README.md`、`.github/workflows` |
| 许可证识别 | `gh api repos/{o}/{r}/license --jq '.license.spdx_id'` | `MIT` 等 |
| Topics | `gh repo view --json repositoryTopics` | 已设置 |
| CI | `gh run list --limit 3` | `success` |
| Release | `gh release view v1.0.0` | 已发布 |

GitHub 识别不出 LICENSE 通常有两个原因：文件名不在白名单，或正文不是标准全文。见 `licenses.md`。

---

## 五、CI 双跑：本地绿不等于远端绿

同一份代码，本地和 CI 的扫描结果可能不同：

- **扫描路径不同**：本地可能还没 `git init`，走的是"非 git 降级扫描"；CI 必然走 git 模式
- **历史不同**：本地浅克隆或未提交时，历史扫描覆盖不到
- **平台差异**：Linux 区分大小写，路径分隔符不同，编码与 BOM 处理不同

所以发布后**必须看第一次 CI 结果**，不能因为本地退出码 0 就收工。

本次实践就踩到了：CI 的历史扫描缺少工作区扫描的同等误报过滤，把文档里的 `postgres://user:pass@host/db` 和私钥示例判成 P0，而本地因为两处逻辑写在不同函数里没暴露出来。

**教训：同一套检测逻辑必须在所有扫描路径复用**（工作区 / 已跟踪 / 历史），否则必然出现"本地绿、CI 红"。修复方式是把匹配与过滤抽成一个共用函数，而不是在每条路径各写一遍。

---

## 六、常见错误对照

| 报错 / 现象 | 原因 | 修复 |
|---|---|---|
| `refusing to allow an OAuth App to create or update workflow` | 缺 `workflow` scope | `gh auth refresh -s workflow` |
| `could not read Username for 'https://github.com'` | 无凭据且非交互 | `gh auth setup-git`，并设 `GIT_TERMINAL_PROMPT=0` |
| push 长时间无输出 | 等待凭据输入 | 停掉进程，检查 `credential.helper` |
| `remote: Repository not found` | 无权限或 owner/仓库名错 | `gh auth status` 核对账号 |
| `GraphQL: Could not resolve to a Repository` | 仓库尚未创建 | 先 `repo create` |
| `failed to push some refs` 且远端已有提交 | 远端有初始 commit | `git pull --rebase origin main` 后再推 |
| CI 失败但本地通过 | 扫描路径 / 平台差异 | `gh run view <id> --log-failed` |
| 徽章一直显示 failing | badge 指向不存在的 workflow | 核对 `.github/workflows/<name>.yml` 文件名 |

---

## 七、发布后的收尾

1. README 加 CI 与许可证徽章，让主页自证状态。
2. 打 tag 并发 Release：写清功能、安装方式、许可证。
3. 开分支保护：必需状态检查（用 CI 的 job 名，如 `audit`）+ 禁止强推 + 禁止删除。
4. 确认 Secret Scanning 与 Push Protection 已开启（公开仓库免费）。
5. 本地目录与远端保持同步，避免"桌面改了没推"。

### 分支保护的注意点

- 必需状态检查的 context 是**job 名**，不是 workflow 名。先用 `gh api repos/{o}/{r}/commits/main/check-runs --jq '.check_runs[].name'` 确认。
- 个人项目不要设 `required_pull_request_reviews`（无法自己批准自己的 PR），否则只能走管理员绕过。
- `enforce_admins: false` 保留 owner 直推能力；要完全锁死再设为 `true`。

```bash
gh api -X PUT repos/{o}/{r}/branches/main/protection --input protection.json
```

```json
{
  "required_status_checks": { "strict": false, "contexts": ["audit"] },
  "enforce_admins": false,
  "required_pull_request_reviews": null,
  "restrictions": null,
  "allow_force_pushes": false,
  "allow_deletions": false,
  "required_conversation_resolution": true
}
```
