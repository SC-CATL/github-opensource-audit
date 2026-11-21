# 报告模板与定级示例

## 一、结论只有三种

| 结论 | 条件 |
|---|---|
| ✅ **可发布** | 无 P0/P1，P2 少量且不影响使用 |
| ⚠️ **修复后可发布** | 有 P1/P2，无 P0 |
| ❌ **不可发布** | 存在任一 P0 |

不要写"基本没问题"这种模糊结论。有 P0 就是不可发布，即使只命中一条。

---

## 二、模板

```markdown
# GitHub 开源发布审查报告

- **目标**：`<path>`
- **范围**：已跟踪 N 个文件 / 未跟踪未忽略 M 个 / 历史 K 个提交
- **本次版本许可证**：MIT（作者确认）
- **时间**：2026-11-21
- **结论**：❌ 不可发布

## 概览

| 级别 | 数量 |
|---|---|
| P0 阻断 | 2 |
| P1 高 | 3 |
| P2 中 | 4 |
| P3 建议 | 5 |

## P0 阻断（必须处理）

### 1. [SEC-PRIVKEY] 仓库内含 SSH 私钥

- **位置**：`deploy/id_rsa`
- **证据**：`-----BEGIN OPENSSH PRIVATE KEY-----`（内容已脱敏）
- **为什么危险**：私钥公开后，任何持有者都能以该身份登录服务器，且无法追溯。
- **怎么修**：
  1. 立即在服务器 `~/.ssh/authorized_keys` 中移除对应公钥；
  2. 重新生成密钥对，新私钥移出仓库；
  3. `.gitignore` 添加 `id_*` 与 `!*.pub`；
  4. 该文件已存在于历史，执行 `git filter-repo --path deploy/id_rsa --invert-paths` 后 force push。

### 2. [SEC-ENV] 生产环境变量文件被跟踪

- **位置**：`.env`
- **证据**：含 `DB_PASSWORD`、`STRIPE_SECRET`（值已脱敏）
- **为什么危险**：`git ls-files` 显示该文件已跟踪，推送即公开全部凭据。
- **怎么修**：`git rm --cached .env` → 加 `.gitignore` → 轮换全部涉及的凭据 → 提供 `.env.example`。

## P1 高（推前必须修）

### 3. [LIC-MISSING] 缺少 LICENSE 文件

- **位置**：仓库根目录
- **为什么危险**：无许可证时默认保留所有权利，任何人都不能合法使用、修改、分发你的代码。
- **怎么修**：新增 `LICENSE`，填入标准 MIT 全文，版权行 `Copyright (c) 2026 <Your Name>`；在 `package.json` 中设 `"license": "MIT"`。

### 4. [GIT-IGNORE-FAILED] 已跟踪文件违反 .gitignore

- **位置**：`dist/bundle.js`、`node_modules/lodash/index.js`（共 214 个）
- **为什么危险**：规则对已跟踪文件无效，体积与噪音会持续累积。
- **怎么修**：`git rm -r --cached dist node_modules` 后提交；确认 `.gitignore` 已包含这两项。

### 5. [SIZE-LARGE] 单文件超过 50MB

- **位置**：`assets/demo.mp4`（82.4 MB）
- **为什么危险**：超过 50MB 会收到警告，超过 100MB 直接拒绝推送；且永久留在历史里。
- **怎么修**：改用 Release 附件或 Git LFS；若已提交，需 `git filter-repo` 清理。

## P2 中（发布前解决）

### 6. [README-WEAK] README 缺少安装与示例

- **位置**：`README.md`
- **缺失**：安装方式、最小可运行示例、许可证段落
- **怎么修**：补齐 `## 安装`、`## 快速开始`、`## 许可证` 三节。

### 7. [META-MISMATCH] 许可证元数据不一致

- **位置**：`package.json` 的 `license: "ISC"`，但 `LICENSE` 正文是 MIT
- **怎么修**：统一为 `MIT`。

### 8. [SEC-PRIVIP] 源码中残留内网地址

- **位置**：`src/config.py:12`
- **证据**：`10.20.**.**`
- **怎么修**：改为 `localhost` 或环境变量。

## P3 建议

- 缺 `CHANGELOG.md`
- 缺 `.github/ISSUE_TEMPLATE/`
- 无 CI workflow
- README 无状态徽章
- 缺 `.editorconfig`

## 历史专项

（有 `--history` 时输出；无则写"未扫描历史"）

## 建议的下一步

1. 处理全部 P0 并轮换凭据（预计 30 分钟）
2. 修复 P1 三项
3. 补齐 P2
4. 重新运行 `python scripts/audit_repo.py . --history` 确认归零
```

---

## 三、定级示例

### 应该是 P0 的

- 仓库内有 `id_rsa`、`.env`、`credentials.json`
- 源码里有形如 `AKIA...` 的真实 AWS Key
- `users.csv` 含真实手机号
- 历史里出现过私钥（当前已删也算）
- 复制了客户的闭源代码
- 含 `sk_live_` 开头的 Stripe 密钥

### 应该是 P1 的

- 缺 `LICENSE`
- `.gitignore` 缺失，或已跟踪文件违反规则
- 单文件 >50MB
- `node_modules/`、`.venv/`、`dist/` 被跟踪
- 数据库 dump、`.sqlite` 文件
- 源码里有无法确认真假的硬编码口令（按 P1 起步，确认真实则升 P0）
- 第三方代码无许可证声明

### 应该是 P2 的

- README 缺安装/示例/许可证段
- 缺 `SECURITY.md`、`CONTRIBUTING.md`
- 许可证元数据不一致
- 内网 IP、内网域名残留
- `package.json` 仍是 `private: true`
- 依赖含 GPL 而项目是 MIT

### 应该是 P3 的

- 缺 `CHANGELOG.md`、Issue 模板、CI
- 缺徽章、`.editorconfig`
- 提交信息不规范

---

## 四、措辞规范

- 说后果，不说感受。写"推送后任何人可读取该私钥"，不写"这样不太好"。
- 每条都给可执行动作，带具体命令。
- 密钥一律脱敏：`AKIA****WXYZ`。
- 不确定就说不确定，并把风险级别往高了放："无法确认是否为真实数据，按 P0 处理，请确认。"
- 不要承诺"清理历史后就安全了"——已泄露的凭据必须轮换。
