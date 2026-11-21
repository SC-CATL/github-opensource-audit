# 历史泄露的处置

## 一、先分清三种状态

| 状态 | 表现 | 处置 |
|---|---|---|
| 只在工作区 | 文件存在但从未提交 | 加 `.gitignore`，删掉即可 |
| 已提交但未推送 | `git log` 有，remote 没有 | 本地 `reset` / `rebase` 或 `filter-repo`，无需轮换（若从未离开本机） |
| 已推送到公开仓库 | 任何人都可能已 clone/fork/抓取 | **轮换凭据 + 清理历史 + 假设已泄露** |

第三条是最常见的误判：以为 `git rm` 再提交就完事，其实 `git show <旧commit>:path` 依然能看到。

---

## 二、铁律：先轮换，再清历史

顺序不能颠倒：

1. **吊销/轮换**泄露的凭据（API Key、数据库密码、私钥、令牌）。
2. 确认旧凭据已失效。
3. 再清理 git 历史。
4. 最后 force push。

原因：清理历史需要时间，期间旧 commit 仍可通过 SHA 直接访问；即使清理完成，fork、GitHub 缓存、第三方镜像、搜索引擎快照都可能留有副本。**清理历史是为了止损，不是为了抹除。**

---

## 三、检测

```bash
# 1. 历史上出现过的所有路径（含已删除）
git rev-list --all --objects | awk '{print $2}' | sort -u

# 2. 被删除过的敏感文件名
git log --all --diff-filter=D --name-only --pretty=format: \
  | grep -iE '\.env|\.pem|\.key|credential|secret|id_rsa' | sort -u

# 3. 历史内容里的密钥（慢，可加 --max-count 限制）
git log -p --all --unified=0 --max-count=500 \
  | grep -nE 'AKIA[0-9A-Z]{16}|gh[pousr]_[A-Za-z0-9]{36}|-----BEGIN .*PRIVATE KEY-----'

# 4. 某个文件在各版本里的内容
git log --all --oneline -- .env
git show <commit>:<path>
```

脚本：`python scripts/audit_repo.py . --history`

---

## 四、清理工具

### 方案 A：git filter-repo（推荐）

安装：`pip install git-filter-repo`

```bash
# 备份
git clone --mirror <repo> repo-backup.git

# 删除某个文件的所有历史
git filter-repo --path .env --invert-paths

# 批量删除
git filter-repo --path .env --path secrets.json --path id_rsa --invert-paths

# 按内容替换（谨慎，会改写所有匹配）
git filter-repo --replace-text replacements.txt
```

`replacements.txt` 格式：

```
old_secret==>***REMOVED***
regex:AKIA[0-9A-Z]{16}==>***REMOVED***
```

注意：`filter-repo` 默认要求 fresh clone，并会移除 `origin` remote，需要重新 `git remote add`。

### 方案 B：BFG Repo-Cleaner

适合超大仓库，速度快。需要 Java。

```bash
java -jar bfg.jar --delete-files .env repo.git
java -jar bfg.jar --replace-text passwords.txt repo.git
cd repo.git && git reflog expire --expire=now --all && git gc --prune=now --aggressive
```

### 方案 C：新开仓库

历史太脏（大文件多、泄露面广）时，最省事的是：建一个干净的新仓库，只导入当前快照。代价是丢掉历史。对个人项目往往是最优解。

---

## 五、推送与善后

```bash
git push --force --all
git push --force --tags
```

force push 之后必须做：

1. 通知所有协作者：**不要 merge 旧分支**，重新 clone（旧的本地历史会把脏数据推回来）。
2. 让所有人删除本地旧 clone 或执行 `git fetch --prune` 后 `git reset --hard origin/main`。
3. 检查 fork：fork 是独立仓库，你的清理不影响它们。公开仓库的 fork 无法删除。
4. GitHub 侧：旧 commit 通过 SHA 仍可能访问一段时间，可联系 GitHub Support 请求清理缓存。
5. 搜索泄露范围：GitHub 代码搜索、搜索引擎、公开的镜像/爬虫站点。
6. 复盘：为什么进了仓库，补 `.gitignore`、pre-commit hook、CI secret scanning。

---

## 六、预防

```bash
# pre-commit 钩子示例（gitleaks）
gitleaks protect --staged --verbose
```

- 安装 `gitleaks` 或 `trufflehog`，在 pre-commit 和 CI 里都跑。
- 开启 GitHub 的 Secret Scanning 与 Push Protection（公开仓库免费）。
- 密钥统一走环境变量或 Secrets，代码里只留 `.env.example` 占位符。
- `.gitignore` 在项目初始化时就写好，别等出事再补。

---

## 七、报告里怎么写

历史问题单独一节，措辞要明确后果：

> **[P0] 历史中存在私钥**：`id_rsa` 曾提交于 `a1b2c3d`（2024-05-12），当前工作区已删除，但 `git show a1b2c3d:id_rsa` 仍可读取。
> 影响：任何 clone 过该仓库的人都持有这把私钥。
> 处置：① 立即作废该密钥对并重新生成；② 用 `git filter-repo --path id_rsa --invert-paths` 清理；③ force push 并通知协作者重新 clone；④ 检查 fork 与搜索缓存。

不要写"建议删除该文件"，那会误导用户以为删了就安全。
