---
name: GitHub 开源发布审查
description: 在项目准备开源、上传或推送到 GitHub、把私有仓库转为公开、打首个公开版本之前使用。审查是否包含不该上传的文件与内容（密钥、私钥、真实用户数据、内网地址、构建产物、大文件、版权风险），并检查开源必备要素是否齐全（LICENSE 与许可证类型、README、.gitignore、CONTRIBUTING、SECURITY 等）及元数据是否一致。用户提到「开源到 GitHub」「上传/发布/推到 GitHub」「push 到 GitHub」「这个仓库能公开吗」「开源前检查一下」「开源规范」「README/LICENSE 齐不齐」「清理敏感提交历史」时都要使用；也适用于询问项目是否适合开源、发布前还缺什么、许可证选哪种。
---

# GitHub 开源发布审查

推送之前的一道门：**先看有没有不该出去的，再看该有的有没有。**

两条结论必须分开说：**不适合公开的内容**（安全与合规）和**缺失的要素**（可用性与规范）。
一个仓库可以完全干净却没人能用，也可以要素齐全但泄露了密钥——这是两类问题，不能互相抵消。

## 何时触发

只要语义指向「把代码放到 GitHub / 公开出去」，就应使用本技能：

- 动作类：开源、开源到 GitHub、上传到 GitHub、发布到 GitHub、推到 GitHub、push 上去、提交到远程、公开仓库、私有转公开、首次发布、发版；**以及要求你直接代为建仓并推送**。
- 判断类：这个仓库能公开吗、适合开源吗、发布前还缺什么、有没有不该上传的东西。
- 规范类：开源规范、仓库结构是否标准、LICENSE 选哪种、README 该怎么写、开源清单。
- 排查类：怀疑密钥或敏感数据进了仓库、要清理提交历史、要确认历史里有没有泄露。

不触发：

- 只是给已有公开仓库写功能、改 bug、做 code review。
- 只问 Git 命令用法（如 rebase、cherry-pick 怎么做）。
- 只问 GitHub Actions 语法、Issue 模板怎么写。
- 与本仓库无关的通用法律咨询。

## 适用与不适用

适用：

- 本地项目准备首次推到 GitHub，或从私有转公开。
- 让 AI 代为 `git add . && git commit && git push` 之前的把关。
- 审查一个已有仓库是否达到开源发布标准。
- 排查"文件已删除但历史里还在"的泄露。

不适用：

- 已公开仓库的日常代码评审（用普通 review 流程）。
- 漏洞扫描、依赖 CVE 审计（那是 SCA 工具的职责，本技能只提示方向）。
- GitHub 远端运营配置（Pages、团队权限、CI 矩阵调优）——发布时只做最小验证，见 `references/github-publish.md`。

## 快速开始

```powershell
python scripts/audit_repo.py . --license MIT      # 声明本次版本许可证（每次必填）
python scripts/audit_repo.py . --history          # 连 git 历史一起查
python scripts/audit_repo.py . --md 报告.md --json 报告.json
python scripts/audit_repo.py . --max-size 20      # 大文件阈值改成 20MB
python scripts/audit_repo.py . --exclude "test/fixtures/"   # 跳过已知安全目录
```

交互式终端下不传 `--license` 会直接弹出许可证选择；CI 用 `--no-prompt`，此时未声明会报 `LIC-UNCONFIRMED`。

退出码：`0` 未发现问题，`1` 存在 P1/P2，`2` 存在 P0。可直接挂到 pre-push 钩子或 CI。

脚本只读，不改任何文件。但**脚本不等于结论**：正则只能覆盖已知模式，必须配合下面七步的人工判断。

### 误报处理

- 在项目根目录放 `.auditignore`，每行一个路径或 glob（支持 `dir/`、`*.min.js`），扫描时跳过。
- 单行豁免：在命中行加注释 `audit:allow`（或 `gitleaks:allow`、`nosec`），该行不再报警。
- 私钥规则要求头部后跟至少 40 位密钥体，纯文档示例不会误报。
- 内网 IP、域名等非凭据信息不做脱敏，方便定位。

## 审查流程

### 0. 先问许可证（每次必做）

**每次启动审查都要向作者提问，不得根据现有 LICENSE 或上一轮答案推断。**

许可证会随版本变更（MIT → Apache-2.0、加双许可、改 AGPL），旧文件只代表上一次的决定。用 `question` 工具问，选项如下：

| 选项 | 适合 | 提醒 |
|---|---|---|
| MIT（默认推荐） | 通用库与工具 | — |
| Apache-2.0 | 需要专利授权、企业采用 | 需保留 NOTICE |
| BSD-3-Clause | 与 MIT 类似 | 禁止用作者名背书 |
| MPL-2.0 / LGPL-3.0 | 弱传染 | 仅修改文件需开源 |
| GPL-3.0 / AGPL-3.0 | 强传染 | **先说明后果再让作者选** |
| Unlicense | 放弃版权 | 部分法域不完全可执行 |
| Proprietary | 保留所有权利 | 与开源目标冲突 |
| 沿用当前 LICENSE | 作者确认本次版本不变 | 仍需记录答案 |

选「沿用当前 LICENSE」时，把检测到的 SPDX（如 `MIT`）作为 `--license` 传入，并在报告里注明「沿用」。

拿到答案后：

1. 记录进报告（`--license` 会写进报告头）。
2. 带参重跑：`python scripts/audit_repo.py . --license MIT`
3. 声明与 `LICENSE` 文件不一致 → `LIC-MISMATCH`（P1）。
4. 未确认 → `LIC-UNCONFIRMED`（P2），**不能视为通过**。
5. 选 Proprietary → `LIC-PROPRIETARY`（P1），提示与开源目标冲突。

### 1. 确定范围

三个范围结论可能完全不同，报告里要分别写明：

| 范围 | 怎么看 | 含义 |
|---|---|---|
| 工作区 | 磁盘上实际文件 | 你本地有什么 |
| 已跟踪 | `git ls-files` | 这次 push 真的会传上去什么 |
| 未跟踪未忽略 | `git ls-files --others --exclude-standard` | `git add .` 会顺手带上去什么 |
| 历史 | `git log --all` | 以前传过、现在删了也还在的东西 |

最容易被忽略的是**第四行**。删掉文件再提交，历史里照样能 `git show` 出来。

### 2. 敏感内容扫描

先跑脚本，再人工复核命中项。重点看：

- 凭据文件：`.env`、`*.pem`、`*.key`、`id_rsa`、`credentials.json`、service account JSON、keystore、`.npmrc`、`.pypirc`、`.netrc`、kubeconfig、terraform state
- 代码内硬编码：`AKIA…`、`ghp_/gho_/ghs_`、`sk-…`、`xox…`、`AIza…`、`sk_live_`、JWT、`BEGIN PRIVATE KEY`
- 通用赋值：`password = "..."`、`token: "..."`、`api_key=...`——脚本会报，但需要人判断是不是占位符
- 个人与客户数据：真实手机号、身份证、邮箱名单、订单/工单导出、数据库 dump、带真实数据的 fixture
- 内网痕迹：`10./172.16-31./192.168.` 地址、`.local/.corp/.internal` 域名、内部系统 URL、公司内网 Git 地址

细节见 `references/forbidden-content.md`。

### 3. 垃圾与产物扫描

- 依赖与构建：`node_modules`、`dist`、`build`、`target`、`.venv`、`__pycache__`、`*.egg-info`、`.next`
- 系统与编辑器：`.DS_Store`、`Thumbs.db`、`desktop.ini`、`.idea`、`.vscode/settings.json`
- 数据文件：`*.db`、`*.sqlite`、`*.dump`、`*.bak`
- 大文件：>5MB 提示、>50MB 告警、>100MB 直接阻断（GitHub 硬限制）
- **ignore 失效**：`git ls-files -ci --exclude-standard` —— 已经被跟踪、但规则说该忽略的文件。这是最常见的坑，改 `.gitignore` 对已跟踪文件无效，必须 `git rm --cached`。

### 4. 必备文件矩阵

必需（缺了就是 P1）：`README.md`、`LICENSE`、`.gitignore`。

社区型项目应备：`CONTRIBUTING.md`、`CODE_OF_CONDUCT.md`、`SECURITY.md`、`CHANGELOG.md`、Issue/PR 模板、CI workflow。

按项目类型追加：`NOTICE`（内含第三方代码）、`CITATION.cff`（学术）、`docs/`、`Dockerfile`、`.editorconfig`、`.gitattributes`。

判断标准与每个文件的最小内容见 `references/required-files.md`。

### 5. 一致性校验

- `LICENSE` 正文 ↔ 实际许可证类型 ↔ README 里的许可证段落 ↔ 包清单的 `license` 字段，四处必须一致
- **没有 LICENSE 不等于"随便用"**，而是保留所有权利，任何人都不能合法使用——这一点必须显式告诉用户
- 包清单的 `name`、`repository`、`author` 是否指向真实仓库
- `package.json` 的 `private: true` 说明这是私有包配置，开源前要改
- 依赖许可证是否与本项目冲突（GPL/AGPL 传染）

许可证细则见 `references/licenses.md`。

### 6. 历史扫描

```bash
# 历史上出现过的所有路径（含已删除）
git rev-list --all --objects | awk '{print $2}' | sort -u

# 历史上出现过的敏感文件名
git log --all --diff-filter=D --name-only --pretty=format: | sort -u

# 历史内容里搜密钥（较慢）
git log -p --all --unified=0 | grep -nE 'AKIA[0-9A-Z]{16}|gh[pousr]_|BEGIN .*PRIVATE KEY'
```

命中后的处置顺序**不能颠倒**：先轮换/吊销密钥，再清理历史。只清历史不轮换，密钥照样是泄露状态。

具体步骤见 `references/history-cleanup.md`。

### 7. 出报告

按 `references/report-template.md` 输出，必须包含：

1. 本次版本许可证（作者确认的答案，不是文件检测结果）
2. 一句话结论：可直接发布 / 修复后发布 / 不可发布
3. 分级计数表
4. 每条问题：级别、位置（文件:行）、证据（脱敏）、为什么危险、怎么修
5. 历史相关的问题单独成节

## 发布执行与验证

只在用户要求**真正发布**时执行；只问「能不能公开」则停在审查这一步。

### 前置检查（一次性）

| 项 | 命令 | 失败后果 |
|---|---|---|
| gh 可用 | `gh --version` | 无法建仓 |
| 已登录 | `gh auth status` | push 失败 |
| token 含 `workflow` scope | 看 `gh auth status` 的 scopes 行 | 整次 push 被拒 |
| git 凭据助手 | `git config --global --get-regexp credential` | push 挂起等密码 |
| git 身份 | `git config user.name` / `user.email` | commit 失败或作者错误（见下节自动同步） |

仓库里有 `.github/workflows/*` 时必须额外授权：

```bash
gh auth refresh -s workflow
```

否则报 `refusing to allow an OAuth App to create or update workflow`。这是 OAuth App 的 scope 限制，仓库 owner 也一样被拒。

非交互环境先设 `GIT_TERMINAL_PROMPT=0`，让缺凭据时快速失败而不是挂起。

### git 身份：连接 GitHub 后同步

**时机**（只在这四个节点，写入永远需要确认）

| 场景 | 动作 |
|---|---|
| `gh auth login` 之后、首次发布前 | 只读检测；缺失则询问是否用 GitHub 账号同步 |
| 每次发布前的前置检查 | 只读检测；缺失即暂停，不静默写入 |
| 审计阶段 | 只读检测，命中报 `GIT-IDENTITY`（P2） |
| 用户主动要求 | 直接运行脚本 |

**方式**

1. `gh api user` 取 `login`、`id`、`name`、`email`
2. `user.name` = `name`，为空回退 `login`
3. `user.email` 默认用 `{id}+{login}@users.noreply.github.com`（noreply，保护隐私）；加 `--public-email` 才用账号公开邮箱
4. 默认写全局，`--local` 只写当前仓库
5. 幂等：已是期望值就不写；新旧 noreply 格式（带 id / 不带 id）视为等价

```bash
python scripts/git_identity.py            # 只读预览，需要写入时退出码 2
python scripts/git_identity.py --apply    # 写入全局
python scripts/git_identity.py --apply --local
```

已有身份与 GitHub 账号不一致时**只提示不覆盖**，因为可能是有意使用公司或个人身份。

### 创建与推送

```bash
gh repo create <owner>/<name> --public --source . --remote origin --push --description "<一句话>"
gh repo edit <owner>/<name> --add-topic topic1,topic2
```

`--push` 失败时仓库**已经创建**，重试只需 `git push -u origin main`，不要重复 `repo create`。

### 验证（不可跳过）

创建成功 ≠ 发布成功。逐项确认：

- 可见性 `PUBLIC`、默认分支 `main`
- 远端文件齐全（含 `LICENSE`、`README.md`、`.github/`）
- `gh api repos/{o}/{r}/license` 能识别出 SPDX
- Topics 已设置
- 第一次 CI 为 `success`
- tag / Release 已发布

### 本地绿 ≠ 远端绿

本地可能走「非 git 降级扫描」，CI 必然走 git 模式，历史范围也不同。
发布后必须看 CI：`gh run view <id> --log-failed`。

**同一套检测逻辑必须在工作区、已跟踪、历史三条路径复用**，否则必然出现本地过、CI 挂。

完整排查表与分支保护配置见 `references/github-publish.md`。

## 分级

| 级别 | 含义 | 处理 |
|---|---|---|
| P0 阻断 | 绝不能推：私钥、有效令牌、真实用户数据、商业代码、客户名单 | 修完并轮换密钥后才能继续 |
| P1 高 | 推前必须修：缺 LICENSE、大文件、构建产物入库、ignore 失效、数据文件 | 本次提交内解决 |
| P2 中 | 影响可用性与信任：README 缺安装/示例、缺 SECURITY、元数据不一致、内网地址残留 | 发布前解决 |
| P3 建议 | 锦上添花：CHANGELOG、模板、badges、.editorconfig | 排期即可 |

## 红线

- **每次审查都要问许可证**，不得用已有 `LICENSE`、包清单字段或上一轮答案代替提问。
- 报告里的密钥一律脱敏，只显示首尾各 4 位。不要把完整密钥再写进任何文件。
- 默认只读。删除文件、`git rm --cached`、改写历史、force push 都必须先说明后果并得到确认。
- 不要建议"直接删掉 `.env` 就安全了"——已经提交过的，先轮换。
- 不确定是否为真实数据的，按 P0 处理并让用户确认，不要自行判定为"测试数据"。
- 脚本退出码为 0 不代表可以发布，只代表没命中已知模式。
- **在非交互环境直接跑 `git push` 前，先确认凭据助手已配置**，否则会挂起而不是报错。
- **不要静默改写已有的 git 身份**，同步必须经用户确认后加 `--apply`。
- **缺 `workflow` scope 时不要反复重试 push**，那会一直失败；先 `gh auth refresh -s workflow`。
- **发布后必须看第一次 CI**，本地绿不等于远端绿。

## 参考

- `references/forbidden-content.md` —— 不该上传的内容清单与识别方法
- `references/required-files.md` —— 必备文件矩阵与各文件最小内容
- `references/licenses.md` —— 许可证选择、SPDX、常见错误
- `references/history-cleanup.md` —— 历史泄露的处置流程
- `references/github-publish.md` —— 认证、workflow scope、推送排查、远端验证
- `references/report-template.md` —— 报告模板与定级示例
- `scripts/audit_repo.py` —— 只读扫描脚本
